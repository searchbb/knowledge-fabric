"""Old-data backward-compat regression (GPT audit 2026-04-17).

Every new field added in this Discover V2 round (``run_id``, ``job_id``
on relations; ``discovery_history`` on themes) is optional by design,
but "optional" only works if every reader uses ``.get()`` with a
default. GPT flagged the risk that a hot reader might assume these
fields exist and KeyError on pre-session data.

This test seeds JSON files shaped like *before* this session's edits,
exercises the main read paths, and asserts nothing crashes. The point
isn't to check semantic correctness — it's to prove that opening an old
deployment's data files doesn't raise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def old_world(tmp_path: Path, monkeypatch):
    """Seed projects/ with pre-Discover-V2-shaped JSON files and redirect
    Config.UPLOAD_FOLDER at them."""
    from app import config as config_module

    uploads = tmp_path / "uploads"
    projects = uploads / "projects"
    projects.mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))

    # Old-style cross_concept_relations.json — no ``run_id`` / ``job_id``.
    (projects / "cross_concept_relations.json").write_text(
        json.dumps({
            "version": 1,
            "relations": {
                "crel_old1": {
                    "relation_id": "crel_old1",
                    "source_entry_id": "canon_a",
                    "target_entry_id": "canon_b",
                    "relation_type": "design_inspiration",
                    "directionality": "directed",
                    "reason": "old data",
                    "evidence_bridge": "",
                    "evidence_refs": [],
                    "discovery_path": [],
                    "confidence": 0.7,
                    "source": "auto",
                    "status": "active",
                    "review_status": "unreviewed",
                    "dedupe_key": "canon_a|design_inspiration|canon_b",
                    "theme_id": "gtheme_old",
                    "model_info": None,
                    # Deliberately no run_id, no job_id.
                    "created_at": "2026-03-01T00:00:00",
                    "updated_at": "2026-03-01T00:00:00",
                },
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Old-style global_themes.json — no ``discovery_history``, no
    # ``discovery_coverage``.
    (projects / "global_themes.json").write_text(
        json.dumps({
            "version": 2,
            "themes": {
                "gtheme_old": {
                    "theme_id": "gtheme_old",
                    "name": "Pre-V2 theme",
                    "slug": "pre-v2-theme",
                    "description": "",
                    "status": "active",
                    "source": "user",
                    "keywords": [],
                    "concept_memberships": [
                        {"entry_id": "canon_a", "role": "member", "score": 1.0,
                         "source": "seed", "assigned_at": "2026-03-01T00:00:00"},
                    ],
                    "source_project_clusters": [],
                    "evidence_refs": [],
                    "created_at": "2026-03-01T00:00:00",
                    "updated_at": "2026-03-01T00:00:00",
                },
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return uploads


class TestRelationReadersTolerateMissingProvenance:
    def test_list_relations_does_not_crash_on_old_rows(self, old_world):
        from app.services.registry.cross_concept_relations import list_relations

        rels = list_relations()
        assert len(rels) == 1
        # run_id/job_id aren't on the old row — readers should .get()
        # and return None / empty, not KeyError.
        r = rels[0]
        assert r.get("run_id", "") in ("", None)
        assert r.get("job_id", None) is None

    def test_has_dedupe_key_reads_old_rows(self, old_world):
        from app.services.registry.cross_concept_relations import has_dedupe_key

        assert has_dedupe_key("canon_a|design_inspiration|canon_b") is True
        assert has_dedupe_key("canon_x|design_inspiration|canon_y") is False

    def test_load_existing_dedupe_keys_sees_old_rows(self, old_world):
        from app.services.registry.cross_concept_relations import (
            load_existing_dedupe_keys,
        )

        keys = load_existing_dedupe_keys()
        assert "canon_a|design_inspiration|canon_b" in keys


class TestThemeReadersTolerateMissingHistory:
    def test_get_theme_on_old_theme(self, old_world):
        from app.services.registry.global_theme_registry import get_theme

        theme = get_theme("gtheme_old")
        # Legacy field should be absent; no KeyError.
        assert "discovery_history" not in theme or theme["discovery_history"] == []
        assert "discovery_coverage" not in theme or theme["discovery_coverage"] == {}

    def test_get_discovery_history_on_old_theme_returns_empty(self, old_world):
        from app.services.registry.global_theme_registry import get_discovery_history

        assert get_discovery_history("gtheme_old") == []

    def test_record_discovery_run_upgrades_shape_in_place(self, old_world):
        """First discover run on an old theme should: (a) succeed,
        (b) create the missing ``discovery_history`` field, (c) not
        remove any existing data."""
        from app.services.registry.global_theme_registry import (
            record_discovery_run,
            get_theme,
            get_discovery_history,
        )

        record_discovery_run(
            "gtheme_old",
            stats={
                "discovered": 1,
                "candidates_count": 1,
                "skipped": 0,
                "errors": [],
                "reason": "first run post-upgrade",
                "funnel": {"final": 1, "committed": 1},
            },
            job_id="djob_first",
        )
        theme = get_theme("gtheme_old")
        # Original membership preserved.
        assert len(theme["concept_memberships"]) == 1
        # History now present.
        hist = get_discovery_history("gtheme_old")
        assert len(hist) == 1
        assert hist[0]["job_id"] == "djob_first"


class TestCrossConceptDiscovererToleratesOldRelations:
    def test_stage1_recall_still_dedupes_against_old_rows(self, old_world):
        """The Stage-1 dedupe preload reads old relations just as well as
        new ones — a relation without run_id/job_id is still a valid
        dedupe key."""
        from app.services.auto.cross_concept_discoverer import (
            CrossConceptDiscoverer,
        )

        def _c(eid, proj):
            return {
                "entry_id": eid,
                "canonical_name": eid,
                "concept_type": "Topic",
                "description": "",
                "source_links": [{"project_id": proj}],
            }

        d = CrossConceptDiscoverer()
        concepts = [
            _c("canon_a", "proj_1"),
            _c("canon_b", "proj_2"),
            _c("canon_c", "proj_3"),
        ]
        _, funnel = d._recall_candidates(
            concepts, exclude_existing=True, return_funnel=True
        )
        # The old (canon_a, canon_b) key is in the dedupe set, so only
        # (canon_a, canon_c) and (canon_b, canon_c) survive.
        assert funnel["after_dedupe_filter"] == 2
        assert funnel["final"] == 2
