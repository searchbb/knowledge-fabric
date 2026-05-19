"""Read-only strategic research traceability map API."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...services.research_traceability_map import build_traceability_map


research_project_traceability_bp = Blueprint(
    "research_project_traceability", __name__, url_prefix="/api/research-projects"
)


@research_project_traceability_bp.route("/<project_id>/traceability-map", methods=["GET"])
def get_traceability_map(project_id: str):
    result = build_traceability_map(
        project_id,
        briefing_id=(request.args.get("briefing_id") or "").strip() or None,
        asset_type=(request.args.get("asset_type") or "").strip() or None,
        issue_severity=(request.args.get("issue_severity") or "").strip() or None,
    )
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": result})
