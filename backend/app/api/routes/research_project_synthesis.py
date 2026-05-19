"""Strategic synthesis asset APIs for ResearchProjects.

P4 stores reviewable Evidence Matrix rows, Insight Cards, and Artifact Drafts.
It is deliberately a writeback/review surface; it does not call models,
generate materials, or run research jobs.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_synthesis_bp = Blueprint(
    "research_project_synthesis", __name__, url_prefix="/api/research-projects"
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


def _created_response(data: dict, replay: bool):
    return jsonify({"success": True, "data": data, "idempotent_replay": replay}), (200 if replay else 201)


def _error_response(exc: Exception):
    status = 409 if "idempotency key conflict" in str(exc) else 400
    if "not found" in str(exc):
        status = 404
    return jsonify({"success": False, "error": str(exc)}), status


@research_project_synthesis_bp.route("/<project_id>/evidence-matrix", methods=["GET"])
def list_evidence_matrix_rows(project_id: str):
    rows = ResearchProjectStore().list_evidence_matrix_rows(project_id)
    if rows is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "rows": rows, "total": len(rows)}})


@research_project_synthesis_bp.route("/<project_id>/evidence-matrix/rows", methods=["POST"])
def create_evidence_matrix_row(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "question", "claim", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_evidence_matrix_row(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    row, replay = result
    return _created_response({"project_id": project_id, "row": row}, replay)


@research_project_synthesis_bp.route("/<project_id>/evidence-matrix/rows/<row_id>", methods=["GET"])
def get_evidence_matrix_row(project_id: str, row_id: str):
    row = ResearchProjectStore().get_evidence_matrix_row(project_id, row_id)
    if row is None:
        return jsonify({"success": False, "error": f"evidence matrix row not found: {row_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "row": row}})


@research_project_synthesis_bp.route("/<project_id>/evidence-matrix/rows/<row_id>", methods=["PATCH"])
def update_evidence_matrix_row(project_id: str, row_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        row = ResearchProjectStore().update_evidence_matrix_row(project_id, row_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if row is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "row": row}})


@research_project_synthesis_bp.route("/<project_id>/insight-cards", methods=["GET"])
def list_insight_cards(project_id: str):
    cards = ResearchProjectStore().list_insight_cards(project_id)
    if cards is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "insight_cards": cards, "total": len(cards)}})


@research_project_synthesis_bp.route("/<project_id>/insight-cards", methods=["POST"])
def create_insight_card(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "claim", "implication", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_insight_card(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    card, replay = result
    return _created_response({"project_id": project_id, "insight_card": card}, replay)


@research_project_synthesis_bp.route("/<project_id>/insight-cards/<card_id>", methods=["GET"])
def get_insight_card(project_id: str, card_id: str):
    card = ResearchProjectStore().get_insight_card(project_id, card_id)
    if card is None:
        return jsonify({"success": False, "error": f"insight card not found: {card_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "insight_card": card}})


@research_project_synthesis_bp.route("/<project_id>/insight-cards/<card_id>", methods=["PATCH"])
def update_insight_card(project_id: str, card_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        card = ResearchProjectStore().update_insight_card(project_id, card_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if card is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "insight_card": card}})


@research_project_synthesis_bp.route("/<project_id>/artifact-drafts", methods=["GET"])
def list_artifact_drafts(project_id: str):
    drafts = ResearchProjectStore().list_artifact_drafts(project_id)
    if drafts is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_drafts": drafts, "total": len(drafts)}})


@research_project_synthesis_bp.route("/<project_id>/artifact-drafts", methods=["POST"])
def create_artifact_draft(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "artifact_type", "title", "purpose", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_artifact_draft(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    draft, replay = result
    return _created_response({"project_id": project_id, "artifact_draft": draft}, replay)


@research_project_synthesis_bp.route("/<project_id>/artifact-drafts/<draft_id>", methods=["GET"])
def get_artifact_draft(project_id: str, draft_id: str):
    draft = ResearchProjectStore().get_artifact_draft(project_id, draft_id)
    if draft is None:
        return jsonify({"success": False, "error": f"artifact draft not found: {draft_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_draft": draft}})


@research_project_synthesis_bp.route("/<project_id>/artifact-drafts/<draft_id>", methods=["PATCH"])
def update_artifact_draft(project_id: str, draft_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        draft = ResearchProjectStore().update_artifact_draft(project_id, draft_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if draft is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_draft": draft}})
