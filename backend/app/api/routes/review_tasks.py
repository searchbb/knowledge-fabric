"""Review workspace routes for Phase 2."""

from __future__ import annotations

from datetime import datetime

from flask import jsonify, request

from .. import review_bp
from ..schemas.review import ReviewViewSchema
from ...models.project import ProjectManager
from ...services.workspace.review_view_service import ReviewViewNotFoundError, ReviewViewService

_VALID_STATUSES = {"approved", "questioned", "ignored"}


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@review_bp.route("/projects/<project_id>/view", methods=["GET"])
def get_review_view(project_id: str):
    """Return a read-only review workspace view model for the given project."""
    try:
        payload = ReviewViewService().build_project_view(project_id)
        schema = ReviewViewSchema(**payload)
        return jsonify(
            {
                "success": True,
                "data": _model_dump(schema),
            }
        )
    except ReviewViewNotFoundError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception as error:  # pragma: no cover - defensive route guard
        return jsonify({"success": False, "error": str(error)}), 500


@review_bp.route("/projects/<project_id>/items/<item_id>", methods=["PUT"])
def put_review_decision(project_id: str, item_id: str):
    """Persist a single review item decision (status + note)."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    body = request.get_json(silent=True) or {}
    status = body.get("status")
    note = body.get("note", "")

    if not status or status not in _VALID_STATUSES:
        return jsonify({"success": False, "error": f"status 必须是 {_VALID_STATUSES} 之一"}), 400

    decisions = project.review_decisions or {"version": 1, "items": {}}
    decisions.setdefault("version", 1)
    decisions.setdefault("items", {})
    decisions["items"][item_id] = {
        "status": status,
        "note": str(note or ""),
        "updated_at": datetime.now().isoformat(),
        "updated_by": "local_user",
    }
    project.review_decisions = decisions
    ProjectManager.save_project(project)

    return jsonify({"success": True, "data": decisions["items"][item_id]})


@review_bp.route("/projects/<project_id>/items/<item_id>", methods=["DELETE"])
def delete_review_decision(project_id: str, item_id: str):
    """Clear a single review item decision."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    decisions = project.review_decisions or {"version": 1, "items": {}}
    if item_id in decisions.get("items", {}):
        del decisions["items"][item_id]
        project.review_decisions = decisions
        ProjectManager.save_project(project)

    return jsonify({"success": True})
