"""Project-scoped theme summary routes for Phase 2."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from flask import jsonify, request

from .. import theme_bp
from ..schemas.theme import ProjectThemeViewSchema
from ...models.project import ProjectManager
from ...services.workspace.concept_normalization import resolve_merge_chains
from ...services.workspace.theme_view_service import ThemeViewNotFoundError, ThemeViewService

_VALID_THEME_STATUSES = {"confirmed", "dismissed", "pending"}


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@theme_bp.route("/projects/<project_id>/view", methods=["GET"])
def get_theme_view(project_id: str):
    """Return a read-only theme candidate view for the requested project."""
    try:
        payload = ThemeViewService().build_project_view(project_id)
        schema = ProjectThemeViewSchema(**payload)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except ThemeViewNotFoundError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception as error:  # pragma: no cover - defensive route guard
        return jsonify({"success": False, "error": str(error)}), 500


@theme_bp.route("/projects/<project_id>/decisions/<path:candidate_key>", methods=["PUT"])
def put_theme_decision(project_id: str, candidate_key: str):
    """Persist a single theme candidate decision."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if not status or status not in _VALID_THEME_STATUSES:
        return jsonify({"success": False, "error": f"status 必须是 {_VALID_THEME_STATUSES} 之一"}), 400

    decisions = project.theme_decisions or {"version": 1, "items": {}}
    decisions.setdefault("version", 1)
    decisions.setdefault("items", {})
    decisions["items"][candidate_key] = {
        "status": status,
        "note": str(body.get("note") or ""),
        "updated_at": datetime.now().isoformat(),
    }
    project.theme_decisions = decisions
    ProjectManager.save_project(project)

    return jsonify({"success": True, "data": decisions["items"][candidate_key]})


@theme_bp.route("/projects/<project_id>/decisions/<path:candidate_key>", methods=["DELETE"])
def delete_theme_decision(project_id: str, candidate_key: str):
    """Clear a single theme candidate decision."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    decisions = project.theme_decisions or {"version": 1, "items": {}}
    if candidate_key in decisions.get("items", {}):
        del decisions["items"][candidate_key]
        project.theme_decisions = decisions
        ProjectManager.save_project(project)

    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Stage G: Theme Cluster CRUD
# ---------------------------------------------------------------------------


def _resolve_concept_id(concept_id: str, project) -> str:
    """Resolve a concept_id through F2 merge chains to its canonical target."""
    merge_map = resolve_merge_chains(project.concept_decisions or {})
    return merge_map.get(concept_id, concept_id)


def _get_clusters(project) -> list:
    return list(project.theme_clusters or [])


def _save_clusters(project, clusters: list):
    project.theme_clusters = clusters
    ProjectManager.save_project(project)


@theme_bp.route("/projects/<project_id>/clusters", methods=["GET"])
def list_theme_clusters(project_id: str):
    """List all theme clusters for a project."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404
    return jsonify({"success": True, "data": _get_clusters(project)})


@theme_bp.route("/projects/<project_id>/clusters", methods=["POST"])
def create_theme_cluster(project_id: str):
    """Create a new theme cluster."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "name 不能为空"}), 400

    now = datetime.now().isoformat()
    cluster = {
        "id": f"tc_{uuid_mod.uuid4().hex[:8]}",
        "name": name,
        "status": "active",
        "summary": str(body.get("summary") or ""),
        "concept_ids": [],
        "evidence_refs": [],
        "snippet_refs": [],
        "source_theme_keys": list(body.get("source_theme_keys") or []),
        "created_at": now,
        "updated_at": now,
    }

    clusters = _get_clusters(project)
    clusters.append(cluster)
    _save_clusters(project, clusters)

    return jsonify({"success": True, "data": cluster}), 201


@theme_bp.route("/projects/<project_id>/clusters/<cluster_id>", methods=["PUT"])
def update_theme_cluster(project_id: str, cluster_id: str):
    """Update a theme cluster (name, summary, status)."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    clusters = _get_clusters(project)
    cluster = next((c for c in clusters if c["id"] == cluster_id), None)
    if not cluster:
        return jsonify({"success": False, "error": "主题簇不存在"}), 404

    body = request.get_json(silent=True) or {}
    if "name" in body:
        cluster["name"] = str(body["name"]).strip()
    if "summary" in body:
        cluster["summary"] = str(body["summary"]).strip()
    if "status" in body and body["status"] in ("active", "archived"):
        cluster["status"] = body["status"]
    cluster["updated_at"] = datetime.now().isoformat()

    _save_clusters(project, clusters)
    return jsonify({"success": True, "data": cluster})


@theme_bp.route("/projects/<project_id>/clusters/<cluster_id>/concepts:attach", methods=["POST"])
def attach_concept_to_cluster(project_id: str, cluster_id: str):
    """Attach concept(s) to a theme cluster, resolving F2 merges."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    clusters = _get_clusters(project)
    cluster = next((c for c in clusters if c["id"] == cluster_id), None)
    if not cluster:
        return jsonify({"success": False, "error": "主题簇不存在"}), 404

    body = request.get_json(silent=True) or {}
    concept_ids = list(body.get("concept_ids") or [])
    if not concept_ids:
        return jsonify({"success": False, "error": "concept_ids 不能为空"}), 400

    existing = set(cluster.get("concept_ids") or [])
    for cid in concept_ids:
        resolved = _resolve_concept_id(cid, project)
        existing.add(resolved)

    cluster["concept_ids"] = sorted(existing)
    cluster["updated_at"] = datetime.now().isoformat()
    _save_clusters(project, clusters)

    return jsonify({"success": True, "data": cluster})


@theme_bp.route("/projects/<project_id>/clusters/<cluster_id>/concepts:detach", methods=["POST"])
def detach_concept_from_cluster(project_id: str, cluster_id: str):
    """Detach concept(s) from a theme cluster."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    clusters = _get_clusters(project)
    cluster = next((c for c in clusters if c["id"] == cluster_id), None)
    if not cluster:
        return jsonify({"success": False, "error": "主题簇不存在"}), 404

    body = request.get_json(silent=True) or {}
    concept_ids = set(body.get("concept_ids") or [])
    if not concept_ids:
        return jsonify({"success": False, "error": "concept_ids 不能为空"}), 400

    cluster["concept_ids"] = [cid for cid in (cluster.get("concept_ids") or []) if cid not in concept_ids]
    cluster["updated_at"] = datetime.now().isoformat()
    _save_clusters(project, clusters)

    return jsonify({"success": True, "data": cluster})


@theme_bp.route("/projects/<project_id>/clusters/<cluster_id>/evidence:attach", methods=["POST"])
def attach_evidence_to_cluster(project_id: str, cluster_id: str):
    """Attach evidence ref(s) to a theme cluster."""
    project = ProjectManager.get_project(project_id, include_legacy_phase1_backfill=False)
    if not project:
        return jsonify({"success": False, "error": "项目不存在"}), 404

    clusters = _get_clusters(project)
    cluster = next((c for c in clusters if c["id"] == cluster_id), None)
    if not cluster:
        return jsonify({"success": False, "error": "主题簇不存在"}), 404

    body = request.get_json(silent=True) or {}
    refs = list(body.get("evidence_refs") or [])
    if not refs:
        return jsonify({"success": False, "error": "evidence_refs 不能为空"}), 400

    existing_ids = {r.get("ref_id") for r in (cluster.get("evidence_refs") or []) if r.get("ref_id")}
    for ref in refs:
        ref_id = ref.get("ref_id") or ref.get("node_id") or ref.get("quote_id")
        if ref_id and ref_id not in existing_ids:
            cluster.setdefault("evidence_refs", []).append(ref)
            existing_ids.add(ref_id)

    cluster["updated_at"] = datetime.now().isoformat()
    _save_clusters(project, clusters)

    return jsonify({"success": True, "data": cluster})
