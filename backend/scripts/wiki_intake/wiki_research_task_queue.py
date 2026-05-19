#!/usr/bin/env python3
"""Small file-backed queue helpers for wiki_research_task records.

This script does not perform Research. It only lists and atomically claims
tasks so a Codex App session can process them with the LLM Wiki skill.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def task_paths(hub: Path) -> list[Path]:
    return sorted((hub / "topics").glob("*/research/tasks/wrt_*.json"))


def list_tasks(hub: Path, status: str = "queued_for_wiki_research") -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in task_paths(hub):
        try:
            task = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if status and task.get("status") != status:
            continue
        task["task_path"] = str(path)
        tasks.append(task)
    return tasks


def claim_task(task_path: Path, claimed_by: str) -> dict[str, Any]:
    task_path = task_path.expanduser().resolve()
    lock_path = task_path.with_suffix(task_path.suffix + ".lock")
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("already_claimed_or_locked") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"claimed_by": claimed_by, "claimed_at": now_iso()}, ensure_ascii=False))
    task = read_json(task_path)
    if task.get("status") != "queued_for_wiki_research":
        raise RuntimeError(f"task_not_queued: {task.get('status')}")
    timestamp = now_iso()
    processor = task.setdefault("processor", {})
    processor["claimed_by"] = claimed_by
    processor["claimed_at"] = timestamp
    task["status"] = "claimed_by_codex_app"
    task["updated_at"] = timestamp
    write_json_atomic(task_path, task)
    topic_root = Path(task.get("topic_path") or task_path.parents[2])
    append_jsonl(topic_root / "research" / "events.jsonl", {"event_type": "wiki_research_task_claimed", "task_id": task.get("task_id"), "topic_id": task.get("topic_id"), "created_at": timestamp, "claimed_by": claimed_by})
    task["task_path"] = str(task_path)
    task["lock_path"] = str(lock_path)
    return task


def transition_task(task_path: Path, status: str, note: str = "") -> dict[str, Any]:
    task_path = task_path.expanduser().resolve()
    task = read_json(task_path)
    timestamp = now_iso()
    task["status"] = status
    task["updated_at"] = timestamp
    if note:
        task["processor_note"] = note
    write_json_atomic(task_path, task)
    topic_root = Path(task.get("topic_path") or task_path.parents[2])
    append_jsonl(topic_root / "research" / "events.jsonl", {"event_type": "wiki_research_task_status_changed", "task_id": task.get("task_id"), "topic_id": task.get("topic_id"), "created_at": timestamp, "status": status})
    task["task_path"] = str(task_path)
    return task


def complete_task(task_path: Path, report_path: Path, sources_path: Path, evidence_path: Path, raw_article_path: Path | None = None, compile_run_id: str = "") -> dict[str, Any]:
    task_path = task_path.expanduser().resolve()
    report_path = report_path.expanduser().resolve()
    sources_path = sources_path.expanduser().resolve()
    evidence_path = evidence_path.expanduser().resolve()
    missing = [str(path) for path in [report_path, sources_path, evidence_path] if not path.exists()]
    if raw_article_path:
        raw_article_path = raw_article_path.expanduser().resolve()
        if not raw_article_path.exists():
            missing.append(str(raw_article_path))
    if missing:
        raise RuntimeError("missing_required_artifacts: " + ", ".join(missing))
    task = read_json(task_path)
    timestamp = now_iso()
    artifacts = task.setdefault("artifacts", {})
    artifacts["report_path"] = str(report_path)
    artifacts["sources_path"] = str(sources_path)
    artifacts["evidence_path"] = str(evidence_path)
    artifacts["raw_article_path"] = str(raw_article_path) if raw_article_path else artifacts.get("raw_article_path")
    artifacts["compile_run_id"] = compile_run_id or artifacts.get("compile_run_id")
    assessment = task.setdefault("research_assessment", {})
    assessment["status"] = "completed_with_artifacts"
    assessment["quality_gate_result"] = "pass"
    assessment["compile_requested"] = bool(task.get("compile_after_research"))
    assessment["compile_allowed_mode"] = assessment.get("compile_allowed_mode") or "incremental_only"
    if compile_run_id:
        assessment["incremental_compile_run_id"] = compile_run_id
    task["status"] = "completed"
    task["updated_at"] = timestamp
    task["error"] = None
    write_json_atomic(task_path, task)
    topic_root = Path(task.get("topic_path") or task_path.parents[2])
    append_jsonl(topic_root / "research" / "events.jsonl", {"event_type": "wiki_research_task_completed", "task_id": task.get("task_id"), "topic_id": task.get("topic_id"), "created_at": timestamp, "status": "completed"})
    task["task_path"] = str(task_path)
    return task


def fail_task(task_path: Path, error: str) -> dict[str, Any]:
    task_path = task_path.expanduser().resolve()
    task = read_json(task_path)
    timestamp = now_iso()
    task["status"] = "failed"
    task["updated_at"] = timestamp
    task["error"] = error
    write_json_atomic(task_path, task)
    topic_root = Path(task.get("topic_path") or task_path.parents[2])
    append_jsonl(topic_root / "research" / "events.jsonl", {"event_type": "wiki_research_task_failed", "task_id": task.get("task_id"), "topic_id": task.get("topic_id"), "created_at": timestamp, "status": "failed", "error": error})
    task["task_path"] = str(task_path)
    return task


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="List or claim wiki Research tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--hub", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub"))
    list_parser.add_argument("--status", default="queued_for_wiki_research")
    claim_parser = subparsers.add_parser("claim")
    claim_parser.add_argument("--task-path", type=Path, required=True)
    claim_parser.add_argument("--claimed-by", default="codex_app_session")
    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("--task-path", type=Path, required=True)
    transition_parser.add_argument("--status", required=True)
    transition_parser.add_argument("--note", default="")
    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--task-path", type=Path, required=True)
    complete_parser.add_argument("--report-path", type=Path, required=True)
    complete_parser.add_argument("--sources-path", type=Path, required=True)
    complete_parser.add_argument("--evidence-path", type=Path, required=True)
    complete_parser.add_argument("--raw-article-path", type=Path)
    complete_parser.add_argument("--compile-run-id", default="")
    fail_parser = subparsers.add_parser("fail")
    fail_parser.add_argument("--task-path", type=Path, required=True)
    fail_parser.add_argument("--error", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(json.dumps({"tasks": list_tasks(args.hub.expanduser().resolve(), args.status)}, ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == "claim":
            print(json.dumps(claim_task(args.task_path, args.claimed_by), ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == "transition":
            print(json.dumps(transition_task(args.task_path, args.status, args.note), ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == "complete":
            print(json.dumps(complete_task(args.task_path, args.report_path, args.sources_path, args.evidence_path, args.raw_article_path, args.compile_run_id), ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == "fail":
            print(json.dumps(fail_task(args.task_path, args.error), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
