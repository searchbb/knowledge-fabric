from __future__ import annotations

from flask import Flask
import pytest

from app.api import theme_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.workspace import theme_view_service as theme_view_module


@pytest.fixture()
def theme_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))

    monkeypatch.setattr(
        theme_view_module,
        "load_graph_data",
        lambda graph_id: {
            "graph_id": graph_id,
            "node_count": 5,
            "edge_count": 3,
            "nodes": [
                {"uuid": "n1", "name": "版本控制", "labels": ["Mechanism"]},
                {"uuid": "n2", "name": "内容分离", "labels": ["Mechanism"]},
                {"uuid": "n3", "name": "GitHub", "labels": ["Technology"]},
                {"uuid": "n4", "name": "协作效率", "labels": ["Metric"]},
                {"uuid": "n5", "name": "开源社区", "labels": ["Evidence"]},
            ],
            "edges": [
                {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n3", "name": "SUPPORTED_BY"},
                {"uuid": "e2", "source_node_uuid": "n2", "target_node_uuid": "n4", "name": "DRIVES"},
                {"uuid": "e3", "source_node_uuid": "n3", "target_node_uuid": "n5", "name": "CONNECTS"},
            ],
        },
    )

    app = Flask(__name__)
    app.register_blueprint(theme_bp, url_prefix="/api/theme")
    return app.test_client()


def test_theme_view_returns_project_scoped_theme_candidates(theme_client):
    project = ProjectManager.create_project(name="Markdown 为什么会流行?")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "mirofish_theme_graph"
    project.analysis_summary = "文章围绕格式与内容分离、版本控制与协作扩散展开。"
    project.reading_structure = {
        "title": "Markdown 为什么会流行",
        "summary": "文章主线围绕低格式开销和协作效率展开。",
        "problem": {"title": "写作与格式冲突", "summary": "作者认为写作过程不该被格式切断。"},
        "solution": {"title": "用 Markdown 降低表达摩擦", "summary": "以轻量标记语言降低写作开销。"},
        "architecture": {"title": "从文本到协作网络", "summary": "通过 Git 与平台放大协作价值。"},
        "group_titles": {
            "Mechanism": "关键机制",
            "Technology": "涉及技术",
            "Metric": "验证指标",
            "Evidence": "关键证据",
        },
        "article_sections": ["版本控制", "内容分离", "开源协作"],
    }
    project.phase1_task_result = {
        "build_outcome": {
            "status": "completed_with_warnings",
            "warnings": ["fallback graph applied"],
        }
    }
    ProjectManager.save_project(project)

    response = theme_client.get(f"/api/theme/projects/{project.project_id}/view")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["meta"]["projectId"] == project.project_id
    assert payload["data"]["meta"]["viewVersion"] == "theme-candidates-v1"
    assert payload["data"]["overview"]["candidateCount"] == 4
    assert payload["data"]["overview"]["readingGroupCount"] == 4
    assert payload["data"]["backbone"]["problem"]["title"] == "写作与格式冲突"
    assert payload["data"]["themeCandidates"][0]["kind"] == "reading_group"
    assert payload["data"]["themeCandidates"][0]["evidence"]["nodeCount"] >= 1
    assert payload["data"]["themeCandidates"][0]["sourceRefs"][0].startswith("reading_structure.group_titles.")
    assert payload["data"]["diagnostics"]["dataCompleteness"] == "reading_structure_with_graph"
    assert payload["data"]["limitations"]


def test_theme_view_returns_404_for_missing_project(theme_client):
    response = theme_client.get("/api/theme/projects/proj_missing/view")
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["success"] is False


# --- Theme writeback tests ---


def _create_theme_project():
    project = ProjectManager.create_project(name="Theme Writeback Test")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "mirofish_theme_graph"
    project.reading_structure = {
        "title": "Test",
        "group_titles": {"Mechanism": "关键机制", "Technology": "涉及技术"},
    }
    project.phase1_task_result = {
        "build_outcome": {"status": "completed", "warnings": []},
    }
    ProjectManager.save_project(project)
    return project.project_id


def test_put_theme_decision_persists_and_appears_in_view(theme_client):
    project_id = _create_theme_project()

    put_resp = theme_client.put(
        f"/api/theme/projects/{project_id}/decisions/reading_group:mechanism",
        json={"status": "confirmed", "note": "Core theme"},
    )
    assert put_resp.status_code == 200
    assert put_resp.get_json()["success"] is True

    view_resp = theme_client.get(f"/api/theme/projects/{project_id}/view")
    view_data = view_resp.get_json()["data"]
    mech = next(c for c in view_data["themeCandidates"] if c["candidateKey"] == "reading_group:mechanism")
    assert mech["status"] == "confirmed"
    assert mech["note"] == "Core theme"
    assert view_data["overview"]["confirmedCount"] >= 1
    assert view_data["themeDecisionsVersion"] == 1


def test_put_theme_decision_rejects_invalid_status(theme_client):
    project_id = _create_theme_project()

    resp = theme_client.put(
        f"/api/theme/projects/{project_id}/decisions/reading_group:mechanism",
        json={"status": "bad_status"},
    )
    assert resp.status_code == 400


def test_delete_theme_decision_clears_state(theme_client):
    project_id = _create_theme_project()

    theme_client.put(
        f"/api/theme/projects/{project_id}/decisions/reading_group:technology",
        json={"status": "dismissed", "note": "Not a theme"},
    )
    del_resp = theme_client.delete(f"/api/theme/projects/{project_id}/decisions/reading_group:technology")
    assert del_resp.status_code == 200

    view_resp = theme_client.get(f"/api/theme/projects/{project_id}/view")
    tech = next(c for c in view_resp.get_json()["data"]["themeCandidates"] if c["candidateKey"] == "reading_group:technology")
    # Without persisted decision, theme candidates don't have a status field set by build_theme_candidates,
    # so it falls through to the schema default
    assert tech.get("status", "unreviewed") in ("unreviewed", "")
