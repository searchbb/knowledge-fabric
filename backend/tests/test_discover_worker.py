"""Tests for ``app.services.auto.discover_worker.DiscoverWorker``.

The worker is a tiny daemon thread that calls
``claim_and_execute_one`` in a loop, sleeping between empty polls. It
replaces the manual CLI drainer for users who want discover to just happen
in the background.

Design constraints verified here:

- start() returns immediately; work happens on a daemon thread.
- stop() blocks until the loop actually exits.
- Empty queue → the worker sleeps; it doesn't spin.
- Exceptions in the executor don't crash the loop.
- recover_stale_running runs once at startup (opt-in).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.auto.discover_job_store import DiscoverJobStore
from app.services.auto.discover_worker import DiscoverWorker


@pytest.fixture
def store(tmp_path: Path) -> DiscoverJobStore:
    return DiscoverJobStore(tmp_path / "discover-jobs.json")


class TestLifecycle:
    def test_start_returns_immediately_and_thread_is_alive(
        self, store: DiscoverJobStore
    ):
        worker = DiscoverWorker(store=store, idle_sleep_seconds=0.05)
        worker.start()
        try:
            assert worker.is_running() is True
        finally:
            worker.stop(timeout=2.0)
        assert worker.is_running() is False

    def test_double_start_is_a_noop(self, store: DiscoverJobStore):
        worker = DiscoverWorker(store=store, idle_sleep_seconds=0.05)
        worker.start()
        worker.start()  # should not raise / not spawn a second thread
        try:
            assert worker.is_running() is True
        finally:
            worker.stop(timeout=2.0)

    def test_stop_before_start_is_a_noop(self, store: DiscoverJobStore):
        worker = DiscoverWorker(store=store)
        worker.stop(timeout=1.0)  # must not raise


class TestClaimLoop:
    def test_claims_and_executes_pending_jobs(self, store: DiscoverJobStore):
        for i in range(3):
            store.create_job(
                theme_id=f"t_{i}",
                trigger_project_id=f"p_{i}",
                new_entry_ids=["canon_a"],
            )

        fake_result = {
            "candidates_count": 1,
            "discovered": 1,
            "skipped": 0,
            "errors": [],
            "llm_chunks_total": 1,
            "llm_chunks_succeeded": 1,
            "llm_chunks_failed": 0,
        }

        with patch(
            "app.services.auto.discover_job_executor.CrossConceptDiscoverer"
        ) as MockDiscoverer:
            MockDiscoverer.return_value.discover.return_value = fake_result
            worker = DiscoverWorker(store=store, idle_sleep_seconds=0.01)
            worker.start()
            # Wait until the queue is empty, bounded.
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if not store.list_jobs(status="pending"):
                    break
                time.sleep(0.02)
            worker.stop(timeout=2.0)

        # All three jobs should be terminal (completed).
        all_jobs = store.list_jobs()
        assert len(all_jobs) == 3
        assert all(j["status"] == "completed" for j in all_jobs)

    def test_empty_queue_sleeps_not_spins(self, store: DiscoverJobStore):
        """With no pending work, the worker should not hammer the store."""
        call_count = {"n": 0}
        real_claim = store.claim_next

        def counting_claim():
            call_count["n"] += 1
            return real_claim()

        store.claim_next = counting_claim  # type: ignore[assignment]

        worker = DiscoverWorker(store=store, idle_sleep_seconds=0.1)
        worker.start()
        time.sleep(0.35)
        worker.stop(timeout=2.0)

        # With idle_sleep_seconds=0.1 and ~0.35s runtime we expect ~3-5 calls,
        # definitely not 100+. Loose bound: fewer than 20.
        assert call_count["n"] < 20, f"worker spun: {call_count['n']} claims in 0.35s"

    def test_executor_exception_does_not_crash_loop(
        self, store: DiscoverJobStore
    ):
        """One bad job must not stop the worker from processing the next."""
        store.create_job(
            theme_id="t1", trigger_project_id="p1", new_entry_ids=["a"]
        )
        store.create_job(
            theme_id="t2", trigger_project_id="p2", new_entry_ids=["b"]
        )

        call_log: list[str] = []

        def fake_discover(**kwargs):
            call_log.append(kwargs.get("theme_id", ""))
            if kwargs.get("theme_id") == "t1":
                raise RuntimeError("simulated bailian failure")
            return {
                "candidates_count": 1,
                "discovered": 1,
                "skipped": 0,
                "errors": [],
                "llm_chunks_total": 1,
                "llm_chunks_succeeded": 1,
                "llm_chunks_failed": 0,
            }

        with patch(
            "app.services.auto.discover_job_executor.CrossConceptDiscoverer"
        ) as MockDiscoverer:
            MockDiscoverer.return_value.discover.side_effect = fake_discover
            worker = DiscoverWorker(store=store, idle_sleep_seconds=0.01)
            worker.start()
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if not store.list_jobs(status="pending"):
                    break
                time.sleep(0.02)
            worker.stop(timeout=2.0)

        statuses = {j["theme_id"]: j["status"] for j in store.list_jobs()}
        assert statuses == {"t1": "failed", "t2": "completed"}
        assert "t1" in call_log and "t2" in call_log


class TestStartupRecovery:
    def test_recover_stale_runs_once_at_startup(
        self, store: DiscoverJobStore
    ):
        called = {"n": 0}
        real_recover = store.recover_stale_running

        def counting(**kw):
            called["n"] += 1
            return real_recover(**kw)

        store.recover_stale_running = counting  # type: ignore[assignment]

        worker = DiscoverWorker(
            store=store,
            idle_sleep_seconds=0.05,
            recover_stale_on_start=True,
        )
        worker.start()
        time.sleep(0.15)
        worker.stop(timeout=2.0)

        assert called["n"] == 1, "recover_stale must run exactly once at startup"

    def test_recover_stale_off_by_default(self, store: DiscoverJobStore):
        called = {"n": 0}
        real_recover = store.recover_stale_running

        def counting(**kw):
            called["n"] += 1
            return real_recover(**kw)

        store.recover_stale_running = counting  # type: ignore[assignment]

        worker = DiscoverWorker(store=store, idle_sleep_seconds=0.05)
        worker.start()
        time.sleep(0.15)
        worker.stop(timeout=2.0)

        assert called["n"] == 0
