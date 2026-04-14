from __future__ import annotations

from flask import Flask
import pytest

from app.api import evolution_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.workspace import evolution_view_service as evolution_view_module


@pytest.fixture()
def evolution_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))

    monkeypatch.setattr(
        evolution_view_module,
        "load_graph_data",
        lambda graph_id: {
            "graph_id": graph_id,
            "node_count": 3,
            "edge_count": 2,
            "nodes": [
                {"uuid": "n1", "name": "Markdown", "labels": ["Topic"], "created_at": "2026-04-08T09:00:00"},
                {"uuid": "n2", "name": "版本控制", "labels": ["Mechanism"], "created_at": "2026-04-08T09:05:00"},
                {"uuid": "n3", "name": "GitHub", "labels": ["Technology"], "created_at": None},
            ],
            "edges": [
                {
                    "uuid": "e1",
                    "name": "ENABLES",
                    "fact": "Markdown 帮助版本控制协作",
                    "source_node_name": "Markdown",
                    "target_node_name": "版本控制",
                    "created_at": "2026-04-08T09:10:00",
                },
                {
                    "uuid": "e2",
                    "name": "SUPPORTED_BY",
                    "fact": "GitHub 放大 Markdown 的协作价值",
                    "source_node_name": "Markdown",
                    "target_node_name": "GitHub",
                    "created_at": None,
                },
            ],
        },
    )

    app = Flask(__name__)
    app.register_blueprint(evolution_bp, url_prefix="/api/evolution")
    return app.test_client()


def test_evolution_view_returns_growth_snapshot(evolution_client):
    project = ProjectManager.create_project(name="Markdown 为什么会流行?")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "mirofish_evolution_graph"
    project.analysis_summary = "文章围绕格式与内容分离、版本控制和协作扩散展开。"
    project.phase1_task_result = {
        "build_outcome": {
            "status": "completed_with_warnings",
            "warnings": ["fallback graph applied"],
        }
    }
    ProjectManager.save_project(project)

    response = evolution_client.get(f"/api/evolution/projects/{project.project_id}/view")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["meta"]["projectId"] == project.project_id
    assert payload["data"]["meta"]["viewVersion"] == "evolution-snapshot-v1"
    assert payload["data"]["projectOverview"]["hasGraph"] is True
    assert payload["data"]["knowledgeAssetSnapshot"]["graphStatus"] == "available"
    assert payload["data"]["traceabilityAndSignalQuality"]["timeSignals"]["nodeCreatedAtCoverage"] == "partial"
    assert payload["data"]["traceabilityAndSignalQuality"]["timeSignals"]["edgeCreatedAtCoverage"] == "partial"
    assert payload["data"]["diagnostics"]["timestampSignalAvailable"] is True
    assert payload["data"]["nextCapabilitiesGap"]["readinessLevel"] == "snapshot_only"
    assert payload["data"]["nextCapabilitiesGap"]["missingCapabilities"]


def test_evolution_view_returns_404_for_missing_project(evolution_client):
    response = evolution_client.get("/api/evolution/projects/proj_missing/view")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["success"] is False
