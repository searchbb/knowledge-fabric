"""Material Workshop APIs for ResearchProjects.

P5 stores Artifact Packs that organize existing drafts, page specs, file
references, and review rounds. It records external outputs only; it does not
generate files, run models, or schedule work.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_artifact_packs_bp = Blueprint(
    "research_project_artifact_packs", __name__, url_prefix="/api/research-projects"
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
    if "not found" in str(exc):
        status = 404
    return jsonify({"success": False, "error": str(exc)}), status


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs", methods=["GET"])
def list_artifact_packs(project_id: str):
    packs = ResearchProjectStore().list_artifact_packs(project_id)
    if packs is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_packs": packs, "total": len(packs)}})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs", methods=["POST"])
def create_artifact_pack(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    _, error = _require(payload, "title", "purpose", "idempotency_key")
    if error:
        return error
    try:
        result = ResearchProjectStore().create_artifact_pack(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    pack, replay = result
    return _created_response({"project_id": project_id, "artifact_pack": pack}, replay)


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>", methods=["GET"])
def get_artifact_pack(project_id: str, pack_id: str):
    pack = ResearchProjectStore().get_artifact_pack(project_id, pack_id)
    if pack is None:
        return jsonify({"success": False, "error": f"artifact pack not found: {pack_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_pack": pack}})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>", methods=["PATCH"])
def update_artifact_pack(project_id: str, pack_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().update_artifact_pack(project_id, pack_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_pack": pack}})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/items", methods=["POST"])
def add_artifact_pack_item(project_id: str, pack_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().add_artifact_pack_item(project_id, pack_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return _created_response({"project_id": project_id, "artifact_pack": pack})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/items/<item_id>", methods=["PATCH"])
def update_artifact_pack_item(project_id: str, pack_id: str, item_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().update_artifact_pack_item(project_id, pack_id, item_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_pack": pack}})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/pages", methods=["POST"])
def add_artifact_pack_page(project_id: str, pack_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().add_artifact_pack_page(project_id, pack_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return _created_response({"project_id": project_id, "artifact_pack": pack})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/pages/<page_id>", methods=["PATCH"])
def update_artifact_pack_page(project_id: str, pack_id: str, page_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().update_artifact_pack_page(project_id, pack_id, page_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_pack": pack}})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/file-refs", methods=["POST"])
def add_artifact_pack_file_ref(project_id: str, pack_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().add_artifact_pack_file_ref(project_id, pack_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return _created_response({"project_id": project_id, "artifact_pack": pack})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/file-refs/<file_ref_id>", methods=["PATCH"])
def update_artifact_pack_file_ref(project_id: str, pack_id: str, file_ref_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().update_artifact_pack_file_ref(project_id, pack_id, file_ref_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "artifact_pack": pack}})


@research_project_artifact_packs_bp.route("/<project_id>/artifact-packs/<pack_id>/review-rounds", methods=["POST"])
def add_artifact_pack_review_round(project_id: str, pack_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        pack = ResearchProjectStore().add_artifact_pack_review_round(project_id, pack_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if pack is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return _created_response({"project_id": project_id, "artifact_pack": pack})
