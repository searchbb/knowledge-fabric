"""Global evolution log routes (Stage K).

Endpoints live under the ``registry_bp`` blueprint at ``/api/registry``.
"""

from __future__ import annotations

from flask import jsonify, request

from .. import registry_bp
from ..schemas.evolution_log import (
    EntityTimelineSchema,
    EvolutionFeedSchema,
    ProjectFeedSchema,
)
from ...services.registry.evolution_log import (
    get_entity_timeline,
    get_global_feed,
    get_project_feed,
)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@registry_bp.route("/evolution/feed", methods=["GET"])
def global_evolution_feed():
    """Global activity feed (newest first, paginated)."""
    limit = min(int(request.args.get("limit") or 50), 200)
    offset = max(int(request.args.get("offset") or 0), 0)
    entity_type = request.args.get("entity_type")
    event_type = request.args.get("event_type")

    result = get_global_feed(
        limit=limit, offset=offset,
        entity_type=entity_type, event_type=event_type,
    )
    schema = EvolutionFeedSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/evolution/concepts/<entry_id>/timeline", methods=["GET"])
def concept_timeline(entry_id: str):
    """Timeline for a specific concept entry."""
    limit = min(int(request.args.get("limit") or 50), 200)
    result = get_entity_timeline("concept_entry", entry_id, limit=limit)
    schema = EntityTimelineSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/evolution/themes/<theme_id>/timeline", methods=["GET"])
def theme_timeline(theme_id: str):
    """Timeline for a specific global theme."""
    limit = min(int(request.args.get("limit") or 50), 200)
    result = get_entity_timeline("global_theme", theme_id, limit=limit)
    schema = EntityTimelineSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/evolution/projects/<project_id>/feed", methods=["GET"])
def project_evolution_feed(project_id: str):
    """Project-scoped activity feed."""
    limit = min(int(request.args.get("limit") or 50), 200)
    offset = max(int(request.args.get("offset") or 0), 0)
    result = get_project_feed(project_id, limit=limit, offset=offset)
    schema = ProjectFeedSchema(**result)
    return jsonify({"success": True, "data": _model_dump(schema)})
