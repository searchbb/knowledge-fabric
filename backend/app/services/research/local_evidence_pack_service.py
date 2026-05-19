"""Local Evidence Pack generation for strategic ResearchProjects.

P2 is deliberately local-only: it reads KFC registry/theme/source evidence
stores, produces reviewable candidates, and never calls models, external
research, workers, or schedulers.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Any

from ...models.research_project import ResearchProject
from ..registry.global_concept_registry import list_entries
from ..registry.global_theme_registry import list_themes
from ..registry import source_evidence_resolver


RETRIEVAL_VERSION = "local_evidence_pack_v1"
DEFAULT_KEYWORDS = [
    "Agent-ready",
    "Agent",
    "Harness",
    "企业软件",
    "软件栈",
    "业务语义",
    "API",
    "MCP",
    "权限",
    "审批",
    "回写",
    "测试",
    "行业资产",
]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _new_pack_id() -> str:
    return f"lep_{secrets.token_hex(6)}"


def _new_evidence_id() -> str:
    return f"ev_{secrets.token_hex(6)}"


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


def _tokens(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9+_.-]*|[\u4e00-\u9fff]{2,}", text or "")
    seen: set[str] = set()
    result: list[str] = []
    for item in raw:
        token = _normalize(item)
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        result.append(item.strip())
    return result


def _project_text(project: ResearchProject) -> str:
    brief = project.research_brief or {}
    questions = " ".join(str(item) for item in (brief.get("key_questions") or []))
    return " ".join([
        project.title,
        project.background,
        project.audience,
        project.goal,
        str(brief.get("problem_statement") or ""),
        str(brief.get("scope") or ""),
        questions,
    ])


def build_query(project: ResearchProject, *, extra_keywords: list[str] | None = None) -> dict[str, Any]:
    text = _project_text(project)
    keywords: list[str] = []
    for token in [*(extra_keywords or []), *_tokens(text)]:
        if _normalize(token) not in {_normalize(k) for k in keywords}:
            keywords.append(token)
    lower_text = _normalize(text)
    for keyword in DEFAULT_KEYWORDS:
        if _normalize(keyword) in lower_text and _normalize(keyword) not in {_normalize(k) for k in keywords}:
            keywords.append(keyword)
    return {
        "topic": project.title,
        "research_brief": project.research_brief or {},
        "key_questions": list((project.research_brief or {}).get("key_questions") or []),
        "keywords": keywords[:40],
    }


def _match_score(haystacks: dict[str, str], keywords: list[str]) -> tuple[float, list[str]]:
    title_hits = 0
    alias_hits = 0
    desc_hits = 0
    why: list[str] = []
    for keyword in keywords:
        needle = _normalize(keyword)
        if not needle:
            continue
        if needle in _normalize(haystacks.get("title", "")):
            title_hits += 1
            why.append(f"title_match: {keyword}")
        if needle in _normalize(haystacks.get("aliases", "")):
            alias_hits += 1
            why.append(f"alias_match: {keyword}")
        if needle in _normalize(haystacks.get("description", "")):
            desc_hits += 1
            why.append(f"description_overlap: {keyword}")
        if needle in _normalize(haystacks.get("keywords", "")):
            alias_hits += 1
            why.append(f"keyword_match: {keyword}")
    if not keywords:
        return 0.0, []
    score = 0.0
    if title_hits:
        score += 0.35
    if alias_hits:
        score += 0.25
    if desc_hits:
        score += 0.20
    overlap = min((title_hits + alias_hits + desc_hits) / max(len(keywords), 1), 1)
    score += 0.20 * overlap
    return min(score, 1.0), why


def _theme_refs_by_entry(themes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    refs: dict[str, list[dict[str, Any]]] = {}
    for theme in themes:
        ref = {"theme_id": theme.get("theme_id", ""), "name": theme.get("name", "")}
        for membership in theme.get("concept_memberships") or []:
            entry_id = membership.get("entry_id")
            if entry_id:
                refs.setdefault(entry_id, []).append(ref)
    return refs


def generate_local_evidence_pack(
    project: ResearchProject,
    *,
    keywords: list[str] | None = None,
    limit: int = 30,
    include_degraded: bool = True,
) -> dict[str, Any]:
    query = build_query(project, extra_keywords=keywords or [])
    query_keywords = query["keywords"]
    themes = list_themes()
    theme_refs = _theme_refs_by_entry(themes)
    graph_cache = source_evidence_resolver._GraphCache()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in list_entries():
        source_text = " ".join(str(entry.get(key) or "") for key in (
            "source_quote",
            "source_excerpt",
            "source_context",
            "source_article_title",
            "source_article_id",
        ))
        source_refs = source_evidence_resolver.resolve_source_evidence(
            entry,
            max_refs=3,
            graph_cache=graph_cache,
        )
        if not include_degraded:
            source_refs = [ref for ref in source_refs if not ref.get("degraded")]
        score, why = _match_score(
            {
                "title": str(entry.get("canonical_name") or ""),
                "aliases": " ".join(str(a) for a in (entry.get("aliases") or [])),
                "description": " ".join([str(entry.get("description") or ""), source_text]),
                "keywords": str(entry.get("concept_type") or ""),
            },
            query_keywords,
        )
        if theme_refs.get(entry.get("entry_id")):
            score += 0.10
            why.append("theme_match")
        if source_refs and any(not ref.get("degraded") for ref in source_refs):
            score += 0.10
            why.append("source_ref_available")
        elif not source_refs:
            score -= 0.15
        if source_refs and all(ref.get("degraded") for ref in source_refs):
            score -= 0.10
        if score <= 0 or not why:
            continue
        key = f"concept:{entry.get('entry_id')}"
        if key in seen:
            continue
        seen.add(key)
        source_ref = next((ref for ref in source_refs if not ref.get("degraded")), source_refs[0] if source_refs else {})
        candidates.append({
            "evidence_id": _new_evidence_id(),
            "status": "candidate",
            "evidence_type": "concept",
            "title": entry.get("canonical_name", ""),
            "summary": entry.get("description", "") or "本地概念注册表条目，暂无描述。",
            "why_matched": why[:8],
            "score": round(max(min(score, 1.0), 0.0), 3),
            "source_concept_id": entry.get("entry_id", ""),
            "source_article_id": source_ref.get("source_article_id") or entry.get("source_article_id", ""),
            "source_article_title": source_ref.get("source_article_title") or entry.get("source_article_title", ""),
            "source_markdown_path": source_ref.get("source_markdown_path") or entry.get("source_markdown_path", ""),
            "source_content_hash": source_ref.get("source_content_hash") or entry.get("source_content_hash", ""),
            "source_material_slice_id": source_ref.get("source_material_slice_id") or entry.get("source_material_slice_id", ""),
            "source_lead_id": source_ref.get("source_lead_id") or entry.get("source_lead_id", ""),
            "source_quote": source_ref.get("source_text") or entry.get("source_quote", ""),
            "source_excerpt": source_ref.get("source_excerpt") or entry.get("source_excerpt", ""),
            "source_context": source_ref.get("source_context") or entry.get("source_context", ""),
            "source": {
                "registry": "global_concept_registry",
                "entry_id": entry.get("entry_id", ""),
                "source_concept_id": entry.get("entry_id", ""),
                "canonical_name": entry.get("canonical_name", ""),
                "concept_type": entry.get("concept_type", ""),
                "source_article_id": source_ref.get("source_article_id") or entry.get("source_article_id", ""),
                "source_material_slice_id": source_ref.get("source_material_slice_id") or entry.get("source_material_slice_id", ""),
                "source_lead_id": source_ref.get("source_lead_id") or entry.get("source_lead_id", ""),
                "source_content_hash": source_ref.get("source_content_hash") or entry.get("source_content_hash", ""),
            },
            "theme_refs": theme_refs.get(entry.get("entry_id"), []),
            "source_refs": source_refs,
            "provenance": {
                "retrieved_by": "local_registry_search",
                "retrieved_at": _now_iso(),
                "model_used": None,
                "external_search_used": False,
            },
        })

    for theme in themes:
        score, why = _match_score(
            {
                "title": str(theme.get("name") or ""),
                "description": str(theme.get("description") or ""),
                "keywords": " ".join(str(k) for k in (theme.get("keywords") or [])),
                "aliases": "",
            },
            query_keywords,
        )
        if not why or score <= 0:
            continue
        key = f"theme:{theme.get('theme_id')}"
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "evidence_id": _new_evidence_id(),
            "status": "candidate",
            "evidence_type": "theme",
            "title": theme.get("name", ""),
            "summary": theme.get("description", "") or "本地主题注册表条目，暂无描述。",
            "why_matched": why[:8],
            "score": round(max(min(score + 0.10, 1.0), 0.0), 3),
            "source": {
                "registry": "global_theme_registry",
                "theme_id": theme.get("theme_id", ""),
                "name": theme.get("name", ""),
                "domain": theme.get("domain", ""),
            },
            "theme_refs": [{"theme_id": theme.get("theme_id", ""), "name": theme.get("name", "")}],
            "source_refs": list(theme.get("evidence_refs") or []),
            "provenance": {
                "retrieved_by": "local_theme_search",
                "retrieved_at": _now_iso(),
                "model_used": None,
                "external_search_used": False,
            },
        })

    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    candidates = candidates[: max(1, min(int(limit or 30), 100))]
    now = _now_iso()
    summary = _summary(candidates)
    status = "draft" if candidates else "empty"
    pack = {
        "pack_id": _new_pack_id(),
        "status": status,
        "query": query,
        "generated_at": now,
        "updated_at": now,
        "retrieval_version": RETRIEVAL_VERSION,
        "candidates": candidates,
        "accepted_evidence_ids": [],
        "rejected_evidence_ids": [],
        "summary": summary,
    }
    if not candidates:
        pack["empty_reason"] = (
            "No local registry/theme evidence matched the research topic. "
            "P2 does not perform external or model-based research."
        )
    return pack


def _summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    degraded_count = sum(
        1 for item in candidates
        if any(ref.get("degraded") for ref in item.get("source_refs") or [])
    )
    source_projects = {
        ref.get("project_id")
        for item in candidates
        for ref in item.get("source_refs") or []
        if ref.get("project_id")
    }
    return {
        "candidate_count": len(candidates),
        "accepted_count": sum(1 for item in candidates if item.get("status") == "accepted"),
        "degraded_count": degraded_count,
        "source_project_count": len(source_projects),
        "concept_count": sum(1 for item in candidates if item.get("evidence_type") == "concept"),
        "theme_count": sum(1 for item in candidates if item.get("evidence_type") == "theme"),
    }
