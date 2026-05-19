#!/usr/bin/env python3
"""Build repo-aware topic candidates for wiki auto-intake routing."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 12

SPECIAL_TERMS = [
    "阿里云",
    "大数据",
    "数据平台",
    "数据智能",
    "湖仓",
    "多模态",
    "语义层",
    "知识工作台",
    "分词",
    "计费",
    "算力",
    "agent",
    "data+ai",
    "dataworks",
    "maxcompute",
    "maxframe",
    "flink",
    "pai",
    "chatbi",
    "nl2sql",
    "lakehouse",
    "cloud",
    "platform",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def slug_tokens(value: str) -> set[str]:
    tokens = set()
    for raw in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", value.lower()):
        token = raw.strip()
        if not token:
            continue
        tokens.add(token)
        if token.endswith("s") and len(token) > 3:
            tokens.add(token[:-1])
    for term in SPECIAL_TERMS:
        if term.lower() in value.lower():
            tokens.add(term.lower())
    return tokens


def compact(values: list[Any], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def manifest_by_id(intake_dir: Path) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(intake_dir / "manifest.jsonl"):
        for key in [row.get("candidate_id"), row.get("source_id")]:
            text = str(key or "").strip()
            if text:
                by_id[text] = row
    return by_id


def article_titles_by_topic(intake_dir: Path) -> dict[str, list[str]]:
    manifest = manifest_by_id(intake_dir)
    titles: dict[str, list[str]] = {}
    for row in read_jsonl(intake_dir / "auto_processed_manifest.jsonl"):
        topic_id = str(row.get("topic_id") or "").strip()
        if not topic_id:
            continue
        candidate_id = str(row.get("candidate_id") or row.get("source_id") or "").strip()
        source_id = str(row.get("source_id") or candidate_id).strip()
        record = manifest.get(candidate_id) or manifest.get(source_id) or {}
        title = str(record.get("title") or "").strip()
        if not title:
            raw_path = Path(str(row.get("raw_article_path") or ""))
            title = raw_path.stem if raw_path.name else ""
        if title:
            titles.setdefault(topic_id, []).append(title)
    return titles


def load_topic_catalog(wiki_hub: Path, intake_dir: Path | None = None) -> list[dict[str, Any]]:
    topics_root = wiki_hub / "topics"
    processed_titles = article_titles_by_topic(intake_dir) if intake_dir else {}
    catalog: list[dict[str, Any]] = []
    if not topics_root.exists():
        return catalog
    for profile_path in sorted(topics_root.glob("*/topic_profile.json")):
        topic_id = profile_path.parent.name
        profile = read_json(profile_path)
        display_name = str(profile.get("display_name") or profile.get("title") or topic_id)
        aliases = compact(
            list(profile.get("aliases") or [])
            + list(profile.get("alias") or [] if isinstance(profile.get("alias"), list) else [])
            + [((profile.get("routing_decision") or {}).get("new_topic_suggestion") or {}).get("topic_id", "")]
            + [((profile.get("routing_decision") or {}).get("new_topic_suggestion") or {}).get("label", "")]
        )
        keywords = compact(list(profile.get("topic_keywords") or []) + list(profile.get("concept_seeds") or []), 16)
        representatives = compact(processed_titles.get(topic_id, []), 8)
        text = " ".join(
            [
                topic_id,
                display_name,
                str(profile.get("description") or ""),
                " ".join(aliases),
                " ".join(keywords),
                " ".join(representatives),
            ]
        )
        catalog.append(
            {
                "topic_id": topic_id,
                "label": display_name,
                "description": str(profile.get("description") or ""),
                "aliases": aliases,
                "keywords": keywords,
                "representative_articles": representatives,
                "tokens": sorted(slug_tokens(text)),
            }
        )
    return catalog


def score_topic(topic: dict[str, Any], article_text: str, guessed_topics: list[dict[str, Any]]) -> tuple[float, list[str]]:
    article_tokens = slug_tokens(article_text)
    topic_tokens = set(topic.get("tokens") or [])
    score = 0.0
    reasons: list[str] = []
    topic_id = str(topic.get("topic_id") or "")
    for guess in guessed_topics:
        if str((guess or {}).get("topic_id") or "") == topic_id:
            guess_score = float((guess or {}).get("score") or 1)
            score += 2.0 + min(guess_score, 4.0) * 0.3
            reasons.append("scanner_guess")
    overlap = sorted(article_tokens & topic_tokens)
    if overlap:
        score += min(len(overlap), 8) * 0.45
        reasons.append("term_overlap:" + ",".join(overlap[:5]))
    for title in topic.get("representative_articles") or []:
        shared = slug_tokens(str(title)) & article_tokens
        if len(shared) >= 2:
            score += 1.5 + min(len(shared), 5) * 0.2
            reasons.append("similar_prior_article")
            break
    label_tokens = slug_tokens(str(topic.get("label") or ""))
    if label_tokens and label_tokens <= article_tokens:
        score += 1.0
        reasons.append("label_exact_terms")
    return score, reasons


def select_topic_candidates(
    *,
    wiki_hub: Path,
    intake_dir: Path,
    job: dict[str, Any],
    article_markdown: str,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    catalog = load_topic_catalog(wiki_hub, intake_dir)
    guessed = job.get("guessed_topics") if isinstance(job.get("guessed_topics"), list) else []
    article_text = "\n".join([str(job.get("title") or ""), article_markdown[:12000]])
    scored = []
    for topic in catalog:
        score, reasons = score_topic(topic, article_text, guessed)
        scored.append({**topic, "score": round(score, 4), "reasons": reasons})
    scored.sort(key=lambda item: (-float(item.get("score") or 0), str(item.get("topic_id") or "")))
    selected = [item for item in scored if float(item.get("score") or 0) > 0][:limit]
    for topic_id in [str((guess or {}).get("topic_id") or "") for guess in guessed]:
        if topic_id and all(item.get("topic_id") != topic_id for item in selected):
            match = next((item for item in scored if item.get("topic_id") == topic_id), None)
            if match:
                selected.append(match)
    if not selected:
        selected = scored[: min(limit, len(scored))]
    return {
        "schema_version": "topic-candidate-context.v1",
        "selection_method": "repo_catalog_keyword_prior_article_hybrid_v1",
        "candidate_limit": limit,
        "visible_candidate_topics": [
            {
                "topic_id": item["topic_id"],
                "label": item.get("label", item["topic_id"]),
                "description": item.get("description", ""),
                "aliases": item.get("aliases", []),
                "keywords": item.get("keywords", []),
                "representative_articles": item.get("representative_articles", [])[:5],
                "score": item.get("score", 0),
                "reasons": item.get("reasons", []),
            }
            for item in selected[:limit]
        ],
        "topic_catalog": [
            {
                "topic_id": item["topic_id"],
                "label": item.get("label", item["topic_id"]),
                "description": item.get("description", ""),
                "aliases": item.get("aliases", []),
                "keywords": item.get("keywords", []),
                "representative_articles": item.get("representative_articles", [])[:5],
            }
            for item in catalog
        ],
    }


def write_topic_candidate_context(
    *,
    wiki_hub: Path,
    intake_dir: Path,
    job: dict[str, Any],
    article_path: Path,
    output_path: Path,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    article_markdown = article_path.read_text(encoding="utf-8", errors="replace") if article_path.exists() else ""
    context = select_topic_candidates(
        wiki_hub=wiki_hub,
        intake_dir=intake_dir,
        job=job,
        article_markdown=article_markdown,
        limit=limit,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return context
