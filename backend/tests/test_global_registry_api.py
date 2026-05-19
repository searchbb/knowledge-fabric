"""Stage H: Global concept registry API tests."""

from __future__ import annotations

from flask import Flask
import pytest

from app.api import registry_bp, concept_bp
from app.api.routes.kfc_material_graphs import kfc_assets_bp
from app.models.project import ProjectManager, ProjectStatus
from app.services.kfc_material_graph_store import KfcMaterialGraphStore
from app.services.registry import global_concept_registry as registry_mod
from app.services.registry import source_evidence_resolver as evidence_resolver
from app.services.workspace import concept_view_service as concept_view_module


@pytest.fixture()
def registry_client(tmp_path, monkeypatch):
    """Flask test client with isolated registry storage."""
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(projects_dir))
    # Point registry storage to the same tmp dir
    monkeypatch.setattr(registry_mod, "_registry_path", lambda: str(projects_dir / "concept_registry.json"))
    monkeypatch.setattr(KfcMaterialGraphStore, "CONCEPT_REGISTRY_PATH", projects_dir / "concept_registry.json")
    monkeypatch.setattr(KfcMaterialGraphStore, "MATERIAL_GRAPH_DIR", tmp_path / "kfc_material_graphs")
    monkeypatch.setattr(KfcMaterialGraphStore, "GRAPHIFICATION_REQUEST_DIR", tmp_path / "kfc_graphification_requests")
    monkeypatch.setattr(KfcMaterialGraphStore, "MATERIAL_SLICE_DIR", tmp_path / "material_slices")
    monkeypatch.setattr(KfcMaterialGraphStore, "KFC_RELATION_DIR", tmp_path / "kfc_asset_relations")

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
    app.register_blueprint(kfc_assets_bp)
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


def _seed_materialized_kfc_concept() -> str:
    """Seed a registry entry plus material slice and KFC relations."""
    concept_id = "canon_agent_runtime"
    registry_mod._save_registry(
        {
            "version": 1,
            "entries": {
                concept_id: {
                    "entry_id": concept_id,
                    "concept_id": concept_id,
                    "canonical_name": "Agent Runtime",
                    "label": "Agent Runtime",
                    "concept_type": "Concept",
                    "asset_type": "concept",
                    "aliases": [],
                    "description": "Mavis article source text",
                    "definition": "Mavis article source text",
                    "source_links": [],
                    "source_article_id": "src_mavis",
                    "source_article_title": "Agent会协作还会决策？我对Mavis的技术实现很好奇",
                    "source_markdown_path": "/tmp/mavis.md",
                    "source_quote": "Mavis uses an Agent Runtime.",
                    "source_context": "Agent Runtime coordinates Leader, Worker, and Verifier.",
                    "source_material_slice_id": "ms_mavis",
                    "source_lead_id": "lp_mavis",
                    "linked_topic_cluster_ids": ["tc_agent_harness"],
                    "linked_research_project_ids": ["rp_strategy"],
                    "related_existing_concepts": [{"concept_id": "canon_agent", "label": "Agent", "score": 0.74}],
                    "created_at": "2026-05-18T12:03:04",
                    "updated_at": "2026-05-18T12:03:04",
                },
                "canon_agent": {
                    "entry_id": "canon_agent",
                    "canonical_name": "Agent",
                    "concept_type": "Concept",
                    "aliases": [],
                    "description": "",
                    "source_links": [],
                    "created_at": "2026-05-01T00:00:00",
                    "updated_at": "2026-05-01T00:00:00",
                },
            },
        }
    )
    KfcMaterialGraphStore.MATERIAL_SLICE_DIR.mkdir(parents=True, exist_ok=True)
    (KfcMaterialGraphStore.MATERIAL_SLICE_DIR / "ms_mavis.json").write_text(
        """
{
  "slice_id": "ms_mavis",
  "title": "Agent Runtime",
  "display_title": "Agent Runtime",
  "source_article_id": "src_mavis",
  "source_title": "Agent会协作还会决策？我对Mavis的技术实现很好奇",
  "source_markdown_path": "/tmp/mavis.md",
  "source_quote": "Mavis uses an Agent Runtime.",
  "source_context": "Agent Runtime coordinates Leader, Worker, and Verifier."
}
""".strip(),
        encoding="utf-8",
    )
    KfcMaterialGraphStore.KFC_RELATION_DIR.mkdir(parents=True, exist_ok=True)
    (KfcMaterialGraphStore.KFC_RELATION_DIR / "rel_mavis_agent.json").write_text(
        """
{
  "relation_id": "rel_mavis_agent",
  "source_type": "concept_registry_entry",
  "source_id": "canon_agent_runtime",
  "target_type": "concept_registry_entry",
  "target_id": "canon_agent",
  "relation_type": "related_to",
  "source_article_id": "src_mavis",
  "cluster_id": "tc_agent_harness",
  "project_id": "rp_strategy"
}
""".strip(),
        encoding="utf-8",
    )
    return concept_id


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

    def test_get_single_enriches_source_evidence_refs_from_project_graph(self, registry_client, monkeypatch):
        project = ProjectManager.create_project(name="FDE source article")
        project.status = ProjectStatus.GRAPH_COMPLETED
        project.graph_id = "graph_fde"
        ProjectManager.save_project(project)
        ProjectManager.save_extracted_text(
            project.project_id,
            "\n".join(
                [
                    "OpenAI 和 Anthropic 都在重估企业服务。",
                    "两家方向不同，但支撑它们的核心组织形式，都是 Palantir 推广的 FDE 模式。",
                    "FDE 直接驻场，理解客户的数据、流程、痛点，然后把通用模型打磨成能跑业务的具体方案。",
                ]
            ),
        )
        monkeypatch.setattr(
            evidence_resolver,
            "load_graph_data",
            lambda graph_id: {
                "graph_id": graph_id,
                "nodes": [
                    {
                        "uuid": "node_fde",
                        "name": "FDE 模式",
                        "labels": ["Method"],
                        "summary": "由前沿部署工程师驻场填补产品与需求差距的组织方法论。",
                    }
                ],
                "edges": [],
            },
        )

        resp = registry_client.post("/api/registry/concepts", json={"canonical_name": "FDE 模式", "concept_type": "Method"})
        entry_id = resp.get_json()["data"]["entry_id"]
        registry_client.post(
            f"/api/registry/concepts/{entry_id}/links",
            json={
                "project_id": project.project_id,
                "project_name": project.name,
                "concept_key": "Method:fde 模式",
            },
        )

        resp = registry_client.get(f"/api/registry/concepts/{entry_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["source_quote"].startswith("两家方向不同")
        assert "FDE 直接驻场" in data["source_context"]
        assert data["source_material_slice_id"] == "node_fde"
        assert data["source_evidence_refs"][0]["source_node_uuid"] == "node_fde"
        assert data["source_evidence_refs"][0]["source_text"].startswith("由前沿部署工程师")

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
# KFC material graph snapshots
# ---------------------------------------------------------------------------


class TestKfcMaterialGraph:
    def test_snapshot_api_creates_deterministic_material_graph_without_project(self, registry_client):
        concept_id = _seed_materialized_kfc_concept()

        resp = registry_client.post(f"/api/registry/concepts/{concept_id}/graph/snapshot", json={"actor": "test"})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["created"] is True
        assert data["graph_status"] == "snapshot_available"
        assert data["node_count"] >= 5
        assert data["edge_count"] >= 5
        assert data["cross_article_link_count"] >= 1
        graph = data["graph"]
        assert graph["provenance"]["no_model_execution"] is True
        assert graph["provenance"]["creation_mode"] == "deterministic"
        node_types = {node["node_type"] for node in graph["nodes"]}
        assert {"concept_registry_entry", "material_slice", "source_article", "topic_cluster", "research_project"}.issubset(node_types)
        edge_types = {edge["edge_type"] for edge in graph["edges"]}
        assert {"derived_from", "sliced_from", "belongs_to", "supports", "related_to"}.issubset(edge_types)
        assert not list((KfcMaterialGraphStore.CONCEPT_REGISTRY_PATH.parent).glob("proj_*.json"))

        concept = registry_client.get(f"/api/registry/concepts/{concept_id}").get_json()["data"]
        assert concept["graph_status"] == "snapshot_available"
        assert concept["material_graph_id"] == data["material_graph_id"]
        assert concept["source_links"] == []

    def test_snapshot_api_is_idempotent_and_material_graph_list_filters(self, registry_client):
        concept_id = _seed_materialized_kfc_concept()

        first = registry_client.post(f"/api/registry/concepts/{concept_id}/graph/snapshot").get_json()["data"]
        second = registry_client.post(f"/api/registry/concepts/{concept_id}/graph/snapshot").get_json()["data"]
        assert first["material_graph_id"] == second["material_graph_id"]
        assert second["created"] is False
        assert len(list(KfcMaterialGraphStore.MATERIAL_GRAPH_DIR.glob("kmg_*.json"))) == 1

        resp = registry_client.get(f"/api/kfc/material-graphs?concept_id={concept_id}")
        assert resp.status_code == 200
        payload = resp.get_json()["data"]
        assert payload["total"] == 1
        assert payload["items"][0]["source_concept_id"] == concept_id

    def test_graphification_request_writes_request_only(self, registry_client):
        concept_id = _seed_materialized_kfc_concept()

        resp = registry_client.post(
            f"/api/registry/concepts/{concept_id}/graphification-requests",
            json={"actor": "human", "reason": "Need external relation proposals."},
        )
        assert resp.status_code == 201
        request_data = resp.get_json()["data"]
        assert request_data["status"] == "requested"
        assert request_data["rules"]["proposal_only"] is True
        assert request_data["rules"]["do_not_auto_apply"] is True
        assert request_data["rules"]["no_kfc_runtime_execution"] is True
        assert len(list(KfcMaterialGraphStore.GRAPHIFICATION_REQUEST_DIR.glob("kgreq_*.json"))) == 1
        assert not list((KfcMaterialGraphStore.CONCEPT_REGISTRY_PATH.parent).glob("proj_*.json"))

        concept = registry_client.get(f"/api/registry/concepts/{concept_id}").get_json()["data"]
        assert concept["graphification_request_id"] == request_data["request_id"]


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
