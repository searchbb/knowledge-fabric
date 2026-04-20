"""Lazy-compute + cache façade for concept embeddings (P4 step 5).

The :class:`ConceptEmbedder` sits between the discover pipeline and two
collaborators:

- :class:`ConceptEmbeddingStore` (sidecar JSON persistence).
- An ``EmbeddingProvider`` (injectable — production will wire the
  bailian API; tests use a deterministic fake).

Responsibilities:

1. For each concept, derive a ``text_hash`` from its canonical_name +
   description so edits invalidate the cached vector.
2. Invalidate stale rows against the store.
3. Batch-compute embeddings only for concepts whose row is missing (or
   just dropped). Call the provider ONCE for the whole uncached batch.
4. Return ``{entry_id: vector}`` for every requested concept.

No wiring into ``cross_concept_discoverer.discover`` yet — Step 6 does
that behind a feature flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.auto.concept_embedder import (
    ConceptEmbedder,
    DeterministicEmbeddingProvider,
    compute_concept_text_hash,
)
from app.services.auto.concept_embedding_store import ConceptEmbeddingStore


def _concept(entry_id: str, name: str = "", desc: str = "") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": name or entry_id,
        "description": desc,
    }


@pytest.fixture
def store(tmp_path: Path) -> ConceptEmbeddingStore:
    return ConceptEmbeddingStore(tmp_path / "concept_embeddings.json")


class TestTextHash:
    def test_same_text_same_hash(self):
        h1 = compute_concept_text_hash("Topic", "a description")
        h2 = compute_concept_text_hash("Topic", "a description")
        assert h1 == h2

    def test_different_name_different_hash(self):
        assert compute_concept_text_hash("a", "x") != compute_concept_text_hash(
            "b", "x"
        )

    def test_different_description_different_hash(self):
        assert compute_concept_text_hash("a", "x") != compute_concept_text_hash(
            "a", "y"
        )

    def test_hash_includes_prefix(self):
        """The hash string should be obviously-a-hash so logs are readable."""
        h = compute_concept_text_hash("foo", "bar")
        assert h.startswith("sha256:")
        assert len(h) > len("sha256:")


class TestDeterministicProvider:
    """Zero-dependency provider used by unit tests and by offline discover
    runs when no real embedding endpoint is configured. Same input ⇒ same
    output so store semantics can be tested deterministically."""

    def test_embed_returns_same_vector_for_same_input(self):
        p = DeterministicEmbeddingProvider(dim=16)
        v1 = p.embed(["hello"])[0]
        v2 = p.embed(["hello"])[0]
        assert v1 == v2

    def test_embed_vectors_respect_requested_dim(self):
        p = DeterministicEmbeddingProvider(dim=32)
        vs = p.embed(["a", "b", "c"])
        assert all(len(v) == 32 for v in vs)

    def test_different_input_different_vector(self):
        p = DeterministicEmbeddingProvider(dim=16)
        assert p.embed(["alpha"])[0] != p.embed(["beta"])[0]

    def test_exposes_model_name(self):
        p = DeterministicEmbeddingProvider(dim=16)
        assert "deterministic" in p.model.lower()


class TestEmbedConceptsCacheMiss:
    def test_first_call_computes_and_persists(self, store: ConceptEmbeddingStore):
        provider = DeterministicEmbeddingProvider(dim=8)
        embedder = ConceptEmbedder(store=store, provider=provider)

        concepts = [
            _concept("canon_a", "A", "topic a"),
            _concept("canon_b", "B", "topic b"),
        ]
        result = embedder.embed_concepts(concepts)
        assert set(result.keys()) == {"canon_a", "canon_b"}
        assert len(result["canon_a"]) == 8

        # Persisted.
        assert store.get("canon_a") is not None
        assert store.get("canon_b") is not None

    def test_second_call_reuses_cached_vectors(self, store: ConceptEmbeddingStore):
        """Call the provider only for uncached concepts — otherwise the
        whole optimisation is pointless."""
        calls = {"n": 0}

        class CountingProvider(DeterministicEmbeddingProvider):
            def embed(self, texts: list[str]) -> list[list[float]]:
                calls["n"] += 1
                return super().embed(texts)

        provider = CountingProvider(dim=8)
        embedder = ConceptEmbedder(store=store, provider=provider)

        concepts = [
            _concept("canon_a", "A", "topic a"),
            _concept("canon_b", "B", "topic b"),
        ]
        embedder.embed_concepts(concepts)
        assert calls["n"] == 1  # one batch call on first run

        # Second run with identical input: provider should be skipped.
        embedder.embed_concepts(concepts)
        assert calls["n"] == 1

    def test_partial_cache_only_calls_provider_for_missing(
        self, store: ConceptEmbeddingStore
    ):
        """Seed one concept in the store; request two; provider sees one."""
        last_batch = {"texts": None}

        class SpyingProvider(DeterministicEmbeddingProvider):
            def embed(self, texts: list[str]) -> list[list[float]]:
                last_batch["texts"] = list(texts)
                return super().embed(texts)

        provider = SpyingProvider(dim=8)
        embedder = ConceptEmbedder(store=store, provider=provider)

        # Seed canon_a.
        pre = embedder.embed_concepts([_concept("canon_a", "A", "seeded")])
        last_batch["texts"] = None  # reset spy

        embedder.embed_concepts([
            _concept("canon_a", "A", "seeded"),
            _concept("canon_b", "B", "fresh"),
        ])
        # Only the fresh concept's text should have been sent to the provider.
        assert last_batch["texts"] is not None
        assert len(last_batch["texts"]) == 1


class TestEmbedConceptsInvalidatesOnEdit:
    def test_edited_description_triggers_recompute(self, store: ConceptEmbeddingStore):
        provider = DeterministicEmbeddingProvider(dim=8)
        embedder = ConceptEmbedder(store=store, provider=provider)

        first = embedder.embed_concepts(
            [_concept("canon_a", "A", "original")]
        )
        second = embedder.embed_concepts(
            [_concept("canon_a", "A", "edited")]
        )
        # Deterministic provider is input-sensitive → vectors differ.
        assert first["canon_a"] != second["canon_a"]

        # And the cached row now reflects the new hash.
        rec = store.get("canon_a")
        expected_hash = compute_concept_text_hash("A", "edited")
        assert rec["text_hash"] == expected_hash


class TestErrorSurface:
    def test_empty_input_is_noop(self, store: ConceptEmbeddingStore):
        provider = DeterministicEmbeddingProvider(dim=8)
        embedder = ConceptEmbedder(store=store, provider=provider)
        assert embedder.embed_concepts([]) == {}

    def test_concept_without_entry_id_is_skipped(
        self, store: ConceptEmbeddingStore
    ):
        """Defensive: upstream shouldn't send concepts without entry_id,
        but if it does, don't crash — just log-and-skip."""
        provider = DeterministicEmbeddingProvider(dim=8)
        embedder = ConceptEmbedder(store=store, provider=provider)
        out = embedder.embed_concepts([{"canonical_name": "orphan"}])
        assert out == {}
