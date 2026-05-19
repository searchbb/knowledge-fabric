#!/usr/bin/env python3
"""Export intake manifest.jsonl into a static JS data file for the prototype UI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake/manifest.jsonl")
DEFAULT_OUTPUT = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/scripts/wiki_intake/candidates.generated.js")


def destination_from_record(record: dict[str, Any]) -> str:
    topics = [item.get("topic_id") for item in record.get("guessed_topics", [])]
    if record.get("duplicate_status") != "none":
        return "neither"
    if topics and topics[0] in {"agent-harness", "knowledge-workspace"}:
        return "both"
    return "llm_wiki_only"


def ui_candidate(record: dict[str, Any]) -> dict[str, Any]:
    guessed_topics = record.get("guessed_topics", [])
    topic = guessed_topics[0]["topic_id"] if guessed_topics else "new-topic"
    score = min(99, 50 + (guessed_topics[0]["score"] * 10 if guessed_topics else 0))
    source_type_label = {
        "wechat_article": "微信",
        "web_article": "网页",
        "local_markdown": "本地",
        "archived_markdown": "归档",
    }.get(record.get("source_type"), "未知")

    return {
        "candidate_id": record["source_id"],
        "title": record["title"],
        "source": source_type_label,
        "source_url": record.get("source_url", ""),
        "domain": record.get("source_domain") or source_type_label,
        "topic": topic,
        "archived_at": record.get("archived_at") or record.get("mtime", ""),
        "discovered_at": record.get("mtime", ""),
        "score": score,
        "user_status": "pending",
        "duplicate_status": record.get("duplicate_status", "none"),
        "similarity_score": 1.0 if record.get("duplicate_status") != "none" else 0.0,
        "similar_to_candidate_ids": record.get("duplicate_candidate_ids", []),
        "content_hash": record["content_hash"],
        "frontmatter_hash": "",
        "source_file_path": record["source_file_path"],
        "summary": record.get("excerpt", ""),
        "tags": [item["topic_id"] for item in guessed_topics],
        "suggested_destination": destination_from_record(record),
        "suggested_note": "由只读扫描器生成的候选项，请在关口 1 做最终判断。",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export manifest.jsonl to candidates.generated.js.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    manifest = args.manifest.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not manifest.exists():
        print(f"ERROR: manifest not found: {manifest}", file=sys.stderr)
        return 2

    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    candidates = [ui_candidate(record) for record in records]
    payload = {
        "schema_version": "ui-candidates.v1",
        "source_manifest": str(manifest),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "window.CLIPPINGS_INTAKE_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "candidate_count": len(candidates)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
