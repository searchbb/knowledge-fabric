"""Legacy Phase 1 snapshot backfill helpers.

These helpers intentionally infer only the minimum stable contract needed by
Phase 2 workspace pages when an older project predates persisted
``phase1_task_result`` storage.
"""

from __future__ import annotations

import os
from typing import Any

from ...models.project import ProjectStatus
from .phase1_build_support import _build_phase1_task_result

LEGACY_PHASE1_SNAPSHOT_SOURCE = "legacy_project_backfill"
ORPHANED_PHASE1_SNAPSHOT_SOURCE = "orphaned_graph_build_recovery"


def _infer_provider(project) -> str:
    return "unknown"


def _infer_build_outcome(project) -> dict[str, Any] | None:
    if project.status == ProjectStatus.GRAPH_COMPLETED:
        return {
            "status": "completed",
            "reason": "legacy project snapshot inferred from persisted project metadata",
            "success_ratio": 1.0,
            "can_generate_reading_structure": bool(project.graph_id or project.reading_structure),
            "warnings": [],
        }

    if project.status == ProjectStatus.FAILED:
        return {
            "status": "failed",
            "reason": str(project.error or "legacy project stored a failed Phase 1 status"),
            "success_ratio": 0.0,
            "can_generate_reading_structure": False,
            "warnings": [],
        }

    return None


def _infer_reading_structure_status(project, build_outcome: dict[str, Any]) -> dict[str, str]:
    if project.reading_structure:
        return {
            "status": "generated",
            "reason": "reading structure restored from persisted project metadata",
            "error_kind": "",
        }

    if build_outcome.get("status") == "failed":
        return {
            "status": "skipped",
            "reason": "legacy project ended in failed state before a persisted reading-structure snapshot was available",
            "error_kind": "",
        }

    return {
        "status": "skipped",
        "reason": "legacy project has no persisted reading-structure snapshot",
        "error_kind": "",
    }


def build_orphaned_graph_build_recovery(project) -> dict[str, Any] | None:
    """Recover a graph-building project whose in-memory task record vanished.

    This happens when the Flask process restarts while a daemon build thread is
    running. The graph may already exist in Neo4j, but the task record and
    final project status are both lost because they only lived in memory.
    """
    if getattr(project, "phase1_task_result", None):
        return None

    if project.status != ProjectStatus.GRAPH_BUILDING:
        return None

    if not getattr(project, "graph_build_task_id", None):
        return None

    graph_data: dict[str, Any] = {}
    if project.graph_id:
        try:
            from ..graph_access_service import GRAPH_BACKEND_LOCAL, load_graph_data_by_backend

            graph_data = load_graph_data_by_backend(
                project.graph_id,
                backend=GRAPH_BACKEND_LOCAL,
            ) or {}
        except Exception:
            graph_data = {}

    node_count = int(graph_data.get("node_count") or len(graph_data.get("nodes") or []))
    edge_count = int(graph_data.get("edge_count") or len(graph_data.get("edges") or []))
    candidate_count = 0
    if graph_data:
        try:
            from .concept_view_service import build_candidate_concepts

            candidates, _ = build_candidate_concepts(graph_data)
            candidate_count = len(candidates)
        except Exception:
            candidate_count = 0

    diagnostics = {
        "snapshot_source": ORPHANED_PHASE1_SNAPSHOT_SOURCE,
        "orphaned_task_recovery": True,
        "backfill_reason": "graph_build_task_id disappeared from in-memory task store while the project was still graph_building",
        "original_task_id": project.graph_build_task_id,
        "candidate_count": candidate_count,
    }

    if node_count > 0 or edge_count > 0 or candidate_count > 0:
        build_outcome = {
            "status": "completed_with_warnings",
            "reason": (
                "Recovered orphaned graph build after the original in-memory task "
                "state disappeared; persisted graph data is available."
            ),
            "success_ratio": 1.0,
            "can_generate_reading_structure": bool(project.reading_structure),
            "warnings": [
                "原始构建任务状态已丢失；当前结果由持久化图数据恢复。"
            ],
        }
        reading_structure_status = (
            {
                "status": "generated",
                "reason": "reading structure restored from persisted project metadata",
                "error_kind": "",
            }
            if project.reading_structure
            else {
                "status": "skipped",
                "reason": "恢复孤儿构建任务时未发现已持久化的阅读骨架",
                "error_kind": "",
            }
        )
        recovered_status = ProjectStatus.GRAPH_COMPLETED
        recovered_error = None
    else:
        build_outcome = {
            "status": "failed",
            "reason": (
                "Recovered orphaned graph build after the original in-memory task "
                "state disappeared, but no persisted graph data was found."
            ),
            "success_ratio": 0.0,
            "can_generate_reading_structure": False,
            "warnings": [
                "原始构建任务状态已丢失，且当前没有可恢复的图数据。"
            ],
        }
        reading_structure_status = {
            "status": "skipped",
            "reason": "图谱构建任务状态已丢失，且没有可恢复的图数据",
            "error_kind": "",
        }
        recovered_status = ProjectStatus.FAILED
        recovered_error = build_outcome["reason"]

    result = _build_phase1_task_result(
        provider="recovered",
        project_id=project.project_id,
        graph_id=project.graph_id,
        chunk_count=0,
        node_count=node_count,
        edge_count=edge_count,
        diagnostics=diagnostics,
        build_outcome=build_outcome,
        reading_structure_status=reading_structure_status,
        dropped_constraints=[],
    )
    result["build_outcome"]["success_ratio"] = None

    return {
        "project_status": recovered_status,
        "phase1_task_result": result,
        "error": recovered_error,
    }


def build_legacy_phase1_snapshot(project) -> dict[str, Any] | None:
    """Infer a minimal Phase 1 contract for projects created before persistence."""
    if getattr(project, "phase1_task_result", None):
        return dict(project.phase1_task_result or {})

    build_outcome = _infer_build_outcome(project)
    if not build_outcome:
        return None

    reading_structure_status = _infer_reading_structure_status(project, build_outcome)
    result = _build_phase1_task_result(
        provider=_infer_provider(project),
        project_id=project.project_id,
        graph_id=project.graph_id,
        chunk_count=0,
        node_count=0,
        edge_count=0,
        diagnostics={
            "snapshot_source": LEGACY_PHASE1_SNAPSHOT_SOURCE,
            "provider_inferred": True,
            "legacy_backfill": True,
            "backfill_reason": "phase1_task_result was missing and was reconstructed from persisted project metadata",
        },
        build_outcome=build_outcome,
        reading_structure_status=reading_structure_status,
        dropped_constraints=[],
    )
    # Chunk-level success data is unavailable for legacy projects; keep it nullable
    # so the UI can render an honest placeholder instead of a fake percentage.
    result["build_outcome"]["success_ratio"] = None
    return result


def backfill_legacy_phase1_snapshots(
    *,
    project_ids: list[str] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Inspect or persist legacy Phase 1 snapshots for older projects."""
    from ...models.project import ProjectManager

    ProjectManager._ensure_projects_dir()
    target_ids = list(project_ids or sorted(os.listdir(ProjectManager.PROJECTS_DIR)))
    results: list[dict[str, Any]] = []

    for project_id in target_ids:
        project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
        if not project:
            results.append({
                "project_id": project_id,
                "status": "missing",
            })
            continue

        if project.phase1_task_result:
            results.append({
                "project_id": project_id,
                "status": "already_present",
            })
            continue

        snapshot = build_legacy_phase1_snapshot(project)
        if not snapshot:
            results.append({
                "project_id": project_id,
                "status": "not_eligible",
            })
            continue

        if persist:
            project.phase1_task_result = snapshot
            ProjectManager.save_project(project, touch_updated_at=False)

        results.append({
            "project_id": project_id,
            "status": "backfilled" if persist else "would_backfill",
            "provider": snapshot.get("provider"),
            "build_status": (snapshot.get("build_outcome") or {}).get("status"),
        })

    summary = {
        "total": len(results),
        "missing": sum(1 for item in results if item["status"] == "missing"),
        "already_present": sum(1 for item in results if item["status"] == "already_present"),
        "eligible": sum(1 for item in results if item["status"] in {"would_backfill", "backfilled"}),
        "not_eligible": sum(1 for item in results if item["status"] == "not_eligible"),
    }
    return {
        "persisted": persist,
        "summary": summary,
        "projects": results,
    }
