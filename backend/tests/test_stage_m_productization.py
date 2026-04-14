"""Stage M: Productization tests (export + overview)."""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp
from app.config import Config
from app.models.project import ProjectManager, ProjectStatus
from app.services.registry import global_concept_registry as concept_reg
from app.services.registry import global_theme_registry as theme_reg
from app.services.registry import evolution_log as evo_mod
from app.services.registry import review_task_service as review_mod


@pytest.fixture()
def prod_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    # Point everything to the same tmp dir
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    monkeypatch.setattr(concept_reg, "_registry_path", lambda: str(projects_dir / "concept_registry.json"))
    monkeypatch.setattr(theme_reg, "_themes_path", lambda: str(projects_dir / "global_themes.json"))
    monkeypatch.setattr(evo_mod, "_log_path", lambda: str(projects_dir / "evolution_log.json"))
    monkeypatch.setattr(review_mod, "_tasks_path", lambda: str(projects_dir / "review_tasks.json"))

    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    return app.test_client()


class TestExport:
    def test_export_empty(self, prod_client):
        resp = prod_client.get("/api/registry/export")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["version"] == 1
        assert "exported_at" in data
        assert "concept_registry" in data
        assert "global_themes" in data
        assert "evolution_log" in data
        assert "review_tasks" in data

    def test_export_with_data(self, prod_client):
        # Create some data
        prod_client.post("/api/registry/concepts", json={"canonical_name": "AI"})
        prod_client.post("/api/registry/themes", json={"name": "Safety"})

        resp = prod_client.get("/api/registry/export")
        data = resp.get_json()["data"]
        assert len(data["concept_registry"].get("entries", {})) == 1
        assert len(data["global_themes"].get("themes", {})) == 1
        assert len(data["evolution_log"].get("events", [])) >= 2


class TestOverview:
    def test_overview_empty(self, prod_client):
        resp = prod_client.get("/api/registry/overview")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["project_count"] == 0
        assert data["global_stats"]["registry_entries"] == 0

    def test_overview_with_projects(self, prod_client):
        # Create a project with concept decisions
        project = ProjectManager.create_project(name="Test Project")
        project.status = ProjectStatus.GRAPH_COMPLETED
        project.concept_decisions = {
            "version": 1,
            "items": {
                "Tech:ml": {"status": "accepted", "canonical_name": "ML"},
                "Tech:dl": {"status": "accepted", "canonical_name": "DL"},
                "Tech:cnn": {"status": "rejected", "canonical_name": "CNN"},
            },
        }
        project.theme_clusters = [
            {"id": "tc_1", "name": "Cluster 1"},
        ]
        ProjectManager.save_project(project)

        # Create a registry entry and link one concept
        resp = prod_client.post("/api/registry/concepts", json={"canonical_name": "Machine Learning", "concept_type": "Tech"})
        entry_id = resp.get_json()["data"]["entry_id"]
        prod_client.post(f"/api/registry/concepts/{entry_id}/links", json={
            "project_id": project.project_id, "concept_key": "Tech:ml",
        })

        # Create a review task
        prod_client.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": entry_id,
            "project_id": project.project_id,
        })

        resp = prod_client.get("/api/registry/overview")
        data = resp.get_json()["data"]
        assert data["project_count"] == 1

        proj = data["projects"][0]
        assert proj["project_name"] == "Test Project"
        assert proj["concept_count"] == 3
        assert proj["accepted_concept_count"] == 2
        assert proj["linked_concept_count"] == 1
        assert proj["alignment_coverage"] == 0.5
        assert proj["theme_cluster_count"] == 1
        assert proj["pending_review_count"] == 1

        assert data["global_stats"]["registry_entries"] == 1
        assert data["global_stats"]["pending_reviews"] == 1
