from __future__ import annotations

from flask import Flask
import pytest

from app.api import concept_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.workspace import concept_view_service as concept_view_module


@pytest.fixture()
def concept_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))

    monkeypatch.setattr(
        concept_view_module,
        "load_graph_data",
        lambda graph_id: {
            "graph_id": graph_id,
            "node_count": 4,
            "edge_count": 3,
            "nodes": [
                {"uuid": "n1", "name": "Markdown", "labels": ["Topic"], "summary": "Markdown 是一种轻量标记语言。"},
                {"uuid": "n2", "name": "Markdown", "labels": ["Topic"], "summary": "Markdown 帮助内容协作与复用。"},
                {"uuid": "n3", "name": "版本控制", "labels": ["Mechanism"], "summary": "版本控制是 Markdown 传播的重要机制。"},
                {"uuid": "n4", "name": "GitHub", "labels": ["Platform"], "summary": "GitHub 放大了 Markdown 的协作价值。"},
            ],
            "edges": [
                {
                    "uuid": "e1",
                    "source_node_uuid": "n1",
                    "target_node_uuid": "n3",
                    "name": "ENABLES",
                },
                {
                    "uuid": "e2",
                    "source_node_uuid": "n2",
                    "target_node_uuid": "n3",
                    "name": "ENABLES",
                },
                {
                    "uuid": "e3",
                    "source_node_uuid": "n1",
                    "target_node_uuid": "n4",
                    "name": "SUPPORTED_BY",
                },
            ],
        },
    )

    app = Flask(__name__)
    app.register_blueprint(concept_bp, url_prefix="/api/concept")
    return app.test_client()


def test_concept_view_returns_project_scoped_candidate_summary(concept_client):
    project = ProjectManager.create_project(name="Markdown 为什么会流行?")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "mirofish_concept_graph"
    project.phase1_task_result = {
        "build_outcome": {
            "status": "completed_with_warnings",
            "warnings": ["fallback graph applied"],
        }
    }
    ProjectManager.save_project(project)

    response = concept_client.get(f"/api/concept/projects/{project.project_id}/view")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["meta"]["projectId"] == project.project_id
    assert payload["data"]["meta"]["phase1Status"] == "completed_with_warnings"
    assert payload["data"]["summary"]["candidateConceptCount"] == 3
    assert payload["data"]["summary"]["warningsCount"] == 1
    assert payload["data"]["diagnostics"]["dataCompleteness"] == "graph_with_phase1_snapshot"
    assert payload["data"]["candidateConcepts"][0]["displayName"] == "Markdown"
    assert payload["data"]["candidateConcepts"][0]["mentionCount"] == 2
    assert payload["data"]["candidateConcepts"][0]["connectedCount"] == 3
    assert payload["data"]["candidateConcepts"][0]["sourceNodeIds"] == ["n1", "n2"]
    assert payload["data"]["diagnostics"]["typeCounts"][0]["type"] == "Topic"


def test_concept_view_returns_404_for_missing_project(concept_client):
    response = concept_client.get("/api/concept/projects/proj_missing/view")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["success"] is False


# --- Concept writeback tests ---


def _create_concept_project():
    project = ProjectManager.create_project(name="Concept Writeback Test")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "mirofish_concept_graph"
    project.phase1_task_result = {
        "build_outcome": {"status": "completed", "warnings": []},
    }
    ProjectManager.save_project(project)
    return project.project_id


def test_put_concept_decision_persists_and_appears_in_view(concept_client):
    project_id = _create_concept_project()

    put_resp = concept_client.put(
        f"/api/concept/projects/{project_id}/decisions/Topic:markdown",
        json={"status": "accepted", "note": "Core concept", "canonical_name": "Markdown"},
    )
    assert put_resp.status_code == 200
    assert put_resp.get_json()["success"] is True

    view_resp = concept_client.get(f"/api/concept/projects/{project_id}/view")
    view_data = view_resp.get_json()["data"]
    md_candidate = next(c for c in view_data["candidateConcepts"] if c["key"] == "Topic:markdown")
    assert md_candidate["status"] == "accepted"
    assert md_candidate["note"] == "Core concept"
    assert md_candidate["canonicalName"] == "Markdown"
    assert view_data["summary"]["acceptedCount"] >= 1
    assert view_data["conceptDecisionsVersion"] == 1


def test_put_concept_decision_rejects_invalid_status(concept_client):
    project_id = _create_concept_project()

    resp = concept_client.put(
        f"/api/concept/projects/{project_id}/decisions/Topic:markdown",
        json={"status": "invalid"},
    )
    assert resp.status_code == 400


def test_delete_concept_decision_clears_state(concept_client):
    project_id = _create_concept_project()

    concept_client.put(
        f"/api/concept/projects/{project_id}/decisions/Mechanism:版本控制",
        json={"status": "rejected", "note": "Not relevant"},
    )
    del_resp = concept_client.delete(f"/api/concept/projects/{project_id}/decisions/Mechanism:版本控制")
    assert del_resp.status_code == 200

    view_resp = concept_client.get(f"/api/concept/projects/{project_id}/view")
    mech = next(c for c in view_resp.get_json()["data"]["candidateConcepts"] if "版本控制" in c["key"])
    assert mech["status"] == "unreviewed"
