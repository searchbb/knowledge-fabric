#!/usr/bin/env python3
"""Read-only taxonomy audit for KFC Wiki Intake, Topics, Clusters, and assets.

This diagnostic intentionally does not import application stores because several
store methods create directories or write sidecars. It reads files directly and
writes only under .codex/diagnostics/topic_taxonomy_audit_<timestamp>/.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
BACKEND_DATA = REPO / "backend" / "data"
UPLOADS_PROJECTS = REPO / "backend" / "uploads" / "projects"
DEFAULT_OUT_ROOT = REPO / ".codex" / "diagnostics"


GENERIC_CLUSTER_NAMES = {
    "ai",
    "infrastructure",
    "business",
    "strategy",
    "platform",
    "markets",
    "knowledge",
    "topic",
    "technology",
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        return {"_read_error": f"{exc.__class__.__name__}: {exc}", "_path": str(path)}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append({"_read_error": f"{path}:{line_no}: {exc}"})
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def rel(path: str | Path | None) -> str:
    if not path:
        return ""
    p = Path(str(path))
    try:
        return str(p.resolve().relative_to(REPO))
    except Exception:
        return str(path)


def compact(value: Any, limit: int = 12) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, dict):
        values = list(value.keys())
    elif isinstance(value, list):
        values = value
    else:
        values = [value]
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def get_first(data: dict[str, Any], keys: list[str], default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def extract_markdown_title(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:80]
    except FileNotFoundError:
        return ""
    in_frontmatter = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter and stripped == "---":
            in_frontmatter = False
            continue
        if in_frontmatter and stripped.lower().startswith("title:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def digest_excerpt(digest: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(digest, dict):
        return {}
    routing = digest.get("routing_decision") if isinstance(digest.get("routing_decision"), dict) else {}
    return {
        "summary": get_first(digest, ["verified_summary", "source_summary", "summary", "safe_wiki_wording"], ""),
        "source_summary": digest.get("source_summary", ""),
        "verified_summary": digest.get("verified_summary", ""),
        "safe_wiki_wording": digest.get("safe_wiki_wording", ""),
        "keywords": compact(
            digest.get("keywords")
            or digest.get("tags")
            or digest.get("core_concepts")
            or digest.get("top_concepts")
            or digest.get("concepts"),
            20,
        ),
        "topics": compact([digest.get("topic"), routing.get("resolved_topic_id"), routing.get("original_recommended_topic")], 8),
        "tags": compact(digest.get("tags"), 20),
        "important_concepts": compact(
            digest.get("core_concepts") or digest.get("top_concepts") or digest.get("concepts"),
            24,
        ),
        "recommended_topic_id": routing.get("resolved_topic_id") or routing.get("original_recommended_topic") or digest.get("topic") or "",
        "recommended_topic_label": routing.get("resolved_topic_label") or routing.get("original_recommended_topic_label") or "",
        "recommended_next_action": digest.get("recommended_next_action", ""),
        "research_gaps": digest.get("research_gaps") or [],
    }


def latest_by(rows: list[dict[str, Any]], keys: list[str], stamp_keys: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_keys = [str(row.get(key) or "") for key in keys]
        stamp = max(str(row.get(key) or "") for key in stamp_keys)
        for item_key in row_keys:
            if not item_key:
                continue
            current = out.get(item_key)
            current_stamp = max(str(current.get(key) or "") for key in stamp_keys) if current else ""
            if current is None or stamp >= current_stamp:
                out[item_key] = row
    return out


def list_inventory() -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    for path in sorted(BACKEND_DATA.rglob("*")):
        if ".lock" in path.name:
            continue
        depth = len(path.relative_to(BACKEND_DATA).parts)
        if depth > 3:
            continue
        kind = "dir" if path.is_dir() else "file"
        suffix = "" if path.is_dir() else path.suffix
        rows.append(
            {
                "path": rel(path),
                "kind": kind,
                "depth": depth,
                "suffix": suffix,
                "size_bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    lines = [
        "# Backend Data Directory Inventory",
        "",
        "只列出 `backend/data` 下 1-3 层目录/文件；更深层素材与正文不展开。",
        "",
        "| path | kind | suffix | size_bytes |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(f"| `{row['path']}` | {row['kind']} | {row['suffix']} | {row['size_bytes'] or ''} |")
    return rows, "\n".join(lines) + "\n"


def load_wiki_intake() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    intake_root = BACKEND_DATA / "wiki_intake"
    manifest = read_jsonl(intake_root / "manifest.jsonl")
    decisions = read_jsonl(intake_root / "decisions.jsonl")
    processing = read_jsonl(intake_root / "processing_results.jsonl")
    auto_processed = read_jsonl(intake_root / "auto_processed_manifest.jsonl")
    routing_events = read_jsonl(intake_root / "topic_routing_events.jsonl")
    events = read_jsonl(intake_root / "events.jsonl")
    auto_events = read_jsonl(intake_root / "auto_intake_events.jsonl")

    latest_decision = latest_by(decisions, ["candidate_id", "source_id"], ["decided_at", "processed_at", "created_at"])
    latest_processing = latest_by(processing, ["candidate_id", "source_id"], ["processed_at", "created_at"])
    latest_auto = latest_by(auto_processed, ["candidate_id", "source_id"], ["processed_at", "created_at"])

    articles: list[dict[str, Any]] = []
    seen: set[str] = set()

    for record in manifest:
        candidate_id = str(record.get("candidate_id") or record.get("source_id") or "")
        if not candidate_id:
            continue
        decision = latest_decision.get(candidate_id) or latest_decision.get(str(record.get("source_id") or "")) or {}
        processing_row = latest_processing.get(candidate_id) or latest_processing.get(str(record.get("source_id") or "")) or {}
        auto_row = latest_auto.get(candidate_id) or latest_auto.get(str(record.get("source_id") or "")) or {}
        digest_path = Path(str(auto_row.get("verified_digest_json_path") or "")) if auto_row.get("verified_digest_json_path") else None
        digest = read_json(digest_path) if digest_path else None
        raw_status = (
            decision.get("status")
            or decision.get("decision")
            or processing_row.get("status")
            or (processing_row.get("wiki") or {}).get("status")
            or record.get("intake_status")
            or "unknown"
        )
        status = "completed" if auto_row else raw_status
        if str(raw_status).lower() in {"rejected", "duplicate"}:
            status = str(raw_status)
        articles.append(
            {
                "candidate_id": candidate_id,
                "source_id": record.get("source_id", ""),
                "title": record.get("title", ""),
                "source_url": record.get("source_url", ""),
                "source_file_path": record.get("source_file_path", ""),
                "source_relative_path": record.get("source_relative_path", ""),
                "status": status,
                "intake_status": record.get("intake_status", ""),
                "decision": decision,
                "guessed_topics": record.get("guessed_topics") or [],
                "processed_at": auto_row.get("processed_at") or processing_row.get("processed_at") or "",
                "raw_article_path": auto_row.get("raw_article_path") or ((processing_row.get("wiki") or {}).get("path") if isinstance(processing_row.get("wiki"), dict) else ""),
                "verified_digest_json_path": auto_row.get("verified_digest_json_path", ""),
                "verified_digest_md_path": auto_row.get("verified_digest_md_path", ""),
                "sources_path": auto_row.get("sources_path", ""),
                "topic_id": auto_row.get("topic_id") or ((processing_row.get("wiki") or {}).get("source_identity") or {}).get("selected_topic", ""),
                "digest": digest_excerpt(digest if isinstance(digest, dict) else None),
                "manifest_excerpt": record.get("excerpt", ""),
                "content_hash": record.get("content_hash", ""),
            }
        )
        seen.add(candidate_id)

    for auto_row in auto_processed:
        candidate_id = str(auto_row.get("candidate_id") or auto_row.get("source_id") or "")
        if not candidate_id or candidate_id in seen:
            continue
        digest_path = Path(str(auto_row.get("verified_digest_json_path") or "")) if auto_row.get("verified_digest_json_path") else None
        digest = read_json(digest_path) if digest_path else None
        raw_path = Path(str(auto_row.get("raw_article_path") or ""))
        articles.append(
            {
                "candidate_id": candidate_id,
                "source_id": auto_row.get("source_id", ""),
                "title": extract_markdown_title(raw_path) or Path(str(auto_row.get("source_md") or raw_path)).stem,
                "source_url": (digest or {}).get("original_source_url", "") if isinstance(digest, dict) else "",
                "source_file_path": auto_row.get("source_md", ""),
                "source_relative_path": "",
                "status": "completed",
                "intake_status": "",
                "decision": {},
                "guessed_topics": [],
                "processed_at": auto_row.get("processed_at", ""),
                "raw_article_path": auto_row.get("raw_article_path", ""),
                "verified_digest_json_path": auto_row.get("verified_digest_json_path", ""),
                "verified_digest_md_path": auto_row.get("verified_digest_md_path", ""),
                "sources_path": auto_row.get("sources_path", ""),
                "topic_id": auto_row.get("topic_id", ""),
                "digest": digest_excerpt(digest if isinstance(digest, dict) else None),
                "manifest_excerpt": "",
                "content_hash": "",
            }
        )
        seen.add(candidate_id)

    source_rows = [
        {"path": rel(intake_root / "manifest.jsonl"), "kind": "wiki_intake_manifest", "rows": len(manifest)},
        {"path": rel(intake_root / "decisions.jsonl"), "kind": "wiki_intake_decisions", "rows": len(decisions)},
        {"path": rel(intake_root / "processing_results.jsonl"), "kind": "wiki_intake_processing_results", "rows": len(processing)},
        {"path": rel(intake_root / "auto_processed_manifest.jsonl"), "kind": "wiki_intake_auto_processed", "rows": len(auto_processed)},
        {"path": rel(intake_root / "topic_routing_events.jsonl"), "kind": "wiki_intake_topic_routing", "rows": len(routing_events)},
        {"path": rel(intake_root / "events.jsonl"), "kind": "wiki_intake_events", "rows": len(events)},
        {"path": rel(intake_root / "auto_intake_events.jsonl"), "kind": "wiki_intake_auto_events", "rows": len(auto_events)},
    ]
    state = {
        "manifest": manifest,
        "decisions": decisions,
        "processing": processing,
        "auto_processed": auto_processed,
        "routing_events": routing_events,
    }
    return articles, state, source_rows


def load_topics(articles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    topics_root = BACKEND_DATA / "wiki_hub" / "topics"
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in articles:
        topic_id = str(article.get("topic_id") or "")
        if topic_id:
            by_topic[topic_id].append(article)
        if not topic_id:
            guessed = article.get("guessed_topics") or []
            if guessed and isinstance(guessed[0], dict):
                by_topic[str(guessed[0].get("topic_id") or "")].append(article)

    topics: list[dict[str, Any]] = []
    for topic_dir in sorted(p for p in topics_root.iterdir() if p.is_dir()):
        profile_path = topic_dir / "topic_profile.json"
        profile = read_json(profile_path) or {}
        topic_id = str(profile.get("topic_id") or topic_dir.name)
        topic_articles = sorted(by_topic.get(topic_id, []), key=lambda item: str(item.get("processed_at") or ""), reverse=True)
        raw_articles = sorted((topic_dir / "raw" / "articles").glob("*.md")) if (topic_dir / "raw" / "articles").exists() else []
        completed = [item for item in topic_articles if item.get("processed_at") or item.get("verified_digest_json_path")]
        pending_review = [
            item
            for item in topic_articles
            if str(item.get("status") or "").lower() in {"candidate", "pending", "review", "needs_human_review", "deferred"}
        ]
        article_rows = [
            {
                "title": item.get("title", ""),
                "candidate_id": item.get("candidate_id", ""),
                "source_url": item.get("source_url", ""),
                "processed_at": item.get("processed_at", ""),
                "tags": item.get("digest", {}).get("tags") or item.get("digest", {}).get("keywords") or [],
                "digest_summary": item.get("digest", {}).get("summary", ""),
            }
            for item in topic_articles
        ]
        topics.append(
            {
                "topic_id": topic_id,
                "name": profile.get("display_name") or topic_id,
                "title": profile.get("display_name") or topic_id,
                "description": profile.get("description") or profile.get("summary") or "",
                "summary": profile.get("summary", ""),
                "aliases": profile.get("aliases") or [],
                "keywords": profile.get("topic_keywords") or profile.get("keywords") or [],
                "tags": profile.get("tags") or [],
                "concept_seeds": profile.get("concept_seeds") or [],
                "article_count": max(len(topic_articles), len(raw_articles)),
                "completed_article_count": len(completed),
                "pending_review_article_count": len(pending_review),
                "raw_article_file_count": len(raw_articles),
                "articles": article_rows,
                "representative_articles": article_rows[:5],
                "profile_path": rel(profile_path),
                "topic_dir": rel(topic_dir),
            }
        )
    sources = [
        {
            "path": rel(topics_root),
            "kind": "wiki_hub_topics",
            "rows": len(topics),
        }
    ]
    return topics, sources


def load_clusters_and_links(topics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cluster_dir = BACKEND_DATA / "topic_clusters"
    link_dir = BACKEND_DATA / "topic_cluster_links"
    topic_by_id = {topic["topic_id"]: topic for topic in topics}
    raw_links = []
    for path in sorted(link_dir.glob("*.json")):
        link = read_json(path)
        if not isinstance(link, dict):
            continue
        raw_links.append({**link, "_path": rel(path)})
    links_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in raw_links:
        links_by_cluster[str(link.get("cluster_id") or "")].append(link)

    clusters: list[dict[str, Any]] = []
    for path in sorted(cluster_dir.glob("*.json")):
        cluster = read_json(path)
        if not isinstance(cluster, dict):
            continue
        cluster_id = str(cluster.get("cluster_id") or path.stem)
        links = links_by_cluster.get(cluster_id, [])
        wiki_topic_ids = [str(link.get("target_id")) for link in links if link.get("target_type") == "wiki_topic" and link.get("status") != "rejected"]
        topic_articles = []
        for topic_id in wiki_topic_ids:
            topic = topic_by_id.get(topic_id)
            if not topic:
                continue
            topic_articles.extend(topic.get("articles") or [])
        kfc_theme_links = [link for link in links if link.get("target_type") == "kfc_theme" and link.get("status") != "rejected"]
        research_links = [link for link in links if link.get("target_type") == "research_project" and link.get("status") != "rejected"]
        concept_links = [link for link in links if link.get("target_type") == "concept" and link.get("status") != "rejected"]
        clusters.append(
            {
                "cluster_id": cluster_id,
                "title": cluster.get("title") or cluster.get("name") or cluster_id,
                "name": cluster.get("name") or cluster.get("title") or cluster_id,
                "description": cluster.get("description", ""),
                "status": cluster.get("status", ""),
                "aliases": cluster.get("aliases") or [],
                "tags": cluster.get("tags") or [],
                "keywords": cluster.get("keywords") or [],
                "created_source": cluster.get("created_source", ""),
                "created_at": cluster.get("created_at", ""),
                "updated_at": cluster.get("updated_at", ""),
                "wiki_topic_count": len(set(wiki_topic_ids)),
                "article_count": len(topic_articles),
                "kfc_theme_count": len(kfc_theme_links),
                "research_project_count": len(research_links),
                "concept_count": len(concept_links),
                "representative_articles": topic_articles[:5],
                "linked_topic_articles": topic_articles,
                "linked_wiki_topics": [
                    {
                        "topic_id": topic_id,
                        "topic_name": (topic_by_id.get(topic_id) or {}).get("name", topic_id),
                        "article_count": (topic_by_id.get(topic_id) or {}).get("article_count", 0),
                    }
                    for topic_id in wiki_topic_ids
                ],
                "linked_kfc_themes": [link.get("target_id") for link in kfc_theme_links],
                "linked_research_projects": [link.get("target_id") for link in research_links],
                "linked_concepts": [link.get("target_id") for link in concept_links],
                "links": [
                    {
                        "link_id": link.get("link_id", ""),
                        "target_type": link.get("target_type", ""),
                        "target_id": link.get("target_id", ""),
                        "target_title": link.get("target_title", ""),
                        "relation_type": link.get("relation_type") or link.get("role", ""),
                        "status": link.get("status", ""),
                        "link_source": link.get("source") or link.get("created_source", ""),
                    }
                    for link in links
                ],
                "path": rel(path),
            }
        )

    links = [
        {
            "link_id": link.get("link_id", ""),
            "cluster_id": link.get("cluster_id", ""),
            "target_type": link.get("target_type", ""),
            "target_id": link.get("target_id", ""),
            "target_title": link.get("target_title", ""),
            "relation_type": link.get("relation_type") or link.get("role", ""),
            "role": link.get("role", ""),
            "status": link.get("status", ""),
            "confidence": link.get("confidence"),
            "score": link.get("score"),
            "reason": link.get("reason") or link.get("rationale", ""),
            "created_by": link.get("created_by", ""),
            "updated_at": link.get("updated_at", ""),
            "link_source": link.get("source") or link.get("created_source", ""),
            "path": link.get("_path", ""),
        }
        for link in raw_links
    ]
    sources = [
        {"path": rel(cluster_dir), "kind": "topic_clusters", "rows": len(clusters)},
        {"path": rel(link_dir), "kind": "topic_cluster_links", "rows": len(links)},
    ]
    return clusters, links, sources


def collect_project_subassets(project: dict[str, Any], project_path: Path) -> list[dict[str, Any]]:
    project_id = project.get("id") or project.get("project_id") or project_path.parent.name
    containers = {
        "evidence_item": "evidence_items",
        "insight_card": "insight_cards",
        "artifact_draft": "artifact_drafts",
        "artifact_pack": "artifact_packs",
        "research_run": "research_runs",
        "external_research_pack": "external_research_packs",
        "decision_record": "leadership_decision_records",
        "briefing": "leadership_briefings",
        "governance_review": "governance_reviews",
        "snapshot": "research_snapshots",
    }
    rows: list[dict[str, Any]] = []
    for asset_type, key in containers.items():
        for idx, item in enumerate(project.get(key) or []):
            if not isinstance(item, dict):
                continue
            asset_id = (
                item.get("id")
                or item.get("evidence_id")
                or item.get("pack_id")
                or item.get("run_id")
                or item.get("decision_id")
                or item.get("briefing_id")
                or item.get("review_id")
                or item.get("snapshot_id")
                or f"{project_id}_{key}_{idx}"
            )
            rows.append(
                {
                    "asset_type": asset_type,
                    "id": asset_id,
                    "title": item.get("title") or item.get("claim") or item.get("summary") or asset_id,
                    "name": item.get("name", ""),
                    "description": item.get("description") or item.get("summary") or item.get("claim") or "",
                    "summary": item.get("summary", ""),
                    "tags": item.get("tags") or [],
                    "keywords": item.get("keywords") or [],
                    "topics": item.get("topics") or [],
                    "source_url": item.get("source_url", ""),
                    "source_path": rel(project_path),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                    "related_ids": compact(item.get("linked_option_ids") or item.get("linked_validation_plan_ids") or item.get("source_refs") or []),
                    "project_id": project_id,
                    "theme_id": "",
                    "topic_id": "",
                    "cluster_id": "",
                    "raw_metadata_keys": sorted(item.keys()),
                }
            )
    return rows


def load_kfc_assets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    themes_path = UPLOADS_PROJECTS / "global_themes.json"
    themes_data = read_json(themes_path) or {}
    themes = themes_data.get("themes") if isinstance(themes_data, dict) else {}
    if isinstance(themes, dict):
        for theme_id, theme in themes.items():
            if not isinstance(theme, dict):
                continue
            assets.append(
                {
                    "asset_type": "kfc_theme",
                    "id": theme.get("theme_id") or theme_id,
                    "title": theme.get("name") or theme_id,
                    "name": theme.get("name") or theme_id,
                    "description": theme.get("description", ""),
                    "summary": theme.get("summary", ""),
                    "tags": theme.get("tags") or [],
                    "keywords": theme.get("keywords") or [],
                    "topics": theme.get("topics") or [],
                    "source_url": theme.get("source_url", ""),
                    "source_path": rel(themes_path),
                    "created_at": theme.get("created_at", ""),
                    "updated_at": theme.get("updated_at", ""),
                    "related_ids": compact([m.get("entry_id") for m in theme.get("concept_memberships") or [] if isinstance(m, dict)], 200),
                    "project_id": "",
                    "theme_id": theme.get("theme_id") or theme_id,
                    "topic_id": "",
                    "cluster_id": "",
                    "status": theme.get("status", ""),
                    "source": theme.get("source", ""),
                    "raw_metadata_keys": sorted(theme.keys()),
                }
            )
    sources.append({"path": rel(themes_path), "kind": "kfc_global_themes", "rows": len(themes or {}) if isinstance(themes, dict) else 0})

    concepts_path = UPLOADS_PROJECTS / "concept_registry.json"
    concepts_data = read_json(concepts_path) or {}
    concepts = concepts_data.get("entries") if isinstance(concepts_data, dict) else {}
    if isinstance(concepts, dict):
        for entry_id, concept in concepts.items():
            if not isinstance(concept, dict):
                continue
            source_links = concept.get("source_links") or []
            assets.append(
                {
                    "asset_type": "concept",
                    "id": concept.get("entry_id") or entry_id,
                    "title": concept.get("canonical_name") or entry_id,
                    "name": concept.get("canonical_name") or entry_id,
                    "description": concept.get("description", ""),
                    "summary": concept.get("summary", ""),
                    "tags": concept.get("tags") or [],
                    "keywords": concept.get("keywords") or concept.get("aliases") or [],
                    "topics": [link.get("project_name") for link in source_links if isinstance(link, dict)],
                    "source_url": "",
                    "source_path": rel(concepts_path),
                    "created_at": concept.get("created_at", ""),
                    "updated_at": concept.get("updated_at", ""),
                    "related_ids": compact([link.get("project_id") for link in source_links if isinstance(link, dict)], 50),
                    "project_id": "",
                    "theme_id": "",
                    "topic_id": "",
                    "cluster_id": "",
                    "concept_type": concept.get("concept_type", ""),
                    "raw_metadata_keys": sorted(concept.keys()),
                }
            )
    sources.append({"path": rel(concepts_path), "kind": "kfc_concept_registry", "rows": len(concepts or {}) if isinstance(concepts, dict) else 0})

    research_dir = BACKEND_DATA / "research_projects"
    research_paths = sorted(research_dir.glob("*.json"))
    for path in research_paths:
        project = read_json(path)
        if not isinstance(project, dict):
            continue
        project_id = project.get("id") or project.get("project_id") or path.stem
        assets.append(
            {
                "asset_type": "research_project",
                "id": project_id,
                "title": project.get("title") or project_id,
                "name": project.get("title") or project_id,
                "description": project.get("background") or project.get("description") or project.get("goal") or "",
                "summary": project.get("summary", ""),
                "tags": project.get("tags") or [],
                "keywords": project.get("keywords") or [],
                "topics": project.get("topics") or [],
                "source_url": project.get("source_url", ""),
                "source_path": rel(path),
                "created_at": project.get("created_at", ""),
                "updated_at": project.get("updated_at", ""),
                "related_ids": compact((project.get("linked_themes") or []) + (project.get("linked_concepts") or []), 100),
                "project_id": project_id,
                "theme_id": "",
                "topic_id": "",
                "cluster_id": "",
                "status": project.get("status", ""),
                "asset_counts": {
                    "evidence_items": len(project.get("evidence_items") or []),
                    "insight_cards": len(project.get("insight_cards") or []),
                    "artifact_drafts": len(project.get("artifact_drafts") or []),
                    "artifact_packs": len(project.get("artifact_packs") or []),
                    "research_runs": len(project.get("research_runs") or []),
                },
                "raw_metadata_keys": sorted(project.keys()),
            }
        )
        assets.extend(collect_project_subassets(project, path))
    sources.append({"path": rel(research_dir), "kind": "research_projects", "rows": len(research_paths)})

    legacy_project_paths = sorted(UPLOADS_PROJECTS.glob("proj_*/project.json"))
    for path in legacy_project_paths:
        project = read_json(path)
        if not isinstance(project, dict):
            continue
        project_id = project.get("id") or project.get("project_id") or path.parent.name
        assets.append(
            {
                "asset_type": "legacy_project",
                "id": project_id,
                "title": project.get("title") or project.get("name") or project_id,
                "name": project.get("name") or project.get("title") or project_id,
                "description": project.get("description") or project.get("summary") or "",
                "summary": project.get("summary", ""),
                "tags": project.get("tags") or [],
                "keywords": project.get("keywords") or [],
                "topics": compact(project.get("theme_clusters") or project.get("concept_decisions") or project.get("theme_decisions") or []),
                "source_url": project.get("source_url") or project.get("url") or "",
                "source_path": rel(path),
                "created_at": project.get("created_at", ""),
                "updated_at": project.get("updated_at", ""),
                "related_ids": [],
                "project_id": project_id,
                "theme_id": "",
                "topic_id": "",
                "cluster_id": "",
                "status": project.get("status", ""),
                "raw_metadata_keys": sorted(project.keys()),
            }
        )
    sources.append({"path": rel(UPLOADS_PROJECTS / "proj_*/project.json"), "kind": "legacy_projects", "rows": len(legacy_project_paths)})

    notes_dir = BACKEND_DATA / "notes"
    note_paths = sorted(notes_dir.glob("*.md"))
    for path in note_paths:
        assets.append(
            {
                "asset_type": "note",
                "id": path.stem,
                "title": extract_markdown_title(path) or path.stem,
                "name": extract_markdown_title(path) or path.stem,
                "description": "",
                "summary": "",
                "tags": [],
                "keywords": [],
                "topics": [],
                "source_url": "",
                "source_path": rel(path),
                "created_at": "",
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "related_ids": [],
                "project_id": "",
                "theme_id": "",
                "topic_id": "",
                "cluster_id": "",
                "raw_metadata_keys": [],
            }
        )
    sources.append({"path": rel(notes_dir), "kind": "notes", "rows": len(note_paths)})
    return assets, sources


def latin_tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text.lower()) if tok not in {"the", "and", "for", "with", "this", "that"}}


def cjk_grams(text: str) -> set[str]:
    chars = re.findall(r"[\u4e00-\u9fff]", text)
    grams = {"".join(chars[i : i + 2]) for i in range(max(0, len(chars) - 1))}
    grams |= {"".join(chars[i : i + 3]) for i in range(max(0, len(chars) - 2))}
    return {gram for gram in grams if len(gram) >= 2}


def tokens_for(item: dict[str, Any]) -> set[str]:
    parts: list[str] = []
    for key in ["title", "name", "description", "summary", "status", "source", "concept_type"]:
        value = item.get(key)
        if value:
            parts.append(str(value))
    for key in ["keywords", "tags", "topics", "aliases", "concept_seeds", "related_ids"]:
        parts.extend(compact(item.get(key), 40))
    text = " ".join(parts)
    return latin_tokens(text) | cjk_grams(text)


def make_matrices(
    articles: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    links: list[dict[str, Any]],
    assets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    topic_by_id = {topic["topic_id"]: topic for topic in topics}
    cluster_by_id = {cluster["cluster_id"]: cluster for cluster in clusters}
    asset_by_key = {(asset.get("asset_type"), asset.get("id")): asset for asset in assets}

    article_to_topic = []
    for article in sorted(articles, key=lambda item: (str(item.get("topic_id") or ""), str(item.get("title") or ""))):
        assigned = article.get("topic_id") or ""
        guessed = article.get("guessed_topics") or []
        if not assigned and guessed and isinstance(guessed[0], dict):
            assigned = guessed[0].get("topic_id") or ""
        article_to_topic.append(
            {
                "article_title": article.get("title", ""),
                "candidate_id": article.get("candidate_id", ""),
                "assigned_topic_id": assigned,
                "assigned_topic_name": (topic_by_id.get(assigned) or {}).get("name", ""),
                "guessed_topics": guessed,
                "digest_topics": article.get("digest", {}).get("topics", []),
                "digest_keywords": article.get("digest", {}).get("keywords", []),
                "status": article.get("status", ""),
            }
        )

    topic_links = [link for link in links if link.get("target_type") == "wiki_topic"]
    topic_to_cluster = []
    for topic in topics:
        matched = [link for link in topic_links if link.get("target_id") == topic["topic_id"]]
        if not matched:
            topic_to_cluster.append(
                {
                    "topic_id": topic["topic_id"],
                    "topic_name": topic["name"],
                    "article_count": topic["article_count"],
                    "cluster_id": "",
                    "cluster_name": "",
                    "relation_type": "",
                    "status": "unlinked",
                    "link_source": "",
                }
            )
        for link in matched:
            cluster = cluster_by_id.get(str(link.get("cluster_id") or ""))
            topic_to_cluster.append(
                {
                    "topic_id": topic["topic_id"],
                    "topic_name": topic["name"],
                    "article_count": topic["article_count"],
                    "cluster_id": link.get("cluster_id", ""),
                    "cluster_name": (cluster or {}).get("title", ""),
                    "relation_type": link.get("relation_type") or link.get("role") or "",
                    "status": link.get("status", ""),
                    "link_source": link.get("link_source", ""),
                }
            )

    cluster_to_kfc = []
    for cluster in clusters:
        matched = [
            link
            for link in links
            if link.get("cluster_id") == cluster["cluster_id"] and link.get("target_type") in {"kfc_theme", "research_project", "concept"}
        ]
        if not matched:
            cluster_to_kfc.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "cluster_name": cluster["title"],
                    "target_type": "",
                    "target_id": "",
                    "target_title": "",
                    "relation_type": "",
                    "status": "no_kfc_asset_links",
                    "link_source": "",
                }
            )
        for link in matched:
            target_type = "kfc_theme" if link.get("target_type") == "kfc_theme" else link.get("target_type")
            asset = asset_by_key.get((target_type, link.get("target_id")))
            cluster_to_kfc.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "cluster_name": cluster["title"],
                    "target_type": link.get("target_type", ""),
                    "target_id": link.get("target_id", ""),
                    "target_title": (asset or {}).get("title") or link.get("target_title", ""),
                    "relation_type": link.get("relation_type") or link.get("role") or "",
                    "status": link.get("status", ""),
                    "link_source": link.get("link_source", ""),
                }
            )

    linked_asset_ids = {(link.get("target_type"), link.get("target_id")) for link in links}
    potential_missing_links = []
    candidate_assets = [
        asset
        for asset in assets
        if asset.get("asset_type") in {"kfc_theme", "research_project", "concept", "legacy_project", "evidence_item", "insight_card", "note"}
    ]
    asset_tokens = {id(asset): tokens_for(asset) for asset in candidate_assets}
    for cluster in clusters:
        cluster_tokens = tokens_for(cluster)
        if not cluster_tokens:
            continue
        scored = []
        for asset in candidate_assets:
            target_type = asset.get("asset_type")
            normalized_target = "kfc_theme" if target_type == "kfc_theme" else target_type
            if (normalized_target, asset.get("id")) in linked_asset_ids or (target_type, asset.get("id")) in linked_asset_ids:
                continue
            overlap = sorted(cluster_tokens & asset_tokens[id(asset)])
            if len(overlap) < 2:
                continue
            denom = math.sqrt(max(1, len(cluster_tokens)) * max(1, len(asset_tokens[id(asset)])))
            score = len(overlap) / denom
            if score < 0.08 and len(overlap) < 4:
                continue
            scored.append((score, len(overlap), overlap, asset))
        for score, _, overlap, asset in sorted(scored, key=lambda item: (item[0], item[1]), reverse=True)[:20]:
            potential_missing_links.append(
                {
                    "source_type": "topic_cluster",
                    "source_id": cluster["cluster_id"],
                    "source_title": cluster["title"],
                    "candidate_target_type": asset.get("asset_type", ""),
                    "candidate_target_id": asset.get("id", ""),
                    "candidate_target_title": asset.get("title", ""),
                    "overlap_keywords": overlap[:20],
                    "reason": f"read-only keyword overlap score={score:.3f}; current TopicClusterLink does not reference this target",
                    "risk_note": "启发式文本重叠只能提示漏链候选，不能作为自动建链依据。",
                }
            )

    return {
        "article_to_topic": article_to_topic,
        "topic_to_cluster": topic_to_cluster,
        "cluster_to_kfc_assets": cluster_to_kfc,
        "potential_missing_links": potential_missing_links,
    }


def detect_anomalies(
    topics: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    links: list[dict[str, Any]],
    matrices: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    mixed_topics = []
    for topic in topics:
        articles = topic.get("articles") or []
        if len(articles) < 2:
            continue
        topic_tokens = tokens_for(topic)
        weak = []
        keyword_sets = []
        for article in articles:
            article_tokens = tokens_for(
                {
                    "title": article.get("title", ""),
                    "summary": article.get("digest_summary", ""),
                    "keywords": article.get("tags") or [],
                }
            )
            keyword_sets.append(article_tokens)
            overlap = topic_tokens & article_tokens
            if topic_tokens and len(overlap) == 0:
                weak.append({"candidate_id": article.get("candidate_id", ""), "title": article.get("title", ""), "reason": "title/digest keywords have no overlap with topic profile keywords"})
        common = set.intersection(*[ks for ks in keyword_sets if ks]) if any(keyword_sets) else set()
        if weak or (len(articles) >= 5 and len(common) == 0):
            mixed_topics.append(
                {
                    "topic_id": topic["topic_id"],
                    "topic_name": topic["name"],
                    "article_count": topic["article_count"],
                    "issue": "topic articles may be mixed or topic keyword boundary may be weak",
                    "weak_article_examples": weak[:10],
                    "common_keyword_count": len(common),
                    "risk_note": "基于标题、topic profile、digest 摘要/关键词的只读启发式检测。",
                }
            )

    cluster_boundary = []
    topic_link_counts = Counter(link.get("cluster_id") for link in links if link.get("target_type") == "wiki_topic" and link.get("status") != "rejected")
    for cluster in clusters:
        title = str(cluster.get("title") or "")
        normalized = title.strip().lower()
        reasons = []
        if topic_link_counts.get(cluster["cluster_id"], 0) == 1 and str(cluster.get("created_source") or "").startswith("legacy"):
            reasons.append("cluster has exactly one Wiki/VT Topic and was imported from legacy wiki state")
        if topic_link_counts.get(cluster["cluster_id"], 0) == 1 and cluster.get("wiki_topic_count") == 1:
            reasons.append("cluster is approximately 1:1 with a Wiki/VT Topic")
        if normalized in GENERIC_CLUSTER_NAMES or any(normalized == name for name in GENERIC_CLUSTER_NAMES):
            reasons.append("cluster title is very generic")
        if title.lower().startswith(("ai ", "ai-", "ai/")) and len(title.split()) <= 2:
            reasons.append("cluster title may be too broad")
        if reasons:
            cluster_boundary.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "cluster_name": cluster["title"],
                    "wiki_topic_count": cluster["wiki_topic_count"],
                    "article_count": cluster["article_count"],
                    "kfc_theme_count": cluster["kfc_theme_count"],
                    "research_project_count": cluster["research_project_count"],
                    "reasons": reasons,
                }
            )

    missing_links = []
    for cluster in clusters:
        if cluster["article_count"] > 0 and cluster["kfc_theme_count"] == 0:
            missing_links.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "cluster_name": cluster["title"],
                    "issue": "Wiki/VT Topic has articles but Cluster has zero KFC Theme links",
                    "article_count": cluster["article_count"],
                    "representative_articles": cluster.get("representative_articles", [])[:3],
                }
            )
        if cluster.get("representative_articles") and cluster["kfc_theme_count"] == 0 and cluster["research_project_count"] == 0 and cluster.get("concept_count", 0) == 0:
            missing_links.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "cluster_name": cluster["title"],
                    "issue": "Cluster has representative articles but no KFC Theme / ResearchProject / Concept links",
                    "article_count": cluster["article_count"],
                    "representative_articles": cluster.get("representative_articles", [])[:3],
                }
            )
    for item in matrices.get("potential_missing_links", [])[:200]:
        missing_links.append(
            {
                "cluster_id": item["source_id"],
                "cluster_name": item["source_title"],
                "issue": "KFC asset looks related by keyword overlap but has no TopicClusterLink",
                "candidate_target_type": item["candidate_target_type"],
                "candidate_target_id": item["candidate_target_id"],
                "candidate_target_title": item["candidate_target_title"],
                "overlap_keywords": item["overlap_keywords"],
                "risk_note": item["risk_note"],
            }
        )

    count_mismatches = []
    topic_by_id = {topic["topic_id"]: topic for topic in topics}
    for cluster in clusters:
        linked_topic_ids = [link["target_id"] for link in links if link.get("cluster_id") == cluster["cluster_id"] and link.get("target_type") == "wiki_topic" and link.get("status") != "rejected"]
        expected_articles = sum((topic_by_id.get(topic_id) or {}).get("article_count", 0) for topic_id in linked_topic_ids)
        if expected_articles != cluster["article_count"]:
            count_mismatches.append(
                {
                    "entity_type": "topic_cluster",
                    "entity_id": cluster["cluster_id"],
                    "field": "article_count",
                    "computed_from_cluster": cluster["article_count"],
                    "computed_from_linked_topics": expected_articles,
                    "note": "Mismatch between cluster linked_topic_articles count and linked topic article_count sum.",
                }
            )
    topic_ids_with_clusters = {row["topic_id"] for row in matrices.get("topic_to_cluster", []) if row.get("cluster_id")}
    topics_with_articles_without_cluster = [topic for topic in topics if topic["article_count"] > 0 and topic["topic_id"] not in topic_ids_with_clusters]
    if topics_with_articles_without_cluster:
        count_mismatches.append(
            {
                "entity_type": "wiki_topics",
                "field": "topic_to_cluster_coverage",
                "topic_count": len(topics_with_articles_without_cluster),
                "examples": [{"topic_id": topic["topic_id"], "topic_name": topic["name"], "article_count": topic["article_count"]} for topic in topics_with_articles_without_cluster[:20]],
                "note": "Wiki topics have article_count > 0 but no TopicClusterLink.",
            }
        )
    return {
        "mixed_topics": mixed_topics,
        "cluster_boundary_issues": cluster_boundary,
        "missing_links": missing_links,
        "count_mismatches": count_mismatches,
    }


def raw_counts(
    articles: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    links: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    data_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    by_asset_type = Counter(asset.get("asset_type", "unknown") for asset in assets)
    by_article_status = Counter(str(article.get("status") or "unknown") for article in articles)
    return {
        "wiki_intake_articles": len(articles),
        "wiki_topics": len(topics),
        "topic_clusters": len(clusters),
        "topic_cluster_links": len(links),
        "kfc_themes": by_asset_type.get("kfc_theme", 0),
        "research_projects": by_asset_type.get("research_project", 0),
        "concept_assets": by_asset_type.get("concept", 0),
        "legacy_projects": by_asset_type.get("legacy_project", 0),
        "notes": by_asset_type.get("note", 0),
        "research_material_assets": sum(
            by_asset_type.get(key, 0)
            for key in [
                "evidence_item",
                "insight_card",
                "artifact_draft",
                "artifact_pack",
                "research_run",
                "external_research_pack",
                "decision_record",
                "briefing",
                "governance_review",
                "snapshot",
            ]
        ),
        "asset_type_counts": dict(sorted(by_asset_type.items())),
        "article_status_counts": dict(sorted(by_article_status.items())),
        "source_files": data_sources,
    }


def summarize(bundle: dict[str, Any], counts: dict[str, Any]) -> str:
    clusters = bundle["topic_clusters"]
    one_to_one = [
        cluster
        for cluster in clusters
        if cluster.get("wiki_topic_count") == 1
        and cluster.get("kfc_theme_count") == 0
        and cluster.get("research_project_count") == 0
        and cluster.get("concept_count", 0) == 0
    ]
    unclear = bundle["anomalies"]["cluster_boundary_issues"][:20]
    missing_assets = bundle["matrices"]["potential_missing_links"][:20]
    empty_sources = [source for source in bundle["data_sources"] if source.get("rows") == 0]
    no_link_clusters = [cluster for cluster in clusters if cluster.get("kfc_theme_count") == 0 and cluster.get("research_project_count") == 0 and cluster.get("concept_count", 0) == 0]
    focus = []
    for item in bundle["anomalies"]["missing_links"]:
        label = item.get("cluster_name") or item.get("candidate_target_title") or item.get("issue")
        if label and label not in focus:
            focus.append(label)
        if len(focus) >= 10:
            break

    lines = [
        "# 主题分类诊断摘要",
        "",
        f"- 生成时间：{bundle['generated_at']}",
        f"- 仓库：`{bundle['repo']}`",
        "",
        "## 总量",
        "",
        f"- Wiki Intake 文章：{counts['wiki_intake_articles']}",
        f"- Wiki/VT Topic：{counts['wiki_topics']}",
        f"- Topic Cluster：{counts['topic_clusters']}",
        f"- Topic Cluster Link：{counts['topic_cluster_links']}",
        f"- KFC Theme：{counts['kfc_themes']}",
        f"- ResearchProject：{counts['research_projects']}",
        f"- 概念资产：{counts['concept_assets']}",
        f"- 研究素材/卡片/证据类资产：{counts['research_material_assets']}",
        f"- 旧 Project 素材：{counts['legacy_projects']}",
        "",
        "## 当前分类链路的实际形态",
        "",
        "当前链路主要是：Wiki Intake / auto_processed_manifest -> Wiki/VT Topic -> TopicClusterLink(wiki_topic) -> Topic Cluster。"
        " 现有 Topic Cluster 多数只通过 `wiki_topic` link 接上 Wiki/VT Topic；"
        " KFC Theme、ResearchProject、Concept 与 Cluster 的 link 基本没有建立，因此页面上 KFC Theme / ResearchProject 计数经常为 0。",
        "",
        "## Legacy 1:1 包装",
        "",
        f"- 疑似只是 legacy Wiki Topic 的 1:1 Cluster 包装：{len(one_to_one)} 个。",
    ]
    for cluster in one_to_one[:20]:
        topic_names = ", ".join(t.get("topic_name", "") for t in cluster.get("linked_wiki_topics", []))
        lines.append(f"- `{cluster['cluster_id']}`：{cluster['title']} -> {topic_names or 'no topic name'}")
    lines.extend(
        [
            "",
            "## 边界不清的 Topic / Cluster",
            "",
        ]
    )
    if unclear:
        for issue in unclear:
            lines.append(f"- `{issue['cluster_id']}`：{issue['cluster_name']}；原因：{'；'.join(issue['reasons'])}")
    else:
        lines.append("- 未发现明显 cluster 边界异常。")
    lines.extend(
        [
            "",
            "## 可能没有关联进 Cluster 的 KFC 资产",
            "",
        ]
    )
    if missing_assets:
        for item in missing_assets:
            lines.append(
                f"- `{item['source_id']}` {item['source_title']} -> {item['candidate_target_type']} `{item['candidate_target_id']}` {item['candidate_target_title']}；重叠：{', '.join(item['overlap_keywords'][:8])}"
            )
    else:
        lines.append("- 未发现足够关键词重叠的漏链候选。")
    lines.extend(
        [
            "",
            "## 空数据源 / 未建 link",
            "",
        ]
    )
    if empty_sources:
        for source in empty_sources:
            lines.append(f"- 空数据源：`{source['path']}` ({source['kind']})")
    else:
        lines.append("- 本次纳入的数据源均非空。")
    lines.append(f"- 没有 KFC Theme / ResearchProject / Concept link 的 Cluster：{len(no_link_clusters)} 个。")
    lines.extend(
        [
            "",
            "## 给 ChatGPT 后续人工分析最需要关注的 10 个样例",
            "",
        ]
    )
    for idx, label in enumerate(focus[:10], start=1):
        lines.append(f"{idx}. {label}")
    if not focus:
        lines.append("1. 暂无明显样例。")
    lines.extend(
        [
            "",
            "## 诊断限制",
            "",
            "- 本诊断只读文件系统，不调用模型、不运行 worker、不写业务 sidecar。",
            "- Potential Missing Links 只是基于 title / tags / keywords / summary 的关键词重叠启发式结果，不代表应自动建链。",
            "- Markdown 正文没有全文导出；只有缺少结构化摘要时才使用标题或少量元数据辅助识别。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()

    out_dir = Path(args.out_root).resolve() / f"topic_taxonomy_audit_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    inventory_rows, inventory_md = list_inventory()
    articles, _intake_state, intake_sources = load_wiki_intake()
    topics, topic_sources = load_topics(articles)
    clusters, links, cluster_sources = load_clusters_and_links(topics)
    assets, asset_sources = load_kfc_assets()
    data_sources = intake_sources + topic_sources + cluster_sources + asset_sources
    matrices = make_matrices(articles, topics, clusters, links, assets)
    anomalies = detect_anomalies(topics, clusters, links, matrices)
    counts = raw_counts(articles, topics, clusters, links, assets, data_sources)

    bundle = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "data_sources": data_sources,
        "directory_inventory": inventory_rows,
        "wiki_intake_articles": articles,
        "wiki_topics": topics,
        "topic_clusters": clusters,
        "topic_cluster_links": links,
        "kfc_assets": assets,
        "raw_counts": counts,
        "matrices": matrices,
        "anomalies": anomalies,
    }

    (out_dir / "taxonomy_audit_bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "raw_counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "directory_inventory.md").write_text(inventory_md, encoding="utf-8")
    (out_dir / "taxonomy_audit_summary.md").write_text(summarize(bundle, counts), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
