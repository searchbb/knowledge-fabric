from __future__ import annotations

import json

from flask import Flask
import pytest

from app.api import registry_bp
from app.api.routes.research_project_evidence import research_project_evidence_bp
from app.api.routes.research_projects import research_projects_bp
from app.api.routes.topic_clusters import topic_cluster_links_bp, topic_clusters_bp
from app.models.research_project import ResearchProjectStore
from app.services.kfc_promotion_store import KfcPromotionStore
from app.services.registry import global_concept_registry as concept_registry
from app.services.registry import global_theme_registry as theme_registry
from app.services.topic_cluster_asset_index import TopicClusterAssetIndexService
from app.services.topic_cluster_store import TopicClusterStore


@pytest.fixture()
def kfc_downstream_client(tmp_path, monkeypatch):
    cluster_dir = tmp_path / "topic_clusters"
    link_dir = tmp_path / "topic_cluster_links"
    material_slice_dir = tmp_path / "material_slices"
    lead_promotion_dir = tmp_path / "lead_promotions"
    registry_candidate_dir = tmp_path / "concept_registry_candidates"
    kfc_relation_dir = tmp_path / "kfc_asset_relations"
    kfc_change_log_dir = tmp_path / "kfc_change_log"
    projects_dir = tmp_path / "projects"
    concept_registry_path = projects_dir / "concept_registry.json"
    theme_registry_path = projects_dir / "global_themes.json"
    research_project_dir = tmp_path / "research_projects"

    monkeypatch.setattr(TopicClusterStore, "CLUSTER_DIR", cluster_dir)
    monkeypatch.setattr(TopicClusterStore, "LINK_DIR", link_dir)
    monkeypatch.setattr(KfcPromotionStore, "MATERIAL_SLICE_DIR", material_slice_dir)
    monkeypatch.setattr(KfcPromotionStore, "LEAD_PROMOTION_DIR", lead_promotion_dir)
    monkeypatch.setattr(KfcPromotionStore, "CONCEPT_REGISTRY_CANDIDATE_DIR", registry_candidate_dir)
    monkeypatch.setattr(KfcPromotionStore, "KFC_RELATION_DIR", kfc_relation_dir)
    monkeypatch.setattr(KfcPromotionStore, "KFC_CHANGE_LOG_DIR", kfc_change_log_dir)
    monkeypatch.setattr(KfcPromotionStore, "CONCEPT_REGISTRY_PATH", concept_registry_path)
    monkeypatch.setattr(TopicClusterAssetIndexService, "CONCEPTS_PATH", concept_registry_path)
    monkeypatch.setattr(TopicClusterAssetIndexService, "THEMES_PATH", theme_registry_path)
    monkeypatch.setattr(TopicClusterAssetIndexService, "KFC_RELATION_DIR", kfc_relation_dir)
    monkeypatch.setattr(TopicClusterAssetIndexService, "RESEARCH_PROJECT_DIR", research_project_dir)
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", research_project_dir)
    monkeypatch.setattr(concept_registry, "_registry_path", lambda: str(concept_registry_path))
    monkeypatch.setattr(theme_registry, "_themes_path", lambda: str(theme_registry_path))
    monkeypatch.setattr(theme_registry, "_neo4j_sync_theme", lambda theme: None)

    _write_json(
        cluster_dir / "tc_digest.json",
        {
            "cluster_id": "tc_digest",
            "title": "KFC 消化链路",
            "description": "验证 Wiki lead 沉淀后能进入 KFC 下游研究资产。",
            "status": "active",
            "strategic_relevance": "high",
        },
    )
    _write_json(
        link_dir / "tcl_digest_wiki.json",
        {
            "link_id": "tcl_digest_wiki",
            "cluster_id": "tc_digest",
            "target_type": "wiki_topic",
            "target_id": "agent-protocol",
            "target_title": "Agent 工具互操作",
            "role": "primary",
            "status": "accepted",
        },
    )
    _write_json(theme_registry_path, {"version": 1, "themes": {}})
    _write_json(
        concept_registry_path,
        {
            "version": 1,
            "entries": {
                "canon_existing_harness": {
                    "entry_id": "canon_existing_harness",
                    "canonical_name": "Agent Harness",
                    "concept_type": "Concept",
                    "aliases": ["执行外壳"],
                    "description": "已有 KFC 概念，用于组织工具调用、权限和审计。",
                    "source_links": [],
                }
            },
        },
    )

    app = Flask(__name__)
    app.register_blueprint(topic_clusters_bp)
    app.register_blueprint(topic_cluster_links_bp)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_evidence_bp)
    return app.test_client(), {
        "concept_registry_path": concept_registry_path,
        "kfc_relation_dir": kfc_relation_dir,
        "kfc_change_log_dir": kfc_change_log_dir,
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_project(client):
    resp = client.post(
        "/api/research-projects",
        json={
            "title": "Agent 工具互操作战略研究",
            "background": "研究工具互操作协议、执行审计和项目证据沉淀。",
            "goal": "判断工具互操作协议是否是 KFC 可复用研究资产。",
            "research_brief": {"key_questions": ["工具互操作协议如何成为项目证据？"]},
        },
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]


def _deposit_concept(client, project_id: str):
    slice_resp = client.post(
        "/api/topic-clusters/tc_digest/material-slices",
        json={
            "slice_type": "concept_lead",
            "title": "工具互操作协议",
            "summary": "文章说明工具互操作协议是 Agent Harness 消化外部工具能力的关键概念。",
            "source_quote": "工具互操作协议让 Agent Harness 可以稳定调用外部工具并保留审计上下文。",
            "source_excerpt": "Agent Harness 需要工具互操作协议、权限边界和审计上下文。",
            "source_context": "在企业环境中，工具互操作协议连接权限、审计、回滚和项目证据沉淀。",
            "source_article_id": "src_tool_protocol",
            "source_markdown_path": "/Users/mac/wiki/tool-protocol.md",
            "source_content_hash": "sha256:toolprotocol",
            "source_title": "Agent 工具互操作协议",
            "linked_wiki_topic": "agent-protocol",
            "linked_research_project": project_id,
            "extraction_reason": "lead label appears in heading and supporting paragraph.",
            "confidence": 0.87,
        },
    )
    assert slice_resp.status_code == 201
    promotion = slice_resp.get_json()["data"]["promotion"]
    action_resp = client.post(
        f"/api/topic-clusters/tc_digest/lead-promotions/{promotion['promotion_id']}/actions",
        json={
            "action": "deposit_as_new_concept",
            "actor": "codex",
            "created_from": "concept_lead",
        },
    )
    assert action_resp.status_code == 200
    concept_id = action_resp.get_json()["data"]["concept"]["concept_id"]
    return concept_id


def test_deposit_lead_creates_searchable_registry_concept(kfc_downstream_client):
    client, _paths = kfc_downstream_client
    project = _create_project(client)
    concept_id = _deposit_concept(client, project["id"])

    get_resp = client.get(f"/api/registry/concepts/{concept_id}")
    assert get_resp.status_code == 200
    concept = get_resp.get_json()["data"]
    assert concept["entry_id"] == concept_id
    assert concept["asset_type"] == "concept"
    assert concept["lifecycle_status"] == "active"
    assert concept["quality_state"] == "machine_generated"
    assert concept["review_state"] == "unreviewed"
    assert concept["source_article_id"] == "src_tool_protocol"
    assert concept["source_content_hash"] == "sha256:toolprotocol"
    assert "工具互操作协议" in concept["source_quote"]
    assert "Quote:" in concept["digest_input_text"]
    assert concept["digested_text"]
    assert concept["related_existing_concepts"][0]["concept_id"] == "canon_existing_harness"
    assert concept["source_material_slice_id"].startswith("ms_")
    assert concept["source_lead_id"].startswith("lp_")
    assert "tc_digest" in concept["linked_topic_cluster_ids"]
    assert project["id"] in concept["linked_research_project_ids"]

    search_resp = client.get("/api/registry/concepts/search?q=工具互操作协议")
    assert search_resp.status_code == 200
    search_ids = [item["entry_id"] for item in search_resp.get_json()["data"]["results"]]
    assert concept_id in search_ids
    quote_search = client.get("/api/registry/concepts/search?q=审计上下文")
    assert quote_search.status_code == 200
    assert concept_id in [item["entry_id"] for item in quote_search.get_json()["data"]["results"]]
    context_search = client.get("/api/registry/concepts/search?q=项目证据沉淀")
    assert context_search.status_code == 200
    assert concept_id in [item["entry_id"] for item in context_search.get_json()["data"]["results"]]


def test_deposited_concept_appears_in_topic_cluster_asset_index(kfc_downstream_client):
    client, _paths = kfc_downstream_client
    project = _create_project(client)
    concept_id = _deposit_concept(client, project["id"])

    index_resp = client.get("/api/topic-clusters/tc_digest/asset-index")
    assert index_resp.status_code == 200
    index = index_resp.get_json()["data"]
    formal_concepts = index["formal_assets"]["concepts"]
    concept_item = next(item for item in formal_concepts if item["concept_id"] == concept_id)
    assert concept_item["target_title"] == "工具互操作协议"
    assert concept_item["association_type"] == "formal"
    assert concept_item["lifecycle_status"] == "active"
    assert concept_item["quality_state"] == "machine_generated"
    assert concept_item["review_state"] == "unreviewed"
    assert concept_item["source_article_id"] == "src_tool_protocol"
    assert "Agent Harness" in concept_item["source_quote"]
    assert concept_item["provenance"]["source_content_hash"] == "sha256:toolprotocol"
    assert index["counts"]["direct_kfc_concept_count"] >= 1


def test_deposited_concept_can_be_accepted_as_project_evidence(kfc_downstream_client):
    client, paths = kfc_downstream_client
    project = _create_project(client)
    concept_id = _deposit_concept(client, project["id"])

    search_resp = client.post(
        f"/api/research-projects/{project['id']}/local-evidence-pack/search",
        json={"keywords": ["审计上下文"], "limit": 10, "include_degraded": True},
    )
    assert search_resp.status_code == 200
    pack = search_resp.get_json()["data"]["local_evidence_pack"]
    candidate = next(item for item in pack["candidates"] if item["source_concept_id"] == concept_id)
    assert candidate["status"] == "candidate"
    assert candidate["source_article_id"] == "src_tool_protocol"
    assert candidate["source_material_slice_id"].startswith("ms_")
    assert candidate["source_lead_id"].startswith("lp_")
    assert candidate["source_content_hash"] == "sha256:toolprotocol"
    assert "权限" in candidate["source_context"]
    assert candidate["source"]["registry"] == "global_concept_registry"

    accept_resp = client.patch(
        f"/api/research-projects/{project['id']}/local-evidence-pack/candidates/{candidate['evidence_id']}",
        json={"status": "accepted", "note": "用于验证 KFC 下游消化链路"},
    )
    assert accept_resp.status_code == 200
    data = accept_resp.get_json()["data"]
    evidence = next(item for item in data["evidence_items"] if item["evidence_id"] == candidate["evidence_id"])
    assert evidence["project_id"] == project["id"]
    assert evidence["source_concept_id"] == concept_id
    assert evidence["source_article_id"] == "src_tool_protocol"
    assert evidence["source_material_slice_id"] == candidate["source_material_slice_id"]
    assert evidence["source_lead_id"] == candidate["source_lead_id"]
    assert evidence["source_content_hash"] == "sha256:toolprotocol"
    assert evidence["created_from"] == "local_evidence_pack"
    assert "Agent Harness" in evidence["source_quote"]

    accept_again = client.patch(
        f"/api/research-projects/{project['id']}/local-evidence-pack/candidates/{candidate['evidence_id']}",
        json={"status": "accepted", "note": "再次接受应保持幂等"},
    )
    assert accept_again.status_code == 200
    evidence_items = [
        item
        for item in accept_again.get_json()["data"]["evidence_items"]
        if item["evidence_id"] == candidate["evidence_id"]
    ]
    assert len(evidence_items) == 1

    registry = json.loads(paths["concept_registry_path"].read_text(encoding="utf-8"))
    assert project["id"] in registry["entries"][concept_id]["linked_research_project_ids"]

    relations = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in paths["kfc_relation_dir"].glob("rel_*.json")
    ]
    assert any(
        relation["source_id"] == concept_id
        and relation["target_type"] == "concept_registry_entry"
        and relation["target_id"] == "canon_existing_harness"
        and relation["relation_type"] == "related_to"
        for relation in relations
    )
    assert any(
        relation["source_id"] == concept_id
        and relation["target_type"] == "research_project"
        and relation["target_id"] == project["id"]
        for relation in relations
    )
    changes = [
        json.loads(line)
        for line in (paths["kfc_change_log_dir"] / "kfc_changes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        change["action"] == "accept_local_evidence_candidate"
        and change["source_ids"]["concept_id"] == concept_id
        and change["source_ids"]["evidence_id"] == candidate["evidence_id"]
        for change in changes
    )


def test_duplicate_deposit_same_promotion_is_idempotent_and_logged(kfc_downstream_client):
    client, paths = kfc_downstream_client
    project = _create_project(client)
    slice_resp = client.post(
        "/api/topic-clusters/tc_digest/material-slices",
        json={
            "slice_type": "concept_lead",
            "title": "重复沉淀测试概念",
            "summary": "用于验证重复点击沉淀不会重复创建概念。",
            "source_quote": "重复沉淀测试概念应当复用已创建的 KFC 概念资产。",
            "source_context": "用户可能重复点击沉淀按钮，因此 KFC 需要幂等处理。",
            "source_article_id": "src_duplicate",
            "source_markdown_path": "/Users/mac/wiki/duplicate.md",
            "source_content_hash": "sha256:duplicate",
            "source_title": "重复沉淀验证",
            "linked_research_project": project["id"],
        },
    )
    assert slice_resp.status_code == 201
    promotion = slice_resp.get_json()["data"]["promotion"]
    action_url = f"/api/topic-clusters/tc_digest/lead-promotions/{promotion['promotion_id']}/actions"
    first = client.post(action_url, json={"action": "deposit_as_new_concept"})
    assert first.status_code == 200
    concept_id = first.get_json()["data"]["concept"]["concept_id"]
    first_registry_count = len(json.loads(paths["concept_registry_path"].read_text(encoding="utf-8"))["entries"])
    first_relation_count = len(list(paths["kfc_relation_dir"].glob("rel_*.json")))

    second = client.post(action_url, json={"action": "deposit_as_new_concept"})
    assert second.status_code == 200
    assert second.get_json()["data"]["concept"]["concept_id"] == concept_id
    second_registry_count = len(json.loads(paths["concept_registry_path"].read_text(encoding="utf-8"))["entries"])
    second_relation_count = len(list(paths["kfc_relation_dir"].glob("rel_*.json")))
    assert second_registry_count == first_registry_count
    assert second_relation_count == first_relation_count
    changes = [
        json.loads(line)
        for line in (paths["kfc_change_log_dir"] / "kfc_changes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        change["action"] == "deposit_concept_idempotent"
        and change["source_ids"]["concept_id"] == concept_id
        for change in changes
    )


def test_correction_governance_preserves_text_digest_lineage(kfc_downstream_client):
    client, _paths = kfc_downstream_client
    project = _create_project(client)
    concept_id = _deposit_concept(client, project["id"])
    before = client.get(f"/api/registry/concepts/{concept_id}").get_json()["data"]

    patched = client.patch(
        f"/api/topic-clusters/kfc-concepts/{concept_id}",
        json={"definition": "人工订正后的定义。", "quality_state": "corrected", "review_state": "reviewed"},
    )
    assert patched.status_code == 200
    after_patch = patched.get_json()["data"]
    assert after_patch["definition"] == "人工订正后的定义。"
    assert after_patch["source_quote"] == before["source_quote"]
    assert after_patch["source_context"] == before["source_context"]
    assert after_patch["digest_input_text"] == before["digest_input_text"]

    deprecated = client.post(
        f"/api/topic-clusters/kfc-concepts/{concept_id}/deprecate",
        json={"reason": "验证废弃不破坏 lineage"},
    )
    assert deprecated.status_code == 200
    after_deprecate = deprecated.get_json()["data"]
    assert after_deprecate["lifecycle_status"] == "deprecated"
    assert after_deprecate["source_material_slice_id"] == before["source_material_slice_id"]
    assert after_deprecate["source_lead_id"] == before["source_lead_id"]
