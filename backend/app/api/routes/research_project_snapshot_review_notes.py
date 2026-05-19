"""Manual snapshot review note APIs for ResearchProjects.

P13 exposes durable human annotations for snapshot diffs. It never changes a
gate result, edits assets, rewinds state, writes analysis, or mutates the
snapshot/upstream assets.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_snapshot_review_notes_bp = Blueprint(
    "research_project_snapshot_review_notes", __name__, url_prefix="/api/research-projects"
)


def _json_payload() -> tuple[dict | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"success": False, "error": "JSON body must be an object"}), 400)
    return payload, None


def _error_response(exc: Exception):
    return jsonify({"success": False, "error": str(exc)}), 400


@research_project_snapshot_review_notes_bp.route("/<project_id>/snapshots/<snapshot_id>/review-notes", methods=["POST"])
def create_snapshot_review_note(project_id: str, snapshot_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        result = ResearchProjectStore().create_snapshot_review_note(project_id, snapshot_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    note = result["snapshot_review_note"]
    history = result["review_history_entry"]
    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "snapshot_review_note": note,
            "review_history_entry_id": history["history_entry_id"],
        },
    }), 201


@research_project_snapshot_review_notes_bp.route("/<project_id>/snapshots/<snapshot_id>/review-notes", methods=["GET"])
def list_snapshot_review_notes(project_id: str, snapshot_id: str):
    try:
        notes = ResearchProjectStore().list_snapshot_review_notes(project_id, snapshot_id)
    except ResearchProjectStoreError as exc:
        return _error_response(exc)
    if notes is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "snapshot_review_notes": notes,
            "total": len(notes),
        },
    })


@research_project_snapshot_review_notes_bp.route("/<project_id>/snapshots/<snapshot_id>/review-notes/<note_id>", methods=["GET"])
def get_snapshot_review_note(project_id: str, snapshot_id: str, note_id: str):
    try:
        note = ResearchProjectStore().get_snapshot_review_note(project_id, snapshot_id, note_id)
    except ResearchProjectStoreError as exc:
        return _error_response(exc)
    if note is None:
        return jsonify({"success": False, "error": f"snapshot review note not found: {note_id}"}), 404
    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "snapshot_review_note": note,
        },
    })


@research_project_snapshot_review_notes_bp.route("/<project_id>/snapshots/<snapshot_id>/review-notes/<note_id>", methods=["PATCH"])
def update_snapshot_review_note(project_id: str, snapshot_id: str, note_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        result = ResearchProjectStore().update_snapshot_review_note(project_id, snapshot_id, note_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"snapshot review note not found: {note_id}"}), 404
    history = result.get("review_history_entry")
    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "snapshot_review_note": result["snapshot_review_note"],
            "review_history_entry_id": history["history_entry_id"] if history else "",
            "history_recorded": bool(history),
        },
    })
