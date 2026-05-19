"""KFC material graph APIs.

These endpoints expose deterministic KFC graph snapshots and graphification
requests. They never execute external runners, models, Codex, or schedulers.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...services.kfc_material_graph_store import KfcMaterialGraphStore, KfcMaterialGraphStoreError


kfc_assets_bp = Blueprint("kfc_assets", __name__, url_prefix="/api/kfc")


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _error_response(exc: KfcMaterialGraphStoreError):
    return (
        jsonify(
            {
                "success": False,
                "error": str(exc),
                "code": getattr(exc, "code", "validation_error"),
            }
        ),
        getattr(exc, "status_code", 400),
    )


@kfc_assets_bp.route("/material-graphs", methods=["GET"])
def list_kfc_material_graphs():
    filters = {
        key: request.args.get(key, "")
        for key in ("concept_id", "article_id", "topic_cluster_id", "research_project_id", "graph_state")
        if request.args.get(key)
    }
    try:
        result = KfcMaterialGraphStore().list_graphs(filters)
    except KfcMaterialGraphStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": result})


@kfc_assets_bp.route("/material-graphs/<graph_id>", methods=["GET"])
def get_kfc_material_graph(graph_id: str):
    try:
        result = KfcMaterialGraphStore().get_graph(graph_id)
    except KfcMaterialGraphStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"material graph not found: {graph_id}"}), 404
    return jsonify({"success": True, "data": result})


@kfc_assets_bp.route("/graphification-requests", methods=["GET"])
def list_graphification_requests():
    # Minimal read surface for UI persistence checks.
    store = KfcMaterialGraphStore()
    items = []
    if store.graphification_request_dir.exists():
        for path in sorted(store.graphification_request_dir.glob("kgreq_*.json")):
            try:
                import json

                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if isinstance(payload, dict):
                    items.append(payload)
            except (OSError, json.JSONDecodeError):
                continue
    items.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
    return jsonify({"success": True, "data": {"items": items, "total": len(items)}})
