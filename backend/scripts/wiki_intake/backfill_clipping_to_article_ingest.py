#!/usr/bin/env python3
"""Backfill a previous raw/clippings staging copy into raw/articles ingest."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from apply_intake_decision import (  # noqa: E402
    append_jsonl,
    ingest_frontmatter,
    safe_filename,
    slugify,
    today_iso,
)


TOOL_VERSION = "clippings-intake-wiki-ingest-backfill-0.1"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_decision(intake_dir: Path, candidate_id: str) -> dict[str, Any]:
    matches = [item for item in read_jsonl(intake_dir / "decisions.jsonl") if item.get("candidate_id") == candidate_id]
    if not matches:
        return {"candidate_id": candidate_id}
    return max(matches, key=lambda item: str(item.get("applied_at") or item.get("decided_at") or ""))


def rewrite_assets(markdown: str, source_path: Path, assets_dir: Path) -> tuple[str, list[dict[str, str]]]:
    copied_assets: list[dict[str, str]] = []
    rewrite_map: dict[str, str] = {}
    asset_ref_root = safe_filename(assets_dir.name)
    for ref in local_markdown_refs(markdown):
        asset_path = (source_path.parent / ref).resolve()
        if not asset_path.exists() or not asset_path.is_file():
            matches = sorted((source_path.parent / "assets").glob(f"**/{Path(ref).name}"))
            asset_path = matches[0].resolve() if matches else asset_path
        if not asset_path.exists() or not asset_path.is_file():
            raise ValueError(f"referenced asset missing: {ref}")
        target_asset = assets_dir / safe_filename(asset_path.name)
        rewrite_ref = f"assets/{asset_ref_root}/{target_asset.name}"
        rewrite_map[ref] = rewrite_ref
        rewrite_map[ref.replace(" ", "%20")] = rewrite_ref
        copied_assets.append({"source": str(asset_path), "target": str(target_asset), "ref": ref, "rewritten_ref": rewrite_ref})
    rewritten = markdown
    for old_ref, new_ref in sorted(rewrite_map.items(), key=lambda item: len(item[0]), reverse=True):
        rewritten = rewritten.replace(f"]({old_ref})", f"]({new_ref})")
        rewritten = rewritten.replace(f"[[{old_ref}]]", f"[[{new_ref}]]")
    return rewritten, copied_assets


def write_assets(copied_assets: list[dict[str, str]]) -> None:
    for asset in copied_assets:
        target = Path(asset["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(asset["source"], target)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill raw/clippings staging copy to canonical raw/articles ingest.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--wiki-hub", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub"))
    parser.add_argument("--intake-dir", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    source = args.source.expanduser().resolve()
    wiki_hub = args.wiki_hub.expanduser().resolve()
    intake_dir = args.intake_dir.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(source)

    topic_root = wiki_hub / "topics" / args.topic
    decision = latest_decision(intake_dir, args.candidate_id)
    decision.setdefault("topic_id", args.topic)
    decision.setdefault("candidate_id", args.candidate_id)
    decision.setdefault("title", source.stem)
    decision.setdefault("decision_id", f"backfill_{args.candidate_id}")

    target = topic_root / "raw" / "articles" / f"{today_iso()}-{slugify(decision.get('title') or source.stem, args.candidate_id)}-{args.candidate_id}.md"
    assets_dir = target.parent / "assets" / safe_filename(target.stem)
    markdown = source.read_text(encoding="utf-8", errors="replace")
    rewritten, assets = rewrite_assets(markdown, source, assets_dir)
    ingest_markdown = ingest_frontmatter(decision, Path(decision.get("source_file_path") or source), rewritten)

    status = "planned"
    if not args.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_assets(assets)
        if target.exists() and target.read_text(encoding="utf-8", errors="replace") == ingest_markdown:
            status = "already_ingested"
        else:
            target.write_text(ingest_markdown, encoding="utf-8")
            status = "ingested"
        event = {
            "schema_version": "intake-processing-result.v1",
            "tool_version": TOOL_VERSION,
            "processed_at": now_iso(),
            "decision_id": decision.get("decision_id", ""),
            "candidate_id": args.candidate_id,
            "source_path": decision.get("source_file_path", ""),
            "wiki": {
                "requested": True,
                "status": status,
                "md_path": str(target),
                "assets_copied": len(assets),
                "assets": assets,
                "staging_copy": {"requested": True, "status": "existing", "md_path": str(source)},
                "ingest": {
                    "requested": True,
                    "status": status,
                    "source_type": "articles",
                    "path": str(target),
                    "assets_copied": len(assets),
                    "assets": assets,
                    "compile_status": "ready_to_compile",
                    "compile_triggered": False,
                    "backfilled": True,
                },
            },
            "kfc": {"requested": False, "status": "skipped"},
            "archive": {"requested": False, "status": "skipped"},
            "side_effects": {
                "modified_obsidian_source": False,
                "copied_to_llm_wiki": True,
                "created_kfc_project": False,
                "called_llm": False,
            },
            "backfill": {
                "event": "wiki_ingest_backfill",
                "reason": "previous_apply_created_staging_copy_only",
                "from": str(source),
                "to": str(target),
                "status": "ready_to_compile",
                "compile_triggered": False,
            },
        }
        append_jsonl(intake_dir / "processing_results.jsonl", [event])

    print(json.dumps({"ok": True, "status": status, "ingest_path": str(target), "assets_copied": len(assets)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
