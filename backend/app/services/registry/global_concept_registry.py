"""Global (cross-project) concept registry.

Stage H: a single JSON-backed canonical concept registry that spans all
projects. Each entry has a stable ID, canonical name, aliases, type, and
a list of links back to the project-scoped concept keys that contributed
to it.

Storage: ``<PROJECTS_DIR>/concept_registry.json``
"""

from __future__ import annotations

import json
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Any

from ...config import Config
from ...services.workspace.concept_normalization import normalize_concept_name


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_REGISTRY_FILENAME = "concept_registry.json"


def _registry_path() -> str:
    projects_dir = os.path.join(Config.UPLOAD_FOLDER, "projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.join(projects_dir, _REGISTRY_FILENAME)


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not os.path.exists(path):
        return {"version": 1, "entries": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("version", 1)
    data.setdefault("entries", {})
    return data


def _save_registry(data: dict[str, Any]) -> None:
    path = _registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class RegistryEntryNotFoundError(KeyError):
    """Raised when a registry entry does not exist."""


class RegistryDuplicateError(ValueError):
    """Raised when a duplicate entry would be created."""


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def list_entries(*, concept_type: str | None = None) -> list[dict[str, Any]]:
    """Return all registry entries, optionally filtered by concept_type."""
    registry = _load_registry()
    entries = list(registry["entries"].values())
    if concept_type:
        entries = [e for e in entries if e.get("concept_type") == concept_type]
    entries.sort(key=lambda e: e.get("canonical_name", "").lower())
    return entries


def get_entry(entry_id: str) -> dict[str, Any]:
    """Return a single registry entry by ID."""
    registry = _load_registry()
    entry = registry["entries"].get(entry_id)
    if not entry:
        raise RegistryEntryNotFoundError(f"注册表条目不存在: {entry_id}")
    return entry


def create_entry(
    *,
    canonical_name: str,
    concept_type: str = "Concept",
    aliases: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Create a new canonical registry entry."""
    canonical_name = canonical_name.strip()
    if not canonical_name:
        raise ValueError("canonical_name 不能为空")

    registry = _load_registry()

    # Duplicate check: same normalized canonical_name + concept_type
    norm = normalize_concept_name(canonical_name)
    for existing in registry["entries"].values():
        if (
            normalize_concept_name(existing["canonical_name"]) == norm
            and existing.get("concept_type") == concept_type
        ):
            raise RegistryDuplicateError(
                f"已存在同名条目: {existing['canonical_name']} (type={concept_type})"
            )

    now = datetime.now().isoformat()
    entry_id = f"canon_{uuid_mod.uuid4().hex[:10]}"
    entry: dict[str, Any] = {
        "entry_id": entry_id,
        "canonical_name": canonical_name,
        "concept_type": concept_type,
        "aliases": list(aliases or []),
        "description": description,
        "source_links": [],
        "created_at": now,
        "updated_at": now,
    }

    registry["entries"][entry_id] = entry
    _save_registry(registry)

    from .evolution_log import emit_event
    emit_event(
        event_type="created", entity_type="concept_entry",
        entity_id=entry_id, entity_name=canonical_name,
    )

    return entry


def update_entry(
    entry_id: str,
    *,
    canonical_name: str | None = None,
    concept_type: str | None = None,
    aliases: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update fields of an existing registry entry."""
    registry = _load_registry()
    entry = registry["entries"].get(entry_id)
    if not entry:
        raise RegistryEntryNotFoundError(f"注册表条目不存在: {entry_id}")

    if canonical_name is not None:
        canonical_name = canonical_name.strip()
        if not canonical_name:
            raise ValueError("canonical_name 不能为空")
        # Duplicate check against others
        norm = normalize_concept_name(canonical_name)
        ctype = concept_type if concept_type is not None else entry.get("concept_type")
        for eid, existing in registry["entries"].items():
            if eid == entry_id:
                continue
            if (
                normalize_concept_name(existing["canonical_name"]) == norm
                and existing.get("concept_type") == ctype
            ):
                raise RegistryDuplicateError(
                    f"已存在同名条目: {existing['canonical_name']} (type={ctype})"
                )
        entry["canonical_name"] = canonical_name

    if concept_type is not None:
        entry["concept_type"] = concept_type
    if aliases is not None:
        entry["aliases"] = list(aliases)
    if description is not None:
        entry["description"] = description

    entry["updated_at"] = datetime.now().isoformat()
    _save_registry(registry)

    from .evolution_log import emit_event
    emit_event(
        event_type="updated", entity_type="concept_entry",
        entity_id=entry_id, entity_name=entry["canonical_name"],
    )

    return entry


def delete_entry(entry_id: str) -> bool:
    """Delete a registry entry. Returns True if it existed."""
    registry = _load_registry()
    if entry_id not in registry["entries"]:
        return False
    deleted_name = registry["entries"][entry_id].get("canonical_name", "")
    del registry["entries"][entry_id]
    _save_registry(registry)

    from .evolution_log import emit_event
    emit_event(
        event_type="deleted", entity_type="concept_entry",
        entity_id=entry_id, entity_name=deleted_name,
    )

    return True


# ---------------------------------------------------------------------------
# Link / unlink project concepts
# ---------------------------------------------------------------------------


def link_project_concept(
    entry_id: str,
    *,
    project_id: str,
    concept_key: str,
    project_name: str = "",
) -> dict[str, Any]:
    """Link a project-scoped concept to a canonical registry entry."""
    registry = _load_registry()
    entry = registry["entries"].get(entry_id)
    if not entry:
        raise RegistryEntryNotFoundError(f"注册表条目不存在: {entry_id}")

    # Avoid duplicate links
    for link in entry["source_links"]:
        if link["project_id"] == project_id and link["concept_key"] == concept_key:
            return entry  # already linked

    entry["source_links"].append({
        "project_id": project_id,
        "concept_key": concept_key,
        "project_name": project_name,
        "linked_at": datetime.now().isoformat(),
    })
    entry["updated_at"] = datetime.now().isoformat()
    _save_registry(registry)

    from .evolution_log import emit_event
    emit_event(
        event_type="linked", entity_type="concept_entry",
        entity_id=entry_id, entity_name=entry["canonical_name"],
        project_id=project_id,
        details={"concept_key": concept_key},
    )

    return entry


def unlink_project_concept(
    entry_id: str,
    *,
    project_id: str,
    concept_key: str,
) -> dict[str, Any]:
    """Remove a project concept link from a registry entry."""
    registry = _load_registry()
    entry = registry["entries"].get(entry_id)
    if not entry:
        raise RegistryEntryNotFoundError(f"注册表条目不存在: {entry_id}")

    entry["source_links"] = [
        link
        for link in entry["source_links"]
        if not (link["project_id"] == project_id and link["concept_key"] == concept_key)
    ]
    entry["updated_at"] = datetime.now().isoformat()
    _save_registry(registry)
    return entry


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_entries(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Search registry by canonical_name and aliases (case-insensitive substring)."""
    norm_query = normalize_concept_name(query)
    if not norm_query:
        return []

    registry = _load_registry()
    scored: list[tuple[float, dict[str, Any]]] = []

    for entry in registry["entries"].values():
        norm_name = normalize_concept_name(entry["canonical_name"])
        # Exact match on canonical
        if norm_name == norm_query:
            scored.append((1.0, entry))
            continue
        # Substring match on canonical
        if norm_query in norm_name:
            scored.append((0.8, entry))
            continue
        # Alias match
        best_alias_score = 0.0
        for alias in entry.get("aliases", []):
            norm_alias = normalize_concept_name(alias)
            if norm_alias == norm_query:
                best_alias_score = max(best_alias_score, 0.9)
            elif norm_query in norm_alias:
                best_alias_score = max(best_alias_score, 0.6)
        if best_alias_score > 0:
            scored.append((best_alias_score, entry))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["canonical_name"].lower()))
    return [entry for _, entry in scored[:limit]]


# ---------------------------------------------------------------------------
# Suggest from project
# ---------------------------------------------------------------------------


def suggest_from_project(
    project_id: str,
) -> dict[str, Any]:
    """Suggest registry entries from a project's accepted concept decisions.

    Returns:
    - ``new_candidates``: concepts that have no matching registry entry
    - ``existing_matches``: concepts that match an existing entry (linkable)
    - ``already_linked``: concepts already linked to a registry entry
    """
    from ...models.project import ProjectManager

    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        raise RegistryEntryNotFoundError(f"项目不存在: {project_id}")

    decisions = (project.concept_decisions or {}).get("items") or {}
    accepted = {
        key: item
        for key, item in decisions.items()
        if item.get("status") in ("accepted", "canonical")
    }

    registry = _load_registry()

    # Build lookups for same-type and cross-type matching.
    norm_to_entry: dict[str, dict[str, Any]] = {}
    norm_to_entries: dict[str, list[dict[str, Any]]] = {}
    for entry in registry["entries"].values():
        norm = normalize_concept_name(entry["canonical_name"])
        ctype = entry.get("concept_type", "Concept")
        norm_to_entry[f"{ctype}:{norm}"] = entry
        norm_to_entries.setdefault(norm, []).append(entry)
        for alias in entry.get("aliases", []):
            norm_alias = normalize_concept_name(alias)
            if norm_alias:
                norm_to_entry[f"{ctype}:{norm_alias}"] = entry
                norm_to_entries.setdefault(norm_alias, []).append(entry)

    # Build a lookup: (project_id, concept_key) → entry_id for already-linked
    linked_set: set[tuple[str, str]] = set()
    for entry in registry["entries"].values():
        for link in entry.get("source_links", []):
            linked_set.add((link["project_id"], link["concept_key"]))

    new_candidates: list[dict[str, Any]] = []
    existing_matches: list[dict[str, Any]] = []
    already_linked: list[dict[str, Any]] = []
    cross_type_matches: list[dict[str, Any]] = []

    for concept_key, item in accepted.items():
        # Parse concept_key = "Label:name"
        parts = concept_key.split(":", 1)
        concept_type = parts[0] if len(parts) == 2 else "Concept"
        raw_name = parts[1] if len(parts) == 2 else concept_key
        display_name = item.get("canonical_name") or raw_name

        if (project_id, concept_key) in linked_set:
            already_linked.append({
                "concept_key": concept_key,
                "display_name": display_name,
                "concept_type": concept_type,
            })
            continue

        # Try to find matching registry entry
        norm = normalize_concept_name(display_name)
        lookup_key = f"{concept_type}:{norm}"
        match = norm_to_entry.get(lookup_key)
        if match:
            existing_matches.append({
                "concept_key": concept_key,
                "display_name": display_name,
                "concept_type": concept_type,
                "matched_entry_id": match["entry_id"],
                "matched_canonical_name": match["canonical_name"],
            })
        else:
            cross_type_entries = [
                entry
                for entry in norm_to_entries.get(norm, [])
                if entry.get("concept_type", "Concept") != concept_type
            ]
            if cross_type_entries:
                seen_entry_ids: set[str] = set()
                for entry in cross_type_entries:
                    entry_id = entry.get("entry_id")
                    if not entry_id or entry_id in seen_entry_ids:
                        continue
                    seen_entry_ids.add(entry_id)
                    cross_type_matches.append({
                        "concept_key": concept_key,
                        "display_name": display_name,
                        "concept_type": concept_type,
                        "matched_entry_id": entry_id,
                        "matched_canonical_name": entry["canonical_name"],
                        "matched_concept_type": entry.get("concept_type", "Concept"),
                    })
            else:
                new_candidates.append({
                    "concept_key": concept_key,
                    "display_name": display_name,
                    "concept_type": concept_type,
                })

    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_accepted": len(accepted),
        "new_candidates": new_candidates,
        "existing_matches": existing_matches,
        "already_linked": already_linked,
        "cross_type_matches": cross_type_matches,
    }


# ---------------------------------------------------------------------------
# Project alignment view
# ---------------------------------------------------------------------------


def get_project_alignment(project_id: str) -> dict[str, Any]:
    """Show how a project's concepts map to registry entries.

    Returns per-concept: linked registry entry (if any), suggestions, and
    unlinked status.
    """
    from ...models.project import ProjectManager

    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        raise RegistryEntryNotFoundError(f"项目不存在: {project_id}")

    decisions = (project.concept_decisions or {}).get("items") or {}
    registry = _load_registry()

    # Reverse index: (project_id, concept_key) → entry
    link_index: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in registry["entries"].values():
        for link in entry.get("source_links", []):
            link_index[(link["project_id"], link["concept_key"])] = entry

    # Normalized lookup for suggestions
    norm_to_entry: dict[str, dict[str, Any]] = {}
    for entry in registry["entries"].values():
        norm = normalize_concept_name(entry["canonical_name"])
        ctype = entry.get("concept_type", "Concept")
        norm_to_entry[f"{ctype}:{norm}"] = entry
        for alias in entry.get("aliases", []):
            norm_alias = normalize_concept_name(alias)
            if norm_alias:
                norm_to_entry[f"{ctype}:{norm_alias}"] = entry

    alignments: list[dict[str, Any]] = []
    linked_count = 0
    suggested_count = 0
    unlinked_count = 0

    for concept_key, item in decisions.items():
        if item.get("status") not in ("accepted", "canonical"):
            continue

        parts = concept_key.split(":", 1)
        concept_type = parts[0] if len(parts) == 2 else "Concept"
        raw_name = parts[1] if len(parts) == 2 else concept_key
        display_name = item.get("canonical_name") or raw_name

        linked_entry = link_index.get((project_id, concept_key))
        if linked_entry:
            alignments.append({
                "concept_key": concept_key,
                "display_name": display_name,
                "concept_type": concept_type,
                "status": "linked",
                "registry_entry_id": linked_entry["entry_id"],
                "registry_canonical_name": linked_entry["canonical_name"],
            })
            linked_count += 1
            continue

        # Try suggestion
        norm = normalize_concept_name(display_name)
        lookup_key = f"{concept_type}:{norm}"
        suggestion = norm_to_entry.get(lookup_key)
        if suggestion:
            alignments.append({
                "concept_key": concept_key,
                "display_name": display_name,
                "concept_type": concept_type,
                "status": "suggested",
                "suggested_entry_id": suggestion["entry_id"],
                "suggested_canonical_name": suggestion["canonical_name"],
            })
            suggested_count += 1
        else:
            alignments.append({
                "concept_key": concept_key,
                "display_name": display_name,
                "concept_type": concept_type,
                "status": "unlinked",
            })
            unlinked_count += 1

    return {
        "project_id": project_id,
        "project_name": project.name,
        "summary": {
            "linked": linked_count,
            "suggested": suggested_count,
            "unlinked": unlinked_count,
            "total": linked_count + suggested_count + unlinked_count,
        },
        "alignments": alignments,
        "registry_total": len(registry["entries"]),
    }
