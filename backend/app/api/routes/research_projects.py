"""ResearchProject API.

P1 exposes a minimal CRUD surface for strategic research asset containers.
This API stores state only; it does not call models, skills, workers, or
research automation.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import (
    ResearchProjectStatus,
    ResearchProjectStore,
    ResearchProjectStoreError,
)


research_projects_bp = Blueprint(
    "research_projects", __name__, url_prefix="/api/research-projects"
)


CREATE_FIELDS = {
    "title",
    "background",
    "audience",
    "goal",
    "status",
    "research_brief",
    "issue_tree",
    "linked_topic_clusters",
    "linked_themes",
    "linked_concepts",
    "evidence_items",
    "evidence_matrix_rows",
    "insight_cards",
    "artifact_drafts",
    "artifact_packs",
    "strategic_options",
    "validation_plans",
    "leadership_decision_records",
    "leadership_briefings",
    "governance_reviews",
    "review_history_entries",
    "research_snapshots",
    "snapshot_review_notes",
    "review_log",
}
UPDATE_FIELDS = CREATE_FIELDS
SERVER_FIELDS = {"id", "created_at", "updated_at"}
ARRAY_FIELDS = {
    "issue_tree",
    "linked_topic_clusters",
    "linked_themes",
    "linked_concepts",
    "evidence_items",
    "evidence_matrix_rows",
    "insight_cards",
    "artifact_drafts",
    "artifact_packs",
    "strategic_options",
    "validation_plans",
    "leadership_decision_records",
    "leadership_briefings",
    "governance_reviews",
    "review_history_entries",
    "research_snapshots",
    "snapshot_review_notes",
    "review_log",
}
TEXT_LIMITS = {
    "title": 200,
    "background": 5000,
    "audience": 5000,
    "goal": 5000,
}


def _json_payload() -> tuple[dict | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"success": False, "error": "JSON body must be an object"}), 400)
    return payload, None


def _validate_payload(payload: dict, *, creating: bool) -> tuple[dict | None, tuple | None]:
    allowed = CREATE_FIELDS if creating else UPDATE_FIELDS
    unknown = sorted(set(payload) - allowed)
    forbidden = sorted(set(payload) & SERVER_FIELDS)
    if unknown or forbidden:
        fields = ", ".join(unknown + forbidden)
        return None, (jsonify({"success": False, "error": f"unsupported fields: {fields}"}), 400)

    if creating and not str(payload.get("title") or "").strip():
        return None, (jsonify({"success": False, "error": "title is required"}), 400)

    clean: dict = {}
    for field, limit in TEXT_LIMITS.items():
        if field not in payload:
            continue
        value = payload.get(field)
        if not isinstance(value, str):
            return None, (jsonify({"success": False, "error": f"{field} must be a string"}), 400)
        value = value.strip() if field == "title" else value
        if field == "title" and not value:
            return None, (jsonify({"success": False, "error": "title is required"}), 400)
        if len(value) > limit:
            return None, (jsonify({"success": False, "error": f"{field} exceeds {limit} characters"}), 400)
        clean[field] = value

    if "status" in payload:
        status = payload["status"]
        valid_statuses = {item.value for item in ResearchProjectStatus}
        if status not in valid_statuses:
            return None, (
                jsonify({"success": False, "error": f"status must be one of {sorted(valid_statuses)}"}),
                400,
            )
        clean["status"] = status

    if "research_brief" in payload:
        if not isinstance(payload["research_brief"], dict):
            return None, (jsonify({"success": False, "error": "research_brief must be an object"}), 400)
        clean["research_brief"] = payload["research_brief"]

    for field in ARRAY_FIELDS:
        if field in payload:
            if not isinstance(payload[field], list):
                return None, (jsonify({"success": False, "error": f"{field} must be an array"}), 400)
            clean[field] = payload[field]

    return clean, None


@research_projects_bp.route("", methods=["GET"])
def list_research_projects():
    store = ResearchProjectStore()
    projects = [item.to_dict() for item in store.list()]
    return jsonify({"success": True, "data": {"projects": projects, "total": len(projects)}})


@research_projects_bp.route("", methods=["POST"])
def create_research_project():
    payload, error = _json_payload()
    if error:
        return error
    clean, error = _validate_payload(payload, creating=True)
    if error:
        return error
    try:
        project = ResearchProjectStore().create(clean)
    except (ResearchProjectStoreError, OSError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    return jsonify({"success": True, "data": project.to_dict()}), 201


@research_projects_bp.route("/<project_id>", methods=["GET"])
def get_research_project(project_id: str):
    project = ResearchProjectStore().get(project_id)
    if project is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": project.to_dict()})


@research_projects_bp.route("/<project_id>", methods=["PATCH"])
def update_research_project(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    clean, error = _validate_payload(payload, creating=False)
    if error:
        return error
    if not clean:
        return jsonify({"success": False, "error": "no supported fields to update"}), 400
    try:
        project = ResearchProjectStore().update(project_id, clean)
    except (ResearchProjectStoreError, OSError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
    if project is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": project.to_dict()})
