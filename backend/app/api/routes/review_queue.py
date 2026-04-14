"""Global review task queue routes (Stage L).

Endpoints live under the ``registry_bp`` blueprint at ``/api/registry``.
"""

from __future__ import annotations

from flask import jsonify, request

from .. import registry_bp
from ..schemas.review_task import (
    BatchResolveResultSchema,
    ReviewStatsSchema,
    ReviewTaskListSchema,
    ReviewTaskSchema,
)
from ...services.registry.review_task_service import (
    ReviewTaskNotFoundError,
    ReviewTaskStateError,
    batch_resolve,
    create_task,
    get_stats,
    get_task,
    list_tasks,
    update_task,
)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@registry_bp.route("/review/tasks", methods=["GET"])
def list_review_tasks():
    status = request.args.get("status")
    entity_type = request.args.get("entity_type")
    project_id = request.args.get("project_id")
    priority = request.args.get("priority")
    limit = min(int(request.args.get("limit") or 100), 500)
    offset = max(int(request.args.get("offset") or 0), 0)

    result = list_tasks(
        status=status, entity_type=entity_type,
        project_id=project_id, priority=priority,
        limit=limit, offset=offset,
    )
    schema = ReviewTaskListSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/review/tasks", methods=["POST"])
def create_review_task():
    body = request.get_json(silent=True) or {}
    entity_type = str(body.get("entity_type") or "").strip()
    entity_id = str(body.get("entity_id") or "").strip()
    if not entity_type or not entity_id:
        return jsonify({"success": False, "error": "entity_type 和 entity_id 不能为空"}), 400

    task = create_task(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=str(body.get("entity_name") or ""),
        action_required=str(body.get("action_required") or "custom"),
        priority=str(body.get("priority") or "normal"),
        project_id=str(body.get("project_id") or ""),
        note=str(body.get("note") or ""),
    )
    schema = ReviewTaskSchema(**task)
    return jsonify({"success": True, "data": _model_dump(schema)}), 201


@registry_bp.route("/review/tasks/<task_id>", methods=["GET"])
def get_review_task(task_id: str):
    try:
        task = get_task(task_id)
        schema = ReviewTaskSchema(**task)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except ReviewTaskNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/review/tasks/<task_id>", methods=["PUT"])
def update_review_task(task_id: str):
    body = request.get_json(silent=True) or {}
    kwargs: dict = {}
    if "status" in body:
        kwargs["status"] = body["status"]
    if "resolution" in body:
        kwargs["resolution"] = body["resolution"]
    if "note" in body:
        kwargs["note"] = body["note"]
    if "priority" in body:
        kwargs["priority"] = body["priority"]

    try:
        task = update_task(task_id, **kwargs)
        schema = ReviewTaskSchema(**task)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except ReviewTaskNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ReviewTaskStateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


@registry_bp.route("/review/tasks/batch-resolve", methods=["POST"])
def batch_resolve_tasks():
    body = request.get_json(silent=True) or {}
    task_ids = list(body.get("task_ids") or [])
    if not task_ids:
        return jsonify({"success": False, "error": "task_ids 不能为空"}), 400

    result = batch_resolve(
        task_ids,
        resolution=str(body.get("resolution") or "approved"),
        note=str(body.get("note") or ""),
    )
    schema = BatchResolveResultSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/review/tasks/stats", methods=["GET"])
def review_stats():
    result = get_stats()
    schema = ReviewStatsSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})
