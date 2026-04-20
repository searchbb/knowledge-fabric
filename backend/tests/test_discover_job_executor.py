"""Tests for ``app.services.auto.discover_job_executor``.

The executor is the thin layer between the job store (pure storage) and
the existing ``CrossConceptDiscoverer`` (pure compute). It's the piece the
CLI drainer and the future background worker both call into.

Responsibilities:
- Claim a pending job via the store.
- Call ``CrossConceptDiscoverer.discover`` with the job's scope.
- Map the discover result to one of: completed / partial / failed.
- Write terminal state back to the store. Exceptions from the discoverer
  are caught and recorded as ``failed``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.auto.discover_job_executor import (
    claim_and_execute_one,
    execute_job,
)
from app.services.auto.discover_job_store import DiscoverJobStore


@pytest.fixture
def store(tmp_path: Path) -> DiscoverJobStore:
    return DiscoverJobStore(tmp_path / "discover-jobs.json")


def _seed_pending_job(store: DiscoverJobStore) -> dict:
    return store.create_job(
        theme_id="gtheme_t1",
        trigger_project_id="proj_1",
        new_entry_ids=["canon_a"],
        origin_run_id="auto_run_x",
    )


# ---------------------------------------------------------------------------
# execute_job
# ---------------------------------------------------------------------------


class TestExecuteJob:
    def test_happy_path_marks_completed_with_stats(
        self, store: DiscoverJobStore
    ):
        job = _seed_pending_job(store)
        # Put the job into running state so the executor can finalize it.
        store.claim_next()

        fake_result = {
            "candidates_count": 4,
            "discovered": 2,
            "skipped": 1,
            "errors": [],
            "llm_chunks_total": 1,
            "llm_chunks_succeeded": 1,
            "llm_chunks_failed": 0,
        }
        with patch(
            "app.services.auto.discover_job_executor.CrossConceptDiscoverer"
        ) as MockDiscoverer:
            MockDiscoverer.return_value.discover.return_value = fake_result
            outcome = execute_job(job["job_id"], store=store)

        assert outcome["status"] == "completed"
        final = store.get_job(job["job_id"])
        assert final["status"] == "completed"
        assert final["stats"]["discovered"] == 2

    def test_execute_job_passes_heartbeat_callback_to_discoverer(
        self, store: DiscoverJobStore
    ):
        job = _seed_pending_job(store)
        claimed = store.claim_next()
        assert claimed is not None
        started_heartbeat = claimed["heartbeat_at"]

        def fake_discover(**kwargs):
            heartbeat_callback = kwargs.get("heartbeat_callback")
            assert callable(heartbeat_callback)
            heartbeat_callback()
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
            outcome = execute_job(job["job_id"], store=store)

        assert outcome["status"] == "completed"
        final = store.get_job(job["job_id"])
        assert final["heartbeat_at"] is not None
        assert final["heartbeat_at"] >= started_heartbeat

    def test_partial_when_some_chunks_failed(self, store: DiscoverJobStore):
        job = _seed_pending_job(store)
        store.claim_next()

        fake_result = {
            "candidates_count": 20,
            "discovered": 3,
            "skipped": 0,
            "errors": ["chunk 1 failed: timeout"],
            "llm_chunks_total": 2,
            "llm_chunks_succeeded": 1,
            "llm_chunks_failed": 1,
        }
        with patch(
            "app.services.auto.discover_job_executor.CrossConceptDiscoverer"
        ) as MockDiscoverer:
            MockDiscoverer.return_value.discover.return_value = fake_result
            outcome = execute_job(job["job_id"], store=store)

        assert outcome["status"] == "partial"
        final = store.get_job(job["job_id"])
        assert final["status"] == "partial"
        assert final["stats"]["llm_chunks_failed"] == 1

    def test_exception_is_captured_as_failed(self, store: DiscoverJobStore):
        job = _seed_pending_job(store)
        store.claim_next()

        with patch(
            "app.services.auto.discover_job_executor.CrossConceptDiscoverer"
        ) as MockDiscoverer:
            MockDiscoverer.return_value.discover.side_effect = RuntimeError(
                "bailian unavailable"
            )
            outcome = execute_job(job["job_id"], store=store)

        assert outcome["status"] == "failed"
        final = store.get_job(job["job_id"])
        assert final["status"] == "failed"
        assert "bailian unavailable" in (final["last_error"] or "")

    def test_missing_job_raises(self, store: DiscoverJobStore):
        from app.services.auto.discover_job_store import DiscoverJobStoreError
        with pytest.raises(DiscoverJobStoreError):
            execute_job("djob_nope", store=store)

    def test_refuses_non_running_job(self, store: DiscoverJobStore):
        """execute_job expects the job to already be in running state (the
        claimer is responsible for the pending→running transition).

        This keeps the claim-and-execute flow composable: the CLI drainer
        and any future worker can share the same claim atomicity.
        """
        job = _seed_pending_job(store)
        # Intentionally do not claim.
        with pytest.raises(RuntimeError, match="not running"):
            execute_job(job["job_id"], store=store)


# ---------------------------------------------------------------------------
# claim_and_execute_one
# ---------------------------------------------------------------------------


class TestClaimAndExecuteOne:
    def test_returns_none_when_queue_empty(self, store: DiscoverJobStore):
        assert claim_and_execute_one(store=store) is None

    def test_claims_runs_and_reports(self, store: DiscoverJobStore):
        job = _seed_pending_job(store)

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
            outcome = claim_and_execute_one(store=store)

        assert outcome is not None
        assert outcome["job_id"] == job["job_id"]
        assert outcome["status"] == "completed"
