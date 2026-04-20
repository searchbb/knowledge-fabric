"""REST surface for the cross-concept discover job queue (P1.4 web visibility).

Endpoints (all mounted under ``/api/auto``):

- ``GET  /api/auto/discover-jobs/stats``         counts by status + total
- ``GET  /api/auto/discover-jobs``               list (optional ?status / ?limit)
- ``GET  /api/auto/discover-jobs/<job_id>``      single-job detail
- ``POST /api/auto/discover-jobs/run-once``      execute the oldest pending job once
- ``POST /api/auto/discover-jobs/recover-stale`` rescue running jobs whose
                                                 heartbeat is older than the cutoff

``run-once`` is intentionally synchronous. It's here so the UI can offer a
"run now" button even when the background worker is off (default). The
background worker in ``discover_worker.py`` uses the same executor, so
there is no risk of divergent behaviour between the two paths.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...services.auto.discover_job_executor import claim_and_execute_one
from ...services.auto.discover_job_store import (
    DiscoverJobStore,
    DiscoverJobStoreError,
)
from ...services.auto.discover_skip_log import DiscoverSkipLog


discover_jobs_bp = Blueprint(
    "discover_jobs", __name__, url_prefix="/api/auto/discover-jobs"
)


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@discover_jobs_bp.route("/stats", methods=["GET"])
def get_stats():
    """Counts by status + total. Cheap enough to poll every few seconds."""
    store = DiscoverJobStore()
    data = store.load()
    jobs = data["jobs"]
    counts: dict[str, int] = {}
    for job in jobs:
        key = str(job.get("status") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return jsonify(
        {
            "success": True,
            "data": {
                "total": len(jobs),
                "by_status": counts,
            },
        }
    )


@discover_jobs_bp.route("", methods=["GET"])
def list_jobs():
    """List jobs. ``?status=pending`` filters; ``?limit=N`` caps the result."""
    status = request.args.get("status")
    try:
        limit = int(request.args.get("limit") or 200)
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 1000))

    store = DiscoverJobStore()
    jobs = store.list_jobs(status=status)
    return jsonify(
        {
            "success": True,
            "data": {
                "jobs": jobs[:limit],
                "total": len(jobs),
                "filter_status": status,
            },
        }
    )


@discover_jobs_bp.route("/<job_id>", methods=["GET"])
def get_job(job_id: str):
    """Return the full record for a single job, or 404."""
    store = DiscoverJobStore()
    job = store.get_job(job_id)
    if job is None:
        return (
            jsonify(
                {"success": False, "error": f"unknown job_id: {job_id}"}
            ),
            404,
        )
    return jsonify({"success": True, "data": job})


# ---------------------------------------------------------------------------
# Control endpoints
# ---------------------------------------------------------------------------


@discover_jobs_bp.route("/run-once", methods=["POST"])
def run_once():
    """Claim + execute the oldest pending job. Synchronous."""
    try:
        outcome = claim_and_execute_one()
    except DiscoverJobStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if outcome is None:
        return jsonify({"success": True, "data": {"executed": False}})
    return jsonify({"success": True, "data": {"executed": True, "outcome": outcome}})


@discover_jobs_bp.route("/by-theme/<theme_id>", methods=["GET"])
def by_theme(theme_id: str):
    """Aggregate view used by the Theme detail page (P4 step 8).

    Returns:
    - ``coverage``: latest-run summary (same as theme.discovery_coverage)
    - ``history``: rolling last-N runs (theme.discovery_history)
    - ``jobs``: every DiscoverJob matching this theme, newest first
    - ``stats``: per-status counts + total for the filtered job set

    An unknown theme_id (e.g. deleted theme with orphan jobs) still
    returns 200 with empty coverage/history so the UI doesn't have to
    branch — this lets the Theme page show "jobs still around but theme
    registry says gone" as a soft state.
    """
    # Jobs are the authoritative source for "discover activity on this
    # theme". Always safe to read, even when the theme itself is gone.
    store = DiscoverJobStore()
    all_jobs = store.list_jobs()
    jobs = [j for j in all_jobs if j.get("theme_id") == theme_id]
    # Newest-first ordering for the UI.
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)

    by_status: dict[str, int] = {}
    for j in jobs:
        key = str(j.get("status") or "unknown")
        by_status[key] = by_status.get(key, 0) + 1

    # Theme registry is optional context — discovery_coverage / history.
    coverage: dict = {}
    history: list = []
    try:
        from ...services.registry.global_theme_registry import (
            get_theme,
            GlobalThemeNotFoundError,
        )
        try:
            theme = get_theme(theme_id)
            coverage = theme.get("discovery_coverage") or {}
            history = theme.get("discovery_history") or []
        except GlobalThemeNotFoundError:
            pass
    except Exception:  # pragma: no cover - defensive, theme module may error
        pass

    return jsonify({
        "success": True,
        "data": {
            "theme_id": theme_id,
            "coverage": coverage,
            "history": history,
            "jobs": jobs,
            "stats": {"total": len(jobs), "by_status": by_status},
        },
    })


@discover_jobs_bp.route("/recent-skips", methods=["GET"])
def recent_skips():
    """Rolling window of schedule-time skips (cooldown/budget).

    Surfaces per-theme-cooldown and daily-budget throttle events so the
    Discover panel can render "N jobs blocked in the last hour" without
    the user having to drill into per-URL summaries.

    Query params:
    - ``within_seconds`` (default 3600): only return entries newer than this.
    - ``limit`` (default 20): cap on returned entries.
    """
    try:
        within_seconds = int(request.args.get("within_seconds") or 3600)
    except ValueError:
        within_seconds = 3600
    try:
        limit = int(request.args.get("limit") or 20)
    except ValueError:
        limit = 20

    log = DiscoverSkipLog()
    entries = log.list_recent(within_seconds=within_seconds, limit=limit)
    stats = log.stats(within_seconds=within_seconds)
    return jsonify(
        {
            "success": True,
            "data": {
                "skips": entries,
                "stats": stats,
                "window_seconds": within_seconds,
            },
        }
    )


@discover_jobs_bp.route("/by-project/<project_id>", methods=["GET"])
def by_project(project_id: str):
    """Every DiscoverJob triggered by the given project_id, newest first.

    Powers article/project-level discover status surfaces (P4 step 12).
    Returns the same shape as ``/by-theme/...`` minus the coverage /
    history block — those are theme-scoped concepts that don't apply
    at project granularity.
    """
    store = DiscoverJobStore()
    all_jobs = store.list_jobs()
    jobs = [j for j in all_jobs if j.get("trigger_project_id") == project_id]
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)

    by_status: dict[str, int] = {}
    for j in jobs:
        key = str(j.get("status") or "unknown")
        by_status[key] = by_status.get(key, 0) + 1

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "jobs": jobs,
            "stats": {"total": len(jobs), "by_status": by_status},
        },
    })


@discover_jobs_bp.route("/<job_id>/retry", methods=["POST"])
def retry_job(job_id: str):
    """Move a terminal (partial/failed/cancelled) job back to ``pending``.

    Returns 404 when the job doesn't exist; 409 when the current status
    can't be retried (running / pending / completed). The UI uses the
    409 path to say "this job can't be retried from its current state".
    """
    store = DiscoverJobStore()
    if store.get_job(job_id) is None:
        return jsonify({"success": False, "error": f"unknown job_id: {job_id}"}), 404
    try:
        job = store.retry_job(job_id)
    except DiscoverJobStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    return jsonify({"success": True, "data": job})


@discover_jobs_bp.route("/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id: str):
    """Cancel a ``pending`` job. Running jobs can't be cancelled — use
    recover-stale for crashed workers. Completed/failed/etc. jobs already
    have their final state and cancelling them is a no-op error.
    """
    store = DiscoverJobStore()
    if store.get_job(job_id) is None:
        return jsonify({"success": False, "error": f"unknown job_id: {job_id}"}), 404
    try:
        job = store.cancel_pending_job(job_id)
    except DiscoverJobStoreError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    return jsonify({"success": True, "data": job})


@discover_jobs_bp.route("/recover-stale", methods=["POST"])
def recover_stale():
    """Revive running jobs whose heartbeat is older than the cutoff."""
    body = request.get_json(silent=True) or {}
    try:
        stale_seconds = int(body.get("stale_after_seconds") or 1800)
    except (TypeError, ValueError):
        stale_seconds = 1800

    store = DiscoverJobStore()
    result = store.recover_stale_running(stale_after_seconds=stale_seconds)
    return jsonify({"success": True, "data": result})
