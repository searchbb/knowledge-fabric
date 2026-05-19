#!/usr/bin/env python3
"""Enqueue new Markdown clippings for automatic one-shot intake."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import auto_intake_job_store as store


DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def previous_scan_cutoff(intake_dir: Path) -> datetime | None:
    scan_events = [item for item in read_jsonl(intake_dir / "events.jsonl") if item.get("event_type") == "scan_completed" and item.get("event_at")]
    if len(scan_events) < 2:
        return None
    scan_events.sort(key=lambda item: str(item.get("event_at") or ""))
    return parse_iso(str(scan_events[-2].get("event_at") or ""))


def enqueue_from_manifest(intake_dir: Path, manifest_name: str = "manifest.jsonl", limit: int = 0, since_previous_scan: bool = True) -> dict[str, Any]:
    intake_dir = intake_dir.expanduser().resolve()
    store.ensure_layout(intake_dir)
    manifest = read_jsonl(intake_dir / manifest_name)
    cutoff = previous_scan_cutoff(intake_dir) if since_previous_scan else None
    seen_keys = store.active_source_keys(intake_dir)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for record in manifest:
        key = store.source_key(record)
        if not key.strip("|"):
            skipped.append({"source_id": record.get("source_id", ""), "reason": "missing_source_key"})
            continue
        if key in seen_keys:
            skipped.append({"source_id": record.get("source_id", ""), "source_key": key, "reason": "already_active_or_processed"})
            continue
        if cutoff:
            mtime = parse_iso(str(record.get("mtime") or ""))
            if not mtime or mtime < cutoff:
                skipped.append({"source_id": record.get("source_id", ""), "source_key": key, "reason": "older_than_previous_scan"})
                continue
        duplicate_status = str(record.get("duplicate_status") or "none")
        if duplicate_status != "none":
            job = store.create_job(intake_dir, record, status="queued", reason=f"duplicate_risk:{duplicate_status}")
            seen_keys.add(key)
            created.append({"job_id": job["job_id"], "source_id": job["source_id"], "source_key": key, "title": job["title"], "duplicate_status": duplicate_status})
            continue
        job = store.create_job(intake_dir, record, status="queued")
        seen_keys.add(key)
        created.append({"job_id": job["job_id"], "source_id": job["source_id"], "source_key": key, "title": job["title"]})
        if limit and len(created) >= limit:
            break

    result = {
        "ok": True,
        "schema_version": "auto-intake-enqueue-result.v1",
        "intake_dir": str(intake_dir),
        "manifest_count": len(manifest),
        "since_previous_scan": since_previous_scan,
        "previous_scan_cutoff": cutoff.isoformat(timespec="seconds") if cutoff else "",
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }
    store.append_jsonl(
        intake_dir / "auto_intake_events.jsonl",
        {
            "schema_version": "auto-intake-event.v1",
            "event_type": "auto_intake_enqueue_completed",
            "event_at": store.now_iso(),
            "manifest_count": len(manifest),
            "previous_scan_cutoff": cutoff.isoformat(timespec="seconds") if cutoff else "",
            "created_count": len(created),
            "skipped_count": len(skipped),
        },
    )
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create auto-intake jobs from a scanner manifest.")
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--manifest-name", default="manifest.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true", help="Enqueue all unseen manifest records, not only files newer than the previous scan.")
    args = parser.parse_args(argv)
    result = enqueue_from_manifest(args.intake_dir, args.manifest_name, args.limit, since_previous_scan=not args.all)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
