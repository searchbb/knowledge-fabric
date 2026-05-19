#!/usr/bin/env python3
"""Rerun routing validation for an existing auto-intake job without mutating data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from topic_candidate_selector import write_topic_candidate_context
from validate_auto_intake_output import validate_paths


DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")
DEFAULT_WIKI = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_completed_job(intake_dir: Path, job_id: str) -> dict[str, Any]:
    for path in sorted((intake_dir / "auto_jobs" / "completed").glob("*.json")):
        payload = read_json(path)
        if str(payload.get("job_id") or "") == job_id:
            return payload
    raise FileNotFoundError(f"completed job not found: {job_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rerun topic routing validation for one completed auto-intake job.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--wiki-hub", type=Path, default=DEFAULT_WIKI)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    intake_dir = args.intake_dir.expanduser().resolve()
    wiki_hub = args.wiki_hub.expanduser().resolve()
    job = find_completed_job(intake_dir, args.job_id)
    artifacts = job.get("artifacts") or {}
    article_path = Path(str(artifacts.get("article_path") or ""))
    result_path = Path(str(artifacts.get("result_path") or ""))
    claim_path = Path(str(artifacts.get("claim_ledger_path") or ""))
    if not article_path.exists() or not result_path.exists() or not claim_path.exists():
        raise FileNotFoundError("job artifacts are incomplete")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    candidate_path = args.out.with_suffix(".topic_candidates.json")
    context = write_topic_candidate_context(
        wiki_hub=wiki_hub,
        intake_dir=intake_dir,
        job=job,
        article_path=article_path,
        output_path=candidate_path,
    )
    validation = validate_paths(
        result_path,
        claim_path,
        allowed_topics_path=candidate_path,
        job_path=Path(str(job.get("job_path") or "")) if str(job.get("job_path") or "") else None,
    )
    payload = {
        "schema_version": "topic-routing-rerun.v1",
        "job_id": args.job_id,
        "article_title": job.get("title", ""),
        "old_primary_topic_id": ((read_json(Path(str(artifacts.get("apply_result_path")))).get("routing_decision") or {}).get("resolved_topic_id") if artifacts.get("apply_result_path") else ""),
        "candidate_topics": context.get("visible_candidate_topics", []),
        "resolver_decision": validation,
        "would_apply": False,
        "side_effects": {
            "modified_obsidian_source": False,
            "modified_wiki_hub": False,
            "modified_intake_state": False,
            "called_llm": False,
        },
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
