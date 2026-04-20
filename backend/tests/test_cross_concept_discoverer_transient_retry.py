"""Transient-error auto-retry at the chunk level (P4 step 3 of Discover V2).

Today's real production log showed a bailian ``Connection error.`` failing
a whole chunk mid-discover. With no auto-retry the user's only recovery
path was the UI "重试" button on the partial/failed job. That's fine for
human-caused bugs but wasteful for network blips.

GPT consult 2026-04-17 recommended whitelisted chunk-level retry. The
rules these tests lock in:

1. Transient errors (Connection / timeout / 5xx gateway errors) retry
   up to ``_CHUNK_MAX_RETRIES`` times with exponential backoff before
   the chunk is finally marked failed.
2. Non-transient errors (JSON parse, ValueError, KeyError, etc.) do
   NOT retry — those are real bugs, retrying just burns tokens.
3. When an eventually-successful retry saves a chunk, its relations
   go through the serial-commit loop unchanged.
4. The final ``result`` reports how many chunk retries happened, so
   the Theme page / A/B dashboard can see retry churn trending.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


FAKE_THEME = {"concept_memberships": [{"entry_id": "e1"}, {"entry_id": "e2"}]}


def _mk_concept(entry_id: str, project_id: str, ctype: str = "Topic") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": f"name-{entry_id}",
        "concept_type": ctype,
        "description": "d",
        "source_links": [{"project_id": project_id, "project_name": project_id}],
    }


@pytest.fixture
def isolated_relations(tmp_path: Path, monkeypatch):
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))


class TestIsTransientError:
    def test_connection_error_text_is_transient(self):
        from app.services.auto.cross_concept_discoverer import _is_transient_error

        assert _is_transient_error(Exception("Connection error.")) is True
        assert _is_transient_error(Exception("ConnectionError: reset")) is True

    def test_timeout_is_transient(self):
        from app.services.auto.cross_concept_discoverer import _is_transient_error

        assert _is_transient_error(Exception("Request timed out")) is True
        assert _is_transient_error(TimeoutError("x")) is True

    def test_5xx_gateway_texts_are_transient(self):
        from app.services.auto.cross_concept_discoverer import _is_transient_error

        assert _is_transient_error(Exception("502 Bad Gateway")) is True
        assert _is_transient_error(Exception("503 Service Unavailable")) is True
        assert _is_transient_error(Exception("504 Gateway Timeout")) is True

    def test_json_and_value_errors_are_not_transient(self):
        from app.services.auto.cross_concept_discoverer import _is_transient_error

        import json as _json
        assert _is_transient_error(ValueError("bad literal")) is False
        assert _is_transient_error(KeyError("missing")) is False
        assert _is_transient_error(_json.JSONDecodeError("bad", "doc", 0)) is False

    def test_builtin_connection_error_class_is_transient(self):
        from app.services.auto.cross_concept_discoverer import _is_transient_error

        assert _is_transient_error(ConnectionError("reset")) is True


class TestChunkRetryOnTransient:
    def _fake_entries(self):
        return [
            _mk_concept("e1", "proj_a", "Problem"),
            _mk_concept("e2", "proj_b", "Solution"),
        ]

    def test_transient_failure_retries_and_succeeds(self, isolated_relations):
        """First _llm_judge call raises a connection error; retry succeeds.
        The chunk's relations should land, and the final report should
        note the retry."""
        d = CrossConceptDiscoverer()

        call_count = {"n": 0}

        def flaky_judge(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Connection error.")
            # Second call: return one relation.
            return [
                {
                    "source_entry_id": "e1",
                    "target_entry_id": "e2",
                    "relation_type": "problem_solution",
                    "directionality": "directed",
                    "reason": "ok",
                    "evidence_bridge": "",
                    "evidence_refs": [],
                    "discovery_path": [],
                    "confidence": 0.8,
                    "model_info": {"model": "test", "prompt_version": "v1"},
                }
            ]

        with (
            patch(
                "app.services.auto.cross_concept_discoverer.themes.get_theme",
                return_value=FAKE_THEME,
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.themes.record_discovery_run"
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.registry.list_entries",
                return_value=self._fake_entries(),
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.load_existing_dedupe_keys",
                return_value=set(),
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.create_relation"
            ) as mock_create,
            # Make retry delays zero-length so tests stay fast.
            patch(
                "app.services.auto.cross_concept_discoverer._CHUNK_RETRY_BACKOFF",
                [0.0, 0.0],
            ),
            patch.object(
                CrossConceptDiscoverer, "_llm_judge", side_effect=flaky_judge
            ),
        ):
            result = d.discover(theme_id="t", new_entry_ids=["e1"], run_id="r")

        assert call_count["n"] == 2  # one flaky failure + one retry
        assert result["discovered"] == 1
        assert mock_create.call_count == 1
        assert result.get("llm_chunks_retried", 0) == 1
        assert result["llm_chunks_failed"] == 0

    def test_persistent_transient_exhausts_retries_and_fails_chunk(
        self, isolated_relations
    ):
        d = CrossConceptDiscoverer()
        call_count = {"n": 0}

        def always_flaky(*a, **kw):
            call_count["n"] += 1
            raise Exception("Connection error.")

        with (
            patch(
                "app.services.auto.cross_concept_discoverer.themes.get_theme",
                return_value=FAKE_THEME,
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.themes.record_discovery_run"
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.registry.list_entries",
                return_value=self._fake_entries(),
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.load_existing_dedupe_keys",
                return_value=set(),
            ),
            patch(
                "app.services.auto.cross_concept_discoverer._CHUNK_RETRY_BACKOFF",
                [0.0, 0.0],
            ),
            patch.object(
                CrossConceptDiscoverer, "_llm_judge", side_effect=always_flaky
            ),
        ):
            result = d.discover(theme_id="t", new_entry_ids=["e1"], run_id="r")

        # _CHUNK_MAX_RETRIES=2 means 1 initial + 2 retries = 3 total calls.
        assert call_count["n"] == 3
        assert result["discovered"] == 0
        assert result["llm_chunks_failed"] == 1
        # The retry count reported is how many retries were attempted.
        assert result.get("llm_chunks_retried", 0) == 2
        # The error is surfaced once (after retries exhaust), not N times.
        assert len(result["errors"]) == 1
        assert "Connection" in result["errors"][0]

    def test_non_transient_error_does_not_retry(self, isolated_relations):
        d = CrossConceptDiscoverer()
        call_count = {"n": 0}

        def value_bug(*a, **kw):
            call_count["n"] += 1
            raise ValueError("malformed LLM response: expected key 'confidence'")

        with (
            patch(
                "app.services.auto.cross_concept_discoverer.themes.get_theme",
                return_value=FAKE_THEME,
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.themes.record_discovery_run"
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.registry.list_entries",
                return_value=self._fake_entries(),
            ),
            patch(
                "app.services.auto.cross_concept_discoverer.load_existing_dedupe_keys",
                return_value=set(),
            ),
            patch(
                "app.services.auto.cross_concept_discoverer._CHUNK_RETRY_BACKOFF",
                [0.0, 0.0],
            ),
            patch.object(
                CrossConceptDiscoverer, "_llm_judge", side_effect=value_bug
            ),
        ):
            result = d.discover(theme_id="t", new_entry_ids=["e1"], run_id="r")

        # Exactly one call — non-transient, no retry.
        assert call_count["n"] == 1
        assert result["llm_chunks_failed"] == 1
        assert result.get("llm_chunks_retried", 0) == 0
