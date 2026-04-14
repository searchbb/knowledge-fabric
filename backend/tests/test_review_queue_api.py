"""Stage L: Review task queue API tests."""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp
from app.models.project import ProjectManager
from app.services.registry import review_task_service as review_mod
from app.services.registry import evolution_log as evo_mod


@pytest.fixture()
def review_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    monkeypatch.setattr(review_mod, "_tasks_path", lambda: str(projects_dir / "review_tasks.json"))
    monkeypatch.setattr(evo_mod, "_log_path", lambda: str(projects_dir / "evolution_log.json"))

    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    return app.test_client()


def _create_task(client, **overrides):
    body = {
        "entity_type": "concept_entry",
        "entity_id": "canon_001",
        "entity_name": "Machine Learning",
        "action_required": "confirm_link",
        "priority": "normal",
        **overrides,
    }
    resp = client.post("/api/registry/review/tasks", json=body)
    assert resp.status_code == 201
    return resp.get_json()["data"]


class TestReviewTaskCRUD:
    def test_create_and_list(self, review_client):
        task = _create_task(review_client)
        assert task["status"] == "open"
        assert task["entity_name"] == "Machine Learning"

        resp = review_client.get("/api/registry/review/tasks")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total"] == 1

    def test_get_single(self, review_client):
        task = _create_task(review_client)
        resp = review_client.get(f"/api/registry/review/tasks/{task['task_id']}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["entity_name"] == "Machine Learning"

    def test_get_not_found(self, review_client):
        resp = review_client.get("/api/registry/review/tasks/nonexistent")
        assert resp.status_code == 404

    def test_missing_fields(self, review_client):
        resp = review_client.post("/api/registry/review/tasks", json={"entity_type": "x"})
        assert resp.status_code == 400


class TestReviewTaskWorkflow:
    def test_claim_and_resolve(self, review_client):
        task = _create_task(review_client)
        tid = task["task_id"]

        # Claim
        resp = review_client.put(f"/api/registry/review/tasks/{tid}", json={"status": "claimed"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "claimed"

        # Resolve
        resp = review_client.put(
            f"/api/registry/review/tasks/{tid}",
            json={"status": "resolved", "resolution": "approved", "note": "LGTM"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "resolved"
        assert data["resolution"] == "approved"
        assert data["resolved_at"] != ""

    def test_reopen(self, review_client):
        task = _create_task(review_client)
        tid = task["task_id"]

        review_client.put(f"/api/registry/review/tasks/{tid}", json={"status": "resolved", "resolution": "approved"})

        resp = review_client.put(f"/api/registry/review/tasks/{tid}", json={"status": "reopened"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "reopened"

    def test_invalid_transition(self, review_client):
        task = _create_task(review_client)
        tid = task["task_id"]

        # open → reopened is invalid
        resp = review_client.put(f"/api/registry/review/tasks/{tid}", json={"status": "reopened"})
        assert resp.status_code == 409


class TestBatchResolve:
    def test_batch_resolve_multiple(self, review_client):
        t1 = _create_task(review_client, entity_id="c1")
        t2 = _create_task(review_client, entity_id="c2")
        t3 = _create_task(review_client, entity_id="c3")

        resp = review_client.post(
            "/api/registry/review/tasks/batch-resolve",
            json={"task_ids": [t1["task_id"], t2["task_id"], t3["task_id"]], "resolution": "approved"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["resolved_count"] == 3
        assert data["skipped_count"] == 0

    def test_batch_skips_already_resolved(self, review_client):
        t1 = _create_task(review_client, entity_id="c1")
        review_client.put(f"/api/registry/review/tasks/{t1['task_id']}", json={"status": "resolved", "resolution": "approved"})

        t2 = _create_task(review_client, entity_id="c2")

        resp = review_client.post(
            "/api/registry/review/tasks/batch-resolve",
            json={"task_ids": [t1["task_id"], t2["task_id"]]},
        )
        data = resp.get_json()["data"]
        assert data["resolved_count"] == 1
        assert data["skipped_count"] == 1

    def test_batch_empty_ids(self, review_client):
        resp = review_client.post("/api/registry/review/tasks/batch-resolve", json={"task_ids": []})
        assert resp.status_code == 400


class TestReviewFiltersAndStats:
    def test_filter_by_status(self, review_client):
        _create_task(review_client, entity_id="c1")
        t2 = _create_task(review_client, entity_id="c2")
        review_client.put(f"/api/registry/review/tasks/{t2['task_id']}", json={"status": "claimed"})

        resp = review_client.get("/api/registry/review/tasks?status=open")
        assert resp.get_json()["data"]["total"] == 1

        resp = review_client.get("/api/registry/review/tasks?status=claimed")
        assert resp.get_json()["data"]["total"] == 1

    def test_filter_by_priority(self, review_client):
        _create_task(review_client, entity_id="c1", priority="high")
        _create_task(review_client, entity_id="c2", priority="low")

        resp = review_client.get("/api/registry/review/tasks?priority=high")
        assert resp.get_json()["data"]["total"] == 1

    def test_stats(self, review_client):
        _create_task(review_client, entity_id="c1", priority="high")
        _create_task(review_client, entity_id="c2", entity_type="global_theme")
        t3 = _create_task(review_client, entity_id="c3")
        review_client.put(f"/api/registry/review/tasks/{t3['task_id']}", json={"status": "resolved", "resolution": "approved"})

        resp = review_client.get("/api/registry/review/tasks/stats")
        assert resp.status_code == 200
        stats = resp.get_json()["data"]
        assert stats["total"] == 3
        assert stats["by_status"]["open"] == 2
        assert stats["by_status"]["resolved"] == 1


class TestEvolutionIntegration:
    def test_create_emits_event(self, review_client):
        task = _create_task(review_client)

        resp = review_client.get("/api/registry/evolution/feed")
        events = resp.get_json()["data"]["events"]
        assert any(e["event_type"] == "review_task_created" for e in events)

    def test_resolve_emits_event(self, review_client):
        task = _create_task(review_client)
        review_client.put(
            f"/api/registry/review/tasks/{task['task_id']}",
            json={"status": "resolved", "resolution": "approved"},
        )

        resp = review_client.get("/api/registry/evolution/feed")
        events = resp.get_json()["data"]["events"]
        assert any(e["event_type"] == "review_task_resolved" for e in events)
