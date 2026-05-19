"""Read-only Topic Cluster asset index.

P27 deliberately computes this view at request time. It must not create links,
research projects, evidence, insights, artifacts, or invoke external workers.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .topic_cluster_store import TopicClusterStore


_DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
_UPLOADS_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "projects"
_GENERIC_TERMS = {
    "ai",
    "artificial",
    "intelligence",
    "topic",
    "wiki",
    "system",
    "systems",
    "platform",
    "data",
    "model",
    "models",
    "project",
    "research",
    "kfc",
    "the",
    "and",
    "for",
    "with",
}
_WEAK_MATCH_TERMS = {
    "agent",
    "agents",
    "context",
    "token",
    "代码",
    "本地",
    "一文读懂",
    "engineering",
}
_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _text_parts(*values: Any) -> list[str]:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (int, float, bool)):
            parts.append(str(value))
        elif isinstance(value, list):
            parts.extend(_text_parts(*value))
        elif isinstance(value, dict):
            parts.extend(_text_parts(*value.values()))
    return parts


def _terms_from_text(*values: Any) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for part in _text_parts(*values):
        for raw in _TOKEN_PATTERN.findall(part):
            term = raw.strip().lower()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
    return terms


def _trim(text: Any, limit: int = 180) -> str:
    value = " ".join(str(text or "").split())
    return value[:limit]


def _concept_detail(value: Any) -> dict[str, str] | None:
    raw = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("{") and "concept" in text:
            try:
                raw = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                raw = value
        else:
            return {"title": text, "summary": ""}
    if isinstance(raw, dict):
        title = str(raw.get("concept") or raw.get("name") or raw.get("title") or "").strip()
        summary = str(raw.get("summary") or raw.get("description") or raw.get("body") or "").strip()
        if title:
            return {"title": title, "summary": summary}
    text = str(value or "").strip()
    return {"title": text, "summary": ""} if text else None


def _compact_concept_details(values: Any, *, limit: int = 8) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    details: list[dict[str, str]] = []
    for value in values:
        detail = _concept_detail(value)
        if not detail or detail["title"] in seen:
            continue
        seen.add(detail["title"])
        details.append(detail)
        if len(details) >= limit:
            break
    return details


class TopicClusterAssetIndexService:
    """Builds a read-only strategic asset index for a TopicCluster."""

    THEMES_PATH: Path = _UPLOADS_ROOT / "global_themes.json"
    CONCEPTS_PATH: Path = _UPLOADS_ROOT / "concept_registry.json"
    RESEARCH_PROJECT_DIR: Path = _DATA_ROOT / "research_projects"
    NOTES_DIR: Path = _DATA_ROOT / "notes"
    KFC_RELATION_DIR: Path = _DATA_ROOT / "kfc_asset_relations"

    def __init__(self, store: TopicClusterStore | None = None) -> None:
        self.store = store or TopicClusterStore()

    def build(self, cluster_id: str) -> dict[str, Any] | None:
        detail = self.store.get_cluster(cluster_id, include_counts=True, include_articles=True)
        if detail is None:
            return None

        cluster = detail["cluster"]
        links_by_type = detail.get("links_by_type") or {}
        direct_links = self._direct_links(links_by_type)
        indirect_assets = self._indirect_assets(cluster)
        query_terms = self._query_terms(cluster, direct_links, indirect_assets)
        formal_assets = self._formal_assets(direct_links, cluster["cluster_id"])
        derived_assets = self._derived_assets(formal_assets)
        candidate_assets, candidate_warnings = self._candidate_assets(query_terms, direct_links)
        ignored_assets = {"kfc_themes": [], "concepts": [], "research_projects": []}
        warnings = list(detail.get("warnings") or [])
        warnings.extend(candidate_warnings)
        if (
            len(direct_links["kfc_themes"]) == 0
            and len(direct_links["research_projects"]) == 0
        ):
            warnings.append(
                {
                    "type": "no_formal_kfc_asset_links",
                    "message": "当前 Cluster 没有正式 KFC asset link；以下 Theme/Concept/ResearchProject 仅为只读候选。",
                }
            )

        counts = {
            "direct_wiki_topic_count": len(direct_links["wiki_topics"]),
            "direct_kfc_theme_count": len(direct_links["kfc_themes"]),
            "direct_kfc_concept_count": len(formal_assets["concepts"]),
            "direct_research_project_count": len(direct_links["research_projects"]),
            "indirect_article_count": len(indirect_assets["articles"]),
            "candidate_concept_count": len(candidate_assets["concepts"]),
            "candidate_theme_count": len(candidate_assets["kfc_themes"]),
            "candidate_research_project_count": len(candidate_assets["research_projects"]),
            "candidate_evidence_count": len(candidate_assets["evidence"]),
            "candidate_insight_count": len(candidate_assets["insights"]),
            "candidate_note_count": len(candidate_assets["notes"]),
            "candidate_artifact_count": len(candidate_assets["artifacts"]),
            "derived_concept_count": len(derived_assets["concepts"]),
            "ignored_theme_count": len(ignored_assets["kfc_themes"]),
            "ignored_concept_count": len(ignored_assets["concepts"]),
            "ignored_research_project_count": len(ignored_assets["research_projects"]),
        }
        confidence_counts = self._candidate_confidence_counts(candidate_assets)
        counts.update(confidence_counts)
        return {
            "cluster_id": cluster["cluster_id"],
            "cluster_title": cluster.get("title") or cluster["cluster_id"],
            "generated_at": _now_iso(),
            "query_terms": query_terms[:30],
            "direct_links": direct_links,
            "formal_assets": formal_assets,
            "derived_assets": derived_assets,
            "indirect_assets": indirect_assets,
            "candidate_assets": candidate_assets,
            "ignored_assets": ignored_assets,
            "counts": counts,
            "warnings": warnings,
            "formal_empty_state": self._formal_empty_state(direct_links, candidate_assets),
            "provenance": {
                "direct_links_source": "backend/data/topic_cluster_links",
                "wiki_articles_source": "backend/data/wiki_hub/topics + wiki_intake auto_processed_manifest",
                "themes_source": "backend/uploads/projects/global_themes.json",
                "concepts_source": "backend/uploads/projects/concept_registry.json",
                "research_projects_source": "backend/data/research_projects",
                "notes_source": "backend/data/notes",
            },
        }

    def _direct_links(self, links_by_type: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        return {
            "wiki_topics": [self._direct_link_item(link) for link in self._active_links(links_by_type.get("wiki_topic") or [])],
            "kfc_themes": [self._direct_link_item(link) for link in self._active_links(links_by_type.get("kfc_theme") or [])],
            "research_projects": [
                self._direct_link_item(link) for link in self._active_links(links_by_type.get("research_project") or [])
            ],
        }

    def _active_links(self, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [link for link in links if not link.get("deleted") and link.get("status") != "rejected"]

    def _direct_link_item(self, link: dict[str, Any]) -> dict[str, Any]:
        return {
            "link_id": link.get("link_id", ""),
            "target_type": link.get("target_type", ""),
            "target_id": link.get("target_id", ""),
            "target_title": link.get("target_title") or link.get("target_id", ""),
            "role": link.get("role", ""),
            "status": link.get("status", ""),
            "confidence": link.get("confidence"),
            "rationale": link.get("rationale", ""),
            "association_kind": "direct_link",
            "association_type": "formal",
            "confirmation_status": "confirmed",
            "relation_state": "linked",
        }

    def _formal_assets(self, direct_links: dict[str, list[dict[str, Any]]], cluster_id: str) -> dict[str, list[dict[str, Any]]]:
        theme_lookup = self._theme_lookup()
        concept_lookup = self._concept_lookup()
        project_lookup = {str(project.get("id") or path.stem): (path, project) for path, project in self._project_jsons()[0]}
        project_theme_lookup = self._project_theme_lookup()
        themes = [
            self._formal_theme_item(link, theme_lookup.get(link.get("target_id") or "") or {}, concept_lookup, project_theme_lookup)
            for link in direct_links["kfc_themes"]
        ]
        projects = [
            self._formal_project_item(link, *(project_lookup.get(link.get("target_id") or "") or (None, {})))
            for link in direct_links["research_projects"]
        ]
        return {
            "kfc_themes": themes,
            "research_projects": projects,
            "concepts": self._formal_concepts_for_cluster(cluster_id, concept_lookup),
        }

    def _formal_concepts_for_cluster(
        self,
        cluster_id: str,
        concept_lookup: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        relation_concept_ids = {
            relation.get("source_id")
            for relation in self._relation_jsons()
            if not relation.get("deleted")
            and relation.get("source_type") == "concept_registry_entry"
            and relation.get("target_type") == "topic_cluster"
            and relation.get("target_id") == cluster_id
        }
        concepts = []
        for concept_id, concept in concept_lookup.items():
            linked_cluster_ids = set(str(item) for item in (concept.get("linked_topic_cluster_ids") or []) if item)
            if concept_id not in relation_concept_ids and cluster_id not in linked_cluster_ids:
                continue
            concepts.append(self._formal_concept_item(cluster_id, concept))
        concepts.sort(key=lambda item: item.get("updated_at") or item.get("target_title") or "", reverse=True)
        return concepts

    def _formal_concept_item(self, cluster_id: str, concept: dict[str, Any]) -> dict[str, Any]:
        concept_id = str(concept.get("entry_id") or concept.get("concept_id") or "")
        linked_projects = [
            {"project_id": project_id, "title": project_id}
            for project_id in (concept.get("linked_research_project_ids") or [])
            if project_id
        ]
        linked_articles = []
        if concept.get("source_article_id"):
            linked_articles.append(
                {
                    "article_id": concept.get("source_article_id", ""),
                    "title": concept.get("source_article_title", ""),
                    "source_markdown_path": concept.get("source_markdown_path", ""),
                    "source_content_hash": concept.get("source_content_hash", ""),
                    "source_quote": concept.get("source_quote", ""),
                    "source_context": concept.get("source_context", ""),
                }
            )
        return {
            "target_type": "concept",
            "target_id": concept_id,
            "concept_id": concept_id,
            "target_title": concept.get("canonical_name") or concept.get("label") or concept_id,
            "display_type": concept.get("concept_type") or "Concept",
            "summary": _trim(concept.get("description") or concept.get("definition") or concept.get("source_quote") or "", 360),
            "definition": _trim(concept.get("definition") or concept.get("description") or "", 360),
            "aliases": concept.get("aliases") or [],
            "concept_type": concept.get("concept_type") or "",
            "asset_type": concept.get("asset_type") or "concept",
            "lifecycle_status": concept.get("lifecycle_status") or "active",
            "quality_state": concept.get("quality_state") or "",
            "review_state": concept.get("review_state") or "",
            "confidence": concept.get("confidence"),
            "association_type": "formal",
            "confirmation_status": concept.get("review_state") or "unreviewed",
            "relation_state": "linked",
            "source_kind": "concept_registry",
            "source_path": str(self.CONCEPTS_PATH),
            "source_path_display": self._display_path(str(self.CONCEPTS_PATH)),
            "match_reason": "Concept carries a formal KFC TopicCluster link.",
            "linked_themes": [],
            "linked_projects": linked_projects,
            "linked_articles": linked_articles,
            "linked_topic_clusters": [{"cluster_id": cluster_id, "title": cluster_id}],
            "source_article_id": concept.get("source_article_id", ""),
            "source_markdown_path": concept.get("source_markdown_path", ""),
            "source_content_hash": concept.get("source_content_hash", ""),
            "source_quote": concept.get("source_quote", ""),
            "source_context": concept.get("source_context", ""),
            "source_material_slice_id": concept.get("source_material_slice_id", ""),
            "source_lead_id": concept.get("source_lead_id", ""),
            "provenance": {
                "source_file": self._display_path(str(self.CONCEPTS_PATH)),
                "source_record_id": concept_id,
                "source_article_id": concept.get("source_article_id", ""),
                "source_markdown_path": concept.get("source_markdown_path", ""),
                "source_content_hash": concept.get("source_content_hash", ""),
                "source_quote": concept.get("source_quote", ""),
                "source_context": concept.get("source_context", ""),
                "source_material_slice_id": concept.get("source_material_slice_id", ""),
                "source_lead_id": concept.get("source_lead_id", ""),
                "created_from": concept.get("created_from", ""),
                "created_by": concept.get("created_by", ""),
                "mutation": False,
            },
            "diagnostics": {
                "missing_definition": not bool(concept.get("description") or concept.get("definition")),
                "missing_article_provenance": not bool(concept.get("source_article_id") or concept.get("source_quote")),
                "promotion_supported": False,
            },
            "risk_note": "已正式关联 Concept；治理操作应通过 KFC concept API 撤销关系或废弃资产。",
            "supported_actions": ["view_detail", "open_concept_registry", "unlink_concept", "deprecate_concept"],
            "promotion_supported": False,
            "updated_at": concept.get("updated_at") or "",
        }

    def _formal_theme_item(
        self,
        link: dict[str, Any],
        theme: dict[str, Any],
        concept_lookup: dict[str, dict[str, Any]],
        project_lookup: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        theme_id = str(link.get("target_id") or theme.get("theme_id") or theme.get("id") or "")
        source_path = str(self.THEMES_PATH) if theme else "backend/data/topic_cluster_links"
        return {
            **link,
            "target_type": "kfc_theme",
            "target_id": theme_id,
            "target_title": theme.get("name") or link.get("target_title") or theme_id,
            "display_type": "Theme",
            "summary": _trim(theme.get("description") or link.get("rationale") or "", 360),
            "definition": _trim(theme.get("description") or "", 360),
            "aliases": [theme.get("slug")] if theme.get("slug") and theme.get("slug") != theme.get("name") else [],
            "canonical": bool(theme),
            "canonical_status": str(theme.get("status") or link.get("status") or "linked"),
            "association_type": "formal",
            "confirmation_status": "confirmed",
            "relation_state": "linked",
            "link_record": self._link_record(link, source_path),
            "match_reason": link.get("rationale") or "已存在 TopicClusterLink 正式关系。",
            "source_kind": "topic_cluster_link",
            "source_path": source_path,
            "source_path_display": self._display_path(source_path),
            "member_concepts": self._theme_member_concepts(theme, concept_lookup) if theme else [],
            "linked_articles": [],
            "linked_projects": project_lookup.get(theme_id, []),
            "linked_themes": [],
            "provenance": {"source_file": self._display_path(source_path), "mutation": False},
            "diagnostics": {
                "missing_definition": not bool(theme.get("description")),
                "missing_article_provenance": True,
                "promotion_supported": False,
            },
            "risk_note": "已正式关联 Theme；取消时只移除 TopicClusterLink，不删除 Theme 或其概念。",
            "supported_actions": ["view_detail", "open_theme_hub", "view_link_record", "unlink_theme"],
            "promotion_supported": False,
        }

    def _formal_project_item(self, link: dict[str, Any], path: Path | None, project: dict[str, Any]) -> dict[str, Any]:
        project_id = str(link.get("target_id") or project.get("id") or "")
        source_path = str(path) if path else "backend/data/topic_cluster_links"
        return {
            **link,
            "target_type": "research_project",
            "target_id": project_id,
            "target_title": project.get("title") or link.get("target_title") or project_id,
            "display_type": "ResearchProject",
            "summary": _trim(self._project_summary(project) or link.get("rationale") or "", 360),
            "definition": _trim(self._project_summary(project), 360),
            "association_type": "formal",
            "confirmation_status": "confirmed",
            "relation_state": "linked",
            "link_record": self._link_record(link, source_path),
            "match_reason": link.get("rationale") or "已存在 TopicClusterLink 正式项目关系。",
            "source_kind": "topic_cluster_link",
            "source_path": source_path,
            "source_path_display": self._display_path(source_path),
            "project_status": project.get("status") or "",
            "project_asset_summary": {
                "topic_cluster_count": len(project.get("linked_topic_clusters") or []),
                "evidence_count": len(project.get("evidence_items") or []),
                "concept_count": len(project.get("linked_concepts") or []),
                "theme_count": len(project.get("linked_themes") or []),
                "review_snapshot_count": len(project.get("review_snapshots") or []),
            },
            "linked_themes": self._project_linked_assets(project.get("linked_themes") or [], "theme"),
            "linked_concepts": self._project_linked_assets(project.get("linked_concepts") or [], "concept"),
            "linked_articles": [],
            "provenance": {"source_file": self._display_path(source_path), "mutation": False},
            "diagnostics": {
                "missing_definition": not bool(self._project_summary(project)),
                "missing_article_provenance": True,
                "promotion_supported": False,
            },
            "risk_note": "已正式关联 ResearchProject；取消时只移除 Cluster 与 Project 的关系，不删除 Project。",
            "drilldown_route": f"/workspace/research?project={project_id}",
            "supported_actions": ["view_detail", "open_project", "view_project_evidence", "unlink_project"],
            "promotion_supported": False,
        }

    def _link_record(self, link: dict[str, Any], source_path: str) -> dict[str, Any]:
        return {
            "link_id": link.get("link_id", ""),
            "link_status": link.get("status", ""),
            "role": link.get("role", ""),
            "created_at": link.get("created_at") or link.get("updated_at") or "",
            "source_path": self._display_path(source_path),
            "rationale": link.get("rationale", ""),
        }

    def _derived_assets(self, formal_assets: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        concept_lookup = self._concept_lookup()
        concepts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for theme in formal_assets.get("kfc_themes", []):
            for member in theme.get("member_concepts") or []:
                concept_id = str(member.get("entry_id") or member.get("id") or "")
                if not concept_id or concept_id in seen:
                    continue
                seen.add(concept_id)
                concept = concept_lookup.get(concept_id) or {}
                concepts.append(
                    {
                        "target_type": "concept",
                        "target_id": concept_id,
                        "target_title": concept.get("canonical_name") or member.get("title") or concept_id,
                        "display_type": concept.get("concept_type") or "Concept",
                        "summary": _trim(concept.get("description") or "", 360),
                        "definition": _trim(concept.get("description") or "", 360),
                        "aliases": concept.get("aliases") or [],
                        "concept_type": concept.get("concept_type") or "",
                        "association_type": "derived",
                        "confirmation_status": "confirmed",
                        "relation_state": "derived_from_linked_theme",
                        "source_kind": "linked_theme",
                        "source_path": theme.get("source_path") or "",
                        "source_path_display": theme.get("source_path_display") or "",
                        "match_reason": f"来自已关联 Theme：{theme.get('target_title') or theme.get('target_id')}",
                        "linked_themes": [{"theme_id": theme.get("target_id"), "title": theme.get("target_title")}],
                        "linked_articles": [],
                        "linked_projects": concept.get("source_links") or [],
                        "provenance": {
                            "source_file": theme.get("source_path_display") or "",
                            "derived_from_link_id": theme.get("link_id") or theme.get("link_record", {}).get("link_id") or "",
                            "mutation": False,
                        },
                        "diagnostics": {
                            "missing_definition": not bool(concept.get("description")),
                            "missing_article_provenance": True,
                            "concept_cluster_link_unsupported": True,
                            "promotion_supported": False,
                        },
                        "risk_note": "派生 Concept 只来自已关联 Theme，不代表存在 Cluster-Concept 正式关系。",
                        "supported_actions": ["view_detail", "open_concept_registry", "add_to_current_project_concept_basket"],
                        "promotion_supported": False,
                    }
                )
        return {"concepts": concepts}

    def _indirect_assets(self, cluster: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        groups = cluster.get("linked_topic_articles") or []
        wiki_topics = [
            {
                "topic_id": group.get("topic_id", ""),
                "title": group.get("title") or group.get("topic_id", ""),
                "article_count": int(group.get("article_count") or 0),
                "association_kind": "indirect_aggregation",
            }
            for group in groups
        ]
        articles: list[dict[str, Any]] = []
        for group in groups:
            for article in group.get("articles") or []:
                top_concept_details = _compact_concept_details(article.get("top_concept_details") or article.get("top_concepts") or [])
                articles.append(
                    {
                        "target_type": "article",
                        "target_id": article.get("candidate_id") or article.get("source_id") or article.get("title", ""),
                        "target_title": article.get("title") or article.get("candidate_id") or "",
                        "topic_id": group.get("topic_id", ""),
                        "topic_title": group.get("title") or group.get("topic_id", ""),
                        "source_url": article.get("source_url", ""),
                        "markdown_path": article.get("markdown_path", ""),
                        "raw_article_path": article.get("raw_article_path", ""),
                        "verified_digest_json_path": article.get("verified_digest_json_path", ""),
                        "verified_digest_md_path": article.get("verified_digest_md_path", ""),
                        "sources_path": article.get("sources_path", ""),
                        "processed_at": article.get("processed_at", ""),
                        "digest_summary": article.get("digest_summary", ""),
                        "top_concepts": [item["title"] for item in top_concept_details],
                        "top_concept_details": top_concept_details,
                        "belongs_to_cluster_reason": article.get("belongs_to_cluster_reason") or [
                            f"formal wiki_topic link: {group.get('topic_id', '')}",
                            "article topic_id matched linked wiki topic",
                        ],
                        "routes": article.get("routes") or self._article_routes(article, group.get("topic_id", "")),
                        "association_kind": "indirect_aggregation",
                    }
                )
        representative = []
        for article in cluster.get("representative_articles") or []:
            top_concept_details = _compact_concept_details(article.get("top_concept_details") or article.get("top_concepts") or [])
            representative.append(
                {
                    "target_type": "article",
                    "target_id": article.get("candidate_id") or article.get("source_id") or article.get("title", ""),
                    "target_title": article.get("title") or article.get("candidate_id") or "",
                    "topic_id": article.get("topic_id", ""),
                    "topic_title": article.get("topic_title", ""),
                    "digest_summary": article.get("digest_summary", ""),
                    "top_concepts": [item["title"] for item in top_concept_details],
                    "top_concept_details": top_concept_details,
                    "association_kind": "indirect_aggregation",
                }
            )
        return {"articles": articles, "wiki_topics": wiki_topics, "representative_articles": representative}

    def _query_terms(
        self,
        cluster: dict[str, Any],
        direct_links: dict[str, list[dict[str, Any]]],
        indirect_assets: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        seed_values: list[Any] = [
            cluster.get("title"),
            cluster.get("description"),
            cluster.get("cluster_id"),
        ]
        for group in direct_links.values():
            seed_values.extend(item.get("target_title") for item in group)
            seed_values.extend(item.get("target_id") for item in group)
        for topic in indirect_assets["wiki_topics"]:
            seed_values.extend([topic.get("title"), topic.get("topic_id")])
        for article in indirect_assets["articles"][:20]:
            seed_values.extend(
                [
                    article.get("target_title"),
                    article.get("digest_summary"),
                    article.get("top_concepts"),
                ]
            )
        terms = _terms_from_text(*seed_values)
        specific = [term for term in terms if term not in _GENERIC_TERMS]
        generic = [term for term in terms if term in _GENERIC_TERMS]
        return (specific + generic)[:50]

    def _candidate_assets(
        self,
        query_terms: list[str],
        direct_links: dict[str, list[dict[str, Any]]],
    ) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
        warnings: list[dict[str, str]] = []
        direct_theme_ids = {item["target_id"] for item in direct_links["kfc_themes"]}
        direct_project_ids = {item["target_id"] for item in direct_links["research_projects"]}
        themes, theme_warnings = self._theme_candidates(query_terms, direct_theme_ids)
        concepts, concept_warnings = self._concept_candidates(query_terms)
        projects, project_assets, project_warnings = self._research_project_candidates(query_terms, direct_project_ids)
        notes, note_warnings = self._note_candidates(query_terms)
        warnings.extend(theme_warnings + concept_warnings + project_warnings + note_warnings)
        return (
            {
                "kfc_themes": themes,
                "concepts": concepts,
                "research_projects": projects,
                "evidence": project_assets["evidence"],
                "insights": project_assets["insights"],
                "notes": notes,
                "artifacts": project_assets["artifacts"],
            },
            warnings,
        )

    def _theme_candidates(self, query_terms: list[str], exclude_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        payload, warnings = self._optional_json(self.THEMES_PATH, "themes")
        themes = _as_list((payload or {}).get("themes") if isinstance(payload, dict) else payload)
        concept_lookup = self._concept_lookup()
        project_lookup = self._project_theme_lookup()
        candidates = []
        for theme in themes:
            theme_id = str(theme.get("theme_id") or theme.get("id") or "")
            if not theme_id or theme_id in exclude_ids:
                continue
            text = _text_parts(theme.get("name"), theme.get("slug"), theme.get("description"), theme.get("keywords"), theme.get("domain"))
            match = self._match(
                query_terms,
                text,
                {
                    "title": _text_parts(theme.get("name"), theme.get("slug")),
                    "description": _text_parts(theme.get("description")),
                    "keywords": _text_parts(theme.get("keywords"), theme.get("domain")),
                },
            )
            if match:
                candidates.append(
                    self._candidate_item(
                        target_type="kfc_theme",
                        target_id=theme_id,
                        target_title=theme.get("name") or theme_id,
                        match=match,
                        source_kind="global_themes",
                        source_path=str(self.THEMES_PATH),
                        risk_note="只读候选 Theme；不是正式 TopicClusterLink。",
                        summary=theme.get("description") or "",
                        aliases=[theme.get("slug")] if theme.get("slug") and theme.get("slug") != theme.get("name") else [],
                        display_type="Theme",
                        canonical_status=str(theme.get("status") or "theme"),
                        canonical=theme.get("status") == "active",
                        linked_themes=[],
                        linked_projects=project_lookup.get(theme_id, []),
                        linked_articles=[],
                        member_concepts=self._theme_member_concepts(theme, concept_lookup),
                        diagnostics_extra={
                            "missing_definition": not bool(theme.get("description")),
                            "missing_article_provenance": True,
                        },
                        supported_actions=[
                            "view_detail",
                            "open_theme_hub",
                            "view_theme_concepts",
                            "suggest_formal_theme_link",
                        ],
                    )
                )
        return self._top(candidates), warnings

    def _concept_candidates(self, query_terms: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        payload, warnings = self._optional_json(self.CONCEPTS_PATH, "concepts")
        concepts = _as_list((payload or {}).get("entries") if isinstance(payload, dict) else payload)
        theme_lookup = self._concept_theme_lookup()
        candidates = []
        for concept in concepts:
            concept_id = str(concept.get("entry_id") or concept.get("id") or "")
            if not concept_id:
                continue
            source_links = concept.get("source_links") or []
            text = _text_parts(
                concept.get("canonical_name"),
                concept.get("concept_type"),
                concept.get("aliases"),
                concept.get("description"),
                source_links[:5],
            )
            match = self._match(
                query_terms,
                text,
                {
                    "title": _text_parts(concept.get("canonical_name")),
                    "aliases": _text_parts(concept.get("aliases")),
                    "description": _text_parts(concept.get("description"), concept.get("concept_type")),
                    "source_links": _text_parts(source_links[:5]),
                },
            )
            if match:
                candidates.append(
                    self._candidate_item(
                        target_type="concept",
                        target_id=concept_id,
                        target_title=concept.get("canonical_name") or concept_id,
                        match=match,
                        source_kind="concept_registry",
                        source_path=str(self.CONCEPTS_PATH),
                        risk_note="只读候选 Concept；P27 不扩展写入 link target_type。",
                        summary=concept.get("description") or "",
                        aliases=concept.get("aliases") or [],
                        display_type=concept.get("concept_type") or "Concept",
                        canonical_status="canonical",
                        canonical=True,
                        linked_themes=theme_lookup.get(concept_id, []),
                        linked_projects=self._concept_source_projects(concept),
                        linked_articles=[],
                        concept_type=concept.get("concept_type") or "",
                        updated_at=concept.get("updated_at") or "",
                        diagnostics_extra={
                            "missing_definition": not bool(concept.get("description")),
                            "missing_article_provenance": True,
                            "concept_cluster_link_unsupported": True,
                        },
                        supported_actions=[
                            "view_detail",
                            "open_concept_registry",
                            "add_to_current_project_concept_basket",
                            "mark_core_concept_candidate",
                        ],
                    )
                )
        return self._top(candidates), warnings

    def _research_project_candidates(
        self,
        query_terms: list[str],
        exclude_ids: set[str],
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
        projects, warnings = self._project_jsons()
        project_candidates: list[dict[str, Any]] = []
        evidence_candidates: list[dict[str, Any]] = []
        insight_candidates: list[dict[str, Any]] = []
        artifact_candidates: list[dict[str, Any]] = []
        for path, project in projects:
            project_text = _text_parts(
                project.get("title"),
                project.get("background"),
                project.get("goal"),
                project.get("audience"),
                project.get("research_brief"),
                project.get("linked_themes"),
                project.get("linked_concepts"),
            )
            project_id = str(project.get("id") or path.stem)
            project_title = str(project.get("title") or project_id)
            project_match = self._match(
                query_terms,
                project_text,
                {
                    "title": _text_parts(project.get("title")),
                    "background": _text_parts(project.get("background")),
                    "goal": _text_parts(project.get("goal")),
                    "research_brief": _text_parts(project.get("research_brief")),
                    "linked_assets": _text_parts(project.get("linked_themes"), project.get("linked_concepts")),
                },
            )
            if project_match and project_id not in exclude_ids:
                project_candidates.append(
                    self._candidate_item(
                        target_type="research_project",
                        target_id=project_id,
                        target_title=project_title,
                        match=project_match,
                        source_kind="research_project",
                        source_path=str(path),
                        risk_note="只读候选 ResearchProject；P27 不写入项目引用。",
                        drilldown_route=f"/workspace/research?project={project_id}",
                        summary=self._project_summary(project),
                        aliases=[],
                        display_type="ResearchProject",
                        canonical_status=str(project.get("status") or "project"),
                        canonical=False,
                        linked_themes=self._project_linked_assets(project.get("linked_themes") or [], "theme"),
                        linked_projects=[],
                        linked_articles=[],
                        linked_topic_clusters=self._project_linked_assets(
                            project.get("linked_topic_clusters") or [],
                            "topic_cluster",
                        ),
                        linked_concepts=self._project_linked_assets(project.get("linked_concepts") or [], "concept"),
                        project_status=project.get("status") or "",
                        project_asset_summary={
                            "topic_cluster_count": len(project.get("linked_topic_clusters") or []),
                            "evidence_count": len(project.get("evidence_items") or []),
                            "concept_count": len(project.get("linked_concepts") or []),
                            "theme_count": len(project.get("linked_themes") or []),
                            "review_snapshot_count": len(project.get("review_snapshots") or []),
                        },
                        diagnostics_extra={
                            "missing_definition": not bool(self._project_summary(project)),
                            "missing_article_provenance": True,
                        },
                        supported_actions=[
                            "view_detail",
                            "open_project",
                            "link_current_cluster_to_project",
                            "view_project_evidence",
                        ],
                    )
                )
            for evidence in project.get("evidence_items") or []:
                match = self._match(query_terms, _text_parts(evidence), {"evidence": _text_parts(evidence)})
                evidence_id = str(evidence.get("evidence_id") or evidence.get("id") or "")
                if match and evidence_id:
                    evidence_candidates.append(
                        self._candidate_item(
                            target_type="evidence",
                            target_id=f"{project_id}:{evidence_id}",
                            target_title=evidence.get("title") or evidence.get("claim") or evidence_id,
                            match=match,
                            source_kind="research_project.evidence_items",
                            source_path=str(path),
                            risk_note="Evidence 是 project-scoped 线索；P27 不建立正式证据 link。",
                            parent_research_project_id=project_id,
                            parent_research_project_title=project_title,
                            drilldown_route=f"/workspace/research?project={project_id}",
                        )
                    )
            for insight in project.get("insight_cards") or []:
                match = self._match(query_terms, _text_parts(insight), {"insight": _text_parts(insight)})
                insight_id = str(insight.get("id") or insight.get("insight_id") or "")
                if match and insight_id:
                    insight_candidates.append(
                        self._candidate_item(
                            target_type="insight",
                            target_id=f"{project_id}:{insight_id}",
                            target_title=insight.get("title") or insight.get("claim") or insight_id,
                            match=match,
                            source_kind="research_project.insight_cards",
                            source_path=str(path),
                            risk_note="Insight 是 project-scoped 线索；P27 不采纳为正式研究结论。",
                            parent_research_project_id=project_id,
                            parent_research_project_title=project_title,
                            drilldown_route=f"/workspace/research?project={project_id}",
                        )
                    )
            for artifact in list(project.get("artifact_drafts") or []) + list(project.get("artifact_packs") or []):
                match = self._match(query_terms, _text_parts(artifact), {"artifact": _text_parts(artifact)})
                artifact_id = str(artifact.get("id") or artifact.get("pack_id") or "")
                if match and artifact_id:
                    artifact_candidates.append(
                        self._candidate_item(
                            target_type="artifact",
                            target_id=f"{project_id}:{artifact_id}",
                            target_title=artifact.get("title") or artifact_id,
                            match=match,
                            source_kind="research_project.artifacts",
                            source_path=str(path),
                            risk_note="Artifact 是 project-scoped 草稿/材料；P27 仅提示候选。",
                            parent_research_project_id=project_id,
                            parent_research_project_title=project_title,
                            drilldown_route=f"/workspace/research?project={project_id}",
                        )
                    )
        return (
            self._top(project_candidates),
            {
                "evidence": self._top(evidence_candidates),
                "insights": self._top(insight_candidates),
                "artifacts": self._top(artifact_candidates),
            },
            warnings,
        )

    def _note_candidates(self, query_terms: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        warnings: list[dict[str, str]] = []
        if not self.NOTES_DIR.exists():
            return [], [{"type": "notes_source_missing", "message": f"notes source not found: {self.NOTES_DIR}"}]
        candidates = []
        for path in sorted(self.NOTES_DIR.glob("*.md"))[:200]:
            try:
                text = path.read_text(encoding="utf-8")[:5000]
            except OSError as exc:
                warnings.append({"type": "note_unreadable", "message": f"{path.name}: {exc}"})
                continue
            match = self._match(query_terms, [text], {"note": [text]})
            if not match:
                continue
            title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()), path.stem)
            candidates.append(
                self._candidate_item(
                    target_type="note",
                    target_id=path.stem,
                    target_title=title or path.stem,
                    match=match,
                    source_kind="notes",
                    source_path=str(path),
                    risk_note="Note 是只读线索；P27 不写入正式研究资产。",
                )
            )
        return self._top(candidates), warnings

    def _optional_json(self, path: Path, source_name: str) -> tuple[Any | None, list[dict[str, str]]]:
        if not path.exists():
            return None, [{"type": f"{source_name}_source_missing", "message": f"{source_name} source not found: {path}"}]
        try:
            return _read_json(path), []
        except (OSError, json.JSONDecodeError) as exc:
            return None, [{"type": f"{source_name}_source_unreadable", "message": f"{path}: {exc}"}]

    def _project_jsons(self) -> tuple[list[tuple[Path, dict[str, Any]]], list[dict[str, str]]]:
        if not self.RESEARCH_PROJECT_DIR.exists():
            return [], [
                {
                    "type": "research_projects_source_missing",
                    "message": f"research projects source not found: {self.RESEARCH_PROJECT_DIR}",
                }
            ]
        projects = []
        warnings: list[dict[str, str]] = []
        for path in sorted(self.RESEARCH_PROJECT_DIR.glob("rp_*.json")):
            try:
                payload = _read_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                warnings.append({"type": "research_project_unreadable", "message": f"{path.name}: {exc}"})
                continue
            if isinstance(payload, dict):
                projects.append((path, payload))
        return projects, warnings

    def _relation_jsons(self) -> list[dict[str, Any]]:
        if not self.KFC_RELATION_DIR.exists():
            return []
        relations: list[dict[str, Any]] = []
        for path in sorted(self.KFC_RELATION_DIR.glob("rel_*.json")):
            try:
                payload = _read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                relations.append(payload)
        return relations

    def _match(
        self,
        query_terms: list[str],
        text_parts: list[str],
        field_texts: dict[str, list[str]] | None = None,
    ) -> dict[str, Any] | None:
        field_texts = field_texts or {"content": text_parts}
        field_haystacks = {field: " ".join(parts).lower() for field, parts in field_texts.items()}
        haystack = " ".join(field_haystacks.values())
        matched: list[str] = []
        matched_fields: list[str] = []
        score_breakdown: dict[str, int] = {}
        for term in query_terms:
            term_fields = [field for field, field_haystack in field_haystacks.items() if term in field_haystack]
            if term_fields and term not in matched:
                matched.append(term)
                for field in term_fields:
                    if field not in matched_fields:
                        matched_fields.append(field)
                    score_breakdown[field] = score_breakdown.get(field, 0) + 1
            if len(matched) >= 8:
                break
        if not matched:
            return None
        strong_terms = [term for term in matched if term not in _GENERIC_TERMS and term not in _WEAK_MATCH_TERMS]
        weak_terms = [term for term in matched if term in _GENERIC_TERMS or term in _WEAK_MATCH_TERMS]
        if len(strong_terms) >= 3 or (len(strong_terms) >= 1 and len(matched) >= 3 and len(matched_fields) >= 2):
            confidence = "high"
        elif len(strong_terms) >= 1 and len(matched) >= 2:
            confidence = "medium"
        else:
            confidence = "low"
        score = len(strong_terms) * 10 + len(matched) + len(matched_fields)
        return {
            "matched_terms": matched,
            "specific_count": len(strong_terms),
            "matched_fields": matched_fields,
            "strong_terms": strong_terms,
            "weak_terms": weak_terms,
            "score_breakdown": score_breakdown,
            "score": score,
            "confidence_hint": confidence,
        }

    def _candidate_item(
        self,
        *,
        target_type: str,
        target_id: str,
        target_title: str,
        match: dict[str, Any],
        source_kind: str,
        source_path: str,
        risk_note: str,
        parent_research_project_id: str | None = None,
        parent_research_project_title: str | None = None,
        drilldown_route: str = "",
        summary: str = "",
        aliases: list[Any] | None = None,
        display_type: str = "",
        canonical_status: str = "",
        canonical: bool = False,
        linked_articles: list[dict[str, Any]] | None = None,
        linked_themes: list[dict[str, Any]] | None = None,
        linked_projects: list[dict[str, Any]] | None = None,
        member_concepts: list[dict[str, Any]] | None = None,
        linked_topic_clusters: list[dict[str, Any]] | None = None,
        linked_concepts: list[dict[str, Any]] | None = None,
        concept_type: str = "",
        project_status: str = "",
        project_asset_summary: dict[str, Any] | None = None,
        updated_at: str = "",
        diagnostics_extra: dict[str, Any] | None = None,
        supported_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        promotion_supported = target_type in {"kfc_theme", "research_project"}
        action_defaults = ["view_detail"]
        if promotion_supported:
            action_defaults.append("create_topic_cluster_link")
        item = {
            "target_type": target_type,
            "target_id": target_id,
            "target_title": _trim(target_title, 160),
            "display_type": display_type or target_type,
            "summary": _trim(summary, 360),
            "definition": _trim(summary, 360),
            "aliases": [str(alias) for alias in (aliases or []) if alias],
            "canonical_status": canonical_status or ("canonical" if canonical else "candidate"),
            "canonical": canonical,
            "concept_type": concept_type,
            "project_status": project_status,
            "project_asset_summary": project_asset_summary or {},
            "linked_articles": linked_articles or [],
            "linked_themes": linked_themes or [],
            "linked_projects": linked_projects or [],
            "member_concepts": member_concepts or [],
            "linked_topic_clusters": linked_topic_clusters or [],
            "linked_concepts": linked_concepts or [],
            "updated_at": updated_at,
            "association_type": "candidate",
            "confirmation_status": "unconfirmed",
            "relation_state": "candidate",
            "match_reason": f"本地字段命中：{', '.join(match['matched_terms'])}",
            "matched_terms": match["matched_terms"],
            "matched_fields": match.get("matched_fields", []),
            "confidence_hint": match["confidence_hint"],
            "source_kind": source_kind,
            "source_path": source_path,
            "source_path_display": self._display_path(source_path),
            "risk_note": risk_note,
            "why_candidate": {
                "matched_fields": match.get("matched_fields", []),
                "strong_terms": match.get("strong_terms", []),
                "weak_terms": match.get("weak_terms", []),
                "score_breakdown": match.get("score_breakdown", {}),
            },
            "provenance": {
                "source_file": self._display_path(source_path),
                "source_record_id": target_id,
                "generated_by": "local_asset_index",
                "mutation": False,
            },
            "diagnostics": {
                "missing_definition": not bool(summary),
                "missing_article_provenance": not bool(linked_articles),
                "promotion_supported": promotion_supported,
                "risk_note": risk_note,
                **(diagnostics_extra or {}),
            },
            "drilldown_route": drilldown_route,
            "promotion_supported": promotion_supported,
            "promotion_action": "create_topic_cluster_link" if promotion_supported else "",
            "supported_actions": supported_actions or action_defaults,
            "_score": match["score"],
        }
        if parent_research_project_id:
            item["parent_research_project_id"] = parent_research_project_id
            item["parent_research_project_title"] = parent_research_project_title or parent_research_project_id
        return item

    def _candidate_confidence_counts(self, candidate_assets: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        counts = {"candidate_high_count": 0, "candidate_medium_count": 0, "candidate_low_count": 0}
        for group in ("kfc_themes", "concepts", "research_projects"):
            for item in candidate_assets.get(group, []):
                key = f"candidate_{item.get('confidence_hint')}_count"
                if key in counts:
                    counts[key] += 1
        return counts

    def _concept_lookup(self) -> dict[str, dict[str, Any]]:
        payload, _warnings = self._optional_json(self.CONCEPTS_PATH, "concepts")
        concepts = _as_list((payload or {}).get("entries") if isinstance(payload, dict) else payload)
        return {str(item.get("entry_id") or item.get("id") or ""): item for item in concepts if item}

    def _theme_lookup(self) -> dict[str, dict[str, Any]]:
        payload, _warnings = self._optional_json(self.THEMES_PATH, "themes")
        themes = _as_list((payload or {}).get("themes") if isinstance(payload, dict) else payload)
        return {str(item.get("theme_id") or item.get("id") or ""): item for item in themes if item}

    def _concept_theme_lookup(self) -> dict[str, list[dict[str, Any]]]:
        payload, _warnings = self._optional_json(self.THEMES_PATH, "themes")
        themes = _as_list((payload or {}).get("themes") if isinstance(payload, dict) else payload)
        lookup: dict[str, list[dict[str, Any]]] = {}
        for theme in themes:
            theme_id = str(theme.get("theme_id") or theme.get("id") or "")
            title = str(theme.get("name") or theme_id)
            for membership in theme.get("concept_memberships") or []:
                entry_id = str(membership.get("entry_id") or "")
                if not entry_id:
                    continue
                lookup.setdefault(entry_id, []).append(
                    {
                        "theme_id": theme_id,
                        "title": title,
                        "role": membership.get("role") or "",
                        "score": membership.get("score"),
                    }
                )
        return lookup

    def _project_theme_lookup(self) -> dict[str, list[dict[str, Any]]]:
        projects, _warnings = self._project_jsons()
        lookup: dict[str, list[dict[str, Any]]] = {}
        for _path, project in projects:
            project_id = str(project.get("id") or "")
            title = str(project.get("title") or project_id)
            for theme in project.get("linked_themes") or []:
                theme_id = str(theme.get("theme_id") or theme.get("id") or theme.get("target_id") or "")
                if theme_id:
                    lookup.setdefault(theme_id, []).append({"project_id": project_id, "title": title})
        return lookup

    def _theme_member_concepts(
        self,
        theme: dict[str, Any],
        concept_lookup: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        members = []
        for membership in (theme.get("concept_memberships") or [])[:12]:
            entry_id = str(membership.get("entry_id") or "")
            concept = concept_lookup.get(entry_id) or {}
            members.append(
                {
                    "entry_id": entry_id,
                    "title": concept.get("canonical_name") or entry_id,
                    "role": membership.get("role") or "",
                    "score": membership.get("score"),
                }
            )
        return members

    def _concept_source_projects(self, concept: dict[str, Any]) -> list[dict[str, Any]]:
        projects = []
        for link in concept.get("source_links") or []:
            project_id = str(link.get("project_id") or "")
            if not project_id:
                continue
            projects.append(
                {
                    "project_id": project_id,
                    "title": link.get("project_name") or project_id,
                    "concept_key": link.get("concept_key") or "",
                }
            )
        return projects[:12]

    def _project_summary(self, project: dict[str, Any]) -> str:
        for key in ("description", "summary", "background", "goal"):
            value = project.get(key)
            if isinstance(value, str) and value.strip():
                return value
        brief = project.get("research_brief")
        if isinstance(brief, dict):
            questions = brief.get("key_questions") or []
            if questions:
                return "；".join(str(item) for item in questions[:3])
        return ""

    def _project_linked_assets(self, assets: list[Any], default_type: str) -> list[dict[str, Any]]:
        result = []
        for asset in assets[:12]:
            if isinstance(asset, dict):
                asset_id = asset.get(f"{default_type}_id") or asset.get("id") or asset.get("target_id") or asset.get("cluster_id") or ""
                result.append(
                    {
                        "id": asset_id,
                        "title": asset.get("title") or asset.get("name") or asset_id,
                        "type": default_type,
                    }
                )
            else:
                result.append({"id": str(asset), "title": str(asset), "type": default_type})
        return result

    def _top(self, candidates: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
        candidates.sort(key=lambda item: (-int(item.get("_score") or 0), str(item.get("target_title") or "").lower()))
        result = []
        for item in candidates[:limit]:
            clean = dict(item)
            clean.pop("_score", None)
            result.append(clean)
        return result

    def _formal_empty_state(
        self,
        direct_links: dict[str, list[dict[str, Any]]],
        candidate_assets: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        return {
            "kfc_theme": {
                "message": "尚未建立正式 KFC Theme 链接；候选 Theme 需要人工确认后才会进入正式区。",
                "candidate_count": len(candidate_assets["kfc_themes"]),
                "has_formal_links": len(direct_links["kfc_themes"]) > 0,
                "suggested_action": "审阅候选 Theme，并只在人工确认后建立 TopicClusterLink。",
            },
            "research_project": {
                "message": "尚未建立正式 ResearchProject 链接；候选项目不会自动创建或自动关联。",
                "candidate_count": len(candidate_assets["research_projects"]),
                "has_formal_links": len(direct_links["research_projects"]) > 0,
                "suggested_action": "审阅候选 ResearchProject，并只在人工确认后建立 TopicClusterLink。",
            },
        }

    def _article_routes(self, article: dict[str, Any], topic_id: str) -> dict[str, str]:
        candidate_id = str(article.get("candidate_id") or article.get("source_id") or "")
        routes = {
            "wiki_topic": f"/workspace/wiki-topics/{topic_id}" if topic_id else "",
            "wiki_intake": f"/workspace/wiki-intake?candidate={candidate_id}" if candidate_id else "/workspace/wiki-intake",
        }
        if article.get("source_url"):
            routes["source_url"] = str(article.get("source_url"))
        if article.get("verified_digest_md_path"):
            routes["verified_digest"] = f"file://{article.get('verified_digest_md_path')}"
        if article.get("markdown_path"):
            routes["source_file"] = f"file://{article.get('markdown_path')}"
        return routes

    def _display_path(self, source_path: str) -> str:
        if not source_path:
            return ""
        path = Path(source_path)
        parts = path.parts
        for marker in ("backend", "uploads"):
            if marker in parts:
                index = parts.index(marker)
                return str(Path(*parts[index:]))
        return path.name
