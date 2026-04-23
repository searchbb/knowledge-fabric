"""E2E integration tests for the global registry system.

Tests 1-20 from GPT-consulted test plan, covering cross-page flows,
CRUD with verification, suggest+link workflows, batch operations,
error/empty states. All use Flask test client against real service logic.
"""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp, concept_bp, theme_bp
from app.config import Config
from app.models.project import ProjectManager, ProjectStatus
from app.services.registry import global_concept_registry as concept_reg
from app.services.registry import global_theme_registry as theme_reg
from app.services.registry import evolution_log as evo_mod
from app.services.registry import review_task_service as review_mod
from app.services.workspace import concept_view_service as concept_view_module


@pytest.fixture()
def e2e(tmp_path, monkeypatch):
    """Full E2E client with all blueprints, isolated storage."""
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    monkeypatch.setattr(concept_reg, "_registry_path", lambda: str(projects_dir / "concept_registry.json"))
    monkeypatch.setattr(theme_reg, "_themes_path", lambda: str(projects_dir / "global_themes.json"))
    monkeypatch.setattr(evo_mod, "_log_path", lambda: str(projects_dir / "evolution_log.json"))
    monkeypatch.setattr(review_mod, "_tasks_path", lambda: str(projects_dir / "review_tasks.json"))

    monkeypatch.setattr(
        concept_view_module, "load_graph_data",
        lambda graph_id: {
            "graph_id": graph_id, "node_count": 2, "edge_count": 1,
            "nodes": [
                {"uuid": "n1", "name": "Machine Learning", "labels": ["Technology"], "summary": "ML"},
                {"uuid": "n2", "name": "Deep Learning", "labels": ["Technology"], "summary": "DL"},
            ],
            "edges": [{"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2", "name": "CONTAINS"}],
        },
    )

    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    app.register_blueprint(concept_bp, url_prefix="/api/concept")
    app.register_blueprint(theme_bp, url_prefix="/api/theme")
    return app.test_client()


def _seed_project(name="Test Project", accepted_keys=None, clusters=None):
    project = ProjectManager.create_project(name=name)
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "test_graph"
    if accepted_keys:
        items = {}
        for key, canonical in accepted_keys.items():
            items[key] = {"status": "accepted", "canonical_name": canonical, "note": "", "updated_at": "2026-04-09T00:00:00"}
        project.concept_decisions = {"version": 1, "items": items}
    project.theme_clusters = clusters or []
    ProjectManager.save_project(project)
    return project


# ===================================================================
# Test 1-2: Overview + navigation
# ===================================================================

class TestOverviewFlows:
    def test_01_overview_loads_with_projects(self, e2e):
        """Test 1: Overview loads with populated project data."""
        _seed_project("Alpha", {"Tech:ml": "ML"})
        _seed_project("Beta", {"Tech:dl": "DL", "Tech:nn": "NN"})

        resp = e2e.get("/api/registry/overview")
        data = resp.get_json()["data"]
        assert data["project_count"] == 2
        names = {p["project_name"] for p in data["projects"]}
        assert "Alpha" in names and "Beta" in names

    def test_02_overview_to_registry_roundtrip(self, e2e):
        """Test 2: Overview → registry → back works without data loss."""
        _seed_project("Gamma")
        e2e.post("/api/registry/concepts", json={"canonical_name": "Test Concept"})

        overview = e2e.get("/api/registry/overview").get_json()["data"]
        assert overview["global_stats"]["registry_entries"] == 1

        registry = e2e.get("/api/registry/concepts").get_json()["data"]
        assert registry["total"] == 1

        overview2 = e2e.get("/api/registry/overview").get_json()["data"]
        assert overview2["global_stats"]["registry_entries"] == 1


# ===================================================================
# Test 3-7: Concepts CRUD
# ===================================================================

class TestConceptsCRUD:
    def test_04_create_and_verify(self, e2e):
        """Test 4: Create concept and verify in list and detail."""
        resp = e2e.post("/api/registry/concepts", json={
            "canonical_name": "Knowledge Graph", "concept_type": "Technology",
            "aliases": ["KG", "知识图谱"], "description": "Graph-based knowledge representation",
        })
        assert resp.status_code == 201
        entry_id = resp.get_json()["data"]["entry_id"]

        # Verify in list
        listing = e2e.get("/api/registry/concepts").get_json()["data"]
        assert any(e["entry_id"] == entry_id for e in listing["entries"])

        # Verify in detail
        detail = e2e.get(f"/api/registry/concepts/{entry_id}").get_json()["data"]
        assert detail["canonical_name"] == "Knowledge Graph"
        assert "KG" in detail["aliases"]

        # Verify searchable
        search = e2e.get("/api/registry/concepts/search?q=knowledge").get_json()["data"]
        assert any(r["entry_id"] == entry_id for r in search["results"])

        # Also searchable by alias
        search2 = e2e.get("/api/registry/concepts/search?q=知识图谱").get_json()["data"]
        assert any(r["entry_id"] == entry_id for r in search2["results"])

    def test_05_edit_and_verify_persist(self, e2e):
        """Test 5: Edit concept and verify persistence."""
        resp = e2e.post("/api/registry/concepts", json={"canonical_name": "NLP"})
        entry_id = resp.get_json()["data"]["entry_id"]

        e2e.put(f"/api/registry/concepts/{entry_id}", json={
            "description": "Natural Language Processing",
            "aliases": ["自然语言处理"],
        })

        detail = e2e.get(f"/api/registry/concepts/{entry_id}").get_json()["data"]
        assert detail["description"] == "Natural Language Processing"
        assert "自然语言处理" in detail["aliases"]

    def test_06_delete_and_verify_removal(self, e2e):
        """Test 6: Delete concept and verify not in list or search."""
        resp = e2e.post("/api/registry/concepts", json={"canonical_name": "Temp Concept"})
        entry_id = resp.get_json()["data"]["entry_id"]

        e2e.delete(f"/api/registry/concepts/{entry_id}")

        assert e2e.get(f"/api/registry/concepts/{entry_id}").status_code == 404
        search = e2e.get("/api/registry/concepts/search?q=temp").get_json()["data"]
        assert not any(r["entry_id"] == entry_id for r in search["results"])

    def test_07_search_by_canonical_and_alias(self, e2e):
        """Test 7: Search matches both canonical name and alias."""
        e2e.post("/api/registry/concepts", json={
            "canonical_name": "Order Allocation", "aliases": ["allocation rule"],
        })

        r1 = e2e.get("/api/registry/concepts/search?q=order allocation").get_json()["data"]
        r2 = e2e.get("/api/registry/concepts/search?q=allocation rule").get_json()["data"]
        assert len(r1["results"]) >= 1
        assert len(r2["results"]) >= 1
        assert r1["results"][0]["canonical_name"] == r2["results"][0]["canonical_name"]


# ===================================================================
# Test 8-10: Suggest + link/unlink workflows
# ===================================================================

class TestSuggestAndLink:
    def test_08_suggest_and_quick_register(self, e2e):
        """Test 8: Suggest from project → quick register → concept appears."""
        pid = _seed_project("ML Paper", {"Technology:machine learning": "Machine Learning"}).project_id

        suggest = e2e.post(f"/api/registry/suggest-from-project/{pid}").get_json()["data"]
        assert len(suggest["new_candidates"]) >= 1
        candidate = suggest["new_candidates"][0]

        # Quick register
        resp = e2e.post("/api/registry/concepts", json={
            "canonical_name": candidate["display_name"],
            "concept_type": candidate["concept_type"],
        })
        entry_id = resp.get_json()["data"]["entry_id"]

        # Link it
        e2e.post(f"/api/registry/concepts/{entry_id}/links", json={
            "project_id": pid, "concept_key": candidate["concept_key"],
        })

        # Verify: re-suggest should show it as already_linked
        suggest2 = e2e.post(f"/api/registry/suggest-from-project/{pid}").get_json()["data"]
        linked_keys = [a["concept_key"] for a in suggest2["already_linked"]]
        assert candidate["concept_key"] in linked_keys

    def test_09_suggest_existing_match_quick_link(self, e2e):
        """Test 9: Suggest finds existing match → quick link."""
        e2e.post("/api/registry/concepts", json={
            "canonical_name": "Deep Learning", "concept_type": "Technology",
        })
        pid = _seed_project("DL Paper", {"Technology:deep learning": "Deep Learning"}).project_id

        suggest = e2e.post(f"/api/registry/suggest-from-project/{pid}").get_json()["data"]
        assert len(suggest["existing_matches"]) >= 1
        match = suggest["existing_matches"][0]

        e2e.post(f"/api/registry/concepts/{match['matched_entry_id']}/links", json={
            "project_id": pid, "concept_key": match["concept_key"],
        })

        detail = e2e.get(f"/api/registry/concepts/{match['matched_entry_id']}").get_json()["data"]
        assert any(l["project_id"] == pid for l in detail["source_links"])

    def test_10_unlink_and_verify(self, e2e):
        """Test 10: Unlink project concept and verify removal."""
        resp = e2e.post("/api/registry/concepts", json={"canonical_name": "Test Link"})
        entry_id = resp.get_json()["data"]["entry_id"]

        e2e.post(f"/api/registry/concepts/{entry_id}/links", json={
            "project_id": "proj_x", "concept_key": "Tech:test",
        })
        assert len(e2e.get(f"/api/registry/concepts/{entry_id}").get_json()["data"]["source_links"]) == 1

        e2e.delete(f"/api/registry/concepts/{entry_id}/links", json={
            "project_id": "proj_x", "concept_key": "Tech:test",
        })
        assert len(e2e.get(f"/api/registry/concepts/{entry_id}").get_json()["data"]["source_links"]) == 0


# ===================================================================
# Test 11-13: Themes
# ===================================================================

class TestThemeFlows:
    def test_11_create_theme_and_attach_concepts(self, e2e):
        """Test 11: Create theme + attach concepts → persist."""
        c1 = e2e.post("/api/registry/concepts", json={"canonical_name": "ML"}).get_json()["data"]["entry_id"]
        c2 = e2e.post("/api/registry/concepts", json={"canonical_name": "DL"}).get_json()["data"]["entry_id"]

        resp = e2e.post("/api/registry/themes", json={"name": "AI Core", "description": "Core AI concepts", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        e2e.post(f"/api/registry/themes/{theme_id}/concepts:attach", json={"concept_entry_ids": [c1, c2]})

        detail = e2e.get(f"/api/registry/themes/{theme_id}").get_json()["data"]
        assert sorted(detail["concept_entry_ids"]) == sorted([c1, c2])

    def test_12_link_project_cluster_to_theme(self, e2e):
        """Test 12: Link project cluster to global theme."""
        resp = e2e.post("/api/registry/themes", json={"name": "Safety", "domain": "tech"})
        theme_id = resp.get_json()["data"]["theme_id"]

        e2e.post(f"/api/registry/themes/{theme_id}/clusters:link", json={
            "project_id": "proj_safe", "cluster_id": "tc_01", "cluster_name": "Safety Cluster",
        })

        detail = e2e.get(f"/api/registry/themes/{theme_id}").get_json()["data"]
        assert len(detail["source_project_clusters"]) == 1
        assert detail["source_project_clusters"][0]["cluster_name"] == "Safety Cluster"

    def test_13_empty_themes_then_first_create(self, e2e):
        """Test 13: Empty theme state → create first → list updates."""
        listing = e2e.get("/api/registry/themes").get_json()["data"]
        assert listing["total"] == 0

        e2e.post("/api/registry/themes", json={"name": "First Theme", "domain": "tech"})

        listing = e2e.get("/api/registry/themes").get_json()["data"]
        assert listing["total"] == 1


# ===================================================================
# Test 14-15: Evolution
# ===================================================================

class TestEvolutionFlows:
    def test_14_filter_by_entity_and_event_type(self, e2e):
        """Test 14: Evolution feed filters by entity_type and event_type."""
        e2e.post("/api/registry/concepts", json={"canonical_name": "A"})
        e2e.post("/api/registry/themes", json={"name": "B"})

        # Filter concept_entry only
        resp = e2e.get("/api/registry/evolution/feed?entity_type=concept_entry")
        events = resp.get_json()["data"]["events"]
        assert all(e["entity_type"] == "concept_entry" for e in events)
        assert len(events) >= 1

        # Filter by created only
        resp = e2e.get("/api/registry/evolution/feed?event_type=created")
        events = resp.get_json()["data"]["events"]
        assert all(e["event_type"] == "created" for e in events)
        assert len(events) >= 2  # both concept and theme

    def test_15_pagination_preserves_filter(self, e2e):
        """Test 15: Pagination works with filters applied."""
        for i in range(8):
            e2e.post("/api/registry/concepts", json={"canonical_name": f"Concept_{i}"})

        page1 = e2e.get("/api/registry/evolution/feed?entity_type=concept_entry&limit=3&offset=0").get_json()["data"]
        page2 = e2e.get("/api/registry/evolution/feed?entity_type=concept_entry&limit=3&offset=3").get_json()["data"]

        assert len(page1["events"]) == 3
        assert len(page2["events"]) == 3
        # No overlap
        ids1 = {e["event_id"] for e in page1["events"]}
        ids2 = {e["event_id"] for e in page2["events"]}
        assert ids1.isdisjoint(ids2)


# ===================================================================
# Test 16-18: Review
# ===================================================================

class TestReviewFlows:
    def test_16_full_task_lifecycle(self, e2e):
        """Test 16: Create → claim → resolve → reopen."""
        resp = e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": "c1",
            "entity_name": "ML", "action_required": "confirm_link",
        })
        task_id = resp.get_json()["data"]["task_id"]
        assert resp.get_json()["data"]["status"] == "open"

        # Claim
        resp = e2e.put(f"/api/registry/review/tasks/{task_id}", json={"status": "claimed"})
        assert resp.get_json()["data"]["status"] == "claimed"

        # Resolve
        resp = e2e.put(f"/api/registry/review/tasks/{task_id}", json={
            "status": "resolved", "resolution": "approved", "note": "LGTM",
        })
        data = resp.get_json()["data"]
        assert data["status"] == "resolved"
        assert data["note"] == "LGTM"

        # Reopen
        resp = e2e.put(f"/api/registry/review/tasks/{task_id}", json={"status": "reopened"})
        assert resp.get_json()["data"]["status"] == "reopened"

        # Stats reflect final state
        stats = e2e.get("/api/registry/review/tasks/stats").get_json()["data"]
        assert stats["by_status"]["reopened"] == 1

    def test_17_batch_resolve_with_priority(self, e2e):
        """Test 17: Batch resolve high-priority tasks."""
        t1 = e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": "h1", "priority": "high",
        }).get_json()["data"]["task_id"]
        t2 = e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": "h2", "priority": "high",
        }).get_json()["data"]["task_id"]
        t3 = e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": "l1", "priority": "low",
        }).get_json()["data"]["task_id"]

        resp = e2e.post("/api/registry/review/tasks/batch-resolve", json={
            "task_ids": [t1, t2], "resolution": "approved", "note": "batch ok",
        })
        result = resp.get_json()["data"]
        assert result["resolved_count"] == 2

        # t3 untouched
        assert e2e.get(f"/api/registry/review/tasks/{t3}").get_json()["data"]["status"] == "open"

    def test_18_invalid_transition_rejected(self, e2e):
        """Test 18: Invalid state transition returns 409."""
        resp = e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": "x",
        })
        task_id = resp.get_json()["data"]["task_id"]

        # open → reopened is invalid
        resp = e2e.put(f"/api/registry/review/tasks/{task_id}", json={"status": "reopened"})
        assert resp.status_code == 409


# ===================================================================
# Test 19-20: Cross-cutting
# ===================================================================

class TestCrossCutting:
    def test_19_evolution_captures_all_mutations(self, e2e):
        """Test 19: All CRUD/link ops generate evolution events."""
        # Concept create + link
        c = e2e.post("/api/registry/concepts", json={"canonical_name": "Evo Test"}).get_json()["data"]
        e2e.post(f"/api/registry/concepts/{c['entry_id']}/links", json={
            "project_id": "proj_evo", "concept_key": "Tech:evo",
        })
        # Theme create + cluster link
        t = e2e.post("/api/registry/themes", json={"name": "Evo Theme"}).get_json()["data"]
        e2e.post(f"/api/registry/themes/{t['theme_id']}/clusters:link", json={
            "project_id": "proj_evo", "cluster_id": "tc_1",
        })
        # Review task create + resolve
        r = e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": c["entry_id"],
        }).get_json()["data"]
        e2e.put(f"/api/registry/review/tasks/{r['task_id']}", json={"status": "resolved", "resolution": "approved"})

        feed = e2e.get("/api/registry/evolution/feed?limit=100").get_json()["data"]
        types = {e["event_type"] for e in feed["events"]}
        assert "created" in types
        assert "linked" in types
        assert "cluster_linked" in types
        assert "review_task_created" in types
        assert "review_task_resolved" in types

    def test_20_export_contains_all_stores(self, e2e):
        """Test 20: Export endpoint dumps all 4 stores with data."""
        e2e.post("/api/registry/concepts", json={"canonical_name": "Export Test"})
        e2e.post("/api/registry/themes", json={"name": "Export Theme"})
        e2e.post("/api/registry/review/tasks", json={
            "entity_type": "concept_entry", "entity_id": "x",
        })

        export = e2e.get("/api/registry/export").get_json()["data"]
        assert export["version"] == 1
        assert len(export["concept_registry"].get("entries", {})) >= 1
        assert len(export["global_themes"].get("themes", {})) >= 1
        assert len(export["evolution_log"].get("events", [])) >= 3
        assert len(export["review_tasks"].get("tasks", {})) >= 1
