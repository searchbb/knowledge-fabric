"""Tests for cooperative task cancel.

Covers the ``TaskManager.request_cancel`` / ``is_cancel_requested`` /
``mark_cancelled`` state machine and the HTTP cancel endpoint. Does NOT
cover the full backend graph build loop — that is exercised by the
existing live E2E and by test_graph_api_build.py.
"""

from __future__ import annotations

import pytest

from app import create_app
from app.models.task import Task, TaskManager, TaskStatus
from app.services.graph_builder import BuildCancelledError


@pytest.fixture(autouse=True)
def _reset_task_manager():
    """Clear singleton task state between tests."""
    manager = TaskManager()
    with manager._task_lock:
        manager._tasks.clear()
    yield
    with manager._task_lock:
        manager._tasks.clear()


class TestRequestCancel:
    def test_sets_flag_on_active_task(self):
        manager = TaskManager()
        tid = manager.create_task(task_type="graph_build")
        manager.update_task(tid, status=TaskStatus.PROCESSING, progress=20)

        ok = manager.request_cancel(tid, reason="watchdog timeout")
        assert ok is True
        assert manager.is_cancel_requested(tid) is True
        task = manager.get_task(tid)
        assert task.cancel_requested is True
        assert task.cancel_reason == "watchdog timeout"
        # Status must stay processing until worker observes the flag
        assert task.status == TaskStatus.PROCESSING

    def test_cannot_cancel_completed_task(self):
        manager = TaskManager()
        tid = manager.create_task(task_type="graph_build")
        manager.complete_task(tid, result={"ok": True})
        assert manager.request_cancel(tid) is False

    def test_cannot_cancel_failed_task(self):
        manager = TaskManager()
        tid = manager.create_task(task_type="graph_build")
        manager.fail_task(tid, error="oops")
        assert manager.request_cancel(tid) is False

    def test_cannot_cancel_unknown_task(self):
        manager = TaskManager()
        assert manager.request_cancel("tid_that_does_not_exist") is False


class TestMarkCancelled:
    def test_transitions_to_cancelled(self):
        manager = TaskManager()
        tid = manager.create_task(task_type="graph_build")
        manager.update_task(tid, status=TaskStatus.PROCESSING, progress=30)
        manager.request_cancel(tid, reason="test")
        manager.mark_cancelled(tid, reason="worker observed cancel")

        task = manager.get_task(tid)
        assert task.status == TaskStatus.CANCELLED
        assert task.cancelled_at is not None
        assert task.error == "worker observed cancel"


class TestCancelEndpoint:
    def test_post_cancel_returns_200_when_active(self):
        app = create_app()
        client = app.test_client()
        manager = TaskManager()
        tid = manager.create_task(task_type="graph_build")
        manager.update_task(tid, status=TaskStatus.PROCESSING, progress=20)

        resp = client.post(f"/api/graph/task/{tid}/cancel", json={"reason": "test"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["cancel_requested"] is True
        assert body["data"]["cancel_reason"] == "test"

    def test_post_cancel_returns_404_when_missing(self):
        app = create_app()
        client = app.test_client()
        resp = client.post("/api/graph/task/nope/cancel")
        assert resp.status_code == 404

    def test_post_cancel_returns_409_when_already_done(self):
        app = create_app()
        client = app.test_client()
        manager = TaskManager()
        tid = manager.create_task(task_type="graph_build")
        manager.complete_task(tid, result={})
        resp = client.post(f"/api/graph/task/{tid}/cancel")
        assert resp.status_code == 409


class TestBuildCancelledError:
    def test_carries_progress_info(self):
        err = BuildCancelledError(
            batch_index=3,
            total_batches=8,
            processed_chunks=4,
            total_chunks=15,
        )
        assert err.batch_index == 3
        assert err.processed_chunks == 4
        assert "3/8" in str(err)
        assert "4/15" in str(err)
