"""Codex/Skill writeback APIs for ResearchProjects.

P3 receives structured outputs from Codex-run tools. It stores and reviews
those outputs only; it does not run models, research tools, or background
execution loops.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_writeback_bp = Blueprint(
    "research_project_writeback", __name__, url_prefix="/api/research-projects"
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


@research_project_writeback_bp.route("/<project_id>/research-runs", methods=["GET"])
def list_research_runs(project_id: str):
    runs = ResearchProjectStore().list_research_runs(project_id)
    if runs is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "research_runs": runs, "total": len(runs)}})


@research_project_writeback_bp.route("/<project_id>/research-runs", methods=["POST"])
def create_research_run(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "stage", "phase", "title", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_research_run(project_id, payload)
    except ResearchProjectStoreError as exc:
        status = 409 if "idempotency key conflict" in str(exc) else 400
        return jsonify({"success": False, "error": str(exc)}), status
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    run, replay = result
    return _created_response({"project_id": project_id, "research_run": run}, replay)


@research_project_writeback_bp.route("/<project_id>/research-runs/<run_id>", methods=["GET"])
def get_research_run(project_id: str, run_id: str):
    run = ResearchProjectStore().get_research_run(project_id, run_id)
    if run is None:
        return jsonify({"success": False, "error": f"research run not found: {run_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "research_run": run}})


@research_project_writeback_bp.route("/<project_id>/consultation-logs", methods=["GET"])
def list_consultation_logs(project_id: str):
    logs = ResearchProjectStore().list_consultation_logs(project_id)
    if logs is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "consultation_logs": logs, "total": len(logs)}})


@research_project_writeback_bp.route("/<project_id>/consultation-logs", methods=["POST"])
def create_consultation_log(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "kind", "stage", "status", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_consultation_log(project_id, payload)
    except ResearchProjectStoreError as exc:
        status = 409 if "idempotency key conflict" in str(exc) else 400
        return jsonify({"success": False, "error": str(exc)}), status
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    log, replay = result
    return _created_response({"project_id": project_id, "consultation_log": log}, replay)


@research_project_writeback_bp.route("/<project_id>/consultation-logs/<consultation_id>", methods=["GET"])
def get_consultation_log(project_id: str, consultation_id: str):
    log = ResearchProjectStore().get_consultation_log(project_id, consultation_id)
    if log is None:
        return jsonify({"success": False, "error": f"consultation log not found: {consultation_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "consultation_log": log}})


@research_project_writeback_bp.route("/<project_id>/external-research-packs", methods=["GET"])
def list_external_research_packs(project_id: str):
    packs = ResearchProjectStore().list_external_research_packs(project_id)
    if packs is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "external_research_packs": packs, "total": len(packs)}})


@research_project_writeback_bp.route("/<project_id>/external-research-packs/import", methods=["POST"])
def import_external_research_pack(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "source_type", "idempotency_key")
    if error:
        return error
    candidates = payload.get("evidence_candidates")
    if not isinstance(candidates, list) or not candidates:
        return jsonify({"success": False, "error": "evidence_candidates must be a non-empty array"}), 400
    try:
        result = ResearchProjectStore().import_external_research_pack(project_id, payload)
    except ResearchProjectStoreError as exc:
        status = 409 if "idempotency key conflict" in str(exc) else 400
        return jsonify({"success": False, "error": str(exc)}), status
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    pack, replay = result
    return _created_response({"project_id": project_id, "external_research_pack": pack}, replay)


@research_project_writeback_bp.route("/<project_id>/external-research-packs/<pack_id>", methods=["GET"])
def get_external_research_pack(project_id: str, pack_id: str):
    pack = ResearchProjectStore().get_external_research_pack(project_id, pack_id)
    if pack is None:
        return jsonify({"success": False, "error": f"external research pack not found: {pack_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "external_research_pack": pack}})


@research_project_writeback_bp.route(
    "/<project_id>/external-research-packs/<pack_id>/candidates/<candidate_id>",
    methods=["PATCH"],
)
def update_external_research_candidate(project_id: str, pack_id: str, candidate_id: str):
    payload, error = _json_payload()
    if error:
        return error
    review_status = str(payload.get("review_status") or "").strip()
    review_note = str(payload.get("review_note") or "")
    try:
        result = ResearchProjectStore().update_external_research_candidate_status(
            project_id,
            pack_id,
            candidate_id,
            review_status=review_status,
            review_note=review_note,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except ResearchProjectStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    pack, project = result
    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "external_research_pack": pack,
            "evidence_items": project.evidence_items,
        },
    })
