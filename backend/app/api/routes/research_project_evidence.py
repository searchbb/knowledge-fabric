"""Local Evidence Pack API for ResearchProjects."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...models.research_project import ResearchProjectStore, ResearchProjectStoreError
from ...services.kfc_promotion_store import KfcPromotionStore, KfcPromotionStoreError
from ...services.research.local_evidence_pack_service import generate_local_evidence_pack


research_project_evidence_bp = Blueprint(
    "research_project_evidence", __name__, url_prefix="/api/research-projects"
)


@research_project_evidence_bp.route("/<project_id>/local-evidence-pack", methods=["GET"])
def get_local_evidence_pack(project_id: str):
    store = ResearchProjectStore()
    project = store.get(project_id)
    if project is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    pack = project.local_evidence_pack or {
        "status": "not_generated",
        "candidates": [],
        "accepted_evidence_ids": [],
        "rejected_evidence_ids": [],
        "summary": {
            "candidate_count": 0,
            "accepted_count": 0,
            "degraded_count": 0,
            "source_project_count": 0,
            "concept_count": 0,
            "theme_count": 0,
        },
    }
    return jsonify({"success": True, "data": {"project_id": project_id, "local_evidence_pack": pack}})


@research_project_evidence_bp.route("/<project_id>/local-evidence-pack/search", methods=["POST"])
def search_local_evidence_pack(project_id: str):
    store = ResearchProjectStore()
    project = store.get(project_id)
    if project is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404

    body = request.get_json(silent=True) or {}
    keywords = body.get("keywords") or []
    if not isinstance(keywords, list):
        return jsonify({"success": False, "error": "keywords must be an array"}), 400
    try:
        limit = int(body.get("limit") or 30)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "limit must be an integer"}), 400
    include_degraded = bool(body.get("include_degraded", True))

    pack = generate_local_evidence_pack(
        project,
        keywords=[str(item) for item in keywords],
        limit=limit,
        include_degraded=include_degraded,
    )
    updated = store.save_local_evidence_pack(project_id, pack)
    if updated is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({"success": True, "data": {"project_id": project_id, "local_evidence_pack": pack}})


@research_project_evidence_bp.route(
    "/<project_id>/local-evidence-pack/candidates/<evidence_id>",
    methods=["PATCH"],
)
def update_local_evidence_candidate(project_id: str, evidence_id: str):
    body = request.get_json(silent=True) or {}
    status = str(body.get("status") or "").strip()
    if status not in {"candidate", "accepted", "rejected"}:
        return jsonify({"success": False, "error": "status must be candidate, accepted, or rejected"}), 400
    note = str(body.get("note") or "")
    try:
        project = ResearchProjectStore().update_local_evidence_candidate_status(
            project_id,
            evidence_id,
            status=status,
            note=note,
        )
        if status == "accepted" and project is not None:
            accepted = next(
                (item for item in (project.evidence_items or []) if item.get("evidence_id") == evidence_id),
                {},
            )
            source_concept_id = str(accepted.get("source_concept_id") or "").strip()
            is_kfc_deposited_evidence = bool(
                accepted.get("source_material_slice_id")
                and accepted.get("source_lead_id")
                and accepted.get("source_article_id")
            )
            if source_concept_id and is_kfc_deposited_evidence:
                KfcPromotionStore().attach_concept_to_research_project(
                    source_concept_id,
                    project_id,
                    evidence_id=evidence_id,
                    actor="human",
                    reason=note or "Accepted local evidence candidate into ResearchProject evidence.",
                )
    except ResearchProjectStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except KfcPromotionStoreError as exc:
        return jsonify({"success": False, "error": str(exc), "code": exc.code}), exc.status_code
    if project is None:
        return jsonify({"success": False, "error": f"research project not found: {project_id}"}), 404
    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "local_evidence_pack": project.local_evidence_pack,
            "evidence_items": project.evidence_items,
        },
    })
