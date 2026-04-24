"""Flag projects where the effective domain doesn't match the ontology
family of its extracted concepts.

Follow-up to v3 domain-scoped ontology (GPT priority C, 2026-04-23).

A project can end up with effective_domain=methodology but concepts typed
under the tech ontology (Solution/Architecture/Mechanism/Technology/etc.)
if it was created before v3 and later re-classified. Downstream
statistics (core_count / reading_structure / theme summarization) will be
polluted by the wrong-family types.

This script adds `concepts_domain_mismatch: true` to project.json for
every project where the effective domain disagrees with the concepts'
ontology family. The flag is a signal only — it does NOT re-extract.

Ontology families (distinctive types, v3):
- tech family distinctive types: Architecture, Solution, Technology,
  Mechanism, Layer, Decision, Metric, Evidence, Insight
- methodology family distinctive types: Principle, Method, Step,
  Antipattern, Case, Signal
- Shared (ambiguous): Topic, Problem, Example

Rule: family = domain with the most distinctive-type concepts. Ties go to
tech (tech-safe default).

Usage:
    python scripts/flag_domain_mismatch.py           # dry-run
    python scripts/flag_domain_mismatch.py --apply   # actually flag
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECTS_DIR = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects")

TECH_DISTINCTIVE = {
    "Architecture", "Solution", "Technology", "Mechanism",
    "Layer", "Decision", "Metric", "Evidence", "Insight",
}
METHODOLOGY_DISTINCTIVE = {
    "Principle", "Method", "Step", "Antipattern", "Case", "Signal",
}


def resolve_effective_domain(project: dict) -> str:
    """Match the resolution logic used by pipeline_runner."""
    metadata = project.get("ontology_metadata") or {}
    dom = metadata.get("resolved_domain") or project.get("domain") or "tech"
    if dom == "auto":
        dom = "tech"
    return dom


def ontology_family(project: dict) -> tuple[str, dict]:
    """Return (family, counts) where family in {tech, methodology, ambiguous}."""
    items = (project.get("concept_decisions") or {}).get("items", {})
    tech_count = 0
    meth_count = 0
    for key, item in items.items():
        if item.get("status") != "accepted":
            continue
        ctype = key.split(":", 1)[0]
        if ctype in TECH_DISTINCTIVE:
            tech_count += 1
        elif ctype in METHODOLOGY_DISTINCTIVE:
            meth_count += 1

    counts = {"tech_distinctive": tech_count, "methodology_distinctive": meth_count}
    if tech_count == 0 and meth_count == 0:
        return "ambiguous", counts
    if tech_count > meth_count:
        return "tech", counts
    if meth_count > tech_count:
        return "methodology", counts
    return "ambiguous", counts  # tie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    mismatches = []
    matches = []
    ambiguous = []
    no_concepts = []
    for proj_dir in sorted(PROJECTS_DIR.glob("proj_*")):
        meta_path = proj_dir / "project.json"
        if not meta_path.exists():
            continue
        project = json.loads(meta_path.read_text())
        pid = project.get("project_id", proj_dir.name)
        pname = (project.get("name") or "")[:30]

        effective = resolve_effective_domain(project)
        family, counts = ontology_family(project)

        if family == "ambiguous":
            if counts["tech_distinctive"] == 0 and counts["methodology_distinctive"] == 0:
                no_concepts.append((pid, pname, effective))
            else:
                ambiguous.append((pid, pname, effective, counts))
            continue

        if family != effective:
            mismatches.append({
                "project_id": pid,
                "name": pname,
                "effective_domain": effective,
                "ontology_family": family,
                "counts": counts,
            })
        else:
            matches.append((pid, pname, effective))

    print(f"Scanned {len(mismatches) + len(matches) + len(ambiguous) + len(no_concepts)} projects\n")
    print(f"✅ Match (effective_domain == family): {len(matches)}")
    print(f"❌ MISMATCH (need flag): {len(mismatches)}")
    print(f"◯ Ambiguous (tied counts): {len(ambiguous)}")
    print(f"— No distinctive-type concepts: {len(no_concepts)}")
    print()

    if mismatches:
        print("MISMATCH detail:")
        print(f"{'project_id':24s} | {'effective':12s} | {'family':12s} | tech/meth | name")
        for m in mismatches:
            c = m["counts"]
            print(f"{m['project_id']:24s} | {m['effective_domain']:12s} | {m['ontology_family']:12s} | {c['tech_distinctive']}/{c['methodology_distinctive']:<4d}    | {m['name']}")
        print()

    if args.apply:
        flagged = 0
        for m in mismatches:
            meta_path = PROJECTS_DIR / m["project_id"] / "project.json"
            project = json.loads(meta_path.read_text())
            project["concepts_domain_mismatch"] = True
            project["concepts_domain_mismatch_detail"] = {
                "effective_domain": m["effective_domain"],
                "ontology_family": m["ontology_family"],
                "counts": m["counts"],
                "note": "Project's effective domain differs from the ontology family of its "
                        "extracted concepts. Downstream stats may be polluted. "
                        "Consider re-submitting the URL to re-extract under current v3.",
            }
            meta_path.write_text(json.dumps(project, ensure_ascii=False, indent=2))
            flagged += 1
        print(f"✅ Flagged {flagged} projects with concepts_domain_mismatch=true")
    else:
        print("(dry-run — pass --apply to flag)")


if __name__ == "__main__":
    main()
