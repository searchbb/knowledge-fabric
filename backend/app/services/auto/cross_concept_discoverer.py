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

import json
import logging
from typing import Any

from ..registry import global_concept_registry as registry
from ..registry import global_theme_registry as themes
from ..registry.cross_concept_relations import (
    create_relation,
    has_dedupe_key,
    CrossRelationDuplicateError,
    VALID_RELATION_TYPES,
)
from ..registry.source_evidence_resolver import (
    _GraphCache,
    build_evidence_refs_for_pair,
)

logger = logging.getLogger("mirofish.cross_concept_discoverer")

# Types that tend to form cross-article bridges
_COMPLEMENTARY_TYPE_PAIRS = {
    ("Problem", "Solution"),
    ("Problem", "Technology"),
    ("Topic", "Technology"),
    ("Topic", "Solution"),
    ("Topic", "Product"),
    ("Constraint", "Solution"),
    ("Constraint", "Technology"),
    ("Evidence", "Topic"),
    ("Example", "Topic"),
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
    ):
        self.actor_id = actor_id
        self.source = source

    def discover(
        self,
        *,
        theme_id: str,
        entry_ids: list[str] | None = None,
        max_pairs: int = 50,
        min_confidence: float = 0.6,
        exclude_existing: bool = True,
        run_id: str = "",
    ) -> dict[str, Any]:
        """Run two-stage discovery for a theme.

        Returns dict with: candidates_count, discovered, skipped, errors
        """
        # Load theme and its concepts
        theme = themes.get_theme(theme_id)
        memberships = theme.get("concept_memberships", [])
        member_entry_ids = [m["entry_id"] for m in memberships]

        # Filter to specified entry_ids if provided
        if entry_ids:
            member_entry_ids = [eid for eid in member_entry_ids if eid in entry_ids]

        # Load concept details
        all_entries = {e["entry_id"]: e for e in registry.list_entries()}
        concepts = []
        for eid in member_entry_ids:
            entry = all_entries.get(eid)
            if entry:
                concepts.append(entry)

        if len(concepts) < 2:
            return {
                "candidates_count": 0,
                "discovered": 0,
                "skipped": 0,
                "errors": [],
                "reason": f"Need at least 2 concepts, got {len(concepts)}",
            }

        # Stage 1: Candidate recall
        candidates = self._recall_candidates(concepts, exclude_existing)
        logger.info(
            "Stage 1 recall: %d candidates from %d concepts",
            len(candidates), len(concepts),
        )

        # Limit pairs
        if len(candidates) > max_pairs:
            candidates = candidates[:max_pairs]

        if not candidates:
            return {
                "candidates_count": 0,
                "discovered": 0,
                "skipped": 0,
                "errors": [],
                "reason": "No candidate pairs after recall filtering",
            }

        # Stage 2: LLM precision judgment
        discovered = 0
        skipped = 0
        errors: list[str] = []

        # Batch candidates into chunks of ~10 for LLM
        chunk_size = 10
        for i in range(0, len(candidates), chunk_size):
            chunk = candidates[i:i + chunk_size]
            try:
                relations = self._llm_judge(chunk, min_confidence)
                for rel_data in relations:
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
                        )
                        discovered += 1
                    except CrossRelationDuplicateError:
                        skipped += 1
                    except Exception as exc:
                        errors.append(f"Create failed: {exc}")
            except Exception as exc:
                errors.append(f"LLM judge failed for chunk {i}: {exc}")

        result = {
            "candidates_count": len(candidates),
            "discovered": discovered,
            "skipped": skipped,
            "errors": errors,
            "reason": f"Discovered {discovered} relations from {len(candidates)} candidates",
        }

        # Persist coverage on the theme so the panorama endpoint can surface
        # "已检查 / 未检查" (GPT suggestion: turn silent discovery into
        # auditable coverage).
        try:
            themes.record_discovery_run(theme_id, stats=result)
        except Exception as exc:  # pragma: no cover - telemetry only
            logger.warning("record_discovery_run(%s) failed: %s", theme_id, exc)

        return result

    def _recall_candidates(
        self,
        concepts: list[dict[str, Any]],
        exclude_existing: bool,
    ) -> list[dict[str, Any]]:
        """Stage 1: Rule-based candidate recall (no LLM cost).

        Rules:
        - Only pairs from different articles
        - Type-complementary pairs prioritized
        - Skip if same canonical/alias
        - Skip if summary is empty on both sides
        - Skip if dedupe_key already exists
        """
        candidates: list[dict[str, Any]] = []

        for i, a in enumerate(concepts):
            for b in concepts[i + 1:]:
                # Must be from different projects
                a_projects = {l["project_id"] for l in a.get("source_links", [])}
                b_projects = {l["project_id"] for l in b.get("source_links", [])}
                if a_projects == b_projects:
                    continue  # Same article(s), skip

                # Get descriptions (may be empty — many concepts lack descriptions)
                a_desc = (a.get("description") or "").strip()
                b_desc = (b.get("description") or "").strip()

                # Check dedupe (both directions, all types)
                if exclude_existing:
                    any_exists = False
                    for rt in VALID_RELATION_TYPES:
                        if has_dedupe_key(f"{a['entry_id']}|{rt}|{b['entry_id']}"):
                            any_exists = True
                            break
                        if has_dedupe_key(f"{b['entry_id']}|{rt}|{a['entry_id']}"):
                            any_exists = True
                            break
                    if any_exists:
                        continue

                # Score: type complementarity + description overlap
                score = 0.0
                a_type = a.get("concept_type", "Concept")
                b_type = b.get("concept_type", "Concept")
                if (a_type, b_type) in _COMPLEMENTARY_TYPE_PAIRS or (b_type, a_type) in _COMPLEMENTARY_TYPE_PAIRS:
                    score += 2.0

                # Simple keyword overlap in descriptions
                if a_desc and b_desc:
                    a_words = set(a_desc.lower().split())
                    b_words = set(b_desc.lower().split())
                    overlap = len(a_words & b_words)
                    if overlap > 2:
                        score += min(overlap * 0.3, 2.0)

                # Different types = more interesting
                if a_type != b_type:
                    score += 0.5

                candidates.append({
                    "concept_a": a,
                    "concept_b": b,
                    "recall_score": score,
                })

        # Sort by recall score, highest first
        candidates.sort(key=lambda c: -c["recall_score"])
        return candidates

    def _llm_judge(
        self,
        candidates: list[dict[str, Any]],
        min_confidence: float,
    ) -> list[dict[str, Any]]:
        """Stage 2: LLM precision judgment on candidate pairs."""
        from ...utils.llm_client import LLMClient
        llm = LLMClient()

        # Share one graph-data cache across every pair in this chunk so we
        # never reload a source article more than once per LLM call.
        graph_cache = _GraphCache()

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

        result = llm.chat_json(messages=messages, temperature=0.2, max_tokens=4096)
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
