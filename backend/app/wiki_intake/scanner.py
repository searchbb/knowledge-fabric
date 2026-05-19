"""Read-only scanner for Clippings Markdown files."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = "manifest.v1"
TOOL_VERSION = "kfc-wiki-intake-scanner-0.1"

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


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        metadata[key.strip()] = value
    return metadata, text[match.end():]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_source_id(path: Path, metadata: dict[str, str], content_hash: str) -> str:
    source_url = metadata.get("source_url", "").strip()
    identity = source_url or str(path)
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    return f"src_{digest}_{content_hash[:8]}"


def _first_heading(body: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(1).strip() if match else ""


def _plain_excerpt(body: str, limit: int = 220) -> str:
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


def _local_refs(pattern: re.Pattern[str], body: str) -> list[str]:
    refs: list[str] = []
    for match in pattern.finditer(body):
        ref = match.group(1).strip()
        if ref.startswith(("http://", "https://", "mailto:", "#")):
            continue
        refs.append(ref.split("#", 1)[0])
    return refs


def _existing_ref_count(root_file: Path, refs: list[str]) -> int:
    count = 0
    for ref in refs:
        try:
            if (root_file.parent / ref).resolve().exists():
                count += 1
        except OSError:
            pass
    return count


def _source_type(source_url: str, workflow: str) -> str:
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


def _guess_topics(title: str, body: str) -> list[dict[str, Any]]:
    haystack = f"{title}\n{body[:4000]}".lower()
    guesses = []
    for topic, keywords in TOPIC_RULES:
        score = sum(1 for keyword in keywords if keyword.lower() in haystack)
        if score:
            guesses.append({"topic_id": topic, "score": score})
    guesses.sort(key=lambda item: (-item["score"], item["topic_id"]))
    return guesses[:3]


def scan_markdown_file(path: Path, root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    metadata, body = parse_frontmatter(text)
    content_hash = _sha256_bytes(raw)
    title = metadata.get("title") or _first_heading(body) or path.stem
    image_refs = _local_refs(IMAGE_RE, body)
    link_refs = _local_refs(LINK_RE, body)
    source_url = metadata.get("source_url", "")
    workflow = metadata.get("workflow", "")
    stat = path.stat()

    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "source_id": _stable_source_id(path, metadata, content_hash),
        "candidate_id": _stable_source_id(path, metadata, content_hash),
        "title": title,
        "source_file_path": str(path),
        "source_relative_path": str(path.relative_to(root)),
        "source_url": source_url,
        "source_domain": urlparse(source_url).netloc if source_url else "",
        "source_type": _source_type(source_url, workflow),
        "archived_at": metadata.get("archived_at", ""),
        "workflow": workflow,
        "content_hash": f"sha256:{content_hash}",
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
        "char_count": len(text),
        "line_count": text.count("\n") + 1,
        "image_ref_count": len(image_refs),
        "existing_image_ref_count": _existing_ref_count(path, image_refs),
        "local_link_ref_count": len(link_refs),
        "existing_local_link_ref_count": _existing_ref_count(path, link_refs),
        "frontmatter_keys": sorted(metadata.keys()),
        "guessed_topics": _guess_topics(title, body),
        "excerpt": _plain_excerpt(body),
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
    by_hash: dict[str, list[str]] = defaultdict(list)
    by_url: dict[str, list[str]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    for record in records:
        source_id = record["source_id"]
        by_hash[record["content_hash"]].append(source_id)
        if record["source_url"]:
            by_url[record["source_url"]].append(source_id)
        normalized_title = re.sub(r"\s+", "", record["title"].lower())
        if normalized_title:
            by_title[normalized_title].append(source_id)

    for record in records:
        source_id = record["source_id"]
        exact_hash = [item for item in by_hash[record["content_hash"]] if item != source_id]
        same_url = [item for item in by_url.get(record["source_url"], []) if item != source_id]
        same_title = [item for item in by_title.get(re.sub(r"\s+", "", record["title"].lower()), []) if item != source_id]
        status = "none"
        if exact_hash:
            status = "exact_hash_duplicate"
        elif same_url:
            status = "same_url_duplicate"
        elif same_title:
            status = "same_title_possible_duplicate"
        record["duplicate_status"] = status
        record["duplicate_candidate_ids"] = sorted(set(exact_hash + same_url + same_title))


def scan_clippings(clippings_root: Path) -> list[dict[str, Any]]:
    root = clippings_root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Clippings root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Clippings root is not a directory: {root}")
    md_files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".markdown"})
    records = [scan_markdown_file(path, root) for path in md_files]
    attach_duplicate_info(records)
    return records
