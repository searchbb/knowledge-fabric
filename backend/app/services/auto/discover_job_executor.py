"""Bridge between the discover job store and the existing discoverer.

Two entry points:

- :func:`execute_job` — finalize one already-running job. The store
  transitions to ``completed`` / ``partial`` / ``failed`` based on the
  discover stats. Raises if the job isn't in running state because the
  claim step is the caller's responsibility (keeps claim atomic with
  the store's flock).
- :func:`claim_and_execute_one` — convenience loop for CLI / future worker:
  claim the oldest pending job, then execute it. Returns ``None`` if
  nothing was pending.

This module never blocks on LLM calls without going through
``CrossConceptDiscoverer.discover``, which already owns its own timeout,
concurrency, and chunk-level soft-fail.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .cross_concept_discoverer import CrossConceptDiscoverer
from .discover_job_store import DiscoverJobStore, DiscoverJobStoreError


logger = logging.getLogger("mirofish.discover_job_executor")


def execute_job(
    job_id: str,
    *,
    store: Optional[DiscoverJobStore] = None,
    actor_id: str = "discover_worker",
    source: str = "discover_background",
) -> dict[str, Any]:
    """Execute the discover logic for a job that is already ``running``.

    Returns the outcome dict ``{"job_id", "status", "stats", "error"}``.
    The store is updated with the terminal state before return.
    """
    store = store or DiscoverJobStore()

    job = store.get_job(job_id)
    if job is None:
        raise DiscoverJobStoreError(f"unknown job_id: {job_id}")
    if job.get("status") != "running":
        raise RuntimeError(
            f"job {job_id} is not running (status={job.get('status')!r}); "
            f"claim via store.claim_next() first"
        )

    theme_id = job.get("theme_id") or ""
    new_entry_ids = list(job.get("new_entry_ids") or [])
    heartbeat_callback = lambda: store.heartbeat(job_id)

    try:
        discoverer = CrossConceptDiscoverer(actor_id=actor_id, source=source)
        result = discoverer.discover(
            theme_id=theme_id,
            new_entry_ids=new_entry_ids,
            run_id=job.get("origin_run_id") or job_id,
            job_id=job_id,
            heartbeat_callback=heartbeat_callback,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("discover job %s failed: %s", job_id, exc)
        store.mark_failed(job_id, error=str(exc))
        return {
            "job_id": job_id,
            "status": "failed",
            "stats": {},
            "error": str(exc),
        }

    chunks_failed = int(result.get("llm_chunks_failed") or 0)
    # A job is "partial" when at least one chunk raised but the phase still
    # produced state we want to preserve. The discoverer itself is soft-fail
    # at chunk granularity (see cross_concept_discoverer.py:296-320) so we
    # don't need to decide between 'retry the whole job' and 'accept what
    # we have' — the job is simply flagged partial and the next run_id can
    # choose to retry it later.
    if chunks_failed > 0:
        store.mark_partial(job_id, stats=result)
        status = "partial"
    else:
        store.mark_completed(job_id, stats=result)
        status = "completed"

    return {
        "job_id": job_id,
        "status": status,
        "stats": result,
        "error": None,
    }


def claim_and_execute_one(
    *,
    store: Optional[DiscoverJobStore] = None,
    actor_id: str = "discover_worker",
    source: str = "discover_background",
) -> Optional[dict[str, Any]]:
    """Claim the oldest pending job and execute it. ``None`` if nothing pending."""
    store = store or DiscoverJobStore()
    claimed = store.claim_next()
    if claimed is None:
        return None
    return execute_job(
        claimed["job_id"],
        store=store,
        actor_id=actor_id,
        source=source,
    )
