#!/usr/bin/env python3
"""Deterministic incremental wiki compile for the Clippings intake prototype.

This is intentionally conservative. It makes newly accepted raw sources visible
in the topic wiki without pretending to be the full llm-wiki compiler:
- create/update one intake summary page per raw source
- update wiki/_index.md with an idempotent recent-compile block
- mark raw sources as compiled or compile_failed
- append a compile_runs.jsonl audit record
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMPILER_VERSION = "prototype_incremental_v1"
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
ANCHOR_RE_TEMPLATE = r"<!-- intake-compile:{key}:start -->.*?<!-- intake-compile:{key}:end -->"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slugify(text: str, fallback: str = "source") -> str:
    value = text.lower()
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return (value[:90].strip("-") or fallback).strip("-") or fallback


def yaml_string(value: Any) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        return value
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        return value
    return yaml_string(value)


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


def update_frontmatter(markdown: str, updates: dict[str, Any]) -> str:
    metadata, body = parse_frontmatter(markdown)
    metadata.update({key: value for key, value in updates.items() if value is not None})
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {yaml_scalar(value)}")
    lines.extend(["---", ""])
    return "\n".join(lines) + body.lstrip()


def title_for(metadata: dict[str, str], body: str, path: Path) -> str:
    if metadata.get("title"):
        return metadata["title"]
    for match in HEADING_RE.finditer(body):
        if match.group(1) == "#":
            return match.group(2).strip()
    return path.stem


def body_lines(markdown: str) -> list[str]:
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
    return lines


def plain_excerpt(markdown: str, limit: int = 260) -> str:
    return " ".join(body_lines(markdown))[:limit]


def sentence_like_units(markdown: str, limit: int = 12) -> list[str]:
    text = " ".join(body_lines(markdown))
    chunks = re.split(r"(?<=[。！？!?])\s*|(?<=\.)\s+", text)
    units: list[str] = []
    for chunk in chunks:
        cleaned = chunk.strip()
        if len(cleaned) < 12:
            continue
        units.append(cleaned[:220])
        if len(units) >= limit:
            break
    return units


def structured_summary(markdown: str, metadata: dict[str, str]) -> dict[str, list[str]]:
    units = sentence_like_units(markdown)
    fallback = metadata.get("summary") or plain_excerpt(markdown, 220) or "暂无可提取内容。"
    facts = [item for item in units if re.search(r"\d|GitHub|Anthropic|Claude|Copilot|价格|计费|Credits|token|模型|订阅", item, re.I)]
    mechanisms = [item for item in units if re.search(r"成本|计费|token|usage|subscription|订阅|额度|推理|agent", item, re.I)]
    verification = [item for item in units if re.search(r"宣布|透露|援引|数据|报告|官方|博客|价格|限制", item, re.I)]
    return {
        "article_claims": [fallback[:220]],
        "key_facts": facts[:4] or units[:2] or [fallback[:220]],
        "cost_or_mechanism": mechanisms[:3] or facts[:2] or [fallback[:220]],
        "verification_gaps": verification[:3] or ["需要 Research 验证原始公告、价格页、官方说明和反方材料。"],
    }


def detect_language(text: str) -> str:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk >= 20 and cjk >= latin // 2:
        return "zh-CN"
    return "en" if latin else "unknown"


def headings(markdown: str, limit: int = 8) -> list[str]:
    _, body = parse_frontmatter(markdown)
    found: list[str] = []
    for match in HEADING_RE.finditer(body):
        text = match.group(2).strip()
        if text and text not in found:
            found.append(text)
        if len(found) >= limit:
            break
    return found


def candidate_concepts(title: str, markdown: str, metadata: dict[str, str], limit: int = 10) -> list[str]:
    text = "\n".join([title, metadata.get("summary", ""), "\n".join(headings(markdown, 12)), plain_excerpt(markdown, 600)])
    concepts: list[str] = []
    blocked = {
        "markdown", "image", "assets", "source", "http", "https", "today", "code",
        "今天", "几乎", "同时", "一起", "一个", "这个", "那个", "行业", "请回", "回来",
        "不如", "给行业", "踩了一脚刹", "一时间",
    }
    preferred = [
        "GitHub Copilot",
        "Claude Code",
        "AI Credits",
        "usage-based billing",
        "按使用量计费",
        "agentic coding",
        "AI 编程工具成本",
        "推理成本",
        "订阅制",
        "Opus",
        "Anthropic",
        "GitHub",
    ]
    lowered = text.lower()
    for item in preferred:
        if item.lower() in lowered and item not in concepts:
            concepts.append(item)
        if len(concepts) >= limit:
            return concepts
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}|[\u4e00-\u9fff]{2,8}", text):
        cleaned = token.strip("-_.,;:，。；：、")
        if len(cleaned) < 2:
            continue
        lower = cleaned.lower()
        if lower in blocked or cleaned in blocked:
            continue
        if cleaned not in concepts:
            concepts.append(cleaned)
        if len(concepts) >= limit:
            break
    return concepts


def research_questions(language: str) -> list[str]:
    if language == "zh-CN":
        return [
            "是否存在原始公告、价格页或官方说明可以验证文中关键事实？",
            "是否需要补充反方观点或不同厂商的对比数据？",
            "这个主题还缺哪些公开资料、论文、新闻或竞品信息？",
        ]
    return [
        "Which primary sources verify the key claims in this clipping?",
        "What opposing evidence or comparable vendor data should be added?",
        "What public reports, papers, news, or competitor references are missing?",
    ]


def source_key(path: Path, metadata: dict[str, str]) -> str:
    return metadata.get("intake_candidate_id") or slugify(path.stem, "source")


def source_relative(topic_root: Path, path: Path) -> str:
    return path.resolve().relative_to(topic_root.resolve()).as_posix()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def json_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item or "").strip()]


def load_source_digest(topic_root: Path, source_path: Path, metadata: dict[str, str]) -> dict[str, Any] | None:
    candidates: list[Path] = []
    if metadata.get("digest_json_path"):
        candidates.append(Path(metadata["digest_json_path"]).expanduser())
    candidates.append(topic_root / "digests" / "source_digest" / f"{source_path.stem}.json")
    topic_root_resolved = topic_root.resolve()
    for candidate in candidates:
        path = candidate.resolve()
        if not path.exists() or not path.is_file() or not is_relative_to(path, topic_root_resolved):
            continue
        try:
            digest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if digest.get("digest_version") == "source_digest_v1":
            digest["_digest_path"] = str(path)
            digest["_digest_relative_path"] = source_relative(topic_root, path)
            return digest
        if digest.get("digest_version") == "verified_digest_v1":
            raw_result: dict[str, Any] = {}
            result_path = Path(str(digest.get("raw_auto_intake_result_path") or "")).expanduser()
            if result_path.exists() and result_path.is_file():
                try:
                    raw_result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    raw_result = {}
            source_digest = raw_result.get("source_digest") or {}
            verification = raw_result.get("verification") or {}
            mechanism = str(source_digest.get("mechanism_summary") or "").strip()
            verified_facts = verification.get("verified_facts") or []
            uncertain = verification.get("uncertain_claims") or digest.get("research_gaps") or []
            normalized = {
                "digest_version": "verified_digest_v1",
                "source_language": "zh-CN",
                "main_claim": source_digest.get("main_claim") or digest.get("verified_summary") or digest.get("source_summary") or "",
                "key_points": source_digest.get("key_points") or ([digest.get("source_summary")] if digest.get("source_summary") else []),
                "mechanism": [mechanism] if mechanism else [],
                "evidence_in_source": [
                    str(item.get("fact") if isinstance(item, dict) else item)
                    for item in verified_facts
                    if str(item.get("fact") if isinstance(item, dict) else item).strip()
                ],
                "verification_gaps": [
                    (f"{item.get('claim', '')}：{item.get('reason', '')}".strip("：") if isinstance(item, dict) else str(item))
                    for item in uncertain
                    if str(item).strip()
                ],
                "candidate_concepts": source_digest.get("core_concepts") or digest.get("core_concepts") or [],
                "recommended_topic": digest.get("topic", ""),
                "related_topics": [],
                "_digest_path": str(path),
                "_digest_relative_path": source_relative(topic_root, path),
            }
            return normalized
    return None


def digest_summary(digest: dict[str, Any] | None, markdown: str, metadata: dict[str, str]) -> dict[str, Any]:
    if digest:
        key_points = [str(item) for item in digest.get("key_points", []) if str(item).strip()]
        mechanism = [str(item) for item in digest.get("mechanism", []) if str(item).strip()]
        evidence = [str(item) for item in digest.get("evidence_in_source", []) if str(item).strip()]
        gaps = [str(item) for item in digest.get("verification_gaps", []) if str(item).strip()]
        return {
            "mode": digest.get("digest_version") or "source_digest_v1",
            "article_claims": [str(digest.get("main_claim") or "暂无可提取主张。")],
            "key_points": key_points or ["暂无可提取关键观点。"],
            "mechanism": mechanism or ["原文未明确说明机制。"],
            "evidence_in_source": evidence or ["原文未提供明确证据。"],
            "verification_gaps": gaps or ["需要后续 Research 验证关键说法。"],
        }
    fallback = structured_summary(markdown, metadata)
    return {
        "mode": "deterministic_fallback",
        "article_claims": fallback["article_claims"],
        "key_points": fallback["key_facts"],
        "mechanism": fallback["cost_or_mechanism"],
        "evidence_in_source": ["deterministic fallback 未单独提取原文内证据。"],
        "verification_gaps": fallback["verification_gaps"],
    }


def research_artifacts_for_source(topic_root: Path, metadata: dict[str, str]) -> dict[str, str]:
    if metadata.get("source_origin") != "wiki_research_task" and metadata.get("source_type") != "wiki_research":
        return {}
    task_id = metadata.get("research_task_id", "").strip()
    if not task_id:
        return {}
    output_dir = topic_root / "research" / "output" / task_id
    artifacts = {
        "research_report": output_dir / "research_report.md",
        "sources": output_dir / "sources.json",
        "evidence": output_dir / "evidence.json",
        "processor_notes": output_dir / "processor_notes.md",
    }
    return {name: source_relative(topic_root, path) for name, path in artifacts.items() if path.exists()}


def write_summary_page(topic_root: Path, source_path: Path, metadata: dict[str, str], markdown: str, run_id: str, topic_fit: dict[str, Any] | None = None) -> dict[str, Any]:
    _, body = parse_frontmatter(markdown)
    title = title_for(metadata, body, source_path)
    digest = load_source_digest(topic_root, source_path, metadata)
    language = (digest or {}).get("source_language") or metadata.get("language") or detect_language(markdown)
    slug = slugify(f"{source_path.stem}-{source_key(source_path, metadata)}", "source")
    page_path = topic_root / "wiki" / "intake" / f"{slug}.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    source_rel = source_relative(topic_root, source_path)
    summary = (digest or {}).get("main_claim") or metadata.get("summary") or plain_excerpt(markdown)
    structured = digest_summary(digest, markdown, metadata)
    concepts = [str(item) for item in (digest or {}).get("candidate_concepts", []) if str(item).strip()] or candidate_concepts(title, markdown, metadata)
    structure = headings(markdown)
    questions = research_questions(language)
    recommended_topic = (digest or {}).get("recommended_topic") or (topic_fit.get("recommended_topics") or [{}])[0].get("topic_id", "") if topic_fit else (digest or {}).get("recommended_topic", "")
    related_topics = (digest or {}).get("related_topics") or json_list(metadata.get("digest_related_topics", ""))
    research_artifacts = research_artifacts_for_source(topic_root, metadata)

    page_lines = [
        "---",
        f"title: {yaml_string(title)}",
        "type: intake-summary",
        f"source: {yaml_string(source_rel)}",
        f"source_url: {yaml_string(metadata.get('source_url') or metadata.get('source') or '')}",
        f"language: {yaml_string(language)}",
        "language_policy: preserve_source_language",
        f"compiled_at: {yaml_string(now_iso())}",
        f"compile_run_id: {yaml_string(run_id)}",
        f"compiler_version: {yaml_string(COMPILER_VERSION)}",
        f"digest_version: {yaml_string((digest or {}).get('digest_version', 'deterministic_fallback'))}",
        f"digest_source: {yaml_string(structured['mode'])}",
        f"digest_json: {yaml_string((digest or {}).get('_digest_relative_path', ''))}",
        "---",
        "",
        f"# {title}",
        "",
        f"> 来源：[{source_rel}](../../{source_rel})",
        "> 编译方式：prototype incremental compile",
        f"> 初步消化：{structured['mode']}",
        "> 语言策略：保留原文语言，不自动翻译",
    ]
    if research_artifacts:
        artifact_links = []
        if research_artifacts.get("research_report"):
            artifact_links.append(f"[完整报告](../../{research_artifacts['research_report']})")
        if research_artifacts.get("sources"):
            artifact_links.append(f"[来源 JSON](../../{research_artifacts['sources']})")
        if research_artifacts.get("evidence"):
            artifact_links.append(f"[证据 JSON](../../{research_artifacts['evidence']})")
        if research_artifacts.get("processor_notes"):
            artifact_links.append(f"[执行说明](../../{research_artifacts['processor_notes']})")
        page_lines.append("> Research 产物：" + " · ".join(artifact_links))
    page_lines.extend(["", "## 摘要", "", "### 文章主张", ""])
    page_lines.extend([f"- {item}" for item in structured["article_claims"]])
    page_lines.extend(["", "### 关键观点", ""])
    page_lines.extend([f"- {item}" for item in structured["key_points"]])
    page_lines.extend(["", "### 机制解释", ""])
    page_lines.extend([f"- {item}" for item in structured["mechanism"]])
    page_lines.extend(["", "### 原文内证据", ""])
    page_lines.extend([f"- {item}" for item in structured["evidence_in_source"]])
    page_lines.extend(["", "### 待验证点", ""])
    page_lines.extend([f"- {item}" for item in structured["verification_gaps"]])
    page_lines.extend(["", "## 主题匹配", ""])
    if recommended_topic:
        page_lines.append(f"- Digest 推荐主题：{recommended_topic}")
    if related_topics:
        page_lines.append(f"- Digest 相关主题：{'、'.join(related_topics)}")
    if topic_fit:
        page_lines.extend(
            [
                f"- 匹配状态：{topic_fit.get('fit_level', 'not_assessed')}",
                f"- 匹配分：{topic_fit.get('fit_score', '-')}",
            ]
        )
        page_lines.extend([f"- 理由：{item}" for item in topic_fit.get("reasons", [])])
        recommendations = topic_fit.get("recommended_topics") or []
        if recommendations:
            page_lines.append(f"- 建议强相关主题：{recommendations[0].get('display_name') or recommendations[0].get('topic_id')}（{recommendations[0].get('reason', '')}）")
        else:
            page_lines.append("- 建议强相关主题：无")
    else:
        page_lines.append("- 匹配状态：not_assessed")
    page_lines.extend(["", "## 候选概念", ""])
    page_lines.extend([f"- {item}" for item in concepts] or ["- 暂无候选概念"])
    page_lines.extend(["", "## 原文结构", ""])
    page_lines.extend([f"- {item}" for item in structure] or ["- 未检测到显式标题结构"])
    page_lines.extend(["", "## 后续 Research 建议", ""])
    page_lines.extend([f"- {item}" for item in questions])
    page_lines.append("")
    page_path.write_text("\n".join(page_lines), encoding="utf-8")
    return {
        "path": str(page_path),
        "relative_path": source_relative(topic_root, page_path),
        "title": title,
        "language": language,
        "summary": summary,
        "structured_summary": structured,
        "concepts": concepts,
        "recommended_topic": recommended_topic,
        "related_topics": related_topics,
        "digest": digest or {},
        "digest_source": structured["mode"],
        "research_artifacts": research_artifacts,
        "research_questions": questions,
        "topic_fit": topic_fit or {},
    }


def index_block(source_key_value: str, page: dict[str, Any], source_rel: str, run_id: str) -> str:
    concepts = "、".join(page.get("concepts") or []) or "暂无候选概念"
    topic_fit = page.get("topic_fit") or {}
    recommendations = topic_fit.get("recommended_topics") or []
    fit_line = f"- 主题匹配：{topic_fit.get('fit_level', 'not_assessed')} · {topic_fit.get('fit_score', '-')}"
    if recommendations:
        fit_line += f"；建议强相关主题：{recommendations[0].get('display_name') or recommendations[0].get('topic_id')}"
    digest_line = f"- 初步消化：{page.get('digest_source') or 'deterministic_fallback'}"
    if page.get("recommended_topic"):
        digest_line += f"；推荐主题：{page.get('recommended_topic')}"
    research_artifacts = page.get("research_artifacts") or {}
    artifact_lines = []
    if research_artifacts.get("research_report"):
        artifact_lines.append(f"- Research 完整报告：[{research_artifacts['research_report']}](../{research_artifacts['research_report']})")
    evidence_links = []
    if research_artifacts.get("sources"):
        evidence_links.append(f"[sources.json](../{research_artifacts['sources']})")
    if research_artifacts.get("evidence"):
        evidence_links.append(f"[evidence.json](../{research_artifacts['evidence']})")
    if evidence_links:
        artifact_lines.append("- Research 证据：" + " · ".join(evidence_links))
    return "\n".join(
        [
            f"<!-- intake-compile:{source_key_value}:start -->",
            f"### {page['title']}",
            "",
            f"- 语言：{page.get('language') or 'unknown'}",
            "- 语言策略：保留原文语言，不自动翻译",
            f"- 来源：[{source_rel}](../{source_rel})",
            f"- 编译页：[{page['relative_path']}](../{page['relative_path']})",
            f"- 摘要：{page.get('summary') or '暂无可提取摘要。'}",
            digest_line,
            *artifact_lines,
            f"- 候选概念：{concepts}",
            fit_line,
            f"- 编译运行：{run_id}",
            "- 后续 Research：如需验证事实、补原始来源或反方观点，请手动发起 Research 增强。",
            f"<!-- intake-compile:{source_key_value}:end -->",
        ]
    )


def update_wiki_index(topic_root: Path, source_key_value: str, page: dict[str, Any], source_rel: str, run_id: str) -> str:
    index_path = topic_root / "wiki" / "_index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8", errors="replace")
    else:
        text = f"# {topic_root.name} Wiki\n\n> Incrementally compiled wiki pages maintained from raw sources.\n"

    block = index_block(source_key_value, page, source_rel, run_id)
    pattern = re.compile(ANCHOR_RE_TEMPLATE.format(key=re.escape(source_key_value)), re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(block, text)
    else:
        section = "## 最近增量编译"
        if section not in text:
            text = text.rstrip() + f"\n\n{section}\n\n"
        text = text.rstrip() + "\n\n" + block + "\n"

    if re.search(r"^Last compiled: .*$", text, flags=re.MULTILINE):
        text = re.sub(r"^Last compiled: .*$", f"Last compiled: {today_iso()}", text, flags=re.MULTILINE)
    elif re.search(r"^Last updated: .*$", text, flags=re.MULTILINE):
        text = re.sub(r"^Last updated: .*$", f"Last updated: {today_iso()}\nLast compiled: {today_iso()}", text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + f"\n\nLast compiled: {today_iso()}\n"

    index_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return str(index_path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def compile_source(topic_root: Path, source_path: Path, run_id: str, candidate_id: str = "", intake_dir: Path | None = None) -> dict[str, Any]:
    raw_markdown = source_path.read_text(encoding="utf-8", errors="replace")
    metadata, _ = parse_frontmatter(raw_markdown)
    key = source_key(source_path, metadata)
    source_hash = sha256_text(raw_markdown)
    try:
        from assess_topic_fit import assess_topic_fit

        topic_fit = assess_topic_fit(topic_root, source_path, candidate_id or metadata.get("intake_candidate_id", ""), intake_dir)
    except Exception as exc:
        topic_fit = {"fit_level": "not_assessed", "fit_score": 0, "reasons": [f"topic fit assessment failed: {exc}"], "recommended_topics": []}
    page = write_summary_page(topic_root, source_path, metadata, raw_markdown, run_id, topic_fit)
    source_rel = source_relative(topic_root, source_path)
    index_path = update_wiki_index(topic_root, key, page, source_rel, run_id)
    compiled_at = now_iso()
    updated_raw = update_frontmatter(
        raw_markdown,
        {
            "compile_status": "compiled",
            "compile_triggered": True,
            "compile_run_id": run_id,
            "compiled_at": compiled_at,
            "compiler_version": COMPILER_VERSION,
            "compile_error": "",
            "source_hash": f"sha256:{source_hash}",
            "language": page["language"],
            "language_policy": "preserve_source_language",
            "topic_fit_status": topic_fit.get("fit_level", "not_assessed"),
            "topic_fit_score": topic_fit.get("fit_score", ""),
            "topic_fit_recommended": (topic_fit.get("recommended_topics") or [{}])[0].get("topic_id", ""),
            "digest_status": metadata.get("digest_status", ""),
            "digest_version": metadata.get("digest_version", ""),
            "digest_json_path": metadata.get("digest_json_path", ""),
            "digest_markdown_path": metadata.get("digest_markdown_path", ""),
        },
    )
    source_path.write_text(updated_raw, encoding="utf-8")
    return {
        "raw_path": str(source_path),
        "raw_relative_path": source_rel,
        "status": "compiled",
        "source_hash": f"sha256:{source_hash}",
        "language": page["language"],
        "summary_path": page["path"],
        "summary_relative_path": page["relative_path"],
        "index_path": index_path,
        "title": page["title"],
        "digest_source": page.get("digest_source", ""),
        "digest_path": (page.get("digest") or {}).get("_digest_path", ""),
        "digest_recommended_topic": page.get("recommended_topic", ""),
        "digest_related_topics": page.get("related_topics", []),
        "topic_fit": topic_fit,
        "error": None,
    }


def mark_compile_failed(source_path: Path, run_id: str, error: str) -> None:
    try:
        markdown = source_path.read_text(encoding="utf-8", errors="replace")
        source_path.write_text(
            update_frontmatter(
                markdown,
                {
                    "compile_status": "compile_failed",
                    "compile_triggered": True,
                    "compile_run_id": run_id,
                    "compiled_at": "",
                    "compiler_version": COMPILER_VERSION,
                    "compile_error": error[:500],
                },
            ),
            encoding="utf-8",
        )
    except OSError:
        return


def incremental_compile(topic_root: Path, source_paths: list[Path], trigger: str = "intake_apply", candidate_id: str = "", intake_dir: Path | None = None) -> dict[str, Any]:
    started_at = now_iso()
    seed = "|".join(str(path) for path in source_paths) + started_at
    run_id = f"compile_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_{sha256_text(seed)[:10]}"
    results: list[dict[str, Any]] = []
    updated_files: list[str] = []

    for source_path in source_paths:
        try:
            result = compile_source(topic_root, source_path.resolve(), run_id, candidate_id, intake_dir)
            results.append(result)
            updated_files.extend([result["summary_path"], result["index_path"], result["raw_path"]])
        except Exception as exc:  # keep raw ingest durable and expose compile failure
            error = str(exc)
            mark_compile_failed(source_path, run_id, error)
            results.append(
                {
                    "raw_path": str(source_path),
                    "status": "compile_failed",
                    "source_hash": "",
                    "language": "unknown",
                    "summary_path": "",
                    "summary_relative_path": "",
                    "index_path": "",
                    "title": source_path.stem,
                    "error": error,
                }
            )

    compiled = [item for item in results if item.get("status") == "compiled"]
    failed = [item for item in results if item.get("status") != "compiled"]
    status = "succeeded" if compiled and not failed else "failed" if failed and not compiled else "partial"
    finished_at = now_iso()
    run = {
        "schema_version": "topic-compile-run.v1",
        "run_id": run_id,
        "topic_id": topic_root.name,
        "topic_path": str(topic_root),
        "status": status,
        "mode": "incremental",
        "trigger": trigger,
        "candidate_id": candidate_id,
        "source_count": len(source_paths),
        "compiled_source_count": len(compiled),
        "failed_source_count": len(failed),
        "updated_files": sorted(set(updated_files)),
        "source_results": results,
        "warnings": [
            "language_policy=preserve_source_language; this prototype compiler does not auto-translate sources.",
            "prototype_incremental_v1 creates conservative intake summaries; run manual Research for evidence gaps.",
        ],
        "started_at": started_at,
        "finished_at": finished_at,
        "compiler_version": COMPILER_VERSION,
    }
    try:
        from generate_wiki_navigation import generate_wiki_navigation

        wiki_hub = topic_root.parent.parent if topic_root.parent.name == "topics" else topic_root.parent
        navigation = generate_wiki_navigation(wiki_hub)
        run["wiki_navigation"] = navigation
        updated_files.extend(navigation.get("written_files", []))
        run["updated_files"] = sorted(set(updated_files))
    except Exception as exc:
        run.setdefault("warnings", []).append(f"wiki navigation refresh failed: {exc}")
    append_jsonl(topic_root / "compile_runs.jsonl", run)
    return run


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incrementally compile topic raw sources into visible wiki pages.")
    parser.add_argument("--topic-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--intake-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = incremental_compile(
        topic_root=args.topic_root.expanduser().resolve(),
        source_paths=[path.expanduser().resolve() for path in args.source],
        trigger=args.trigger,
        candidate_id=args.candidate_id,
        intake_dir=args.intake_dir.expanduser().resolve() if args.intake_dir else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"succeeded", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
