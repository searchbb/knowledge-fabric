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


def test_build_article_pipeline_uses_vite_frontend_port_when_env_unset(monkeypatch):
    runner = AutoPipelineRunner()

    monkeypatch.delenv("KNOWLEDGE_WORKSPACE_FRONTEND", raising=False)

    pipeline = runner._build_article_pipeline()

    assert pipeline.frontend_base_url == "http://localhost:3000"


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
