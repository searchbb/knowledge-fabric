"""HTTP-level tests for ``app.api.routes.discover_jobs``.

Backend surface for the discover-job queue. Thin wrapper over
``DiscoverJobStore`` + ``claim_and_execute_one``; most invariants live in
``test_discover_job_store.py`` / ``test_discover_job_executor.py``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask

from app.api.routes.discover_jobs import discover_jobs_bp
from app.services.auto import discover_job_store as store_module
from app.services.auto.discover_job_store import DiscoverJobStore


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch):
    scratch = tmp_path / "discover-jobs.json"
    skip_scratch = tmp_path / "discover-skips.json"
    # The routes construct DiscoverJobStore()/DiscoverSkipLog() with no args,
    # so redirect both modules' default paths at our scratch dirs.
    monkeypatch.setattr(store_module, "_DEFAULT_DATA_PATH", scratch)
    from app.services.auto import discover_skip_log as skip_module
    monkeypatch.setattr(skip_module, "_DEFAULT_DATA_PATH", skip_scratch)

    app = Flask(__name__)
    app.register_blueprint(discover_jobs_bp)
    client = app.test_client()
    client.store_path = scratch
    client.skip_log_path = skip_scratch
    return client


def _seed_pending(store_path: Path, **overrides) -> dict:
    store = DiscoverJobStore(store_path)
    return store.create_job(
        theme_id=overrides.get("theme_id", "gtheme_t1"),
        trigger_project_id=overrides.get("trigger_project_id", "proj_1"),
        new_entry_ids=overrides.get("new_entry_ids", ["canon_a"]),
        origin_run_id=overrides.get("origin_run_id", "auto_run_x"),
    )


# ---------------------------------------------------------------------------
# GET /api/auto/discover-jobs/stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_empty_queue_returns_zero_counts(self, api_client):
        resp = api_client.get("/api/auto/discover-jobs/stats")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["total"] == 0
        assert body["data"]["by_status"] == {}

    def test_counts_by_status(self, api_client):
        _seed_pending(api_client.store_path, theme_id="a")
        second = _seed_pending(api_client.store_path, theme_id="b")
        third = _seed_pending(api_client.store_path, theme_id="c")

        store = DiscoverJobStore(api_client.store_path)
        store.claim_next()  # first → running
        store.mark_completed(second["job_id"], stats={"discovered": 1})
        store.mark_failed(third["job_id"], error="boom")

        resp = api_client.get("/api/auto/discover-jobs/stats")
        body = resp.get_json()
        assert body["data"]["total"] == 3
        assert body["data"]["by_status"] == {
            "running": 1,
            "completed": 1,
            "failed": 1,
        }


# ---------------------------------------------------------------------------
# GET /api/auto/discover-jobs
# ---------------------------------------------------------------------------


class TestList:
    def test_list_all_when_no_filter(self, api_client):
        _seed_pending(api_client.store_path, theme_id="a")
        _seed_pending(api_client.store_path, theme_id="b")

        resp = api_client.get("/api/auto/discover-jobs")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["success"] is True
        assert len(body["data"]["jobs"]) == 2

    def test_list_with_status_filter(self, api_client):
        a = _seed_pending(api_client.store_path, theme_id="a")
        _seed_pending(api_client.store_path, theme_id="b")
        store = DiscoverJobStore(api_client.store_path)
        store.mark_completed(a["job_id"], stats={})

        resp = api_client.get("/api/auto/discover-jobs?status=pending")
        body = resp.get_json()
        assert len(body["data"]["jobs"]) == 1
        assert body["data"]["jobs"][0]["theme_id"] == "b"

    def test_limit_caps_response(self, api_client):
        for i in range(5):
            _seed_pending(api_client.store_path, theme_id=f"t{i}")

        resp = api_client.get("/api/auto/discover-jobs?limit=2")
        body = resp.get_json()
        assert len(body["data"]["jobs"]) == 2


# ---------------------------------------------------------------------------
# GET /api/auto/discover-jobs/<job_id>
# ---------------------------------------------------------------------------


class TestDetail:
    def test_detail_returns_full_job(self, api_client):
        job = _seed_pending(api_client.store_path)
        resp = api_client.get(f"/api/auto/discover-jobs/{job['job_id']}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["job_id"] == job["job_id"]
        assert body["data"]["theme_id"] == "gtheme_t1"

    def test_detail_404_when_unknown(self, api_client):
        resp = api_client.get("/api/auto/discover-jobs/djob_nope")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["success"] is False


# ---------------------------------------------------------------------------
# POST /api/auto/discover-jobs/run-once
# ---------------------------------------------------------------------------


class TestRunOnce:
    def test_run_once_empty_queue_reports_none(self, api_client):
        resp = api_client.post("/api/auto/discover-jobs/run-once")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["executed"] is False

    def test_run_once_executes_oldest_pending(self, api_client):
        job = _seed_pending(api_client.store_path)

        fake = {
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
            MockDiscoverer.return_value.discover.return_value = fake
            resp = api_client.post("/api/auto/discover-jobs/run-once")

        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["executed"] is True
        assert body["data"]["outcome"]["job_id"] == job["job_id"]
        assert body["data"]["outcome"]["status"] == "completed"


# ---------------------------------------------------------------------------
# POST /api/auto/discover-jobs/recover-stale
# ---------------------------------------------------------------------------


class TestRecoverStale:
    def test_recover_stale_no_op_reports_empty(self, api_client):
        resp = api_client.post("/api/auto/discover-jobs/recover-stale")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["data"]["requeued"] == []
        assert body["data"]["gave_up"] == []


# ---------------------------------------------------------------------------
# POST /api/auto/discover-jobs/<job_id>/retry
# ---------------------------------------------------------------------------


class TestRetryJob:
    def _make_partial(self, store_path, **kw) -> dict:
        job = _seed_pending(store_path, **kw)
        store = DiscoverJobStore(store_path)
        store.claim_next()
        store.mark_partial(job["job_id"], stats={"discovered": 2})
        return job

    def test_retry_partial_moves_back_to_pending(self, api_client):
        job = self._make_partial(api_client.store_path)
        resp = api_client.post(f"/api/auto/discover-jobs/{job['job_id']}/retry")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["success"] is True
        assert body["data"]["job_id"] == job["job_id"]
        assert body["data"]["status"] == "pending"

    def test_retry_failed_job(self, api_client):
        job = _seed_pending(api_client.store_path)
        store = DiscoverJobStore(api_client.store_path)
        store.claim_next()
        store.mark_failed(job["job_id"], error="bailian down")

        resp = api_client.post(f"/api/auto/discover-jobs/{job['job_id']}/retry")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "pending"

    def test_retry_unknown_returns_404(self, api_client):
        resp = api_client.post("/api/auto/discover-jobs/djob_nope/retry")
        assert resp.status_code == 404
        assert resp.get_json()["success"] is False

    def test_retry_running_returns_409(self, api_client):
        """Retry on a currently-running job conflicts with the worker."""
        _seed_pending(api_client.store_path)
        store = DiscoverJobStore(api_client.store_path)
        claimed = store.claim_next()

        resp = api_client.post(f"/api/auto/discover-jobs/{claimed['job_id']}/retry")
        assert resp.status_code == 409
        assert "running" in (resp.get_json().get("error") or "").lower()

    def test_retry_completed_returns_409(self, api_client):
        job = _seed_pending(api_client.store_path)
        store = DiscoverJobStore(api_client.store_path)
        store.claim_next()
        store.mark_completed(job["job_id"], stats={"discovered": 3})

        resp = api_client.post(f"/api/auto/discover-jobs/{job['job_id']}/retry")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/auto/discover-jobs/<job_id>/cancel
# ---------------------------------------------------------------------------


class TestByTheme:
    """GET /api/auto/discover-jobs/by-theme/<theme_id> — the one-stop
    aggregate the Theme detail page needs: coverage + rolling history +
    all matching jobs + per-status counts, in a single response."""

    def _seed_jobs_for(self, store_path, theme_id="gtheme_t1", n=3):
        import time as _time

        jobs = []
        for i in range(n):
            job = _seed_pending(
                store_path,
                theme_id=theme_id,
                trigger_project_id=f"proj_{i}",
                new_entry_ids=[f"canon_{i}"],
            )
            jobs.append(job)
            # created_at is ISO-seconds precision in the store; sleep >1s so
            # consecutive jobs get strictly increasing timestamps.
            _time.sleep(1.05)
        return jobs

    def test_returns_jobs_filtered_by_theme(self, api_client):
        self._seed_jobs_for(api_client.store_path, theme_id="gtheme_A", n=2)
        self._seed_jobs_for(api_client.store_path, theme_id="gtheme_B", n=1)

        resp = api_client.get("/api/auto/discover-jobs/by-theme/gtheme_A")
        assert resp.status_code == 200
        body = resp.get_json()
        data = body["data"]
        assert [j["theme_id"] for j in data["jobs"]] == ["gtheme_A", "gtheme_A"]
        assert data["stats"]["total"] == 2
        assert data["stats"]["by_status"] == {"pending": 2}

    def test_jobs_are_newest_first(self, api_client):
        jobs = self._seed_jobs_for(
            api_client.store_path, theme_id="gtheme_t1", n=3
        )
        resp = api_client.get("/api/auto/discover-jobs/by-theme/gtheme_t1")
        data = resp.get_json()["data"]
        assert [j["job_id"] for j in data["jobs"]] == [
            jobs[2]["job_id"],
            jobs[1]["job_id"],
            jobs[0]["job_id"],
        ]

    def test_includes_coverage_and_history_when_recorded(
        self, api_client, monkeypatch, tmp_path
    ):
        # Point theme registry at a scratch file and seed one history run.
        from app import config as config_module
        (tmp_path / "uploads" / "projects").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            config_module.Config, "UPLOAD_FOLDER", str(tmp_path / "uploads")
        )
        import json as _json
        themes_file = tmp_path / "uploads" / "projects" / "global_themes.json"
        themes_file.write_text(_json.dumps({
            "version": 2,
            "themes": {
                "gtheme_t1": {
                    "theme_id": "gtheme_t1",
                    "name": "T1",
                    "concept_memberships": [],
                }
            },
        }))
        from app.services.registry.global_theme_registry import record_discovery_run

        record_discovery_run(
            "gtheme_t1",
            stats={"discovered": 4, "candidates_count": 10,
                    "skipped": 1, "errors": [], "funnel": {"final": 10}},
            job_id="djob_xyz",
        )

        resp = api_client.get("/api/auto/discover-jobs/by-theme/gtheme_t1")
        data = resp.get_json()["data"]
        assert data["coverage"]["discovered"] == 4
        assert len(data["history"]) == 1
        assert data["history"][0]["job_id"] == "djob_xyz"

    def test_missing_theme_in_registry_still_returns_jobs(self, api_client):
        """Theme might not be in the global registry (e.g. deleted) but
        its old discover jobs may still linger. The endpoint should still
        return the jobs + empty coverage/history rather than 404."""
        self._seed_jobs_for(api_client.store_path, theme_id="gtheme_orphan", n=1)

        resp = api_client.get(
            "/api/auto/discover-jobs/by-theme/gtheme_orphan"
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["stats"]["total"] == 1
        assert data["coverage"] in (None, {}, {"discovered": 0})
        assert data["history"] == []


class TestRecentSkips:
    """GET /api/auto/discover-jobs/recent-skips — powers the UI badge
    'N throttled in the last hour'."""

    def test_empty_returns_zero(self, api_client):
        resp = api_client.get("/api/auto/discover-jobs/recent-skips")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["stats"]["total"] == 0
        assert body["data"]["skips"] == []

    def test_returns_entries_after_log_append(self, api_client):
        from app.services.auto.discover_skip_log import DiscoverSkipLog

        log = DiscoverSkipLog(api_client.skip_log_path)
        log.append(
            reason="theme cooldown: 11 in the last hour (cap=10)",
            kind="theme_cooldown",
            theme_id="gtheme_hot",
            origin_run_id="run_a",
        )
        log.append(
            reason="daily budget exceeded: 50 created today (cap=50)",
            kind="daily_budget",
        )
        resp = api_client.get("/api/auto/discover-jobs/recent-skips")
        data = resp.get_json()["data"]
        assert data["stats"]["total"] == 2
        assert data["stats"]["by_kind"] == {
            "theme_cooldown": 1,
            "daily_budget": 1,
        }
        # Most-recent first.
        assert data["skips"][0]["kind"] == "daily_budget"
        assert data["skips"][1]["kind"] == "theme_cooldown"


class TestByProject:
    """GET /api/auto/discover-jobs/by-project/<project_id> — analogous to
    by-theme, but filtered by the job's triggering project_id. Used by
    article/project-level pages (P4 step 12)."""

    def test_returns_only_matching_project(self, api_client):
        _seed_pending(api_client.store_path, trigger_project_id="proj_A")
        _seed_pending(api_client.store_path, trigger_project_id="proj_B")
        _seed_pending(api_client.store_path, trigger_project_id="proj_A")

        resp = api_client.get("/api/auto/discover-jobs/by-project/proj_A")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["success"] is True
        assert body["data"]["stats"]["total"] == 2
        assert all(
            j["trigger_project_id"] == "proj_A"
            for j in body["data"]["jobs"]
        )

    def test_unknown_project_returns_empty(self, api_client):
        resp = api_client.get("/api/auto/discover-jobs/by-project/proj_ghost")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["stats"]["total"] == 0


class TestCancelJob:
    def test_cancel_pending_moves_to_cancelled(self, api_client):
        job = _seed_pending(api_client.store_path)
        resp = api_client.post(f"/api/auto/discover-jobs/{job['job_id']}/cancel")
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["success"] is True
        assert body["data"]["status"] == "cancelled"

    def test_cancel_running_returns_409(self, api_client):
        _seed_pending(api_client.store_path)
        store = DiscoverJobStore(api_client.store_path)
        claimed = store.claim_next()

        resp = api_client.post(f"/api/auto/discover-jobs/{claimed['job_id']}/cancel")
        assert resp.status_code == 409

    def test_cancel_unknown_returns_404(self, api_client):
        resp = api_client.post("/api/auto/discover-jobs/djob_nope/cancel")
        assert resp.status_code == 404
