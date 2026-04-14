"""Global review task queue.

Stage L: a JSON-backed review task queue for human review of concepts,
themes, and alignments. Per GPT advice: separate review_tasks.json from
evolution_log.json — tasks are current workflow state, log is history.

Storage: ``<PROJECTS_DIR>/review_tasks.json``
"""

from __future__ import annotations

import json
import os
import uuid as uuid_mod
from collections import Counter
from datetime import datetime
from typing import Any

from ...config import Config


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_TASKS_FILENAME = "review_tasks.json"


def _tasks_path() -> str:
    projects_dir = os.path.join(Config.UPLOAD_FOLDER, "projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.join(projects_dir, _TASKS_FILENAME)


def _load_tasks() -> dict[str, Any]:
    path = _tasks_path()
    if not os.path.exists(path):
        return {"version": 1, "tasks": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("version", 1)
    data.setdefault("tasks", {})
    return data


def _save_tasks(data: dict[str, Any]) -> None:
    path = _tasks_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReviewTaskNotFoundError(KeyError):
    pass


class ReviewTaskStateError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Valid states & transitions
# ---------------------------------------------------------------------------

VALID_STATUSES = {"open", "claimed", "resolved", "reopened"}
VALID_RESOLUTIONS = {"approved", "rejected", "deferred", ""}
VALID_ACTIONS = {
    "confirm_link", "review_merge", "verify_alignment",
    "approve_theme", "review_concept", "custom",
}
VALID_PRIORITIES = {"low", "normal", "high"}

# Allowed transitions: current_status → set of next statuses
_TRANSITIONS: dict[str, set[str]] = {
    "open": {"claimed", "resolved"},
    "claimed": {"resolved", "open"},  # can unclaim back to open
    "resolved": {"reopened"},
    "reopened": {"claimed", "resolved"},
}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_task(
    *,
    entity_type: str,
    entity_id: str,
    entity_name: str = "",
    action_required: str = "custom",
    priority: str = "normal",
    project_id: str = "",
    note: str = "",
) -> dict[str, Any]:
    store = _load_tasks()
    now = datetime.now().isoformat()
    task_id = f"rtask_{uuid_mod.uuid4().hex[:10]}"

    task: dict[str, Any] = {
        "task_id": task_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "action_required": action_required if action_required in VALID_ACTIONS else "custom",
        "status": "open",
        "priority": priority if priority in VALID_PRIORITIES else "normal",
        "project_id": project_id,
        "note": note,
        "resolution": "",
        "created_at": now,
        "updated_at": now,
        "resolved_at": "",
    }

    store["tasks"][task_id] = task
    _save_tasks(store)

    from .evolution_log import emit_event
    emit_event(
        event_type="review_task_created", entity_type=entity_type,
        entity_id=entity_id, entity_name=entity_name,
        project_id=project_id,
        details={"task_id": task_id, "action_required": action_required},
    )

    return task


def get_task(task_id: str) -> dict[str, Any]:
    store = _load_tasks()
    task = store["tasks"].get(task_id)
    if not task:
        raise ReviewTaskNotFoundError(f"审核任务不存在: {task_id}")
    return task


def list_tasks(
    *,
    status: str | None = None,
    entity_type: str | None = None,
    project_id: str | None = None,
    priority: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    store = _load_tasks()
    tasks = list(store["tasks"].values())

    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if entity_type:
        tasks = [t for t in tasks if t.get("entity_type") == entity_type]
    if project_id:
        tasks = [t for t in tasks if t.get("project_id") == project_id]
    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority]

    # Sort: high priority first, then by created_at desc
    priority_order = {"high": 0, "normal": 1, "low": 2}
    tasks.sort(key=lambda t: (priority_order.get(t.get("priority", "normal"), 1), t.get("created_at", "")))
    tasks.reverse()  # newest first within same priority

    total = len(tasks)
    page = tasks[offset : offset + limit]
    return {"tasks": page, "total": total, "offset": offset, "limit": limit}


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    resolution: str | None = None,
    note: str | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    store = _load_tasks()
    task = store["tasks"].get(task_id)
    if not task:
        raise ReviewTaskNotFoundError(f"审核任务不存在: {task_id}")

    if status:
        current = task["status"]
        allowed = _TRANSITIONS.get(current, set())
        if status not in allowed:
            raise ReviewTaskStateError(
                f"不允许的状态转换: {current} → {status}（允许: {allowed}）"
            )
        task["status"] = status
        if status == "resolved":
            task["resolved_at"] = datetime.now().isoformat()

    if resolution is not None:
        task["resolution"] = resolution
    if note is not None:
        task["note"] = note
    if priority and priority in VALID_PRIORITIES:
        task["priority"] = priority

    task["updated_at"] = datetime.now().isoformat()
    _save_tasks(store)

    from .evolution_log import emit_event
    emit_event(
        event_type=f"review_task_{status or 'updated'}",
        entity_type=task["entity_type"],
        entity_id=task["entity_id"],
        entity_name=task["entity_name"],
        project_id=task.get("project_id", ""),
        details={"task_id": task_id, "resolution": task.get("resolution", "")},
    )

    return task


# ---------------------------------------------------------------------------
# Batch resolve
# ---------------------------------------------------------------------------


def batch_resolve(
    task_ids: list[str],
    *,
    resolution: str = "approved",
    note: str = "",
) -> dict[str, Any]:
    store = _load_tasks()
    now = datetime.now().isoformat()
    resolved_ids: list[str] = []
    skipped_ids: list[str] = []

    for tid in task_ids:
        task = store["tasks"].get(tid)
        if not task:
            skipped_ids.append(tid)
            continue
        current = task["status"]
        if current not in ("open", "claimed", "reopened"):
            skipped_ids.append(tid)
            continue
        task["status"] = "resolved"
        task["resolution"] = resolution
        task["resolved_at"] = now
        task["updated_at"] = now
        if note:
            task["note"] = note
        resolved_ids.append(tid)

    _save_tasks(store)

    from .evolution_log import emit_event
    if resolved_ids:
        emit_event(
            event_type="review_task_batch_resolved",
            entity_type="review_queue",
            entity_id="batch",
            details={"resolved_ids": resolved_ids, "resolution": resolution, "count": len(resolved_ids)},
        )

    return {
        "resolved": resolved_ids,
        "skipped": skipped_ids,
        "resolved_count": len(resolved_ids),
        "skipped_count": len(skipped_ids),
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_stats() -> dict[str, Any]:
    store = _load_tasks()
    tasks = list(store["tasks"].values())
    status_counts = Counter(t.get("status", "unknown") for t in tasks)
    priority_counts = Counter(t.get("priority", "normal") for t in tasks)
    entity_type_counts = Counter(t.get("entity_type", "unknown") for t in tasks)

    return {
        "total": len(tasks),
        "by_status": dict(status_counts),
        "by_priority": dict(priority_counts),
        "by_entity_type": dict(entity_type_counts),
    }
