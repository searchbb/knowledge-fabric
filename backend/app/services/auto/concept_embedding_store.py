"""File-locked JSON sidecar for concept embeddings (P4 step 5).

Part of Discover V2's embedding recall path. Computing concept embeddings
on every discover run is wasteful — a concept's canonical_name and
description change rarely, and its vector is deterministic for a fixed
model + text. The sidecar lets us cache-on-write, invalidate-on-edit,
and survive process restarts without ever touching Neo4j.

Layout mirrors ``pending_store.PendingUrlStore`` and
``discover_job_store.DiscoverJobStore``:

- Single JSON file (``backend/data/concept_embeddings.json`` by default).
- ``fcntl.flock`` sidecar for concurrent-writer safety.
- Atomic rename on every write.

Each row:

    {
      "entry_id": "canon_abc",
      "vector": [0.12, -0.03, ...],
      "text_hash": "sha256:<source text digest>",  # detect stale
      "model":    "qwen3-embed-v2",
      "dim":      1024,
      "created_at": "...",
      "updated_at": "..."
    }

Stale detection is intentionally hash-based rather than timestamp-based:
a discover run can pass in ``current_hashes`` derived from each concept's
live text and :meth:`invalidate_stale` drops rows whose cached hash no
longer matches. That keeps the "is this embedding still usable?" check
identical whether the edit happened 5 seconds or 5 months ago.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional


_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "concept_embeddings.json"
)

_EMPTY_STATE: dict[str, Any] = {"version": 1, "embeddings": {}}


class ConceptEmbeddingStoreError(RuntimeError):
    """Raised on schema-violation writes (bad dim, empty vector, ...)."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextlib.contextmanager
def _flock(file_path: Path) -> Iterator[Any]:
    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class ConceptEmbeddingStore:
    """File-locked sidecar over a single concept_embeddings.json file."""

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path: Path = (
            Path(path).expanduser().resolve() if path else _DEFAULT_DATA_PATH
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write(dict(_EMPTY_STATE, embeddings={}))

    # ------------------------------------------------------------------
    # Low-level read / write
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"version": 1, "embeddings": {}}
        if not text.strip():
            return {"version": 1, "embeddings": {}}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ConceptEmbeddingStoreError(
                f"concept_embeddings.json is corrupted: {error}"
            ) from error
        data.setdefault("version", 1)
        data.setdefault("embeddings", {})
        return data

    def _atomic_write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, entry_id: str) -> Optional[dict[str, Any]]:
        """Return a copy of the row for ``entry_id`` or ``None`` if absent."""
        data = self._read()
        rec = data["embeddings"].get(entry_id)
        return dict(rec) if rec else None

    def batch_get(self, entry_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return ``{entry_id: row}`` for all known ids in the input list."""
        if not entry_ids:
            return {}
        data = self._read()
        out: dict[str, dict[str, Any]] = {}
        for eid in entry_ids:
            rec = data["embeddings"].get(eid)
            if rec:
                out[eid] = dict(rec)
        return out

    def upsert(
        self,
        *,
        entry_id: str,
        vector: list[float],
        text_hash: str,
        model: str,
        dim: int,
    ) -> dict[str, Any]:
        """Insert-or-replace an embedding row. Returns a copy of the stored record."""
        if not vector:
            raise ConceptEmbeddingStoreError("vector must be non-empty")
        if dim != len(vector):
            raise ConceptEmbeddingStoreError(
                f"dim={dim} does not match vector length {len(vector)}"
            )

        with _flock(self.path):
            data = self._read()
            existing = data["embeddings"].get(entry_id) or {}
            now = _now_iso()
            row = {
                "entry_id": entry_id,
                "vector": list(vector),
                "text_hash": text_hash,
                "model": model,
                "dim": int(dim),
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
            }
            data["embeddings"][entry_id] = row
            self._atomic_write(data)
            return dict(row)

    def delete(self, entry_id: str) -> None:
        """Remove a row; silent no-op for unknown ids."""
        with _flock(self.path):
            data = self._read()
            if entry_id in data["embeddings"]:
                del data["embeddings"][entry_id]
                self._atomic_write(data)

    def invalidate_stale(self, *, current_hashes: dict[str, str]) -> list[str]:
        """Drop cached rows whose ``text_hash`` differs from the live value.

        Args:
            current_hashes: ``{entry_id: current_text_hash}`` — typically
                computed by the caller hashing each concept's
                canonical_name + description at discover-run time.

        Returns the list of dropped ``entry_id``s (useful for logging:
        "X concepts were re-embedded this run because their text changed").
        Entry_ids in ``current_hashes`` that aren't in the store are
        ignored — they simply aren't cached yet.
        """
        dropped: list[str] = []
        with _flock(self.path):
            data = self._read()
            for entry_id, current_hash in current_hashes.items():
                cached = data["embeddings"].get(entry_id)
                if cached and cached.get("text_hash") != current_hash:
                    del data["embeddings"][entry_id]
                    dropped.append(entry_id)
            if dropped:
                self._atomic_write(data)
        return dropped

    def stats(self) -> dict[str, Any]:
        """Summary suitable for a health endpoint."""
        data = self._read()
        by_model: dict[str, int] = {}
        for rec in data["embeddings"].values():
            m = rec.get("model", "unknown")
            by_model[m] = by_model.get(m, 0) + 1
        return {"total": len(data["embeddings"]), "by_model": by_model}
