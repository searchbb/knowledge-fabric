"""Project-scoped concept summary routes for Phase 2."""

from __future__ import annotations

from datetime import datetime

from flask import jsonify, request

from .. import concept_bp
from ..schemas.concept import ProjectConceptViewSchema
from ...models.project import ProjectManager
from ...services.workspace.concept_view_service import ConceptViewNotFoundError, ConceptViewService

_VALID_CONCEPT_STATUSES = {"accepted", "rejected", "pending", "merged", "canonical"}


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@concept_bp.route("/projects/<project_id>/view", methods=["GET"])
def get_concept_view(project_id: str):
    """Return a read-only concept summary view for the requested project."""
    try:
        payload = ConceptViewService().build_project_view(project_id)
        schema = ProjectConceptViewSchema(**payload)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except ConceptViewNotFoundError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception as error:  # pragma: no cover - defensive route guard
        return jsonify({"success": False, "error": str(error)}), 500


@concept_bp.route("/projects/<project_id>/decisions/<path:concept_key>", methods=["PUT"])
def put_concept_decision(project_id: str, concept_key: str):
    """Persist a single concept candidate decision."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if not status or status not in _VALID_CONCEPT_STATUSES:
        return jsonify({"success": False, "error": f"status 必须是 {_VALID_CONCEPT_STATUSES} 之一"}), 400

    decisions = project.concept_decisions or {"version": 1, "items": {}}
    decisions.setdefault("version", 1)
    decisions.setdefault("items", {})
    item_data = {
        "status": status,
        "note": str(body.get("note") or ""),
        "canonical_name": str(body.get("canonical_name") or ""),
        "updated_at": datetime.now().isoformat(),
    }
    # F2 merge fields (optional)
    if body.get("merge_to"):
        item_data["merge_to"] = str(body["merge_to"])
    if body.get("aliases"):
        item_data["aliases"] = list(body["aliases"])
    decisions["items"][concept_key] = item_data
    project.concept_decisions = decisions
    ProjectManager.save_project(project)

    return jsonify({"success": True, "data": decisions["items"][concept_key]})


@concept_bp.route("/projects/<project_id>/decisions/<path:concept_key>", methods=["DELETE"])
def delete_concept_decision(project_id: str, concept_key: str):
    """Clear a single concept candidate decision."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    decisions = project.concept_decisions or {"version": 1, "items": {}}
    if concept_key in decisions.get("items", {}):
        del decisions["items"][concept_key]
        project.concept_decisions = decisions
        ProjectManager.save_project(project)

    return jsonify({"success": True})


@concept_bp.route("/projects/<project_id>/merge-suggest", methods=["POST"])
def post_concept_merge_suggest(project_id: str):
    """Return merge suggestions without persisting anything.

    Uses rule-based normalization + gray-zone similarity detection.
    """
    from ...services.workspace.concept_view_service import ConceptViewNotFoundError, ConceptViewService
    from ...services.workspace.concept_normalization import build_merge_suggestions

    try:
        view = ConceptViewService().build_project_view(project_id)
    except ConceptViewNotFoundError as error:
        return jsonify({"success": False, "error": str(error)}), 404

    candidates = view.get("candidateConcepts") or []
    suggestions = build_merge_suggestions(candidates)
    return jsonify({"success": True, "data": suggestions})


@concept_bp.route("/projects/<project_id>/normalize", methods=["POST"])
def post_concept_normalize(project_id: str):
    """Return normalized names for all concept candidates."""
    from ...services.workspace.concept_view_service import ConceptViewNotFoundError, ConceptViewService
    from ...services.workspace.concept_normalization import normalize_concept_name, expand_abbreviation

    try:
        view = ConceptViewService().build_project_view(project_id)
    except ConceptViewNotFoundError as error:
        return jsonify({"success": False, "error": str(error)}), 404

    candidates = view.get("candidateConcepts") or []
    results = []
    for candidate in candidates:
        raw = candidate.get("displayName") or ""
        normalized = normalize_concept_name(raw)
        expanded = expand_abbreviation(normalized)
        results.append({
            "key": candidate.get("key"),
            "original": raw,
            "normalized": normalized,
            "expandedFrom": expanded,
            "label": candidate.get("conceptType"),
        })

    return jsonify({"success": True, "data": results})
