#!/usr/bin/env python3
"""Generate source-only digest artifacts for a raw article.

The digest is intentionally constrained to the raw Markdown and metadata that
already exist on disk. The optional Codex mode is available for local use, but
tests and failure fallback use the deterministic generator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIGEST_VERSION = "source_digest_v1"
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
PATH_RE = re.compile(r"(/Users/|/tmp/|\\\\|[A-Za-z]:\\\\)")
NOISY_CONCEPTS = {
    "为什么",
    "作者",
    "路径",
    "来源",
    "文章",
    "阅读",
    "图片",
    "markdown",
    "assets",
    "source",
    "http",
    "https",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_language(text: str) -> str:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk >= 20 and cjk >= latin // 2:
        return "zh-CN"
    return "en" if latin else "unknown"


def clean_markdown(markdown: str) -> str:
    _, body = parse_frontmatter(markdown)
    lines: list[str] = []
    in_code = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith("!"):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = line.strip("#>*- 　")
        if line and not PATH_RE.search(line):
            lines.append(line)
    return "\n".join(lines)


def sentence_units(text: str, limit: int = 24) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    chunks = re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+", normalized)
    units: list[str] = []
    for chunk in chunks:
        cleaned = sanitize_fact(chunk)
        if len(cleaned) < 10:
            continue
        units.append(cleaned[:260])
        if len(units) >= limit:
            break
    return units


def sanitize_fact(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip(" -_*#>　")
    value = re.sub(r"`[^`]*`", "", value)
    if PATH_RE.search(value):
        return ""
    return value[:320]


def first_items(items: list[str], count: int, fallback: str = "") -> list[str]:
    cleaned: list[str] = []
    for item in items:
        value = sanitize_fact(item)
        if value and value not in cleaned:
            cleaned.append(value)
        if len(cleaned) >= count:
            break
    if not cleaned and fallback:
        cleaned.append(fallback[:220])
    return cleaned


def concept_candidates(title: str, body_text: str, metadata: dict[str, str], limit: int = 10) -> list[str]:
    seed = "\n".join([title, metadata.get("summary", ""), body_text[:1800]])
    concepts: list[str] = []
    preferred = [
        "GitHub Copilot",
        "Claude Code",
        "AI Credits",
        "usage-based billing",
        "tokenization",
        "LLM pricing",
        "Agent Harness",
        "Codex",
        "KFC",
        "知识工作台",
        "按使用量计费",
        "中文税",
        "推理成本",
        "订阅制",
    ]
    lowered = seed.lower()
    for item in preferred:
        if item.lower() in lowered and item not in concepts:
            concepts.append(item)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}|[\u4e00-\u9fff]{2,10}", seed):
        cleaned = token.strip("-_.,;:，。；：、")
        lower = cleaned.lower()
        if len(cleaned) < 2 or lower in NOISY_CONCEPTS or cleaned in NOISY_CONCEPTS:
            continue
        if PATH_RE.search(cleaned) or cleaned not in concepts:
            if PATH_RE.search(cleaned):
                continue
            concepts.append(cleaned)
        if len(concepts) >= limit:
            break
    return concepts[:limit]


def normalize_related_topics(selected_topic: str, recommended_topic: str, related_topics: list[str]) -> list[str]:
    topics: list[str] = []
    for item in [selected_topic, recommended_topic, *related_topics]:
        value = str(item or "").strip()
        if value and value not in topics:
            topics.append(value)
    return topics


def deterministic_digest(
    raw_article_path: Path,
    candidate_id: str,
    source_fingerprint: str,
    selected_topic: str,
    recommended_topic: str = "",
    related_topics: list[str] | None = None,
) -> dict[str, Any]:
    markdown = raw_article_path.read_text(encoding="utf-8", errors="replace")
    metadata, _ = parse_frontmatter(markdown)
    body_text = clean_markdown(markdown)
    units = sentence_units(body_text)
    title = metadata.get("title") or raw_article_path.stem
    source_url = metadata.get("source_url") or metadata.get("source") or ""
    fallback = sanitize_fact(metadata.get("summary") or (units[0] if units else title))
    main_claim = fallback or title
    key_points = first_items(units[:6], 5, main_claim)
    mechanism_terms = r"因为|通过|机制|导致|成本|计费|token|usage|pricing|订阅|额度|推理|agent|workflow|pipeline|harness|工具"
    evidence_terms = r"\d|例如|比如|引用|援引|数据|报告|宣布|官方|价格|according|report|said|announced"
    mechanism = first_items([item for item in units if re.search(mechanism_terms, item, re.I)], 4, key_points[0])
    evidence = first_items([item for item in units if re.search(evidence_terms, item, re.I)], 4)
    if not evidence:
        evidence = ["原文未提供足够明确的可核验证据，需要后续 Research 补充来源。"]
    verification_gaps = [
        "需要后续 Research 验证原文关键说法是否有官方来源。",
        "需要检查是否存在反方证据或不同解释材料。",
    ]
    concepts = concept_candidates(title, body_text, metadata)
    resolved_recommended = recommended_topic or selected_topic
    related = normalize_related_topics(selected_topic, resolved_recommended, related_topics or [])
    topic_fit_status = "good_fit" if not resolved_recommended or resolved_recommended == selected_topic else "weak_fit"
    depth = "basic" if any(re.search(evidence_terms, item, re.I) for item in units) else "none"
    return validate_digest(
        {
            "digest_version": DIGEST_VERSION,
            "generated_at": now_iso(),
            "generator": "deterministic_source_only",
            "candidate_id": candidate_id,
            "source_fingerprint": source_fingerprint or sha256_text(markdown)[:16],
            "raw_article_path": str(raw_article_path),
            "title": title,
            "source_url": source_url,
            "source_language": metadata.get("language") or detect_language(markdown),
            "main_claim": main_claim,
            "key_points": key_points,
            "mechanism": mechanism,
            "evidence_in_source": evidence,
            "verification_gaps": verification_gaps,
            "candidate_concepts": concepts,
            "recommended_topic": resolved_recommended,
            "selected_topic": selected_topic,
            "related_topics": related,
            "topic_fit_status": topic_fit_status,
            "recommended_research_depth": depth,
            "quality_flags": ["source_only", "needs_primary_sources"],
        }
    )


def digest_from_decision_digest(
    raw_article_path: Path,
    candidate_id: str,
    source_fingerprint: str,
    selected_topic: str,
    accepted_decision_digest: dict[str, Any],
    recommended_topic: str = "",
    related_topics: list[str] | None = None,
) -> dict[str, Any]:
    markdown = raw_article_path.read_text(encoding="utf-8", errors="replace")
    metadata, _ = parse_frontmatter(markdown)
    decision_digest = accepted_decision_digest.get("decision_digest") if isinstance(accepted_decision_digest.get("decision_digest"), dict) else accepted_decision_digest
    if decision_digest.get("digest_version") != "decision_digest_v1":
        raise ValueError("accepted decision digest must be decision_digest_v1")
    if decision_digest.get("source_only") is False or decision_digest.get("web_research_used") is True or decision_digest.get("wiki_mutation") is True:
        raise ValueError("accepted decision digest violated source-only/no-mutation contract")
    decision_candidate = str(decision_digest.get("candidate_id") or accepted_decision_digest.get("candidate_id") or "")
    if decision_candidate and candidate_id and decision_candidate != candidate_id:
        raise ValueError(f"accepted decision digest candidate mismatch: {decision_candidate} != {candidate_id}")

    understanding = decision_digest.get("article_understanding") or {}
    topic = decision_digest.get("topic_recommendation") or {}
    scanner = decision_digest.get("scanner_signal") or {}
    resolved_recommended = topic.get("recommended_topic_id") or accepted_decision_digest.get("recommended_topic") or recommended_topic or selected_topic
    related = normalize_related_topics(
        selected_topic,
        str(resolved_recommended or ""),
        [
            scanner.get("primary_topic", ""),
            *(related_topics or []),
            *[item.get("topic_id", "") for item in topic.get("alternative_topics", []) if isinstance(item, dict)],
        ],
    )
    summary = sanitize_fact(understanding.get("summary") or accepted_decision_digest.get("summary") or metadata.get("summary") or raw_article_path.stem)
    key_points = understanding.get("key_points") if isinstance(understanding.get("key_points"), list) else []
    mechanisms = understanding.get("mechanisms") if isinstance(understanding.get("mechanisms"), list) else []
    evidence = understanding.get("evidence_in_source") if isinstance(understanding.get("evidence_in_source"), list) else []
    uncertainties = understanding.get("uncertainties") if isinstance(understanding.get("uncertainties"), list) else []
    concepts = understanding.get("important_entities") if isinstance(understanding.get("important_entities"), list) else []
    return validate_digest(
        {
            "digest_version": DIGEST_VERSION,
            "generated_at": now_iso(),
            "generator": "decision_digest_v1_derived_source_digest",
            "candidate_id": candidate_id,
            "source_fingerprint": source_fingerprint or sha256_text(markdown)[:16],
            "raw_article_path": str(raw_article_path),
            "title": decision_digest.get("source_title") or metadata.get("title") or raw_article_path.stem,
            "source_url": metadata.get("source_url") or metadata.get("source") or "",
            "source_language": decision_digest.get("source_language") or metadata.get("language") or detect_language(markdown),
            "main_claim": understanding.get("main_claim") or summary,
            "key_points": key_points or [summary],
            "mechanism": mechanisms or [topic.get("rationale") or summary],
            "evidence_in_source": evidence or ["原文没有提供明确可核验证据，后续 Research 可补充。"],
            "verification_gaps": uncertainties or ["这是由已采纳 decision_digest_v1 派生的 source_digest_v1，仍需后续 Research 做外部核验。"],
            "candidate_concepts": concepts or concept_candidates(str(metadata.get("title") or raw_article_path.stem), clean_markdown(markdown), metadata),
            "recommended_topic": str(resolved_recommended or ""),
            "selected_topic": selected_topic,
            "related_topics": related,
            "topic_fit_status": "good_fit" if not resolved_recommended or resolved_recommended == selected_topic else "weak_fit",
            "recommended_research_depth": (decision_digest.get("apply_recommendation") or {}).get("recommended_research_depth") or "basic",
            "quality_flags": ["source_only", "derived_from_decision_digest_v1", "needs_primary_sources"],
            "derived_from_decision_digest": {
                "digest_version": decision_digest.get("digest_version", ""),
                "digest_path": accepted_decision_digest.get("digest_path", ""),
                "digest_markdown_path": accepted_decision_digest.get("digest_markdown_path", ""),
                "generator": decision_digest.get("generator") or accepted_decision_digest.get("generator", ""),
                "source_fingerprint": decision_digest.get("source_fingerprint") or accepted_decision_digest.get("source_fingerprint", ""),
                "accepted_at": accepted_decision_digest.get("accepted_at", ""),
                "summary": summary,
                "rationale": topic.get("rationale") or accepted_decision_digest.get("rationale", ""),
            },
        }
    )


def validate_digest(digest: dict[str, Any]) -> dict[str, Any]:
    required = [
        "digest_version",
        "candidate_id",
        "source_fingerprint",
        "title",
        "source_url",
        "source_language",
        "main_claim",
        "key_points",
        "mechanism",
        "evidence_in_source",
        "verification_gaps",
        "candidate_concepts",
        "recommended_topic",
        "related_topics",
        "topic_fit_status",
        "recommended_research_depth",
        "quality_flags",
    ]
    missing = [key for key in required if key not in digest]
    if missing:
        raise ValueError(f"digest missing required fields: {', '.join(missing)}")
    digest["digest_version"] = DIGEST_VERSION
    digest["topic_fit_status"] = digest.get("topic_fit_status") if digest.get("topic_fit_status") in {"good_fit", "weak_fit"} else "weak_fit"
    digest["recommended_research_depth"] = digest.get("recommended_research_depth") if digest.get("recommended_research_depth") in {"none", "basic", "deep"} else "basic"
    for key in ["key_points", "mechanism", "evidence_in_source", "verification_gaps", "candidate_concepts", "related_topics", "quality_flags"]:
        value = digest.get(key)
        if not isinstance(value, list):
            digest[key] = [str(value)] if value else []
        digest[key] = [sanitize_fact(item) for item in digest[key] if sanitize_fact(item)]
    for key in ["main_claim", "title", "source_url", "source_language", "recommended_topic"]:
        digest[key] = sanitize_fact(str(digest.get(key) or ""))
    for key in ["main_claim", "key_points", "mechanism"]:
        values = digest[key] if isinstance(digest[key], list) else [digest[key]]
        if any(PATH_RE.search(str(item)) for item in values):
            raise ValueError(f"digest field contains local path: {key}")
    digest["candidate_concepts"] = [
        item for item in digest["candidate_concepts"]
        if item and item.lower() not in NOISY_CONCEPTS and item not in NOISY_CONCEPTS and not PATH_RE.search(item)
    ][:12]
    if "source_only" not in digest["quality_flags"]:
        digest["quality_flags"].insert(0, "source_only")
    return digest


def codex_digest(
    raw_article_path: Path,
    candidate_id: str,
    source_fingerprint: str,
    selected_topic: str,
    recommended_topic: str = "",
    related_topics: list[str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    markdown = raw_article_path.read_text(encoding="utf-8", errors="replace")
    metadata, _ = parse_frontmatter(markdown)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "digest_version",
            "candidate_id",
            "source_fingerprint",
            "title",
            "source_url",
            "source_language",
            "main_claim",
            "key_points",
            "mechanism",
            "evidence_in_source",
            "verification_gaps",
            "candidate_concepts",
            "recommended_topic",
            "related_topics",
            "topic_fit_status",
            "recommended_research_depth",
            "quality_flags",
        ],
        "properties": {
            "digest_version": {"type": "string"},
            "candidate_id": {"type": "string"},
            "source_fingerprint": {"type": "string"},
            "title": {"type": "string"},
            "source_url": {"type": "string"},
            "source_language": {"type": "string"},
            "main_claim": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "mechanism": {"type": "array", "items": {"type": "string"}},
            "evidence_in_source": {"type": "array", "items": {"type": "string"}},
            "verification_gaps": {"type": "array", "items": {"type": "string"}},
            "candidate_concepts": {"type": "array", "items": {"type": "string"}},
            "recommended_topic": {"type": "string"},
            "related_topics": {"type": "array", "items": {"type": "string"}},
            "topic_fit_status": {"type": "string", "enum": ["good_fit", "weak_fit"]},
            "recommended_research_depth": {"type": "string", "enum": ["none", "basic", "deep"]},
            "quality_flags": {"type": "array", "items": {"type": "string"}},
        },
    }
    prompt = f"""Read only the Markdown source below. Do not browse, do not verify externally, and do not use the file path as article evidence.

Generate a source-only digest JSON that follows the provided schema.

Context:
- candidate_id: {candidate_id}
- source_fingerprint: {source_fingerprint}
- selected_topic: {selected_topic}
- initial_recommended_topic: {recommended_topic or selected_topic}
- related_topics: {json.dumps(related_topics or [], ensure_ascii=False)}
- title metadata: {metadata.get('title', '')}
- source_url metadata: {metadata.get('source_url') or metadata.get('source') or ''}

Markdown:
<<<SOURCE_MARKDOWN
{markdown[:45000]}
SOURCE_MARKDOWN
"""
    with tempfile.TemporaryDirectory() as tmp:
        schema_path = Path(tmp) / "schema.json"
        out_path = Path(tmp) / "digest.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        result = subprocess.run(
            [
                "codex",
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--ask-for-approval",
                "never",
                "--output-schema",
                str(schema_path),
                "-o",
                str(out_path),
                "-",
            ],
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "codex digest failed").strip()[:1000])
        digest = json.loads(out_path.read_text(encoding="utf-8"))
    digest["generator"] = "codex_source_only"
    digest["generated_at"] = now_iso()
    digest["raw_article_path"] = str(raw_article_path)
    digest.setdefault("selected_topic", selected_topic)
    return validate_digest(digest)


def markdown_digest(digest: dict[str, Any]) -> str:
    derived = digest.get("derived_from_decision_digest") or {}
    lines = [
        "---",
        f"digest_version: {json.dumps(digest['digest_version'], ensure_ascii=False)}",
        f"candidate_id: {json.dumps(digest.get('candidate_id', ''), ensure_ascii=False)}",
        f"source_fingerprint: {json.dumps(digest.get('source_fingerprint', ''), ensure_ascii=False)}",
        f"source_url: {json.dumps(digest.get('source_url', ''), ensure_ascii=False)}",
        f"source_language: {json.dumps(digest.get('source_language', ''), ensure_ascii=False)}",
        f"recommended_topic: {json.dumps(digest.get('recommended_topic', ''), ensure_ascii=False)}",
        f"topic_fit_status: {json.dumps(digest.get('topic_fit_status', ''), ensure_ascii=False)}",
        f"derived_from_decision_digest_v1: {json.dumps(derived.get('digest_path', '') if derived else '', ensure_ascii=False)}",
        "---",
        "",
        f"# Source Digest: {digest.get('title') or digest.get('candidate_id')}",
        "",
        "> Source-only digest. No web search or external verification was performed.",
        "",
        "## 文章主张",
        "",
        digest.get("main_claim") or "暂无主张。",
        "",
        "## 关键观点",
        "",
    ]
    for key in ["key_points", "mechanism", "evidence_in_source", "verification_gaps", "candidate_concepts", "related_topics", "quality_flags"]:
        title = {
            "key_points": "关键观点",
            "mechanism": "机制解释",
            "evidence_in_source": "原文内证据",
            "verification_gaps": "待验证点",
            "candidate_concepts": "候选概念",
            "related_topics": "相关主题",
            "quality_flags": "质量标记",
        }[key]
        if key != "key_points":
            lines.extend(["", f"## {title}", ""])
        lines.extend([f"- {item}" for item in digest.get(key, [])] or ["- 暂无"])
    lines.extend(["", "## 推荐主题", "", f"- {digest.get('recommended_topic') or '-'}", f"- fit: {digest.get('topic_fit_status') or '-'}", f"- research depth: {digest.get('recommended_research_depth') or '-'}", ""])
    return "\n".join(lines)


def digest_paths(topic_root: Path, source_id: str) -> tuple[Path, Path]:
    digest_dir = topic_root / "digests" / "source_digest"
    return digest_dir / f"{source_id}.json", digest_dir / f"{source_id}.md"


def generate_source_digest(
    topic_root: Path,
    raw_article_path: Path,
    candidate_id: str = "",
    source_fingerprint: str = "",
    selected_topic: str = "",
    recommended_topic: str = "",
    related_topics: list[str] | None = None,
    mode: str = "auto",
    timeout_seconds: int = 120,
    accepted_decision_digest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if os.environ.get("SOURCE_DIGEST_FORCE_FAIL"):
        raise RuntimeError("SOURCE_DIGEST_FORCE_FAIL requested")
    raw_article_path = raw_article_path.expanduser().resolve()
    topic_root = topic_root.expanduser().resolve()
    source_id = raw_article_path.stem
    json_path, md_path = digest_paths(topic_root, source_id)
    mode = (mode or os.environ.get("SOURCE_DIGEST_MODE") or "auto").strip().lower()
    if accepted_decision_digest:
        digest = digest_from_decision_digest(raw_article_path, candidate_id, source_fingerprint, selected_topic, accepted_decision_digest, recommended_topic, related_topics)
    elif mode in {"codex", "llm"}:
        digest = codex_digest(raw_article_path, candidate_id, source_fingerprint, selected_topic, recommended_topic, related_topics, timeout_seconds)
    elif mode == "auto":
        try:
            digest = codex_digest(raw_article_path, candidate_id, source_fingerprint, selected_topic, recommended_topic, related_topics, timeout_seconds)
        except Exception:
            digest = deterministic_digest(raw_article_path, candidate_id, source_fingerprint, selected_topic, recommended_topic, related_topics)
    else:
        digest = deterministic_digest(raw_article_path, candidate_id, source_fingerprint, selected_topic, recommended_topic, related_topics)
    digest["source_id"] = source_id
    digest["digest_json_path"] = str(json_path)
    digest["digest_markdown_path"] = str(md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_digest(digest), encoding="utf-8")
    return {
        "status": "generated",
        "source_id": source_id,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "digest": digest,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a source-only digest for one raw article.")
    parser.add_argument("--topic-root", type=Path, required=True)
    parser.add_argument("--raw-article", type=Path, required=True)
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--source-fingerprint", default="")
    parser.add_argument("--selected-topic", default="")
    parser.add_argument("--recommended-topic", default="")
    parser.add_argument("--related-topic", action="append", default=[])
    parser.add_argument("--mode", default=os.environ.get("SOURCE_DIGEST_MODE", "auto"), choices=["deterministic", "codex", "llm", "auto"])
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = generate_source_digest(
        topic_root=args.topic_root,
        raw_article_path=args.raw_article,
        candidate_id=args.candidate_id,
        source_fingerprint=args.source_fingerprint,
        selected_topic=args.selected_topic,
        recommended_topic=args.recommended_topic,
        related_topics=args.related_topic,
        mode=args.mode,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
