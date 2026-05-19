"""Topic Cluster APIs.

These routes intentionally expose only KFC-owned sidecar assets. They do not call
models, Codex, GPT, schedulers, workers, or ResearchProject creation flows.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...services.topic_cluster_refresh_request_store import (
    TopicClusterRefreshRequestStore,
    TopicClusterRefreshRequestStoreError,
)
from ...services.topic_cluster_proposal_store import TopicClusterProposalStore, TopicClusterProposalStoreError
from ...services.topic_cluster_asset_index import TopicClusterAssetIndexService
from ...services.topic_cluster_store import TopicClusterStore, TopicClusterStoreError
from ...services.kfc_promotion_store import KfcPromotionStore, KfcPromotionStoreError


topic_clusters_bp = Blueprint("topic_clusters", __name__, url_prefix="/api/topic-clusters")
topic_cluster_links_bp = Blueprint(
    "topic_cluster_links", __name__, url_prefix="/api/topic-cluster-links"
)


def _json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise TopicClusterStoreError("JSON body must be an object")
    return payload


def _error_response(exc: TopicClusterStoreError):
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


def _refresh_error_response(exc: TopicClusterRefreshRequestStoreError):
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


def _proposal_error_response(exc: TopicClusterProposalStoreError):
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


def _promotion_error_response(exc: KfcPromotionStoreError):
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


def _truthy_query(name: str) -> bool:
    return str(request.args.get(name) or "").lower() in {"1", "true", "yes", "on"}


@topic_clusters_bp.route("", methods=["GET"])
def list_topic_clusters():
    result = TopicClusterStore().list_clusters(
        include_counts=_truthy_query("include_counts"),
        include_articles=_truthy_query("include_articles"),
    )
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("", methods=["POST"])
def create_topic_cluster():
    try:
        result = TopicClusterStore().create_cluster(_json_payload())
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": result}), 201


@topic_clusters_bp.route("/by-target", methods=["GET"])
def get_topic_clusters_by_target():
    target_type = request.args.get("target_type", "")
    target_id = request.args.get("target_id", "")
    try:
        result = TopicClusterStore().find_by_target(target_type, target_id)
    except TopicClusterStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/refresh-requests", methods=["POST"])
def create_topic_cluster_refresh_request():
    try:
        result = TopicClusterRefreshRequestStore().create(_json_payload())
    except TopicClusterRefreshRequestStoreError as exc:
        return _refresh_error_response(exc)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": result}), 201


@topic_clusters_bp.route("/refresh-requests", methods=["GET"])
def list_topic_cluster_refresh_requests():
    try:
        limit = int(request.args.get("limit", "20"))
    except ValueError:
        limit = 20
    result = TopicClusterRefreshRequestStore().list(limit=max(1, min(limit, 100)))
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/refresh-requests/<request_id>", methods=["GET"])
def get_topic_cluster_refresh_request(request_id: str):
    try:
        result = TopicClusterRefreshRequestStore().get(request_id)
    except TopicClusterRefreshRequestStoreError as exc:
        return _refresh_error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster refresh request not found: {request_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/proposals", methods=["GET"])
def list_topic_cluster_proposals():
    result = TopicClusterProposalStore().list_proposals()
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/proposals/<proposal_id>", methods=["GET"])
def get_topic_cluster_proposal(proposal_id: str):
    try:
        result = TopicClusterProposalStore().get_proposal(proposal_id)
    except TopicClusterProposalStoreError as exc:
        return _proposal_error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster proposal not found: {proposal_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/proposals/<proposal_id>/apply", methods=["POST"])
def apply_topic_cluster_proposal(proposal_id: str):
    try:
        payload = _json_payload()
        result = TopicClusterProposalStore().apply_proposal(
            proposal_id,
            payload.get("accepted_actions"),
            payload.get("rejected_actions") or [],
        )
    except TopicClusterProposalStoreError as exc:
        return _proposal_error_response(exc)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster proposal not found: {proposal_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>", methods=["GET"])
def get_topic_cluster(cluster_id: str):
    try:
        result = TopicClusterStore().get_cluster(
            cluster_id,
            include_counts=_truthy_query("include_counts"),
            include_articles=_truthy_query("include_articles"),
        )
    except TopicClusterStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster not found: {cluster_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/asset-index", methods=["GET"])
def get_topic_cluster_asset_index(cluster_id: str):
    try:
        result = TopicClusterAssetIndexService().build(cluster_id)
    except TopicClusterStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster not found: {cluster_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/promotion-basket", methods=["GET"])
def get_topic_cluster_promotion_basket(cluster_id: str):
    try:
        result = KfcPromotionStore().list_promotion_basket(cluster_id)
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/promotion-changes", methods=["GET"])
def get_topic_cluster_promotion_changes(cluster_id: str):
    try:
        limit = int(request.args.get("limit") or 30)
        result = KfcPromotionStore().list_recent_changes(cluster_id, limit=limit)
    except ValueError:
        return jsonify({"success": False, "error": "limit must be an integer", "code": "validation_error"}), 400
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/articles/<article_id>/processing-review", methods=["GET"])
def get_topic_cluster_article_processing_review(cluster_id: str, article_id: str):
    try:
        result = KfcPromotionStore().get_article_processing_review(cluster_id, article_id)
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/articles/<article_id>/processing-review/batch-actions", methods=["POST"])
def apply_topic_cluster_article_processing_batch_action(cluster_id: str, article_id: str):
    try:
        result = KfcPromotionStore().apply_article_processing_batch_action(
            cluster_id,
            article_id,
            _json_payload(),
        )
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/kfc-concepts/<concept_id>", methods=["PATCH"])
def update_kfc_concept(concept_id: str):
    try:
        result = KfcPromotionStore().update_concept(concept_id, _json_payload())
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/kfc-concepts/<concept_id>/deprecate", methods=["POST"])
def deprecate_kfc_concept(concept_id: str):
    try:
        result = KfcPromotionStore().deprecate_concept(concept_id, _json_payload())
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/kfc-concepts/<concept_id>/relations", methods=["DELETE"])
def unlink_kfc_concept_relation(concept_id: str):
    try:
        result = KfcPromotionStore().unlink_concept_relation(
            concept_id,
            relation_id=request.args.get("relation_id"),
            target_type=request.args.get("target_type"),
            target_id=request.args.get("target_id"),
        )
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/material-slices", methods=["POST"])
def create_topic_cluster_material_slice(cluster_id: str):
    try:
        result = KfcPromotionStore().create_material_slice(cluster_id, _json_payload())
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": result}), 201


@topic_clusters_bp.route("/<cluster_id>/relation-candidates", methods=["POST"])
def create_topic_cluster_relation_candidate(cluster_id: str):
    try:
        result = KfcPromotionStore().create_relation_candidate(cluster_id, _json_payload())
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": result}), 201


@topic_clusters_bp.route("/<cluster_id>/relation-candidates/<relation_candidate_id>/actions", methods=["POST"])
def apply_topic_cluster_relation_candidate_action(cluster_id: str, relation_candidate_id: str):
    try:
        result = KfcPromotionStore().apply_relation_candidate_action(
            cluster_id,
            relation_candidate_id,
            _json_payload(),
        )
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"relation candidate not found: {relation_candidate_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/lead-promotions/<promotion_id>", methods=["GET"])
def get_topic_cluster_lead_promotion(cluster_id: str, promotion_id: str):
    try:
        result = KfcPromotionStore().get_promotion_trace(cluster_id, promotion_id)
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"lead promotion not found: {promotion_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/lead-promotions/<promotion_id>/actions", methods=["POST"])
def apply_topic_cluster_lead_promotion_action(cluster_id: str, promotion_id: str):
    try:
        result = KfcPromotionStore().apply_promotion_action(cluster_id, promotion_id, _json_payload())
    except KfcPromotionStoreError as exc:
        return _promotion_error_response(exc)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"lead promotion not found: {promotion_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>", methods=["PATCH"])
def update_topic_cluster(cluster_id: str):
    try:
        result = TopicClusterStore().update_cluster(cluster_id, _json_payload())
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster not found: {cluster_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/links", methods=["GET"])
def get_topic_cluster_links(cluster_id: str):
    try:
        result = TopicClusterStore().get_cluster_links(cluster_id)
    except TopicClusterStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster not found: {cluster_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_clusters_bp.route("/<cluster_id>/links", methods=["POST"])
def create_topic_cluster_link(cluster_id: str):
    try:
        result = TopicClusterStore().create_cluster_link(cluster_id, _json_payload())
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster not found: {cluster_id}"}), 404
    return jsonify({"success": True, "data": result}), 201


@topic_cluster_links_bp.route("/<link_id>", methods=["PATCH"])
def update_topic_cluster_link(link_id: str):
    try:
        result = TopicClusterStore().update_cluster_link(link_id, _json_payload())
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster link not found: {link_id}"}), 404
    return jsonify({"success": True, "data": result})


@topic_cluster_links_bp.route("/<link_id>", methods=["DELETE"])
def delete_topic_cluster_link(link_id: str):
    try:
        result = TopicClusterStore().delete_cluster_link(link_id)
    except TopicClusterStoreError as exc:
        return _error_response(exc)
    if result is None:
        return jsonify({"success": False, "error": f"topic cluster link not found: {link_id}"}), 404
    return jsonify({"success": True, "data": result})
