"""Tests for ``app.services.auto.discover_job_store.DiscoverJobStore``.

Part of P1 (Discover V2 execution plan): detach cross-concept discover from
the main pipeline and turn it into a recoverable background job.

The store is modelled on ``PendingUrlStore``: file-locked JSON with a
sidecar ``.lock``, atomic rename on every write. Differences:

- Single flat list of jobs (no multi-bucket layout). ``status`` is a field.
- No URL fingerprint concept — each job has a unique ``job_id``.
- State machine:
      pending → running → completed
                         → partial     (chunks failed, some succeeded)
                         → failed      (max_attempts exhausted)
      running (stale) → pending  (attempt += 1, retry)
                      → failed   (attempt >= max_attempts, give up)
      pending → cancelled
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services.auto.discover_job_store import (
    DiscoverJobStore,
    DiscoverJobStoreError,
)


@pytest.fixture
def store(tmp_path: Path) -> DiscoverJobStore:
    return DiscoverJobStore(tmp_path / "discover-jobs.json")


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_creates_empty_file_if_missing(self, tmp_path: Path):
        path = tmp_path / "fresh.json"
        assert not path.exists()
        DiscoverJobStore(path)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"jobs": []}

    def test_load_returns_jobs_list(self, store: DiscoverJobStore):
        data = store.load()
        assert data == {"jobs": []}


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


class TestCreateJob:
    def test_creates_pending_job_with_metadata(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="gtheme_xyz",
            trigger_project_id="proj_42",
            new_entry_ids=["canon_a", "canon_b"],
            origin_run_id="auto_run_abc",
        )
        assert job["job_id"].startswith("djob_")
        assert job["status"] == "pending"
        assert job["theme_id"] == "gtheme_xyz"
        assert job["trigger_project_id"] == "proj_42"
        assert job["new_entry_ids"] == ["canon_a", "canon_b"]
        assert job["origin_run_id"] == "auto_run_abc"
        assert job["attempt_count"] == 0
        assert job["max_attempts"] == 3
        assert "created_at" in job
        assert "updated_at" in job
        assert job["started_at"] is None
        assert job["finished_at"] is None
        assert job["heartbeat_at"] is None
        assert job["last_error"] is None
        assert job["stats"] == {}

        data = store.load()
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == job["job_id"]

    def test_create_without_new_entry_ids_is_allowed(self, store: DiscoverJobStore):
        """Empty list is a legitimate scope (e.g., manual rerun with entry_ids only).

        The store doesn't enforce semantic gates — the caller (pipeline_runner)
        decides whether to schedule a job at all.
        """
        job = store.create_job(
            theme_id="gtheme_xyz",
            trigger_project_id="proj_42",
            new_entry_ids=[],
        )
        assert job["new_entry_ids"] == []

    def test_create_with_scope_snapshot(self, store: DiscoverJobStore):
        snapshot = {
            "incremental": True,
            "max_pairs": 50,
            "min_confidence": 0.6,
        }
        job = store.create_job(
            theme_id="gtheme_xyz",
            trigger_project_id="proj_42",
            new_entry_ids=["canon_a"],
            scope_snapshot=snapshot,
        )
        assert job["scope_snapshot"] == snapshot

    def test_job_ids_are_unique(self, store: DiscoverJobStore):
        job1 = store.create_job(
            theme_id="t1", trigger_project_id="p1", new_entry_ids=["a"]
        )
        job2 = store.create_job(
            theme_id="t1", trigger_project_id="p1", new_entry_ids=["b"]
        )
        assert job1["job_id"] != job2["job_id"]


# ---------------------------------------------------------------------------
# get_job / list_jobs
# ---------------------------------------------------------------------------


class TestGetAndList:
    def test_get_job_returns_none_for_unknown(self, store: DiscoverJobStore):
        assert store.get_job("djob_missing") is None

    def test_get_job_returns_copy(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        fetched = store.get_job(job["job_id"])
        assert fetched is not None
        # Mutating the returned dict must not affect the stored state.
        fetched["status"] = "HACKED"
        assert store.get_job(job["job_id"])["status"] == "pending"

    def test_list_jobs_returns_all_by_default(self, store: DiscoverJobStore):
        for i in range(3):
            store.create_job(
                theme_id=f"t{i}", trigger_project_id=f"p{i}", new_entry_ids=["a"]
            )
        jobs = store.list_jobs()
        assert len(jobs) == 3

    def test_list_jobs_filters_by_status(self, store: DiscoverJobStore):
        a = store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["x"])
        b = store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["y"])
        store.claim_next()  # a → running

        pending = store.list_jobs(status="pending")
        running = store.list_jobs(status="running")
        assert [j["job_id"] for j in pending] == [b["job_id"]]
        assert [j["job_id"] for j in running] == [a["job_id"]]


# ---------------------------------------------------------------------------
# claim_next (pending → running)
# ---------------------------------------------------------------------------


class TestClaimNext:
    def test_claim_returns_none_when_empty(self, store: DiscoverJobStore):
        assert store.claim_next() is None

    def test_claim_picks_oldest_pending_first(self, store: DiscoverJobStore):
        first = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        time.sleep(0.01)
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["b"])
        claimed = store.claim_next()
        assert claimed is not None
        assert claimed["job_id"] == first["job_id"]
        assert claimed["status"] == "running"
        assert claimed["attempt_count"] == 1
        assert claimed["started_at"] is not None
        assert claimed["heartbeat_at"] is not None

    def test_claim_skips_non_pending(self, store: DiscoverJobStore):
        a = store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["x"])
        # Manually flip a to completed.
        store.mark_completed(a["job_id"], stats={"discovered": 1})
        b = store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["y"])

        claimed = store.claim_next()
        assert claimed is not None
        assert claimed["job_id"] == b["job_id"]

    def test_claim_returns_copy(self, store: DiscoverJobStore):
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["a"])
        claimed = store.claim_next()
        claimed["status"] = "HACKED"
        fresh = store.get_job(claimed["job_id"])
        assert fresh["status"] == "running"


# ---------------------------------------------------------------------------
# heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_updates_timestamp(self, store: DiscoverJobStore):
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["a"])
        claimed = store.claim_next()
        first_hb = claimed["heartbeat_at"]
        time.sleep(0.05)
        store.heartbeat(claimed["job_id"])
        after = store.get_job(claimed["job_id"])
        assert after["heartbeat_at"] >= first_hb
        assert after["status"] == "running"

    def test_heartbeat_silently_ignores_unknown(self, store: DiscoverJobStore):
        # Matching PendingUrlStore.heartbeat behaviour: silent miss is fine,
        # the runner may already have moved on.
        store.heartbeat("djob_missing")  # must not raise


# ---------------------------------------------------------------------------
# mark_completed / mark_partial / mark_failed / mark_cancelled
# ---------------------------------------------------------------------------


class TestTerminalTransitions:
    def _claimed_job(self, store: DiscoverJobStore) -> dict:
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["a"])
        return store.claim_next()

    def test_mark_completed_records_stats_and_finish(self, store: DiscoverJobStore):
        job = self._claimed_job(store)
        stats = {
            "candidates_count": 12,
            "discovered": 5,
            "skipped": 2,
            "errors": [],
            "llm_chunks_total": 2,
            "llm_chunks_succeeded": 2,
        }
        store.mark_completed(job["job_id"], stats=stats)
        result = store.get_job(job["job_id"])
        assert result["status"] == "completed"
        assert result["stats"] == stats
        assert result["finished_at"] is not None
        assert result["last_error"] is None

    def test_mark_partial_records_error_and_stats(self, store: DiscoverJobStore):
        job = self._claimed_job(store)
        stats = {
            "candidates_count": 10,
            "discovered": 3,
            "llm_chunks_failed": 1,
            "errors": ["chunk 0 failed: timeout"],
        }
        store.mark_partial(job["job_id"], stats=stats)
        result = store.get_job(job["job_id"])
        assert result["status"] == "partial"
        assert result["stats"] == stats
        assert result["finished_at"] is not None

    def test_mark_failed_stores_error_string(self, store: DiscoverJobStore):
        job = self._claimed_job(store)
        store.mark_failed(job["job_id"], error="theme not found")
        result = store.get_job(job["job_id"])
        assert result["status"] == "failed"
        assert result["last_error"] == "theme not found"
        assert result["finished_at"] is not None

    def test_mark_cancelled_from_pending(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.mark_cancelled(job["job_id"])
        assert store.get_job(job["job_id"])["status"] == "cancelled"

    def test_mark_on_unknown_raises(self, store: DiscoverJobStore):
        with pytest.raises(DiscoverJobStoreError):
            store.mark_completed("djob_nope", stats={})
        with pytest.raises(DiscoverJobStoreError):
            store.mark_failed("djob_nope", error="x")


# ---------------------------------------------------------------------------
# retry_job  (partial/failed/cancelled → pending)
# ---------------------------------------------------------------------------


class TestRetryJob:
    def test_retry_from_partial_moves_to_pending(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.claim_next()
        store.mark_partial(
            job["job_id"],
            stats={"discovered": 3, "llm_chunks_failed": 1, "errors": ["x"]},
        )
        pre = store.get_job(job["job_id"])
        assert pre["status"] == "partial"

        store.retry_job(job["job_id"])

        after = store.get_job(job["job_id"])
        assert after["status"] == "pending"
        # Run-specific state is reset so the next claim_next() starts fresh.
        assert after["started_at"] is None
        assert after["heartbeat_at"] is None
        assert after["finished_at"] is None
        assert after["last_error"] is None
        # attempt_count is preserved so the audit trail survives.
        assert after["attempt_count"] == pre["attempt_count"]
        # created_at is preserved — this isn't a new job.
        assert after["created_at"] == pre["created_at"]

    def test_retry_from_failed(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.claim_next()
        store.mark_failed(job["job_id"], error="bailian down")

        store.retry_job(job["job_id"])

        after = store.get_job(job["job_id"])
        assert after["status"] == "pending"
        assert after["last_error"] is None

    def test_retry_from_cancelled(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.mark_cancelled(job["job_id"])
        store.retry_job(job["job_id"])
        assert store.get_job(job["job_id"])["status"] == "pending"

    def test_retry_rejects_running(self, store: DiscoverJobStore):
        """Retrying a still-running job would race with the worker."""
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["a"])
        claimed = store.claim_next()
        with pytest.raises(DiscoverJobStoreError, match="running"):
            store.retry_job(claimed["job_id"])

    def test_retry_rejects_pending(self, store: DiscoverJobStore):
        """No-op retry is a user mistake; fail loudly so the UI can show it."""
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        with pytest.raises(DiscoverJobStoreError, match="pending"):
            store.retry_job(job["job_id"])

    def test_retry_rejects_completed(self, store: DiscoverJobStore):
        """Completed jobs are immutable — discovered relations already committed."""
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.claim_next()
        store.mark_completed(job["job_id"], stats={"discovered": 1})
        with pytest.raises(DiscoverJobStoreError, match="completed"):
            store.retry_job(job["job_id"])

    def test_retry_on_unknown_raises(self, store: DiscoverJobStore):
        with pytest.raises(DiscoverJobStoreError):
            store.retry_job("djob_nope")

    def test_retry_then_claim_resumes_work(self, store: DiscoverJobStore):
        """After retry, the job is eligible for claim_next() again."""
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.claim_next()
        store.mark_failed(job["job_id"], error="boom")
        store.retry_job(job["job_id"])

        claimed = store.claim_next()
        assert claimed["job_id"] == job["job_id"]
        # attempt_count is bumped by claim (it was 1 before, so now 2).
        assert claimed["attempt_count"] == 2


# ---------------------------------------------------------------------------
# cancel_pending_job  (pending → cancelled via policy-aware API)
# ---------------------------------------------------------------------------


class TestCancelPendingJob:
    def test_cancel_from_pending(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.cancel_pending_job(job["job_id"])
        assert store.get_job(job["job_id"])["status"] == "cancelled"

    def test_cancel_rejects_running(self, store: DiscoverJobStore):
        """The worker owns the job until it releases it — UI cancel on a
        running job would race. Use recover_stale_running for crashed
        workers instead.
        """
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["a"])
        claimed = store.claim_next()
        with pytest.raises(DiscoverJobStoreError, match="running"):
            store.cancel_pending_job(claimed["job_id"])

    def test_cancel_rejects_terminal(self, store: DiscoverJobStore):
        job = store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        store.claim_next()
        store.mark_completed(job["job_id"], stats={"discovered": 0})
        with pytest.raises(DiscoverJobStoreError, match="completed"):
            store.cancel_pending_job(job["job_id"])

    def test_cancel_on_unknown_raises(self, store: DiscoverJobStore):
        with pytest.raises(DiscoverJobStoreError):
            store.cancel_pending_job("djob_nope")


# ---------------------------------------------------------------------------
# count_recent_for_theme  (per-theme rate limiting)
# ---------------------------------------------------------------------------


class TestCountStartedToday:
    """Used by the global daily-budget soft-gate (P4 step 11).

    Counts jobs created today (local-time midnight boundary). Cancelled
    jobs don't count — same policy as per-theme cooldown.
    """

    def test_empty_returns_zero(self, store: DiscoverJobStore):
        assert store.count_started_today() == 0

    def test_counts_all_themes_jobs_today(self, store: DiscoverJobStore):
        store.create_job(theme_id="a", trigger_project_id="p", new_entry_ids=["x"])
        store.create_job(theme_id="b", trigger_project_id="p", new_entry_ids=["y"])
        store.create_job(theme_id="a", trigger_project_id="p", new_entry_ids=["z"])
        assert store.count_started_today() == 3

    def test_excludes_jobs_from_yesterday(self, store: DiscoverJobStore):
        j = store.create_job(
            theme_id="a", trigger_project_id="p", new_entry_ids=["x"]
        )
        data = store.load()
        yesterday = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        for row in data["jobs"]:
            if row["job_id"] == j["job_id"]:
                row["created_at"] = yesterday
        store.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Add one fresh job so count is 1, not 0.
        store.create_job(
            theme_id="a", trigger_project_id="p", new_entry_ids=["today"]
        )
        assert store.count_started_today() == 1

    def test_excludes_cancelled(self, store: DiscoverJobStore):
        j = store.create_job(theme_id="a", trigger_project_id="p", new_entry_ids=["x"])
        store.mark_cancelled(j["job_id"])
        store.create_job(theme_id="a", trigger_project_id="p", new_entry_ids=["y"])
        assert store.count_started_today() == 1


class TestCountRecentForTheme:
    """Used by the pipeline_runner to enforce per-theme per-hour cooldown
    (P4 step 10). The store is the natural home: it already has every
    job's created_at and knows the theme_id scope."""

    def test_empty_store_returns_zero(self, store: DiscoverJobStore):
        assert store.count_recent_for_theme("gtheme_t1", window_seconds=3600) == 0

    def test_counts_jobs_within_window(self, store: DiscoverJobStore):
        for _ in range(3):
            store.create_job(
                theme_id="gtheme_t1",
                trigger_project_id="p",
                new_entry_ids=["x"],
            )
        # Generous window — all 3 count.
        assert store.count_recent_for_theme("gtheme_t1", window_seconds=3600) == 3

    def test_only_counts_matching_theme(self, store: DiscoverJobStore):
        store.create_job(theme_id="gtheme_A", trigger_project_id="p", new_entry_ids=["x"])
        store.create_job(theme_id="gtheme_B", trigger_project_id="p", new_entry_ids=["y"])
        store.create_job(theme_id="gtheme_A", trigger_project_id="p", new_entry_ids=["z"])
        assert store.count_recent_for_theme("gtheme_A", window_seconds=3600) == 2
        assert store.count_recent_for_theme("gtheme_B", window_seconds=3600) == 1
        assert store.count_recent_for_theme("gtheme_ghost", window_seconds=3600) == 0

    def test_excludes_jobs_outside_window(self, store: DiscoverJobStore):
        """Backdate one job so it falls outside a 60s window."""
        job = store.create_job(
            theme_id="gtheme_t1", trigger_project_id="p", new_entry_ids=["x"]
        )
        data = store.load()
        old_iso = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
        for j in data["jobs"]:
            if j["job_id"] == job["job_id"]:
                j["created_at"] = old_iso
        store.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Add a fresh one — should be the only one in the 60s window.
        store.create_job(
            theme_id="gtheme_t1", trigger_project_id="p", new_entry_ids=["y"]
        )
        assert store.count_recent_for_theme("gtheme_t1", window_seconds=60) == 1

    def test_ignores_cancelled_jobs(self, store: DiscoverJobStore):
        """Cancelled jobs never actually executed, so they don't count
        against the rate limit — otherwise a human cancelling a bad job
        would still eat the quota."""
        j1 = store.create_job(
            theme_id="gtheme_t1", trigger_project_id="p", new_entry_ids=["x"]
        )
        store.mark_cancelled(j1["job_id"])
        store.create_job(
            theme_id="gtheme_t1", trigger_project_id="p", new_entry_ids=["y"]
        )
        assert store.count_recent_for_theme("gtheme_t1", window_seconds=3600) == 1


# ---------------------------------------------------------------------------
# recover_stale_running
# ---------------------------------------------------------------------------


class TestRecoverStale:
    def _make_stale_running(
        self, store: DiscoverJobStore, *, attempt: int, age_hours: int = 2
    ) -> dict:
        """Create one running job whose heartbeat is ancient."""
        store.create_job(
            theme_id="t", trigger_project_id="p", new_entry_ids=["a"]
        )
        claimed = store.claim_next()
        data = store.load()
        for j in data["jobs"]:
            if j["job_id"] == claimed["job_id"]:
                j["attempt_count"] = attempt
                j["heartbeat_at"] = (
                    datetime.now() - timedelta(hours=age_hours)
                ).isoformat(timespec="seconds")
        store.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return claimed

    def test_no_stale_no_changes(self, store: DiscoverJobStore):
        store.create_job(theme_id="t", trigger_project_id="p", new_entry_ids=["a"])
        store.claim_next()
        result = store.recover_stale_running(stale_after_seconds=1800)
        assert result == {"requeued": [], "gave_up": []}

    def test_stale_under_max_goes_back_to_pending(self, store: DiscoverJobStore):
        claimed = self._make_stale_running(store, attempt=1)
        result = store.recover_stale_running(
            stale_after_seconds=1800, max_attempts=3
        )
        assert claimed["job_id"] in result["requeued"]

        job = store.get_job(claimed["job_id"])
        assert job["status"] == "pending"
        # Run-specific fields are cleared so the next claim_next() starts fresh.
        assert job["started_at"] is None
        assert job["heartbeat_at"] is None

    def test_stale_at_max_gives_up(self, store: DiscoverJobStore):
        claimed = self._make_stale_running(store, attempt=3)
        result = store.recover_stale_running(
            stale_after_seconds=1800, max_attempts=3
        )
        assert claimed["job_id"] in result["gave_up"]

        job = store.get_job(claimed["job_id"])
        assert job["status"] == "failed"
        assert "stale" in (job["last_error"] or "").lower()
