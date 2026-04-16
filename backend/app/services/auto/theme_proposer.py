"""
Auto theme assignment — Hub-and-Spoke model.

2026-04-12 redesign: replaces per-article theme creation with semantic
classification of concepts into existing global themes.

Strategy D (GPT consult):
  - User defines theme boundaries (manual create)
  - Auto-pipeline assigns concepts to existing themes inline (LLM-based)
  - Only creates new theme **candidates** (not active) when orphan ratio
    is high and core orphan count >= 3

Key design rules:
  - Theme naming authority = user, NOT LLM
  - LLM only classifies concepts into existing themes
  - article_title is NOT used for theme naming (root cause of old 1:1 bug)
  - Confidence thresholds: >= 0.78 member, 0.55-0.78 candidate, <0.55 orphan
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..registry import global_theme_registry as themes
from ..registry import global_concept_registry as registry

logger = logging.getLogger("mirofish.auto_theme_proposer")

# Bumped whenever proposer decision logic changes (GPT C9 audit — lets a bad
# decision get attributed back to a specific proposer iteration).
PROPOSER_VERSION = "v2.candidate_visible_2026-04-16"


@dataclass
class AutoThemeResult:
    """Result of theme assignment for one pipeline run."""
    action: str  # "noop" | "classified" | "classified_with_new_candidate"
    assignments: list[dict] = field(default_factory=list)
    new_candidate_theme: Optional[dict] = None
    orphan_count: int = 0
    degraded: bool = False
    reason: str = ""

    # Legacy compat fields (pipeline_runner._build_summary reads these)
    theme_id: Optional[str] = None
    theme_name: Optional[str] = None
    attached_concept_ids: list[str] = field(default_factory=list)

    # Audit (GPT consult df46f0a3b611600b, 2026-04-16): expose what the proposer
    # actually saw and how it decided so split-theme regressions are diagnosable
    # from the run summary without grepping logs.
    audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "assignments": self.assignments,
            "new_candidate_theme": self.new_candidate_theme,
            "orphan_count": self.orphan_count,
            "degraded": self.degraded,
            "reason": self.reason,
            # Legacy compat
            "theme_id": self.theme_id,
            "theme_name": self.theme_name,
            "attached_concept_ids": self.attached_concept_ids,
            "audit": self.audit,
        }


class AutoThemeProposer:
    """Classify concepts into existing global themes using LLM."""

    def __init__(
        self,
        *,
        member_threshold: float = 0.78,
        candidate_threshold: float = 0.55,
        min_concepts_for_action: int = 2,
        orphan_ratio_for_new_theme: float = 0.6,
        min_core_orphans_for_new_theme: int = 3,
        actor_id: str = "auto_pipeline",
        source: str = "auto_url_pipeline",
    ):
        self.member_threshold = member_threshold
        self.candidate_threshold = candidate_threshold
        self.min_concepts_for_action = min_concepts_for_action
        self.orphan_ratio_for_new_theme = orphan_ratio_for_new_theme
        self.min_core_orphans_for_new_theme = min_core_orphans_for_new_theme
        self.actor_id = actor_id
        self.source = source

    def process(
        self,
        *,
        project_id: str,
        project_name: str = "",
        new_canonical_ids: list[str],
        run_id: str = "",
        article_title: str = "",
    ) -> AutoThemeResult:
        """Classify new canonical concepts into existing themes."""
        # Snapshot the thresholds this run used so audit can explain post-hoc
        # why a concept attached/didn't after any future tuning.
        threshold_snapshot = {
            "member_threshold": self.member_threshold,
            "candidate_threshold": self.candidate_threshold,
            "orphan_ratio_for_new_theme": self.orphan_ratio_for_new_theme,
            "min_core_orphans_for_new_theme": self.min_core_orphans_for_new_theme,
        }

        if len(new_canonical_ids) < self.min_concepts_for_action:
            return AutoThemeResult(
                action="noop",
                reason=f"only {len(new_canonical_ids)} canonical(s), need >= {self.min_concepts_for_action}",
                audit={
                    "proposer_version": PROPOSER_VERSION,
                    "threshold_snapshot": threshold_snapshot,
                    "visible_active_theme_count": 0,
                    "visible_candidate_theme_count": 0,
                    "skip_reason": "below_min_concepts",
                },
            )

        # Plumbing fix (GPT consult d10c98cab0b64a56 rule 1, 2026-04-16):
        # before this, only status="active" themes were visible to the
        # proposer — but auto-created themes are always status="candidate"
        # and never get auto-promoted, so every new article saw an empty
        # active-theme list → created its own theme island. Include
        # candidate themes in the classification working set. Keep
        # list_themes(status="active") semantics intact for other callers.
        active_themes = themes.list_themes(status="active")
        candidate_themes = themes.list_themes(status="candidate")
        classifiable_themes = list(active_themes) + list(candidate_themes)

        audit: dict[str, Any] = {
            "proposer_version": PROPOSER_VERSION,
            "threshold_snapshot": threshold_snapshot,
            "visible_active_theme_count": len(active_themes),
            "visible_candidate_theme_count": len(candidate_themes),
            "classifiable_theme_ids": [t["theme_id"] for t in classifiable_themes][:20],
        }

        concepts = self._load_concept_details(new_canonical_ids)

        if not concepts:
            audit["skip_reason"] = "no_concept_details"
            return AutoThemeResult(action="noop", reason="no concept details found", audit=audit)

        # If neither active nor candidate themes exist, this is a genuine
        # first-article cold start → propose candidate.
        if not classifiable_themes:
            audit["decision"] = "create_theme_cold_start"
            result = self._handle_no_themes(concepts, run_id, article_title)
            result.audit = {**audit, **result.audit}
            return result

        # LLM classification against the unified working set. The prompt
        # exposes theme.status so the LLM can weight stable active themes
        # over provisional candidates (GPT consult rule 1 副作用防护).
        try:
            llm_result = self._classify_via_llm(
                concepts, classifiable_themes, article_title
            )
            audit["classification_source"] = "llm"
        except Exception as e:
            logger.warning("LLM classification failed, falling back to keyword match: %s", e)
            llm_result = self._fallback_keyword_match(concepts, classifiable_themes)
            audit["classification_source"] = "keyword_fallback"
            audit["llm_error"] = str(e)[:200]
            if llm_result is None:
                return AutoThemeResult(
                    action="noop", degraded=True,
                    reason=f"LLM failed and keyword fallback found no matches: {e}",
                    audit=audit,
                )

        result = self._apply_classification(
            llm_result, concepts, classifiable_themes, run_id, article_title
        )
        # Preserve run-level audit without clobbering anything classification
        # downstream may have added.
        result.audit = {**audit, **result.audit}
        return result

    def _load_concept_details(self, entry_ids: list[str]) -> list[dict]:
        all_entries = {e["entry_id"]: e for e in registry.list_entries()}
        result = []
        for eid in entry_ids:
            entry = all_entries.get(eid)
            if entry:
                result.append({
                    "entry_id": eid,
                    "canonical_name": entry.get("canonical_name", ""),
                    "concept_type": entry.get("concept_type", "Concept"),
                })
        return result

    def _classify_via_llm(
        self,
        concepts: list[dict],
        active_themes: list[dict],
        article_title: str = "",
    ) -> dict:
        from ...utils.llm_client import LLMClient
        llm = LLMClient()

        themes_for_prompt = []
        for t in active_themes[:10]:
            members = [m for m in t.get("concept_memberships", []) if m.get("role") == "member"]
            top_members = sorted(members, key=lambda m: -m.get("score", 0))[:5]
            # Resolve names
            all_entries = {e["entry_id"]: e for e in registry.list_entries()}
            member_names = []
            for m in top_members:
                entry = all_entries.get(m["entry_id"])
                if entry:
                    member_names.append(entry.get("canonical_name", m["entry_id"]))
            themes_for_prompt.append({
                "theme_id": t["theme_id"],
                "name": t["name"],
                "status": t.get("status", "active"),
                "description": t.get("description", ""),
                "keywords": t.get("keywords", []),
                "example_concepts": member_names[:5],
            })

        concepts_for_prompt = [
            {"entry_id": c["entry_id"], "name": c["canonical_name"], "type": c["concept_type"]}
            for c in concepts
        ]

        system_prompt = (
            "你是知识治理系统中的主题归属判定器。\n"
            "你的任务不是为每篇文章发明新主题，而是把 canonical 概念归入少量稳定的全局主题。\n"
            "优先复用已有主题，谨慎提议新主题。\n"
            "主题列表中每个主题都带有 status 字段：\n"
            "  - status=active 表示该主题已稳定运行，跨多文章存在；优先归到这里。\n"
            "  - status=candidate 表示该主题仍在观察期（单文章/新建）；可以归入，\n"
            "    但证据需要略强（如多个概念和该主题高度相关），否则说明是另一个主题域。\n"
            "主题应该是可跨文章持续累积的问题域、方法域或工作域。\n"
            "工具名/产品名/单篇文章标题通常不是主题。\n"
            "严格返回 JSON，不要输出 markdown。"
        )

        user_prompt = (
            f"已有主题列表：\n{json.dumps(themes_for_prompt, ensure_ascii=False, indent=2)}\n\n"
            f"本次 canonical 概念：\n{json.dumps(concepts_for_prompt, ensure_ascii=False, indent=2)}\n\n"
        )
        if article_title:
            user_prompt += f"文章标题（仅供参考，不要用于主题命名）：{article_title}\n\n"

        user_prompt += (
            "对每个 concept 判断：\n"
            '- attach_to_theme_id: 归属的已有主题ID，或 null（表示无法归入）\n'
            '- confidence: 0~1 的置信度\n'
            '- reason: 一句话理由\n\n'
            "严格返回 JSON，格式：\n"
            '{"assignments": [{"entry_id": "...", "attach_to_theme_id": "..." | null, '
            '"confidence": 0.85, "reason": "..."}]}'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = llm.chat_json(messages=messages, temperature=0.2, max_tokens=4096)
        return result

    def _fallback_keyword_match(
        self, concepts: list[dict], active_themes: list[dict]
    ) -> Optional[dict]:
        assignments = []
        for c in concepts:
            name_lower = c["canonical_name"].lower()
            best_theme = None
            best_score = 0.0
            for t in active_themes:
                keywords = [kw.lower() for kw in t.get("keywords", [])]
                theme_name_lower = t["name"].lower()
                score = 0.0
                for kw in keywords:
                    if kw in name_lower or name_lower in kw:
                        score = max(score, 0.6)
                for word in theme_name_lower.split():
                    if len(word) >= 2 and word in name_lower:
                        score = max(score, 0.5)
                if score > best_score:
                    best_score = score
                    best_theme = t
            assignments.append({
                "entry_id": c["entry_id"],
                "attach_to_theme_id": best_theme["theme_id"] if best_theme and best_score >= 0.5 else None,
                "confidence": best_score,
                "reason": "keyword_fallback",
            })
        return {"assignments": assignments} if assignments else None

    def _apply_classification(
        self,
        llm_result: dict,
        concepts: list[dict],
        active_themes: list[dict],
        run_id: str,
        article_title: str,
    ) -> AutoThemeResult:
        assignments_raw = llm_result.get("assignments", [])
        theme_ids = {t["theme_id"] for t in active_themes}

        result_assignments = []
        orphans = []
        all_attached_ids = []

        for a in assignments_raw:
            entry_id = a.get("entry_id", "")
            target_theme = a.get("attach_to_theme_id")
            confidence = float(a.get("confidence", 0))
            reason = a.get("reason", "")

            if target_theme and target_theme in theme_ids and confidence >= self.member_threshold:
                try:
                    themes.attach_concepts(
                        target_theme, [entry_id],
                        role="member", score=confidence,
                        actor_type="auto", actor_id=self.actor_id,
                        run_id=run_id, source=self.source,
                    )
                    result_assignments.append({
                        "entry_id": entry_id, "theme_id": target_theme,
                        "role": "member", "confidence": confidence, "reason": reason,
                    })
                    all_attached_ids.append(entry_id)
                except Exception as e:
                    logger.warning("attach member %s→%s failed: %s", entry_id, target_theme, e)

            elif target_theme and target_theme in theme_ids and confidence >= self.candidate_threshold:
                try:
                    themes.attach_concepts(
                        target_theme, [entry_id],
                        role="candidate", score=confidence,
                        actor_type="auto", actor_id=self.actor_id,
                        run_id=run_id, source=self.source,
                    )
                    result_assignments.append({
                        "entry_id": entry_id, "theme_id": target_theme,
                        "role": "candidate", "confidence": confidence, "reason": reason,
                    })
                    all_attached_ids.append(entry_id)
                except Exception as e:
                    logger.warning("attach candidate %s→%s failed: %s", entry_id, target_theme, e)
            else:
                orphans.append({"entry_id": entry_id, "confidence": confidence, "reason": reason})

        # New theme candidate?
        new_candidate = None
        orphan_ratio = len(orphans) / max(len(assignments_raw), 1)
        core_orphans = [o for o in orphans if self._is_core_concept_type(o["entry_id"], concepts)]

        if (
            orphan_ratio >= self.orphan_ratio_for_new_theme
            and len(core_orphans) >= self.min_core_orphans_for_new_theme
        ):
            new_candidate = self._propose_new_theme_candidate(
                orphans, concepts, run_id, article_title
            )

        action = "classified"
        if new_candidate:
            action = "classified_with_new_candidate"

        # Set legacy compat fields
        first_theme = result_assignments[0] if result_assignments else None

        return AutoThemeResult(
            action=action,
            assignments=result_assignments,
            new_candidate_theme=new_candidate,
            orphan_count=len(orphans),
            reason=f"{len(result_assignments)} assigned, {len(orphans)} orphans",
            theme_id=new_candidate["theme_id"] if new_candidate else (first_theme["theme_id"] if first_theme else None),
            theme_name=new_candidate["name"] if new_candidate else None,
            attached_concept_ids=all_attached_ids,
        )

    def _is_core_concept_type(self, entry_id: str, concepts: list[dict]) -> bool:
        core_types = {"Problem", "Solution", "Architecture", "Topic", "Mechanism"}
        for c in concepts:
            if c["entry_id"] == entry_id:
                return c.get("concept_type", "") in core_types
        return False

    def _propose_new_theme_candidate(
        self, orphans: list[dict], concepts: list[dict],
        run_id: str, article_title: str,
    ) -> Optional[dict]:
        orphan_ids = {o["entry_id"] for o in orphans}
        orphan_concepts = [c for c in concepts if c["entry_id"] in orphan_ids]

        try:
            from ...utils.llm_client import LLMClient
            llm = LLMClient()

            concept_list = "\n".join(
                f"- [{c['concept_type']}] {c['canonical_name']}" for c in orphan_concepts
            )
            messages = [
                {"role": "system", "content": (
                    "你是知识图谱主题命名助手。给你一组 canonical 概念，"
                    "请生成一个跨文章可复用的知识域主题名（不超过 15 字），"
                    "以及一句话描述（30-60 字）和 3-5 个关键词。\n"
                    "主题名必须是可跨文章累积的问题域/方法域/工作域，"
                    "禁止使用文章标题、单个产品名。\n"
                    "严格返回 JSON，不要输出 markdown。"
                )},
                {"role": "user", "content": (
                    f"以下概念暂时无法归入现有主题：\n{concept_list}\n\n"
                    '返回 JSON：{"name": "...", "description": "...", "keywords": ["...", "..."]}'
                )},
            ]
            result = llm.chat_json(messages=messages, temperature=0.3, max_tokens=1024)
            theme_name = str(result.get("name", "")).strip()
            theme_desc = str(result.get("description", "")).strip()
            theme_keywords = result.get("keywords", [])

            if not theme_name:
                return None

            new_theme = themes.create_theme(
                name=theme_name, description=theme_desc,
                status="candidate", source="auto_candidate",
                keywords=theme_keywords if isinstance(theme_keywords, list) else [],
            )

            orphan_entry_ids = [o["entry_id"] for o in orphans]
            themes.attach_concepts(
                new_theme["theme_id"], orphan_entry_ids,
                role="member", score=0.7,
                actor_type="auto", actor_id=self.actor_id,
                run_id=run_id, source=self.source,
            )

            logger.info(
                "Created new theme candidate: %s (%s) with %d orphan concepts",
                theme_name, new_theme["theme_id"], len(orphan_entry_ids),
            )

            return {
                "theme_id": new_theme["theme_id"],
                "name": theme_name,
                "description": theme_desc,
                "status": "candidate",
                "attached_count": len(orphan_entry_ids),
            }

        except Exception as e:
            logger.warning("Failed to propose new theme candidate: %s", e)
            return None

    def _handle_no_themes(
        self, concepts: list[dict], run_id: str, article_title: str,
    ) -> AutoThemeResult:
        core = [c for c in concepts if c.get("concept_type") in {
            "Problem", "Solution", "Architecture", "Topic", "Mechanism"
        }]
        if len(core) >= self.min_core_orphans_for_new_theme:
            candidate = self._propose_new_theme_candidate(
                [{"entry_id": c["entry_id"], "confidence": 0} for c in concepts],
                concepts, run_id, article_title,
            )
            return AutoThemeResult(
                action="classified_with_new_candidate",
                new_candidate_theme=candidate,
                orphan_count=len(concepts),
                reason="no active themes exist, proposed candidate",
                theme_id=candidate["theme_id"] if candidate else None,
                theme_name=candidate["name"] if candidate else None,
            )
        return AutoThemeResult(
            action="noop",
            orphan_count=len(concepts),
            reason=f"no active themes and only {len(core)} core concepts",
        )
