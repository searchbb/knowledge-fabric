"""Cross-concept relation discoverer (L3 discovery layer).

Two-stage discovery:
1. Candidate recall (rules, no LLM cost) — filter down N*(N-1)/2 pairs
2. LLM precision judgment — only on candidate pairs

Design rules:
- Only discover relations between concepts from DIFFERENT articles
- Use evidence (sampleEvidence/summary) to ground the relation
- confidence < threshold → do not persist
- dedupe_key prevents duplicates on re-run
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import os
import time
from typing import Any, Callable, Optional

from .concept_embedder import ConceptEmbedder

from ..registry import global_concept_registry as registry
from ..registry import global_theme_registry as themes
from ..registry.cross_concept_relations import (
    create_relation,
    has_dedupe_key,
    load_existing_dedupe_keys,
    CrossRelationDuplicateError,
    VALID_RELATION_TYPES,
)
from ..registry.source_evidence_resolver import (
    _GraphCache,
    build_evidence_refs_for_pair,
)

logger = logging.getLogger("mirofish.cross_concept_discoverer")

# Stage 1 recall mode (P4 steps 6+7, 2026-04-17).
#
# "rules"     → original path: enumerate every pair, filter, score.
# "embedding" → top-K nearest-neighbour recall per new concept, then the
#               same hard edge filters (cross-article, dedupe), then the
#               same light-rule score used as rerank feature.
#
# Default stays "rules" so existing behaviour ships unchanged. Operators
# flip "DISCOVER_RECALL_MODE=embedding" in the env to try the new path;
# tests can use the per-call ``recall_mode`` override to exercise either
# path without touching env state.
_RECALL_MODE_RULES = "rules"
_RECALL_MODE_EMBEDDING = "embedding"
_VALID_RECALL_MODES = {_RECALL_MODE_RULES, _RECALL_MODE_EMBEDDING}

# How many nearest-neighbour candidates to keep per "new" concept in
# embedding mode. GPT consult 2026-04-17 suggested 20 as a sensible
# starting point: wide enough for recall, narrow enough to avoid sliding
# back into the N×N explosion that P1.5 just escaped.
_EMBEDDING_TOP_K = 20


def _current_recall_mode() -> str:
    raw = os.environ.get("DISCOVER_RECALL_MODE", _RECALL_MODE_RULES).strip().lower()
    return raw if raw in _VALID_RECALL_MODES else _RECALL_MODE_RULES


def _compute_pair_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Light rule-based score used both as main ranker in rules mode AND
    as rerank feature in embedding mode.

    Shared so any future tweak to the scoring formula lands in one place.
    Components:

    - +2.0 if the ``(concept_type, concept_type)`` pair is in
      :data:`_COMPLEMENTARY_TYPE_PAIRS` (either direction).
    - +0..2.0 for description token overlap (>2 shared words → scaled).
    - +0.5 if the concept types differ (diversity nudge).
    """
    score = 0.0
    a_type = a.get("concept_type", "Concept")
    b_type = b.get("concept_type", "Concept")
    if (a_type, b_type) in _COMPLEMENTARY_TYPE_PAIRS or (
        b_type,
        a_type,
    ) in _COMPLEMENTARY_TYPE_PAIRS:
        score += 2.0

    a_desc = (a.get("description") or "").strip()
    b_desc = (b.get("description") or "").strip()
    if a_desc and b_desc:
        a_words = set(a_desc.lower().split())
        b_words = set(b_desc.lower().split())
        overlap = len(a_words & b_words)
        if overlap > 2:
            score += min(overlap * 0.3, 2.0)

    if a_type != b_type:
        score += 0.5
    return score


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in pure Python (small vectors, once-per-pair).

    Returns 0.0 if either vector is zero-length or zero-norm so the
    embedding path never propagates NaN into the rerank sort.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom == 0.0:
        return 0.0
    return dot / denom


# Transient-error retry policy (P4 step 3, 2026-04-17).
#
# Chunk-level _llm_judge() calls hit the outside world (bailian / local
# qwen3 / openai-compat). Connection resets, gateway 5xx, and socket
# timeouts are routine enough to absorb silently; forcing the user to
# UI-retry those is pure annoyance. Non-transient errors (ValueError,
# JSONDecodeError, KeyError) bypass retry — retrying real bugs just
# burns tokens.
#
# ``_CHUNK_RETRY_BACKOFF`` is the delay (seconds) between the 1st and
# 2nd retry. Length of the list == max retries beyond the initial attempt.
_CHUNK_RETRY_BACKOFF = [0.5, 2.0]
_CHUNK_MAX_RETRIES = len(_CHUNK_RETRY_BACKOFF)


def _discover_llm_timeout_seconds() -> int:
    try:
        return max(1, int(os.environ.get("DISCOVER_LLM_TIMEOUT_SECONDS", "90")))
    except ValueError:
        return 90

# Substring matches for ``str(exc)``. Case-insensitive. Kept deliberately
# narrow — if a new transient signature shows up in the wild, add it here
# with a log-grep reference, not a broad wildcard.
_TRANSIENT_ERROR_SUBSTRINGS = (
    "connection error",
    "connectionerror",
    "connection reset",
    "connection aborted",
    "timed out",
    "timeout",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    "remote end closed connection",
    "read timeout",
    "temporarily unavailable",
)

# Exception classes treated as transient regardless of message text.
_TRANSIENT_ERROR_TYPES: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
)


def _is_transient_error(exc: BaseException) -> bool:
    """Return True if ``exc`` looks like a network/gateway blip worth retrying.

    Kept as a module-level helper so tests can pin the classification
    without instantiating the whole discoverer.
    """
    if isinstance(exc, _TRANSIENT_ERROR_TYPES):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in _TRANSIENT_ERROR_SUBSTRINGS)


# Types that tend to form cross-article bridges. Checked in both directions
# via _score_pair. Covers tech domain (original set) + methodology domain
# (v3 addition — so methodology concepts also get the complementary-pair
# bonus when discovered cross-project).
_COMPLEMENTARY_TYPE_PAIRS = {
    # Tech domain
    ("Problem", "Solution"),
    ("Problem", "Technology"),
    ("Topic", "Technology"),
    ("Topic", "Solution"),
    ("Topic", "Product"),
    ("Constraint", "Solution"),
    ("Constraint", "Technology"),
    ("Evidence", "Topic"),
    ("Example", "Topic"),
    # Methodology domain (v3 2026-04-23)
    ("Problem", "Method"),
    ("Problem", "Principle"),
    ("Principle", "Method"),
    ("Method", "Case"),
    ("Principle", "Antipattern"),
    ("Method", "Antipattern"),
    ("Topic", "Method"),
    ("Topic", "Principle"),
    ("Problem", "Signal"),
}

# Relation type definitions for LLM prompt
_RELATION_TYPE_SPEC = """
relation_type 定义（6种，严格选择其一）：

1. design_inspiration (设计启示) [directed]
   定义：A 的设计可以借鉴 B 提供的洞察或经验
   正例：B 的 UX 研究揭示的模式可以启发 A 的界面设计
   反例：A 和 B 只是同一领域的不同产品（那是 contrast_reference）

2. technical_foundation (技术支撑) [directed]
   定义：B 是 A 的底层技术基础或实现依赖
   正例：A（应用层）依赖 B（框架/协议/算法）
   反例：A 和 B 都使用了同一技术（那是 pattern_reuse）

3. problem_solution (问题-方案) [directed]
   定义：A 提出了一个问题/挑战，B 提供了解决方案
   正例：A 描述了 AI 在物理环境中的局限，B 提出了仿真环境方案
   反例：A 和 B 都在解决同一问题（那是 contrast_reference）

4. contrast_reference (对比参照) [bidirectional]
   定义：A 和 B 解决类似问题但采用不同路径/哲学
   正例：A 用沙箱模式，B 用直连终端 — 两种 agent 隔离策略
   反例：A 只是引用了 B（那是 design_inspiration）

5. capability_constraint (能力约束) [directed]
   定义：B 揭示了 A 的能力边界、适用条件或前置假设
   正例：B 指出 AI agent 在复杂环境中表现受限，A 设计工作台时需考虑
   反例：B 只是更好的替代方案（那是 contrast_reference）

6. pattern_reuse (模式借鉴) [directed]
   定义：B 的做法/原则/方法论可迁移到 A 的场景
   正例：B 的开发哲学（为自己造工具）可以指导 A 的产品设计理念
   反例：A 和 B 用的完全相同的技术（那是 technical_foundation）
""".strip()


class CrossConceptDiscoverer:
    """Discover semantic bridges between canonical concepts across articles."""

    def __init__(
        self,
        *,
        actor_id: str = "auto_pipeline",
        source: str = "auto_url_pipeline",
        embedder: Optional[ConceptEmbedder] = None,
    ):
        self.actor_id = actor_id
        self.source = source
        # Lazily constructed on first embedding-mode use so tests / rules-
        # mode runs don't incur the embedding store's startup cost.
        self._embedder: Optional[ConceptEmbedder] = embedder

    def discover(
        self,
        *,
        theme_id: str,
        entry_ids: list[str] | None = None,
        new_entry_ids: list[str] | None = None,
        max_pairs: int = 50,
        min_confidence: float = 0.6,
        exclude_existing: bool = True,
        run_id: str = "",
        job_id: str | None = None,
        heartbeat_callback: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Run two-stage discovery for a theme.

        Args:
            theme_id: theme to discover within
            entry_ids: hard scope — if set, only consider these entries (subset
                of theme membership). Manual reruns from ThemeDetailPage.
            new_entry_ids: incremental scope — if set, only emit candidate pairs
                where AT LEAST ONE endpoint is in new_entry_ids. Designed for
                the inline pipeline discover phase: "this article just brought
                in N new concepts; bridge them to the rest of the theme without
                re-paying for old×old pairs". Pairs entirely outside
                new_entry_ids are dropped at recall time, not via dedupe.

        Returns dict with: candidates_count, discovered, skipped, errors
        """
        # Load theme and its concepts
        theme = themes.get_theme(theme_id)
        memberships = theme.get("concept_memberships", [])
        member_entry_ids = [m["entry_id"] for m in memberships]
        theme_member_count = len(member_entry_ids)

        # Filter to specified entry_ids if provided
        if entry_ids:
            member_entry_ids = [eid for eid in member_entry_ids if eid in entry_ids]

        # Load concept details + tally how many distinct articles back this
        # theme. The diagnostic answers "is candidate_pairs=0 because the
        # theme is too small to bridge across, or because dedupe ate
        # everything?" — added 2026-04-16 per GPT consult e297dd59ad8ab94b.
        all_entries = {e["entry_id"]: e for e in registry.list_entries()}
        concepts = []
        article_ids: set[str] = set()
        for eid in member_entry_ids:
            entry = all_entries.get(eid)
            if entry:
                concepts.append(entry)
                for link in entry.get("source_links") or []:
                    pid = link.get("project_id")
                    if pid:
                        article_ids.add(pid)
        theme_article_count = len(article_ids)

        # Build a "scope" snapshot so audit consumers can see the contract
        # this run executed under without re-deriving it from defaults.
        new_entry_id_set = set(new_entry_ids or [])
        scope_snapshot: dict[str, Any] = {
            "theme_id": theme_id,
            "incremental": bool(new_entry_id_set),
            "require_endpoint_in_new_entry_ids": bool(new_entry_id_set),
            "different_article_required": True,
            "exclude_existing": exclude_existing,
            "max_pairs": max_pairs,
            "min_confidence": min_confidence,
        }
        diagnostic_fields: dict[str, Any] = {
            "scope": scope_snapshot,
            "theme_member_count": theme_member_count,
            "theme_article_count": theme_article_count,
            "eligible_entry_count": len(concepts),
        }

        # Empty-funnel template: early-return paths still emit the full
        # key set so downstream consumers (Theme state, A/B dashboards)
        # never have to special-case missing keys.
        _empty_funnel = {
            "raw_pairs": 0,
            "after_incremental_gate": 0,
            "after_cross_article": 0,
            "after_dedupe_filter": 0,
            "final": 0,
            "sent_to_llm": 0,
            "llm_accepted": 0,
            "deduped_on_commit": 0,
            "committed": 0,
        }

        if len(concepts) < 2:
            return {
                "candidates_count": 0,
                "discovered": 0,
                "skipped": 0,
                "errors": [],
                "reason": f"Need at least 2 concepts, got {len(concepts)}",
                "funnel": _empty_funnel,
                **diagnostic_fields,
            }

        # Stage 1: Candidate recall (incremental: at least one endpoint in
        # new_entry_ids when provided, so we don't repay for old×old pairs).
        candidates, funnel = self._recall_candidates(
            concepts,
            exclude_existing,
            require_endpoint_in=new_entry_id_set or None,
            return_funnel=True,
        )
        logger.info(
            "Stage 1 recall: %d candidates from %d concepts across %d articles "
            "(incremental=%s) funnel=%s",
            len(candidates), len(concepts), theme_article_count,
            bool(new_entry_id_set), funnel,
        )
        if heartbeat_callback is not None:
            heartbeat_callback()

        # Limit pairs
        if len(candidates) > max_pairs:
            candidates = candidates[:max_pairs]

        if not candidates:
            # GPT consult e297dd59ad8ab94b: distinguish "split theme" (this
            # article is the only one in the theme so there's literally
            # nothing to bridge) from "candidates filtered by dedupe" — the
            # former is an upstream-bucketing problem, the latter is normal
            # idempotent rerun behaviour.
            if new_entry_id_set and theme_article_count <= 1:
                reason = (
                    "Split-theme: this run is the only article in the theme "
                    f"(theme_article_count={theme_article_count}); no other "
                    "articles to bridge to. Likely upstream theme_proposer "
                    "over-fragmentation, not a discover bug."
                )
            else:
                reason = (
                    "No candidate pairs after recall filtering "
                    f"(theme_member_count={theme_member_count}, "
                    f"theme_article_count={theme_article_count}, "
                    f"eligible_entries={len(concepts)})"
                )
            return {
                "candidates_count": 0,
                "discovered": 0,
                "skipped": 0,
                "errors": [],
                "reason": reason,
                # funnel up to Stage 1 is real; Stage 2 never ran.
                "funnel": {**_empty_funnel, **funnel, "sent_to_llm": 0},
                **diagnostic_fields,
            }

        # Stage 2: LLM precision judgment — concurrent judge, serial commit.
        #
        # Design (GPT consult 2026-04-16):
        # - Split candidates into chunks of ~10
        # - Run _llm_judge concurrently (one thread per chunk, capped by
        #   provider semaphore_limit so we don't blast the API rate limit)
        # - Each worker returns (chunk_idx, relations, error) — no writes
        # - Main thread collects results ordered by chunk_idx, then serially
        #   calls create_relation so there is zero write concurrency
        # - Soft-fail is preserved at chunk granularity: one chunk failing
        #   does NOT abort the others or the overall discover phase
        chunk_size = 10
        chunks = [
            candidates[i: i + chunk_size]
            for i in range(0, len(candidates), chunk_size)
        ]

        # Shared graph-data cache across all chunks so the same source article
        # is not re-read from disk once per chunk (P3 — cross-chunk cache).
        shared_graph_cache = _GraphCache()

        # Cap workers at the provider's semaphore limit to avoid flooding the
        # API. Snapshot params once; we don't need the full params dict here.
        from ..llm_mode_service import get_graphiti_llm_params
        try:
            _semaphore_limit = int(
                (get_graphiti_llm_params() or {}).get("semaphore_limit") or 4
            )
        except Exception:
            _semaphore_limit = 4
        max_workers = min(len(chunks), _semaphore_limit)

        # Worker: returns (chunk_idx, relations, error_str_or_None, retries_used).
        # Transient errors (network / gateway 5xx / timeout) retry up to
        # _CHUNK_MAX_RETRIES times with exponential backoff. Non-transient
        # errors short-circuit to immediate failure — retrying real bugs
        # just burns tokens. See _is_transient_error() for the whitelist.
        def _run_chunk(
            chunk_idx: int,
        ) -> tuple[int, list[dict[str, Any]], str | None, int]:
            t0 = time.monotonic()
            chunk = chunks[chunk_idx]
            last_exc: BaseException | None = None
            retries_used = 0

            # attempt 0 = first try; attempts 1..N = retries
            for attempt in range(_CHUNK_MAX_RETRIES + 1):
                try:
                    relations = self._llm_judge(
                        chunk,
                        min_confidence,
                        graph_cache=shared_graph_cache,
                        chunk_idx=chunk_idx,
                    )
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    if attempt > 0:
                        logger.info(
                            "discover chunk %d/%d: recovered after %d retry(s) "
                            "— %d pairs → %d relations in %dms",
                            chunk_idx, len(chunks) - 1, attempt,
                            len(chunk), len(relations), duration_ms,
                        )
                    else:
                        logger.info(
                            "discover chunk %d/%d: %d pairs → %d relations in %dms",
                            chunk_idx, len(chunks) - 1,
                            len(chunk), len(relations), duration_ms,
                        )
                    return chunk_idx, relations, None, retries_used
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if not _is_transient_error(exc):
                        # Non-transient: no retry, bail out now.
                        logger.warning(
                            "discover chunk %d/%d failed with non-transient "
                            "error (no retry): %s",
                            chunk_idx, len(chunks) - 1, exc,
                        )
                        break
                    if attempt < _CHUNK_MAX_RETRIES:
                        # Transient + retries remaining: back off and try again.
                        delay = _CHUNK_RETRY_BACKOFF[attempt]
                        logger.warning(
                            "discover chunk %d/%d transient error on attempt "
                            "%d (%s); retrying in %.1fs",
                            chunk_idx, len(chunks) - 1, attempt + 1, exc, delay,
                        )
                        retries_used += 1
                        if delay > 0:
                            time.sleep(delay)
                        continue
                    # Transient but retries exhausted.
                    logger.warning(
                        "discover chunk %d/%d failed after %d retry(s) "
                        "(final: %s)",
                        chunk_idx, len(chunks) - 1, retries_used, exc,
                    )
                    break

            return chunk_idx, [], str(last_exc) if last_exc else "unknown", retries_used

        # Collect results; as_completed gives us finished futures quickly but
        # we key by chunk_idx so the commit loop below stays ordered.
        chunk_relations: dict[int, list[dict[str, Any]]] = {}
        chunk_errors: dict[int, str] = {}
        failed_chunk_indices: list[int] = []
        total_chunk_retries = 0

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"discover_{run_id}",
        ) as executor:
            futures = {
                executor.submit(_run_chunk, idx): idx
                for idx in range(len(chunks))
            }
            for future in concurrent.futures.as_completed(futures):
                idx, relations, error, retries = future.result()
                if heartbeat_callback is not None:
                    heartbeat_callback()
                total_chunk_retries += retries
                if error is not None:
                    chunk_errors[idx] = error
                    failed_chunk_indices.append(idx)
                else:
                    chunk_relations[idx] = relations

        # Serial commit — iterate chunks in original order for determinism.
        discovered = 0
        skipped = 0
        errors: list[str] = [
            f"LLM judge failed for chunk {idx}: {msg}"
            for idx, msg in sorted(chunk_errors.items())
        ]

        # Count what Stage 2 actually returned vs what got committed so the
        # funnel picks up the LLM-side drop-off (accept→commit duplicates).
        llm_accepted_total = sum(len(rs) for rs in chunk_relations.values())

        for idx in range(len(chunks)):
            for rel_data in chunk_relations.get(idx, []):
                try:
                    create_relation(
                        source_entry_id=rel_data["source_entry_id"],
                        target_entry_id=rel_data["target_entry_id"],
                        relation_type=rel_data["relation_type"],
                        directionality=rel_data.get("directionality", "directed"),
                        reason=rel_data["reason"],
                        evidence_bridge=rel_data.get("evidence_bridge", ""),
                        evidence_refs=rel_data.get("evidence_refs", []),
                        discovery_path=rel_data.get("discovery_path", []),
                        confidence=rel_data["confidence"],
                        source="auto",
                        theme_id=theme_id,
                        model_info=rel_data.get("model_info"),
                        actor_id=self.actor_id,
                        run_id=run_id,
                        job_id=job_id,
                    )
                    discovered += 1
                except CrossRelationDuplicateError:
                    skipped += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Create failed: {exc}")

        chunks_succeeded = len(chunks) - len(failed_chunk_indices)

        # Retrieve the LLM provider/model for observability — best-effort.
        try:
            _p = get_graphiti_llm_params()
            _llm_provider = _p.get("provider", "unknown")
            _llm_model = _p.get("model", "unknown")
        except Exception:
            _llm_provider = "unknown"
            _llm_model = "unknown"

        # Full funnel: Stage 1 rule-based counts (raw→filters→final) +
        # Stage 2 LLM + commit counts (sent→accepted→committed+deduped).
        # This is the "尺子" GPT called for: any future A/B cutover to
        # embedding recall can compare apples-to-apples using these keys.
        full_funnel = {
            **funnel,  # raw_pairs / after_incremental_gate / after_cross_article / after_dedupe_filter / final
            "sent_to_llm": len(candidates),
            "llm_accepted": llm_accepted_total,
            "deduped_on_commit": skipped,
            "committed": discovered,
        }

        result = {
            "candidates_count": len(candidates),
            "discovered": discovered,
            "skipped": skipped,
            "errors": errors,
            "reason": f"Discovered {discovered} relations from {len(candidates)} candidates",
            # Chunk-level observability (added 2026-04-16)
            "llm_chunks_total": len(chunks),
            "llm_chunks_succeeded": chunks_succeeded,
            "llm_chunks_failed": len(failed_chunk_indices),
            "llm_chunks_retried": total_chunk_retries,
            "llm_max_workers": max_workers,
            "failed_chunk_indices": sorted(failed_chunk_indices),
            "llm_provider": _llm_provider,
            "llm_model": _llm_model,
            "llm_max_tokens": 1500,
            # P4 step 1 (2026-04-17): full candidate funnel for A/B analysis.
            "funnel": full_funnel,
            **diagnostic_fields,
        }

        # Persist coverage on the theme so the panorama endpoint can surface
        # "已检查 / 未检查" (GPT suggestion: turn silent discovery into
        # auditable coverage).
        try:
            themes.record_discovery_run(theme_id, stats=result, job_id=job_id)
        except Exception as exc:  # pragma: no cover - telemetry only
            logger.warning("record_discovery_run(%s) failed: %s", theme_id, exc)

        return result

    def _recall_candidates(
        self,
        concepts: list[dict[str, Any]],
        exclude_existing: bool,
        *,
        require_endpoint_in: set[str] | None = None,
        return_funnel: bool = False,
        recall_mode: str | None = None,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, int]]:
        """Stage 1 dispatch: pick rules vs embedding recall based on flag.

        ``recall_mode`` (per-call) wins over ``DISCOVER_RECALL_MODE`` env.
        Tests use the override; operators use the env var. Default behaviour
        stays the rule-based path so nothing ships changed until someone
        explicitly opts in.
        """
        mode = (recall_mode or _current_recall_mode()).lower()
        if mode == _RECALL_MODE_EMBEDDING:
            # Gate 1 (GPT audit block-release A, 2026-04-17): refuse
            # embedding mode when the resolved provider is a fallback
            # (SHA-derived vectors have no semantic content). Operators
            # who know what they're doing can set
            # DISCOVER_ALLOW_FALLBACK_EMBEDDING=1 to bypass — useful for
            # tests + local dev without a real provider.
            gate_ok, gate_reason = self._embedding_mode_usable()
            if not gate_ok:
                logger.warning(
                    "embedding recall requested but not usable (%s); "
                    "falling back to rules mode",
                    gate_reason,
                )
                return self._recall_with_fallback_marker(
                    concepts,
                    exclude_existing=exclude_existing,
                    require_endpoint_in=require_endpoint_in,
                    return_funnel=return_funnel,
                    reason=gate_reason,
                )
            # Gate 2 (GPT audit block-release C): wrap the embedding path
            # in runtime try/except so a transient provider blip falls
            # back to rules rather than failing the whole discover job.
            try:
                return self._recall_candidates_embedding(
                    concepts,
                    exclude_existing=exclude_existing,
                    require_endpoint_in=require_endpoint_in,
                    return_funnel=return_funnel,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "embedding recall raised %s; falling back to rules mode",
                    exc,
                )
                return self._recall_with_fallback_marker(
                    concepts,
                    exclude_existing=exclude_existing,
                    require_endpoint_in=require_endpoint_in,
                    return_funnel=return_funnel,
                    reason=f"embedding provider error: {exc}",
                )
        return self._recall_candidates_rules(
            concepts,
            exclude_existing=exclude_existing,
            require_endpoint_in=require_endpoint_in,
            return_funnel=return_funnel,
        )

    def _embedding_mode_usable(self) -> tuple[bool, str]:
        """Return ``(ok, reason)``. ``ok=False`` means the dispatch should
        fall back to rules mode with ``reason`` recorded in the funnel.

        A provider is considered "unsafe for embedding mode" if its
        ``is_fallback`` attribute is truthy — that's the explicit
        contract on :class:`DeterministicEmbeddingProvider` and the
        default on the abstract :class:`EmbeddingProvider` base.
        """
        embedder = self._ensure_embedder()
        provider = getattr(embedder, "provider", None)
        if provider is None:
            return False, "no embedding provider available"
        if getattr(provider, "is_fallback", True):
            if os.environ.get("DISCOVER_ALLOW_FALLBACK_EMBEDDING") == "1":
                return True, ""
            return False, (
                f"fallback provider {provider.model!r} rejected "
                "(set DISCOVER_ALLOW_FALLBACK_EMBEDDING=1 to allow)"
            )
        return True, ""

    def _recall_with_fallback_marker(
        self,
        concepts: list[dict[str, Any]],
        *,
        exclude_existing: bool,
        require_endpoint_in: set[str] | None,
        return_funnel: bool,
        reason: str,
    ):
        """Run rules-mode recall and, if the caller wants the funnel back,
        stamp it with ``fallback_to_rules=True`` + ``fallback_reason``
        so downstream audit can tell this run was a fallback, not a
        first-choice rules run.
        """
        result = self._recall_candidates_rules(
            concepts,
            exclude_existing=exclude_existing,
            require_endpoint_in=require_endpoint_in,
            return_funnel=return_funnel,
        )
        if return_funnel:
            candidates, funnel = result
            funnel = dict(funnel)
            funnel["fallback_to_rules"] = True
            funnel["fallback_reason"] = reason
            return candidates, funnel
        return result

    def _recall_candidates_rules(
        self,
        concepts: list[dict[str, Any]],
        *,
        exclude_existing: bool,
        require_endpoint_in: set[str] | None = None,
        return_funnel: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, int]]:
        """Stage 1: Rule-based candidate recall (no LLM cost).

        Rules:
        - Only pairs from different articles
        - Type-complementary pairs prioritized
        - Skip if same canonical/alias
        - Skip if summary is empty on both sides
        - Skip if dedupe_key already exists
        - If require_endpoint_in is given: at least one endpoint must be in
          that set (incremental discover — only "new ↔ existing" pairs)

        Performance (P1.5): dedupe existence was previously checked with
        up to 12 ``has_dedupe_key()`` calls per pair (6 relation types × 2
        directions), each of which re-read the relations JSON from disk
        and full-scanned it. For a theme with 80+ concepts that turned
        into ~40k disk reads. We now load every existing dedupe_key into
        a single set at the start of the call and flip per-pair checks
        into O(1) membership lookups. Semantics are identical — the set
        is built from the same relation store ``has_dedupe_key`` reads.

        Funnel counts (P4 step 1, opt-in via ``return_funnel=True``):
        when set, returns ``(candidates, funnel)`` where funnel is a dict
        with per-filter survivor counts. Lets downstream A/B analysis
        (e.g. embedding recall vs rule recall) compare apples-to-apples.
        Default return shape stays backward-compatible.
        """
        candidates: list[dict[str, Any]] = []

        funnel: dict[str, int] = {
            "raw_pairs": 0,
            "after_incremental_gate": 0,
            "after_cross_article": 0,
            "after_dedupe_filter": 0,
            "final": 0,
        }

        # P1.5: preload existing dedupe_keys once per Stage-1 call. If the
        # caller explicitly asked to skip this filter (exclude_existing=False)
        # we don't need the set at all, so we avoid the (cheap) disk read too.
        existing_keys: set[str] = (
            load_existing_dedupe_keys() if exclude_existing else set()
        )

        for i, a in enumerate(concepts):
            for b in concepts[i + 1:]:
                funnel["raw_pairs"] += 1

                # Incremental gate: skip pairs that don't touch the "new" set.
                if require_endpoint_in is not None and (
                    a["entry_id"] not in require_endpoint_in
                    and b["entry_id"] not in require_endpoint_in
                ):
                    continue
                funnel["after_incremental_gate"] += 1

                # Must be from different projects
                a_projects = {l["project_id"] for l in a.get("source_links", [])}
                b_projects = {l["project_id"] for l in b.get("source_links", [])}
                if a_projects == b_projects:
                    continue  # Same article(s), skip
                funnel["after_cross_article"] += 1

                # Check dedupe via the preloaded set (O(1) each). Both
                # directions × every valid relation type, same semantics as
                # the old has_dedupe_key loop.
                if exclude_existing:
                    a_id = a["entry_id"]
                    b_id = b["entry_id"]
                    if any(
                        f"{a_id}|{rt}|{b_id}" in existing_keys
                        or f"{b_id}|{rt}|{a_id}" in existing_keys
                        for rt in VALID_RELATION_TYPES
                    ):
                        continue
                funnel["after_dedupe_filter"] += 1

                candidates.append({
                    "concept_a": a,
                    "concept_b": b,
                    "recall_score": _compute_pair_score(a, b),
                })

        # Sort by recall score, highest first
        candidates.sort(key=lambda c: -c["recall_score"])
        funnel["final"] = len(candidates)

        if return_funnel:
            return candidates, funnel
        return candidates

    def _ensure_embedder(self) -> ConceptEmbedder:
        """Lazily instantiate a :class:`ConceptEmbedder` the first time
        embedding-mode recall runs. Tests pass one in via ``__init__``
        so they can control the provider deterministically."""
        if self._embedder is None:
            self._embedder = ConceptEmbedder()
        return self._embedder

    def _recall_candidates_embedding(
        self,
        concepts: list[dict[str, Any]],
        *,
        exclude_existing: bool,
        require_endpoint_in: set[str] | None,
        return_funnel: bool,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, int]]:
        """Stage 1 embedding-mode recall (P4 steps 6+7).

        For each "new" concept (seeds, from ``require_endpoint_in``), pull
        the top-K nearest neighbours by cosine similarity of their cached
        embedding vectors. Apply the identical hard edge filters as rules
        mode (incremental gate / cross-article / dedupe) so boundary
        semantics never drift between paths. Finally, score survivors
        with :func:`_compute_pair_score` — the same light-rule function
        rules mode uses — so the final rerank stays interpretable.

        When ``require_endpoint_in`` is empty or None, every concept is
        treated as a seed. That's O(N·K) vs rules mode's O(N²); big win
        when K << N, neutral otherwise.
        """
        n = len(concepts)
        funnel: dict[str, int] = {
            # Match rules-mode raw_pairs so A/B dashboards can diff the
            # "enumerated universe" across modes even though we never
            # actually enumerated.
            "raw_pairs": n * (n - 1) // 2,
            "after_incremental_gate": 0,
            "after_cross_article": 0,
            "after_dedupe_filter": 0,
            "final": 0,
            # Embedding-specific: how many UNIQUE pairs the neighbour
            # search proposed, pre-filter.
            "embedding_neighbors": 0,
        }

        if n < 2:
            return ([], funnel) if return_funnel else []

        # Seeds: either the explicit "new" set or every concept.
        if require_endpoint_in:
            seeds = [c for c in concepts if c.get("entry_id") in require_endpoint_in]
        else:
            seeds = list(concepts)
        if not seeds:
            return ([], funnel) if return_funnel else []

        embedder = self._ensure_embedder()
        vectors = embedder.embed_concepts(concepts)

        # Top-K per seed. Canonical-ordered tuples so (a, b) / (b, a) collapse.
        proposed: set[tuple[str, str]] = set()
        for seed in seeds:
            seed_id = seed.get("entry_id")
            seed_vec = vectors.get(seed_id) if seed_id else None
            if not seed_vec:
                continue
            scored: list[tuple[str, float]] = []
            for other in concepts:
                other_id = other.get("entry_id")
                if not other_id or other_id == seed_id:
                    continue
                other_vec = vectors.get(other_id)
                if not other_vec:
                    continue
                sim = _cosine_similarity(seed_vec, other_vec)
                scored.append((other_id, sim))
            scored.sort(key=lambda pair: -pair[1])
            for other_id, _sim in scored[:_EMBEDDING_TOP_K]:
                pair = tuple(sorted([seed_id, other_id]))
                proposed.add(pair)

        funnel["embedding_neighbors"] = len(proposed)

        # Filter + score. Mirrors rules mode filter cascade exactly.
        by_id = {c["entry_id"]: c for c in concepts if c.get("entry_id")}
        existing_keys: set[str] = (
            load_existing_dedupe_keys() if exclude_existing else set()
        )

        candidates: list[dict[str, Any]] = []
        for a_id, b_id in proposed:
            a = by_id.get(a_id)
            b = by_id.get(b_id)
            if not a or not b:
                continue

            if require_endpoint_in is not None and (
                a_id not in require_endpoint_in
                and b_id not in require_endpoint_in
            ):
                continue
            funnel["after_incremental_gate"] += 1

            a_projects = {l["project_id"] for l in a.get("source_links", [])}
            b_projects = {l["project_id"] for l in b.get("source_links", [])}
            if a_projects == b_projects:
                continue
            funnel["after_cross_article"] += 1

            if exclude_existing:
                if any(
                    f"{a_id}|{rt}|{b_id}" in existing_keys
                    or f"{b_id}|{rt}|{a_id}" in existing_keys
                    for rt in VALID_RELATION_TYPES
                ):
                    continue
            funnel["after_dedupe_filter"] += 1

            candidates.append({
                "concept_a": a,
                "concept_b": b,
                "recall_score": _compute_pair_score(a, b),
            })

        candidates.sort(key=lambda c: -c["recall_score"])
        funnel["final"] = len(candidates)

        if return_funnel:
            return candidates, funnel
        return candidates

    def _llm_judge(
        self,
        candidates: list[dict[str, Any]],
        min_confidence: float,
        *,
        graph_cache: _GraphCache,
        chunk_idx: int = 0,
    ) -> list[dict[str, Any]]:
        """Stage 2: LLM precision judgment on candidate pairs.

        Args:
            candidates: list of candidate pairs for this chunk.
            min_confidence: minimum confidence threshold to accept a relation.
            graph_cache: shared _GraphCache instance (lifecycle owned by
                discover() so the cache is reused across all chunks).
            chunk_idx: index of this chunk within the overall batch, used only
                for log correlation.
        """
        from ...utils.llm_client import LLMClient
        from ..llm_mode_service import get_graphiti_llm_params

        # Route through the runtime mode switch (local / online DeepSeek /
        # bailian) rather than the static LLM_* env vars — keeps discovery on
        # the same provider as graph_builder so the user's "切换抽取模式" UI
        # actually owns this LLM call too. Snapshot once per chunk; do NOT
        # hold a reference (the mode may have changed by the next chunk).
        params = get_graphiti_llm_params()
        llm = LLMClient(
            api_key=params["api_key"],
            base_url=params["base_url"],
            model=params["model"],
        )
        llm.timeout_seconds = _discover_llm_timeout_seconds()
        llm.max_retries = 0

        # entry_id -> canonical concept entry, for cheap lookup when building
        # evidence refs.
        entry_lookup: dict[str, dict[str, Any]] = {}
        for c in candidates:
            for side in ("concept_a", "concept_b"):
                e = c.get(side) or {}
                eid = e.get("entry_id")
                if eid:
                    entry_lookup[eid] = e

        pairs_for_prompt = []
        for c in candidates:
            a = c["concept_a"]
            b = c["concept_b"]
            a_projects = [l.get("project_name", l["project_id"]) for l in a.get("source_links", [])]
            b_projects = [l.get("project_name", l["project_id"]) for l in b.get("source_links", [])]
            pairs_for_prompt.append({
                "pair_index": len(pairs_for_prompt),
                "a_id": a["entry_id"],
                "a_name": a["canonical_name"],
                "a_type": a.get("concept_type", "Concept"),
                "a_description": (a.get("description") or "")[:300],
                "a_articles": a_projects[:3],
                "b_id": b["entry_id"],
                "b_name": b["canonical_name"],
                "b_type": b.get("concept_type", "Concept"),
                "b_description": (b.get("description") or "")[:300],
                "b_articles": b_projects[:3],
            })

        system_prompt = (
            "你是跨文章知识发现系统。你的任务是判断来自不同文章的概念对之间是否存在有意义的语义关系。\n\n"
            "关键原则：\n"
            "- 只识别真正有价值的关系，不要强行关联\n"
            "- 每条关系必须有可追溯的证据支撑\n"
            "- reason 要说清楚为什么相关\n"
            "- evidence_bridge 要指出具体的证据链路\n"
            "- 如果两个概念没有有意义的关系，跳过不输出\n\n"
            f"{_RELATION_TYPE_SPEC}\n\n"
            "严格返回 JSON，不要输出 markdown。"
        )

        user_prompt = (
            f"以下是 {len(pairs_for_prompt)} 对候选概念对：\n"
            f"{json.dumps(pairs_for_prompt, ensure_ascii=False, indent=2)}\n\n"
            "对每对概念判断：是否存在跨文章关系？\n"
            "- 如果存在，输出关系详情\n"
            "- 如果不存在有意义的关系，不要输出该 pair\n\n"
            "输出格式：\n"
            '{"relations": [\n'
            '  {\n'
            '    "pair_index": 0,\n'
            '    "source_entry_id": "a_id or b_id (关系的起点)",\n'
            '    "target_entry_id": "b_id or a_id (关系的终点)",\n'
            '    "relation_type": "design_inspiration|technical_foundation|problem_solution|contrast_reference|capability_constraint|pattern_reuse",\n'
            '    "directionality": "directed|bidirectional",\n'
            '    "reason": "一句话说明为什么相关",\n'
            '    "evidence_bridge": "具体的证据链路，引用description中的关键信息",\n'
            '    "confidence": 0.0-1.0\n'
            '  }\n'
            ']}'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = llm.chat_json(messages=messages, temperature=0.2, max_tokens=1500)
        raw_relations = result.get("relations", [])

        # Post-process: filter by confidence, add metadata
        accepted: list[dict[str, Any]] = []
        for rel in raw_relations:
            conf = rel.get("confidence", 0)
            if conf < min_confidence:
                continue

            rtype = rel.get("relation_type", "")
            if rtype not in VALID_RELATION_TYPES:
                continue

            # Build discovery_path from pair data
            pair_idx = rel.get("pair_index", 0)
            if 0 <= pair_idx < len(pairs_for_prompt):
                pair = pairs_for_prompt[pair_idx]
                discovery_path = [pair["a_name"], pair["b_name"]]
                # Add article name
                articles = pair.get("a_articles", []) + pair.get("b_articles", [])
                if articles:
                    discovery_path.append(articles[0])
            else:
                discovery_path = []

            # Build evidence_refs from actual article graph node summaries.
            # NEVER copy evidence_bridge into a "quote" field — that string is
            # LLM reasoning, not source-article text, and was historically
            # mislabelled as "原文引用" in the UI. The resolver pulls the node
            # summary captured during phase-1 ingestion (zero-fallback rule:
            # if no match, the ref is marked degraded with a reason).
            src_id = rel.get("source_entry_id", "")
            tgt_id = rel.get("target_entry_id", "")
            bridge_text = rel.get("evidence_bridge", "")
            evidence_refs = build_evidence_refs_for_pair(
                source_entry=entry_lookup.get(src_id, {}),
                target_entry=entry_lookup.get(tgt_id, {}),
                graph_cache=graph_cache,
            )

            accepted.append({
                "source_entry_id": src_id,
                "target_entry_id": tgt_id,
                "relation_type": rtype,
                "directionality": rel.get("directionality", "directed"),
                "reason": rel.get("reason", ""),
                "evidence_bridge": bridge_text,
                "evidence_refs": evidence_refs,
                "discovery_path": discovery_path,
                "confidence": conf,
                "model_info": {"model": getattr(llm, "model", "unknown"), "prompt_version": "crossrel_v1"},
            })

        return accepted
