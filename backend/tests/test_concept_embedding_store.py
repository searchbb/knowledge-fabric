"""File-locked sidecar store for concept embeddings (P4 step 5).

Discover V2 Step 6 swaps Stage 1 recall to embedding nearest-neighbour.
Computing embeddings on every discover run is wasteful — once a concept's
canonical_name + description is fixed, its vector is too.

This store is the persistence layer:

- One JSON file per deployment (``concept_embeddings.json``), sibling
  to ``discover-jobs.json`` and ``pending-urls.json``.
- Keyed by ``entry_id``. Each row: vector, text_hash (to detect stale
  embeddings after a concept edit), model name, dim, timestamp.
- File lock + atomic rename, same pattern as every other state store in
  ``services/auto/``.

Tests below pin the store invariants only. The lazy-compute façade that
USES this store lives in ``concept_embedder.py`` and gets its own tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.auto.concept_embedding_store import (
    ConceptEmbeddingStore,
    ConceptEmbeddingStoreError,
)


@pytest.fixture
def store(tmp_path: Path) -> ConceptEmbeddingStore:
    return ConceptEmbeddingStore(tmp_path / "concept_embeddings.json")


class TestEmptyStore:
    def test_fresh_store_has_empty_file(self, tmp_path: Path):
        path = tmp_path / "new.json"
        assert not path.exists()
        ConceptEmbeddingStore(path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == {"version": 1, "embeddings": {}}

    def test_get_unknown_returns_none(self, store: ConceptEmbeddingStore):
        assert store.get("canon_missing") is None

    def test_batch_get_empty_returns_empty(self, store: ConceptEmbeddingStore):
        assert store.batch_get([]) == {}


class TestUpsertAndGet:
    def test_upsert_stores_and_roundtrips(self, store: ConceptEmbeddingStore):
        store.upsert(
            entry_id="canon_a",
            vector=[0.1, 0.2, 0.3],
            text_hash="sha256:abc",
            model="qwen3-embed",
            dim=3,
        )
        rec = store.get("canon_a")
        assert rec is not None
        assert rec["entry_id"] == "canon_a"
        assert rec["vector"] == [0.1, 0.2, 0.3]
        assert rec["text_hash"] == "sha256:abc"
        assert rec["model"] == "qwen3-embed"
        assert rec["dim"] == 3
        assert "created_at" in rec
        assert "updated_at" in rec

    def test_upsert_overwrites_existing(self, store: ConceptEmbeddingStore):
        store.upsert(
            entry_id="canon_a",
            vector=[0.1, 0.2, 0.3],
            text_hash="sha256:old",
            model="v1",
            dim=3,
        )
        store.upsert(
            entry_id="canon_a",
            vector=[0.9, 0.8, 0.7],
            text_hash="sha256:new",
            model="v2",
            dim=3,
        )
        rec = store.get("canon_a")
        assert rec["vector"] == [0.9, 0.8, 0.7]
        assert rec["text_hash"] == "sha256:new"
        assert rec["model"] == "v2"

    def test_upsert_validates_dim_matches_vector_length(
        self, store: ConceptEmbeddingStore
    ):
        with pytest.raises(ConceptEmbeddingStoreError, match="dim"):
            store.upsert(
                entry_id="canon_a",
                vector=[0.1, 0.2],  # length 2
                text_hash="h",
                model="m",
                dim=3,  # says 3
            )

    def test_upsert_rejects_empty_vector(self, store: ConceptEmbeddingStore):
        with pytest.raises(ConceptEmbeddingStoreError):
            store.upsert(
                entry_id="canon_a",
                vector=[],
                text_hash="h",
                model="m",
                dim=0,
            )


class TestBatchGet:
    def test_batch_get_returns_only_known_ids(self, store: ConceptEmbeddingStore):
        store.upsert(
            entry_id="canon_a", vector=[0.1], text_hash="h1", model="m", dim=1
        )
        store.upsert(
            entry_id="canon_b", vector=[0.2], text_hash="h2", model="m", dim=1
        )
        result = store.batch_get(["canon_a", "canon_b", "canon_missing"])
        assert set(result.keys()) == {"canon_a", "canon_b"}
        assert result["canon_a"]["vector"] == [0.1]
        assert result["canon_b"]["vector"] == [0.2]


class TestStaleInvalidation:
    def test_invalidate_stale_drops_rows_whose_hash_no_longer_matches(
        self, store: ConceptEmbeddingStore
    ):
        """Use-case: user edited two concepts; their description text_hashes
        changed; their embeddings are now stale and should be evicted so the
        next discover run regenerates them."""
        store.upsert(
            entry_id="canon_a", vector=[0.1], text_hash="h1", model="m", dim=1
        )
        store.upsert(
            entry_id="canon_b", vector=[0.2], text_hash="h2", model="m", dim=1
        )
        store.upsert(
            entry_id="canon_c", vector=[0.3], text_hash="h3", model="m", dim=1
        )

        # Caller supplies the current "expected" hash per id. Entries
        # whose cached hash differs get dropped.
        dropped = store.invalidate_stale(
            current_hashes={
                "canon_a": "h1",            # unchanged → keep
                "canon_b": "h2_NEW",        # changed → drop
                "canon_c": "h3",            # unchanged → keep
            }
        )
        assert dropped == ["canon_b"]
        assert store.get("canon_a") is not None
        assert store.get("canon_b") is None
        assert store.get("canon_c") is not None

    def test_invalidate_stale_ignores_ids_not_in_store(
        self, store: ConceptEmbeddingStore
    ):
        """Hashes for entries we never embedded should not be treated as
        stale — they simply aren't in the store."""
        store.upsert(
            entry_id="canon_a", vector=[0.1], text_hash="h1", model="m", dim=1
        )
        dropped = store.invalidate_stale(
            current_hashes={
                "canon_a": "h1",
                "canon_ghost": "ignored",
            }
        )
        assert dropped == []


class TestDeleteAndStats:
    def test_delete_removes_row(self, store: ConceptEmbeddingStore):
        store.upsert(
            entry_id="canon_a", vector=[0.1], text_hash="h", model="m", dim=1
        )
        store.delete("canon_a")
        assert store.get("canon_a") is None

    def test_delete_unknown_is_silent_noop(self, store: ConceptEmbeddingStore):
        # Matches PendingUrlStore.heartbeat's silent-miss policy.
        store.delete("canon_ghost")

    def test_stats_reports_counts(self, store: ConceptEmbeddingStore):
        store.upsert(
            entry_id="canon_a", vector=[0.1], text_hash="h", model="m1", dim=1
        )
        store.upsert(
            entry_id="canon_b", vector=[0.2], text_hash="h", model="m2", dim=1
        )
        stats = store.stats()
        assert stats["total"] == 2
        assert stats["by_model"] == {"m1": 1, "m2": 1}
