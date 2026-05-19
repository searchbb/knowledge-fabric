"""Strategic decision workspace APIs for ResearchProjects.

P6 stores strategic options, validation plans, and leadership decision
records. These are reviewable decision assets; KFC does not execute plans,
call models, or generate external materials.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_decisions_bp = Blueprint(
    "research_project_decisions", __name__, url_prefix="/api/research-projects"
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


@research_project_decisions_bp.route("/<project_id>/strategic-options", methods=["GET"])
def list_strategic_options(project_id: str):
    options = ResearchProjectStore().list_strategic_options(project_id)
    if options is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "strategic_options": options, "total": len(options)}})


@research_project_decisions_bp.route("/<project_id>/strategic-options", methods=["POST"])
def create_strategic_option(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_strategic_option(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    option, replay = result
    return _created_response({"project_id": project_id, "strategic_option": option}, replay)


@research_project_decisions_bp.route("/<project_id>/strategic-options/<option_id>", methods=["GET"])
def get_strategic_option(project_id: str, option_id: str):
    option = ResearchProjectStore().get_strategic_option(project_id, option_id)
    if option is None:
        return jsonify({"success": False, "error": f"strategic option not found: {option_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "strategic_option": option}})


@research_project_decisions_bp.route("/<project_id>/strategic-options/<option_id>", methods=["PATCH"])
def update_strategic_option(project_id: str, option_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        option = ResearchProjectStore().update_strategic_option(project_id, option_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if option is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "strategic_option": option}})


@research_project_decisions_bp.route("/<project_id>/validation-plans", methods=["GET"])
def list_validation_plans(project_id: str):
    plans = ResearchProjectStore().list_validation_plans(project_id)
    if plans is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "validation_plans": plans, "total": len(plans)}})


@research_project_decisions_bp.route("/<project_id>/validation-plans", methods=["POST"])
def create_validation_plan(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_validation_plan(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    plan, replay = result
    return _created_response({"project_id": project_id, "validation_plan": plan}, replay)


@research_project_decisions_bp.route("/<project_id>/validation-plans/<plan_id>", methods=["GET"])
def get_validation_plan(project_id: str, plan_id: str):
    plan = ResearchProjectStore().get_validation_plan(project_id, plan_id)
    if plan is None:
        return jsonify({"success": False, "error": f"validation plan not found: {plan_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "validation_plan": plan}})


@research_project_decisions_bp.route("/<project_id>/validation-plans/<plan_id>", methods=["PATCH"])
def update_validation_plan(project_id: str, plan_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        plan = ResearchProjectStore().update_validation_plan(project_id, plan_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if plan is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "validation_plan": plan}})


@research_project_decisions_bp.route("/<project_id>/leadership-decision-records", methods=["GET"])
def list_leadership_decision_records(project_id: str):
    records = ResearchProjectStore().list_leadership_decision_records(project_id)
    if records is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "leadership_decision_records": records, "total": len(records)}})


@research_project_decisions_bp.route("/<project_id>/leadership-decision-records", methods=["POST"])
def create_leadership_decision_record(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_leadership_decision_record(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    record, replay = result
    return _created_response({"project_id": project_id, "leadership_decision_record": record}, replay)


@research_project_decisions_bp.route("/<project_id>/leadership-decision-records/<decision_id>", methods=["GET"])
def get_leadership_decision_record(project_id: str, decision_id: str):
    record = ResearchProjectStore().get_leadership_decision_record(project_id, decision_id)
    if record is None:
        return jsonify({"success": False, "error": f"leadership decision record not found: {decision_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "leadership_decision_record": record}})


@research_project_decisions_bp.route("/<project_id>/leadership-decision-records/<decision_id>", methods=["PATCH"])
def update_leadership_decision_record(project_id: str, decision_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        record = ResearchProjectStore().update_leadership_decision_record(project_id, decision_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if record is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "leadership_decision_record": record}})
