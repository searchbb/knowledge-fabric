"""Embedding-based Stage 1 recall behind a feature flag (P4 steps 6 + 7).

Rule-based recall enumerates every pair and scores. That's fine for small
themes but quadratic as themes grow. This module pins the behaviour of the
alternate path: for each "new" concept, pull top-K nearest-neighbour
concepts by cosine similarity, apply the same hard edge filters
(incremental / cross-article / dedupe), then rerank with the original
light-rule score so the final ordering stays interpretable.

Flag: ``DISCOVER_RECALL_MODE=embedding`` (env var) OR per-call override
via ``recall_mode="embedding"``. Default stays ``"rules"`` so existing
behaviour ships unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.auto.concept_embedder import (
    ConceptEmbedder,
    DeterministicEmbeddingProvider,
)
from app.services.auto.concept_embedding_store import ConceptEmbeddingStore
from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


def _c(entry_id: str, projects: list[str], ctype: str = "Topic", desc: str = "") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": entry_id,
        "concept_type": ctype,
        "description": desc or f"concept {entry_id}",
        "source_links": [{"project_id": p} for p in projects],
    }


@pytest.fixture(autouse=True)
def _opt_in_fallback_embedding(monkeypatch):
    """These tests exercise the embedding path using ``DeterministicEmbeddingProvider``
    (a fallback provider). The post-audit embedding gate refuses fallback
    providers unless ``DISCOVER_ALLOW_FALLBACK_EMBEDDING=1`` is set, so
    opt the whole file in. Tests that specifically want to verify the
    gate's refusal behaviour live in a separate file (test_..._fallback).
    """
    monkeypatch.setenv("DISCOVER_ALLOW_FALLBACK_EMBEDDING", "1")


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch):
    """Isolate both the relations JSON and the embedding sidecar."""
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))
    return uploads


@pytest.fixture
def embedder(tmp_path: Path) -> ConceptEmbedder:
    store = ConceptEmbeddingStore(tmp_path / "concept_embeddings.json")
    provider = DeterministicEmbeddingProvider(dim=16)
    return ConceptEmbedder(store=store, provider=provider)


class TestFeatureFlagDispatch:
    def test_default_is_rules_mode(self, isolated_stores, monkeypatch):
        monkeypatch.delenv("DISCOVER_RECALL_MODE", raising=False)
        from app.services.auto.cross_concept_discoverer import _current_recall_mode
        assert _current_recall_mode() == "rules"

    def test_env_var_switches_to_embedding(self, isolated_stores, monkeypatch):
        monkeypatch.setenv("DISCOVER_RECALL_MODE", "embedding")
        from app.services.auto.cross_concept_discoverer import _current_recall_mode
        assert _current_recall_mode() == "embedding"

    def test_unrecognised_mode_falls_back_to_rules(
        self, isolated_stores, monkeypatch
    ):
        monkeypatch.setenv("DISCOVER_RECALL_MODE", "bananas")
        from app.services.auto.cross_concept_discoverer import _current_recall_mode
        assert _current_recall_mode() == "rules"

    def test_per_call_override_wins_over_env(
        self, isolated_stores, monkeypatch, embedder
    ):
        """Tests shouldn't need to fiddle with env vars — per-call override
        takes precedence so the flag can be exercised deterministically."""
        monkeypatch.setenv("DISCOVER_RECALL_MODE", "rules")
        d = CrossConceptDiscoverer(embedder=embedder)

        concepts = [
            _c("a", ["proj_1"]),
            _c("b", ["proj_2"]),
            _c("c", ["proj_3"]),
        ]
        # embedding mode explicitly — should still produce candidates
        # from the correct path.
        cands, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        assert isinstance(cands, list)
        # Funnel includes the embedding-specific bucket.
        assert "embedding_neighbors" in funnel


class TestEmbeddingRecallTopK:
    def test_top_k_bounds_candidate_count_per_new_concept(
        self, isolated_stores, embedder
    ):
        """With K=2 and 1 new concept in a 5-other-concept theme, at most
        2 candidate pairs should come out (before any filter)."""
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [
            _c("a", ["proj_1"]),  # new
            _c("b", ["proj_2"]),
            _c("c", ["proj_3"]),
            _c("d", ["proj_4"]),
            _c("e", ["proj_5"]),
            _c("f", ["proj_6"]),
        ]
        with patch(
            "app.services.auto.cross_concept_discoverer._EMBEDDING_TOP_K", 2
        ):
            cands, funnel = d._recall_candidates(
                concepts,
                exclude_existing=True,
                require_endpoint_in={"a"},
                return_funnel=True,
                recall_mode="embedding",
            )

        # At most K=2 pairs from 'a'. Each pair touches 'a'.
        assert len(cands) <= 2
        assert funnel["embedding_neighbors"] <= 2
        for cand in cands:
            ids = {cand["concept_a"]["entry_id"], cand["concept_b"]["entry_id"]}
            assert "a" in ids

    def test_embedding_recall_drops_same_article_pairs(
        self, isolated_stores, embedder
    ):
        """Even when an embedding says two same-article concepts are the
        most similar, the cross-article rule still drops them."""
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [
            # 'a' and 'a_same' share proj_1 — same article.
            _c("a", ["proj_1"], desc="identical text twin"),
            _c("a_same", ["proj_1"], desc="identical text twin"),
            _c("b", ["proj_2"], desc="different topic"),
        ]
        cands, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        for cand in cands:
            a_projects = {
                l["project_id"] for l in cand["concept_a"]["source_links"]
            }
            b_projects = {
                l["project_id"] for l in cand["concept_b"]["source_links"]
            }
            assert a_projects != b_projects, (
                "embedding recall leaked a same-article pair past cross-article rule"
            )

    def test_embedding_recall_respects_dedupe_set(
        self, isolated_stores, embedder, tmp_path
    ):
        """Seed a dedupe key for (a, design_inspiration, b); embedding
        recall must drop (a, b) even if they're the most similar pair."""
        import json
        from app import config as config_module

        uploads = Path(config_module.Config.UPLOAD_FOLDER)
        rels_file = uploads / "projects" / "cross_concept_relations.json"
        rels_file.write_text(json.dumps({
            "version": 1,
            "relations": {
                "crel_1": {
                    "relation_id": "crel_1",
                    "dedupe_key": "a|design_inspiration|b",
                    "status": "active",
                    "source_entry_id": "a",
                    "target_entry_id": "b",
                    "relation_type": "design_inspiration",
                },
            },
        }))

        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [
            _c("a", ["proj_1"], desc="x x x"),
            _c("b", ["proj_2"], desc="x x x"),
            _c("c", ["proj_3"], desc="unrelated"),
        ]
        cands, _ = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        pair_ids = {
            tuple(sorted([c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]]))
            for c in cands
        }
        assert ("a", "b") not in pair_ids

    def test_embedding_recall_still_carries_rule_score(
        self, isolated_stores, embedder
    ):
        """Embedding-mode candidates should still have a ``recall_score``
        derived from the light-rule features (type complementarity +
        token overlap) — so the final sort order uses BOTH neighbour
        proximity AND rule features, not just embedding similarity."""
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [
            _c("a", ["proj_1"], ctype="Problem", desc="inference latency issue"),
            _c("b", ["proj_2"], ctype="Solution", desc="scale inference workers"),
            _c("c", ["proj_3"], ctype="Topic", desc="unrelated"),
        ]
        cands, _ = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        for c in cands:
            assert "recall_score" in c
            assert isinstance(c["recall_score"], (int, float))

    def test_embedding_recall_returns_funnel_superset(
        self, isolated_stores, embedder
    ):
        """The embedding-mode funnel must still include every rules-mode
        key (raw_pairs, after_incremental_gate, ..., final) so A/B
        dashboards don't have to branch on mode."""
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [
            _c("a", ["proj_1"]),
            _c("b", ["proj_2"]),
            _c("c", ["proj_3"]),
        ]
        _, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"a"},
            return_funnel=True,
            recall_mode="embedding",
        )
        for key in (
            "raw_pairs",
            "after_incremental_gate",
            "after_cross_article",
            "after_dedupe_filter",
            "final",
            "embedding_neighbors",
        ):
            assert key in funnel, f"embedding funnel missing key: {key}"


class TestRulesModeUnchanged:
    """Regression guard: adding the embedding path must not change rules behaviour."""

    def test_rules_mode_default_matches_pre_embedding_behaviour(
        self, isolated_stores, monkeypatch, embedder
    ):
        monkeypatch.delenv("DISCOVER_RECALL_MODE", raising=False)
        d = CrossConceptDiscoverer(embedder=embedder)
        concepts = [
            _c("a", ["proj_1"]),
            _c("b", ["proj_2"]),
            _c("c", ["proj_3"]),
        ]
        cands = d._recall_candidates(concepts, exclude_existing=True)
        assert isinstance(cands, list)
        assert len(cands) == 3  # all cross-article pairs
