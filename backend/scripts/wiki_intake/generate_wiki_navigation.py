#!/usr/bin/env python3
"""Build a derived hub-level navigation layer for the local llm-wiki.

The topic wikis remain the source of truth. This script scans their compiled
intake pages and raw frontmatter, then writes a lightweight navigation cache:

- wiki/index.md
- wiki/topics/{topic_id}.md
- wiki/governance.md
- wiki/_data/wiki_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
LIST_VALUE_RE = re.compile(r"\[(.*)\]\s*$")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(markdown)
    if not match:
        return {}, markdown
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("'\"")
        metadata[key.strip()] = value
    return metadata, markdown[match.end():]


def markdown_title(path: Path, fallback: str = "") -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fallback or path.stem
    metadata, body = parse_frontmatter(text)
    if metadata.get("title"):
        return metadata["title"]
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback or path.stem
    return fallback or path.stem


def yaml_list(value: str) -> list[str]:
    if not value:
        return []
    match = LIST_VALUE_RE.match(value)
    if not match:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item or "").strip()]


def bullets_after_heading(markdown: str, heading: str, limit: int = 12) -> list[str]:
    lines = markdown.splitlines()
    start = -1
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start < 0:
        return []
    items: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#") and items:
            break
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        if len(items) >= limit:
            break
    return items


def first_bullet_after_heading(markdown: str, heading: str) -> str:
    values = bullets_after_heading(markdown, heading, 1)
    return values[0] if values else ""


def source_key_from_raw(path: Path, metadata: dict[str, str]) -> str:
    return metadata.get("intake_candidate_id") or metadata.get("job_id") or path.stem


def latest_compile_results(topic_root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in read_jsonl(topic_root / "compile_runs.jsonl"):
        stamp = str(run.get("finished_at") or run.get("started_at") or "")
        for result in run.get("source_results", []):
            raw_path = str(result.get("raw_path") or "")
            if not raw_path:
                continue
            current = latest.get(raw_path)
            current_stamp = str(current.get("_stamp") or "") if current else ""
            if current is None or stamp >= current_stamp:
                item = dict(result)
                item["_stamp"] = stamp
                latest[raw_path] = item
    return latest


def topic_profile(topic_root: Path) -> dict[str, Any]:
    profile = read_json(topic_root / "topic_profile.json")
    return {
        "topic_id": profile.get("topic_id") or topic_root.name,
        "title": profile.get("display_name") or profile.get("title") or topic_root.name,
        "description": (profile.get("routing_decision") or {}).get("resolved_topic_label") or "",
        "updated_at": profile.get("updated_at") or profile.get("created_at") or "",
        "status": profile.get("status") or "active",
    }


def article_from_raw(topic_root: Path, raw_path: Path, compile_results: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    try:
        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    metadata, _ = parse_frontmatter(raw_text)
    raw_resolved = str(raw_path.resolve())
    result = compile_results.get(raw_resolved) or compile_results.get(str(raw_path))
    compiled_rel = str((result or {}).get("summary_relative_path") or metadata.get("compiled_page_relative_path") or "")
    compiled_abs = str((result or {}).get("summary_path") or "")
    compiled_path = topic_root / compiled_rel if compiled_rel else (Path(compiled_abs) if compiled_abs else Path())
    compiled_text = ""
    if str(compiled_path) and compiled_path.exists() and compiled_path.is_file():
        compiled_text = compiled_path.read_text(encoding="utf-8", errors="replace")

    digest_path_value = metadata.get("digest_json_path") or ""
    digest_path = Path(digest_path_value) if digest_path_value else Path()
    if digest_path_value and not digest_path.is_absolute():
        digest_path = topic_root / digest_path
    digest = read_json(digest_path) if digest_path_value and digest_path.exists() and digest_path.is_file() else {}
    source_digest = {}
    raw_result_path = Path(str(digest.get("raw_auto_intake_result_path") or ""))
    if raw_result_path.exists():
        source_digest = read_json(raw_result_path).get("source_digest") or {}

    title = metadata.get("title") or (result or {}).get("title") or markdown_title(raw_path)
    summary = (
        source_digest.get("one_sentence_summary")
        or digest.get("verified_summary")
        or digest.get("source_summary")
        or first_bullet_after_heading(compiled_text, "### 文章主张")
        or metadata.get("summary")
        or ""
    )
    concepts = (
        source_digest.get("core_concepts")
        or digest.get("core_concepts")
        or bullets_after_heading(compiled_text, "## 候选概念", 16)
        or yaml_list(metadata.get("candidate_concepts", ""))
    )
    if not isinstance(concepts, list):
        concepts = []

    topic_fit_status = metadata.get("topic_fit_status") or ((result or {}).get("topic_fit") or {}).get("fit_level", "")
    topic_fit_recommended = metadata.get("topic_fit_recommended") or (
        (((result or {}).get("topic_fit") or {}).get("recommended_topics") or [{}])[0].get("topic_id", "")
    )
    compiled_rel = compiled_rel or (compiled_path.relative_to(topic_root).as_posix() if str(compiled_path) and compiled_path.exists() and compiled_path.is_file() else "")
    return {
        "job_id": metadata.get("intake_candidate_id") or metadata.get("job_id") or "",
        "source_id": source_key_from_raw(raw_path, metadata),
        "title": title,
        "summary": summary,
        "concepts": [str(item) for item in concepts if str(item or "").strip()][:16],
        "source_path": raw_path.relative_to(topic_root).as_posix(),
        "source_absolute_path": str(raw_path),
        "compiled_path": compiled_rel,
        "compiled_absolute_path": str(compiled_path) if str(compiled_path) and compiled_path.exists() and compiled_path.is_file() else "",
        "status": metadata.get("compile_status") or "raw",
        "last_updated": metadata.get("compiled_at") or metadata.get("updated_at") or metadata.get("archived_at") or "",
        "source_url": metadata.get("source_url") or metadata.get("source") or digest.get("original_source_url") or "",
        "digest_version": metadata.get("digest_version") or digest.get("digest_version") or "",
        "digest_json_path": metadata.get("digest_json_path") or (str(digest_path) if digest_path_value and digest_path.exists() and digest_path.is_file() else ""),
        "topic_fit_status": topic_fit_status,
        "topic_fit_score": metadata.get("topic_fit_score") or str(((result or {}).get("topic_fit") or {}).get("fit_score", "")),
        "topic_fit_recommended": topic_fit_recommended,
        "kfc_candidate": str(digest.get("recommended_next_action") or "").lower() in {"formal_research", "kfc_research"},
    }


def quick_entries(articles: list[dict[str, Any]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    patterns = [
        ("整体架构", ["架构", "系统", "工作台", "知识系统"]),
        ("代码库第二大脑", ["Graphify", "second brain", "代码"]),
        ("本体/语义地图", ["本体", "语义地图", "ontology", "ArchiCG"]),
        ("数据语义层", ["NL2SQL", "SemanticDB", "语义层", "LogicForm"]),
        ("向量检索基础设施", ["pgvector", "RaBitQ", "向量", "RAG"]),
    ]
    for intent, keywords in patterns:
        for article in articles:
            haystack = " ".join([article.get("title", ""), " ".join(article.get("concepts") or [])])
            if any(keyword.lower() in haystack.lower() for keyword in keywords):
                key = f"{intent}:{article.get('source_id')}"
                if key not in seen:
                    entries.append({"intent": intent, "title": article.get("title", ""), "compiled_path": article.get("compiled_path", "")})
                    seen.add(key)
                break
    for article in articles[:5]:
        key = f"代表文章:{article.get('source_id')}"
        if key not in seen:
            entries.append({"intent": "代表文章", "title": article.get("title", ""), "compiled_path": article.get("compiled_path", "")})
            seen.add(key)
    return entries[:8]


def governance_items(manifest_topics: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    items = {"misfit": [], "topic_conflicts": [], "uncategorized": [], "kfc_candidates": []}
    for topic in manifest_topics:
        for article in topic.get("articles", []):
            enriched = {"topic_id": topic["topic_id"], "topic_title": topic["title"], **article}
            fit = str(article.get("topic_fit_status") or "")
            recommended = str(article.get("topic_fit_recommended") or "")
            if fit == "misfit":
                items["misfit"].append(enriched)
            if recommended and recommended != topic["topic_id"]:
                items["topic_conflicts"].append(enriched)
            if not topic["topic_id"] or topic["topic_id"] == "uncategorized":
                items["uncategorized"].append(enriched)
            if article.get("kfc_candidate"):
                items["kfc_candidates"].append(enriched)
    for key in items:
        items[key] = sorted(items[key], key=lambda item: item.get("last_updated") or "", reverse=True)[:50]
    return items


def build_manifest(wiki_hub: Path) -> dict[str, Any]:
    topics_dir = wiki_hub / "topics"
    manifest_topics: list[dict[str, Any]] = []
    if not topics_dir.exists():
        return {"schema_version": "wiki-navigation-manifest.v1", "generated_at": now_iso(), "topics": [], "governance": {}}
    for topic_root in sorted(path for path in topics_dir.iterdir() if path.is_dir()):
        raw_articles = topic_root / "raw" / "articles"
        if not raw_articles.exists():
            continue
        profile = topic_profile(topic_root)
        compile_results = latest_compile_results(topic_root)
        articles = [
            article
            for article in (article_from_raw(topic_root, path, compile_results) for path in sorted(raw_articles.glob("*.md")))
            if article
        ]
        if not articles:
            continue
        concept_counts = Counter(concept for article in articles for concept in article.get("concepts", []))
        last_updated = max((article.get("last_updated") or "" for article in articles), default=profile["updated_at"])
        manifest_topics.append(
            {
                "topic_id": profile["topic_id"],
                "title": profile["title"],
                "definition": profile["description"] or f"{profile['title']} 主题收纳相关来源的 source-only 预消化、概念索引和后续 Research 入口。",
                "article_count": len(articles),
                "last_updated": last_updated[:10] if last_updated else "",
                "concepts": [item for item, _ in concept_counts.most_common(12)],
                "articles": sorted(articles, key=lambda item: item.get("last_updated") or "", reverse=True),
                "quick_entries": quick_entries(sorted(articles, key=lambda item: item.get("last_updated") or "", reverse=True)),
            }
        )
    manifest_topics.sort(key=lambda item: (item["article_count"], item.get("last_updated") or ""), reverse=True)
    governance = governance_items(manifest_topics)
    return {
        "schema_version": "wiki-navigation-manifest.v1",
        "generated_at": now_iso(),
        "wiki_hub": str(wiki_hub),
        "topics": manifest_topics,
        "governance": governance,
        "side_effects": {
            "modified_raw_sources": False,
            "called_llm": False,
            "created_kfc_project": False,
        },
    }


def article_card(article: dict[str, Any], topic_id: str) -> str:
    concepts = "、".join(article.get("concepts") or []) or "暂无"
    compiled = article.get("compiled_path") or ""
    source = article.get("source_path") or ""
    status = article.get("status") or "unknown"
    follow_up = "可进入 KFC Research 候选" if article.get("kfc_candidate") else "保留为主题材料"
    lines = [
        f"### {article.get('title') or article.get('source_id')}",
        f"- 摘要：{article.get('summary') or '暂无摘要。'}",
        f"- 概念：{concepts}",
        f"- 来源：[{source}](../../topics/{topic_id}/{source})" if source else "- 来源：-",
        f"- 编译页：[{compiled}](../../topics/{topic_id}/{compiled})" if compiled else "- 编译页：-",
        f"- 状态：{status}",
        f"- 后续：{follow_up}",
    ]
    if article.get("topic_fit_status"):
        lines.append(f"- 主题匹配：{article.get('topic_fit_status')} · {article.get('topic_fit_score') or '-'}")
    if article.get("topic_fit_recommended"):
        lines.append(f"- 建议主题：{article.get('topic_fit_recommended')}")
    return "\n".join(lines)


def write_markdown_outputs(wiki_hub: Path, manifest: dict[str, Any]) -> list[str]:
    out_root = wiki_hub / "wiki"
    data_root = out_root / "_data"
    topics_out = out_root / "topics"
    data_root.mkdir(parents=True, exist_ok=True)
    topics_out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    rows = [
        "| 主题 | 文章数 | 最近更新 | 代表概念 | 推荐动作 |",
        "|---|---:|---|---|---|",
    ]
    for topic in manifest["topics"]:
        concepts = "、".join(topic.get("concepts") or []) or "暂无"
        rows.append(
            f"| [{topic['title']}](topics/{topic['topic_id']}.md) | {topic['article_count']} | {topic.get('last_updated') or '-'} | {concepts} | 进入主题 |"
        )
    recent = sorted(
        ({"topic_id": topic["topic_id"], "topic_title": topic["title"], **article} for topic in manifest["topics"] for article in topic["articles"]),
        key=lambda item: item.get("last_updated") or "",
        reverse=True,
    )[:20]
    governance = manifest.get("governance") or {}
    index_lines = [
        "# knowledge-workspace Wiki",
        "",
        f"> 派生导航层；生成时间：{manifest['generated_at']}。llm-wiki 仍只做 source-only 预消化、主题归档和人工可读索引。",
        "",
        "## 主题地图",
        "",
        *rows,
        "",
        "## 最近新增",
        "",
        *[
            f"- [{item['title']}](../topics/{item['topic_id']}/{item.get('compiled_path') or item.get('source_path')}) · {item['topic_title']} · {item.get('last_updated') or '-'}"
            for item in recent
        ],
        "",
        "## 待整理 / 主题不确定",
        "",
        f"- misfit 高的文章：{len(governance.get('misfit') or [])} 篇",
        f"- 推荐主题与实际主题冲突：{len(governance.get('topic_conflicts') or [])} 篇",
        f"- 候选 KFC Research：{len(governance.get('kfc_candidates') or [])} 篇",
        "",
        "详见 [待治理视图](governance.md)。",
    ]
    index_path = out_root / "index.md"
    index_path.write_text("\n".join(index_lines).rstrip() + "\n", encoding="utf-8")
    written.append(str(index_path))

    for topic in manifest["topics"]:
        topic_lines = [
            f"# {topic['title']}",
            "",
            topic.get("definition") or "",
            "",
            "## 核心概念",
            "",
            *[f"- {concept}" for concept in (topic.get("concepts") or ["暂无候选概念"])],
            "",
            "## 文章",
            "",
            *[article_card(article, topic["topic_id"]) + "\n" for article in topic.get("articles", [])],
            "## 快速入口",
            "",
            *[
                f"- 想看“{entry['intent']}”：优先读《{entry['title']}》"
                for entry in topic.get("quick_entries", [])
            ],
            "",
        ]
        topic_path = topics_out / f"{topic['topic_id']}.md"
        topic_path.write_text("\n".join(topic_lines).rstrip() + "\n", encoding="utf-8")
        written.append(str(topic_path))

    governance_lines = ["# 待治理视图", "", f"> 生成时间：{manifest['generated_at']}。", ""]
    labels = {
        "misfit": "misfit 高的文章",
        "topic_conflicts": "推荐主题与实际主题冲突",
        "uncategorized": "未归类文章",
        "kfc_candidates": "进入 KFC 候选",
    }
    for key, label in labels.items():
        governance_lines.extend([f"## {label}", ""])
        items = governance.get(key) or []
        if not items:
            governance_lines.append("- 暂无")
        else:
            for item in items:
                governance_lines.append(
                    f"- [{item.get('title')}](../topics/{item.get('topic_id')}/{item.get('compiled_path') or item.get('source_path')}) · 当前主题：{item.get('topic_title')} · 建议：{item.get('topic_fit_recommended') or '-'}"
                )
        governance_lines.append("")
    governance_path = out_root / "governance.md"
    governance_path.write_text("\n".join(governance_lines).rstrip() + "\n", encoding="utf-8")
    written.append(str(governance_path))

    manifest_path = data_root / "wiki_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.append(str(manifest_path))
    return written


def generate_wiki_navigation(wiki_hub: Path) -> dict[str, Any]:
    wiki_hub = wiki_hub.expanduser().resolve()
    manifest = build_manifest(wiki_hub)
    written = write_markdown_outputs(wiki_hub, manifest)
    return {
        "schema_version": "wiki-navigation-run.v1",
        "status": "succeeded",
        "generated_at": manifest["generated_at"],
        "topic_count": len(manifest.get("topics") or []),
        "article_count": sum(topic.get("article_count", 0) for topic in manifest.get("topics") or []),
        "written_files": written,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate hub-level llm-wiki navigation files.")
    parser.add_argument("--wiki-hub", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub"))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = generate_wiki_navigation(args.wiki_hub)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
