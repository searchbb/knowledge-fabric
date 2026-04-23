"""Stage J: Global theme registry API tests."""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.registry import global_theme_registry as theme_reg_mod


@pytest.fixture()
def theme_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    monkeypatch.setattr(theme_reg_mod, "_themes_path", lambda: str(projects_dir / "global_themes.json"))

    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    return app.test_client()


def _create_project_with_clusters(clusters=None):
    project = ProjectManager.create_project(name="Theme Test Project")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "test_graph"
    project.theme_clusters = clusters or []
    ProjectManager.save_project(project)
    return project.project_id


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestGlobalThemeCRUD:
    def test_create_and_list(self, theme_client):
        resp = theme_client.post(
            "/api/registry/themes",
            json={"name": "AI Safety", "description": "Safety in AI systems", "domain": "tech"},
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["name"] == "AI Safety"
        assert data["status"] == "active"
        theme_id = data["theme_id"]

        resp = theme_client.get("/api/registry/themes")
        assert resp.status_code == 200
        themes = resp.get_json()["data"]["themes"]
        assert len(themes) == 1
        assert themes[0]["theme_id"] == theme_id

    def test_get_single(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "NLP Advances", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        resp = theme_client.get(f"/api/registry/themes/{theme_id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "NLP Advances"

    def test_get_not_found(self, theme_client):
        resp = theme_client.get("/api/registry/themes/nonexistent")
        assert resp.status_code == 404

    def test_update(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "Draft Theme", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        resp = theme_client.put(
            f"/api/registry/themes/{theme_id}",
            json={"name": "Finalized Theme", "status": "archived"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "Finalized Theme"
        assert data["status"] == "archived"

    def test_delete(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "To Delete", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        resp = theme_client.delete(f"/api/registry/themes/{theme_id}")
        assert resp.status_code == 200

        resp = theme_client.get(f"/api/registry/themes/{theme_id}")
        assert resp.status_code == 404

    def test_duplicate_rejected(self, theme_client):
        theme_client.post("/api/registry/themes", json={"name": "Unique Theme", "domain": "tech"})
        resp = theme_client.post("/api/registry/themes", json={"name": "unique theme", "domain": "tech"})
        assert resp.status_code == 409

    def test_empty_name_rejected(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": ""})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Concept attach / detach
# ---------------------------------------------------------------------------


class TestGlobalThemeConcepts:
    def test_attach_and_detach_concepts(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "ML Theme", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        # Attach
        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/concepts:attach",
            json={"concept_entry_ids": ["canon_001", "canon_002"]},
        )
        assert resp.status_code == 200
        assert sorted(resp.get_json()["data"]["concept_entry_ids"]) == ["canon_001", "canon_002"]

        # Detach one
        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/concepts:detach",
            json={"concept_entry_ids": ["canon_001"]},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["concept_entry_ids"] == ["canon_002"]

    def test_attach_idempotent(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "Idem Theme", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        theme_client.post(
            f"/api/registry/themes/{theme_id}/concepts:attach",
            json={"concept_entry_ids": ["canon_x"]},
        )
        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/concepts:attach",
            json={"concept_entry_ids": ["canon_x"]},
        )
        assert len(resp.get_json()["data"]["concept_entry_ids"]) == 1


# ---------------------------------------------------------------------------
# Project cluster link / unlink
# ---------------------------------------------------------------------------


class TestGlobalThemeClusterLinks:
    def test_link_and_unlink_cluster(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "Cluster Theme", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        # Link
        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/clusters:link",
            json={"project_id": "proj_a", "cluster_id": "tc_001", "cluster_name": "Project A Cluster"},
        )
        assert resp.status_code == 200
        links = resp.get_json()["data"]["source_project_clusters"]
        assert len(links) == 1
        assert links[0]["project_id"] == "proj_a"

        # Idempotent
        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/clusters:link",
            json={"project_id": "proj_a", "cluster_id": "tc_001"},
        )
        assert len(resp.get_json()["data"]["source_project_clusters"]) == 1

        # Unlink
        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/clusters:unlink",
            json={"project_id": "proj_a", "cluster_id": "tc_001"},
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]["source_project_clusters"]) == 0

    def test_link_missing_fields(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "Bad Link", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        resp = theme_client.post(
            f"/api/registry/themes/{theme_id}/clusters:link",
            json={"project_id": "p1"},  # missing cluster_id
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Suggest from project
# ---------------------------------------------------------------------------


class TestGlobalThemeSuggest:
    def test_suggest_new_candidates(self, theme_client):
        pid = _create_project_with_clusters([
            {"id": "tc_1", "name": "Deep Learning Advances", "concept_ids": ["c1", "c2"], "status": "active"},
            {"id": "tc_2", "name": "NLP Trends", "concept_ids": ["c3"], "status": "active"},
        ])

        resp = theme_client.post(f"/api/registry/themes/suggest-from-project/{pid}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total_clusters"] == 2
        assert len(data["new_candidates"]) == 2

    def test_suggest_with_existing_match(self, theme_client):
        # Pre-create a global theme
        theme_client.post("/api/registry/themes", json={"name": "Deep Learning Advances", "domain": "tech"})

        pid = _create_project_with_clusters([
            {"id": "tc_1", "name": "Deep Learning Advances", "concept_ids": ["c1"], "status": "active"},
            {"id": "tc_2", "name": "New Topic", "concept_ids": [], "status": "active"},
        ])

        resp = theme_client.post(f"/api/registry/themes/suggest-from-project/{pid}")
        data = resp.get_json()["data"]
        assert len(data["existing_matches"]) == 1
        assert data["existing_matches"][0]["matched_theme_name"] == "Deep Learning Advances"
        assert len(data["new_candidates"]) == 1

    def test_suggest_project_not_found(self, theme_client):
        resp = theme_client.post("/api/registry/themes/suggest-from-project/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cross-project scenario
# ---------------------------------------------------------------------------


class TestCrossProjectTheme:
    def test_two_projects_link_clusters_to_same_theme(self, theme_client):
        resp = theme_client.post("/api/registry/themes", json={"name": "Shared Theme", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        # Attach concepts
        theme_client.post(
            f"/api/registry/themes/{theme_id}/concepts:attach",
            json={"concept_entry_ids": ["canon_ml"]},
        )

        # Link from two projects
        theme_client.post(
            f"/api/registry/themes/{theme_id}/clusters:link",
            json={"project_id": "proj_a", "cluster_id": "tc_a1", "cluster_name": "A Cluster"},
        )
        theme_client.post(
            f"/api/registry/themes/{theme_id}/clusters:link",
            json={"project_id": "proj_b", "cluster_id": "tc_b1", "cluster_name": "B Cluster"},
        )

        resp = theme_client.get(f"/api/registry/themes/{theme_id}")
        theme = resp.get_json()["data"]
        assert len(theme["source_project_clusters"]) == 2
        assert theme["concept_entry_ids"] == ["canon_ml"]
