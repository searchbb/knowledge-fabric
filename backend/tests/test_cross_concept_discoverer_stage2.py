"""Tests for Stage 2 (concurrent LLM judge + serial commit) of CrossConceptDiscoverer.

Added 2026-04-16: covers the parallel _llm_judge refactor.
Three scenarios:
  1. Happy path — all chunks succeed, relations committed in order
  2. Soft-fail — one chunk's LLM call raises, others still commit
  3. Observability — summary.discover carries the new chunk-level fields
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _concept(entry_id: str, project_id: str, ctype: str = "Topic") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": f"name-{entry_id}",
        "concept_type": ctype,
        "description": f"description for {entry_id}",
        "source_links": [{"project_id": project_id, "project_name": project_id}],
    }


def _fake_theme(entry_ids: list[str]) -> dict:
    return {"concept_memberships": [{"entry_id": eid} for eid in entry_ids]}


def _rel(src: str, tgt: str) -> dict:
    """Minimal relation payload as returned by _llm_judge."""
    return {
        "source_entry_id": src,
        "target_entry_id": tgt,
        "relation_type": "problem_solution",
        "directionality": "directed",
        "reason": "test reason",
        "evidence_bridge": "test bridge",
        "evidence_refs": [],
        "discovery_path": [src, tgt],
        "confidence": 0.9,
        "model_info": {"model": "test-model", "prompt_version": "crossrel_v1"},
    }


# Common patches shared across all Stage 2 tests
_COMMON_PATCHES = {
    "themes": "app.services.auto.cross_concept_discoverer.themes",
    "registry": "app.services.auto.cross_concept_discoverer.registry",
    "has_dedupe_key": "app.services.auto.cross_concept_discoverer.has_dedupe_key",
    "create_relation": "app.services.auto.cross_concept_discoverer.create_relation",
    "record_discovery_run": None,  # handled separately per test
    "llm_params": "app.services.auto.cross_concept_discoverer.get_graphiti_llm_params",
}


# ---------------------------------------------------------------------------
# Test 1: happy path — all chunks succeed
# ---------------------------------------------------------------------------

def test_stage2_all_chunks_succeed_commits_all_relations():
    """All LLM chunks return relations; every relation is committed serially."""
    # 4 concepts from 4 different articles → 6 pairs → 1 chunk (< 10)
    entries = [
        _concept("e1", "p1", "Problem"),
        _concept("e2", "p2", "Solution"),
        _concept("e3", "p3", "Topic"),
        _concept("e4", "p4", "Technology"),
    ]
    fake_theme = _fake_theme(["e1", "e2", "e3", "e4"])

    # _llm_judge returns 2 relations for the single chunk
    expected_relations = [_rel("e1", "e2"), _rel("e3", "e4")]

    d = CrossConceptDiscoverer()

    with (
        patch("app.services.auto.cross_concept_discoverer.themes.get_theme", return_value=fake_theme),
        patch("app.services.auto.cross_concept_discoverer.themes.record_discovery_run"),
        patch("app.services.auto.cross_concept_discoverer.registry.list_entries", return_value=entries),
        patch("app.services.auto.cross_concept_discoverer.has_dedupe_key", return_value=False),
        patch("app.services.auto.cross_concept_discoverer.create_relation") as mock_create,
        patch.object(d, "_llm_judge", return_value=expected_relations) as mock_judge,
        patch("app.services.llm_mode_service.get_graphiti_llm_params",
              return_value={"semaphore_limit": 4, "provider": "test", "model": "test-model"}),
    ):
        result = d.discover(theme_id="t1", new_entry_ids=["e1", "e3"], run_id="r1")

    assert result["discovered"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == []
    assert mock_create.call_count == 2
    # _llm_judge was called exactly once (one chunk)
    assert mock_judge.call_count == 1


# ---------------------------------------------------------------------------
# Test 2: soft-fail — one chunk raises, others succeed
# ---------------------------------------------------------------------------

def test_stage2_one_chunk_fails_others_commit():
    """A failing chunk is recorded in errors/failed_chunk_indices but does
    NOT abort the remaining chunks or mark discover as a hard failure."""
    # Build enough concepts to produce 2 chunks (11–20 pairs → 2 chunks)
    # Use 6 concepts from 6 articles → 15 pairs → 2 chunks (10 + 5)
    entries = [_concept(f"e{i}", f"p{i}", "Topic") for i in range(1, 7)]
    entry_ids = [e["entry_id"] for e in entries]
    fake_theme = _fake_theme(entry_ids)

    d = CrossConceptDiscoverer()

    call_count = {"n": 0}

    def _selective_judge(candidates, min_confidence, *, graph_cache, chunk_idx):
        call_count["n"] += 1
        if chunk_idx == 0:
            raise RuntimeError("simulated LLM failure on chunk 0")
        # chunk 1 succeeds with one relation
        a = candidates[0]["concept_a"]["entry_id"]
        b = candidates[0]["concept_b"]["entry_id"]
        return [_rel(a, b)]

    with (
        patch("app.services.auto.cross_concept_discoverer.themes.get_theme", return_value=fake_theme),
        patch("app.services.auto.cross_concept_discoverer.themes.record_discovery_run"),
        patch("app.services.auto.cross_concept_discoverer.registry.list_entries", return_value=entries),
        patch("app.services.auto.cross_concept_discoverer.has_dedupe_key", return_value=False),
        patch("app.services.auto.cross_concept_discoverer.create_relation") as mock_create,
        patch.object(d, "_llm_judge", side_effect=_selective_judge),
        patch("app.services.llm_mode_service.get_graphiti_llm_params",
              return_value={"semaphore_limit": 4, "provider": "test", "model": "test-model"}),
    ):
        result = d.discover(theme_id="t2", run_id="r2")

    # chunk 0 failed — should be recorded
    assert result["llm_chunks_failed"] == 1
    assert 0 in result["failed_chunk_indices"]
    assert any("chunk 0" in e for e in result["errors"])

    # chunk 1 succeeded — its relation was committed
    assert result["discovered"] == 1
    assert mock_create.call_count == 1

    # discover itself did NOT raise — soft-fail preserved
    assert "candidates_count" in result


# ---------------------------------------------------------------------------
# Test 3: observability fields present in summary
# ---------------------------------------------------------------------------

def test_stage2_result_contains_chunk_observability_fields():
    """summary.discover must carry all chunk-level observability fields."""
    entries = [
        _concept("e1", "p1", "Problem"),
        _concept("e2", "p2", "Solution"),
    ]
    fake_theme = _fake_theme(["e1", "e2"])

    d = CrossConceptDiscoverer()

    with (
        patch("app.services.auto.cross_concept_discoverer.themes.get_theme", return_value=fake_theme),
        patch("app.services.auto.cross_concept_discoverer.themes.record_discovery_run"),
        patch("app.services.auto.cross_concept_discoverer.registry.list_entries", return_value=entries),
        patch("app.services.auto.cross_concept_discoverer.has_dedupe_key", return_value=False),
        patch("app.services.auto.cross_concept_discoverer.create_relation"),
        patch.object(d, "_llm_judge", return_value=[]),
        patch("app.services.llm_mode_service.get_graphiti_llm_params",
              return_value={"semaphore_limit": 6, "provider": "bailian", "model": "qwen3.5-plus"}),
    ):
        result = d.discover(theme_id="t3", new_entry_ids=["e1"], run_id="r3")

    required_fields = {
        "llm_chunks_total",
        "llm_chunks_succeeded",
        "llm_chunks_failed",
        "llm_max_workers",
        "failed_chunk_indices",
        "llm_provider",
        "llm_model",
        "llm_max_tokens",
    }
    missing = required_fields - result.keys()
    assert not missing, f"Missing fields: {missing}"

    assert result["llm_provider"] == "bailian"
    assert result["llm_model"] == "qwen3.5-plus"
    assert result["llm_max_tokens"] == 1500
    assert result["llm_max_workers"] >= 1
    assert isinstance(result["failed_chunk_indices"], list)


def test_llm_judge_uses_discover_specific_timeout_and_disables_client_retries(monkeypatch):
    candidate = {
        "concept_a": _concept("e1", "p1", "Problem"),
        "concept_b": _concept("e2", "p2", "Solution"),
    }
    d = CrossConceptDiscoverer()
    created = {}

    class _FakeLLMClient:
        def __init__(self, api_key=None, base_url=None, model=None):
            created["client"] = self
            self.api_key = api_key
            self.base_url = base_url
            self.model = model
            self.timeout_seconds = None
            self.max_retries = None

        def chat_json(self, messages, temperature=0.2, max_tokens=1500):
            return {"relations": []}

    monkeypatch.setenv("DISCOVER_LLM_TIMEOUT_SECONDS", "77")
    monkeypatch.setattr(
        "app.utils.llm_client.LLMClient",
        _FakeLLMClient,
    )

    with patch(
        "app.services.llm_mode_service.get_graphiti_llm_params",
        return_value={
            "api_key": "k",
            "base_url": "http://llm.local/v1",
            "model": "test-model",
            "semaphore_limit": 4,
        },
    ):
        result = d._llm_judge(
            [candidate],
            0.6,
            graph_cache=MagicMock(),
            chunk_idx=0,
        )

    assert result == []
    assert created["client"].timeout_seconds == 77
    assert created["client"].max_retries == 0
