"""Stage H: Global concept registry API tests."""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp, concept_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.registry import global_concept_registry as registry_mod
from app.services.workspace import concept_view_service as concept_view_module


@pytest.fixture()
def registry_client(tmp_path, monkeypatch):
    """Flask test client with isolated registry storage."""
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    # Point registry storage to the same tmp dir
    monkeypatch.setattr(registry_mod, "_registry_path", lambda: str(projects_dir / "concept_registry.json"))

    # Stub graph loader for project concept tests
    monkeypatch.setattr(
        concept_view_module,
        "load_graph_data",
        lambda graph_id: {
            "graph_id": graph_id,
            "node_count": 2,
            "edge_count": 1,
            "nodes": [
                {"uuid": "n1", "name": "Machine Learning", "labels": ["Technology"], "summary": "ML is a branch of AI."},
                {"uuid": "n2", "name": "Deep Learning", "labels": ["Technology"], "summary": "DL is a subset of ML."},
            ],
            "edges": [
                {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2", "name": "CONTAINS"},
            ],
        },
    )

    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    app.register_blueprint(concept_bp, url_prefix="/api/concept")
    return app.test_client()


def _create_project_with_concepts(accepted_keys: dict[str, str] | None = None) -> str:
    """Helper: create a project with concept decisions."""
    project = ProjectManager.create_project(name="Test Project")
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "test_graph"
    if accepted_keys:
        items = {}
        for key, canonical in accepted_keys.items():
            items[key] = {
                "status": "accepted",
                "canonical_name": canonical,
                "note": "",
                "updated_at": "2026-04-09T00:00:00",
            }
        project.concept_decisions = {"version": 1, "items": items}
    ProjectManager.save_project(project)
    return project.project_id


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


class TestRegistryCRUD:
    def test_create_and_list(self, registry_client):
        # Create
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Artificial Intelligence", "concept_type": "Technology", "aliases": ["AI", "人工智能"]},
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["canonical_name"] == "Artificial Intelligence"
        assert data["concept_type"] == "Technology"
        assert data["aliases"] == ["AI", "人工智能"]
        entry_id = data["entry_id"]

        # List
        resp = registry_client.get("/api/registry/concepts")
        assert resp.status_code == 200
        entries = resp.get_json()["data"]["entries"]
        assert len(entries) == 1
        assert entries[0]["entry_id"] == entry_id

    def test_get_single(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Kubernetes"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        resp = registry_client.get(f"/api/registry/concepts/{entry_id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["canonical_name"] == "Kubernetes"

    def test_get_not_found(self, registry_client):
        resp = registry_client.get("/api/registry/concepts/nonexistent")
        assert resp.status_code == 404

    def test_update(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "ML", "concept_type": "Technology"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        resp = registry_client.put(
            f"/api/registry/concepts/{entry_id}",
            json={"canonical_name": "Machine Learning", "aliases": ["ML"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["canonical_name"] == "Machine Learning"
        assert data["aliases"] == ["ML"]

    def test_delete(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Temp Concept"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        resp = registry_client.delete(f"/api/registry/concepts/{entry_id}")
        assert resp.status_code == 200

        resp = registry_client.get(f"/api/registry/concepts/{entry_id}")
        assert resp.status_code == 404

    def test_duplicate_rejected(self, registry_client):
        registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Neural Network", "concept_type": "Technology"},
        )
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "neural network", "concept_type": "Technology"},
        )
        assert resp.status_code == 409

    def test_empty_name_rejected(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": ""},
        )
        assert resp.status_code == 400

    def test_filter_by_type(self, registry_client):
        registry_client.post("/api/registry/concepts", json={"canonical_name": "Python", "concept_type": "Language"})
        registry_client.post("/api/registry/concepts", json={"canonical_name": "Docker", "concept_type": "Tool"})

        resp = registry_client.get("/api/registry/concepts?concept_type=Language")
        entries = resp.get_json()["data"]["entries"]
        assert len(entries) == 1
        assert entries[0]["canonical_name"] == "Python"


# ---------------------------------------------------------------------------
# Link / unlink tests
# ---------------------------------------------------------------------------


class TestRegistryLinks:
    def test_link_and_unlink(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Attention Mechanism", "concept_type": "Technology"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        # Link
        resp = registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": "proj_abc", "concept_key": "Technology:attention mechanism", "project_name": "NLP Paper"},
        )
        assert resp.status_code == 200
        links = resp.get_json()["data"]["source_links"]
        assert len(links) == 1
        assert links[0]["project_id"] == "proj_abc"

        # Duplicate link is idempotent
        resp = registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": "proj_abc", "concept_key": "Technology:attention mechanism"},
        )
        assert len(resp.get_json()["data"]["source_links"]) == 1

        # Unlink
        resp = registry_client.delete(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": "proj_abc", "concept_key": "Technology:attention mechanism"},
        )
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]["source_links"]) == 0

    def test_link_not_found(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts/nonexistent/links",
            json={"project_id": "p1", "concept_key": "k1"},
        )
        assert resp.status_code == 404

    def test_link_missing_fields(self, registry_client):
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Test"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        resp = registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": "p1"},  # missing concept_key
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestRegistrySearch:
    def test_search_by_canonical_name(self, registry_client):
        registry_client.post("/api/registry/concepts", json={"canonical_name": "Transformer", "concept_type": "Technology"})
        registry_client.post("/api/registry/concepts", json={"canonical_name": "Transfer Learning", "concept_type": "Technology"})

        resp = registry_client.get("/api/registry/concepts/search?q=transformer")
        assert resp.status_code == 200
        results = resp.get_json()["data"]["results"]
        assert len(results) >= 1
        assert results[0]["canonical_name"] == "Transformer"

    def test_search_by_alias(self, registry_client):
        registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Large Language Model", "aliases": ["LLM", "大语言模型"]},
        )

        resp = registry_client.get("/api/registry/concepts/search?q=LLM")
        results = resp.get_json()["data"]["results"]
        assert len(results) == 1
        assert results[0]["canonical_name"] == "Large Language Model"

    def test_search_empty_query(self, registry_client):
        resp = registry_client.get("/api/registry/concepts/search?q=")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Suggest from project
# ---------------------------------------------------------------------------


class TestSuggestFromProject:
    def test_suggest_new_candidates(self, registry_client):
        project_id = _create_project_with_concepts({
            "Technology:machine learning": "Machine Learning",
            "Technology:deep learning": "Deep Learning",
        })

        resp = registry_client.post(f"/api/registry/suggest-from-project/{project_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total_accepted"] == 2
        assert len(data["new_candidates"]) == 2
        assert len(data["existing_matches"]) == 0

    def test_suggest_with_existing_match(self, registry_client):
        # Pre-create registry entry
        registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Machine Learning", "concept_type": "Technology"},
        )

        project_id = _create_project_with_concepts({
            "Technology:machine learning": "Machine Learning",
            "Technology:deep learning": "Deep Learning",
        })

        resp = registry_client.post(f"/api/registry/suggest-from-project/{project_id}")
        data = resp.get_json()["data"]
        assert len(data["existing_matches"]) == 1
        assert data["existing_matches"][0]["matched_canonical_name"] == "Machine Learning"
        assert len(data["new_candidates"]) == 1

    def test_suggest_with_cross_type_possible_match(self, registry_client):
        registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "JSON output", "concept_type": "Technology"},
        )

        project_id = _create_project_with_concepts({
            "Mechanism:structured json response": "JSON output",
        })

        resp = registry_client.post(f"/api/registry/suggest-from-project/{project_id}")
        data = resp.get_json()["data"]
        assert len(data["existing_matches"]) == 0
        assert len(data["cross_type_matches"]) == 1
        assert data["cross_type_matches"][0]["matched_canonical_name"] == "JSON output"
        assert data["cross_type_matches"][0]["matched_concept_type"] == "Technology"
        assert len(data["new_candidates"]) == 0

    def test_suggest_project_not_found(self, registry_client):
        resp = registry_client.post("/api/registry/suggest-from-project/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project alignment
# ---------------------------------------------------------------------------


class TestProjectAlignment:
    def test_alignment_unlinked(self, registry_client):
        project_id = _create_project_with_concepts({
            "Technology:machine learning": "Machine Learning",
        })

        resp = registry_client.get(f"/api/registry/projects/{project_id}/alignment")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["summary"]["unlinked"] == 1
        assert data["summary"]["total"] == 1
        assert data["alignments"][0]["status"] == "unlinked"

    def test_alignment_linked(self, registry_client):
        # Create registry entry
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Machine Learning", "concept_type": "Technology"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        project_id = _create_project_with_concepts({
            "Technology:machine learning": "Machine Learning",
        })

        # Link the concept
        registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": project_id, "concept_key": "Technology:machine learning"},
        )

        resp = registry_client.get(f"/api/registry/projects/{project_id}/alignment")
        data = resp.get_json()["data"]
        assert data["summary"]["linked"] == 1
        assert data["summary"]["total"] == 1
        assert data["alignments"][0]["status"] == "linked"
        assert data["alignments"][0]["registry_entry_id"] == entry_id

    def test_alignment_suggested(self, registry_client):
        # Create registry entry
        registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Machine Learning", "concept_type": "Technology"},
        )

        project_id = _create_project_with_concepts({
            "Technology:machine learning": "Machine Learning",
        })

        # Not linked, but name matches → suggested
        resp = registry_client.get(f"/api/registry/projects/{project_id}/alignment")
        data = resp.get_json()["data"]
        assert data["summary"]["suggested"] == 1
        assert data["alignments"][0]["status"] == "suggested"

    def test_alignment_project_not_found(self, registry_client):
        resp = registry_client.get("/api/registry/projects/nonexistent/alignment")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cross-project linking scenario
# ---------------------------------------------------------------------------


class TestCrossProjectScenario:
    def test_two_projects_link_to_same_entry(self, registry_client):
        """Two projects both have ML concepts → link both to the same canonical."""
        resp = registry_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Machine Learning", "concept_type": "Technology", "aliases": ["ML"]},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        pid_a = _create_project_with_concepts({"Technology:machine learning": "Machine Learning"})
        pid_b = _create_project_with_concepts({"Technology:ml": "ML"})

        registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": pid_a, "concept_key": "Technology:machine learning", "project_name": "Project A"},
        )
        registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": pid_b, "concept_key": "Technology:ml", "project_name": "Project B"},
        )

        resp = registry_client.get(f"/api/registry/concepts/{entry_id}")
        entry = resp.get_json()["data"]
        assert len(entry["source_links"]) == 2

        # Both project alignments show linked
        for pid in (pid_a, pid_b):
            resp = registry_client.get(f"/api/registry/projects/{pid}/alignment")
            assert resp.get_json()["data"]["summary"]["linked"] == 1
