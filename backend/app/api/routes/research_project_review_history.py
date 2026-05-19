"""Review history APIs for ResearchProjects.

P10 exposes immutable audit-history sidecars and read-only timeline views. It
does not run workflows, generate assets, or mutate the target asset when adding
manual notes.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_review_history_bp = Blueprint(
    "research_project_review_history", __name__, url_prefix="/api/research-projects"
)


def _json_payload() -> tuple[dict | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"success": False, "error": "JSON body must be an object"}), 400)
    return payload, None


def _error_response(exc: Exception):
    return jsonify({"success": False, "error": str(exc)}), 400


@research_project_review_history_bp.route("/<project_id>/review-history", methods=["GET"])
def list_review_history(project_id: str):
    try:
        limit = int(request.args.get("limit") or 50)
    except ValueError:
        return jsonify({"success": False, "error": "limit must be an integer"}), 400
    entries = ResearchProjectStore().list_review_history(
        project_id,
        asset_type=(request.args.get("asset_type") or "").strip() or None,
        asset_id=(request.args.get("asset_id") or "").strip() or None,
        event_type=(request.args.get("event_type") or "").strip() or None,
        limit=limit,
    )
    if entries is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "review_history_entries": entries, "total": len(entries)}})


@research_project_review_history_bp.route("/<project_id>/review-history/assets/<asset_type>/<asset_id>", methods=["GET"])
def list_asset_review_history(project_id: str, asset_type: str, asset_id: str):
    entries = ResearchProjectStore().list_review_history(
        project_id,
        asset_type=asset_type,
        asset_id=asset_id,
        limit=int(request.args.get("limit") or 100),
    )
    if entries is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    entries = sorted(entries, key=lambda item: item.get("created_at", ""))
    return jsonify({"success": True, "data": {"project_id": project_id, "asset_type": asset_type, "asset_id": asset_id, "review_history_entries": entries, "total": len(entries)}})


@research_project_review_history_bp.route("/<project_id>/review-history/<history_entry_id>", methods=["GET"])
def get_review_history_entry(project_id: str, history_entry_id: str):
    entry = ResearchProjectStore().get_review_history_entry(project_id, history_entry_id)
    if entry is None:
        return jsonify({"success": False, "error": f"review history entry not found: {history_entry_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "review_history_entry": entry}})


@research_project_review_history_bp.route("/<project_id>/review-history/notes", methods=["POST"])
def create_review_history_note(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        entry = ResearchProjectStore().create_review_history_note(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if entry is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "review_history_entry": entry}}), 201
