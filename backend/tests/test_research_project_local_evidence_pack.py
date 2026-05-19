from __future__ import annotations

import json

from app.models.research_project import ResearchProjectStore
from app.services.registry import global_concept_registry as concept_registry
from app.services.registry import global_theme_registry as theme_registry
from app.services.registry import source_evidence_resolver as evidence_resolver
from app.services.research.local_evidence_pack_service import generate_local_evidence_pack


def _seed_registry(tmp_path, monkeypatch):
    registry_path = tmp_path / "projects" / "concept_registry.json"
    themes_path = tmp_path / "projects" / "global_themes.json"
    monkeypatch.setattr(concept_registry, "_registry_path", lambda: str(registry_path))
    monkeypatch.setattr(theme_registry, "_themes_path", lambda: str(themes_path))
    monkeypatch.setattr(theme_registry, "_neo4j_sync_theme", lambda theme: None)

    entry = concept_registry.create_entry(
        canonical_name="企业级 Harness",
        concept_type="Architecture",
        aliases=["Harness", "Agent-ready 适配层"],
        description="企业级 Harness 负责权限、审批、测试和回写，是 Agent-ready 软件栈的执行控制面。",
    )
    concept_registry.link_project_concept(
        entry["entry_id"],
        project_id="proj_source",
        concept_key="Architecture:企业级 Harness",
        project_name="Agent-ready 架构笔记",
    )
    theme = theme_registry.create_theme(
        name="Agent-ready 企业软件栈",
        description="围绕 Agent-ready 适配层、企业级 Harness 和行业资产复用的主题。",
        keywords=["Agent-ready", "Harness", "企业软件栈"],
        domain="tech",
    )
    theme_registry.attach_concepts(theme["theme_id"], [entry["entry_id"]])
    return entry


def _stub_source_evidence(monkeypatch, *, degraded=False):
    def fake_resolve(entry, max_refs=3, graph_cache=None):
        return [{
            "entry_id": entry["entry_id"],
            "project_id": "proj_source",
            "project_name": "Agent-ready 架构笔记",
            "concept_key": "Architecture:企业级 Harness",
            "source_node_uuid": "" if degraded else "node_1",
            "source_text": "" if degraded else "企业级 Harness 是 Agent-ready 体系中的执行控制面。",
            "group_label": "Architecture",
            "group_title": "执行控制层",
            "degraded": degraded,
            "degraded_reason": "matched node has empty summary" if degraded else "",
        }]
    monkeypatch.setattr(evidence_resolver, "resolve_source_evidence", fake_resolve)


def test_generate_local_evidence_pack_from_local_registry(tmp_path, monkeypatch):
    _seed_registry(tmp_path, monkeypatch)
    _stub_source_evidence(monkeypatch)
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "background": "研究企业级 Harness 和 Agent-ready 适配层。",
    })

    pack = generate_local_evidence_pack(project, keywords=["Harness"], limit=10)

    assert pack["status"] == "draft"
    assert pack["summary"]["candidate_count"] >= 2
    concept = next(item for item in pack["candidates"] if item["evidence_type"] == "concept")
    assert concept["title"] == "企业级 Harness"
    assert concept["source"]["registry"] == "global_concept_registry"
    assert concept["source_refs"][0]["source_text"]
    assert concept["provenance"]["model_used"] is None
    assert concept["provenance"]["external_search_used"] is False


def test_generate_empty_pack_without_fake_evidence(tmp_path, monkeypatch):
    registry_path = tmp_path / "projects" / "concept_registry.json"
    themes_path = tmp_path / "projects" / "global_themes.json"
    monkeypatch.setattr(concept_registry, "_registry_path", lambda: str(registry_path))
    monkeypatch.setattr(theme_registry, "_themes_path", lambda: str(themes_path))
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = store.create({"title": "完全不匹配的研究题"})

    pack = generate_local_evidence_pack(project, keywords=["no-match-token"])

    assert pack["status"] == "empty"
    assert pack["candidates"] == []
    assert "does not perform external" in pack["empty_reason"]


def test_degraded_source_ref_is_preserved(tmp_path, monkeypatch):
    _seed_registry(tmp_path, monkeypatch)
    _stub_source_evidence(monkeypatch, degraded=True)
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = store.create({"title": "Agent-ready Harness"})

    pack = generate_local_evidence_pack(project, keywords=["Harness"], include_degraded=True)
    concept = next(item for item in pack["candidates"] if item["evidence_type"] == "concept")

    assert concept["source_refs"][0]["degraded"] is True
    assert concept["source_refs"][0]["degraded_reason"] == "matched node has empty summary"


def test_accept_and_reject_candidate_persist_consistently(tmp_path, monkeypatch):
    _seed_registry(tmp_path, monkeypatch)
    _stub_source_evidence(monkeypatch)
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = store.create({"title": "Agent-ready Harness"})
    pack = generate_local_evidence_pack(project, keywords=["Harness"])
    store.save_local_evidence_pack(project.id, pack)
    evidence_id = pack["candidates"][0]["evidence_id"]

    accepted = store.update_local_evidence_candidate_status(
        project.id,
        evidence_id,
        status="accepted",
        note="用于说明执行控制面",
    )
    assert accepted is not None
    assert accepted.local_evidence_pack["summary"]["accepted_count"] == 1
    assert accepted.evidence_items[0]["evidence_id"] == evidence_id

    # Re-accept is idempotent for evidence_items.
    accepted_again = store.update_local_evidence_candidate_status(
        project.id,
        evidence_id,
        status="accepted",
    )
    assert len([item for item in accepted_again.evidence_items if item["evidence_id"] == evidence_id]) == 1

    rejected = store.update_local_evidence_candidate_status(
        project.id,
        evidence_id,
        status="rejected",
        note="暂不使用",
    )
    assert rejected is not None
    assert evidence_id in rejected.local_evidence_pack["rejected_evidence_ids"]
    assert all(item["evidence_id"] != evidence_id for item in rejected.evidence_items)

    reloaded = ResearchProjectStore(tmp_path / "research_projects").get(project.id)
    assert reloaded.local_evidence_pack["candidates"][0]["status"] == "rejected"
    assert reloaded.evidence_items == []


def test_saved_pack_survives_store_reinitialization(tmp_path, monkeypatch):
    _seed_registry(tmp_path, monkeypatch)
    _stub_source_evidence(monkeypatch)
    root = tmp_path / "research_projects"
    store = ResearchProjectStore(root)
    project = store.create({"title": "Agent-ready Harness"})
    pack = generate_local_evidence_pack(project, keywords=["Harness"])
    store.save_local_evidence_pack(project.id, pack)

    raw = json.loads((root / f"{project.id}.json").read_text(encoding="utf-8"))
    assert raw["local_evidence_pack"]["pack_id"].startswith("lep_")

    reloaded = ResearchProjectStore(root).get(project.id)
    assert reloaded.local_evidence_pack["summary"]["candidate_count"] >= 1
