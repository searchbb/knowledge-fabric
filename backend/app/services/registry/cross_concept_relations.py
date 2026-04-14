"""Cross-article concept relations (L3 discovery layer).

Stores semantic bridges between canonical concepts from different articles.
Unlike L2 registry (identity: "these are the same concept"), L3 captures
cross-article *relationships* ("these different concepts are related because...").

Storage: ``<PROJECTS_DIR>/cross_concept_relations.json``
"""

from __future__ import annotations

import json
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Any

from ...config import Config
from .evolution_log import emit_event


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_RELATION_TYPES = {
    "design_inspiration",
    "technical_foundation",
    "problem_solution",
    "contrast_reference",
    "capability_constraint",
    "pattern_reuse",
}

VALID_DIRECTIONALITY = {"directed", "bidirectional"}
VALID_STATUSES = {"active", "deleted", "superseded"}
VALID_REVIEW_STATUSES = {"unreviewed", "accepted", "rejected", "needs_revision"}

_RELATIONS_FILENAME = "cross_concept_relations.json"


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _relations_path() -> str:
    projects_dir = os.path.join(Config.UPLOAD_FOLDER, "projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.join(projects_dir, _RELATIONS_FILENAME)


def _load_relations() -> dict[str, Any]:
    path = _relations_path()
    if not os.path.exists(path):
        return {"version": 1, "relations": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("version", 1)
    data.setdefault("relations", {})
    return data


def _save_relations(data: dict[str, Any]) -> None:
    path = _relations_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CrossRelationNotFoundError(KeyError):
    """Raised when a cross relation does not exist."""


class CrossRelationDuplicateError(ValueError):
    """Raised when a duplicate relation would be created."""


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def list_relations(
    *,
    entry_id: str | None = None,
    theme_id: str | None = None,
    relation_type: str | None = None,
    min_confidence: float | None = None,
    source: str | None = None,
    review_status: str | None = None,
    status: str = "active",
    sort: str = "confidence_desc",
) -> list[dict[str, Any]]:
    """Return cross-concept relations with rich filtering.

    Parameters
    ----------
    entry_id : filter by source OR target entry_id
    theme_id : filter by theme_id
    relation_type : filter by relation_type
    min_confidence : filter by minimum confidence score
    source : filter by source (auto/manual)
    review_status : filter by review_status
    status : filter by status (default: active only)
    sort : sort order (confidence_desc, confidence_asc, created_desc)
    """
    store = _load_relations()
    results: list[dict[str, Any]] = []

    for rel in store["relations"].values():
        # Status filter
        if status and rel.get("status", "active") != status:
            continue
        # Entry filter: match source OR target
        if entry_id and rel.get("source_entry_id") != entry_id and rel.get("target_entry_id") != entry_id:
            continue
        # Theme filter
        if theme_id and rel.get("theme_id") != theme_id:
            continue
        # Relation type filter
        if relation_type and rel.get("relation_type") != relation_type:
            continue
        # Confidence filter
        if min_confidence is not None and (rel.get("confidence") or 0) < min_confidence:
            continue
        # Source filter
        if source and rel.get("source") != source:
            continue
        # Review status filter
        if review_status and rel.get("review_status") != review_status:
            continue

        results.append(rel)

    # Sort
    if sort == "confidence_desc":
        results.sort(key=lambda r: r.get("confidence", 0), reverse=True)
    elif sort == "confidence_asc":
        results.sort(key=lambda r: r.get("confidence", 0))
    elif sort == "created_desc":
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    return results


def get_relation(relation_id: str) -> dict[str, Any]:
    """Return a single cross relation by ID."""
    store = _load_relations()
    rel = store["relations"].get(relation_id)
    if not rel:
        raise CrossRelationNotFoundError(f"跨文章关系不存在: {relation_id}")
    return rel


def create_relation(
    *,
    source_entry_id: str,
    target_entry_id: str,
    relation_type: str,
    directionality: str = "directed",
    reason: str,
    evidence_bridge: str = "",
    evidence_refs: list[dict[str, Any]] | None = None,
    discovery_path: list[str] | None = None,
    confidence: float = 0.5,
    source: str = "manual",
    theme_id: str | None = None,
    model_info: dict[str, str] | None = None,
    actor_id: str = "user",
    run_id: str = "",
) -> dict[str, Any]:
    """Create a new cross-concept relation."""
    # Validate
    if not source_entry_id or not target_entry_id:
        raise ValueError("source_entry_id and target_entry_id are required")
    if source_entry_id == target_entry_id:
        raise ValueError("Cannot create self-referencing relation")
    if relation_type not in VALID_RELATION_TYPES:
        raise ValueError(f"Invalid relation_type: {relation_type}. Must be one of {VALID_RELATION_TYPES}")
    if directionality not in VALID_DIRECTIONALITY:
        raise ValueError(f"Invalid directionality: {directionality}")
    if not reason.strip():
        raise ValueError("reason is required")

    # Dedupe check — also resurrect soft-deleted relations instead of creating duplicates
    dedupe_key = f"{source_entry_id}|{relation_type}|{target_entry_id}"
    store = _load_relations()
    for existing in store["relations"].values():
        if existing.get("dedupe_key") != dedupe_key:
            continue
        if existing.get("status") == "active":
            raise CrossRelationDuplicateError(
                f"Relation already exists: {dedupe_key}"
            )
        if existing.get("status") == "deleted":
            # Resurrect: update fields and set back to active
            now = datetime.now().isoformat()
            existing["status"] = "active"
            existing["review_status"] = "unreviewed"
            existing["reason"] = reason.strip()
            existing["evidence_bridge"] = (evidence_bridge or "").strip()
            existing["evidence_refs"] = evidence_refs or []
            existing["confidence"] = max(0.0, min(1.0, confidence))
            existing["source"] = source
            existing["model_info"] = model_info
            existing["updated_at"] = now
            store["relations"][existing["relation_id"]] = existing
            _save_relations(store)
            emit_event(
                event_type="cross_relation_resurrected",
                entity_type="cross_concept_relation",
                entity_id=existing["relation_id"],
                entity_name=f"{source_entry_id} -> {target_entry_id}",
                details={"dedupe_key": dedupe_key, "new_confidence": confidence},
                actor_type="auto" if source == "auto" else "user",
                actor_id=actor_id,
                run_id=run_id,
                source="cross_concept_relations",
            )
            return existing

    now = datetime.now().isoformat()
    relation_id = f"xrel_{uuid_mod.uuid4().hex[:10]}"

    entry = {
        "relation_id": relation_id,
        "source_entry_id": source_entry_id,
        "target_entry_id": target_entry_id,
        "relation_type": relation_type,
        "directionality": directionality,
        "reason": reason.strip(),
        "evidence_bridge": (evidence_bridge or "").strip(),
        "evidence_refs": evidence_refs or [],
        "discovery_path": discovery_path or [],
        "confidence": max(0.0, min(1.0, confidence)),
        "source": source,
        "status": "active",
        "review_status": "unreviewed",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_note": None,
        "dedupe_key": dedupe_key,
        "theme_id": theme_id,
        "model_info": model_info,
        "created_at": now,
        "updated_at": now,
    }

    store["relations"][relation_id] = entry
    _save_relations(store)

    emit_event(
        event_type="cross_relation_created",
        entity_type="cross_concept_relation",
        entity_id=relation_id,
        entity_name=f"{source_entry_id} -> {target_entry_id}",
        details={
            "relation_type": relation_type,
            "confidence": confidence,
            "source": source,
        },
        actor_type="auto" if source == "auto" else "user",
        actor_id=actor_id,
        run_id=run_id,
        source="cross_concept_relations",
    )

    return entry


def update_relation(
    relation_id: str,
    *,
    relation_type: str | None = None,
    reason: str | None = None,
    evidence_bridge: str | None = None,
    confidence: float | None = None,
    review_status: str | None = None,
    review_note: str | None = None,
    reviewed_by: str | None = None,
    status: str | None = None,
    actor_id: str = "user",
) -> dict[str, Any]:
    """Update fields of an existing cross relation (PATCH semantics)."""
    store = _load_relations()
    rel = store["relations"].get(relation_id)
    if not rel:
        raise CrossRelationNotFoundError(f"跨文章关系不存在: {relation_id}")

    changes: dict[str, Any] = {}

    if relation_type is not None:
        if relation_type not in VALID_RELATION_TYPES:
            raise ValueError(f"Invalid relation_type: {relation_type}")
        changes["relation_type"] = relation_type
        # Update dedupe_key when type changes
        changes["dedupe_key"] = f"{rel['source_entry_id']}|{relation_type}|{rel['target_entry_id']}"

    if reason is not None:
        changes["reason"] = reason.strip()
    if evidence_bridge is not None:
        changes["evidence_bridge"] = evidence_bridge.strip()
    if confidence is not None:
        changes["confidence"] = max(0.0, min(1.0, confidence))

    if review_status is not None:
        if review_status not in VALID_REVIEW_STATUSES:
            raise ValueError(f"Invalid review_status: {review_status}")
        changes["review_status"] = review_status
        changes["reviewed_at"] = datetime.now().isoformat()
        if reviewed_by:
            changes["reviewed_by"] = reviewed_by

    if review_note is not None:
        changes["review_note"] = review_note

    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        changes["status"] = status

    if not changes:
        return rel

    changes["updated_at"] = datetime.now().isoformat()
    rel.update(changes)
    store["relations"][relation_id] = rel
    _save_relations(store)

    emit_event(
        event_type="cross_relation_updated",
        entity_type="cross_concept_relation",
        entity_id=relation_id,
        entity_name=f"{rel['source_entry_id']} -> {rel['target_entry_id']}",
        details={"changes": list(changes.keys())},
        actor_type="user",
        actor_id=actor_id,
        source="cross_concept_relations",
    )

    return rel


def soft_delete_relation(
    relation_id: str,
    *,
    actor_id: str = "user",
) -> dict[str, Any]:
    """Soft-delete a cross relation (set status=deleted)."""
    return update_relation(
        relation_id,
        status="deleted",
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def count_by_entry(entry_id: str) -> int:
    """Count active cross relations involving a given entry."""
    store = _load_relations()
    count = 0
    for rel in store["relations"].values():
        if rel.get("status") != "active":
            continue
        if rel.get("source_entry_id") == entry_id or rel.get("target_entry_id") == entry_id:
            count += 1
    return count


def count_by_entry_batch(entry_ids: list[str]) -> dict[str, int]:
    """Count active cross relations for multiple entries at once."""
    store = _load_relations()
    counts: dict[str, int] = {eid: 0 for eid in entry_ids}
    for rel in store["relations"].values():
        if rel.get("status") != "active":
            continue
        src = rel.get("source_entry_id", "")
        tgt = rel.get("target_entry_id", "")
        if src in counts:
            counts[src] += 1
        if tgt in counts:
            counts[tgt] += 1
    return counts


def theme_summary(theme_id: str) -> dict[str, Any]:
    """Return aggregated summary for a theme's cross relations."""
    rels = list_relations(theme_id=theme_id)

    # Collect unique entry IDs and project IDs
    entry_ids: set[str] = set()
    type_counts: dict[str, int] = {}
    bridge_scores: dict[str, float] = {}  # entry_id -> total confidence

    for r in rels:
        src = r["source_entry_id"]
        tgt = r["target_entry_id"]
        entry_ids.add(src)
        entry_ids.add(tgt)

        rtype = r.get("relation_type", "unknown")
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

        conf = r.get("confidence", 0)
        bridge_scores[src] = bridge_scores.get(src, 0) + conf
        bridge_scores[tgt] = bridge_scores.get(tgt, 0) + conf

    # Top bridge concepts (by total confidence score)
    top_bridges = sorted(bridge_scores.items(), key=lambda x: -x[1])[:5]

    return {
        "theme_id": theme_id,
        "relation_count": len(rels),
        "concept_count": len(entry_ids),
        "type_distribution": type_counts,
        "top_bridge_entry_ids": [eid for eid, _ in top_bridges],
        "top_bridge_scores": {eid: score for eid, score in top_bridges},
    }


def has_dedupe_key(dedupe_key: str, *, active_only: bool = False) -> bool:
    """Check if a dedupe_key already exists.

    By default checks ALL statuses (including deleted), because the
    create_relation() function handles resurrection of deleted relations.
    Pass active_only=True to only match active relations.
    """
    store = _load_relations()
    for rel in store["relations"].values():
        if rel.get("dedupe_key") != dedupe_key:
            continue
        if active_only and rel.get("status") != "active":
            continue
        return True
    return False
