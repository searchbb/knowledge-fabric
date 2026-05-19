#!/usr/bin/env python3
"""Plan llm-wiki source sync from accepted intake decisions.

This is a dry-run planner. It writes a plan under /Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake and
does not copy sources into topic raw directories.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INTAKE = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake")
DEFAULT_HUB = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub")
TOOL_VERSION = "clippings-intake-llm-wiki-sync-planner-0.1"
LLM_WIKI_DESTINATIONS = {"llm_wiki_only", "both"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# llm-wiki Sync Dry Run",
        "",
        f"- Generated: {plan['generated_at']}",
        f"- Decisions considered: {plan['summary']['decisions_considered']}",
        f"- Planned copies: {plan['summary']['planned_copies']}",
        f"- Blocked: {plan['summary']['blocked']}",
        f"- Skipped: {plan['summary']['skipped']}",
        "",
        "## Side Effects",
        "",
        "- modified_obsidian_source: false",
        "- copied_to_llm_wiki: false",
        "- created_kfc_project: false",
        "- called_llm: false",
        "",
        "## Items",
        "",
        "| Status | Topic | Title | Reason | Target |",
        "|---|---|---|---|---|",
    ]
    for item in plan["items"]:
        target = item.get("planned_raw_path") or ""
        lines.append(
            "| {status} | {topic} | {title} | {reason} | {target} |".format(
                status=item["plan_status"],
                topic=item.get("topic_id", ""),
                title=str(item.get("title", "")).replace("|", "\\|"),
                reason=str(item.get("reason", "")).replace("|", "\\|"),
                target=target.replace("|", "\\|"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def latest_decisions(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_candidate: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        candidate_id = decision.get("candidate_id")
        if not candidate_id:
            continue
        current = by_candidate.get(candidate_id)
        if current is None or str(decision.get("applied_at") or decision.get("decided_at") or "") >= str(
            current.get("applied_at") or current.get("decided_at") or ""
        ):
            by_candidate[candidate_id] = decision
    return list(by_candidate.values())


def slugify(text: str, fallback: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        text = fallback
    return text[:80].strip("-") or fallback


def source_type_to_raw_dir(source_path: str, source_url: str) -> str:
    lower = f"{source_path} {source_url}".lower()
    if ".pdf" in lower or "arxiv.org" in lower:
        return "papers"
    if "github.com" in lower or "gitlab.com" in lower:
        return "repos"
    return "articles"


def build_item(decision: dict[str, Any], hub: Path) -> dict[str, Any]:
    topic_id = decision.get("topic_id") or ""
    source_path = decision.get("source_file_path") or ""
    title = decision.get("title") or decision.get("candidate_id") or "untitled"
    raw_dir = source_type_to_raw_dir(source_path, decision.get("source_url") or "")
    topic_root = hub / "topics" / topic_id if topic_id else None
    slug = slugify(title, decision.get("candidate_id", "source"))
    target = topic_root / "raw" / raw_dir / f"{slug}-{decision.get('candidate_id', 'source')}.md" if topic_root else None

    item = {
        "candidate_id": decision.get("candidate_id"),
        "decision_id": decision.get("decision_id"),
        "apply_batch_id": decision.get("apply_batch_id"),
        "title": title,
        "topic_id": topic_id,
        "gate1_destination": decision.get("gate1_destination"),
        "decision_status": decision.get("decision_status"),
        "source_file_path": source_path,
        "source_exists": Path(source_path).exists() if source_path else False,
        "source_url": decision.get("source_url", ""),
        "content_hash": decision.get("content_hash", ""),
        "raw_category": raw_dir,
        "topic_root": str(topic_root) if topic_root else "",
        "topic_exists": topic_root.exists() if topic_root else False,
        "planned_raw_path": str(target) if target else "",
        "will_copy": False,
        "reason": "",
        "plan_status": "planned",
        "side_effects": {
            "modified_obsidian_source": False,
            "copied_to_llm_wiki": False,
            "created_kfc_project": False,
            "called_llm": False,
        },
    }

    if not topic_id:
        item.update({"plan_status": "blocked", "reason": "missing_topic_id"})
    elif not item["source_exists"]:
        item.update({"plan_status": "blocked", "reason": "source_file_missing"})
    elif not item["topic_exists"]:
        item.update({"plan_status": "blocked", "reason": "topic_missing"})
    else:
        item.update({"plan_status": "ready", "reason": "would_copy_on_explicit_sync", "will_copy": False})
    return item


def build_plan(intake_dir: Path, hub: Path) -> dict[str, Any]:
    decisions_path = intake_dir / "decisions.jsonl"
    decisions = latest_decisions(read_jsonl(decisions_path))
    items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for decision in decisions:
        if decision.get("decision_status") != "accepted":
            skipped.append({"candidate_id": decision.get("candidate_id"), "reason": "decision_not_accepted"})
            continue
        if decision.get("gate1_destination") not in LLM_WIKI_DESTINATIONS:
            skipped.append({"candidate_id": decision.get("candidate_id"), "reason": "destination_not_llm_wiki"})
            continue
        items.append(build_item(decision, hub))

    by_status = defaultdict(int)
    for item in items:
        by_status[item["plan_status"]] += 1

    return {
        "schema_version": "llm-wiki-sync-plan.v1",
        "tool_version": TOOL_VERSION,
        "generated_at": now_iso(),
        "dry_run": True,
        "intake_dir": str(intake_dir),
        "hub": str(hub),
        "decisions_path": str(decisions_path),
        "summary": {
            "decisions_considered": len(decisions),
            "eligible_decisions": len(items),
            "planned_copies": by_status["ready"],
            "blocked": by_status["blocked"],
            "skipped": len(skipped),
            "by_status": dict(sorted(by_status.items())),
        },
        "items": items,
        "skipped": skipped,
        "side_effects": {
            "modified_obsidian_source": False,
            "copied_to_llm_wiki": False,
            "created_kfc_project": False,
            "called_llm": False,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run plan for llm-wiki sync from intake decisions.")
    parser.add_argument("--intake-dir", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--hub", type=Path, default=DEFAULT_HUB)
    parser.add_argument("--plan-json", default="llm-wiki-sync-plan.json")
    parser.add_argument("--plan-md", default="llm-wiki-sync-plan.md")
    parser.add_argument("--no-event", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="Print a dry-run summary without writing plan files or events.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    intake_dir = args.intake_dir.expanduser().resolve()
    hub = args.hub.expanduser().resolve()
    plan = build_plan(intake_dir, hub)
    json_path = intake_dir / args.plan_json
    md_path = intake_dir / args.plan_md
    if not args.check_only:
        write_json(json_path, plan)
        write_markdown(md_path, plan)
    if not args.no_event and not args.check_only:
        append_event(
            intake_dir / "events.jsonl",
            {
                "schema_version": "event.v1",
                "tool_version": TOOL_VERSION,
                "event_type": "llm_wiki_sync_dry_run_planned",
                "event_at": now_iso(),
                "plan_json": str(json_path),
                "plan_md": str(md_path),
                "summary": plan["summary"],
                "dry_run": True,
                "side_effects": plan["side_effects"],
            },
        )
    print(json.dumps({
        "check_only": args.check_only,
        "plan_json": None if args.check_only else str(json_path),
        "plan_md": None if args.check_only else str(md_path),
        "summary": plan["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
