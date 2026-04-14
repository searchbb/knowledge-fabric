"""Project-scoped evolution routes for Phase 2 workspace views."""

from __future__ import annotations

from flask import jsonify

from .. import evolution_bp
from ..schemas.evolution import ProjectEvolutionViewSchema
from ...services.workspace.evolution_view_service import EvolutionViewNotFoundError, EvolutionViewService


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@evolution_bp.route("/projects/<project_id>/view", methods=["GET"])
def get_evolution_view(project_id: str):
    """Return a read-only evolution snapshot for the requested project."""
    try:
        payload = EvolutionViewService().build_project_view(project_id)
        schema = ProjectEvolutionViewSchema(**payload)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except EvolutionViewNotFoundError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception as error:  # pragma: no cover - defensive route guard
        return jsonify({"success": False, "error": str(error)}), 500
