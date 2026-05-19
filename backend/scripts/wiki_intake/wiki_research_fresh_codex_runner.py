#!/usr/bin/env python3
"""Run one Wiki Research task in a fresh Codex exec session.

The Codex App heartbeat automation grew a long-lived conversation context and
could hang before claiming queued tasks. This runner keeps the scheduler thin:
it claims one file-backed task, then starts a brand-new `codex exec` process
with a minimal prompt that points at the task file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import wiki_research_task_queue as queue


ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "wiki_research_task_queue.py"
COMPILER = ROOT / "incremental_compile_topic.py"
WIKI_SKILL_PATH = Path("/Users/mac/.codex/plugins/cache/llm-wiki/wiki/0.8.0/skills/wiki/SKILL.md")
WIKI_RESEARCH_REFERENCE_PATH = Path("/Users/mac/.codex/plugins/cache/llm-wiki/wiki/0.8.0/skills/wiki/references/research-infrastructure.md")


def now_stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%dT%H%M%S")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def skill_contract() -> dict[str, Any]:
    missing = [str(path) for path in [WIKI_SKILL_PATH, WIKI_RESEARCH_REFERENCE_PATH] if not path.exists()]
    if missing:
        raise RuntimeError("missing_llm_wiki_skill_contract: " + ", ".join(missing))
    return {
        "skill": {
            "name": "wiki",
            "path": str(WIKI_SKILL_PATH),
            "sha256": sha256_path(WIKI_SKILL_PATH),
        },
        "workflow": {
            "name": "research",
            "reference_path": str(WIKI_RESEARCH_REFERENCE_PATH),
            "reference_sha256": sha256_path(WIKI_RESEARCH_REFERENCE_PATH),
        },
        "contract": "llm_wiki_research_infrastructure",
    }


def prompt_for_task(task_path: Path, claimed_by: str, contract: dict[str, Any]) -> str:
    return f"""You are processing exactly one file-backed Wiki Research task.

Task path:
{task_path}

Installed LLM Wiki skill contract:
- Skill: {contract["skill"]["name"]}
- Skill file: {contract["skill"]["path"]}
- Skill file sha256: {contract["skill"]["sha256"]}
- Workflow: {contract["workflow"]["name"]}
- Workflow reference: {contract["workflow"]["reference_path"]}
- Workflow reference sha256: {contract["workflow"]["reference_sha256"]}

Hard constraints:
- Before doing Research, read the installed wiki skill file and the research workflow reference listed above. Follow that contract, not an invented local workflow.
- Use only the task JSON and files referenced by it as local context.
- Do not rely on prior chat/session memory.
- Do not modify original OB Clippings.
- Do not call /research-runs or any local stub/generic executor.
- Do not mark the task completed unless report, sources, and evidence artifacts exist.
- Use live web search for external verification when needed.
- Keep output Chinese-first and separate verified facts, evidence, open questions, and recommendations.
- Treat source framing as source framing. Do not promote article titles, marketing claims, or "new paradigm" language into wiki conclusions unless independently verified.
- Use source-type discipline: label every external source as official product page, official docs, source repository, repository docs, third-party media, community page, inferred, or unverified.
- In processor_notes.md, include the skill file path, workflow reference path, and both sha256 values to make the skill contract auditable.

Required workflow:
1. Read the task JSON at the task path. It is already claimed by {claimed_by}.
2. Transition it to running_wiki_research using:
   python3 {HELPER} transition --task-path {task_path} --status running_wiki_research
3. Read the raw article, source digest, topic wiki index, and compiled intake page paths referenced by the task.
4. Write artifacts under /Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub/topics/<topic>/research/output/<task_id>/:
   - research_report.md
   - sources.json
   - evidence.json
   - processor_notes.md
   The report must include a claim ledger with: claim, source ids, evidence type, confidence, allowed wiki wording, blocked wording, and open question.
   The evidence JSON must include negative evidence / not-found notes for important claims that could not be verified.
   The research-derived raw article must include sections for verified facts, source claims, topic fit, not yet verified, safe wiki wording, and unsafe wording to avoid.
5. If compile_after_research is true and useful, write one research-derived raw article under /Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub/topics/<topic>/raw/articles/ with frontmatter:
   source_origin: wiki_research_task
   source_type: wiki_research
   research_task_id: <task_id>
   language: zh-CN
   compile_status: ready_to_compile
6. If a research-derived raw article was written, run only incremental compile:
   python3 {COMPILER} --topic-root /Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub/topics/<topic> --source <raw_article_path> --trigger wiki_research_task --candidate-id <candidate_id> --intake-dir /Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake
7. Complete the task only through:
   python3 {HELPER} complete --task-path {task_path} --report-path <report> --sources-path <sources> --evidence-path <evidence> [--raw-article-path <raw>] [--compile-run-id <run_id>]
8. If processing cannot continue, fail it through:
   python3 {HELPER} fail --task-path {task_path} --error "<concrete error>"

Return a concise final summary with the task id, final status, and artifact paths.
"""


def write_execution_record(task_path: Path, record: dict[str, Any]) -> dict[str, Any]:
    task = read_json(task_path)
    task["execution_record"] = record
    task["updated_at"] = now_iso()
    queue.write_json_atomic(task_path, task)
    return task


def validate_execution_record(task_path: Path, result_returncode: int) -> dict[str, Any]:
    task = read_json(task_path)
    record = task.get("execution_record")
    if not isinstance(record, dict):
        raise RuntimeError("missing_execution_record")
    if record.get("execution_mode") != "fresh_codex_exec":
        raise RuntimeError("invalid_execution_mode")
    skill = record.get("skill") or {}
    workflow = record.get("workflow") or {}
    if skill.get("name") != "wiki" or skill.get("path") != str(WIKI_SKILL_PATH):
        raise RuntimeError("invalid_wiki_skill_record")
    if workflow.get("name") != "research" or workflow.get("reference_path") != str(WIKI_RESEARCH_REFERENCE_PATH):
        raise RuntimeError("invalid_research_workflow_record")
    if skill.get("sha256") != sha256_path(WIKI_SKILL_PATH):
        raise RuntimeError("wiki_skill_hash_mismatch")
    if workflow.get("reference_sha256") != sha256_path(WIKI_RESEARCH_REFERENCE_PATH):
        raise RuntimeError("research_reference_hash_mismatch")
    prompt_path = Path(str(record.get("prompt_path") or ""))
    if not prompt_path.exists() or record.get("prompt_sha256") != sha256_path(prompt_path):
        raise RuntimeError("prompt_hash_mismatch")
    artifacts = task.get("artifacts") or {}
    missing_artifacts = [name for name in ["report_path", "sources_path", "evidence_path"] if not artifacts.get(name) or not Path(str(artifacts.get(name))).exists()]
    if missing_artifacts:
        raise RuntimeError("missing_completed_artifacts: " + ", ".join(missing_artifacts))
    notes_path = task_path.parents[1] / "output" / str(task.get("task_id") or task_path.stem) / "processor_notes.md"
    if not notes_path.exists():
        raise RuntimeError("missing_processor_notes")
    notes_text = notes_path.read_text(encoding="utf-8", errors="replace")
    required_notes_markers = [
        str(WIKI_SKILL_PATH),
        str(WIKI_RESEARCH_REFERENCE_PATH),
        skill["sha256"],
        workflow["reference_sha256"],
    ]
    missing_notes_markers = [marker for marker in required_notes_markers if marker not in notes_text]
    if missing_notes_markers:
        raise RuntimeError("processor_notes_missing_skill_contract_markers")
    record["completed_at"] = now_iso()
    record["status"] = "completed"
    record["codex_returncode"] = result_returncode
    record["artifacts"] = artifacts
    record["processor_notes_path"] = str(notes_path)
    return write_execution_record(task_path, record).get("execution_record", {})


def choose_task(hub: Path) -> dict[str, Any] | None:
    tasks = queue.list_tasks(hub, "queued_for_wiki_research")
    if not tasks:
        return None
    # Deterministic order prevents starvation.
    tasks.sort(key=lambda task: (str(task.get("created_at") or ""), str(task.get("task_id") or "")))
    return tasks[0]


def run_codex(task_path: Path, claimed_by: str, timeout_seconds: int, codex_bin: str, model: str = "") -> subprocess.CompletedProcess[str]:
    contract = skill_contract()
    prompt = prompt_for_task(task_path, claimed_by, contract)
    prompt_dir = task_path.parents[1] / "runner_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / f"{task_path.stem}.{now_stamp()}.prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    logs_dir = task_path.parents[1] / "runner_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{task_path.stem}.{now_stamp()}.stdout.log"
    stderr_path = logs_dir / f"{task_path.stem}.{now_stamp()}.stderr.log"
    cmd = [
        codex_bin,
        "exec",
        "--cd",
        str(ROOT),
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    execution_record = {
        "schema_version": "wiki-research-execution-record.v1",
        "execution_mode": "fresh_codex_exec",
        "executor": "codex_exec",
        "started_at": now_iso(),
        "status": "started",
        "claimed_by": claimed_by,
        "skill": contract["skill"],
        "workflow": contract["workflow"],
        "contract": contract["contract"],
        "task_path": str(task_path),
        "prompt_path": str(prompt_path),
        "prompt_sha256": sha256_path(prompt_path),
        "command": [codex_bin, "exec", "--cd", str(ROOT), "--dangerously-bypass-approvals-and-sandbox", "<prompt: see prompt_path>"],
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    write_execution_record(task_path, execution_record)
    env = {
        **os.environ,
        "CODEX_WIKI_RESEARCH_TASK_PATH": str(task_path),
        "CODEX_WIKI_RESEARCH_PROMPT_PATH": str(prompt_path),
        "CODEX_WIKI_SKILL_PATH": str(WIKI_SKILL_PATH),
        "CODEX_WIKI_RESEARCH_REFERENCE_PATH": str(WIKI_RESEARCH_REFERENCE_PATH),
    }
    result = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")
    return result


def process_one(args: argparse.Namespace) -> int:
    hub = args.hub.expanduser().resolve()
    task = choose_task(hub)
    if not task:
        print(json.dumps({"ok": True, "status": "no_queued_tasks"}, ensure_ascii=False, indent=2))
        return 0
    task_path = Path(task["task_path"]).expanduser().resolve()
    claimed_by = f"fresh-codex-runner:{now_stamp()}"
    try:
        queue.claim_task(task_path, claimed_by)
    except Exception as exc:
        print(json.dumps({"ok": False, "status": "claim_failed", "task_path": str(task_path), "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    try:
        result = run_codex(task_path, claimed_by, args.timeout_seconds, args.codex_bin, args.model)
    except subprocess.TimeoutExpired as exc:
        task_after_timeout = read_json(task_path)
        record = task_after_timeout.get("execution_record") if isinstance(task_after_timeout.get("execution_record"), dict) else {}
        record["status"] = "timeout"
        record["completed_at"] = now_iso()
        record["error"] = f"fresh codex exec timed out after {args.timeout_seconds}s"
        write_execution_record(task_path, record)
        queue.fail_task(task_path, f"fresh codex exec timed out after {args.timeout_seconds}s")
        print(json.dumps({"ok": False, "status": "timeout_failed_task", "task_path": str(task_path), "stdout": exc.stdout or "", "stderr": exc.stderr or ""}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 124

    refreshed = read_json(task_path)
    if refreshed.get("status") == "completed":
        try:
            execution_record = validate_execution_record(task_path, result.returncode)
        except Exception as exc:
            queue.fail_task(task_path, f"execution_record_validation_failed: {exc}")
            print(json.dumps({"ok": False, "status": "execution_record_validation_failed", "task_id": refreshed.get("task_id"), "error": str(exc), "codex_returncode": result.returncode}, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "status": "completed", "task_id": refreshed.get("task_id"), "artifacts": refreshed.get("artifacts"), "execution_record": execution_record, "codex_returncode": result.returncode}, ensure_ascii=False, indent=2))
        return 0
    if refreshed.get("status") == "failed":
        print(json.dumps({"ok": False, "status": "task_failed", "task_id": refreshed.get("task_id"), "error": refreshed.get("error"), "codex_returncode": result.returncode}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    error = f"fresh codex exec exited {result.returncode} without completing task"
    record = refreshed.get("execution_record") if isinstance(refreshed.get("execution_record"), dict) else {}
    record["status"] = "incomplete_failed"
    record["completed_at"] = now_iso()
    record["codex_returncode"] = result.returncode
    record["error"] = error
    write_execution_record(task_path, record)
    queue.fail_task(task_path, error)
    print(json.dumps({"ok": False, "status": "incomplete_failed_task", "task_path": str(task_path), "error": error, "stdout_tail": result.stdout[-4000:], "stderr_tail": result.stderr[-4000:]}, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Process one queued Wiki Research task with a fresh Codex exec session.")
    parser.add_argument("--hub", type=Path, default=Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub"))
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "/opt/homebrew/bin/codex"))
    parser.add_argument("--model", default=os.environ.get("CODEX_RESEARCH_MODEL", ""))
    args = parser.parse_args(argv)
    return process_one(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
