"""Shared project-scoped data loaders for Phase 2 workspace views."""

from __future__ import annotations

from ...models.task import TaskManager
from ..graph_access_service import GRAPH_BACKEND_LOCAL, empty_graph_data, load_graph_data_by_backend


def load_phase1_task_result(project) -> dict:
    """Return the best available Phase 1 result, preferring live task memory."""
    persisted = dict(project.phase1_task_result or {})
    if not project.graph_build_task_id:
        return persisted

    task = TaskManager().get_task(project.graph_build_task_id)
    if not task or not task.result:
        return persisted
    return dict(task.result)


def load_graph_data(graph_id: str | None) -> dict:
    """Load graph data from the current local-first runtime path."""
    if not graph_id:
        return empty_graph_data(graph_id)

    try:
        return load_graph_data_by_backend(graph_id, backend=GRAPH_BACKEND_LOCAL)
    except Exception:
        return empty_graph_data(graph_id)
