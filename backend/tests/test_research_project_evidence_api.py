from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_evidence import research_project_evidence_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore
from app.services.registry import global_concept_registry as concept_registry
from app.services.registry import global_theme_registry as theme_registry
from app.services.registry import source_evidence_resolver as evidence_resolver


@pytest.fixture()
def research_evidence_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    monkeypatch.setattr(concept_registry, "_registry_path", lambda: str(tmp_path / "projects" / "concept_registry.json"))
    monkeypatch.setattr(theme_registry, "_themes_path", lambda: str(tmp_path / "projects" / "global_themes.json"))
    monkeypatch.setattr(theme_registry, "_neo4j_sync_theme", lambda theme: None)

    entry = concept_registry.create_entry(
        canonical_name="企业级 Harness",
        concept_type="Architecture",
        aliases=["Harness"],
        description="Harness 支撑 Agent-ready 企业软件栈的测试、权限和回写。",
    )
    concept_registry.link_project_concept(
        entry["entry_id"],
        project_id="proj_source",
        concept_key="Architecture:企业级 Harness",
        project_name="Agent-ready 架构笔记",
    )
    theme = theme_registry.create_theme(
        name="Agent-ready 企业软件栈",
        description="Agent-ready 与企业级 Harness 的本地主题。",
        keywords=["Agent-ready", "Harness"],
        domain="tech",
    )
    theme_registry.attach_concepts(theme["theme_id"], [entry["entry_id"]])

    monkeypatch.setattr(
        evidence_resolver,
        "resolve_source_evidence",
        lambda entry, max_refs=3, graph_cache=None: [{
            "entry_id": entry["entry_id"],
            "project_id": "proj_source",
            "project_name": "Agent-ready 架构笔记",
            "concept_key": "Architecture:企业级 Harness",
            "source_node_uuid": "node_1",
            "source_text": "企业级 Harness 是执行控制面。",
            "group_label": "Architecture",
            "group_title": "执行控制层",
            "degraded": False,
        }],
    )

    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_evidence_bp)
    return app.test_client()


def _create_project(client):
    return client.post(
        "/api/research-projects",
        json={
            "title": "华为云 Agent-ready 企业软件栈战略研究",
            "background": "研究 Agent-ready 与 Harness。",
        },
    ).get_json()["data"]


def test_search_get_and_accept_local_evidence(research_evidence_client):
    project = _create_project(research_evidence_client)

    search = research_evidence_client.post(
        f"/api/research-projects/{project['id']}/local-evidence-pack/search",
        json={"keywords": ["Harness"], "limit": 10, "include_degraded": True},
    )
    assert search.status_code == 200
    pack = search.get_json()["data"]["local_evidence_pack"]
    assert pack["summary"]["candidate_count"] >= 1
    evidence_id = pack["candidates"][0]["evidence_id"]

    get_resp = research_evidence_client.get(f"/api/research-projects/{project['id']}/local-evidence-pack")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["data"]["local_evidence_pack"]["pack_id"] == pack["pack_id"]

    accept = research_evidence_client.patch(
        f"/api/research-projects/{project['id']}/local-evidence-pack/candidates/{evidence_id}",
        json={"status": "accepted", "note": "用于说明执行控制面"},
    )
    assert accept.status_code == 200
    data = accept.get_json()["data"]
    assert data["local_evidence_pack"]["summary"]["accepted_count"] == 1
    assert data["evidence_items"][0]["evidence_id"] == evidence_id


def test_local_evidence_api_missing_and_invalid_inputs(research_evidence_client):
    missing = research_evidence_client.post(
        "/api/research-projects/rp_000000000000/local-evidence-pack/search",
        json={"keywords": ["Harness"]},
    )
    assert missing.status_code == 404

    project = _create_project(research_evidence_client)
    bad_keywords = research_evidence_client.post(
        f"/api/research-projects/{project['id']}/local-evidence-pack/search",
        json={"keywords": "Harness"},
    )
    assert bad_keywords.status_code == 400

    bad_status = research_evidence_client.patch(
        f"/api/research-projects/{project['id']}/local-evidence-pack/candidates/ev_missing",
        json={"status": "insight"},
    )
    assert bad_status.status_code == 400


def test_patch_missing_candidate_returns_404(research_evidence_client):
    project = _create_project(research_evidence_client)
    research_evidence_client.post(
        f"/api/research-projects/{project['id']}/local-evidence-pack/search",
        json={"keywords": ["Harness"]},
    )

    resp = research_evidence_client.patch(
        f"/api/research-projects/{project['id']}/local-evidence-pack/candidates/ev_000000000000",
        json={"status": "accepted"},
    )

    assert resp.status_code == 404


def test_get_pack_before_generation_returns_not_generated(research_evidence_client):
    project = _create_project(research_evidence_client)

    resp = research_evidence_client.get(f"/api/research-projects/{project['id']}/local-evidence-pack")

    assert resp.status_code == 200
    assert resp.get_json()["data"]["local_evidence_pack"]["status"] == "not_generated"
