"""Multi-project workspace overview endpoint (Stage M).

Returns a per-project summary with concept alignment coverage,
theme counts, and pending review counts.
"""

from __future__ import annotations

import json
import os
from typing import Any

from flask import jsonify

from .. import registry_bp
from ...config import Config
from ...models.project import ProjectManager
from ...models.task import TaskManager


def _read_json(filename: str) -> dict:
    path = os.path.join(Config.UPLOAD_FOLDER, "projects", filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@registry_bp.route("/overview", methods=["GET"])
def workspace_overview():
    """Multi-project overview with per-project alignment summary."""
    projects = ProjectManager.list_projects(limit=200)

    # Load global stores once
    concept_registry = _read_json("concept_registry.json")
    review_tasks_store = _read_json("review_tasks.json")
    evolution_store = _read_json("evolution_log.json")

    # Build reverse index: project_id → linked concept count
    linked_by_project: dict[str, int] = {}
    for entry in (concept_registry.get("entries") or {}).values():
        for link in entry.get("source_links", []):
            pid = link.get("project_id", "")
            if pid:
                linked_by_project[pid] = linked_by_project.get(pid, 0) + 1

    # Review task counts by project
    review_by_project: dict[str, int] = {}
    for task in (review_tasks_store.get("tasks") or {}).values():
        if task.get("status") in ("open", "claimed", "reopened"):
            pid = task.get("project_id", "")
            if pid:
                review_by_project[pid] = review_by_project.get(pid, 0) + 1

    # Recent evolution events by project (last 30 days worth, simplified to count)
    evo_by_project: dict[str, int] = {}
    for evt in (evolution_store.get("events") or []):
        pid = evt.get("project_id", "")
        if pid:
            evo_by_project[pid] = evo_by_project.get(pid, 0) + 1

    task_manager = TaskManager()

    summaries: list[dict[str, Any]] = []
    for project in projects:
        pid = project.project_id
        decisions = (project.concept_decisions or {}).get("items") or {}
        accepted = sum(1 for d in decisions.values() if d.get("status") in ("accepted", "canonical"))
        clusters = list(project.theme_clusters or [])
        status = project.status.value if hasattr(project.status, "value") else str(project.status)

        # When the project is still in graph_building, the flat concept_count
        # will sit at 0 for the entire build window (concept_decisions is only
        # populated post-build). Surface the live task progress so the overview
        # row doesn't look identical to a finished-with-zero-concepts project.
        build_progress = None
        build_message = None
        build_task_status = None
        if status == "graph_building" and project.graph_build_task_id:
            task = task_manager.get_task(project.graph_build_task_id)
            if task is not None:
                build_progress = task.progress
                build_message = task.message
                build_task_status = task.status.value

        summaries.append({
            "project_id": pid,
            "project_name": project.name,
            "status": status,
            "updated_at": project.updated_at,
            "concept_count": len(decisions),
            "accepted_concept_count": accepted,
            "linked_concept_count": linked_by_project.get(pid, 0),
            "alignment_coverage": round(linked_by_project.get(pid, 0) / accepted, 2) if accepted else 0,
            "theme_cluster_count": len(clusters),
            "pending_review_count": review_by_project.get(pid, 0),
            "evolution_event_count": evo_by_project.get(pid, 0),
            "build_progress": build_progress,
            "build_message": build_message,
            "build_task_status": build_task_status,
        })

    # Global stats
    total_registry = len((concept_registry.get("entries") or {}))
    total_themes = len((_read_json("global_themes.json").get("themes") or {}))
    total_reviews = sum(1 for t in (review_tasks_store.get("tasks") or {}).values()
                        if t.get("status") in ("open", "claimed", "reopened"))

    return jsonify({
        "success": True,
        "data": {
            "projects": summaries,
            "project_count": len(summaries),
            "global_stats": {
                "registry_entries": total_registry,
                "global_themes": total_themes,
                "pending_reviews": total_reviews,
                "total_evolution_events": len(evolution_store.get("events") or []),
            },
        },
    })
