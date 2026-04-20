"""Rolling discovery history on themes (P4 step 2 of Discover V2).

``record_discovery_run`` used to overwrite the latest stats blob each call,
so a Theme page could answer "how did the last run go?" but not "is
recall getting better across runs?". For the upcoming embedding A/B
cutover to be measurable we need to keep the last N runs keyed by job
so dashboards can diff funnel counts over time.

Contract:

- ``discovery_coverage`` (single dict, backward-compat) stays — still the
  latest run's stats.
- ``discovery_history`` (new, list, most-recent first) carries the last
  N runs. Each entry contains a minimal, stable set of fields — enough
  for Theme UI + A/B diffing, NOT the full raw stats blob (which can
  contain model payloads / errors of unbounded length).
- History is capped; the oldest entries roll off silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def isolated_themes(tmp_path: Path, monkeypatch):
    """Point the theme registry at a scratch JSON store by redirecting
    Config.UPLOAD_FOLDER — _themes_path() is derived from it."""
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))
    return uploads / "projects" / "global_themes.json"


def _seed_theme(path: Path, theme_id: str = "gtheme_t1") -> None:
    store = {
        "version": 2,
        "themes": {
            theme_id: {
                "theme_id": theme_id,
                "name": "Test theme",
                "concept_memberships": [],
            }
        },
    }
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2))


def _sample_stats(*, discovered: int = 1, sent_to_llm: int = 5) -> dict:
    return {
        "candidates_count": sent_to_llm,
        "discovered": discovered,
        "skipped": 0,
        "errors": [],
        "reason": "test",
        "funnel": {
            "raw_pairs": 20,
            "after_incremental_gate": 10,
            "after_cross_article": 8,
            "after_dedupe_filter": sent_to_llm,
            "final": sent_to_llm,
            "sent_to_llm": sent_to_llm,
            "llm_accepted": discovered,
            "deduped_on_commit": 0,
            "committed": discovered,
        },
    }


class TestDiscoveryHistoryRolling:
    def test_first_run_seeds_history_with_one_entry(self, isolated_themes):
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_theme,
        )

        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=3), job_id="djob_a"
        )
        theme = get_theme("gtheme_t1")
        history = theme.get("discovery_history") or []
        assert len(history) == 1
        assert history[0]["job_id"] == "djob_a"
        assert history[0]["discovered"] == 3
        # Funnel is preserved (subset is fine — we copy the whole funnel).
        assert history[0]["funnel"]["raw_pairs"] == 20
        assert history[0]["funnel"]["sent_to_llm"] == 5

    def test_history_is_most_recent_first(self, isolated_themes):
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_theme,
        )

        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=1), job_id="djob_old"
        )
        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=2), job_id="djob_mid"
        )
        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=3), job_id="djob_new"
        )
        history = get_theme("gtheme_t1")["discovery_history"]
        assert [h["job_id"] for h in history] == [
            "djob_new",
            "djob_mid",
            "djob_old",
        ]

    def test_history_caps_at_default_max(self, isolated_themes):
        """Default cap is 10. Extra runs roll off the oldest entries."""
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_theme,
        )

        for i in range(15):
            record_discovery_run(
                "gtheme_t1",
                stats=_sample_stats(discovered=i),
                job_id=f"djob_{i:02d}",
            )
        history = get_theme("gtheme_t1")["discovery_history"]
        assert len(history) == 10
        # Keeps the 10 most recent (indexes 5..14 descending).
        assert history[0]["job_id"] == "djob_14"
        assert history[-1]["job_id"] == "djob_05"

    def test_history_entry_is_minimal_bounded(self, isolated_themes):
        """Raw stats may contain LLM payloads / long error strings. History
        should store a bounded subset so the themes JSON doesn't bloat."""
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_theme,
        )

        big_errors = ["very long error " * 100] * 20  # 20 × ~1.5k chars
        record_discovery_run(
            "gtheme_t1",
            stats={**_sample_stats(discovered=1), "errors": big_errors},
            job_id="djob_big",
        )
        history = get_theme("gtheme_t1")["discovery_history"]
        entry = history[0]
        # The entry captures the error COUNT but not the raw list.
        assert entry["errors_count"] == 20
        assert "errors" not in entry

    def test_coverage_still_reflects_latest_for_backcompat(self, isolated_themes):
        """discovery_coverage is the existing UI field — keep it working."""
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_theme,
        )

        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=1), job_id="djob_old"
        )
        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=7), job_id="djob_new"
        )
        coverage = get_theme("gtheme_t1")["discovery_coverage"]
        assert coverage["discovered"] == 7


class TestDiscoveryHistoryAccessor:
    """A convenience getter so callers don't have to know the nested key path."""

    def test_get_discovery_history_returns_list(self, isolated_themes):
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_discovery_history,
        )

        record_discovery_run(
            "gtheme_t1", stats=_sample_stats(discovered=1), job_id="djob_a"
        )
        history = get_discovery_history("gtheme_t1")
        assert isinstance(history, list)
        assert history[0]["job_id"] == "djob_a"

    def test_get_discovery_history_for_unknown_theme_raises(self, isolated_themes):
        from app.services.registry.global_theme_registry import (
            get_discovery_history,
            GlobalThemeNotFoundError,
        )

        with pytest.raises(GlobalThemeNotFoundError):
            get_discovery_history("gtheme_ghost")

    def test_get_discovery_history_empty_for_theme_never_run(self, isolated_themes):
        _seed_theme(isolated_themes)
        from app.services.registry.global_theme_registry import get_discovery_history

        assert get_discovery_history("gtheme_t1") == []
