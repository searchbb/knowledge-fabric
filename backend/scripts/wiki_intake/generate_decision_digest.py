#!/usr/bin/env python3
"""Generate a source-only pre-Apply decision digest for one candidate.

Unlike source_digest_v1, this artifact lives under the intake area and never
mutates topic raw/articles. It helps the user choose a final topic before Apply.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assess_topic_fit import DEFAULT_PROFILES
from generate_source_digest import (
    PATH_RE,
    clean_markdown,
    detect_language,
    parse_frontmatter,
    sanitize_fact,
    sentence_units,
    sha256_text,
)
from scan_clippings import TOPIC_RULES


DIGEST_VERSION = "decision_digest_v1"


def codex_executable() -> str:
    configured = os.environ.get("CODEX_BIN", "").strip()
    if configured:
        if Path(configured).exists():
            return configured
        raise FileNotFoundError(f"configured CODEX_BIN does not exist: {configured}")
    candidates = [
        shutil.which("codex") or "",
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("codex executable not found; set CODEX_BIN or install codex in PATH")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_record_by_candidate(intake_dir: Path, candidate_id: str) -> dict[str, Any]:
    for record in read_jsonl(intake_dir / "manifest.jsonl"):
        if record.get("source_id") == candidate_id:
            return record
    raise FileNotFoundError(f"candidate not found: {candidate_id}")


def digest_paths(intake_dir: Path, candidate_id: str) -> tuple[Path, Path]:
    root = intake_dir / "pre_digest"
    return root / f"{candidate_id}.decision_digest.json", root / f"{candidate_id}.decision_digest.md"


def source_fingerprint(record: dict[str, Any], markdown: str) -> str:
    content_hash = str(record.get("content_hash") or "")
    if content_hash:
        return content_hash
    return f"sha256:{sha256_text(markdown)}"


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for keyword in keywords:
        value = str(keyword).strip()
        if value and value.lower() in lowered and value not in hits:
            hits.append(value)
    return hits


def scanner_signal(record: dict[str, Any], title: str, body_text: str) -> dict[str, Any]:
    haystack = f"{title}\n{body_text[:4000]}"
    guessed = record.get("guessed_topics") or []
    enriched = []
    for guess in guessed:
        topic_id = str(guess.get("topic_id") or "")
        keywords = next((items for topic, items in TOPIC_RULES if topic == topic_id), [])
        enriched.append(
            {
                "topic_id": topic_id,
                "score": guess.get("score", 0),
                "matched_terms": keyword_hits(haystack, list(keywords)),
            }
        )
    return {
        "primary_topic": (enriched[0] or {}).get("topic_id", "") if enriched else "",
        "guessed_topics": enriched,
    }


def profile_score(text: str, topic_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    hits = keyword_hits(text, list(profile.get("topic_keywords", [])))
    score = min(0.98, 0.18 + len(hits) * 0.13)
    return {
        "topic_id": topic_id,
        "topic_label": profile.get("display_name", topic_id),
        "score": round(score, 2),
        "matched_keywords": hits,
        "reason": f"命中 {', '.join(hits[:6])}" if hits else "关键词命中较少",
    }


def topic_recommendation(text: str, scanner: dict[str, Any]) -> dict[str, Any]:
    lowered = text.lower()
    profile_scores = [profile_score(text, topic_id, profile) for topic_id, profile in DEFAULT_PROFILES.items()]
    profile_scores.sort(key=lambda item: item["score"], reverse=True)
    best = profile_scores[0] if profile_scores else {"topic_id": scanner.get("primary_topic", ""), "topic_label": scanner.get("primary_topic", ""), "score": 0.0, "matched_keywords": []}

    if re.search(r"思维链|推理式思考|智能体式思考|chain[- ]?of[- ]?thought|cot|控制感|行为边界", text, re.I):
        recommended = {
            "recommended_topic_id": "agent-reasoning-behavior",
            "recommended_topic_label": "Agent 行为与推理机制",
            "confidence": "medium",
            "fit_status": "new_topic_recommended",
            "rationale": "文章重点讨论 Agent 的思维链表达、推理方式、行为边界和用户控制感，现有 agent-harness 更偏工程编排。",
            "alternative_topics": [
                {
                    "topic_id": "agent-harness",
                    "topic_label": DEFAULT_PROFILES["agent-harness"]["display_name"],
                    "fit": "medium",
                    "reason": "文章涉及 Agent，但核心不是工具编排或 runtime harness。",
                }
            ],
            "new_topic_proposal": {
                "topic_id": "agent-reasoning-behavior",
                "topic_label": "Agent 行为与推理机制",
                "reason": "用于承载 Agent 推理表达、行为模式、控制感和交互边界材料。",
            },
        }
    elif any(term in lowered for term in ["copilot", "claude code", "ai credits", "usage-based billing", "agentic coding"]):
        recommended = {
            "recommended_topic_id": "ai-devtools-economics",
            "recommended_topic_label": DEFAULT_PROFILES["ai-devtools-economics"]["display_name"],
            "confidence": "high",
            "fit_status": "strong_fit",
            "rationale": "文章围绕 AI 编程工具、Copilot/Claude Code、用量计费、credits 和成本模型，强于泛 tokenization 分类。",
            "alternative_topics": [
                {
                    "topic_id": "ai-tokenization",
                    "topic_label": DEFAULT_PROFILES["ai-tokenization"]["display_name"],
                    "fit": "medium",
                    "reason": "涉及 token/计费，但不是分词机制或语言 token 效率本身。",
                }
            ],
            "new_topic_proposal": None,
        }
    else:
        confidence = "high" if best.get("score", 0) >= 0.55 else "medium" if best.get("score", 0) >= 0.35 else "low"
        recommended = {
            "recommended_topic_id": best.get("topic_id", ""),
            "recommended_topic_label": best.get("topic_label", ""),
            "confidence": confidence,
            "fit_status": "strong_fit" if confidence == "high" else "weak_fit" if confidence == "medium" else "needs_user_choice",
            "rationale": best.get("reason", "根据源文内容与本地 topic profile 做 source-only 匹配。"),
            "alternative_topics": [
                {
                    "topic_id": item["topic_id"],
                    "topic_label": item["topic_label"],
                    "fit": "medium" if item["score"] >= 0.35 else "low",
                    "reason": item["reason"],
                }
                for item in profile_scores[1:4]
                if item["matched_keywords"]
            ],
            "new_topic_proposal": None,
        }

    scanner_topic = scanner.get("primary_topic", "")
    recommended["scanner_topic_id"] = scanner_topic
    recommended["scanner_differs"] = bool(scanner_topic and scanner_topic != recommended.get("recommended_topic_id"))
    return recommended


def article_understanding(markdown: str, metadata: dict[str, str], title: str) -> dict[str, Any]:
    text = clean_markdown(markdown)
    units = sentence_units(text, 24)
    fallback = sanitize_fact(metadata.get("summary") or (units[0] if units else title))
    mechanism_terms = r"因为|通过|机制|导致|成本|计费|token|推理|思维链|智能体|agent|workflow|工具|控制|边界"
    evidence_terms = r"\d|例如|比如|引用|援引|数据|报告|宣布|官方|价格|限制|截图|博客|according|report|said|announced"
    entities: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}|[\u4e00-\u9fff]{2,10}", "\n".join([title, text[:1600]])):
        cleaned = token.strip("-_.,;:，。；：、")
        if cleaned and cleaned not in entities and not PATH_RE.search(cleaned):
            entities.append(cleaned)
        if len(entities) >= 12:
            break
    article_type = "technical_analysis" if re.search(r"机制|架构|系统|模型|agent|token|workflow", text, re.I) else "news_commentary" if re.search(r"宣布|今天|涨价|限制|发布", text, re.I) else "opinion"
    return {
        "article_type": article_type,
        "summary": fallback,
        "main_claim": fallback,
        "key_points": [item for item in units[:5] if item] or [fallback],
        "important_entities": entities,
        "mechanisms": [item for item in units if re.search(mechanism_terms, item, re.I)][:4] or [fallback],
        "evidence_in_source": [item for item in units if re.search(evidence_terms, item, re.I)][:4] or ["原文没有提供明确可核验证据，后续 Research 可补充。"],
        "uncertainties": [
            "这是 Apply 前的 source-only 理解，未做外部事实核验。",
            "如需验证官方来源、反方证据或补充材料，应在 Apply 后运行 Research。",
        ],
    }


def apply_recommendation(topic: dict[str, Any], understanding: dict[str, Any]) -> dict[str, Any]:
    depth = "basic"
    if topic.get("confidence") == "low" or topic.get("fit_status") == "needs_user_choice":
        destination = "needs_review"
    elif topic.get("recommended_topic_id") in {"agent-reasoning-behavior", "ai-devtools-economics"}:
        destination = "llm_wiki_and_kfc"
    else:
        destination = "llm_wiki_only"
    return {
        "default_destination": destination,
        "recommended_research_depth": depth,
        "reason": "建议先进入 wiki，并在 Apply 后排队基础 Research；KFC 由用户按长期价值决定。",
        "should_queue_basic_research_after_apply": True,
    }


def validate_digest(digest: dict[str, Any]) -> dict[str, Any]:
    required = ["digest_version", "candidate_id", "source_fingerprint", "source_only", "web_research_used", "wiki_mutation", "scanner_signal", "article_understanding", "topic_recommendation", "apply_recommendation"]
    missing = [key for key in required if key not in digest]
    if missing:
        raise ValueError(f"decision digest missing required fields: {', '.join(missing)}")
    if digest["digest_version"] != DIGEST_VERSION:
        raise ValueError("invalid decision digest version")
    if digest["source_only"] is not True or digest["web_research_used"] is not False or digest["wiki_mutation"] is not False:
        raise ValueError("decision digest violated source-only/no-mutation contract")
    fields = [
        digest.get("article_understanding", {}).get("summary", ""),
        digest.get("article_understanding", {}).get("main_claim", ""),
        digest.get("topic_recommendation", {}).get("rationale", ""),
    ]
    if any(PATH_RE.search(str(item)) for item in fields):
        raise ValueError("decision digest contains local path in semantic fields")
    return digest


def deterministic_digest(record: dict[str, Any], source_path: Path, markdown: str) -> dict[str, Any]:
    metadata, body = parse_frontmatter(markdown)
    title = record.get("title") or metadata.get("title") or source_path.stem
    text = clean_markdown(markdown)
    scanner = scanner_signal(record, title, text)
    understanding = article_understanding(markdown, metadata, title)
    recommendation = topic_recommendation("\n".join([title, text]), scanner)
    return validate_digest(
        {
            "digest_version": DIGEST_VERSION,
            "candidate_id": record.get("source_id", ""),
            "created_at": now_iso(),
            "source_path": str(source_path),
            "source_fingerprint": source_fingerprint(record, markdown),
            "source_title": title,
            "source_language": detect_language(markdown),
            "source_only": True,
            "web_research_used": False,
            "wiki_mutation": False,
            "generator": "deterministic_decision_digest",
            "scanner_signal": scanner,
            "article_understanding": understanding,
            "topic_recommendation": recommendation,
            "apply_recommendation": apply_recommendation(recommendation, understanding),
        }
    )


def codex_digest(record: dict[str, Any], source_path: Path, markdown: str, timeout_seconds: int = 120) -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    topic_option_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["topic_id", "topic_label", "fit", "reason"],
        "properties": {
            "topic_id": {"type": "string"},
            "topic_label": {"type": "string"},
            "fit": {"type": "string"},
            "reason": {"type": "string"},
        },
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["digest_version", "candidate_id", "source_fingerprint", "source_title", "source_language", "source_only", "web_research_used", "wiki_mutation", "scanner_signal", "article_understanding", "topic_recommendation", "apply_recommendation"],
        "properties": {
            "digest_version": {"type": "string"},
            "candidate_id": {"type": "string"},
            "source_fingerprint": {"type": "string"},
            "source_title": {"type": "string"},
            "source_language": {"type": "string"},
            "source_only": {"type": "boolean"},
            "web_research_used": {"type": "boolean"},
            "wiki_mutation": {"type": "boolean"},
            "scanner_signal": {
                "type": "object",
                "additionalProperties": False,
                "required": ["primary_topic", "guessed_topics"],
                "properties": {
                    "primary_topic": {"type": "string"},
                    "guessed_topics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["topic_id", "score", "matched_terms"],
                            "properties": {
                                "topic_id": {"type": "string"},
                                "score": {"type": "number"},
                                "matched_terms": string_array,
                            },
                        },
                    },
                },
            },
            "article_understanding": {
                "type": "object",
                "additionalProperties": False,
                "required": ["article_type", "summary", "main_claim", "key_points", "important_entities", "mechanisms", "evidence_in_source", "uncertainties"],
                "properties": {
                    "article_type": {"type": "string"},
                    "summary": {"type": "string"},
                    "main_claim": {"type": "string"},
                    "key_points": string_array,
                    "important_entities": string_array,
                    "mechanisms": string_array,
                    "evidence_in_source": string_array,
                    "uncertainties": string_array,
                },
            },
            "topic_recommendation": {
                "type": "object",
                "additionalProperties": False,
                "required": ["scanner_topic_id", "recommended_topic_id", "recommended_topic_label", "confidence", "fit_status", "rationale", "alternative_topics", "scanner_differs", "new_topic_proposal"],
                "properties": {
                    "scanner_topic_id": {"type": "string"},
                    "recommended_topic_id": {"type": "string"},
                    "recommended_topic_label": {"type": "string"},
                    "confidence": {"type": "string"},
                    "fit_status": {"type": "string"},
                    "rationale": {"type": "string"},
                    "alternative_topics": {"type": "array", "items": topic_option_schema},
                    "scanner_differs": {"type": "boolean"},
                    "new_topic_proposal": {
                        "anyOf": [
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["topic_id", "topic_label", "reason"],
                                "properties": {
                                    "topic_id": {"type": "string"},
                                    "topic_label": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                            },
                            {"type": "null"},
                        ]
                    },
                },
            },
            "apply_recommendation": {
                "type": "object",
                "additionalProperties": False,
                "required": ["default_destination", "recommended_research_depth", "reason", "should_queue_basic_research_after_apply"],
                "properties": {
                    "default_destination": {"type": "string"},
                    "recommended_research_depth": {"type": "string"},
                    "reason": {"type": "string"},
                    "should_queue_basic_research_after_apply": {"type": "boolean"},
                },
            },
        },
    }
    prompt = f"""Read only this source Markdown and generate a pre-Apply decision_digest_v1 JSON.
Do not browse the web. Do not verify externally. Do not write wiki artifacts. Do not treat local paths as article facts.

Candidate metadata:
{json.dumps({k: record.get(k) for k in ['source_id','title','source_url','guessed_topics','content_hash']}, ensure_ascii=False)}

Known topic profiles:
{json.dumps({k: {'display_name': v.get('display_name'), 'topic_keywords': v.get('topic_keywords'), 'negative_scope': v.get('negative_scope')} for k, v in DEFAULT_PROFILES.items()}, ensure_ascii=False)}

If the article is better served by a new topic, propose it in topic_recommendation.new_topic_proposal.

Markdown:
<<<SOURCE
{markdown[:45000]}
SOURCE
"""
    with tempfile.TemporaryDirectory() as tmp:
        schema_path = Path(tmp) / "schema.json"
        out_path = Path(tmp) / "digest.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        result = subprocess.run(
            [
                codex_executable(),
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
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
            raise RuntimeError((result.stderr or result.stdout or "codex decision digest failed").strip()[:1000])
        digest = json.loads(out_path.read_text(encoding="utf-8"))
    digest["created_at"] = now_iso()
    digest["source_path"] = str(source_path)
    digest["generator"] = "codex_decision_digest"
    digest["candidate_id"] = record.get("source_id", digest.get("candidate_id", ""))
    digest["source_fingerprint"] = source_fingerprint(record, markdown)
    return validate_digest(digest)


def markdown_digest(digest: dict[str, Any]) -> str:
    understanding = digest.get("article_understanding", {})
    topic = digest.get("topic_recommendation", {})
    scanner = digest.get("scanner_signal", {})
    lines = [
        "---",
        f"digest_version: {DIGEST_VERSION}",
        f"candidate_id: {json.dumps(digest.get('candidate_id', ''), ensure_ascii=False)}",
        f"source_fingerprint: {json.dumps(digest.get('source_fingerprint', ''), ensure_ascii=False)}",
        f"recommended_topic: {json.dumps(topic.get('recommended_topic_id', ''), ensure_ascii=False)}",
        f"scanner_topic: {json.dumps(scanner.get('primary_topic', ''), ensure_ascii=False)}",
        "source_only: true",
        "web_research_used: false",
        "wiki_mutation: false",
        "---",
        "",
        f"# Decision Digest: {digest.get('source_title') or digest.get('candidate_id')}",
        "",
        "## Source-only Summary",
        "",
        understanding.get("summary", ""),
        "",
        "## Topic Recommendation",
        "",
        f"- 规则初猜：{scanner.get('primary_topic') or '-'}",
        f"- AI 源文推荐：{topic.get('recommended_topic_label') or topic.get('recommended_topic_id') or '-'}",
        f"- 置信度：{topic.get('confidence') or '-'}",
        f"- 理由：{topic.get('rationale') or '-'}",
        "",
        "## Key Points",
        "",
    ]
    lines.extend([f"- {item}" for item in understanding.get("key_points", [])] or ["- 暂无"])
    lines.extend(["", "## User Decision Guidance", "", f"- {digest.get('apply_recommendation', {}).get('reason', '')}", ""])
    return "\n".join(lines)


def cached_digest(intake_dir: Path, candidate_id: str, fingerprint: str) -> dict[str, Any] | None:
    json_path, md_path = digest_paths(intake_dir, candidate_id)
    if not json_path.exists():
        return None
    try:
        digest = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if digest.get("digest_version") != DIGEST_VERSION:
        return None
    digest["_json_path"] = str(json_path)
    digest["_markdown_path"] = str(md_path)
    digest["_cache_status"] = "fresh" if digest.get("source_fingerprint") == fingerprint else "stale"
    return digest


def generate_decision_digest(intake_dir: Path, candidate_id: str, mode: str = "auto", force: bool = False, timeout_seconds: int = 300) -> dict[str, Any]:
    if os.environ.get("DECISION_DIGEST_FORCE_FAIL"):
        raise RuntimeError("DECISION_DIGEST_FORCE_FAIL requested")
    intake_dir = intake_dir.expanduser().resolve()
    record = manifest_record_by_candidate(intake_dir, candidate_id)
    source_path = Path(record.get("source_file_path", "")).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"source file missing: {source_path}")
    markdown = source_path.read_text(encoding="utf-8", errors="replace")
    fingerprint = source_fingerprint(record, markdown)
    existing = cached_digest(intake_dir, candidate_id, fingerprint)
    if not force:
        if existing and existing.get("_cache_status") == "fresh":
            return {"status": "cached", "json_path": existing["_json_path"], "md_path": existing["_markdown_path"], "digest": existing}
    mode = (mode or os.environ.get("DECISION_DIGEST_MODE") or "auto").strip().lower()
    if mode in {"codex", "llm"}:
        digest = codex_digest(record, source_path, markdown, timeout_seconds)
    elif mode == "auto":
        try:
            digest = codex_digest(record, source_path, markdown, timeout_seconds)
        except Exception as exc:
            if existing and existing.get("_cache_status") == "fresh" and existing.get("generator") == "codex_decision_digest":
                existing["_last_generation_status"] = "codex_failed_kept_cached"
                existing["_last_generation_error"] = str(exc)[:500]
                return {
                    "status": "codex_failed_kept_cached",
                    "json_path": existing["_json_path"],
                    "md_path": existing["_markdown_path"],
                    "digest": existing,
                    "error": str(exc)[:500],
                }
            digest = deterministic_digest(record, source_path, markdown)
            digest["generator"] = "deterministic_decision_digest_fallback"
            digest["fallback_reason"] = str(exc)[:500]
    else:
        digest = deterministic_digest(record, source_path, markdown)
    json_path, md_path = digest_paths(intake_dir, candidate_id)
    digest["_json_path"] = str(json_path)
    digest["_markdown_path"] = str(md_path)
    digest["_cache_status"] = "fresh"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_digest(digest), encoding="utf-8")
    return {"status": "generated", "json_path": str(json_path), "md_path": str(md_path), "digest": digest}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pre-Apply decision digest for a candidate.")
    parser.add_argument("--intake-dir", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake"))
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--mode", default=os.environ.get("DECISION_DIGEST_MODE", "auto"), choices=["auto", "deterministic", "codex", "llm"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = generate_decision_digest(args.intake_dir, args.candidate_id, args.mode, args.force, args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
