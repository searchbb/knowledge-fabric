"""Research snapshot APIs for ResearchProjects.

P11 exposes manual gate baselines and read-only comparisons for audit review.
It never mutates included assets while reading or comparing snapshots.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError


research_project_snapshots_bp = Blueprint(
    "research_project_snapshots", __name__, url_prefix="/api/research-projects"
)


def _json_payload() -> tuple[dict | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({"success": False, "error": "JSON body must be an object"}), 400)
    return payload, None


def _error_response(exc: Exception):
    return jsonify({"success": False, "error": str(exc)}), 400


@research_project_snapshots_bp.route("/<project_id>/snapshots", methods=["POST"])
def create_research_snapshot(project_id: str):
    payload, error = _json_payload()
    if error:
        return error
    try:
        snapshot = ResearchProjectStore().create_research_snapshot(project_id, payload)
    except (ResearchProjectStoreError, ValueError) as exc:
        return _error_response(exc)
    if snapshot is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "snapshot": snapshot}}), 201


@research_project_snapshots_bp.route("/<project_id>/snapshots", methods=["GET"])
def list_research_snapshots(project_id: str):
    snapshots = ResearchProjectStore().list_research_snapshots(project_id)
    if snapshots is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "snapshots": snapshots, "total": len(snapshots)}})


@research_project_snapshots_bp.route("/<project_id>/snapshots/<snapshot_id>", methods=["GET"])
def get_research_snapshot(project_id: str, snapshot_id: str):
    snapshot = ResearchProjectStore().get_research_snapshot(project_id, snapshot_id)
    if snapshot is None:
        return jsonify({"success": False, "error": f"research snapshot not found: {snapshot_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "snapshot": snapshot}})


@research_project_snapshots_bp.route("/<project_id>/snapshots/<snapshot_id>/diff", methods=["GET"])
def diff_research_snapshot(project_id: str, snapshot_id: str):
    try:
        diff = ResearchProjectStore().diff_research_snapshot_to_current(project_id, snapshot_id)
    except ResearchProjectStoreError as exc:
        return _error_response(exc)
    if diff is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "snapshot_diff": diff}})
