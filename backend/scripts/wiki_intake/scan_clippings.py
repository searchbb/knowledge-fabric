#!/usr/bin/env python3
"""Read-only scanner for Obsidian Clippings -> wiki intake manifest.

The scanner reads Markdown files from the Clippings folder, computes stable
identity/metadata, refreshes manifest.jsonl, and appends a scan event. It never
writes inside the Obsidian vault and does not trigger llm-wiki or KFC actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_CLIPPINGS = Path("/Users/mac/Downloads/OB笔记/Clippings")
DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")
SCHEMA_VERSION = "manifest.v1"
TOOL_VERSION = "clippings-intake-scanner-0.1"

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("ai-tokenization", ["token", "tokenization", "中文税", "计费", "pricing", "copilot", "claude code"]),
    ("agent-harness", ["agent", "智能体", "harness", "coordination", "skill", "hermes", "openclaw", "codex"]),
    ("knowledge-workspace", ["知识工作台", "knowledge fabric", "kfc", "图谱", "语义层", "nl2sql", "data agent"]),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_source_id(path: Path, metadata: dict[str, str], content_hash: str) -> str:
    source_url = metadata.get("source_url", "").strip()
    identity = source_url or str(path)
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    return f"src_{digest}_{content_hash[:8]}"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
      return {}, text

    raw = match.group(1)
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        metadata[key.strip()] = value
    return metadata, text[match.end():]


def first_heading(body: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(1).strip() if match else ""


def plain_excerpt(body: str, limit: int = 220) -> str:
    lines: list[str] = []
    in_code = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if line.startswith("!") or line.startswith("> 来源"):
            continue
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = cleaned.strip("#>*- 　")
        if cleaned:
            lines.append(cleaned)
        if sum(len(item) for item in lines) >= limit:
            break
    excerpt = " ".join(lines)
    return excerpt[:limit]


def local_refs(pattern: re.Pattern[str], body: str) -> list[str]:
    refs = []
    for match in pattern.finditer(body):
        ref = match.group(1).strip()
        if ref.startswith(("http://", "https://", "mailto:", "#")):
            continue
        refs.append(ref.split("#", 1)[0])
    return refs


def existing_ref_count(root_file: Path, refs: list[str]) -> int:
    count = 0
    for ref in refs:
        candidate = (root_file.parent / ref).resolve()
        try:
            exists = candidate.exists()
        except OSError:
            exists = False
        if exists:
            count += 1
    return count


def source_type(source_url: str, workflow: str) -> str:
    if "clippings_archive" in workflow:
        if "mp.weixin.qq.com" in source_url:
            return "wechat_article"
        if source_url:
            return "web_article"
        return "archived_markdown"
    if "mp.weixin.qq.com" in source_url:
        return "wechat_article"
    if source_url:
        return "web_article"
    return "local_markdown"


def guess_topics(title: str, body: str) -> list[dict[str, Any]]:
    haystack = f"{title}\n{body[:4000]}".lower()
    guesses = []
    for topic, keywords in TOPIC_RULES:
        score = sum(1 for keyword in keywords if keyword.lower() in haystack)
        if score:
            guesses.append({"topic_id": topic, "score": score})
    guesses.sort(key=lambda item: (-item["score"], item["topic_id"]))
    return guesses[:3]


def scan_file(path: Path, root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    metadata, body = parse_frontmatter(text)
    title = metadata.get("title") or first_heading(body) or path.stem
    content_hash = sha256_bytes(raw)
    image_refs = local_refs(IMAGE_RE, body)
    link_refs = local_refs(LINK_RE, body)
    source_url = metadata.get("source_url", "")
    workflow = metadata.get("workflow", "")
    stat = path.stat()

    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "source_id": stable_source_id(path, metadata, content_hash),
        "title": title,
        "source_file_path": str(path),
        "source_relative_path": str(path.relative_to(root)),
        "source_url": source_url,
        "source_domain": urlparse(source_url).netloc if source_url else "",
        "source_type": source_type(source_url, workflow),
        "archived_at": metadata.get("archived_at", ""),
        "workflow": workflow,
        "content_hash": f"sha256:{content_hash}",
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
        "char_count": len(text),
        "line_count": text.count("\n") + 1,
        "image_ref_count": len(image_refs),
        "existing_image_ref_count": existing_ref_count(path, image_refs),
        "local_link_ref_count": len(link_refs),
        "existing_local_link_ref_count": existing_ref_count(path, link_refs),
        "frontmatter_keys": sorted(metadata.keys()),
        "guessed_topics": guess_topics(title, body),
        "excerpt": plain_excerpt(body),
        "intake_status": "candidate",
        "routing_suggestion": "review_required",
        "scanner_side_effects": {
            "modified_obsidian_source": False,
            "copied_to_llm_wiki": False,
            "created_kfc_project": False,
            "called_llm": False,
        },
    }


def attach_duplicate_info(records: list[dict[str, Any]]) -> None:
    by_hash = defaultdict(list)
    by_url = defaultdict(list)
    by_title = defaultdict(list)
    for record in records:
        by_hash[record["content_hash"]].append(record["source_id"])
        if record["source_url"]:
            by_url[record["source_url"]].append(record["source_id"])
        normalized_title = re.sub(r"\s+", "", record["title"].lower())
        if normalized_title:
            by_title[normalized_title].append(record["source_id"])

    for record in records:
        exact_hash = [item for item in by_hash[record["content_hash"]] if item != record["source_id"]]
        same_url = [item for item in by_url.get(record["source_url"], []) if item != record["source_id"]]
        same_title = [item for item in by_title.get(re.sub(r"\s+", "", record["title"].lower()), []) if item != record["source_id"]]
        status = "none"
        if exact_hash:
            status = "exact_hash_duplicate"
        elif same_url:
            status = "same_url_duplicate"
        elif same_title:
            status = "same_title_possible_duplicate"
        record["duplicate_status"] = status
        record["duplicate_candidate_ids"] = sorted(set(exact_hash + same_url + same_title))


def atomic_write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def existing_jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def build_event(records: list[dict[str, Any]], clippings_root: Path, manifest_path: Path, dry_run: bool) -> dict[str, Any]:
    topic_counter = Counter()
    for record in records:
        if record["guessed_topics"]:
            topic_counter[record["guessed_topics"][0]["topic_id"]] += 1

    duplicate_count = sum(1 for record in records if record["duplicate_status"] != "none")
    return {
        "schema_version": "event.v1",
        "tool_version": TOOL_VERSION,
        "event_type": "scan_completed",
        "event_at": now_iso(),
        "dry_run": dry_run,
        "clippings_root": str(clippings_root),
        "manifest_path": str(manifest_path),
        "markdown_count": len(records),
        "duplicate_count": duplicate_count,
        "topic_guess_counts": dict(sorted(topic_counter.items())),
        "side_effects": {
            "modified_obsidian_source": False,
            "copied_to_llm_wiki": False,
            "created_kfc_project": False,
            "called_llm": False,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Clippings scanner for wiki intake.")
    parser.add_argument("--clippings-root", type=Path, default=DEFAULT_CLIPPINGS)
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--manifest-name", default="manifest.jsonl")
    parser.add_argument("--events-name", default="events.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Print summary but do not write manifest/events.")
    parser.add_argument("--allow-empty-overwrite", action="store_true", help="Allow an empty scan to overwrite a previously non-empty manifest.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    clippings_root = args.clippings_root.expanduser().resolve()
    intake_dir = args.intake_dir.expanduser().resolve()
    manifest_path = intake_dir / args.manifest_name
    events_path = intake_dir / args.events_name

    if not clippings_root.exists():
        print(f"ERROR: Clippings root does not exist: {clippings_root}", file=sys.stderr)
        return 2
    if not clippings_root.is_dir():
        print(f"ERROR: Clippings root is not a directory: {clippings_root}", file=sys.stderr)
        return 2

    md_files = sorted(clippings_root.glob("*.md"))
    records = [scan_file(path, clippings_root) for path in md_files]
    attach_duplicate_info(records)

    event = build_event(records, clippings_root, manifest_path, args.dry_run)
    summary = {
        "dry_run": args.dry_run,
        "clippings_root": str(clippings_root),
        "intake_dir": str(intake_dir),
        "manifest_path": str(manifest_path),
        "events_path": str(events_path),
        "markdown_count": len(records),
        "duplicate_count": event["duplicate_count"],
        "topic_guess_counts": event["topic_guess_counts"],
    }

    if not args.dry_run:
        previous_count = existing_jsonl_count(manifest_path)
        if not records and previous_count > 0 and not args.allow_empty_overwrite:
            print(
                f"ERROR: refusing to overwrite non-empty manifest ({previous_count} records) with an empty scan from {clippings_root}",
                file=sys.stderr,
            )
            return 3
        atomic_write_jsonl(manifest_path, records)
        append_event(events_path, event)

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
