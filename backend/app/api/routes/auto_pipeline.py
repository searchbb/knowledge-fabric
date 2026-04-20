"""REST surface for the auto URL pipeline.

Currently exposes a single endpoint::

    POST /api/auto/process-pending

Body (optional)::

    {
        "max_runs": 1,
        "add": ["https://example.com/article"]
    }

The handler invokes the same :class:`AutoPipelineRunner` used by the CLI
script, so behaviour stays in lockstep. The response is a synchronous JSON
payload describing what happened in this drain.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...services.auto.note_store import save_note_to_file
from ...services.auto.pending_store import (
    DuplicateUrlError,
    PendingUrlStore,
    RetryNotAllowedError,
)
from ...services.auto.pipeline_runner import AutoPipelineRunner


auto_pipeline_bp = Blueprint("auto_pipeline", __name__, url_prefix="/api/auto")


@auto_pipeline_bp.route("/pending-urls", methods=["GET"])
def list_pending() -> "Response":
    """Return the current contents of pending-urls.json."""
    store = PendingUrlStore()
    return jsonify({"success": True, "data": store.load()})


@auto_pipeline_bp.route("/pending-urls", methods=["POST"])
def add_pending() -> "Response":
    """Add one or more URLs to the pending bucket."""
    body = request.get_json(silent=True) or {}
    urls = body.get("urls") or ([body.get("url")] if body.get("url") else [])
    allow_dup = bool(body.get("allow_duplicate"))
    if not urls:
        return jsonify({"success": False, "error": "missing urls"}), 400

    store = PendingUrlStore()
    added: list[dict] = []
    duplicates: list[dict] = []
    for url in urls:
        try:
            item = store.add_pending(url, allow_duplicate=allow_dup)
            added.append({"url": url, "url_fingerprint": item["url_fingerprint"]})
        except DuplicateUrlError as error:
            duplicates.append(
                {
                    "url": url,
                    "existing_bucket": error.existing_bucket,
                    "existing_url": error.existing_item.get("url"),
                }
            )
    return jsonify(
        {
            "success": True,
            "data": {"added": added, "duplicates": duplicates},
        }
    )


@auto_pipeline_bp.route("/pending-notes", methods=["POST"])
def add_pending_note() -> "Response":
    """Add a rich-text paste entry to the pending bucket.

    Body::

        {
            "title": "...",       # required
            "markdown": "...",    # required — already-converted Markdown
            "allow_duplicate": false  # optional
        }

    The markdown is written to a content-hashed file under
    ``backend/data/notes/`` and registered via
    ``PendingUrlStore.add_pending(md_path=...)``. The downstream drain
    logic handles it identically to a URL-sourced markdown file.
    """
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    markdown = (body.get("markdown") or "").strip()
    allow_dup = bool(body.get("allow_duplicate"))

    if not title:
        return jsonify({"success": False, "error": "title is required"}), 400
    if not markdown:
        return jsonify({"success": False, "error": "markdown is required"}), 400

    try:
        note_path = save_note_to_file(title=title, body_markdown=markdown)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    store = PendingUrlStore()
    try:
        item = store.add_pending(md_path=str(note_path), allow_duplicate=allow_dup)
        added = [{
            "title": title,
            "md_path": str(note_path),
            "url_fingerprint": item["url_fingerprint"],
        }]
        duplicates: list[dict] = []
    except DuplicateUrlError as error:
        added = []
        duplicates = [{
            "title": title,
            "md_path": str(note_path),
            "existing_bucket": error.existing_bucket,
            "existing_url": error.existing_item.get("url") or error.existing_item.get("md_path"),
        }]

    return jsonify({
        "success": True,
        "data": {"added": added, "duplicates": duplicates},
    })


@auto_pipeline_bp.route("/pending-urls/<fingerprint>", methods=["DELETE"])
def cancel_pending(fingerprint: str) -> "Response":
    """Remove one pending URL from the queue before it is claimed.

    Only ``pending`` entries can be cancelled. Returns 409 if the entry is
    already ``in_flight`` (the worker owns it) and 404 if the fingerprint is
    not in the pending bucket.
    """
    store = PendingUrlStore()
    try:
        item = store.cancel_pending(fingerprint)
    except RuntimeError as err:
        return jsonify({"success": False, "error": str(err)}), 409
    except KeyError as err:
        return jsonify({"success": False, "error": str(err)}), 404
    return jsonify({"success": True, "data": {"cancelled": item}})


@auto_pipeline_bp.route("/retry-errored", methods=["POST"])
def retry_errored() -> "Response":
    """Move a failed URL back to pending so the next drain picks it up again.

    Body::

        {"url_fingerprint": "sha256:..."}

    Response on success (200)::

        {"success": true, "data": {"url": "...", "url_fingerprint": "...", "attempt": 1}}

    Errors:
        - 400 if ``url_fingerprint`` is missing or the body is not JSON.
        - 404 if no entry with that fingerprint exists in the errored bucket.
        - 409 if the fingerprint is already live in pending or in_flight —
          retrying would create a duplicate run. The UI should tell the user
          the URL is already queued.
    """
    body = request.get_json(silent=True)
    if not body or not body.get("url_fingerprint"):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "missing url_fingerprint in body",
                }
            ),
            400,
        )

    fingerprint = body["url_fingerprint"]
    store = PendingUrlStore()
    try:
        entry = store.retry_errored(fingerprint)
    except RetryNotAllowedError as error:
        # Split the two failure modes into distinct HTTP codes so the UI
        # can distinguish "nothing to retry" from "already queued".
        if "not in errored" in error.reason:
            status = 404
        else:
            status = 409
        return (
            jsonify({"success": False, "error": str(error)}),
            status,
        )

    return jsonify({"success": True, "data": entry})


@auto_pipeline_bp.route("/retry-all-errored", methods=["POST"])
def retry_all_errored() -> "Response":
    """Move every unique-fingerprint errored entry back to pending.

    Response::

        {
          "success": true,
          "data": {
            "retried": ["fp1", "fp2"],
            "skipped_already_queued": ["fp3"],   # already live in pending/in_flight
            "deduped": 1,                          # historical duplicate rows dropped
            "cleared_errored_count": 3             # total entries removed from errored
          }
        }
    """
    store = PendingUrlStore()
    before_errored = len(store.load()["errored"])
    result = store.retry_all_errored()
    after_errored = len(store.load()["errored"])
    result["cleared_errored_count"] = before_errored - after_errored
    return jsonify({"success": True, "data": result})


@auto_pipeline_bp.route("/clear-errored", methods=["POST"])
def clear_errored() -> "Response":
    """Delete every entry in the errored bucket (destructive).

    Response::

        {"success": true, "data": {"cleared": 4}}
    """
    store = PendingUrlStore()
    count = store.clear_errored()
    return jsonify({"success": True, "data": {"cleared": count}})


@auto_pipeline_bp.route("/process-pending", methods=["POST"])
def process_pending() -> "Response":
    """Drain the pending bucket synchronously and return per-URL results."""
    body = request.get_json(silent=True) or {}
    max_runs = body.get("max_runs")
    if max_runs is not None:
        try:
            max_runs = int(max_runs)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "max_runs must be int"}), 400

    add_urls = body.get("add") or []
    store = PendingUrlStore()
    if add_urls:
        for url in add_urls:
            try:
                store.add_pending(url, allow_duplicate=bool(body.get("allow_duplicate")))
            except DuplicateUrlError:
                pass  # silent dedup; the response will not include duplicates

    runner = AutoPipelineRunner(store=store)
    result = runner.run_until_drained(max_runs=max_runs)
    return jsonify({"success": True, "data": result.to_dict()})
