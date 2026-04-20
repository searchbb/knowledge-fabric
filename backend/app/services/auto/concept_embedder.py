"""Lazy-compute + cache façade for concept embeddings (P4 step 5).

Sits between :mod:`cross_concept_discoverer` (the consumer that wants
"give me a vector for each concept") and two collaborators:

- :class:`ConceptEmbeddingStore` — JSON sidecar on disk.
- An :class:`EmbeddingProvider` — injectable. Production wiring points
  at the bailian / openai-compat embedding endpoint (TODO step 6);
  tests use :class:`DeterministicEmbeddingProvider`, which produces
  stable vectors from input text so store invariants can be asserted
  without any network.

Design notes
------------

``compute_concept_text_hash`` is the source-of-truth for staleness. We
derive it from canonical_name + description because those are the two
fields the LLM actually sees during ontology extraction. Anything else
(source_links, concept_type, etc.) doesn't change the semantic content
of the concept, so re-embedding on those edits is waste.

Batch semantics: ``embed_concepts`` ALWAYS calls the provider at most
once per invocation, regardless of how many concepts are uncached. The
provider receives just the texts for uncached concepts, in stable order.
Anything already cached is served from disk without touching the
provider. If the provider is expensive (bailian charges per request),
this is the main reason to keep the façade at all.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from abc import ABC, abstractmethod
from typing import Any, Optional

from .concept_embedding_store import ConceptEmbeddingStore

logger = logging.getLogger("mirofish.concept_embedder")


_CONCEPT_TEXT_SEP = "\u0001"  # unlikely to appear in canonical_name/description


def compute_concept_text_hash(canonical_name: str, description: str) -> str:
    """Stable SHA-256 digest over the fields that drive the embedding.

    Uses an unambiguous separator so ``("ab", "cd")`` and ``("a", "bcd")``
    don't collide. Prefixed with ``sha256:`` so it's obviously-a-hash in
    logs.
    """
    payload = f"{canonical_name}{_CONCEPT_TEXT_SEP}{description}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Provider contract
# ---------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Injectable contract: given N texts, return N vectors of equal ``dim``.

    Subclasses set ``is_fallback = False`` when they represent a real
    production-grade embedding backend (bailian, openai, etc). The
    CrossConceptDiscoverer dispatch refuses embedding mode when the
    resolved provider is a fallback and the operator has not explicitly
    opted in via ``DISCOVER_ALLOW_FALLBACK_EMBEDDING=1`` — so flipping
    ``DISCOVER_RECALL_MODE=embedding`` without wiring a real provider
    doesn't silently degrade recall quality.
    """

    #: Human-readable model identifier persisted in the sidecar. Also used
    #: by :meth:`ConceptEmbeddingStore.stats` so operators can spot a
    #: cache warmed by the wrong model.
    model: str
    dim: int
    #: Default to ``True`` (safe: unknown providers are treated as
    #: fallback). Real providers MUST set this to ``False`` on the class
    #: or instance level.
    is_fallback: bool = True

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Zero-dependency, no-network provider used by tests + as a default
    fallback when no real embedding endpoint is configured.

    The vector is derived from a SHA-256 of the text, unpacked into
    ``dim`` floats in [-1, 1]. Same input → same output; different input
    → different output; no network; no tokens.
    """

    #: Explicit marker so the discover dispatch knows this is not a
    #: production-grade provider. Flipping embedding mode without wiring
    #: a real provider should NOT silently use SHA-derived vectors.
    is_fallback: bool = True

    def __init__(self, dim: int = 64, model: str = "deterministic-sha256-v1"):
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = int(dim)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(self._embed_one(text))
        return vectors

    def _embed_one(self, text: str) -> list[float]:
        # Expand SHA-256 across enough bytes to fill ``dim`` floats.
        # Each float takes 4 bytes from an extended digest stream.
        bytes_needed = self.dim * 4
        buf = b""
        counter = 0
        while len(buf) < bytes_needed:
            h = hashlib.sha256(f"{text}|{counter}".encode("utf-8")).digest()
            buf += h
            counter += 1
        # Convert chunks to signed int32, normalise to [-1, 1].
        floats: list[float] = []
        for i in range(self.dim):
            chunk = buf[i * 4: (i + 1) * 4]
            (val,) = struct.unpack(">i", chunk)
            # int32 max is 2**31 − 1; clamp just in case.
            floats.append(max(-1.0, min(1.0, val / (2 ** 31 - 1))))
        return floats


# ---------------------------------------------------------------------------
# Façade
# ---------------------------------------------------------------------------


class ConceptEmbedder:
    """Batch + cache orchestration around a store and a provider."""

    def __init__(
        self,
        *,
        store: Optional[ConceptEmbeddingStore] = None,
        provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.store = store or ConceptEmbeddingStore()
        self.provider = provider or DeterministicEmbeddingProvider()

    def embed_concepts(
        self, concepts: list[dict[str, Any]]
    ) -> dict[str, list[float]]:
        """Return ``{entry_id: vector}`` for every concept with a non-empty
        ``entry_id``. Silently skips malformed inputs so a single upstream
        glitch doesn't blow up the whole discover run.
        """
        if not concepts:
            return {}

        # Build the per-concept text + hash once; downstream operations
        # (cache lookup, invalidation, provider batch) all key off these.
        work: list[tuple[str, str, str]] = []  # (entry_id, text, hash)
        for c in concepts:
            eid = str(c.get("entry_id") or "").strip()
            if not eid:
                logger.warning(
                    "embed_concepts: skipping concept without entry_id: %r",
                    c.get("canonical_name"),
                )
                continue
            name = str(c.get("canonical_name") or "")
            desc = str(c.get("description") or "")
            text = f"{name}\n{desc}".strip() or eid  # fall back to eid text
            thash = compute_concept_text_hash(name, desc)
            work.append((eid, text, thash))

        if not work:
            return {}

        # Step 1: drop stale rows whose cached hash no longer matches.
        current_hashes = {eid: thash for eid, _text, thash in work}
        dropped = self.store.invalidate_stale(current_hashes=current_hashes)
        if dropped:
            logger.info(
                "concept_embedder: invalidated %d stale rows (%s)",
                len(dropped),
                dropped[:5],
            )

        # Step 2: batch lookup the remaining cache.
        cached = self.store.batch_get([eid for eid, _, _ in work])

        # Step 3: collect uncached work for a single provider batch.
        missing: list[tuple[str, str, str]] = [
            (eid, text, thash)
            for (eid, text, thash) in work
            if eid not in cached
        ]

        fresh_vectors: dict[str, list[float]] = {}
        if missing:
            texts = [text for _eid, text, _thash in missing]
            vectors = self.provider.embed(texts)
            if len(vectors) != len(missing):
                raise RuntimeError(
                    f"embedding provider returned {len(vectors)} vectors for "
                    f"{len(missing)} texts — contract violation"
                )
            for (eid, _text, thash), vec in zip(missing, vectors):
                self.store.upsert(
                    entry_id=eid,
                    vector=vec,
                    text_hash=thash,
                    model=self.provider.model,
                    dim=self.provider.dim,
                )
                fresh_vectors[eid] = list(vec)

        # Step 4: assemble the result dict in the order concepts came in.
        out: dict[str, list[float]] = {}
        for eid, _text, _thash in work:
            if eid in fresh_vectors:
                out[eid] = fresh_vectors[eid]
            elif eid in cached:
                out[eid] = list(cached[eid]["vector"])
        return out
