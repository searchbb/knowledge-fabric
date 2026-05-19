#!/usr/bin/env python3
"""Apply a single Clippings intake decision.

This processor performs the real post-decision side effects for the local
prototype:
- copy accepted wiki-bound Markdown into the wiki raw area
- copy local Markdown assets and rewrite copied Markdown references
- enqueue KFC-bound material into a local intake queue
- optionally archive processed source files after all requested destinations
  succeed

It never creates KFC projects and never edits the source Markdown in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from generate_source_digest import generate_source_digest
from incremental_compile_topic import incremental_compile, update_frontmatter


LLM_WIKI_DESTINATIONS = {"llm_wiki_only", "both"}
KFC_DESTINATIONS = {"kfc_only", "both"}
TOOL_VERSION = "clippings-intake-apply-processor-0.1"
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def slugify(text: str, fallback: str) -> str:
    value = text.lower()
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return (value[:80].strip("-") or fallback).strip("-") or fallback


def safe_filename(name: str) -> str:
    value = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "-", name).strip("-")
    return value or "asset"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate unique path for {path}")


def local_markdown_refs(markdown: str) -> list[str]:
    refs: list[str] = []
    patterns = [
        r"!\[[^\]]*\]\(([^)]+)\)",
        r"\[\[([^]\n]+\.(?:png|jpg|jpeg|gif|webp|svg|pdf))\]\]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, markdown, flags=re.IGNORECASE):
            raw = match.group(1).strip()
            if not raw:
                continue
            raw = raw.split("#", 1)[0].strip()
            raw = raw.split("?", 1)[0].strip()
            if "://" in raw or raw.startswith(("/", "\\")):
                continue
            refs.append(unquote(raw))
    return list(dict.fromkeys(refs))


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(markdown)
    if not match:
        return {}, markdown
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        metadata[key.strip()] = value
    return metadata, markdown[match.end():]


def yaml_string(value: Any) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def plain_excerpt(markdown: str, limit: int = 220) -> str:
    _, body = parse_frontmatter(markdown)
    lines: list[str] = []
    in_code = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith("!") or line.startswith("> 来源"):
            continue
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = cleaned.strip("#>*- 　")
        if cleaned:
            lines.append(cleaned)
        if sum(len(item) for item in lines) >= limit:
            break
    return " ".join(lines)[:limit]


def source_fingerprint(source_path: Path, markdown: str, candidate_id: str = "") -> str:
    seed = "\n".join([str(source_path), candidate_id, markdown[:4000]])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def related_topics_for_decision(decision: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    for raw in [
        decision.get("topic_id"),
        decision.get("recommended_topic"),
        decision.get("source_topic"),
        decision.get("topic"),
        *(decision.get("related_topics") if isinstance(decision.get("related_topics"), list) else []),
    ]:
        value = str(raw or "").strip()
        if value and value not in topics:
            topics.append(value)
    return topics


def digest_frontmatter_updates(digest_result: dict[str, Any] | None, error: str = "") -> dict[str, Any]:
    if not digest_result:
        return {
            "digest_status": "digest_failed",
            "digest_error": error[:500],
            "digest_version": "",
            "digest_json_path": "",
            "digest_markdown_path": "",
        }
    digest = digest_result.get("digest") or {}
    return {
        "digest_status": "generated",
        "digest_error": "",
        "digest_version": digest.get("digest_version", "source_digest_v1"),
        "digest_json_path": digest_result.get("json_path", ""),
        "digest_markdown_path": digest_result.get("md_path", ""),
        "digest_recommended_topic": digest.get("recommended_topic", ""),
        "digest_related_topics": json.dumps(digest.get("related_topics", []), ensure_ascii=False),
        "digest_research_depth": digest.get("recommended_research_depth", ""),
        "source_fingerprint": digest.get("source_fingerprint", ""),
        "derived_from_decision_digest_v1": (digest.get("derived_from_decision_digest") or {}).get("digest_path", ""),
    }


def accepted_decision_digest_for_apply(decision: dict[str, Any]) -> dict[str, Any] | None:
    accepted = decision.get("accepted_decision_digest")
    if not isinstance(accepted, dict):
        return None
    digest = accepted.get("decision_digest") if isinstance(accepted.get("decision_digest"), dict) else None
    digest_path = str(accepted.get("digest_path") or "").strip()
    if not digest and digest_path:
        path = Path(digest_path).expanduser()
        if path.exists() and path.is_file():
            digest = json.loads(path.read_text(encoding="utf-8"))
    if not digest:
        return None
    if digest.get("digest_version") != "decision_digest_v1":
        raise ValueError("accepted_decision_digest must reference decision_digest_v1")
    candidate_id = str(decision.get("candidate_id") or "")
    digest_candidate = str(digest.get("candidate_id") or accepted.get("candidate_id") or "")
    if candidate_id and digest_candidate and candidate_id != digest_candidate:
        raise ValueError(f"accepted_decision_digest candidate mismatch: {digest_candidate} != {candidate_id}")
    return {
        **accepted,
        "digest_version": accepted.get("digest_version") or digest.get("digest_version"),
        "decision_digest": digest,
    }


def write_source_digest_routing_event(topic_root: Path, intake_dir: Path, decision: dict[str, Any], digest_result: dict[str, Any]) -> None:
    digest = digest_result.get("digest") or {}
    selected_topic = str(decision.get("topic_id") or "")
    recommended_topic = str(digest.get("recommended_topic") or "")
    if not selected_topic or not recommended_topic or selected_topic == recommended_topic:
        return
    event = {
        "schema_version": "topic-routing-event.v1",
        "event_type": "source_digest_topic_routing",
        "created_at": now_iso(),
        "candidate_id": decision.get("candidate_id", ""),
        "source_fingerprint": digest.get("source_fingerprint", ""),
        "selected_topic": selected_topic,
        "recommended_topic": recommended_topic,
        "related_topics": digest.get("related_topics", []),
        "digest_path": digest_result.get("json_path", ""),
        "raw_article_path": digest.get("raw_article_path", ""),
        "reason": "source_digest_recommended_topic_differs_from_selected_topic",
    }
    append_jsonl(intake_dir / "topic_routing_events.jsonl", [event])
    append_jsonl(topic_root / "intake" / "topic_routing_events.jsonl", [event])


def diagnose_article_for_pre_kfc(title: str, markdown: str, topic_fit: dict[str, Any] | None = None) -> dict[str, Any]:
    text = f"{title}\n{plain_excerpt(markdown, 1600)}".lower()
    cjk_text = f"{title}\n{plain_excerpt(markdown, 1600)}"
    technical_terms = ["api", "github", "模型", "框架", "架构", "代码", "repo", "论文", "mcp", "agent", "llm", "数据库", "性能"]
    business_terms = ["价格", "成本", "收入", "利润", "市场", "投资", "财报", "公告", "套餐", "计费", "预算", "credits", "billing"]
    opinion_terms = ["认为", "意味着", "趋势", "不会", "必然", "正在", "应该", "可能", "危机", "失败", "取代"]
    financial_terms = ["股价", "融资", "估值", "营收", "现金流", "roi", "支出", "资本", "gdp", "财务"]
    tech_score = sum(1 for term in technical_terms if term in text)
    business_score = sum(1 for term in business_terms if term in text)
    opinion_score = sum(1 for term in opinion_terms if term in cjk_text.lower())
    financial_score = sum(1 for term in financial_terms if term in text)
    if financial_score >= 2:
        article_type = "financial"
    elif tech_score >= 2 and business_score >= 2:
        article_type = "mixed"
    elif tech_score >= 2:
        article_type = "technical"
    elif business_score >= 2:
        article_type = "business"
    elif opinion_score >= 2:
        article_type = "opinion"
    else:
        article_type = "unknown"
    claim_score = len(re.findall(r"\d+|宣布|确认|显示|证明|意味着|将于|已经|不会|必然|成本|价格|收入|模型|官方", cjk_text, re.I))
    claim_density = "high" if claim_score >= 8 else "medium" if claim_score >= 3 else "low"
    evidence_need_score = business_score + financial_score + min(claim_score, 6)
    evidence_need = "high" if evidence_need_score >= 8 else "medium" if evidence_need_score >= 3 else "low"
    fit_status = (topic_fit or {}).get("fit_level") or "unknown"
    if evidence_need == "low":
        recommended_research_depth = "none"
        recommended_action = "ingest_only"
    elif fit_status == "weak_fit":
        recommended_research_depth = "basic"
        recommended_action = "topic_migration_suggest"
    else:
        recommended_research_depth = "basic"
        recommended_action = "basic_research"
    return {
        "article_type": article_type,
        "claim_density": claim_density,
        "evidence_need": evidence_need,
        "topic_fit_status": fit_status,
        "topic_fit_score": (topic_fit or {}).get("fit_score", ""),
        "recommended_topic": ((topic_fit or {}).get("recommended_topics") or [{}])[0].get("topic_id", ""),
        "recommended_research_depth": recommended_research_depth,
        "recommended_action": recommended_action,
    }


@dataclass
class ProcessorContext:
    intake_dir: Path
    wiki_hub: Path
    clippings_root: Path
    archive_processed: bool = False
    execute: bool = True


def topic_root_for(decision: dict[str, Any], ctx: ProcessorContext) -> Path:
    topic_id = decision.get("topic_id") or ""
    if not topic_id:
        raise ValueError("wiki-bound decision requires topic_id")
    topic_root = (ctx.wiki_hub / "topics" / topic_id).resolve()
    if not topic_root.exists() or not topic_root.is_dir():
        raise ValueError(f"wiki topic does not exist: {topic_root}")
    return topic_root


def build_staging_target(decision: dict[str, Any], ctx: ProcessorContext) -> Path:
    topic_root = topic_root_for(decision, ctx)
    filename = f"{slugify(decision.get('title') or '', decision.get('candidate_id') or 'source')}-{decision.get('candidate_id')}.md"
    return topic_root / "raw" / "clippings" / filename


def build_ingest_target(decision: dict[str, Any], ctx: ProcessorContext) -> Path:
    topic_root = topic_root_for(decision, ctx)
    filename = f"{today_iso()}-{slugify(decision.get('title') or '', decision.get('candidate_id') or 'source')}-{decision.get('candidate_id')}.md"
    return topic_root / "raw" / "articles" / filename


def rewrite_markdown_assets(markdown: str, source_path: Path, assets_dir: Path, clippings_root: Path) -> tuple[str, list[dict[str, str]]]:
    copied_assets: list[dict[str, str]] = []
    rewrite_map: dict[str, str] = {}
    asset_ref_root = safe_filename(assets_dir.name)

    for ref in local_markdown_refs(markdown):
        asset_path = (source_path.parent / ref).resolve()
        if not asset_path.exists() or not asset_path.is_file():
            raise ValueError(f"referenced asset missing: {ref}")
        if not is_relative_to(asset_path, clippings_root):
            raise ValueError(f"referenced asset outside Clippings root: {asset_path}")
        target_asset = assets_dir / safe_filename(asset_path.name)
        rewrite_ref = f"assets/{asset_ref_root}/{target_asset.name}"
        rewrite_map[ref] = rewrite_ref
        rewrite_map[ref.replace(" ", "%20")] = rewrite_ref
        copied_assets.append({"source": str(asset_path), "target": str(target_asset), "ref": ref, "rewritten_ref": rewrite_ref})

    copied_markdown = markdown
    for old_ref, new_ref in sorted(rewrite_map.items(), key=lambda item: len(item[0]), reverse=True):
        copied_markdown = copied_markdown.replace(f"]({old_ref})", f"]({new_ref})")
        copied_markdown = copied_markdown.replace(f"[[{old_ref}]]", f"[[{new_ref}]]")
    return copied_markdown, copied_assets


def write_assets(copied_assets: list[dict[str, str]]) -> None:
    for asset in copied_assets:
        target_asset = Path(asset["target"])
        target_asset.parent.mkdir(parents=True, exist_ok=True)
        if not target_asset.exists():
            shutil.copy2(asset["source"], target_asset)


def ingest_frontmatter(decision: dict[str, Any], source_path: Path, markdown: str) -> str:
    metadata, body = parse_frontmatter(markdown)
    title = decision.get("title") or metadata.get("title") or source_path.stem
    source_url = decision.get("source_url") or metadata.get("source_url") or ""
    topic_id = decision.get("topic_id") or ""
    topic_display_name = decision.get("topic_display_name") or decision.get("topic_name") or topic_id
    tags = [topic_id] if topic_id else []
    lines = [
        "---",
        f"title: {yaml_string(title)}",
        f"source: {yaml_string(source_url or 'clippings-intake')}",
        "type: articles",
        f"ingested: {yaml_string(today_iso())}",
        f"tags: [{', '.join(tags)}]",
        f"topic_id: {yaml_string(topic_id)}",
        f"topic_display_name: {yaml_string(topic_display_name)}",
        f"summary: {yaml_string(plain_excerpt(markdown))}",
        f"original_path: {yaml_string(source_path)}",
        f"source_url: {yaml_string(source_url)}",
        f"archived_at: {yaml_string(metadata.get('archived_at', ''))}",
        "content_format: markdown",
        f"intake_candidate_id: {yaml_string(decision.get('candidate_id', ''))}",
        f"intake_decision_id: {yaml_string(decision.get('decision_id', ''))}",
        "intake_source_kind: obsidian_clipping",
        "compile_status: ready_to_compile",
        "compile_triggered: false",
        "---",
        "",
        f"# {title}",
        "",
        f"> Ingested from local Obsidian clipping. Original clipping path: `{source_path}`.",
        "",
    ]
    return "\n".join(lines) + body.lstrip()


def copy_wiki(decision: dict[str, Any], ctx: ProcessorContext) -> dict[str, Any]:
    if decision.get("gate1_destination") not in LLM_WIKI_DESTINATIONS or decision.get("decision_status") != "accepted":
        return {"requested": False, "status": "skipped"}

    source_path = Path(decision.get("source_file_path") or "").expanduser().resolve()
    clippings_root = ctx.clippings_root.resolve()
    if not source_path.exists() or not source_path.is_file():
        raise ValueError(f"source Markdown missing: {source_path}")
    if not is_relative_to(source_path, clippings_root):
        raise ValueError(f"source outside Clippings root: {source_path}")

    source_bytes = source_path.read_bytes()
    expected_hash = str(decision.get("content_hash") or "")
    if expected_hash.startswith("sha256:") and expected_hash.removeprefix("sha256:") != sha256_bytes(source_bytes):
        raise ValueError(f"content hash mismatch: {source_path}")

    markdown = source_bytes.decode("utf-8", errors="replace")
    staging_target = build_staging_target(decision, ctx)
    staging_assets_dir = staging_target.parent / "assets" / safe_filename(source_path.stem)
    staging_markdown, staging_assets = rewrite_markdown_assets(markdown, source_path, staging_assets_dir, clippings_root)

    ingest_target = build_ingest_target(decision, ctx)
    ingest_assets_dir = ingest_target.parent / "assets" / safe_filename(ingest_target.stem)
    ingest_body_markdown, ingest_assets = rewrite_markdown_assets(markdown, source_path, ingest_assets_dir, clippings_root)
    ingest_markdown = ingest_frontmatter(decision, source_path, ingest_body_markdown)

    if not ctx.execute:
        source_id = ingest_target.stem
        digest_json = topic_root_for(decision, ctx) / "digests" / "source_digest" / f"{source_id}.json"
        digest_md = topic_root_for(decision, ctx) / "digests" / "source_digest" / f"{source_id}.md"
        return {
            "requested": True,
            "status": "planned",
            "md_path": str(ingest_target),
            "digest": {
                "requested": True,
                "status": "planned",
                "json_path": str(digest_json),
                "md_path": str(digest_md),
            },
            "assets_copied": len(ingest_assets),
            "assets": ingest_assets,
            "staging_copy": {"requested": True, "status": "planned", "md_path": str(staging_target), "assets_copied": len(staging_assets), "assets": staging_assets},
            "ingest": {
                "requested": True,
                "status": "planned",
                "source_type": "articles",
                "path": str(ingest_target),
                "assets_copied": len(ingest_assets),
                "assets": ingest_assets,
                "compile_status": "planned",
                "compile_triggered": True,
            },
            "compile": {
                "requested": True,
                "status": "planned",
                "mode": "incremental",
                "trigger": "intake_apply",
                "language_policy": "preserve_source_language",
            },
        }

    staging_target.parent.mkdir(parents=True, exist_ok=True)
    write_assets(staging_assets)
    if staging_target.exists() and staging_target.read_text(encoding="utf-8", errors="replace") == staging_markdown:
        staging_status = "already_copied"
    else:
        staging_target.write_text(staging_markdown, encoding="utf-8")
        staging_status = "copied"

    ingest_target.parent.mkdir(parents=True, exist_ok=True)
    write_assets(ingest_assets)
    if ingest_target.exists() and ingest_target.read_text(encoding="utf-8", errors="replace") == ingest_markdown:
        ingest_status = "already_ingested"
    else:
        ingest_target.write_text(ingest_markdown, encoding="utf-8")
        ingest_status = "ingested"
    fingerprint = source_fingerprint(source_path, markdown, str(decision.get("candidate_id") or ""))
    topic_root = topic_root_for(decision, ctx)
    digest_result: dict[str, Any] | None = None
    digest_error = ""
    try:
        accepted_digest = accepted_decision_digest_for_apply(decision)
        digest_result = generate_source_digest(
            topic_root=topic_root,
            raw_article_path=ingest_target,
            candidate_id=str(decision.get("candidate_id") or ""),
            source_fingerprint=fingerprint,
            selected_topic=str(decision.get("topic_id") or ""),
            recommended_topic=str(decision.get("recommended_topic") or decision.get("topic") or decision.get("source_topic") or decision.get("topic_id") or ""),
            related_topics=related_topics_for_decision(decision),
            mode=os.environ.get("SOURCE_DIGEST_MODE", "auto"),
            accepted_decision_digest=accepted_digest,
        )
        write_source_digest_routing_event(topic_root, ctx.intake_dir, decision, digest_result)
    except Exception as exc:
        digest_error = str(exc)
    ingest_markdown_for_compile = ingest_target.read_text(encoding="utf-8", errors="replace")
    ingest_target.write_text(
        update_frontmatter(ingest_markdown_for_compile, digest_frontmatter_updates(digest_result, digest_error)),
        encoding="utf-8",
    )
    compile_result = incremental_compile(
        topic_root=topic_root,
        source_paths=[ingest_target],
        trigger="intake_apply",
        candidate_id=str(decision.get("candidate_id") or ""),
        intake_dir=ctx.intake_dir,
    )
    source_compile = (compile_result.get("source_results") or [{}])[0]
    compile_status = "compiled" if source_compile.get("status") == "compiled" else "compile_failed"
    topic_fit = source_compile.get("topic_fit") or {}
    article_diagnosis = diagnose_article_for_pre_kfc(str(decision.get("title") or ""), markdown, topic_fit)
    digest_payload = {
        "requested": True,
        "status": digest_result.get("status") if digest_result else "digest_failed",
        "json_path": digest_result.get("json_path") if digest_result else "",
        "md_path": digest_result.get("md_path") if digest_result else "",
        "error": digest_error,
        "recommended_topic": ((digest_result or {}).get("digest") or {}).get("recommended_topic", ""),
        "related_topics": ((digest_result or {}).get("digest") or {}).get("related_topics", []),
        "derived_from_decision_digest": ((digest_result or {}).get("digest") or {}).get("derived_from_decision_digest", {}),
    }
    return {
        "requested": True,
        "status": ingest_status,
        "md_path": str(ingest_target),
        "digest": digest_payload,
        "source_identity": {
            "candidate_id": decision.get("candidate_id", ""),
            "source_fingerprint": fingerprint,
            "original_path": str(source_path),
            "raw_article_path": str(ingest_target),
            "raw_source_id": ingest_target.stem,
            "digest_path": digest_payload.get("json_path", ""),
            "digest_markdown_path": digest_payload.get("md_path", ""),
            "title": decision.get("title", ""),
            "source_url": decision.get("source_url", ""),
            "topic_id": decision.get("topic_id", ""),
            "selected_topic": decision.get("topic_id", ""),
            "recommended_topic": digest_payload.get("recommended_topic", ""),
            "related_topics": digest_payload.get("related_topics", []),
            "topic_display_name": decision.get("topic_display_name") or decision.get("topic_name") or decision.get("topic_id", ""),
        },
        "article_diagnosis": article_diagnosis,
        "assets_copied": len(ingest_assets),
        "assets": ingest_assets,
        "staging_copy": {"requested": True, "status": staging_status, "md_path": str(staging_target), "assets_copied": len(staging_assets), "assets": staging_assets},
        "ingest": {
            "requested": True,
            "status": ingest_status,
            "source_type": "articles",
            "path": str(ingest_target),
            "assets_copied": len(ingest_assets),
            "assets": ingest_assets,
            "compile_status": compile_status,
            "compile_triggered": True,
            "compile_run_id": compile_result.get("run_id", ""),
            "compiled_at": compile_result.get("finished_at", ""),
            "compiled_page_path": source_compile.get("summary_path", ""),
            "compiled_page_relative_path": source_compile.get("summary_relative_path", ""),
            "compile_error": source_compile.get("error") or "",
        },
        "compile": compile_result,
    }


def enqueue_kfc(decision: dict[str, Any], ctx: ProcessorContext, wiki_result: dict[str, Any]) -> dict[str, Any]:
    if decision.get("gate1_destination") not in KFC_DESTINATIONS or not decision.get("gate2_promote_to_kfc"):
        return {"requested": False, "status": "skipped"}

    queue_id = f"kfcq_{safe_filename(str(decision.get('decision_id') or decision.get('candidate_id') or 'item'))}"
    queue_path = ctx.intake_dir / "kfc_queue" / f"{queue_id}.json"
    payload = {
        "schema_version": "kfc-intake-queue.v1",
        "tool_version": TOOL_VERSION,
        "queue_id": queue_id,
        "created_at": now_iso(),
        "source_path": decision.get("source_file_path", ""),
        "title": decision.get("title", ""),
        "topic_id": decision.get("topic_id", ""),
        "reason": decision.get("kfc_promotion_reason", ""),
        "priority": decision.get("kfc_priority") or "normal",
        "mode": decision.get("kfc_project_mode") or "graph_review_candidate",
        "wiki_copy_path": wiki_result.get("md_path", ""),
        "wiki_ingest_path": wiki_result.get("ingest", {}).get("path", ""),
        "decision_id": decision.get("decision_id", ""),
        "candidate_id": decision.get("candidate_id", ""),
        "status": "queued",
    }
    if not ctx.execute:
        return {"requested": True, "status": "planned", "queue_path": str(queue_path), "queue_id": queue_id}
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    status = "already_queued" if queue_path.exists() else "queued"
    queue_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"requested": True, "status": status, "queue_path": str(queue_path), "queue_id": queue_id}


def archive_source(decision: dict[str, Any], ctx: ProcessorContext, wiki_result: dict[str, Any], kfc_result: dict[str, Any]) -> dict[str, Any]:
    if not ctx.archive_processed:
        return {"requested": False, "status": "skipped"}
    requested_results = [item for item in (wiki_result, kfc_result) if item.get("requested")]
    if not requested_results:
        return {"requested": True, "status": "skipped_no_destination"}
    if wiki_result.get("requested") and wiki_result.get("compile", {}).get("status") not in {None, "", "planned", "succeeded", "partial"}:
        raise ValueError("cannot archive before wiki incremental compile succeeds")
    success_statuses = {"copied", "already_copied", "ingested", "already_ingested", "queued", "already_queued"}
    if any(item.get("status") not in success_statuses for item in requested_results):
        raise ValueError("cannot archive before all requested destinations succeed")

    source_path = Path(decision.get("source_file_path") or "").expanduser().resolve()
    if not source_path.exists():
        return {"requested": True, "status": "already_archived"}
    if not is_relative_to(source_path, ctx.clippings_root.resolve()):
        raise ValueError(f"source outside Clippings root: {source_path}")
    archive_root = ctx.clippings_root / "_processed" / datetime.now().strftime("%Y-%m")
    archive_path = unique_path(archive_root / source_path.name)
    if not ctx.execute:
        return {"requested": True, "status": "planned", "md_path": str(archive_path), "assets_moved": 0, "assets": []}

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(archive_path))
    manifest = {
        "schema_version": "processed-source.v1",
        "tool_version": TOOL_VERSION,
        "processed_at": now_iso(),
        "decision_id": decision.get("decision_id", ""),
        "candidate_id": decision.get("candidate_id", ""),
        "source_md_before": str(source_path),
        "source_md_after": str(archive_path),
        "assets_moved": [],
        "reversible": True,
    }
    return {"requested": True, "status": "moved", "md_path": str(archive_path), "assets_moved": 0, "manifest": manifest}


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def apply_decision(decision: dict[str, Any], ctx: ProcessorContext) -> dict[str, Any]:
    wiki = copy_wiki(decision, ctx)
    kfc = enqueue_kfc(decision, ctx, wiki)
    archive = archive_source(decision, ctx, wiki, kfc)
    result = {
        "schema_version": "intake-processing-result.v1",
        "tool_version": TOOL_VERSION,
        "processed_at": now_iso(),
        "decision_id": decision.get("decision_id", ""),
        "candidate_id": decision.get("candidate_id", ""),
        "source_path": decision.get("source_file_path", ""),
        "wiki": wiki,
        "kfc": kfc,
        "archive": archive,
        "side_effects": {
            "modified_obsidian_source": archive.get("status") == "moved",
            "copied_to_llm_wiki": wiki.get("status") in {"ingested", "already_ingested", "copied", "already_copied"},
            "created_kfc_project": False,
            "called_llm": False,
        },
    }
    if ctx.execute:
        append_jsonl(ctx.intake_dir / "processing_results.jsonl", [result])
        if archive.get("manifest"):
            append_jsonl(ctx.intake_dir / "processed_manifest.jsonl", [archive["manifest"]])
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply one Clippings intake decision.")
    parser.add_argument("--decision-json", required=True, help="Decision JSON string or path to a JSON file.")
    parser.add_argument("--intake-dir", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake"))
    parser.add_argument("--wiki-hub", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub"))
    parser.add_argument("--clippings-root", type=Path, default=Path("/Users/mac/Downloads/OB笔记/Clippings"))
    parser.add_argument("--archive-processed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def load_decision(value: str) -> dict[str, Any]:
    path = Path(value).expanduser()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ctx = ProcessorContext(
        intake_dir=args.intake_dir.expanduser().resolve(),
        wiki_hub=args.wiki_hub.expanduser().resolve(),
        clippings_root=args.clippings_root.expanduser().resolve(),
        archive_processed=args.archive_processed,
        execute=not args.dry_run,
    )
    result = apply_decision(load_decision(args.decision_json), ctx)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
