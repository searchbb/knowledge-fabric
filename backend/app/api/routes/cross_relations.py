"""Cross-article concept relation routes (L3 discovery layer).

All endpoints live under the ``registry_bp`` blueprint, mounted at
``/api/registry``.
"""

from __future__ import annotations

from flask import jsonify, request

from .. import registry_bp
from ...services.registry.cross_concept_relations import (
    CrossRelationDuplicateError,
    CrossRelationNotFoundError,
    count_by_entry_batch,
    create_relation,
    get_relation,
    list_relations,
    soft_delete_relation,
    theme_summary,
    update_relation,
)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@registry_bp.route("/cross-relations", methods=["GET"])
def list_cross_relations():
    """List cross-concept relations with rich filtering."""
    entry_id = request.args.get("entry_id")
    theme_id = request.args.get("theme_id")
    relation_type = request.args.get("relation_type")
    min_confidence = request.args.get("min_confidence", type=float)
    source = request.args.get("source")
    review_status = request.args.get("review_status")
    status = request.args.get("status", "active")
    sort = request.args.get("sort", "confidence_desc")

    results = list_relations(
        entry_id=entry_id,
        theme_id=theme_id,
        relation_type=relation_type,
        min_confidence=min_confidence,
        source=source,
        review_status=review_status,
        status=status,
        sort=sort,
    )
    return jsonify({"success": True, "data": results, "total": len(results)})


@registry_bp.route("/cross-relations/<relation_id>", methods=["GET"])
def get_cross_relation(relation_id: str):
    """Get a single cross relation."""
    try:
        rel = get_relation(relation_id)
        return jsonify({"success": True, "data": rel})
    except CrossRelationNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/cross-relations", methods=["POST"])
def create_cross_relation():
    """Create a new cross-concept relation."""
    body = request.get_json(force=True)
    try:
        rel = create_relation(
            source_entry_id=body.get("source_entry_id", ""),
            target_entry_id=body.get("target_entry_id", ""),
            relation_type=body.get("relation_type", ""),
            directionality=body.get("directionality", "directed"),
            reason=body.get("reason", ""),
            evidence_bridge=body.get("evidence_bridge", ""),
            evidence_refs=body.get("evidence_refs"),
            discovery_path=body.get("discovery_path"),
            confidence=body.get("confidence", 0.5),
            source=body.get("source", "manual"),
            theme_id=body.get("theme_id"),
            model_info=body.get("model_info"),
            actor_id=body.get("actor_id", "user"),
            run_id=body.get("run_id", ""),
        )
        return jsonify({"success": True, "data": rel}), 201
    except CrossRelationDuplicateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@registry_bp.route("/cross-relations/<relation_id>", methods=["PATCH"])
def patch_cross_relation(relation_id: str):
    """Update fields of a cross relation (PATCH semantics)."""
    body = request.get_json(force=True)
    try:
        rel = update_relation(
            relation_id,
            relation_type=body.get("relation_type"),
            reason=body.get("reason"),
            evidence_bridge=body.get("evidence_bridge"),
            confidence=body.get("confidence"),
            review_status=body.get("review_status"),
            review_note=body.get("review_note"),
            reviewed_by=body.get("reviewed_by"),
            status=body.get("status"),
            actor_id=body.get("actor_id", "user"),
        )
        return jsonify({"success": True, "data": rel})
    except CrossRelationNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@registry_bp.route("/cross-relations/<relation_id>", methods=["DELETE"])
def delete_cross_relation(relation_id: str):
    """Soft-delete a cross relation (sets status=deleted)."""
    try:
        rel = soft_delete_relation(relation_id)
        return jsonify({"success": True, "data": rel})
    except CrossRelationNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Summary & batch queries
# ---------------------------------------------------------------------------


@registry_bp.route("/cross-relations/counts", methods=["POST"])
def cross_relation_counts():
    """Batch count cross relations for multiple entry IDs."""
    body = request.get_json(force=True)
    entry_ids = body.get("entry_ids", [])
    if not entry_ids:
        return jsonify({"success": False, "error": "entry_ids required"}), 400
    counts = count_by_entry_batch(entry_ids)
    return jsonify({"success": True, "data": counts})


@registry_bp.route("/themes/<theme_id>/cross-relations-summary", methods=["GET"])
def get_theme_cross_relations_summary(theme_id: str):
    """Return aggregated summary of cross relations for a theme."""
    summary = theme_summary(theme_id)
    return jsonify({"success": True, "data": summary})


# ---------------------------------------------------------------------------
# Discovery trigger
# ---------------------------------------------------------------------------


@registry_bp.route("/backfill-descriptions", methods=["POST"])
def backfill_descriptions():
    """Backfill empty concept descriptions from article graph summaries."""
    body = request.get_json(force=True) if request.data else {}
    dry_run = body.get("dry_run", False)
    overwrite_degraded = body.get("overwrite_degraded", False)

    from ...services.registry.backfill_descriptions import backfill_all

    try:
        result = backfill_all(dry_run=dry_run, overwrite_degraded=overwrite_degraded)
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@registry_bp.route("/cross-relations/discover", methods=["POST"])
def discover_cross_relations():
    """Trigger LLM-based cross-concept relation discovery.

    Body:
        theme_id: str (required)
        entry_ids: list[str] (optional - limit to specific entries)
        max_pairs: int (optional, default 50)
        min_confidence: float (optional, default 0.6)
        exclude_existing: bool (optional, default true)
    """
    body = request.get_json(force=True)
    theme_id = body.get("theme_id")
    if not theme_id:
        return jsonify({"success": False, "error": "theme_id is required"}), 400

    # Import here to avoid circular imports
    from ...services.auto.cross_concept_discoverer import CrossConceptDiscoverer

    discoverer = CrossConceptDiscoverer()
    try:
        result = discoverer.discover(
            theme_id=theme_id,
            entry_ids=body.get("entry_ids"),
            max_pairs=body.get("max_pairs", 50),
            min_confidence=body.get("min_confidence", 0.6),
            exclude_existing=body.get("exclude_existing", True),
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
