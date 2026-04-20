"""Background daemon that drains the discover job queue.

Part of P1.2 (Discover V2). The P1 first cut left job execution to a manual
CLI drainer (``scripts/run_discover_jobs.py``). This module provides the
opt-in background alternative: a daemon thread that loops on
``claim_and_execute_one`` with a small idle sleep so the queue gets drained
without human intervention.

Two design commitments keep the worker simple:

- **Single thread.** Discover itself already does internal chunk-level
  concurrency (see ``cross_concept_discoverer.py``). A second layer of
  worker concurrency here would just compete with the provider's
  semaphore. One worker running one job at a time is plenty for P1.2.
- **Opt-in start.** The worker is NOT started by default. It's wired into
  ``create_app()`` behind ``AUTO_START_DISCOVER_WORKER=1`` so operators
  can deploy the scheduling change first, observe the main pipeline get
  faster, and only then flip the background execution on.

If the process dies while a job is running, that job's ``heartbeat_at``
will eventually go stale and the next ``recover_stale_running`` call will
reset it to ``pending``. Pass ``recover_stale_on_start=True`` to have the
worker trigger that recovery once on startup.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from .discover_job_executor import claim_and_execute_one
from .discover_job_store import DiscoverJobStore


logger = logging.getLogger("mirofish.discover_worker")


class DiscoverWorker:
    """Single-threaded daemon loop around ``claim_and_execute_one``."""

    def __init__(
        self,
        *,
        store: Optional[DiscoverJobStore] = None,
        idle_sleep_seconds: float = 5.0,
        recover_stale_on_start: bool = False,
        stale_after_seconds: int = 1800,
        actor_id: str = "discover_worker",
        source: str = "discover_background",
    ) -> None:
        self._store = store or DiscoverJobStore()
        self._idle_sleep = max(0.01, float(idle_sleep_seconds))
        self._recover_stale_on_start = bool(recover_stale_on_start)
        self._stale_after_seconds = int(stale_after_seconds)
        self._actor_id = actor_id
        self._source = source

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background thread. No-op if already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="discover_worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        """Signal the loop to exit and wait for the thread to finish."""
        thread = self._thread
        if thread is None:
            return
        self._stop_event.set()
        thread.join(timeout=timeout)
        with self._lock:
            if not (thread.is_alive()):
                self._thread = None

    def is_running(self) -> bool:
        t = self._thread
        return bool(t and t.is_alive())

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        logger.info(
            "discover worker started (idle_sleep=%.2fs recover_stale=%s)",
            self._idle_sleep,
            self._recover_stale_on_start,
        )

        if self._recover_stale_on_start:
            try:
                result = self._store.recover_stale_running(
                    stale_after_seconds=self._stale_after_seconds
                )
                if result["requeued"] or result["gave_up"]:
                    logger.info(
                        "startup stale-recovery: requeued=%d gave_up=%d",
                        len(result["requeued"]),
                        len(result["gave_up"]),
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("stale-recovery at startup failed: %s", exc)

        while not self._stop_event.is_set():
            try:
                outcome = claim_and_execute_one(
                    store=self._store,
                    actor_id=self._actor_id,
                    source=self._source,
                )
            except Exception as exc:  # noqa: BLE001
                # The executor already catches discoverer exceptions and
                # marks the job failed. Anything reaching here is a bug in
                # the store/claim path — log loudly but don't exit the
                # thread, a subsequent job may succeed.
                logger.exception("discover worker claim loop error: %s", exc)
                outcome = None

            if outcome is None:
                # Nothing pending: sleep but wake up promptly on stop().
                self._stop_event.wait(self._idle_sleep)
                continue

            status = outcome.get("status", "?")
            discovered = (outcome.get("stats") or {}).get("discovered", 0)
            logger.info(
                "discover worker executed %s -> %s (discovered=%s)",
                outcome.get("job_id"),
                status,
                discovered,
            )

        logger.info("discover worker stopped")


# ---------------------------------------------------------------------------
# Module-level singleton helpers (for create_app wiring).
# ---------------------------------------------------------------------------

_global_worker: Optional[DiscoverWorker] = None
_global_lock = threading.Lock()


def get_global_worker() -> Optional[DiscoverWorker]:
    """Return the process-wide worker, if one has been started."""
    return _global_worker


def start_global_worker(
    *,
    idle_sleep_seconds: float = 5.0,
    recover_stale_on_start: bool = True,
) -> DiscoverWorker:
    """Start the process-wide discover worker. Idempotent."""
    global _global_worker
    with _global_lock:
        if _global_worker is not None and _global_worker.is_running():
            return _global_worker
        _global_worker = DiscoverWorker(
            idle_sleep_seconds=idle_sleep_seconds,
            recover_stale_on_start=recover_stale_on_start,
        )
        _global_worker.start()
    return _global_worker


def stop_global_worker(*, timeout: float = 5.0) -> None:
    global _global_worker
    with _global_lock:
        worker = _global_worker
        _global_worker = None
    if worker is not None:
        worker.stop(timeout=timeout)
