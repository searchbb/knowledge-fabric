"""Global concept registry routes (Stage H).

All endpoints live under the ``registry_bp`` blueprint, mounted at
``/api/registry``.
"""

from __future__ import annotations

from flask import jsonify, request

from .. import registry_bp
from ..schemas.registry import (
    AlignmentItemSchema,
    ProjectAlignmentSchema,
    ProjectSuggestResponseSchema,
    RegistryEntryListSchema,
    RegistryEntrySchema,
    RegistrySearchResultSchema,
)
from ...services.registry.global_concept_registry import (
    RegistryDuplicateError,
    RegistryEntryNotFoundError,
    create_entry,
    delete_entry,
    get_entry,
    get_project_alignment,
    link_project_concept,
    list_entries,
    search_entries,
    suggest_from_project,
    unlink_project_concept,
    update_entry,
)


from ...services.registry.cross_concept_relations import (
    count_by_entry as count_cross_by_entry,
)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@registry_bp.route("/concepts", methods=["GET"])
def list_registry_concepts():
    """List all global registry entries."""
    concept_type = request.args.get("concept_type")
    entries = list_entries(concept_type=concept_type)
    schema = RegistryEntryListSchema(entries=entries, total=len(entries))
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/concepts/<entry_id>", methods=["GET"])
def get_registry_concept(entry_id: str):
    """Get a single registry entry."""
    try:
        entry = get_entry(entry_id)
        schema = RegistryEntrySchema(**entry)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except RegistryEntryNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/concepts", methods=["POST"])
def create_registry_concept():
    """Create a new canonical registry entry."""
    body = request.get_json(silent=True) or {}
    canonical_name = str(body.get("canonical_name") or "").strip()
    if not canonical_name:
        return jsonify({"success": False, "error": "canonical_name 不能为空"}), 400

    try:
        entry = create_entry(
            canonical_name=canonical_name,
            concept_type=str(body.get("concept_type") or "Concept"),
            aliases=list(body.get("aliases") or []),
            description=str(body.get("description") or ""),
        )
        schema = RegistryEntrySchema(**entry)
        return jsonify({"success": True, "data": _model_dump(schema)}), 201
    except RegistryDuplicateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


@registry_bp.route("/concepts/<entry_id>", methods=["PUT"])
def update_registry_concept(entry_id: str):
    """Update an existing registry entry."""
    body = request.get_json(silent=True) or {}
    kwargs: dict = {}
    if "canonical_name" in body:
        kwargs["canonical_name"] = body["canonical_name"]
    if "concept_type" in body:
        kwargs["concept_type"] = body["concept_type"]
    if "aliases" in body:
        kwargs["aliases"] = body["aliases"]
    if "description" in body:
        kwargs["description"] = body["description"]

    try:
        entry = update_entry(entry_id, **kwargs)
        schema = RegistryEntrySchema(**entry)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except RegistryEntryNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except RegistryDuplicateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


@registry_bp.route("/concepts/<entry_id>", methods=["DELETE"])
def delete_registry_concept(entry_id: str):
    """Delete a registry entry."""
    deleted = delete_entry(entry_id)
    if not deleted:
        return jsonify({"success": False, "error": "注册表条目不存在"}), 404
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Link / unlink
# ---------------------------------------------------------------------------


@registry_bp.route("/concepts/<entry_id>/links", methods=["POST"])
def link_concept(entry_id: str):
    """Link a project concept to a registry entry."""
    body = request.get_json(silent=True) or {}
    project_id = str(body.get("project_id") or "").strip()
    concept_key = str(body.get("concept_key") or "").strip()
    if not project_id or not concept_key:
        return jsonify({"success": False, "error": "project_id 和 concept_key 不能为空"}), 400

    try:
        entry = link_project_concept(
            entry_id,
            project_id=project_id,
            concept_key=concept_key,
            project_name=str(body.get("project_name") or ""),
        )
        schema = RegistryEntrySchema(**entry)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except RegistryEntryNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/concepts/<entry_id>/links", methods=["DELETE"])
def unlink_concept(entry_id: str):
    """Remove a project concept link from a registry entry."""
    body = request.get_json(silent=True) or {}
    project_id = str(body.get("project_id") or "").strip()
    concept_key = str(body.get("concept_key") or "").strip()
    if not project_id or not concept_key:
        return jsonify({"success": False, "error": "project_id 和 concept_key 不能为空"}), 400

    try:
        entry = unlink_project_concept(
            entry_id,
            project_id=project_id,
            concept_key=concept_key,
        )
        schema = RegistryEntrySchema(**entry)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except RegistryEntryNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@registry_bp.route("/concepts/search", methods=["GET"])
def search_registry():
    """Search registry entries by name or alias."""
    query = str(request.args.get("q") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "q 参数不能为空"}), 400

    limit = min(int(request.args.get("limit") or 20), 100)
    results = search_entries(query, limit=limit)
    schema = RegistrySearchResultSchema(
        results=results, query=query, total=len(results)
    )
    return jsonify({"success": True, "data": _model_dump(schema)})


# ---------------------------------------------------------------------------
# Suggest from project
# ---------------------------------------------------------------------------


@registry_bp.route("/suggest-from-project/<project_id>", methods=["POST"])
def suggest_from_project_route(project_id: str):
    """Suggest registry entries from a project's accepted concepts."""
    try:
        result = suggest_from_project(project_id)
        schema = ProjectSuggestResponseSchema(**result)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except RegistryEntryNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Project alignment
# ---------------------------------------------------------------------------


@registry_bp.route("/projects/<project_id>/alignment", methods=["GET"])
def project_alignment(project_id: str):
    """Show how a project's concepts align with the global registry."""
    try:
        result = get_project_alignment(project_id)
        schema = ProjectAlignmentSchema(**result)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except RegistryEntryNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Phase C: Lookup by project concept key
# ---------------------------------------------------------------------------


@registry_bp.route("/concepts/lookup", methods=["GET"])
def lookup_concept_by_project():
    """Find canonical entry by project_id + concept_key.

    Used by article graph node detail panel to check if a node
    has a corresponding canonical concept in the global registry.

    Returns the matching entry with cross-relation count, or 404.
    """
    project_id = request.args.get("project_id", "").strip()
    concept_key = request.args.get("concept_key", "").strip()

    if not project_id:
        return jsonify({"success": False, "error": "project_id required"}), 400

    node_name = request.args.get("node_name", "").strip().lower()
    if concept_key:
        concept_key = concept_key.lower()

    entries = list_entries()

    # Strategy 1: exact concept_key match
    if concept_key:
        for entry in entries:
            for link in entry.get("source_links", []):
                if link.get("project_id") == project_id and link.get("concept_key", "").lower() == concept_key:
                    xrel_count = count_cross_by_entry(entry["entry_id"])
                    return jsonify({"success": True, "data": _build_lookup_result(entry, xrel_count)})

    # Strategy 2: match by node_name (ignoring type prefix) within same project
    search_name = node_name or (concept_key.split(":", 1)[1] if concept_key and ":" in concept_key else "")
    if search_name:
        for entry in entries:
            for link in entry.get("source_links", []):
                if link.get("project_id") != project_id:
                    continue
                # Compare just the name part after "Type:"
                link_key = link.get("concept_key", "")
                link_name = link_key.split(":", 1)[1].lower() if ":" in link_key else link_key.lower()
                if link_name == search_name:
                    xrel_count = count_cross_by_entry(entry["entry_id"])
                    return jsonify({"success": True, "data": _build_lookup_result(entry, xrel_count)})

    return jsonify({"success": False, "error": "未找到对应的全局概念"}), 404


def _build_lookup_result(entry, xrel_count):
    return {
        "entry_id": entry["entry_id"],
        "canonical_name": entry.get("canonical_name", ""),
        "concept_type": entry.get("concept_type", ""),
        "description": entry.get("description", ""),
        "xrel_count": xrel_count,
    }
