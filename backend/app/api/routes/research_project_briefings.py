"""Leadership briefing APIs for ResearchProjects.

P7 stores structured readout assets for leadership review. These endpoints
persist briefing structure, source references, and review state only.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_briefings_bp = Blueprint(
    "research_project_briefings", __name__, url_prefix="/api/research-projects"
)


def _json_payload() -> tuple[dict | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"success": False, "error": "JSON body must be an object"}), 400)
    return payload, None


def _require(payload: dict, *fields: str) -> tuple[None, tuple | None]:
    missing = [field for field in fields if not str(payload.get(field) or "").strip()]
    if missing:
        return None, (jsonify({"success": False, "error": f"missing required fields: {', '.join(missing)}"}), 400)
    return None, None


def _created_response(data: dict, replay: bool = False):
    return jsonify({"success": True, "data": data, "idempotent_replay": replay}), (200 if replay else 201)


def _error_response(exc: Exception):
    status = 409 if "idempotency key conflict" in str(exc) else 400
    if str(exc).startswith("research decision asset not found"):
        status = 404
    return jsonify({"success": False, "error": str(exc)}), status


@research_project_briefings_bp.route("/<project_id>/leadership-briefings", methods=["GET"])
def list_leadership_briefings(project_id: str):
    briefings = ResearchProjectStore().list_leadership_briefings(project_id)
    if briefings is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "leadership_briefings": briefings, "total": len(briefings)}})


@research_project_briefings_bp.route("/<project_id>/leadership-briefings", methods=["POST"])
def create_leadership_briefing(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "audience", "purpose", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_leadership_briefing(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    briefing, replay = result
    return _created_response({"project_id": project_id, "leadership_briefing": briefing}, replay)


@research_project_briefings_bp.route("/<project_id>/leadership-briefings/<briefing_id>", methods=["GET"])
def get_leadership_briefing(project_id: str, briefing_id: str):
    briefing = ResearchProjectStore().get_leadership_briefing(project_id, briefing_id)
    if briefing is None:
        return jsonify({"success": False, "error": f"leadership briefing not found: {briefing_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "leadership_briefing": briefing}})


@research_project_briefings_bp.route("/<project_id>/leadership-briefings/<briefing_id>", methods=["PATCH"])
def update_leadership_briefing(project_id: str, briefing_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        briefing = ResearchProjectStore().update_leadership_briefing(project_id, briefing_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if briefing is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "leadership_briefing": briefing}})
