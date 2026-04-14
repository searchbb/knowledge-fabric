"""Global knowledge evolution log.

Stage K: an append-only event log tracking concept/theme lifecycle across
projects. Per GPT advice: separate evolution_log.json — main registry files
stay as current-state, this file holds history.

Storage: ``<PROJECTS_DIR>/evolution_log.json``
"""

from __future__ import annotations

import json
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Any

from ...config import Config


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_LOG_FILENAME = "evolution_log.json"


def _log_path() -> str:
    projects_dir = os.path.join(Config.UPLOAD_FOLDER, "projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.join(projects_dir, _LOG_FILENAME)


def _load_log() -> dict[str, Any]:
    path = _log_path()
    if not os.path.exists(path):
        return {"version": 1, "events": []}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("version", 1)
    data.setdefault("events", [])
    return data


def _save_log(data: dict[str, Any]) -> None:
    path = _log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = {
    "created",
    "updated",
    "deleted",
    "linked",
    "unlinked",
    "merged",
    "archived",
    "concept_attached",
    "concept_detached",
    "cluster_linked",
    "cluster_unlinked",
    # auto pipeline event types (added 2026-04-11)
    # Note: there is intentionally NO ``theme_auto_attached``. Attach
    # actions (auto or manual) now emit ``concept_attached`` via the
    # service layer, distinguished by ``actor_type`` in the event record.
    "concept_auto_accepted",
    "canonical_auto_created",
    "canonical_auto_linked",
    "cross_type_match_flagged",
    "theme_auto_created",
    "theme_auto_reused",
    "auto_run_summary",
}

VALID_ENTITY_TYPES = {
    "concept_entry",
    "global_theme",
    "project_concept",
    "project_cluster",
    # auto pipeline entity types (added 2026-04-11)
    "auto_run",
}

# Default audit fields used when callers do not pass actor info — preserves
# backwards compatibility with existing emit_event() callers in the registry
# and theme services.
DEFAULT_ACTOR_TYPE = "human"
DEFAULT_ACTOR_ID = ""
DEFAULT_SOURCE = "workspace_ui"


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------


def emit_event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    entity_name: str = "",
    project_id: str = "",
    details: dict[str, Any] | None = None,
    actor_type: str = DEFAULT_ACTOR_TYPE,
    actor_id: str = DEFAULT_ACTOR_ID,
    run_id: str = "",
    source: str = DEFAULT_SOURCE,
) -> dict[str, Any]:
    """Append a single event to the evolution log.

    Returns the created event record.

    Audit fields (added 2026-04-11):
    - ``actor_type``: ``"auto"`` for events emitted by the auto pipeline,
      ``"human"`` for events emitted by interactive UI / direct API.
    - ``actor_id``: opaque identifier of the actor (e.g. ``auto_pipeline``,
      a username, or empty).
    - ``run_id``: when actor_type is ``"auto"``, the per-URL run identifier
      so multiple events from one auto run can be grouped.
    - ``source``: where the event originated. Known values:
      ``auto_url_pipeline``, ``workspace_ui``, ``api_direct``.

    Existing callers that do not pass these fields get the human/UI defaults
    so backwards compatibility is preserved.
    """
    log = _load_log()
    event: dict[str, Any] = {
        "event_id": f"evt_{uuid_mod.uuid4().hex[:10]}",
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "project_id": project_id,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "run_id": run_id,
        "source": source,
    }
    log["events"].append(event)
    _save_log(log)
    return event


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_global_feed(
    *,
    limit: int = 50,
    offset: int = 0,
    entity_type: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    """Global activity feed (newest first, paginated)."""
    log = _load_log()
    events = list(reversed(log["events"]))

    if entity_type:
        events = [e for e in events if e.get("entity_type") == entity_type]
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]

    total = len(events)
    page = events[offset : offset + limit]
    return {"events": page, "total": total, "offset": offset, "limit": limit}


def get_entity_timeline(
    entity_type: str,
    entity_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Timeline for a specific entity (newest first)."""
    log = _load_log()
    events = [
        e
        for e in reversed(log["events"])
        if e.get("entity_type") == entity_type and e.get("entity_id") == entity_id
    ]
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "events": events[:limit],
        "total": len(events),
    }


def get_project_feed(
    project_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Project-scoped activity feed (includes events referencing this project)."""
    log = _load_log()
    events = [
        e
        for e in reversed(log["events"])
        if e.get("project_id") == project_id
    ]
    total = len(events)
    page = events[offset : offset + limit]
    return {"project_id": project_id, "events": page, "total": total, "offset": offset, "limit": limit}
