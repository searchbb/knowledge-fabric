"""Wiki Intake APIs for Clippings scan, pre-digest, and sidecar state."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from ...wiki_intake import WikiIntakeStore, WikiIntakeStoreError


wiki_intake_bp = Blueprint("wiki_intake", __name__, url_prefix="/api/wiki-intake")


def _error_response(exc: WikiIntakeStoreError):
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


@wiki_intake_bp.route("/config", methods=["GET"])
def get_config():
    return jsonify({"success": True, "data": WikiIntakeStore().config()})


@wiki_intake_bp.route("/stats", methods=["GET"])
def get_stats():
    return jsonify({"success": True, "data": WikiIntakeStore().stats()})


@wiki_intake_bp.route("/candidates", methods=["GET"])
def list_candidates():
    status = request.args.get("status") or None
    try:
        data = WikiIntakeStore().list_candidates(status=status)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/topics", methods=["GET"])
def list_topics():
    try:
        include_coverage = str(request.args.get("include_coverage") or "").lower() in {"1", "true", "yes", "on"}
        data = WikiIntakeStore().list_topics(include_coverage=include_coverage)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/topics/<topic_id>/articles", methods=["GET"])
def get_topic_articles(topic_id: str):
    try:
        data = WikiIntakeStore().get_topic_articles(topic_id)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/topics/<topic_id>/cluster-coverage", methods=["GET"])
def get_topic_cluster_coverage(topic_id: str):
    try:
        data = WikiIntakeStore().get_topic_cluster_coverage(topic_id)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/topics/<topic_id>/cluster-coverage/override", methods=["POST"])
def set_topic_cluster_coverage_override(topic_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error_response(WikiIntakeStoreError("JSON body must be an object"))
    try:
        data = WikiIntakeStore().set_topic_cluster_coverage_override(topic_id, body)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/topics/<topic_id>/cluster-coverage/link", methods=["POST"])
def link_topic_to_cluster(topic_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error_response(WikiIntakeStoreError("JSON body must be an object"))
    try:
        data = WikiIntakeStore().link_topic_to_cluster(topic_id, body)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data}), 201 if data.get("created") else 200


@wiki_intake_bp.route("/topics/<topic_id>/cluster-coverage/proposals", methods=["POST"])
def request_topic_cluster_proposal(topic_id: str):
    body = request.get_json(silent=True) or {}
    try:
        data = WikiIntakeStore().request_topic_cluster_proposal(topic_id, body)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data}), 201


@wiki_intake_bp.route("/candidates/<candidate_id>", methods=["GET"])
def get_candidate(candidate_id: str):
    try:
        data = WikiIntakeStore().get_candidate(candidate_id)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/candidates/<candidate_id>/processed-result", methods=["GET"])
def get_candidate_processed_result(candidate_id: str):
    try:
        data = WikiIntakeStore().get_processed_result(candidate_id)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/candidates/<candidate_id>/topic-associations/primary", methods=["PATCH"])
def change_candidate_primary_topic(candidate_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error_response(WikiIntakeStoreError("JSON body must be an object"))
    try:
        data = WikiIntakeStore().change_candidate_primary_topic(candidate_id, body)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/candidates/<candidate_id>/topic-associations/unlink-primary", methods=["POST"])
def unlink_candidate_primary_topic(candidate_id: str):
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _error_response(WikiIntakeStoreError("JSON body must be an object"))
    try:
        data = WikiIntakeStore().unlink_candidate_primary_topic(candidate_id, body)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/candidates/<candidate_id>/assets", methods=["GET"])
def get_candidate_asset(candidate_id: str):
    relative_path = request.args.get("path") or ""
    try:
        asset_path, mime_type = WikiIntakeStore().resolve_candidate_asset(candidate_id, relative_path)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    response = send_file(asset_path, mimetype=mime_type, as_attachment=False, conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if mime_type == "image/svg+xml":
        response.headers["Content-Security-Policy"] = "default-src 'none'; img-src data:; style-src 'unsafe-inline'"
    return response


@wiki_intake_bp.route("/scan", methods=["POST"])
def scan_clippings():
    body = request.get_json(silent=True) or {}
    try:
        data = WikiIntakeStore().scan(allow_empty_overwrite=bool(body.get("allow_empty_overwrite")))
    except FileNotFoundError as exc:
        return _error_response(WikiIntakeStoreError(str(exc), code="clippings_missing", status_code=404))
    except NotADirectoryError as exc:
        return _error_response(WikiIntakeStoreError(str(exc), code="clippings_not_directory", status_code=400))
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/decisions", methods=["POST"])
def append_decision():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error_response(WikiIntakeStoreError("JSON body must be an object"))
    try:
        data = WikiIntakeStore().append_decision(body)
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    return jsonify({"success": True, "data": data}), 201


@wiki_intake_bp.route("/runs", methods=["GET"])
def list_runs():
    return jsonify({"success": True, "data": WikiIntakeStore().list_runs()})


@wiki_intake_bp.route("/runs/<run_id>", methods=["GET"])
def get_run(run_id: str):
    runs = WikiIntakeStore().list_runs()["items"]
    hit = next((item for item in runs if item["run_id"] == run_id), None)
    if not hit:
        return _error_response(WikiIntakeStoreError(f"run not found: {run_id}", code="not_found", status_code=404))
    return jsonify({"success": True, "data": hit})


@wiki_intake_bp.route("/process-next", methods=["POST"])
def process_next():
    body = request.get_json(silent=True) or {}
    try:
        data = WikiIntakeStore().process_next(
            adapter=body.get("adapter"),
            timeout_seconds=int(body.get("timeout_seconds") or 1500),
            image_limit=int(body.get("image_limit") or 4),
            enqueue_first=body.get("enqueue_first", True) is not False,
            since_previous_scan=body.get("since_previous_scan", True) is not False,
        )
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    except Exception as exc:  # noqa: BLE001
        return _error_response(WikiIntakeStoreError(str(exc), code="runner_failed", status_code=500))
    return jsonify({"success": True, "data": data})


@wiki_intake_bp.route("/process-batch", methods=["POST"])
def process_batch():
    body = request.get_json(silent=True) or {}
    try:
        data = WikiIntakeStore().process_batch(
            max_runs=int(body.get("max_runs") or 1),
            adapter=body.get("adapter"),
            timeout_seconds=int(body.get("timeout_seconds") or 1500),
            image_limit=int(body.get("image_limit") or 4),
            since_previous_scan=body.get("since_previous_scan", True) is not False,
        )
    except WikiIntakeStoreError as exc:
        return _error_response(exc)
    except Exception as exc:  # noqa: BLE001
        return _error_response(WikiIntakeStoreError(str(exc), code="runner_failed", status_code=500))
    return jsonify({"success": True, "data": data})
