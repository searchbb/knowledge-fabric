from __future__ import annotations

import time

import pytest

from app.services.auto import pipeline_runner as pipeline_runner_module
from app.services.auto.pipeline_runner import (
    AutoPipelineRunner,
    AutoPipelineTimeoutError,
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
