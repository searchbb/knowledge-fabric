"""Regenerate reading_structure for an existing project using current code.

Use case: legacy projects processed before the reading_structure_extractor
domain-aware fix (commit b182b6f) have group_titles/backbone labels
baked in tech-era schema (Layer/Mechanism/Technology/...). For
methodology projects these are semantically wrong.

This script:
- reads project.json + extracted_text.txt + graph_data
- re-invokes ReadingStructureExtractor.extract(..., domain=<project's domain>)
- writes the new reading_structure back to project.json

Does NOT rebuild graph, re-extract concepts, or re-run proposer.

Usage:
    python scripts/regen_reading_structure.py <project_id> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/mac/Downloads/code/knowledge-fabric/backend")

from app.services.reading_structure_extractor import ReadingStructureExtractor


PROJECTS_DIR = Path("/Users/mac/Downloads/code/knowledge-fabric/backend/uploads/projects")


def _load_graph_data(project_id: str, graph_id: str) -> dict:
    """Best-effort load of graph nodes/edges. Returns empty dict if not
    available — the extractor can still run with ontology + document text."""
    # Graph data lives in Neo4j for live projects; reading_structure only
    # needs ontology + text + a brief digest, so missing graph is tolerable.
    # If project.json has cached phase1_task_result.artifacts.graph, use it.
    return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    meta_path = PROJECTS_DIR / args.project_id / "project.json"
    project = json.loads(meta_path.read_text())

    domain = (project.get("ontology_metadata") or {}).get("resolved_domain") or project.get("domain") or "tech"
    if domain == "auto":
        domain = "tech"

    text_path = PROJECTS_DIR / args.project_id / "extracted_text.txt"
    document_text = text_path.read_text() if text_path.exists() else ""

    print(f"=== Regen reading_structure for {args.project_id} ===")
    print(f"name: {project.get('name')}")
    print(f"domain: {domain}")
    print(f"ontology entity_types: {[e.get('name') for e in (project.get('ontology') or {}).get('entity_types', [])]}")
    print(f"old group_titles: {(project.get('reading_structure') or {}).get('group_titles', {})}")
    print()

    extractor = ReadingStructureExtractor()
    result = extractor.extract(
        project_name=project.get("name", ""),
        document_text=document_text,
        analysis_summary=project.get("analysis_summary") or "",
        ontology=project.get("ontology") or {},
        graph_data=_load_graph_data(args.project_id, project.get("graph_id", "")),
        simulation_requirement=project.get("simulation_requirement") or "",
        domain=domain,
    )

    print("=== NEW reading_structure ===")
    print(f"title: {result.get('title')}")
    print(f"summary: {result.get('summary')}")
    for key in ("problem", "solution", "architecture"):
        s = result.get(key) or {}
        print(f"{key}: {s.get('title','')!r} — {s.get('summary','')[:60]}")
    print(f"group_titles: {result.get('group_titles', {})}")
    print(f"article_sections: {result.get('article_sections', [])[:5]}")
    print()

    if args.dry_run:
        print("(dry-run — pass without --dry-run to write)")
        return

    project["reading_structure"] = result
    meta_path.write_text(json.dumps(project, ensure_ascii=False, indent=2))
    print(f"✅ Wrote updated reading_structure to {meta_path}")


if __name__ == "__main__":
    main()
