from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def research_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    return app.test_client()


def test_create_research_project(research_client):
    resp = research_client.post(
        "/api/research-projects",
        json={
            "title": "华为云 Agent-ready 企业软件栈战略研究",
            "background": "研究华为云在 Agent-ready 企业软件栈中的战略机会",
            "audience": "华为云战略部二层领导",
            "goal": "形成战略判断、试点路径和汇报材料输入",
        },
    )

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["id"].startswith("rp_")
    assert data["title"] == "华为云 Agent-ready 企业软件栈战略研究"
    assert data["status"] == "draft"


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": "   "}])
def test_create_requires_title(research_client, payload):
    resp = research_client.post("/api/research-projects", json=payload)

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_create_rejects_invalid_status(research_client):
    resp = research_client.post(
        "/api/research-projects",
        json={"title": "Strategy", "status": "researching"},
    )

    assert resp.status_code == 400
    assert "status" in resp.get_json()["error"]


def test_create_rejects_unknown_and_server_fields(research_client):
    resp = research_client.post(
        "/api/research-projects",
        json={"title": "Strategy", "id": "rp_000000000000", "scheduler": True},
    )

    assert resp.status_code == 400
    assert "unsupported fields" in resp.get_json()["error"]


def test_list_and_get_research_projects(research_client):
    created = research_client.post("/api/research-projects", json={"title": "Strategy"}).get_json()["data"]

    list_resp = research_client.get("/api/research-projects")
    assert list_resp.status_code == 200
    payload = list_resp.get_json()["data"]
    assert payload["total"] == 1
    assert payload["projects"][0]["id"] == created["id"]

    get_resp = research_client.get(f"/api/research-projects/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["data"]["title"] == "Strategy"


def test_get_missing_returns_404(research_client):
    resp = research_client.get("/api/research-projects/rp_000000000000")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_patch_updates_basic_fields(research_client):
    created = research_client.post("/api/research-projects", json={"title": "Draft"}).get_json()["data"]

    resp = research_client.patch(
        f"/api/research-projects/{created['id']}",
        json={
            "title": "Updated",
            "status": "active",
            "research_brief": {"problem_statement": "What should Huawei Cloud control?"},
            "issue_tree": [{"title": "Strategic window"}],
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["title"] == "Updated"
    assert data["status"] == "active"
    assert data["research_brief"]["problem_statement"] == "What should Huawei Cloud control?"
    assert data["issue_tree"] == [{"title": "Strategic window"}]
    assert data["created_at"] == created["created_at"]
    assert data["updated_at"] > created["updated_at"]


def test_patch_rejects_id_and_invalid_array(research_client):
    created = research_client.post("/api/research-projects", json={"title": "Draft"}).get_json()["data"]

    id_resp = research_client.patch(f"/api/research-projects/{created['id']}", json={"id": "rp_000000000000"})
    assert id_resp.status_code == 400

    array_resp = research_client.patch(f"/api/research-projects/{created['id']}", json={"evidence_items": {}})
    assert array_resp.status_code == 400
    assert "array" in array_resp.get_json()["error"]


def test_patch_missing_returns_404(research_client):
    resp = research_client.patch("/api/research-projects/rp_000000000000", json={"title": "Updated"})

    assert resp.status_code == 404


def test_api_rejects_non_object_json(research_client):
    resp = research_client.post("/api/research-projects", json=["not", "object"])

    assert resp.status_code == 400
    assert "object" in resp.get_json()["error"]
