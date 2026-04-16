"""Global theme registry routes (Stage J).

All endpoints live under the ``registry_bp`` blueprint, mounted at
``/api/registry``.
"""

from __future__ import annotations

from flask import jsonify, request

from .. import registry_bp
from ..schemas.global_theme import (
    GlobalThemeListSchema,
    GlobalThemeSchema,
    ThemeSuggestResponseSchema,
)
from ...services.registry.global_theme_registry import (
    GlobalThemeDuplicateError,
    GlobalThemeNotFoundError,
    attach_concepts,
    create_theme,
    delete_theme,
    detach_concepts,
    get_hub_view,
    get_theme,
    link_project_cluster,
    list_orphans,
    list_themes,
    merge_themes,
    promote_candidate,
    reject_candidate,
    suggest_from_project,
    suggested_memberships_for_theme,
    unlink_project_cluster,
    update_theme,
)
from ...services.registry.cross_concept_relations import (
    list_relations as list_cross_relations,
    theme_summary as cross_theme_summary,
)
from ...services.registry.global_concept_registry import (
    get_entry as get_concept_entry,
    list_entries as list_concept_entries,
)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# Legacy auto-generated description templates we want the UI to flag. These
# were created by older ingestion paths that stringified the associated node
# title instead of running the LLM description prompt. Keeping the list
# explicit — zero-fallback rule: we don't hide a degraded description as
# though it were a real summary.
_DEGRADED_DESCRIPTION_PREFIXES = ("关联节点：", "关联节点:")


def _is_description_degraded(entry: dict) -> bool:
    """Return True when the canonical concept description is a stub/template.

    Triggers:
    * The registry flags ``description_degraded=true`` explicitly, or
    * description is empty, or
    * description matches a known template prefix and the
      ``description_source`` has not been set to an authoritative value
      (``manual`` or ``article_node_summary``).
    """
    if entry.get("description_degraded") is True:
        return True
    desc = (entry.get("description") or "").strip()
    if not desc:
        return True
    if entry.get("description_source") in ("manual", "article_node_summary"):
        return False
    return any(desc.startswith(prefix) for prefix in _DEGRADED_DESCRIPTION_PREFIXES)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@registry_bp.route("/themes", methods=["GET"])
def list_global_themes():
    themes = list_themes()
    schema = GlobalThemeListSchema(themes=themes, total=len(themes))
    return jsonify({"success": True, "data": _model_dump(schema)})


@registry_bp.route("/themes/<theme_id>", methods=["GET"])
def get_global_theme(theme_id: str):
    try:
        theme = get_theme(theme_id)
        schema = GlobalThemeSchema(**theme)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes", methods=["POST"])
def create_global_theme():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "name 不能为空"}), 400

    try:
        theme = create_theme(
            name=name,
            description=str(body.get("description") or ""),
            keywords=body.get("keywords") if isinstance(body.get("keywords"), list) else None,
        )
        return jsonify({"success": True, "data": theme}), 201
    except GlobalThemeDuplicateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


@registry_bp.route("/themes/<theme_id>", methods=["PUT"])
def update_global_theme(theme_id: str):
    body = request.get_json(silent=True) or {}
    kwargs: dict = {}
    if "name" in body:
        kwargs["name"] = body["name"]
    if "description" in body:
        kwargs["description"] = body["description"]
    if "status" in body:
        kwargs["status"] = body["status"]

    try:
        theme = update_theme(theme_id, **kwargs)
        schema = GlobalThemeSchema(**theme)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except GlobalThemeDuplicateError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


@registry_bp.route("/themes/<theme_id>", methods=["DELETE"])
def delete_global_theme(theme_id: str):
    deleted = delete_theme(theme_id)
    if not deleted:
        return jsonify({"success": False, "error": "全局主题不存在"}), 404
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Concept attach / detach
# ---------------------------------------------------------------------------


@registry_bp.route("/themes/<theme_id>/concepts:attach", methods=["POST"])
def attach_concepts_to_theme(theme_id: str):
    body = request.get_json(silent=True) or {}
    ids = list(body.get("concept_entry_ids") or [])
    if not ids:
        return jsonify({"success": False, "error": "concept_entry_ids 不能为空"}), 400

    # Interactive UI calls land here — tag the resulting evolution event
    # accordingly so downstream filters can separate human edits from
    # auto-pipeline actions.
    try:
        theme = attach_concepts(
            theme_id,
            ids,
            actor_type="human",
            source="workspace_ui",
        )
        schema = GlobalThemeSchema(**theme)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/<theme_id>/concepts:detach", methods=["POST"])
def detach_concepts_from_theme(theme_id: str):
    body = request.get_json(silent=True) or {}
    ids = list(body.get("concept_entry_ids") or [])
    if not ids:
        return jsonify({"success": False, "error": "concept_entry_ids 不能为空"}), 400

    try:
        theme = detach_concepts(
            theme_id,
            ids,
            actor_type="human",
            source="workspace_ui",
        )
        schema = GlobalThemeSchema(**theme)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Project cluster link / unlink
# ---------------------------------------------------------------------------


@registry_bp.route("/themes/<theme_id>/clusters:link", methods=["POST"])
def link_cluster_to_theme(theme_id: str):
    body = request.get_json(silent=True) or {}
    project_id = str(body.get("project_id") or "").strip()
    cluster_id = str(body.get("cluster_id") or "").strip()
    if not project_id or not cluster_id:
        return jsonify({"success": False, "error": "project_id 和 cluster_id 不能为空"}), 400

    try:
        theme = link_project_cluster(
            theme_id,
            project_id=project_id,
            cluster_id=cluster_id,
            cluster_name=str(body.get("cluster_name") or ""),
        )
        schema = GlobalThemeSchema(**theme)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/<theme_id>/clusters:unlink", methods=["POST"])
def unlink_cluster_from_theme(theme_id: str):
    body = request.get_json(silent=True) or {}
    project_id = str(body.get("project_id") or "").strip()
    cluster_id = str(body.get("cluster_id") or "").strip()
    if not project_id or not cluster_id:
        return jsonify({"success": False, "error": "project_id 和 cluster_id 不能为空"}), 400

    try:
        theme = unlink_project_cluster(
            theme_id,
            project_id=project_id,
            cluster_id=cluster_id,
        )
        schema = GlobalThemeSchema(**theme)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Suggest from project
# ---------------------------------------------------------------------------


@registry_bp.route("/themes/suggest-from-project/<project_id>", methods=["POST"])
def suggest_themes_from_project(project_id: str):
    try:
        result = suggest_from_project(project_id)
        schema = ThemeSuggestResponseSchema(**result)
        return jsonify({"success": True, "data": _model_dump(schema)})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


# ---------------------------------------------------------------------------
# Hub-and-Spoke governance endpoints (2026-04-12 redesign)
# ---------------------------------------------------------------------------


@registry_bp.route("/themes/<theme_id>/view", methods=["GET"])
def get_theme_hub_view(theme_id: str):
    """Hub view: theme + member/candidate concepts + related projects."""
    try:
        data = get_hub_view(theme_id)
        return jsonify({"success": True, "data": data})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/<theme_id>/members", methods=["POST"])
def attach_members(theme_id: str):
    """Attach concepts as members with explicit score/role."""
    body = request.get_json(silent=True) or {}
    ids = list(body.get("concept_entry_ids") or [])
    if not ids:
        return jsonify({"success": False, "error": "concept_entry_ids 不能为空"}), 400
    try:
        theme = attach_concepts(
            theme_id, ids,
            role=body.get("role", "member"),
            score=float(body.get("score", 1.0)),
            actor_type="human", source="governance_ui",
        )
        return jsonify({"success": True, "data": theme})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/<theme_id>/members", methods=["DELETE"])
def detach_members(theme_id: str):
    """Detach concepts from a theme."""
    body = request.get_json(silent=True) or {}
    ids = list(body.get("concept_entry_ids") or [])
    if not ids:
        return jsonify({"success": False, "error": "concept_entry_ids 不能为空"}), 400
    try:
        theme = detach_concepts(theme_id, ids, source="governance_ui")
        return jsonify({"success": True, "data": theme})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/<theme_id>/candidates/promote", methods=["POST"])
def promote_theme_candidates(theme_id: str):
    """Promote candidate memberships to member role."""
    body = request.get_json(silent=True) or {}
    ids = list(body.get("concept_entry_ids") or [])
    if not ids:
        return jsonify({"success": False, "error": "concept_entry_ids 不能为空"}), 400
    try:
        theme = promote_candidate(theme_id, ids)
        return jsonify({"success": True, "data": theme})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/<theme_id>/candidates/reject", methods=["POST"])
def reject_theme_candidates(theme_id: str):
    """Reject/remove candidate memberships."""
    body = request.get_json(silent=True) or {}
    ids = list(body.get("concept_entry_ids") or [])
    if not ids:
        return jsonify({"success": False, "error": "concept_entry_ids 不能为空"}), 400
    try:
        theme = reject_candidate(theme_id, ids)
        return jsonify({"success": True, "data": theme})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/orphans", methods=["GET"])
def list_orphan_concepts():
    """Return canonical concepts not assigned to any theme."""
    limit = request.args.get("limit", 200, type=int)
    orphans = list_orphans(limit=limit)
    return jsonify({"success": True, "data": {"orphans": orphans, "total": len(orphans)}})


@registry_bp.route("/themes/merge", methods=["POST"])
def merge_global_themes():
    """Merge source theme into target theme."""
    body = request.get_json(silent=True) or {}
    source_id = str(body.get("source_theme_id") or "").strip()
    target_id = str(body.get("target_theme_id") or "").strip()
    if not source_id or not target_id:
        return jsonify({"success": False, "error": "need source_theme_id and target_theme_id"}), 400
    if source_id == target_id:
        return jsonify({"success": False, "error": "source and target must be different"}), 400
    try:
        merged = merge_themes(source_id, target_id)
        return jsonify({"success": True, "data": merged})
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@registry_bp.route("/themes/merge-scan", methods=["POST"])
def run_theme_merge_scan():
    """Run the near-duplicate theme merge scanner (P1 M3).

    Body (all optional):
        dry_run: bool (default false) — score + decide but don't actually merge
        enable_llm_adjudication: bool (default true)
        max_llm_calls: int (default 20) — safety cap

    Returns the full audit dict from scan_and_merge_candidates.
    """
    from ...services.auto.theme_merge_scanner import scan_and_merge_candidates

    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    enable_llm = bool(body.get("enable_llm_adjudication", True))
    max_llm = int(body.get("max_llm_calls", 20))

    try:
        result = scan_and_merge_candidates(
            dry_run=dry_run,
            enable_llm_adjudication=enable_llm,
            max_llm_calls=max_llm,
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": str(exc)}), 500


@registry_bp.route("/themes/promote-candidates", methods=["POST"])
def run_theme_promotion_scan():
    """Promote candidate themes that pass the M2 rules to active (P1 M2).

    Body:
        dry_run: bool (default false)

    Rules (GPT consult d10c98cab0b64a56 A3):
        Rule A: distinct_articles >= 2 AND member_count >= 6
        Rule B: distinct_articles >= 3 AND member_count >= 4
    """
    from ...services.auto.theme_merge_scanner import promote_eligible_candidate_themes

    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    try:
        result = promote_eligible_candidate_themes(dry_run=dry_run)
        return jsonify({"success": True, "data": result})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": str(exc)}), 500


@registry_bp.route("/themes/governance-scan", methods=["POST"])
def run_theme_governance_scan():
    """Run the full P1 governance pass: merge-scan then promote-candidates.

    Do this post-pipeline (async / manual). GPT consult d10c98cab0b64a56
    recommends promote AFTER merge so merged themes don't get promoted.
    """
    from ...services.auto.theme_merge_scanner import (
        promote_eligible_candidate_themes,
        scan_and_merge_candidates,
    )

    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    enable_llm = bool(body.get("enable_llm_adjudication", True))

    try:
        merge_result = scan_and_merge_candidates(
            dry_run=dry_run,
            enable_llm_adjudication=enable_llm,
        )
        promote_result = promote_eligible_candidate_themes(dry_run=dry_run)
        return jsonify({
            "success": True,
            "data": {
                "merge_scan": merge_result,
                "promotion_scan": promote_result,
            },
        })
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Panorama (Phase B: theme detail with cross-article relations)
# ---------------------------------------------------------------------------


@registry_bp.route("/themes/<theme_id>/panorama", methods=["GET"])
def get_theme_panorama(theme_id: str):
    """Return aggregated panorama data for a theme detail page.

    Combines theme metadata, grouped concepts, cross-article relations,
    and discovery stats into a single response.
    """
    try:
        theme = get_theme(theme_id)
    except GlobalThemeNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    memberships = theme.get("concept_memberships", [])
    all_entries = {e["entry_id"]: e for e in list_concept_entries()}

    # Classify concepts into core / bridge / peripheral
    member_ids = [m["entry_id"] for m in memberships if m.get("role") == "member"]
    candidate_ids = [m["entry_id"] for m in memberships if m.get("role") == "candidate"]

    # Get cross-relation counts for bridge detection
    xrel_summary = cross_theme_summary(theme_id)
    bridge_scores = xrel_summary.get("top_bridge_scores", {})

    core_concepts = []
    bridge_concepts = []
    peripheral_concepts = []

    for m in memberships:
        eid = m["entry_id"]
        entry = all_entries.get(eid, {})
        if not entry:
            continue
        concept_data = {
            "entry_id": eid,
            "canonical_name": entry.get("canonical_name", ""),
            "concept_type": entry.get("concept_type", ""),
            "description": entry.get("description", ""),
            "description_degraded": _is_description_degraded(entry),
            "source_links": entry.get("source_links", []),
            "role": m.get("role", "candidate"),
            "score": m.get("score", 0),
            "xrel_count": 0,
            "bridge_score": bridge_scores.get(eid, 0),
        }
        # Count x-rels for this concept
        concept_data["xrel_count"] = sum(
            1 for _ in list_cross_relations(entry_id=eid, theme_id=theme_id)
        )
        # Classify
        if concept_data["bridge_score"] > 0:
            bridge_concepts.append(concept_data)
        elif m.get("role") == "member":
            core_concepts.append(concept_data)
        else:
            peripheral_concepts.append(concept_data)

    # Sort each group
    bridge_concepts.sort(key=lambda c: -c["bridge_score"])
    core_concepts.sort(key=lambda c: -c["score"])
    peripheral_concepts.sort(key=lambda c: c["canonical_name"].lower())

    # Collect unique project names
    project_set = set()
    for m in memberships:
        entry = all_entries.get(m["entry_id"], {})
        for link in entry.get("source_links", []):
            project_set.add(link.get("project_name", link.get("project_id", "")))

    # Get bridge relations
    bridge_relations = list_cross_relations(theme_id=theme_id)

    # --- Coverage & risk surfacing (GPT suggestion: make silent gaps visible)
    # limit=60 to keep both high-relevance substantive concepts AND the
    # low-relevance quantitative Evidence/Example tail visible; the UI
    # renders them under separate sections so the tail can't drown out
    # substantive suggestions (GPT must-fix 2026-04-14 round 2).
    suggestions = suggested_memberships_for_theme(theme_id, limit=60)

    # Count silent failures we can detect from the current response. "Silent"
    # means the user would otherwise not know something is broken/partial.
    silent_failures = {
        "concepts_missing_source_links": sum(
            1 for group in (core_concepts, bridge_concepts, peripheral_concepts)
            for c in group if not c.get("source_links")
        ),
        "descriptions_degraded": sum(
            1 for group in (core_concepts, bridge_concepts, peripheral_concepts)
            for c in group if c.get("description_degraded")
        ),
        # An xrel whose evidence_refs is entirely degraded means the user
        # cannot actually read the source for either side of the bridge.
        "xrels_with_no_readable_source": sum(
            1 for rel in bridge_relations
            if rel.get("evidence_refs") and all(
                ref.get("degraded") for ref in rel["evidence_refs"]
            )
        ),
        # Partial: at least one endpoint of a bridge has no readable summary.
        "xrels_with_partial_source": sum(
            1 for rel in bridge_relations
            if rel.get("evidence_refs") and any(
                ref.get("degraded") for ref in rel["evidence_refs"]
            ) and not all(ref.get("degraded") for ref in rel["evidence_refs"])
        ),
        # A bridge concept that still has xrel_count == 0 is a classification
        # bug (it was put into `bridge` on an old bridge_score but now has no
        # active xrel to back it up).
        "bridge_without_xrels": sum(
            1 for c in bridge_concepts if (c.get("xrel_count") or 0) == 0
        ),
    }

    panorama = {
        "theme": {
            "theme_id": theme.get("theme_id"),
            "name": theme.get("name"),
            "description": theme.get("description", ""),
            "status": theme.get("status"),
            "keywords": theme.get("keywords", []),
        },
        "stats": {
            "concept_count": len(memberships),
            "member_count": len(member_ids),
            "candidate_count": len(candidate_ids),
            "article_count": len(project_set),
            "relation_count": xrel_summary.get("relation_count", 0),
            "type_distribution": xrel_summary.get("type_distribution", {}),
        },
        "grouped_concepts": {
            "core": core_concepts,
            "bridge": bridge_concepts,
            "peripheral": peripheral_concepts,
        },
        "bridge_relations": bridge_relations,
        "articles": sorted(project_set),
        "suggested_memberships": suggestions,
        # Latest auto-discovery run stats; null when discover has never run
        # for this theme (UI renders that as "未运行发现").
        "discovery_coverage": theme.get("discovery_coverage"),
        "silent_failures": silent_failures,
    }

    return jsonify({"success": True, "data": panorama})
