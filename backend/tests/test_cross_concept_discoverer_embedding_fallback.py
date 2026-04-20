"""Embedding mode safety gate + runtime soft-fallback (P4 step 5/6 hardening).

GPT audit (2026-04-17) flagged two block-release issues:

A. The ``DISCOVER_RECALL_MODE=embedding`` flag could be flipped on a
   deployment that has no real embedding provider configured — the
   default fallback is :class:`DeterministicEmbeddingProvider`, which
   returns SHA-derived vectors. Flipping the flag without a real
   provider silently makes recall *worse*, not better.

B. When a real provider IS configured, a single transient blip from the
   upstream embedding endpoint would throw out of
   ``_recall_candidates_embedding`` and fail the entire discover job
   — no retry, no fallback, no audit trail.

Both are fixed by putting a dispatch-time gate in ``_recall_candidates``:

1. If embedding mode is requested but the resolved embedder's provider
   is a non-production fallback (Deterministic by default) AND the
   operator has not explicitly opted in via
   ``DISCOVER_ALLOW_FALLBACK_EMBEDDING=1``, fall back to rules mode.
2. If embedding mode is requested with a real provider but the
   embedding call raises, catch it and fall back to rules mode.
3. In both fall-back paths, the funnel gains
   ``fallback_to_rules = True`` + ``fallback_reason = "..."`` so the
   Theme page / A/B dashboard can distinguish "ran in rules mode by
   choice" from "ran in rules mode because embedding was unsafe".

Tests below pin all three.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.auto.concept_embedder import (
    ConceptEmbedder,
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
)
from app.services.auto.concept_embedding_store import ConceptEmbeddingStore
from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


def _c(entry_id: str, projects: list[str], ctype: str = "Topic") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": entry_id,
        "concept_type": ctype,
        "description": f"d {entry_id}",
        "source_links": [{"project_id": p} for p in projects],
    }


@pytest.fixture
def isolated_relations(tmp_path: Path, monkeypatch):
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))


@pytest.fixture
def fallback_embedder(tmp_path: Path) -> ConceptEmbedder:
    # Deterministic provider = ``is_fallback=True`` (SHA vectors, not semantic).
    store = ConceptEmbeddingStore(tmp_path / "concept_embeddings.json")
    return ConceptEmbedder(store=store, provider=DeterministicEmbeddingProvider(dim=8))


class _FakeProductionProvider(EmbeddingProvider):
    """Test stand-in for a real embedding provider (bailian/openai/etc).

    Identical behaviour to the Deterministic one, but with
    ``is_fallback=False`` so dispatch trusts it as production-grade.
    """

    def __init__(self, *, fail: bool = False):
        self.model = "fake-production-v1"
        self.dim = 8
        self.is_fallback = False
        self._fail = fail

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._fail:
            raise RuntimeError("simulated bailian embedding failure")
        # Trivial deterministic mapping — we only need CONSISTENT vectors
        # for the test, not semantically meaningful ones.
        return [[float(i + 1) / 10.0] * self.dim for i, _ in enumerate(texts)]


class TestFallbackProviderIsRefused:
    """A: embedding mode + Deterministic (fallback) provider without
    opt-in env → dispatch refuses and goes to rules mode."""

    def test_deterministic_provider_without_optin_falls_back(
        self, isolated_relations, fallback_embedder, monkeypatch
    ):
        monkeypatch.delenv("DISCOVER_ALLOW_FALLBACK_EMBEDDING", raising=False)
        d = CrossConceptDiscoverer(embedder=fallback_embedder)
        concepts = [_c("a", ["p1"]), _c("b", ["p2"]), _c("c", ["p3"])]
        cands, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        assert funnel.get("fallback_to_rules") is True
        assert "fallback" in funnel.get("fallback_reason", "").lower()
        # And the actual returned candidates should match what rules mode
        # would have produced (sanity: a and cross-article pairs).
        pair_ids = {
            tuple(sorted([c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]]))
            for c in cands
        }
        assert ("a", "b") in pair_ids
        assert ("a", "c") in pair_ids

    def test_deterministic_provider_with_optin_runs_embedding(
        self, isolated_relations, fallback_embedder, monkeypatch
    ):
        """Opt-in env var unlocks the embedding path for tests/dev."""
        monkeypatch.setenv("DISCOVER_ALLOW_FALLBACK_EMBEDDING", "1")
        d = CrossConceptDiscoverer(embedder=fallback_embedder)
        concepts = [_c("a", ["p1"]), _c("b", ["p2"])]
        _, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        # Embedding path ran — no fallback flag, but embedding_neighbors is set.
        assert funnel.get("fallback_to_rules") is not True
        assert "embedding_neighbors" in funnel

    def test_production_provider_runs_embedding_without_optin(
        self, isolated_relations, tmp_path, monkeypatch
    ):
        """Real (non-fallback) provider needs no opt-in."""
        monkeypatch.delenv("DISCOVER_ALLOW_FALLBACK_EMBEDDING", raising=False)
        store = ConceptEmbeddingStore(tmp_path / "concept_embeddings.json")
        real_provider = _FakeProductionProvider()
        embedder = ConceptEmbedder(store=store, provider=real_provider)
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [_c("a", ["p1"]), _c("b", ["p2"])]
        _, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        assert funnel.get("fallback_to_rules") is not True
        assert "embedding_neighbors" in funnel


class TestRuntimeFailureFallback:
    """C: embedding provider throws mid-discover → fall back to rules,
    don't fail the job, mark the fallback in the funnel."""

    def test_provider_exception_falls_back_to_rules(
        self, isolated_relations, tmp_path
    ):
        store = ConceptEmbeddingStore(tmp_path / "concept_embeddings.json")
        bad_provider = _FakeProductionProvider(fail=True)
        embedder = ConceptEmbedder(store=store, provider=bad_provider)
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [_c("a", ["p1"]), _c("b", ["p2"]), _c("c", ["p3"])]
        cands, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        assert funnel.get("fallback_to_rules") is True
        assert "fail" in funnel.get("fallback_reason", "").lower() or \
               "error" in funnel.get("fallback_reason", "").lower() or \
               "exception" in funnel.get("fallback_reason", "").lower()
        # Candidates still come out via the rules path.
        assert len(cands) >= 1


class TestFunnelMarkerShape:
    """Rules mode by choice (not by fallback) should NOT carry the fallback flag."""

    def test_rules_mode_funnel_has_no_fallback_flag(self, isolated_relations):
        d = CrossConceptDiscoverer()
        concepts = [_c("a", ["p1"]), _c("b", ["p2"])]
        _, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            return_funnel=True,
            recall_mode="rules",
        )
        assert "fallback_to_rules" not in funnel or funnel["fallback_to_rules"] is False
