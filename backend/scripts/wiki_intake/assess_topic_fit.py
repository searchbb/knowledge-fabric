#!/usr/bin/env python3
"""Deterministic topic-fit assessment for intake sources.

This keeps v1 topic routing explainable and testable. It does not create or
move topics automatically; it records whether the selected topic is a strong
home and suggests a better topic when the match is weak.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from incremental_compile_topic import parse_frontmatter, title_for


DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "ai-tokenization": {
        "display_name": "AI 分词与计费成本",
        "topic_keywords": [
            "token",
            "tokens",
            "tokenization",
            "tokenizer",
            "pricing",
            "inference cost",
            "llm pricing",
            "chinese token",
            "language efficiency",
        ],
        "concept_seeds": ["中文令牌成本", "分词器语言效率", "大模型定价"],
        "negative_scope": ["没有价格、token 或推理成本角度的泛 AI 编程工具新闻"],
    },
    "agent-harness": {
        "display_name": "Agent Harness 与工具编排",
        "topic_keywords": ["agent", "harness", "tool use", "workflow", "orchestration", "skill", "runtime"],
        "concept_seeds": ["Agent 运行时", "工具编排"],
        "negative_scope": ["泛产品定价新闻"],
    },
    "knowledge-workspace": {
        "display_name": "知识工作台",
        "topic_keywords": ["knowledge", "workspace", "research", "wiki", "notes", "insight", "clippings"],
        "concept_seeds": ["知识接收", "Research 工作台"],
        "negative_scope": ["孤立厂商定价新闻"],
    },
    "ai-devtools-economics": {
        "display_name": "AI 编程工具经济学",
        "topic_keywords": [
            "copilot",
            "claude code",
            "ai coding",
            "devtools",
            "usage-based billing",
            "ai credits",
            "agentic coding",
            "subscription",
            "pricing",
            "inference cost",
            "opus",
        ],
        "concept_seeds": ["AI 编程成本模型", "按使用量计费", "Agentic coding 经济性"],
        "negative_scope": ["不涉及价格或编程工具经济性的分词器内部机制"],
    },
    "agent-reasoning-behavior": {
        "display_name": "Agent 行为与推理机制",
        "topic_keywords": [
            "思维链",
            "推理式思考",
            "智能体式思考",
            "chain-of-thought",
            "cot",
            "reasoning",
            "agent behavior",
            "control",
            "行为边界",
            "控制感",
        ],
        "concept_seeds": ["Agent 推理表达", "行为边界", "用户控制感"],
        "negative_scope": ["只讨论工具编排、runtime harness 或任务流，不讨论推理表达和行为边界"],
    },
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "into",
    "今天",
    "一个",
    "我们",
    "他们",
    "几乎",
    "一起",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def ensure_topic_profile(topic_root: Path) -> dict[str, Any]:
    profile_path = topic_root / "topic_profile.json"
    default = DEFAULT_PROFILES.get(topic_root.name, {})
    profile = read_json(profile_path)
    if profile:
        default_display = default.get("display_name")
        if default_display and profile.get("display_name") != default_display:
            profile["display_name"] = default_display
            profile["updated_at"] = now_iso()
            write_json(profile_path, profile)
        return profile
    profile = {
        "schema_version": "topic-profile.v1",
        "topic_id": topic_root.name,
        "display_name": default.get("display_name", topic_root.name),
        "language_policy": "preserve_source_language",
        "topic_keywords": default.get("topic_keywords", [topic_root.name.replace("-", " ")]),
        "concept_seeds": default.get("concept_seeds", []),
        "negative_scope": default.get("negative_scope", []),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_json(profile_path, profile)
    return profile


def source_text(source_path: Path) -> tuple[dict[str, str], str, str]:
    markdown = source_path.read_text(encoding="utf-8", errors="replace")
    metadata, body = parse_frontmatter(markdown)
    title = title_for(metadata, body, source_path)
    text = "\n".join([title, metadata.get("summary", ""), body[:4000]])
    return metadata, title, text


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    hits = []
    for keyword in keywords:
        value = str(keyword).strip()
        if value and value.lower() in lowered and value not in hits:
            hits.append(value)
    return hits


def salient_terms(text: str, limit: int = 18) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}|[\u4e00-\u9fff]{2,8}", text):
        cleaned = token.strip("-_.,;:，。；：、").lower()
        if len(cleaned) < 2 or cleaned in STOPWORDS:
            continue
        if cleaned not in found:
            found.append(cleaned)
        if len(found) >= limit:
            break
    return found


def recommended_topic(source_body: str, selected_topic: str) -> dict[str, Any] | None:
    candidates = []
    for topic_id, profile in DEFAULT_PROFILES.items():
        if topic_id == selected_topic:
            continue
        hits = keyword_hits(source_body, list(profile.get("topic_keywords", [])))
        if hits:
            candidates.append(
                {
                    "topic_id": topic_id,
                    "display_name": profile.get("display_name", topic_id),
                    "score": min(0.95, 0.30 + len(hits) * 0.11),
                    "reason": f"命中 {', '.join(hits[:5])}",
                    "matched_keywords": hits,
                }
            )
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item["score"], reverse=True)[0]


def assess_topic_fit(topic_root: Path, source_path: Path, candidate_id: str = "", intake_dir: Path | None = None) -> dict[str, Any]:
    profile = ensure_topic_profile(topic_root)
    metadata, title, text = source_text(source_path)
    hits = keyword_hits(text, list(profile.get("topic_keywords", [])))
    terms = salient_terms(text)
    fit_score = min(0.95, 0.18 + len(hits) * 0.12)
    fit_level = "strong_fit" if fit_score >= 0.58 else "weak_fit" if fit_score >= 0.30 else "misfit"
    reasons = []
    if hits:
        reasons.append(f"当前主题命中关键词：{', '.join(hits[:6])}")
    else:
        reasons.append("当前主题关键词命中较少。")
    if fit_level != "strong_fit":
        reasons.append("该来源可以先保留为 intake source，但不应直接视为正式主题沉淀。")

    recommendation = recommended_topic(text, topic_root.name)
    recommended_topics = [recommendation] if recommendation else []
    if recommendation and recommendation["score"] > fit_score + 0.12:
        fit_level = "weak_fit" if fit_level == "strong_fit" else fit_level
        reasons.append(f"存在更强相关主题建议：{recommendation.get('display_name') or recommendation['topic_id']}。")

    proposal = recommendation or {
        "topic_id": re.sub(r"[^a-z0-9-]+", "-", "-".join(terms[:3])).strip("-") or f"{topic_root.name}-followup",
        "display_name": " / ".join(terms[:3]) or f"{topic_root.name} 后续主题",
        "score": 0.0,
        "reason": "根据来源高频词生成的新主题候选。",
        "matched_keywords": [],
    }
    event = {
        "schema_version": "topic-routing-event.v1",
        "event_type": "topic_fit_assessed",
        "candidate_id": candidate_id or metadata.get("intake_candidate_id", ""),
        "source_path": str(source_path),
        "source_relative_path": source_path.relative_to(topic_root).as_posix() if source_path.is_relative_to(topic_root) else "",
        "source_title": title,
        "selected_topic": topic_root.name,
        "selected_topic_display_name": profile.get("display_name", topic_root.name),
        "fit_level": fit_level,
        "fit_score": round(fit_score, 2),
        "matched_keywords": hits,
        "salient_terms": terms,
        "reasons": reasons,
        "recommended_topics": recommended_topics,
        "new_topic_proposal": {
            "topic_id": proposal["topic_id"],
            "display_name": proposal.get("display_name", proposal["topic_id"]),
            "reason": proposal.get("reason", ""),
        },
        "created_at": now_iso(),
    }
    append_jsonl(topic_root / "routing" / "recommendations.jsonl", event)
    if intake_dir:
        append_jsonl(intake_dir / "topic_routing_events.jsonl", event)
    return event


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assess whether a source strongly fits a topic.")
    parser.add_argument("--topic-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--intake-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = assess_topic_fit(
        topic_root=args.topic_root.expanduser().resolve(),
        source_path=args.source.expanduser().resolve(),
        candidate_id=args.candidate_id,
        intake_dir=args.intake_dir.expanduser().resolve() if args.intake_dir else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
