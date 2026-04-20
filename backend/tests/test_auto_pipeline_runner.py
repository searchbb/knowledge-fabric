from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.auto import pipeline_runner as pipeline_runner_module
from app.services.auto.pipeline_runner import (
    AutoPipelineRunner,
    AutoPipelineTimeoutError,
    DrainResult,
    RunOutcome,
)


class _FakeStore:
    def heartbeat(self, run_id: str, *, phase: str | None = None) -> None:
        return None


def test_watchdog_resets_stall_tracking_after_build_finishes(monkeypatch):
    runner = AutoPipelineRunner(store=_FakeStore())

    snapshots = iter([
        {
            "task_id": "task_1",
            "progress": 100,
            "message": "图谱构建完成",
            "status": "processing",
        },
        None,
        None,
        None,
    ])

    monkeypatch.setattr(
        runner,
        "_latest_build_task_snapshot",
        lambda: next(snapshots, None),
    )
    monkeypatch.setattr(
        runner,
        "_get_task_snapshot",
        lambda task_id: {"task_id": task_id, "status": "completed"},
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS",
        0.02,
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_STALL_TIMEOUT_SECONDS",
        0.05,
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS",
        1,
    )

    def invoke():
        time.sleep(0.12)
        return {"project_id": "proj_test", "graph_id": "graph_test"}

    result = runner._invoke_article_pipeline_with_watchdog(
        run_id="auto_run_test",
        invoke=invoke,
    )

    assert result["project_id"] == "proj_test"
    assert result["graph_id"] == "graph_test"


def test_watchdog_captures_project_id_from_snapshot_metadata_on_timeout(monkeypatch):
    runner = AutoPipelineRunner(store=_FakeStore())

    monkeypatch.setattr(
        runner,
        "_latest_build_task_snapshot",
        lambda: {
            "task_id": "task_1",
            "progress": 20,
            "message": "处理批次 1/4",
            "status": "processing",
            "metadata": {"project_id": "proj_from_snapshot"},
        },
    )
    monkeypatch.setattr(
        runner,
        "_get_task_snapshot",
        lambda task_id: {"task_id": task_id, "status": "processing"},
    )
    monkeypatch.setattr(
        pipeline_runner_module, "AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS", 0.02
    )
    monkeypatch.setattr(
        pipeline_runner_module, "AUTO_PIPELINE_STALL_TIMEOUT_SECONDS", 10
    )
    monkeypatch.setattr(
        pipeline_runner_module, "AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS", 0.1
    )

    with pytest.raises(AutoPipelineTimeoutError) as excinfo:
        runner._invoke_article_pipeline_with_watchdog(
            run_id="auto_run_test",
            invoke=lambda: time.sleep(0.5),
        )

    assert excinfo.value.project_id == "proj_from_snapshot"
    assert excinfo.value.task_id == "task_1"


def test_run_claimed_timeout_populates_project_id_from_error(monkeypatch):
    """Regression: when the watchdog raises with project_id set, the outcome
    recorded in ``mark_errored`` must carry that project_id so the UI shows
    the half-built project instead of null.
    """
    mark_errored_calls: list[dict] = []

    class _CapturingStore:
        def heartbeat(self, run_id, *, phase=None):
            return None

        def mark_errored(
            self, run_id, *, error, phase, project_id=None, graph_id=None
        ):
            mark_errored_calls.append(
                {
                    "run_id": run_id,
                    "error": error,
                    "phase": phase,
                    "project_id": project_id,
                    "graph_id": graph_id,
                }
            )

    runner = AutoPipelineRunner(store=_CapturingStore())

    def _raise_timeout(**kwargs):
        raise AutoPipelineTimeoutError(
            "total timeout after 1s (limit 1s)",
            phase="build_extract",
            task_id="task_x",
            project_id="proj_from_timeout",
        )

    monkeypatch.setattr(runner, "_invoke_article_pipeline_with_watchdog", _raise_timeout)
    monkeypatch.setattr(runner, "_emit_timeout_audit", lambda **_: None)

    claimed = {
        "run_id": "auto_run_test_timeout",
        "url": "https://example.com/very-long-article",
    }
    outcome = runner._run_claimed(claimed)

    assert outcome.status == "errored"
    assert outcome.project_id == "proj_from_timeout"
    assert len(mark_errored_calls) == 1
    assert mark_errored_calls[0]["project_id"] == "proj_from_timeout"
    assert mark_errored_calls[0]["phase"] == "errored_timeout:build_extract"


def test_watchdog_still_times_out_when_active_build_stalls(monkeypatch):
    runner = AutoPipelineRunner(store=_FakeStore())

    monkeypatch.setattr(
        runner,
        "_latest_build_task_snapshot",
        lambda: {
            "task_id": "task_1",
            "progress": 18,
            "message": "正在处理批次 1/4",
            "status": "processing",
        },
    )
    monkeypatch.setattr(
        runner,
        "_get_task_snapshot",
        lambda task_id: {"task_id": task_id, "status": "processing"},
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS",
        0.02,
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_STALL_TIMEOUT_SECONDS",
        0.05,
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS",
        1,
    )

    with pytest.raises(AutoPipelineTimeoutError, match="no progress for"):
        runner._invoke_article_pipeline_with_watchdog(
            run_id="auto_run_test",
            invoke=lambda: time.sleep(0.5),
        )


def test_watchdog_recovers_completed_project_after_post_build_grace(monkeypatch):
    runner = AutoPipelineRunner(store=_FakeStore())

    snapshots = iter(
        [
            {
                "task_id": "task_1",
                "progress": 100,
                "message": "图谱构建完成",
                "status": "processing",
                "metadata": {"project_id": "proj_done"},
            },
            None,
            None,
            None,
        ]
    )

    monkeypatch.setattr(
        runner,
        "_latest_build_task_snapshot",
        lambda: next(snapshots, None),
    )
    monkeypatch.setattr(
        runner,
        "_get_task_snapshot",
        lambda task_id: {"task_id": task_id, "status": "completed"},
    )
    monkeypatch.setattr(
        runner,
        "_recover_completed_project_result",
        lambda project_id: {
            "project_id": project_id,
            "graph_id": "graph_done",
            "project_name": "Recovered Project",
            "title": "Recovered Project",
            "md_path": "",
            "content_hash": "sha256:test",
        },
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_WATCHDOG_INTERVAL_SECONDS",
        0.02,
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_POST_BUILD_GRACE_SECONDS",
        0.05,
    )
    monkeypatch.setattr(
        pipeline_runner_module,
        "AUTO_PIPELINE_TOTAL_TIMEOUT_SECONDS",
        1,
    )

    result = runner._invoke_article_pipeline_with_watchdog(
        run_id="auto_run_test",
        invoke=lambda: time.sleep(0.5),
    )

    assert result["project_id"] == "proj_done"
    assert result["graph_id"] == "graph_done"


def test_recover_completed_project_result_reads_uploaded_markdown_hash(
    monkeypatch, tmp_path
):
    runner = AutoPipelineRunner(store=_FakeStore())
    uploaded_md = tmp_path / "uploaded.md"
    uploaded_md.write_text("# 标题\n\n正文", encoding="utf-8")

    monkeypatch.setattr(
        runner,
        "_http_get",
        lambda url: {
            "success": True,
            "data": {
                "status": "graph_completed",
                "graph_id": "graph_done",
                "name": "Recovered Project",
                "files": [{"source_md_path": str(uploaded_md)}],
            },
        },
    )

    result = runner._recover_completed_project_result("proj_done")

    assert result is not None
    assert result["project_id"] == "proj_done"
    assert result["graph_id"] == "graph_done"
    assert result["project_name"] == "Recovered Project"
    assert result["title"] == "Recovered Project"
    assert result["md_path"] == str(uploaded_md)
    assert result["content_hash"].startswith("sha256:")


def test_build_article_pipeline_uses_vite_frontend_port_when_env_unset(monkeypatch):
    runner = AutoPipelineRunner()

    monkeypatch.delenv("KNOWLEDGE_WORKSPACE_FRONTEND", raising=False)

    pipeline = runner._build_article_pipeline()

    assert pipeline.frontend_base_url == "http://localhost:3000"


def test_http_get_bypasses_env_proxy_for_loopback(monkeypatch):
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"success": true}'

    class _FakeOpener:
        def open(self, req, timeout):
            assert req.full_url == "http://127.0.0.1:5001/api/graph/tasks"
            assert timeout == 30
            return _FakeResponse()

    monkeypatch.setattr(
        pipeline_runner_module.urllib.request,
        "build_opener",
        lambda handler: _FakeOpener(),
    )
    monkeypatch.setattr(
        pipeline_runner_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("loopback requests should not use env proxies")
        ),
    )

    payload = AutoPipelineRunner._http_get("http://127.0.0.1:5001/api/graph/tasks")

    assert payload["success"] is True


def test_http_send_uses_default_urlopen_for_remote_backend(monkeypatch):
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"success": true}'

    monkeypatch.setattr(
        pipeline_runner_module.urllib.request,
        "build_opener",
        lambda handler: (_ for _ in ()).throw(
            AssertionError("remote requests should not force proxy bypass")
        ),
    )

    def _fake_urlopen(req, timeout):
        assert req.full_url == "https://backend.example.com/api/test"
        assert timeout == 60
        assert req.data == b'{"hello": "world"}'
        return _FakeResponse()

    monkeypatch.setattr(
        pipeline_runner_module.urllib.request,
        "urlopen",
        _fake_urlopen,
    )

    payload = AutoPipelineRunner._http_send(
        "https://backend.example.com/api/test",
        {"hello": "world"},
        method="POST",
    )

    assert payload["success"] is True


# ---------------------------------------------------------------------------
# Post-drain governance flag tests
# ---------------------------------------------------------------------------


class _DrainFakeStore:
    """Minimal store stub for run_until_drained() tests."""

    def __init__(self, urls=None):
        self._urls = list(urls or [])
        self._idx = 0

    def recover_stale_inflight(self) -> dict:
        return {}

    def heartbeat(self, run_id: str, *, phase: str | None = None) -> None:
        pass

    def claim_next(self):
        if self._idx < len(self._urls):
            url = self._urls[self._idx]
            self._idx += 1
            return {"url": url, "run_id": f"run_{self._idx}"}
        return None


def _fake_outcome(claimed) -> RunOutcome:
    return RunOutcome(
        run_id=claimed["run_id"],
        url=claimed["url"],
        status="processed",
    )


def test_drain_marks_governance_when_articles_processed(monkeypatch):
    """After processing ≥1 URL, drain must mark a pending governance request."""
    store = _DrainFakeStore(urls=["http://example.com/a"])
    runner = AutoPipelineRunner(store=store)
    monkeypatch.setattr(runner, "_run_claimed", _fake_outcome)

    calls = []
    monkeypatch.setattr(
        "app.services.auto.governance_request_store.mark_pending",
        lambda **kwargs: calls.append(kwargs) or {"requested": True, "status": "pending"},
    )

    result = runner.run_until_drained()

    assert len(result.runs) == 1
    assert result.runs[0].status == "processed"
    assert len(calls) == 1, "mark_pending should be called exactly once"
    assert calls[0].get("reason") == "post_drain"


def test_drain_skips_governance_when_queue_empty(monkeypatch):
    """If the queue is already empty (executed == 0), governance must NOT be marked."""
    store = _DrainFakeStore(urls=[])
    runner = AutoPipelineRunner(store=store)

    calls = []
    monkeypatch.setattr(
        "app.services.auto.governance_request_store.mark_pending",
        lambda **kwargs: calls.append(kwargs) or {"requested": True, "status": "pending"},
    )

    result = runner.run_until_drained()

    assert len(result.runs) == 0
    assert calls == [], "mark_pending must NOT be called when no URLs were processed"


# ---------------------------------------------------------------------------
# Discover V2 — _schedule_discover_job (P1 detachment)
# ---------------------------------------------------------------------------


def test_schedule_discover_job_creates_pending_record(tmp_path):
    """Happy path: theme + new entries → a pending job lands in the store."""
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)

    stats = runner._schedule_discover_job(
        theme_id="gtheme_abc",
        trigger_project_id="proj_1",
        new_entry_ids=["canon_a", "canon_b"],
        run_id="auto_run_xyz",
    )

    assert stats["scheduled"] is True
    assert stats["status"] == "pending"
    assert stats["theme_id"] == "gtheme_abc"
    assert stats["new_entry_count"] == 2
    assert stats["job_id"].startswith("djob_")

    pending = jobs_store.list_jobs(status="pending")
    assert len(pending) == 1
    assert pending[0]["origin_run_id"] == "auto_run_xyz"
    assert pending[0]["trigger_project_id"] == "proj_1"
    assert pending[0]["new_entry_ids"] == ["canon_a", "canon_b"]


def test_schedule_discover_job_skips_without_theme(tmp_path):
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)

    stats = runner._schedule_discover_job(
        theme_id=None,
        trigger_project_id="proj_1",
        new_entry_ids=["canon_a"],
        run_id="run",
    )

    assert stats["scheduled"] is False
    assert "no theme" in stats["skipped_reason"].lower()
    assert jobs_store.list_jobs() == []


def test_schedule_discover_job_skips_when_no_new_entries(tmp_path):
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)

    stats = runner._schedule_discover_job(
        theme_id="gtheme_abc",
        trigger_project_id="proj_1",
        new_entry_ids=[],
        run_id="run",
    )

    assert stats["scheduled"] is False
    assert "no new canonical" in stats["skipped_reason"].lower()
    assert jobs_store.list_jobs() == []


def test_schedule_discover_job_respects_theme_cooldown(monkeypatch, tmp_path):
    """P4 step 10: if a theme has hit the per-hour creation cap, new
    jobs are skipped with a readable reason instead of created."""
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    # Pretend five jobs were already created for this theme this hour.
    for _ in range(5):
        jobs_store.create_job(
            theme_id="gtheme_hot",
            trigger_project_id="proj_old",
            new_entry_ids=["x"],
        )
    # Cap the window at 5 via env.
    monkeypatch.setenv("DISCOVER_THEME_HOURLY_CAP", "5")

    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)

    stats = runner._schedule_discover_job(
        theme_id="gtheme_hot",
        trigger_project_id="proj_new",
        new_entry_ids=["canon_fresh"],
        run_id="run_z",
    )
    assert stats["scheduled"] is False
    assert "cooldown" in stats["skipped_reason"].lower()
    # Still only 5 jobs — the new one was blocked.
    assert len(jobs_store.list_jobs()) == 5


def test_schedule_discover_job_below_cooldown_cap_still_creates(monkeypatch, tmp_path):
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    monkeypatch.setenv("DISCOVER_THEME_HOURLY_CAP", "10")

    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)
    stats = runner._schedule_discover_job(
        theme_id="gtheme_ok",
        trigger_project_id="proj_1",
        new_entry_ids=["canon_a"],
        run_id="run_1",
    )
    assert stats["scheduled"] is True
    assert stats["job_id"].startswith("djob_")


def test_schedule_discover_job_logs_skip_to_skip_log(monkeypatch, tmp_path):
    """P4 audit fix (2026-04-17): when cooldown/budget blocks a schedule,
    the event is recorded in the DiscoverSkipLog so the UI can surface
    'N jobs blocked in the last hour' without grepping URL summaries."""
    from app.services.auto.discover_job_store import DiscoverJobStore
    from app.services.auto.discover_skip_log import DiscoverSkipLog

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    skip_log = DiscoverSkipLog(tmp_path / "discover-skips.json")
    for _ in range(5):
        jobs_store.create_job(
            theme_id="gtheme_hot", trigger_project_id="p_old", new_entry_ids=["x"]
        )
    monkeypatch.setenv("DISCOVER_THEME_HOURLY_CAP", "5")
    monkeypatch.setenv("DISCOVER_DAILY_JOB_BUDGET", "0")

    runner = AutoPipelineRunner(
        store=_FakeStore(),
        discover_job_store=jobs_store,
        discover_skip_log=skip_log,
    )
    stats = runner._schedule_discover_job(
        theme_id="gtheme_hot",
        trigger_project_id="p_new",
        new_entry_ids=["canon_fresh"],
        run_id="run_z",
    )
    assert stats["scheduled"] is False
    entries = skip_log.list_recent()
    assert len(entries) == 1
    assert entries[0]["kind"] == "theme_cooldown"
    assert entries[0]["theme_id"] == "gtheme_hot"
    assert entries[0]["origin_run_id"] == "run_z"
    assert "cooldown" in entries[0]["reason"].lower()


def test_schedule_discover_job_respects_daily_budget(monkeypatch, tmp_path):
    """P4 step 11: once the daily budget is hit, new jobs skip with a
    budget-specific reason. Theme cooldown is disabled so this test
    isolates the budget path."""
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    # Seed 3 jobs today across different themes so the per-theme cap
    # doesn't trigger first.
    for i in range(3):
        jobs_store.create_job(
            theme_id=f"gtheme_{i}",
            trigger_project_id=f"p{i}",
            new_entry_ids=["x"],
        )
    monkeypatch.setenv("DISCOVER_DAILY_JOB_BUDGET", "3")
    monkeypatch.setenv("DISCOVER_THEME_HOURLY_CAP", "0")  # disable the other gate

    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)
    stats = runner._schedule_discover_job(
        theme_id="gtheme_fresh",
        trigger_project_id="p_fresh",
        new_entry_ids=["canon_fresh"],
        run_id="run_over",
    )
    assert stats["scheduled"] is False
    assert "daily" in stats["skipped_reason"].lower()
    assert len(jobs_store.list_jobs()) == 3


def test_schedule_discover_job_under_daily_budget_still_creates(
    monkeypatch, tmp_path
):
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")
    monkeypatch.setenv("DISCOVER_DAILY_JOB_BUDGET", "100")
    monkeypatch.setenv("DISCOVER_THEME_HOURLY_CAP", "0")

    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)
    stats = runner._schedule_discover_job(
        theme_id="gtheme_new",
        trigger_project_id="p",
        new_entry_ids=["canon_a"],
        run_id="run",
    )
    assert stats["scheduled"] is True


def test_schedule_discover_job_soft_fails_if_store_raises(monkeypatch, tmp_path):
    """If the job store blows up, the pipeline must not break — discover is enrich."""
    from app.services.auto.discover_job_store import DiscoverJobStore

    jobs_store = DiscoverJobStore(tmp_path / "discover-jobs.json")

    def _boom(**kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(jobs_store, "create_job", _boom)
    runner = AutoPipelineRunner(store=_FakeStore(), discover_job_store=jobs_store)

    stats = runner._schedule_discover_job(
        theme_id="gtheme_abc",
        trigger_project_id="proj_1",
        new_entry_ids=["canon_a"],
        run_id="run",
    )
    assert stats["scheduled"] is False
    assert "disk full" in stats["error"]


def test_drain_governance_mark_soft_fails(monkeypatch):
    """If _mark_theme_governance_scan_requested raises, drain must still succeed."""
    store = _DrainFakeStore(urls=["http://example.com/b"])
    runner = AutoPipelineRunner(store=store)
    monkeypatch.setattr(runner, "_run_claimed", _fake_outcome)

    def _boom(**kwargs):
        raise RuntimeError("governance store unavailable")

    monkeypatch.setattr(
        "app.services.auto.governance_request_store.mark_pending",
        _boom,
    )

    # Must not raise — soft-fail only
    result = runner.run_until_drained()

    assert isinstance(result, DrainResult)
    assert len(result.runs) == 1
