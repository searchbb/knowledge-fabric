from __future__ import annotations

from flask import Flask
import pytest

from app.api import review_bp
from app.models.project import ProjectManager, ProjectStatus
from app.models.task import TaskManager
from app.services.workspace import review_view_service as review_view_module


class _FakeBuilder:
    def __init__(self, graph_data: dict):
        self.graph_data = graph_data

    def get_graph_data(self, graph_id: str) -> dict:
        return self.graph_data


@pytest.fixture()
def review_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    task_manager = TaskManager()
    task_manager._tasks = {}

    builder = _FakeBuilder(
        {
            "graph_id": "mirofish_review_graph",
            "node_count": 9,
            "edge_count": 4,
            "nodes": [
                {"uuid": "n1", "name": "Markdown", "labels": ["Topic"]},
                {"uuid": "n2", "name": "版本控制", "labels": ["Mechanism"]},
                {"uuid": "n3", "name": "GitHub", "labels": ["Technology"]},
            ],
            "edges": [
                {
                    "uuid": "e1",
                    "source_node_uuid": "n1",
                    "target_node_uuid": "n2",
                    "name": "ENABLES",
                    "fact": "Markdown 帮助版本控制协作",
                },
                {
                    "uuid": "e2",
                    "source_node_uuid": "n2",
                    "target_node_uuid": "n3",
                    "name": "SUPPORTED_BY",
                    "fact": "GitHub 放大 Markdown 的协作价值",
                },
            ],
        }
    )
    monkeypatch.setattr(review_view_module, "load_graph_data", lambda graph_id: builder.get_graph_data(graph_id))

    app = Flask(__name__)
    app.register_blueprint(review_bp, url_prefix="/api/review")
    return app.test_client()


def _create_project(name: str, *, analysis_summary: str, reading_title: str) -> str:
    project = ProjectManager.create_project(name=name)
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.analysis_summary = analysis_summary
    project.reading_structure = {"title": reading_title}
    ProjectManager.save_project(project)
    return project.project_id


def test_review_view_returns_aggregated_prototype_payload(review_client):
    project_id = _create_project(
        "Markdown 为什么会流行?",
        analysis_summary="文章围绕格式与内容分离、版本控制和协作效率展开。",
        reading_title="Markdown 为什么会流行",
    )
    current_project = ProjectManager.get_project(project_id)
    assert current_project is not None

    current_project.graph_id = "mirofish_review_graph"
    task_id = TaskManager().create_task("graph_build", {"project_id": project_id})
    current_project.graph_build_task_id = task_id
    ProjectManager.save_project(current_project)
    ProjectManager.save_extracted_text(
        project_id,
        "\n".join(
            [
                "# Markdown 为什么会流行？",
                "",
                "Markdown 的关键优势在于格式与内容分离。",
                "",
                "## 版本控制",
                "Markdown 适合 Git 版本控制，也适合进入 canonical 与 theme 治理链路。",
            ]
        ),
    )
    TaskManager().complete_task(
        task_id,
        {
            "provider": "local",
            "build_outcome": {
                "status": "completed_with_warnings",
                "warnings": ["fallback graph applied", "阅读骨架状态: generated"],
            },
            "reading_structure_status": {
                "status": "generated",
            },
            "diagnostics": {
                "chunk_count": 4,
                "processed_chunk_count": 4,
                "fallback_graph_applied": True,
            },
        },
    )

    related_project_id = _create_project(
        "Markdown 在 AI 时代的第二次生命",
        analysis_summary="文章讨论 Markdown、AI 和人机协作之间的结构透明性。",
        reading_title="Markdown 与 AI 协作",
    )
    assert related_project_id != project_id

    response = review_client.get(f"/api/review/projects/{project_id}/view")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["project"]["project_id"] == project_id
    assert payload["data"]["summary"]["warningCount"] == 2
    assert payload["data"]["summary"]["articleTextAvailable"] is True
    assert payload["data"]["summary"]["relatedProjectCount"] == 2
    assert len(payload["data"]["items"]) == 5
    assert payload["data"]["items"][0]["sourceSnippets"]
    assert payload["data"]["items"][0]["subgraph"]["nodes"]
    assert payload["data"]["items"][0]["crossArticleCandidates"][0]["name"] == "Markdown 在 AI 时代的第二次生命"


def test_review_view_returns_404_for_missing_project(review_client):
    response = review_client.get("/api/review/projects/proj_missing/view")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["success"] is False


# --- Review writeback tests ---


def _setup_project_with_graph(review_client):
    """Create a project with graph data and a completed build task."""
    project_id = _create_project(
        "Writeback Test Article",
        analysis_summary="Test article for review writeback.",
        reading_title="Writeback Test",
    )
    project = ProjectManager.get_project(project_id)
    project.graph_id = "mirofish_review_graph"
    task_id = TaskManager().create_task("graph_build", {"project_id": project_id})
    project.graph_build_task_id = task_id
    ProjectManager.save_project(project)
    ProjectManager.save_extracted_text(project_id, "Test article content.")
    TaskManager().complete_task(
        task_id,
        {
            "provider": "local",
            "build_outcome": {"status": "completed", "warnings": ["test warning"]},
            "reading_structure_status": {"status": "generated"},
            "diagnostics": {"chunk_count": 1, "processed_chunk_count": 1},
        },
    )
    return project_id


def test_put_review_decision_persists_and_appears_in_view(review_client):
    project_id = _setup_project_with_graph(review_client)

    # PUT a decision on the first warning item
    put_resp = review_client.put(
        f"/api/review/projects/{project_id}/items/warning-1",
        json={"status": "approved", "note": "Looks correct"},
    )
    assert put_resp.status_code == 200
    put_data = put_resp.get_json()
    assert put_data["success"] is True
    assert put_data["data"]["status"] == "approved"

    # GET the view and confirm the decision is reflected
    view_resp = review_client.get(f"/api/review/projects/{project_id}/view")
    view_data = view_resp.get_json()["data"]
    warning_item = next(i for i in view_data["items"] if i["id"] == "warning-1")
    assert warning_item["status"] == "approved"
    assert warning_item["note"] == "Looks correct"
    assert warning_item["statusLabel"] == "已通过"
    assert view_data["summary"]["approvedCount"] >= 1
    assert view_data["reviewDecisionsVersion"] == 1


def test_put_review_decision_rejects_invalid_status(review_client):
    project_id = _setup_project_with_graph(review_client)

    resp = review_client.put(
        f"/api/review/projects/{project_id}/items/warning-1",
        json={"status": "invalid_status"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_delete_review_decision_clears_persisted_state(review_client):
    project_id = _setup_project_with_graph(review_client)

    # PUT then DELETE
    review_client.put(
        f"/api/review/projects/{project_id}/items/concept-alignment",
        json={"status": "questioned", "note": "Need to verify"},
    )
    del_resp = review_client.delete(f"/api/review/projects/{project_id}/items/concept-alignment")
    assert del_resp.status_code == 200
    assert del_resp.get_json()["success"] is True

    # View should show the item back as pending
    view_resp = review_client.get(f"/api/review/projects/{project_id}/view")
    concept_item = next(i for i in view_resp.get_json()["data"]["items"] if i["id"] == "concept-alignment")
    assert concept_item["status"] == "pending"


def test_put_review_decision_returns_404_for_missing_project(review_client):
    resp = review_client.put(
        "/api/review/projects/proj_missing/items/warning-1",
        json={"status": "approved"},
    )
    assert resp.status_code == 404
