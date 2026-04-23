"""Stage K: Evolution log API tests."""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.registry import evolution_log as evo_mod
from app.services.registry import global_concept_registry as concept_reg_mod
from app.services.registry import global_theme_registry as theme_reg_mod


@pytest.fixture()
def evo_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    monkeypatch.setattr(evo_mod, "_log_path", lambda: str(projects_dir / "evolution_log.json"))
    monkeypatch.setattr(concept_reg_mod, "_registry_path", lambda: str(projects_dir / "concept_registry.json"))
    monkeypatch.setattr(theme_reg_mod, "_themes_path", lambda: str(projects_dir / "global_themes.json"))

    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    return app.test_client()


# ---------------------------------------------------------------------------
# Direct emit + query
# ---------------------------------------------------------------------------


class TestEvolutionLogDirect:
    def test_emit_and_read_global_feed(self, evo_client):
        """Manually emitting events shows up in the global feed."""
        evo_mod.emit_event(
            event_type="created", entity_type="concept_entry",
            entity_id="canon_001", entity_name="Machine Learning",
        )
        evo_mod.emit_event(
            event_type="linked", entity_type="concept_entry",
            entity_id="canon_001", entity_name="Machine Learning",
            project_id="proj_a", details={"concept_key": "Tech:ml"},
        )

        resp = evo_client.get("/api/registry/evolution/feed")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total"] == 2
        # Newest first
        assert data["events"][0]["event_type"] == "linked"
        assert data["events"][1]["event_type"] == "created"

    def test_entity_timeline(self, evo_client):
        evo_mod.emit_event(
            event_type="created", entity_type="concept_entry",
            entity_id="canon_x", entity_name="X",
        )
        evo_mod.emit_event(
            event_type="updated", entity_type="concept_entry",
            entity_id="canon_x", entity_name="X Updated",
        )
        evo_mod.emit_event(
            event_type="created", entity_type="concept_entry",
            entity_id="canon_y", entity_name="Y",
        )

        resp = evo_client.get("/api/registry/evolution/concepts/canon_x/timeline")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total"] == 2
        assert data["entity_id"] == "canon_x"

    def test_project_feed(self, evo_client):
        evo_mod.emit_event(
            event_type="linked", entity_type="concept_entry",
            entity_id="canon_1", project_id="proj_a",
        )
        evo_mod.emit_event(
            event_type="linked", entity_type="concept_entry",
            entity_id="canon_2", project_id="proj_b",
        )

        resp = evo_client.get("/api/registry/evolution/projects/proj_a/feed")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total"] == 1
        assert data["events"][0]["project_id"] == "proj_a"

    def test_global_feed_filter_by_entity_type(self, evo_client):
        evo_mod.emit_event(event_type="created", entity_type="concept_entry", entity_id="c1")
        evo_mod.emit_event(event_type="created", entity_type="global_theme", entity_id="t1")

        resp = evo_client.get("/api/registry/evolution/feed?entity_type=global_theme")
        data = resp.get_json()["data"]
        assert data["total"] == 1
        assert data["events"][0]["entity_type"] == "global_theme"

    def test_global_feed_pagination(self, evo_client):
        for i in range(5):
            evo_mod.emit_event(event_type="created", entity_type="concept_entry", entity_id=f"c{i}")

        resp = evo_client.get("/api/registry/evolution/feed?limit=2&offset=0")
        data = resp.get_json()["data"]
        assert len(data["events"]) == 2
        assert data["total"] == 5

        resp = evo_client.get("/api/registry/evolution/feed?limit=2&offset=2")
        data = resp.get_json()["data"]
        assert len(data["events"]) == 2

    def test_theme_timeline(self, evo_client):
        evo_mod.emit_event(
            event_type="created", entity_type="global_theme",
            entity_id="gtheme_1", entity_name="AI Safety",
        )
        resp = evo_client.get("/api/registry/evolution/themes/gtheme_1/timeline")
        data = resp.get_json()["data"]
        assert data["total"] == 1
        assert data["entity_type"] == "global_theme"


# ---------------------------------------------------------------------------
# Integration: concept registry emits events automatically
# ---------------------------------------------------------------------------


class TestConceptRegistryEmitsEvents:
    def test_create_concept_emits_event(self, evo_client):
        resp = evo_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Transformer", "concept_type": "Technology"},
        )
        assert resp.status_code == 201
        entry_id = resp.get_json()["data"]["entry_id"]

        resp = evo_client.get(f"/api/registry/evolution/concepts/{entry_id}/timeline")
        data = resp.get_json()["data"]
        assert data["total"] >= 1
        assert data["events"][0]["event_type"] == "created"
        assert data["events"][0]["entity_name"] == "Transformer"

    def test_update_concept_emits_event(self, evo_client):
        resp = evo_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "GPT"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        evo_client.put(
            f"/api/registry/concepts/{entry_id}",
            json={"canonical_name": "GPT-4"},
        )

        resp = evo_client.get(f"/api/registry/evolution/concepts/{entry_id}/timeline")
        events = resp.get_json()["data"]["events"]
        event_types = [e["event_type"] for e in events]
        assert "created" in event_types
        assert "updated" in event_types

    def test_link_concept_emits_event(self, evo_client):
        resp = evo_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "BERT"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        evo_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={"project_id": "proj_nlp", "concept_key": "Tech:bert"},
        )

        resp = evo_client.get("/api/registry/evolution/projects/proj_nlp/feed")
        data = resp.get_json()["data"]
        assert data["total"] >= 1
        assert any(e["event_type"] == "linked" for e in data["events"])

    def test_delete_concept_emits_event(self, evo_client):
        resp = evo_client.post(
            "/api/registry/concepts",
            json={"canonical_name": "Temp"},
        )
        entry_id = resp.get_json()["data"]["entry_id"]

        evo_client.delete(f"/api/registry/concepts/{entry_id}")

        resp = evo_client.get(f"/api/registry/evolution/concepts/{entry_id}/timeline")
        events = resp.get_json()["data"]["events"]
        assert any(e["event_type"] == "deleted" for e in events)


# ---------------------------------------------------------------------------
# Integration: theme registry emits events automatically
# ---------------------------------------------------------------------------


class TestThemeRegistryEmitsEvents:
    def test_create_theme_emits_event(self, evo_client):
        resp = evo_client.post(
            "/api/registry/themes",
            json={"name": "AI Ethics", "domain": "tech"},
        )
        assert resp.status_code == 201
        theme_id = resp.get_json()["data"]["theme_id"]

        resp = evo_client.get(f"/api/registry/evolution/themes/{theme_id}/timeline")
        data = resp.get_json()["data"]
        assert data["total"] >= 1
        assert data["events"][0]["event_type"] == "created"

    def test_link_cluster_emits_event(self, evo_client):
        resp = evo_client.post("/api/registry/themes", json={"name": "Safety Theme", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        evo_client.post(
            f"/api/registry/themes/{theme_id}/clusters:link",
            json={"project_id": "proj_safe", "cluster_id": "tc_1", "cluster_name": "Safety Cluster"},
        )

        resp = evo_client.get("/api/registry/evolution/projects/proj_safe/feed")
        data = resp.get_json()["data"]
        assert any(e["event_type"] == "cluster_linked" for e in data["events"])
