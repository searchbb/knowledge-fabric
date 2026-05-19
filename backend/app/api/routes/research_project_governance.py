"""Governance review APIs for ResearchProjects.

P9 persists manual review state derived from the traceability map. These
endpoints store checklist, finding, risk disposition, sign-off, and gate state
only; orchestration and remediation remain outside KFC runtime.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_governance_bp = Blueprint(
    "research_project_governance", __name__, url_prefix="/api/research-projects"
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


@research_project_governance_bp.route("/<project_id>/governance-reviews", methods=["GET"])
def list_governance_reviews(project_id: str):
    reviews = ResearchProjectStore().list_governance_reviews(project_id)
    if reviews is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "governance_reviews": reviews, "total": len(reviews)}})


@research_project_governance_bp.route("/<project_id>/governance-reviews", methods=["POST"])
def create_governance_review(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_governance_review(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    review, replay = result
    return _created_response({"project_id": project_id, "governance_review": review}, replay)


@research_project_governance_bp.route("/<project_id>/governance-reviews/<review_id>", methods=["GET"])
def get_governance_review(project_id: str, review_id: str):
    review = ResearchProjectStore().get_governance_review(project_id, review_id)
    if review is None:
        return jsonify({"success": False, "error": f"governance review not found: {review_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "governance_review": review}})


@research_project_governance_bp.route("/<project_id>/governance-reviews/<review_id>", methods=["PATCH"])
def update_governance_review(project_id: str, review_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        review = ResearchProjectStore().update_governance_review(project_id, review_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if review is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "governance_review": review}})
