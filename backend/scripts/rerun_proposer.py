"""Re-run AutoThemeProposer against an already-processed project's concepts
with real side effects (writes to global_themes.json and evolution_log).

Use case: a project's original run hit a bug (e.g. core_types mismatch) that
was later fixed; the concepts are already in concept_registry, so we don't
need to rebuild the graph. We only need to re-invoke the proposer with the
post-fix code.

Usage:
    python scripts/rerun_proposer.py <project_id> [--domain methodology]

If --domain is omitted, uses project.json's domain field
(resolved_domain in ontology_metadata wins over declared domain).

Idempotency: if the proposer creates a new theme and attaches concepts,
a second run would attach the same concepts again (noop per attach_concepts
dedupe) or create a duplicate theme. Use with care.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/Users/mac/Downloads/code/knowledge-fabric/backend")

from app.services.auto.theme_proposer import AutoThemeProposer, PROPOSER_VERSION
from app.services.registry import global_concept_registry as cr


def load_project(project_id: str) -> dict:
    path = Path(f"/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects/{project_id}/project.json")
    return json.loads(path.read_text())


def resolve_canonical_ids(project: dict) -> list[str]:
    """Map the project's accepted concept_decisions to canonical entry_ids."""
    items = project.get("concept_decisions", {}).get("items", {})
    all_entries = {e["canonical_name"]: e for e in cr.list_entries()}

    resolved = []
    for key, item in items.items():
        if item.get("status") != "accepted":
            continue
        cname = item.get("canonical_name", "")
        entry = all_entries.get(cname)
        if entry:
            resolved.append(entry["entry_id"])
        else:
            print(f"WARN: canonical_name {cname!r} not in global concept registry — skipping")
    return resolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_id")
    ap.add_argument("--domain", default=None, help="Force domain (tech/methodology); else read from project.json")
    args = ap.parse_args()

    project = load_project(args.project_id)
    project_name = project.get("name", "")

    # Resolve the domain to use
    if args.domain:
        domain = args.domain
    else:
        metadata = project.get("ontology_metadata") or {}
        domain = metadata.get("resolved_domain") or project.get("domain") or "tech"
        if domain == "auto":
            domain = "tech"

    canonical_ids = resolve_canonical_ids(project)

    print(f"=== Re-run proposer for {args.project_id} ===")
    print(f"project_name: {project_name}")
    print(f"proposer_version: {PROPOSER_VERSION}")
    print(f"project_domain: {domain}")
    print(f"canonical concepts: {len(canonical_ids)}")
    print()

    if not canonical_ids:
        print("No canonical concepts — cannot proceed.")
        return 1

    proposer = AutoThemeProposer(project_domain=domain)
    run_id = f"rerun_{uuid.uuid4().hex[:10]}"
    result = proposer.process(
        project_id=args.project_id,
        project_name=project_name,
        new_canonical_ids=canonical_ids,
        run_id=run_id,
        article_title=project_name,
    )

    print(f"action: {result.action}")
    print(f"reason: {result.reason}")
    print()
    print("Audit:")
    for k, v in result.audit.items():
        if isinstance(v, list) and len(v) > 8:
            v = f"{v[:8]}... ({len(result.audit[k])} total)"
        print(f"  {k}: {v}")
    print()

    if result.new_candidate_theme:
        nc = result.new_candidate_theme
        print("NEW THEME CREATED:")
        print(f"  theme_id: {nc.get('theme_id')}")
        print(f"  name: {nc.get('name')}")
        print(f"  description: {nc.get('description', '')}")
        print(f"  attached_count: {nc.get('attached_count', '?')}")

    if result.assignments:
        print(f"\nassignments ({len(result.assignments)}):")
        for a in result.assignments:
            print(f"  [{a.get('role'):9s} {a.get('confidence')}] → {a.get('theme_id')}: {a.get('reason','')[:80]}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
