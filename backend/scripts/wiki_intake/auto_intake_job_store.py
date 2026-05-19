#!/usr/bin/env python3
"""File-backed auto-intake job helpers.

The auto-intake pipeline is intentionally file-backed: each clipping becomes a
single job with its own run directory, audit log, artifacts, and bounded runner
state. This keeps scheduled processing recoverable and prevents long-lived UI,
ChatGPT, or Codex sessions from becoming the source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote


DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")
ACTIVE_STATUSES = {
    "queued",
    "claimed",
    "preparing_input",
    "gpt_running",
    "gpt_output_received",
    "validating_output",
    "topic_resolved",
    "ingesting_wiki",
    "compiling_wiki",
}
TERMINAL_STATUSES = {
    "completed",
    "failed",
    "failed_gpt",
    "failed_validation",
    "failed_ingest",
    "failed_compile",
    "needs_human_review",
    "skipped_duplicate",
    "stuck",
}
STATUS_DIRS = sorted(ACTIVE_STATUSES | TERMINAL_STATUSES)
RUNNING_STATUSES = {
    "claimed",
    "preparing_input",
    "gpt_running",
    "gpt_output_received",
    "validating_output",
    "topic_resolved",
    "ingesting_wiki",
    "compiling_wiki",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def jobs_root(intake_dir: Path) -> Path:
    return intake_dir / "auto_jobs"


def runs_root(intake_dir: Path) -> Path:
    return intake_dir / "auto_runs"


def status_dir(intake_dir: Path, status: str) -> Path:
    return jobs_root(intake_dir) / status


def source_key(record: dict[str, Any]) -> str:
    return "|".join([
        str(record.get("source_id") or ""),
        str(record.get("content_hash") or ""),
    ])


def job_id_for_record(record: dict[str, Any]) -> str:
    digest = sha1_text(source_key(record) or str(record.get("source_file_path") or ""))[:14]
    return f"auto_{digest}"


def ensure_layout(intake_dir: Path) -> None:
    for status in STATUS_DIRS:
        status_dir(intake_dir, status).mkdir(parents=True, exist_ok=True)
    runs_root(intake_dir).mkdir(parents=True, exist_ok=True)


def all_job_paths(intake_dir: Path) -> list[Path]:
    root = jobs_root(intake_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.glob("*/*.json") if path.is_file())


def load_jobs(intake_dir: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for path in all_job_paths(intake_dir):
        try:
            job = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        job["job_path"] = str(path)
        jobs.append(job)
    jobs.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("job_id") or "")))
    return jobs


def find_job_by_id(intake_dir: Path, job_id: str) -> tuple[dict[str, Any], Path] | None:
    for path in all_job_paths(intake_dir):
        if path.stem != job_id:
            continue
        job = read_json(path)
        job["job_path"] = str(path)
        return job, path
    return None


def active_source_keys(intake_dir: Path) -> set[str]:
    keys: set[str] = set()
    for job in load_jobs(intake_dir):
        key = str(job.get("source_key") or "")
        if key:
            keys.add(key)
    for record in read_jsonl(intake_dir / "processed_manifest.jsonl") + read_jsonl(intake_dir / "auto_processed_manifest.jsonl"):
        key = str(record.get("source_key") or "")
        if key:
            keys.add(key)
    return keys


def processed_source_keys(intake_dir: Path) -> set[str]:
    keys: set[str] = set()
    for record in read_jsonl(intake_dir / "processed_manifest.jsonl") + read_jsonl(intake_dir / "auto_processed_manifest.jsonl"):
        key = str(record.get("source_key") or "")
        if key:
            keys.add(key)
    return keys


def run_dir_for_job(intake_dir: Path, job_id: str) -> Path:
    return runs_root(intake_dir) / job_id


def job_path_for_status(intake_dir: Path, job_id: str, status: str) -> Path:
    return status_dir(intake_dir, status) / f"{job_id}.json"


def write_transition_event(intake_dir: Path, job: dict[str, Any], from_status: str, to_status: str, note: str = "") -> None:
    timestamp = now_iso()
    event = {
        "schema_version": "auto-intake-event.v1",
        "event_type": "auto_intake_status_changed",
        "event_at": timestamp,
        "job_id": job.get("job_id"),
        "source_id": job.get("source_id"),
        "source_key": job.get("source_key"),
        "from_status": from_status,
        "to_status": to_status,
        "note": note,
    }
    append_jsonl(intake_dir / "auto_intake_events.jsonl", event)
    audit_path = Path(str(job.get("run_dir") or run_dir_for_job(intake_dir, str(job.get("job_id"))))) / "audit" / "transitions.jsonl"
    append_jsonl(audit_path, event)


def create_job(intake_dir: Path, record: dict[str, Any], status: str = "queued", reason: str = "") -> dict[str, Any]:
    ensure_layout(intake_dir)
    job_id = job_id_for_record(record)
    run_dir = run_dir_for_job(intake_dir, job_id)
    timestamp = now_iso()
    job = {
        "schema_version": "auto-intake-job.v1",
        "job_id": job_id,
        "source_key": source_key(record),
        "source_id": record.get("source_id", ""),
        "content_hash": record.get("content_hash", ""),
        "title": record.get("title", ""),
        "source_url": record.get("source_url", ""),
        "source_file_path": record.get("source_file_path", ""),
        "source_relative_path": record.get("source_relative_path", ""),
        "duplicate_status": record.get("duplicate_status", "none"),
        "duplicate_candidate_ids": record.get("duplicate_candidate_ids", []),
        "guessed_topics": record.get("guessed_topics", []),
        "image_refs_total": record.get("image_ref_count", 0),
        "image_refs_resolved": record.get("existing_image_ref_count", 0),
        "status": status,
        "attempt": 0,
        "max_attempts": 2,
        "created_at": timestamp,
        "updated_at": timestamp,
        "claimed_at": "",
        "heartbeat_at": "",
        "finished_at": timestamp if status in TERMINAL_STATUSES else "",
        "runner_pid": None,
        "session_strategy": {
            "chatgpt": "fresh_chatgpt_thinking_one_md",
            "codex": "fresh_codex_exec_per_job_required",
            "reuse_current_conversation": False,
        },
        "timeout_seconds": 1500,
        "run_dir": str(run_dir),
        "artifacts": {},
        "error": "",
        "reason": reason,
    }
    path = job_path_for_status(intake_dir, job_id, status)
    write_json_atomic(path, job)
    write_transition_event(intake_dir, job, "", status, reason)
    job["job_path"] = str(path)
    return job


def move_job(intake_dir: Path, job: dict[str, Any], to_status: str, note: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_layout(intake_dir)
    job_id = str(job.get("job_id") or "")
    if not job_id:
        raise ValueError("job_id_required")
    current = find_job_by_id(intake_dir, job_id)
    current_path = current[1] if current else job_path_for_status(intake_dir, job_id, str(job.get("status") or "queued"))
    from_status = str(job.get("status") or current_path.parent.name)
    updated = dict(job)
    updated["status"] = to_status
    updated["updated_at"] = now_iso()
    if to_status in TERMINAL_STATUSES:
        updated["finished_at"] = updated.get("finished_at") or now_iso()
    if note:
        updated["status_note"] = note
    if extra:
        updated.update(extra)
    new_path = job_path_for_status(intake_dir, job_id, to_status)
    write_json_atomic(new_path, updated)
    if current_path.exists() and current_path.resolve() != new_path.resolve():
        current_path.unlink()
    write_transition_event(intake_dir, updated, from_status, to_status, note)
    updated["job_path"] = str(new_path)
    return updated


def claim_next(intake_dir: Path, claimed_by: str, pid: int | None = None) -> dict[str, Any] | None:
    ensure_layout(intake_dir)
    queued = sorted(status_dir(intake_dir, "queued").glob("*.json"))
    processed_keys = processed_source_keys(intake_dir)
    for path in queued:
        job = read_json(path)
        source = str(job.get("source_key") or "")
        if source and source in processed_keys:
            move_job(intake_dir, job, "skipped_duplicate", "already_auto_processed")
            continue
        lock_path = path.with_suffix(path.suffix + ".lock")
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"claimed_by": claimed_by, "claimed_at": now_iso()}, ensure_ascii=False))
        job["attempt"] = int(job.get("attempt") or 0) + 1
        job["claimed_at"] = now_iso()
        job["heartbeat_at"] = job["claimed_at"]
        job["runner_pid"] = pid or os.getpid()
        job["claimed_by"] = claimed_by
        job["run_dir"] = str(run_dir_for_job(intake_dir, str(job["job_id"])) / f"attempt_{job['attempt']}")
        claimed = move_job(intake_dir, job, "claimed", f"claimed_by={claimed_by}")
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        return claimed
    return None


def heartbeat(intake_dir: Path, job: dict[str, Any], note: str = "") -> dict[str, Any]:
    job["heartbeat_at"] = now_iso()
    job["runner_pid"] = os.getpid()
    job["updated_at"] = job["heartbeat_at"]
    if note:
        job["heartbeat_note"] = note
    path = job_path_for_status(intake_dir, str(job["job_id"]), str(job["status"]))
    write_json_atomic(path, job)
    job["job_path"] = str(path)
    return job


def fail_or_retry(intake_dir: Path, job: dict[str, Any], failed_status: str, error: str) -> dict[str, Any]:
    return move_job(intake_dir, job, failed_status, error, {"error": error})


def recover_stuck(intake_dir: Path, stale_seconds: int = 1800) -> list[dict[str, Any]]:
    recovered: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).astimezone()
    for job in load_jobs(intake_dir):
        if job.get("status") not in RUNNING_STATUSES:
            continue
        heartbeat_at = parse_iso(str(job.get("heartbeat_at") or job.get("updated_at") or ""))
        stale = True if not heartbeat_at else (now - heartbeat_at).total_seconds() > stale_seconds
        pid = job.get("runner_pid")
        pid_dead = False
        if isinstance(pid, int) and pid > 0:
            try:
                os.kill(pid, 0)
            except OSError:
                pid_dead = True
        if stale or pid_dead:
            reason = "heartbeat_stale" if stale else "runner_pid_dead"
            recovered.append(move_job(intake_dir, job, "stuck", reason, {"error": reason}))
    return recovered


def copy_input_bundle(job: dict[str, Any]) -> dict[str, str]:
    source_path = Path(str(job.get("source_file_path") or "")).expanduser().resolve()
    run_dir = Path(str(job.get("run_dir") or ""))
    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    article_path = input_dir / "article.md"
    if source_path.exists():
        shutil.copy2(source_path, article_path)
    asset_refs: list[str] = []
    if source_path.exists():
        text = source_path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)|\[\[([^]\n]+\.(?:png|jpg|jpeg|gif|webp|svg|pdf))\]\]", text, flags=re.IGNORECASE):
            raw = (match.group(1) or match.group(2) or "").strip()
            raw = raw.split("#", 1)[0].split("?", 1)[0].strip()
            if raw and "://" not in raw and not raw.startswith(("/", "\\")):
                asset_refs.append(raw)
    copied_images: list[dict[str, str]] = []
    assets_dir = input_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for ref in list(dict.fromkeys(asset_refs)):
        ref_candidates = list(dict.fromkeys([ref, unquote(ref)]))
        candidate: Path | None = None
        for candidate_ref in ref_candidates:
            try:
                possible = (source_path.parent / candidate_ref).expanduser().resolve()
                if possible.exists() and possible.is_file():
                    candidate = possible
                    break
            except OSError:
                continue
        if candidate is None:
            continue
        if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        target = assets_dir / candidate.name
        if not target.exists():
            shutil.copy2(candidate, target)
        copied_images.append({"ref": ref, "source": str(candidate), "input_path": str(target), "provided_to_gpt": False})
    manifest_path = input_dir / "assets_manifest.json"
    manifest = {
        "source_file_path": str(source_path),
        "image_refs_total": job.get("image_refs_total", 0),
        "image_refs_resolved": job.get("image_refs_resolved", 0),
        "images": copied_images,
        "note": "Local image refs are copied when resolvable; attachment adapters mark provided_to_gpt after upload.",
    }
    write_json_atomic(manifest_path, manifest)
    return {"article_path": str(article_path), "assets_manifest_path": str(manifest_path)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Inspect or recover auto-intake jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    list_parser.add_argument("--status", default="")
    recover_parser = subparsers.add_parser("recover-stuck")
    recover_parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    recover_parser.add_argument("--stale-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    if args.command == "list":
        jobs = load_jobs(args.intake_dir.expanduser().resolve())
        if args.status:
            jobs = [job for job in jobs if job.get("status") == args.status]
        print(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "recover-stuck":
        recovered = recover_stuck(args.intake_dir.expanduser().resolve(), args.stale_seconds)
        print(json.dumps({"recovered": recovered}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
