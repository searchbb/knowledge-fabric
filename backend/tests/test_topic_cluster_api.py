from __future__ import annotations

import json
import subprocess

from flask import Flask
import pytest

from app.api.routes.topic_clusters import topic_cluster_links_bp, topic_clusters_bp
from app.models.research_project import ResearchProjectStore
from app.services.kfc_promotion_store import KfcPromotionStore
from app.services.topic_cluster_proposal_store import TopicClusterProposalStore
from app.services.topic_cluster_refresh_request_store import TopicClusterRefreshRequestStore
from app.services.topic_cluster_asset_index import TopicClusterAssetIndexService
from app.services.topic_cluster_store import TopicClusterStore
from app.wiki_intake.store import WikiIntakeStore


@pytest.fixture()
def topic_cluster_client(tmp_path, monkeypatch):
    cluster_dir = tmp_path / "topic_clusters"
    link_dir = tmp_path / "topic_cluster_links"
    refresh_request_dir = tmp_path / "topic_cluster_refresh_requests"
    proposal_dir = tmp_path / "topic_cluster_proposals"
    application_dir = tmp_path / "topic_cluster_proposal_applications"
    material_slice_dir = tmp_path / "material_slices"
    lead_promotion_dir = tmp_path / "lead_promotions"
    registry_candidate_dir = tmp_path / "concept_registry_candidates"
    kfc_relation_dir = tmp_path / "kfc_asset_relations"
    relation_candidate_dir = tmp_path / "relation_candidates"
    kfc_change_log_dir = tmp_path / "kfc_change_log"
    concept_registry_path = tmp_path / "uploads" / "projects" / "concept_registry.json"
    research_project_dir = tmp_path / "research_projects"
    monkeypatch.setattr(TopicClusterStore, "CLUSTER_DIR", cluster_dir)
    monkeypatch.setattr(TopicClusterStore, "LINK_DIR", link_dir)
    monkeypatch.setattr(TopicClusterRefreshRequestStore, "ROOT_DIR", refresh_request_dir)
    monkeypatch.setattr(TopicClusterProposalStore, "PROPOSAL_DIR", proposal_dir)
    monkeypatch.setattr(TopicClusterProposalStore, "APPLICATION_DIR", application_dir)
    monkeypatch.setattr(KfcPromotionStore, "MATERIAL_SLICE_DIR", material_slice_dir)
    monkeypatch.setattr(KfcPromotionStore, "LEAD_PROMOTION_DIR", lead_promotion_dir)
    monkeypatch.setattr(KfcPromotionStore, "CONCEPT_REGISTRY_CANDIDATE_DIR", registry_candidate_dir)
    monkeypatch.setattr(KfcPromotionStore, "KFC_RELATION_DIR", kfc_relation_dir)
    monkeypatch.setattr(KfcPromotionStore, "RELATION_CANDIDATE_DIR", relation_candidate_dir)
    monkeypatch.setattr(KfcPromotionStore, "KFC_CHANGE_LOG_DIR", kfc_change_log_dir)
    monkeypatch.setattr(KfcPromotionStore, "CONCEPT_REGISTRY_PATH", concept_registry_path)
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", research_project_dir)
    app = Flask(__name__)
    app.register_blueprint(topic_clusters_bp)
    app.register_blueprint(topic_cluster_links_bp)
    return app.test_client(), cluster_dir, link_dir


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_cluster(cluster_dir, link_dir):
    _write_json(
        cluster_dir / "tc_agent_ready.json",
        {
            "cluster_id": "tc_agent_ready",
            "title": "Agent-ready 企业软件栈",
            "description": "聚合 Agent 化、Harness 和执行治理。",
            "status": "active",
            "strategic_relevance": "high",
            "updated_at": "2026-05-12T10:00:00",
        },
    )
    links = [
        {
            "link_id": "tcl_wiki",
            "cluster_id": "tc_agent_ready",
            "target_type": "wiki_topic",
            "target_id": "agent-ready-enterprise-stack",
            "target_title": "Agent-ready 企业软件栈",
            "role": "primary",
            "status": "accepted",
        },
        {
            "link_id": "tcl_theme",
            "cluster_id": "tc_agent_ready",
            "target_type": "kfc_theme",
            "target_id": "gtheme_agent",
            "target_title": "AI Agent系统架构与上下文管理",
            "role": "supporting",
            "status": "candidate",
        },
        {
            "link_id": "tcl_rp",
            "cluster_id": "tc_agent_ready",
            "target_type": "research_project",
            "target_id": "rp_000000000000",
            "target_title": "Agent-ready 战略研究",
            "role": "supporting",
            "status": "needs_review",
        },
    ]
    for link in links:
        _write_json(link_dir / f"{link['link_id']}.json", link)


def _seed_asset_index_cluster(cluster_dir, link_dir):
    _write_json(
        cluster_dir / "tc_agent_index.json",
        {
            "cluster_id": "tc_agent_index",
            "title": "Agent Harness 战略控制点",
            "description": "企业 Agent 执行治理、权限审批、回滚和审计。",
            "status": "active",
            "strategic_relevance": "high",
            "updated_at": "2026-05-13T10:00:00",
        },
    )
    _write_json(
        link_dir / "tcl_agent_index_wiki.json",
        {
            "link_id": "tcl_agent_index_wiki",
            "cluster_id": "tc_agent_index",
            "target_type": "wiki_topic",
            "target_id": "agent-harness",
            "target_title": "Agent Harness 与工具编排",
            "role": "primary",
            "status": "accepted",
        },
    )


def _seed_asset_index_sources(tmp_path, monkeypatch):
    wiki_intake_dir = tmp_path / "wiki_intake"
    wiki_hub = tmp_path / "wiki_hub"
    clipping = tmp_path / "Clippings" / "agent.md"
    clipping.parent.mkdir()
    clipping.write_text("# Agent Harness", encoding="utf-8")
    topic_dir = wiki_hub / "topics" / "agent-harness"
    digest_dir = topic_dir / "digests" / "verified_digest"
    digest_dir.mkdir(parents=True)
    (topic_dir / "topic_profile.json").write_text(
        json.dumps(
            {
                "topic_id": "agent-harness",
                "display_name": "Agent Harness 与工具编排",
                "topic_keywords": ["Agent Harness", "执行治理"],
                "concept_seeds": ["权限审批", "审计"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    digest_path = digest_dir / "agent.json"
    digest_path.write_text(
        json.dumps(
            {
                "title": "Agent Harness 工作流笔记",
                "summary": "企业 Agent Harness 需要执行治理、权限审批和审计。",
                "core_concepts": [
                    "Agent Harness",
                    "{'concept': '执行治理', 'summary': '权限审批和审计是 Agent Harness 的治理核心。'}",
                    {"concept": "审计控制", "summary": "记录执行链路，支持回滚和问责。"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    wiki_intake_dir.mkdir()
    (wiki_intake_dir / "manifest.jsonl").write_text(
        json.dumps(
            {
                "candidate_id": "src_agent",
                "source_id": "src_agent",
                "title": "Agent Harness 工作流笔记",
                "source_url": "https://example.com/agent-harness",
                "source_file_path": str(clipping),
                "guessed_topics": [{"topic_id": "agent-harness"}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (wiki_intake_dir / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "candidate_id": "src_agent",
                "source_id": "src_agent",
                "source_md": str(clipping),
                "topic_id": "agent-harness",
                "processed_at": "2026-05-13T11:53:36+08:00",
                "verified_digest_json_path": str(digest_path),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    themes_path = tmp_path / "uploads" / "global_themes.json"
    concepts_path = tmp_path / "uploads" / "concept_registry.json"
    research_dir = tmp_path / "research_projects"
    notes_dir = tmp_path / "notes"
    _write_json(
        themes_path,
        {
            "version": 1,
            "themes": {
                "gtheme_agent_harness": {
                    "theme_id": "gtheme_agent_harness",
                    "name": "Agent Harness 执行治理",
                    "description": "企业 Agent 的权限审批、回滚和审计控制点。",
                    "keywords": ["Agent Harness", "执行治理", "权限审批"],
                    "concept_memberships": [
                        {"entry_id": "canon_agent_harness", "role": "member", "score": 0.9}
                    ],
                }
            },
        },
    )
    _write_json(
        concepts_path,
        {
            "version": 1,
            "entries": {
                "canon_agent_harness": {
                    "entry_id": "canon_agent_harness",
                    "canonical_name": "Agent Harness",
                    "concept_type": "Solution",
                    "aliases": ["执行治理外壳"],
                    "description": "围绕工具编排、审计和回滚的企业 Agent 控制层。",
                }
            },
        },
    )
    _write_json(
        research_dir / "rp_aaaaaaaaaaaa.json",
        {
            "id": "rp_aaaaaaaaaaaa",
            "title": "Agent Harness 战略研究",
            "background": "研究企业 Agent Harness 执行治理和审计控制点。",
            "goal": "识别可复用控制点。",
            "research_brief": {"key_questions": ["Agent Harness 如何做权限审批？"]},
            "evidence_items": [
                {
                    "evidence_id": "ev_harness",
                    "title": "Agent Harness evidence",
                    "claim": "企业 Agent 需要权限审批和执行审计。",
                    "status": "accepted",
                }
            ],
            "insight_cards": [
                {
                    "id": "ic_harness",
                    "title": "执行治理层是长期控制点",
                    "claim": "Agent Harness 的审计和回滚能力构成控制点。",
                }
            ],
            "artifact_drafts": [
                {
                    "id": "ad_harness",
                    "title": "Agent Harness 汇报草稿",
                    "artifact_type": "brief",
                }
            ],
        },
    )
    notes_dir.mkdir(parents=True)
    (notes_dir / "note_agent.md").write_text(
        "# Agent Harness 定价判断\n\n权限审批、审计和执行治理是关键控制点。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", wiki_intake_dir)
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clipping.parent)
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    monkeypatch.setattr(TopicClusterAssetIndexService, "THEMES_PATH", themes_path)
    monkeypatch.setattr(TopicClusterAssetIndexService, "CONCEPTS_PATH", concepts_path)
    monkeypatch.setattr(TopicClusterAssetIndexService, "RESEARCH_PROJECT_DIR", research_dir)
    monkeypatch.setattr(TopicClusterAssetIndexService, "NOTES_DIR", notes_dir)
    return {
        "themes_path": themes_path,
        "concepts_path": concepts_path,
        "research_dir": research_dir,
        "notes_dir": notes_dir,
    }


def _seed_promotion_cluster(cluster_dir, link_dir):
    _write_json(
        cluster_dir / "tc_promotion.json",
        {
            "cluster_id": "tc_promotion",
            "title": "Promotion Cluster",
            "description": "Wiki 粗加工到 KFC 加工篮测试。",
            "status": "active",
            "strategic_relevance": "high",
        },
    )
    _write_json(
        link_dir / "tcl_promotion_wiki.json",
        {
            "link_id": "tcl_promotion_wiki",
            "cluster_id": "tc_promotion",
            "target_type": "wiki_topic",
            "target_id": "agent-harness",
            "target_title": "Agent Harness 与工具编排",
            "role": "primary",
            "status": "accepted",
        },
    )


def _slice_payload(**overrides):
    payload = {
        "slice_type": "concept_lead",
        "title": "代码知识图谱",
        "summary": "文章讨论代码知识图谱作为 Agent Harness 的上下文组织方式。",
        "source_quote": "代码知识图谱把 AST、调用关系和语义线索组织为可检索上下文。",
        "source_span": {"start_char": 120, "end_char": 180, "selector": "heading:代码知识图谱"},
        "source_article_id": "src_agent_harness",
        "source_markdown_path": "/Users/mac/wiki/agent-harness.md",
        "source_content_hash": "sha256:agentharness",
        "source_title": "AI 还在猜代码？",
        "source_url": "https://example.com/agent-harness",
        "linked_wiki_topic": "agent-harness",
        "create_promotion": True,
        "created_from": "topic_cluster_detail.article_card",
    }
    payload.update(overrides)
    return payload


def _create_promotion(client):
    resp = client.post("/api/topic-clusters/tc_promotion/material-slices", json=_slice_payload())
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    return data["slice"], data["promotion"]


def test_list_topic_clusters_empty(topic_cluster_client):
    client, _, _ = topic_cluster_client

    resp = client.get("/api/topic-clusters")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["warnings"] == []


def test_list_topic_clusters_with_counts(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)

    resp = client.get("/api/topic-clusters")

    assert resp.status_code == 200
    item = resp.get_json()["data"]["items"][0]
    assert item["cluster_id"] == "tc_agent_ready"
    assert item["counts"] == {
        "wiki_topics": 1,
        "kfc_themes": 1,
        "research_projects": 1,
        "candidate_links": 1,
        "needs_review_links": 1,
    }


def test_get_topic_cluster_detail(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)

    resp = client.get("/api/topic-clusters/tc_agent_ready")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["cluster"]["description"] == "聚合 Agent 化、Harness 和执行治理。"
    assert [item["target_id"] for item in data["links_by_type"]["wiki_topic"]] == [
        "agent-ready-enterprise-stack"
    ]
    assert [item["target_id"] for item in data["links_by_type"]["kfc_theme"]] == ["gtheme_agent"]
    assert [item["target_id"] for item in data["links_by_type"]["research_project"]] == [
        "rp_000000000000"
    ]


def test_get_topic_clusters_by_wiki_topic_target(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)

    resp = client.get(
        "/api/topic-clusters/by-target?target_type=wiki_topic&target_id=agent-ready-enterprise-stack"
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["cluster"]["cluster_id"] == "tc_agent_ready"
    assert data["items"][0]["link"]["target_type"] == "wiki_topic"


def test_get_topic_clusters_by_kfc_theme_target(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)

    resp = client.get("/api/topic-clusters/by-target?target_type=kfc_theme&target_id=gtheme_agent")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["cluster"]["title"] == "Agent-ready 企业软件栈"


def test_malformed_cluster_json_degraded(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)
    cluster_dir.mkdir(parents=True, exist_ok=True)
    (cluster_dir / "tc_bad.json").write_text("{bad json", encoding="utf-8")

    resp = client.get("/api/topic-clusters")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["total"] == 1
    assert data["warnings"][0]["type"] == "malformed_cluster_json"


def test_malformed_link_json_degraded(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)
    link_dir.mkdir(parents=True, exist_ok=True)
    (link_dir / "tcl_bad.json").write_text("{bad json", encoding="utf-8")

    resp = client.get("/api/topic-clusters/tc_agent_ready")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["cluster"]["counts"]["wiki_topics"] == 1
    assert data["warnings"][0]["type"] == "malformed_link_json"


def test_by_target_rejects_path_traversal(topic_cluster_client):
    client, _, _ = topic_cluster_client

    resp = client.get("/api/topic-clusters/by-target?target_type=wiki_topic&target_id=../secret")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_no_research_project_created_by_cluster_apis(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_cluster(cluster_dir, link_dir)

    client.get("/api/topic-clusters")
    client.get("/api/topic-clusters/tc_agent_ready")
    client.get("/api/topic-clusters/tc_agent_ready/links")
    client.get("/api/topic-clusters/by-target?target_type=research_project&target_id=rp_000000000000")

    assert not (cluster_dir.parent / "research_projects").exists()


def test_topic_cluster_include_counts_and_articles_aggregates_wiki_topics(topic_cluster_client, monkeypatch, tmp_path):
    client, cluster_dir, link_dir = topic_cluster_client
    wiki_intake_dir = tmp_path / "wiki_intake"
    wiki_hub = tmp_path / "wiki_hub"
    clipping = tmp_path / "Clippings" / "agent.md"
    clipping.parent.mkdir()
    clipping.write_text("# Agent Harness", encoding="utf-8")
    topic_dir = wiki_hub / "topics" / "agent-ready-enterprise-stack"
    digest_dir = topic_dir / "digests" / "verified_digest"
    digest_dir.mkdir(parents=True)
    (topic_dir / "topic_profile.json").write_text(
        json.dumps({"topic_id": "agent-ready-enterprise-stack", "display_name": "Agent-ready 企业软件栈"}, ensure_ascii=False),
        encoding="utf-8",
    )
    digest_path = digest_dir / "agent.json"
    digest_path.write_text(
        json.dumps({"title": "Agent Harness", "summary": "Agent article summary", "core_concepts": ["agent runtime"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    wiki_intake_dir.mkdir()
    (wiki_intake_dir / "manifest.jsonl").write_text(
        json.dumps(
            {
                "candidate_id": "src_agent",
                "source_id": "src_agent",
                "title": "Agent Harness",
                "source_url": "https://example.com/agent",
                "source_file_path": str(clipping),
                "guessed_topics": [{"topic_id": "agent-ready-enterprise-stack"}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (wiki_intake_dir / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "candidate_id": "src_agent",
                "source_id": "src_agent",
                "source_md": str(clipping),
                "topic_id": "agent-ready-enterprise-stack",
                "processed_at": "2026-05-12T11:53:36+08:00",
                "verified_digest_json_path": str(digest_path),
                "raw_article_path": str(topic_dir / "raw" / "articles" / "agent.md"),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", wiki_intake_dir)
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clipping.parent)
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    _seed_cluster(cluster_dir, link_dir)

    listed = client.get("/api/topic-clusters?include_counts=1")
    assert listed.status_code == 200
    item = listed.get_json()["data"]["items"][0]
    assert item["wiki_topic_count"] == 1
    assert item["kfc_theme_count"] == 1
    assert item["research_project_count"] == 1
    assert item["article_count"] == 1
    assert item["representative_articles"][0]["title"] == "Agent Harness"

    detail = client.get("/api/topic-clusters/tc_agent_ready?include_counts=1&include_articles=1")
    assert detail.status_code == 200
    cluster = detail.get_json()["data"]["cluster"]
    assert cluster["article_count"] == 1
    assert cluster["linked_topic_articles"][0]["topic_id"] == "agent-ready-enterprise-stack"
    assert cluster["linked_topic_articles"][0]["articles"][0]["digest_summary"] == "Agent article summary"
    assert not (cluster_dir.parent / "research_projects").exists()


def test_asset_index_api_returns_direct_indirect_and_candidate_assets(topic_cluster_client, monkeypatch, tmp_path):
    client, cluster_dir, link_dir = topic_cluster_client
    sources = _seed_asset_index_sources(tmp_path, monkeypatch)
    _seed_asset_index_cluster(cluster_dir, link_dir)
    link_before = sorted(path.name for path in link_dir.glob("*.json"))
    research_before = sorted(path.name for path in sources["research_dir"].glob("*.json"))

    resp = client.get("/api/topic-clusters/tc_agent_index/asset-index")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["cluster_id"] == "tc_agent_index"
    assert [item["target_id"] for item in data["direct_links"]["wiki_topics"]] == ["agent-harness"]
    assert data["direct_links"]["kfc_themes"] == []
    assert data["direct_links"]["research_projects"] == []
    assert data["indirect_assets"]["articles"][0]["target_title"] == "Agent Harness 工作流笔记"
    assert data["indirect_assets"]["articles"][0]["source_url"] == "https://example.com/agent-harness"
    assert data["indirect_assets"]["articles"][0]["top_concepts"] == ["Agent Harness", "执行治理", "审计控制"]
    assert data["indirect_assets"]["articles"][0]["top_concept_details"][1] == {
        "title": "执行治理",
        "summary": "权限审批和审计是 Agent Harness 的治理核心。",
    }
    assert data["indirect_assets"]["articles"][0]["top_concept_details"][2] == {
        "title": "审计控制",
        "summary": "记录执行链路，支持回滚和问责。",
    }
    assert "formal wiki_topic link: agent-harness" in data["indirect_assets"]["articles"][0]["belongs_to_cluster_reason"]
    assert "top concepts overlap: Agent Harness, 执行治理, 审计控制" in data["indirect_assets"]["articles"][0]["belongs_to_cluster_reason"]
    assert data["indirect_assets"]["articles"][0]["routes"]["wiki_topic"] == "/workspace/wiki-topics/agent-harness"
    assert data["candidate_assets"]["kfc_themes"][0]["target_id"] == "gtheme_agent_harness"
    assert data["candidate_assets"]["kfc_themes"][0]["association_type"] == "candidate"
    assert data["candidate_assets"]["kfc_themes"][0]["confirmation_status"] == "unconfirmed"
    assert data["candidate_assets"]["kfc_themes"][0]["promotion_supported"] is True
    assert data["candidate_assets"]["kfc_themes"][0]["summary"] == "企业 Agent 的权限审批、回滚和审计控制点。"
    assert data["candidate_assets"]["kfc_themes"][0]["member_concepts"][0]["entry_id"] == "canon_agent_harness"
    assert data["candidate_assets"]["kfc_themes"][0]["diagnostics"]["missing_article_provenance"] is True
    assert "matched_fields" in data["candidate_assets"]["kfc_themes"][0]["why_candidate"]
    assert data["candidate_assets"]["concepts"][0]["target_id"] == "canon_agent_harness"
    assert data["candidate_assets"]["concepts"][0]["promotion_supported"] is False
    assert data["candidate_assets"]["concepts"][0]["aliases"] == ["执行治理外壳"]
    assert data["candidate_assets"]["concepts"][0]["concept_type"] == "Solution"
    assert data["candidate_assets"]["concepts"][0]["diagnostics"]["concept_cluster_link_unsupported"] is True
    assert data["candidate_assets"]["research_projects"][0]["target_id"] == "rp_aaaaaaaaaaaa"
    assert data["candidate_assets"]["research_projects"][0]["project_asset_summary"]["evidence_count"] == 1
    assert data["candidate_assets"]["evidence"][0]["target_id"] == "rp_aaaaaaaaaaaa:ev_harness"
    assert data["candidate_assets"]["evidence"][0]["parent_research_project_id"] == "rp_aaaaaaaaaaaa"
    assert data["candidate_assets"]["evidence"][0]["parent_research_project_title"] == "Agent Harness 战略研究"
    assert data["candidate_assets"]["evidence"][0]["source_path_display"].endswith("rp_aaaaaaaaaaaa.json")
    assert data["candidate_assets"]["insights"][0]["target_type"] == "insight"
    assert data["candidate_assets"]["notes"][0]["target_type"] == "note"
    assert data["candidate_assets"]["artifacts"][0]["target_type"] == "artifact"
    assert data["counts"]["direct_kfc_theme_count"] == 0
    assert data["counts"]["indirect_article_count"] == 1
    assert data["counts"]["candidate_high_count"] >= 1
    assert data["counts"]["candidate_medium_count"] >= 0
    assert data["counts"]["candidate_low_count"] >= 0
    assert data["formal_empty_state"]["kfc_theme"]["candidate_count"] == 1
    assert data["formal_empty_state"]["research_project"]["candidate_count"] == 1
    assert data["warnings"][-1]["type"] == "no_formal_kfc_asset_links"
    assert sorted(path.name for path in link_dir.glob("*.json")) == link_before
    assert sorted(path.name for path in sources["research_dir"].glob("*.json")) == research_before


def test_asset_index_returns_state_aware_formal_and_derived_assets(topic_cluster_client, monkeypatch, tmp_path):
    client, cluster_dir, link_dir = topic_cluster_client
    sources = _seed_asset_index_sources(tmp_path, monkeypatch)
    _seed_asset_index_cluster(cluster_dir, link_dir)
    _write_json(
        link_dir / "tcl_agent_index_theme.json",
        {
            "link_id": "tcl_agent_index_theme",
            "cluster_id": "tc_agent_index",
            "target_type": "kfc_theme",
            "target_id": "gtheme_agent_harness",
            "target_title": "Agent Harness 执行治理",
            "role": "supporting",
            "status": "accepted",
            "rationale": "覆盖 Agent Harness、权限审批和执行审计。",
            "created_at": "2026-05-14T10:00:00+08:00",
        },
    )
    _write_json(
        link_dir / "tcl_agent_index_project.json",
        {
            "link_id": "tcl_agent_index_project",
            "cluster_id": "tc_agent_index",
            "target_type": "research_project",
            "target_id": "rp_aaaaaaaaaaaa",
            "target_title": "Agent Harness 战略研究",
            "role": "supporting",
            "status": "needs_review",
            "rationale": "已显式关联到现有研究项目。",
        },
    )
    link_before = sorted(path.name for path in link_dir.glob("*.json"))
    research_before = sorted(path.name for path in sources["research_dir"].glob("*.json"))

    resp = client.get("/api/topic-clusters/tc_agent_index/asset-index")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    formal_theme = data["formal_assets"]["kfc_themes"][0]
    assert formal_theme["target_id"] == "gtheme_agent_harness"
    assert formal_theme["relation_state"] == "linked"
    assert formal_theme["link_record"]["link_id"] == "tcl_agent_index_theme"
    assert formal_theme["supported_actions"] == ["view_detail", "open_theme_hub", "view_link_record", "unlink_theme"]
    assert formal_theme["member_concepts"][0]["entry_id"] == "canon_agent_harness"
    formal_project = data["formal_assets"]["research_projects"][0]
    assert formal_project["target_id"] == "rp_aaaaaaaaaaaa"
    assert formal_project["relation_state"] == "linked"
    assert formal_project["project_asset_summary"]["evidence_count"] == 1
    derived_concept = data["derived_assets"]["concepts"][0]
    assert derived_concept["target_id"] == "canon_agent_harness"
    assert derived_concept["relation_state"] == "derived_from_linked_theme"
    assert derived_concept["promotion_supported"] is False
    assert "add_to_current_project_concept_basket" in derived_concept["supported_actions"]
    assert data["candidate_assets"]["kfc_themes"] == []
    assert data["candidate_assets"]["research_projects"] == []
    assert data["ignored_assets"] == {"kfc_themes": [], "concepts": [], "research_projects": []}
    assert sorted(path.name for path in link_dir.glob("*.json")) == link_before
    assert sorted(path.name for path in sources["research_dir"].glob("*.json")) == research_before


def test_asset_index_degrades_when_optional_sources_are_missing(topic_cluster_client, monkeypatch, tmp_path):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_asset_index_cluster(cluster_dir, link_dir)
    monkeypatch.setattr(TopicClusterAssetIndexService, "THEMES_PATH", tmp_path / "missing_themes.json")
    monkeypatch.setattr(TopicClusterAssetIndexService, "CONCEPTS_PATH", tmp_path / "missing_concepts.json")
    monkeypatch.setattr(TopicClusterAssetIndexService, "RESEARCH_PROJECT_DIR", tmp_path / "missing_research_projects")
    monkeypatch.setattr(TopicClusterAssetIndexService, "NOTES_DIR", tmp_path / "missing_notes")

    resp = client.get("/api/topic-clusters/tc_agent_index/asset-index")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["candidate_assets"]["kfc_themes"] == []
    assert data["candidate_assets"]["concepts"] == []
    assert data["candidate_assets"]["research_projects"] == []
    warning_types = {item["type"] for item in data["warnings"]}
    assert "themes_source_missing" in warning_types
    assert "concepts_source_missing" in warning_types
    assert "research_projects_source_missing" in warning_types
    assert "notes_source_missing" in warning_types


def test_asset_index_does_not_execute_external_process(topic_cluster_client, monkeypatch, tmp_path):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_asset_index_sources(tmp_path, monkeypatch)
    _seed_asset_index_cluster(cluster_dir, link_dir)

    def fail(*args, **kwargs):
        raise AssertionError("external process must not be started")

    monkeypatch.setattr("subprocess.run", fail)
    monkeypatch.setattr("subprocess.Popen", fail)
    monkeypatch.setattr("os.system", fail)

    resp = client.get("/api/topic-clusters/tc_agent_index/asset-index")

    assert resp.status_code == 200
    assert resp.get_json()["data"]["candidate_assets"]["research_projects"][0]["target_id"] == "rp_aaaaaaaaaaaa"


def test_create_topic_cluster_generates_id_and_defaults(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client

    resp = client.post("/api/topic-clusters", json={"title": "Manual Cluster"})

    assert resp.status_code == 201
    cluster = resp.get_json()["data"]["cluster"]
    assert cluster["cluster_id"].startswith("tc_")
    assert cluster["status"] == "candidate"
    assert cluster["strategic_relevance"] == "unknown"
    assert (cluster_dir / f"{cluster['cluster_id']}.json").exists()
    assert "\n  " in (cluster_dir / f"{cluster['cluster_id']}.json").read_text(encoding="utf-8")


def test_create_topic_cluster_rejects_duplicate_and_path_traversal(topic_cluster_client):
    client, _, _ = topic_cluster_client

    first = client.post("/api/topic-clusters", json={"cluster_id": "tc_manual", "title": "Manual"})
    assert first.status_code == 201

    duplicate = client.post("/api/topic-clusters", json={"cluster_id": "tc_manual", "title": "Manual"})
    assert duplicate.status_code == 409
    assert duplicate.get_json()["code"] == "duplicate_cluster"

    bad = client.post("/api/topic-clusters", json={"cluster_id": "../evil", "title": "Bad"})
    assert bad.status_code == 400


def test_patch_topic_cluster_preserves_fields_and_rejects_immutable(topic_cluster_client):
    client, _, _ = topic_cluster_client
    created = client.post(
        "/api/topic-clusters",
        json={"cluster_id": "tc_manual", "title": "Old", "description": "Keep", "status": "candidate"},
    ).get_json()["data"]["cluster"]

    resp = client.patch("/api/topic-clusters/tc_manual", json={"title": "New", "status": "active"})

    assert resp.status_code == 200
    cluster = resp.get_json()["data"]["cluster"]
    assert cluster["title"] == "New"
    assert cluster["description"] == "Keep"
    assert cluster["created_at"] == created["created_at"]
    assert cluster["updated_at"] >= created["updated_at"]

    immutable = client.patch("/api/topic-clusters/tc_manual", json={"cluster_id": "tc_other"})
    assert immutable.status_code == 400


def test_create_link_validates_and_returns_unresolved_warning(topic_cluster_client):
    client, _, link_dir = topic_cluster_client
    client.post("/api/topic-clusters", json={"cluster_id": "tc_manual", "title": "Manual"})

    resp = client.post(
        "/api/topic-clusters/tc_manual/links",
        json={
            "target_type": "wiki_topic",
            "target_id": "missing-topic",
            "target_title": "Missing Topic",
            "role": "primary",
            "status": "candidate",
            "source": "candidate_promotion",
            "review_decision": {
                "decision": "accepted",
                "reviewed_by": "human",
                "reason": "visible in candidate review",
            },
        },
    )

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["link"]["link_id"].startswith("tcl_")
    assert data["link"]["cluster_id"] == "tc_manual"
    assert data["link"]["source"] == "candidate_promotion"
    assert data["link"]["review_decision"]["decision"] == "accepted"
    assert data["warnings"][0]["code"] == "target_unresolved"
    assert (link_dir / f"{data['link']['link_id']}.json").exists()

    invalid = client.post(
        "/api/topic-clusters/tc_manual/links",
        json={"target_type": "bad", "target_id": "x"},
    )
    assert invalid.status_code == 400


def test_create_link_rejects_duplicate_active_link(topic_cluster_client):
    client, _, _ = topic_cluster_client
    client.post("/api/topic-clusters", json={"cluster_id": "tc_manual", "title": "Manual"})
    payload = {"target_type": "kfc_theme", "target_id": "gtheme_agent"}

    assert client.post("/api/topic-clusters/tc_manual/links", json=payload).status_code == 201
    duplicate = client.post("/api/topic-clusters/tc_manual/links", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.get_json()["code"] == "duplicate_link"


def test_patch_and_delete_topic_cluster_link(topic_cluster_client):
    client, _, link_dir = topic_cluster_client
    client.post("/api/topic-clusters", json={"cluster_id": "tc_manual", "title": "Manual"})
    created = client.post(
        "/api/topic-clusters/tc_manual/links",
        json={"target_type": "wiki_topic", "target_id": "agent-harness"},
    ).get_json()["data"]["link"]
    link_id = created["link_id"]

    patched = client.patch(
        f"/api/topic-cluster-links/{link_id}",
        json={"role": "supporting", "status": "accepted", "rationale": "Reviewed"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["link"]["role"] == "supporting"

    immutable = client.patch(f"/api/topic-cluster-links/{link_id}", json={"target_id": "other"})
    assert immutable.status_code == 400

    deleted = client.delete(f"/api/topic-cluster-links/{link_id}")
    assert deleted.status_code == 200
    saved = json.loads((link_dir / f"{link_id}.json").read_text(encoding="utf-8"))
    assert saved["deleted"] is True

    detail = client.get("/api/topic-clusters/tc_manual")
    assert detail.get_json()["data"]["cluster"]["counts"]["wiki_topics"] == 0


def _refresh_payload(**overrides):
    payload = {
        "scope": "all",
        "inputs": {
            "include_wiki_topics": True,
            "include_kfc_themes": True,
            "include_kfc_concepts": False,
            "include_research_projects": False,
        },
    }
    payload.update(overrides)
    return payload


def test_create_refresh_request_sidecar_with_safety_rules(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client

    resp = client.post("/api/topic-clusters/refresh-requests", json=_refresh_payload())

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["request_id"].startswith("tcr_")
    assert data["status"] == "requested"
    assert data["rules"]["proposal_only"] is True
    assert data["rules"]["do_not_auto_apply"] is True
    assert data["rules"]["kfc_must_not_execute_model"] is True
    assert data["rules"]["kfc_must_not_start_external_process"] is True
    assert (cluster_dir.parent / "topic_cluster_refresh_requests" / f"{data['request_id']}.json").exists()


def test_create_refresh_request_rejects_invalid_payloads(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client

    cases = [
        _refresh_payload(scope="selected"),
        _refresh_payload(scope="wiki_topic"),
        _refresh_payload(inputs={"include_wiki_topics": "yes"}),
        _refresh_payload(
            inputs={
                "include_wiki_topics": True,
                "include_kfc_themes": True,
                "include_kfc_concepts": False,
                "include_research_projects": False,
                "run_model": True,
            }
        ),
        _refresh_payload(
            inputs={
                "include_wiki_topics": False,
                "include_kfc_themes": False,
                "include_kfc_concepts": False,
                "include_research_projects": False,
            }
        ),
        {**_refresh_payload(), "status": "running_external"},
    ]

    for payload in cases:
        resp = client.post("/api/topic-clusters/refresh-requests", json=payload)
        assert resp.status_code == 400
    assert not (cluster_dir.parent / "topic_cluster_refresh_requests").exists()


def test_create_topic_scoped_refresh_request_sidecar(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client

    payload = _refresh_payload(
        scope="wiki_topic",
        topic_id="cloud-data-ai-platform",
        topic_title="Cloud Data and AI Platform",
        suggested_title="AI-native Data Platform",
        rationale="Human requested a new cluster proposal.",
        source="wiki_topic_cluster_coverage",
    )
    resp = client.post("/api/topic-clusters/refresh-requests", json=payload)

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["scope"] == "wiki_topic"
    assert data["topic_id"] == "cloud-data-ai-platform"
    assert data["suggested_title"] == "AI-native Data Platform"
    assert data["rules"]["proposal_only"] is True
    assert (cluster_dir.parent / "topic_cluster_refresh_requests" / f"{data['request_id']}.json").exists()


def test_list_and_get_refresh_requests(topic_cluster_client):
    client, _, _ = topic_cluster_client
    first = client.post("/api/topic-clusters/refresh-requests", json=_refresh_payload()).get_json()["data"]
    second = client.post("/api/topic-clusters/refresh-requests", json=_refresh_payload()).get_json()["data"]

    list_resp = client.get("/api/topic-clusters/refresh-requests")
    assert list_resp.status_code == 200
    items = list_resp.get_json()["data"]["items"]
    assert [item["request_id"] for item in items] == [second["request_id"], first["request_id"]]

    get_resp = client.get(f"/api/topic-clusters/refresh-requests/{first['request_id']}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["data"]["request_id"] == first["request_id"]

    missing = client.get("/api/topic-clusters/refresh-requests/tcr_20260512_missing")
    assert missing.status_code == 404


def test_create_refresh_request_does_not_execute_any_runner(topic_cluster_client, monkeypatch):
    client, _, _ = topic_cluster_client

    def fail(*args, **kwargs):
        raise AssertionError("external process must not be started")

    monkeypatch.setattr("subprocess.run", fail)
    monkeypatch.setattr("subprocess.Popen", fail)
    monkeypatch.setattr("os.system", fail)

    resp = client.post("/api/topic-clusters/refresh-requests", json=_refresh_payload())

    assert resp.status_code == 201
    assert resp.get_json()["data"]["status"] == "requested"


def _write_proposal(root, payload):
    path = root / "topic_cluster_proposals" / f"{payload['proposal_id']}.json"
    _write_json(path, payload)
    return path


def _proposal_payload():
    return {
        "proposal_id": "tcp_sample",
        "request_id": "tcr_20260512_001",
        "status": "ready_for_review",
        "created_at": "2026-05-12T10:00:00",
        "summary": {"new_clusters": 1, "candidate_links": 1},
        "warnings": [{"code": "review_merge", "message": "Review merge manually"}],
        "actions": [
            {
                "action_id": "create_cluster:tc_proposed",
                "action_type": "create_cluster",
                "confidence": 0.86,
                "rationale": "Candidate strategic cluster",
                "payload": {
                    "cluster_id": "tc_proposed",
                    "title": "Proposed Cluster",
                    "description": "Created from proposal",
                    "status": "candidate",
                    "strategic_relevance": "high",
                },
            },
            {
                "action_id": "add_link:tcl_proposed",
                "action_type": "add_link",
                "confidence": 0.78,
                "rationale": "Candidate supporting topic",
                "payload": {
                    "link_id": "tcl_proposed",
                    "cluster_id": "tc_proposed",
                    "target_type": "wiki_topic",
                    "target_id": "agent-harness",
                    "target_title": "Agent Harness",
                    "role": "supporting",
                    "status": "candidate",
                },
            },
            {
                "action_id": "merge_cluster:tc_old->tc_new",
                "action_type": "merge_cluster",
                "confidence": 0.4,
                "rationale": "Review only",
                "payload": {"from_cluster_id": "tc_old", "to_cluster_id": "tc_new"},
            },
        ],
    }


def test_list_and_get_topic_cluster_proposals(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client
    _write_proposal(cluster_dir.parent, _proposal_payload())

    list_resp = client.get("/api/topic-clusters/proposals")
    assert list_resp.status_code == 200
    item = list_resp.get_json()["data"]["items"][0]
    assert item["proposal_id"] == "tcp_sample"
    assert item["action_count"] == 3
    assert item["supported_action_count"] == 2
    assert item["unsupported_action_count"] == 1
    assert item["warning_count"] == 1

    detail_resp = client.get("/api/topic-clusters/proposals/tcp_sample")
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()["data"]
    assert len(detail["proposal"]["actions"]) == 3
    assert detail["applications"] == []


def test_apply_selected_create_cluster_and_add_link(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _write_proposal(cluster_dir.parent, _proposal_payload())

    resp = client.post(
        "/api/topic-clusters/proposals/tcp_sample/apply",
        json={
            "accepted_actions": ["create_cluster:tc_proposed", "add_link:tcl_proposed"],
            "rejected_actions": ["merge_cluster:tc_old->tc_new"],
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["created_cluster_ids"] == ["tc_proposed"]
    assert data["created_link_ids"] == ["tcl_proposed"]
    assert (cluster_dir / "tc_proposed.json").exists()
    assert (link_dir / "tcl_proposed.json").exists()
    assert (cluster_dir.parent / "topic_cluster_proposal_applications" / f"{data['application_id']}.json").exists()
    assert not (cluster_dir.parent / "research_projects").exists()


def test_apply_selected_never_applies_all_by_default(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client
    proposal = _proposal_payload()
    proposal["actions"].append(
        {
            "action_id": "create_cluster:tc_not_selected",
            "action_type": "create_cluster",
            "payload": {"cluster_id": "tc_not_selected", "title": "Not Selected"},
        }
    )
    _write_proposal(cluster_dir.parent, proposal)

    resp = client.post(
        "/api/topic-clusters/proposals/tcp_sample/apply",
        json={"accepted_actions": ["create_cluster:tc_proposed"], "rejected_actions": []},
    )

    assert resp.status_code == 200
    assert (cluster_dir / "tc_proposed.json").exists()
    assert not (cluster_dir / "tc_not_selected.json").exists()


def test_apply_proposal_rejects_unsupported_or_unknown_actions(topic_cluster_client):
    client, cluster_dir, _ = topic_cluster_client
    _write_proposal(cluster_dir.parent, _proposal_payload())

    unsupported = client.post(
        "/api/topic-clusters/proposals/tcp_sample/apply",
        json={"accepted_actions": ["merge_cluster:tc_old->tc_new"], "rejected_actions": []},
    )
    assert unsupported.status_code == 400

    unknown = client.post(
        "/api/topic-clusters/proposals/tcp_sample/apply",
        json={"accepted_actions": ["create_cluster:missing"], "rejected_actions": []},
    )
    assert unknown.status_code == 400

    overlap = client.post(
        "/api/topic-clusters/proposals/tcp_sample/apply",
        json={
            "accepted_actions": ["create_cluster:tc_proposed"],
            "rejected_actions": ["create_cluster:tc_proposed"],
        },
    )
    assert overlap.status_code == 400
    assert not (cluster_dir / "tc_proposed.json").exists()


def test_apply_proposal_preserves_existing_cluster_and_link(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _write_proposal(cluster_dir.parent, _proposal_payload())
    _write_json(
        cluster_dir / "tc_proposed.json",
        {"cluster_id": "tc_proposed", "title": "Human title", "status": "active"},
    )
    _write_json(
        link_dir / "tcl_proposed.json",
        {
            "link_id": "tcl_proposed",
            "cluster_id": "tc_proposed",
            "target_type": "wiki_topic",
            "target_id": "agent-harness",
            "target_title": "Agent Harness",
            "role": "primary",
            "status": "accepted",
        },
    )

    resp = client.post(
        "/api/topic-clusters/proposals/tcp_sample/apply",
        json={
            "accepted_actions": ["create_cluster:tc_proposed", "add_link:tcl_proposed"],
            "rejected_actions": [],
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["skipped_existing_cluster_ids"] == ["tc_proposed"]
    assert data["skipped_existing_link_ids"] == ["tcl_proposed"]
    assert json.loads((cluster_dir / "tc_proposed.json").read_text(encoding="utf-8"))["title"] == "Human title"
    assert json.loads((link_dir / "tcl_proposed.json").read_text(encoding="utf-8"))["status"] == "accepted"


def test_create_material_slice_creates_promotion_with_traceability(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)

    resp = client.post("/api/topic-clusters/tc_promotion/material-slices", json=_slice_payload())

    assert resp.status_code == 201
    data = resp.get_json()["data"]
    material_slice = data["slice"]
    promotion = data["promotion"]
    assert material_slice["slice_id"].startswith("ms_")
    assert material_slice["slice_type"] == "concept_lead"
    assert material_slice["source_article_id"] == "src_agent_harness"
    assert material_slice["source_markdown_path"].endswith("agent-harness.md")
    assert material_slice["source_content_hash"] == "sha256:agentharness"
    assert material_slice["source_quote"]
    assert material_slice["linked_topic_cluster"] == "tc_promotion"
    assert material_slice["created_from"] == "topic_cluster_detail.article_card"
    assert material_slice["review_status"] == "promoted"
    assert promotion["promotion_id"].startswith("lp_")
    assert promotion["slice_id"] == material_slice["slice_id"]
    assert promotion["lead_type"] == "concept_lead"
    assert promotion["review_status"] == "pending"
    assert (cluster_dir.parent / "material_slices" / f"{material_slice['slice_id']}.json").exists()
    assert (cluster_dir.parent / "lead_promotions" / f"{promotion['promotion_id']}.json").exists()


def test_get_promotion_basket_lists_cluster_promotions_only(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    _create_promotion(client)
    _write_json(
        cluster_dir / "tc_other.json",
        {"cluster_id": "tc_other", "title": "Other", "status": "active"},
    )
    client.post("/api/topic-clusters/tc_other/material-slices", json=_slice_payload(title="Other Lead"))

    resp = client.get("/api/topic-clusters/tc_promotion/promotion-basket")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["cluster_id"] == "tc_promotion"
    assert data["counts"]["pending"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["title"] == "代码知识图谱"
    assert item["source"]["source_article_id"] == "src_agent_harness"
    assert "代码知识图谱把 AST" in item["source_quote"]
    assert "Markdown 原文" not in json.dumps(item, ensure_ascii=False)


def test_apply_link_existing_registry_entry_writes_relation_and_change_log(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    _slice, promotion = _create_promotion(client)
    registry_path = cluster_dir.parent / "uploads" / "projects" / "concept_registry.json"
    _write_json(registry_path, {"entries": {}})
    before = registry_path.read_text(encoding="utf-8")

    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={
            "action": "link_existing_registry_entry",
            "target": {
                "registry_entry_id": "canon_code_knowledge_graph",
                "registry_entry_label": "代码知识图谱",
            },
            "note": "人工确认已有条目",
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["review_status"] == "linked"
    assert data["decision"] == "link_existing_registry_entry"
    assert data["target"]["target_type"] == "concept_registry_entry"
    assert data["target"]["target_id"] == "canon_code_knowledge_graph"
    assert data["action_history"][-1]["note"] == "人工确认已有条目"
    assert registry_path.read_text(encoding="utf-8") == before
    relations = list((cluster_dir.parent / "kfc_asset_relations").glob("rel_*.json"))
    assert len(relations) == 1
    relation = json.loads(relations[0].read_text(encoding="utf-8"))
    assert relation["target_id"] == "canon_code_knowledge_graph"
    assert relation["relation_type"] == "mention"
    assert relation["source_quote"].startswith("代码知识图谱把 AST")
    changes = (cluster_dir.parent / "kfc_change_log" / "kfc_changes.jsonl").read_text(encoding="utf-8")
    assert "link_lead_to_existing_concept" in changes


def test_article_processing_review_unifies_leads_relations_and_review_trail(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    material_slice, promotion = _create_promotion(client)
    resp = client.post(
        "/api/topic-clusters/tc_promotion/relation-candidates",
        json={
            "relation_candidate_id": "relcand_agent_context",
            "source_article_id": "src_agent_harness",
            "source_title": "AI 还在猜代码？",
            "source_quote": "代码知识图谱把 AST、调用关系和语义线索组织为可检索上下文。",
            "subject_concept": "代码知识图谱",
            "relation_type": "supports",
            "object_concept": "Agent Harness",
            "why_relation_exists": "文章把代码知识图谱描述为 Harness 的上下文组织方式。",
            "possible_alternative_relation_types": [{"type": "enables", "reason": "偏能力支撑"}],
        },
    )
    assert resp.status_code == 201

    changed = client.post(
        "/api/topic-clusters/tc_promotion/relation-candidates/relcand_agent_context/actions",
        json={"action": "change_relation_type", "relation_type": "enables", "note": "关系类型更贴近原文"},
    )
    assert changed.status_code == 200

    reviewed_quote = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={"action": "review_quote", "quote_status": "weak", "note": "quote 需要更具体上下文"},
    )
    assert reviewed_quote.status_code == 200

    review = client.get("/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review")
    assert review.status_code == 200
    data = review.get_json()["data"]
    assert data["summary"]["concept_leads"] == 1
    assert data["summary"]["relation_candidates"] == 1
    assert data["summary"]["needs_review"] == 2
    assert data["summary"]["high_risk"] == 2
    cards = {item["candidate_type"]: item for item in data["candidate_cards"]}
    assert cards["concept_lead"]["candidate_id"] == promotion["promotion_id"]
    assert cards["concept_lead"]["quote_review"]["status"] == "weak"
    assert cards["concept_lead"]["quote"] == material_slice["source_quote"]
    assert cards["relation_candidate"]["relation_type"] == "enables"
    assert cards["relation_candidate"]["status"] == "needs_revision"
    assert data["provenance"]["review_trail_source"] == "backend/data/kfc_change_log/kfc_changes.jsonl"
    changes = (cluster_dir.parent / "kfc_change_log" / "kfc_changes.jsonl").read_text(encoding="utf-8")
    assert "quote_review_updated" in changes
    assert "relation_candidate_change_relation_type" in changes


def test_article_processing_review_p1_groups_completion_and_batch_actions(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    concept_resp = client.post(
        "/api/topic-clusters/tc_promotion/material-slices",
        json=_slice_payload(
            title="高置信 Agent Harness",
            confidence=0.88,
            source_quote="Agent Harness 通过权限审批和回滚机制降低上线风险。",
            create_promotion=True,
        ),
    )
    assert concept_resp.status_code == 201
    concept = concept_resp.get_json()["data"]["promotion"]
    evidence_resp = client.post(
        "/api/topic-clusters/tc_promotion/material-slices",
        json=_slice_payload(
            slice_type="evidence_slice",
            title="审计证据片段",
            confidence=0.74,
            source_quote="执行治理需要审计记录、权限审批和回滚链路。",
            create_promotion=True,
        ),
    )
    assert evidence_resp.status_code == 201
    evidence = evidence_resp.get_json()["data"]["promotion"]
    weak_evidence_resp = client.post(
        "/api/topic-clusters/tc_promotion/material-slices",
        json=_slice_payload(
            slice_type="evidence_slice",
            title="弱证据片段",
            confidence=0.58,
            source_quote="",
            source_context="只有宽泛背景，需要人工核对。",
            create_promotion=True,
        ),
    )
    assert weak_evidence_resp.status_code == 201
    weak_evidence = weak_evidence_resp.get_json()["data"]["promotion"]
    rel_resp = client.post(
        "/api/topic-clusters/tc_promotion/relation-candidates",
        json={
            "relation_candidate_id": "relcand_p1_weak",
            "source_article_id": "src_agent_harness",
            "source_title": "AI 还在猜代码？",
            "source_context": "缺少明确 quote 的弱关系候选。",
            "subject_concept": "Agent Harness",
            "relation_type": "supports",
            "object_concept": "上线治理",
            "why_relation_exists": "仅从上下文弱推导出的关系。",
            "confidence": 0.55,
        },
    )
    assert rel_resp.status_code == 201

    review = client.get("/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review")
    assert review.status_code == 200
    data = review.get_json()["data"]
    group_counts = {group["group_id"]: group["count"] for group in data["review_groups"]}
    assert group_counts["pending_review"] == 4
    assert group_counts["high_confidence_quick_confirm"] == 1
    assert group_counts["low_confidence_manual_judgment"] >= 2
    assert group_counts["weak_quote_review"] >= 2
    assert group_counts["relation_pending"] == 1
    assert data["summary"]["total_candidates"] == 4
    assert data["summary"]["pending_count"] == 4
    assert data["summary"]["completion_status"] == "at_risk"
    cards = {card["card_id"]: card for card in data["candidate_cards"]}
    assert cards[concept["promotion_id"]]["candidate_kind"] == "concept"
    assert cards[concept["promotion_id"]]["confidence_bucket"] == "high"
    assert cards[concept["promotion_id"]]["batch_action_types"] == ["confirm_high_confidence_concepts"]
    assert cards[evidence["promotion_id"]]["candidate_kind"] == "evidence"
    assert "mark_evidence_reviewed" in cards[evidence["promotion_id"]]["batch_action_types"]
    assert cards[weak_evidence["promotion_id"]]["needs_quote_review"] is True
    assert "weak_quote" in cards["relcand_p1_weak"]["risk_flags"]
    assert "reject_weak_relations" in cards["relcand_p1_weak"]["batch_action_types"]

    group_batch = client.post(
        "/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review/batch-actions",
        json={"action_type": "confirm_high_confidence_concepts", "group_id": "high_confidence_quick_confirm"},
    )
    assert group_batch.status_code == 400

    confirm_batch = client.post(
        "/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review/batch-actions",
        json={
            "action_type": "confirm_high_confidence_concepts",
            "card_ids": [concept["promotion_id"], weak_evidence["promotion_id"]],
            "reviewer": "local",
            "note": "P1 批量确认高置信概念",
        },
    )
    assert confirm_batch.status_code == 200
    confirm_data = confirm_batch.get_json()["data"]
    assert confirm_data["summary"] == {"requested": 2, "applied": 1, "skipped": 1}
    assert confirm_data["applied"][0]["status"] == "confirmed"
    assert confirm_data["skipped"][0]["reason"] == "not_batch_eligible"

    evidence_batch = client.post(
        "/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review/batch-actions",
        json={
            "action_type": "mark_evidence_reviewed",
            "card_ids": [evidence["promotion_id"]],
            "reviewer": "local",
        },
    )
    assert evidence_batch.status_code == 200
    assert evidence_batch.get_json()["data"]["applied"][0]["status"] == "reviewed"

    relation_batch = client.post(
        "/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review/batch-actions",
        json={
            "action_type": "reject_weak_relations",
            "card_ids": ["relcand_p1_weak"],
            "reviewer": "local",
        },
    )
    assert relation_batch.status_code == 200
    assert relation_batch.get_json()["data"]["applied"][0]["status"] == "rejected"

    after = client.get("/api/topic-clusters/tc_promotion/articles/src_agent_harness/processing-review").get_json()["data"]
    after_groups = {group["group_id"]: group["count"] for group in after["review_groups"]}
    assert after["summary"]["reviewed_count"] == 3
    assert after["summary"]["rejected_count"] == 1
    assert after["summary"]["pending_count"] == 1
    assert after_groups["processed"] == 3
    assert after["review_trail"]["total"] >= 3
    trail_actions = [item["action_type"] for item in after["review_trail"]["compact_items"]]
    assert "confirm_review" in trail_actions
    assert "mark_reviewed" in trail_actions
    assert "reject" in trail_actions
    assert all(item["action_id"] for item in after["review_trail"]["compact_items"][:3])
    changes = (cluster_dir.parent / "kfc_change_log" / "kfc_changes.jsonl").read_text(encoding="utf-8")
    assert "confirm_review" in changes
    assert "mark_reviewed" in changes
    assert "relation_candidate_reject" in changes


def test_switch_registry_match_persists_action_without_mutating_source_slice(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    material_slice, promotion = _create_promotion(
        client,
    )
    slice_path = cluster_dir.parent / "material_slices" / f"{material_slice['slice_id']}.json"
    before_slice = slice_path.read_text(encoding="utf-8")

    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={
            "action": "switch_registry_match",
            "target": {
                "registry_entry_id": "canon_context_engineering",
                "registry_entry_label": "Context Engineering",
            },
            "note": "原匹配过宽，切到更窄概念。",
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["decision"] == "switch_registry_match"
    assert data["action_history"][-1]["action"] == "switch_registry_match"
    assert data["target"]["target_id"] == "canon_context_engineering"
    assert slice_path.read_text(encoding="utf-8") == before_slice
    changes = (cluster_dir.parent / "kfc_change_log" / "kfc_changes.jsonl").read_text(encoding="utf-8")
    assert "switch_registry_match" in changes


def test_deposit_as_new_concept_writes_registry_relations_and_change_log(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    material_slice, promotion = _create_promotion(client)
    project_dir = cluster_dir.parent / "research_projects"
    _write_json(
        project_dir / "rp_aaaaaaaaaaaa.json",
        {
            "id": "rp_aaaaaaaaaaaa",
            "title": "Agent-ready 战略研究",
            "status": "active",
            "evidence_items": [],
        },
    )
    # Attach current project context to the slice/promotion for relation writing.
    slice_path = cluster_dir.parent / "material_slices" / f"{material_slice['slice_id']}.json"
    slice_doc = json.loads(slice_path.read_text(encoding="utf-8"))
    slice_doc["linked_research_project"] = "rp_aaaaaaaaaaaa"
    _write_json(slice_path, slice_doc)
    promotion_path = cluster_dir.parent / "lead_promotions" / f"{promotion['promotion_id']}.json"
    promotion_doc = json.loads(promotion_path.read_text(encoding="utf-8"))
    promotion_doc["linked_research_project"] = "rp_aaaaaaaaaaaa"
    _write_json(promotion_path, promotion_doc)

    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={
            "action": "deposit_as_new_concept",
            "concept": {
                "label": "代码知识图谱",
                "definition": "代码语义、AST 与调用关系的图谱化表达。",
                "aliases": ["Code Knowledge Graph"],
            },
            "created_by": "system",
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["review_status"] == "materialized_concept"
    assert data["target"]["target_type"] == "concept_registry_entry"
    concept_id = data["concept"]["concept_id"]
    registry = json.loads((cluster_dir.parent / "uploads" / "projects" / "concept_registry.json").read_text(encoding="utf-8"))
    concept = registry["entries"][concept_id]
    assert concept["lifecycle_status"] == "active"
    assert concept["quality_state"] == "machine_generated"
    assert concept["review_state"] == "unreviewed"
    assert concept["source_article_id"] == "src_agent_harness"
    assert concept["source_quote"].startswith("代码知识图谱把 AST")
    assert concept["source_content_hash"] == "sha256:agentharness"
    assert concept["source_material_slice_id"] == material_slice["slice_id"]
    assert concept["linked_topic_cluster_ids"] == ["tc_promotion"]
    assert concept["linked_research_project_ids"] == ["rp_aaaaaaaaaaaa"]
    relations = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (cluster_dir.parent / "kfc_asset_relations").glob("rel_*.json")
    ]
    relation_pairs = {(item["source_type"], item["target_type"]) for item in relations}
    assert ("article", "concept_registry_entry") in relation_pairs
    assert ("concept_registry_entry", "topic_cluster") in relation_pairs
    assert ("concept_registry_entry", "research_project") in relation_pairs
    assert ("concept_registry_entry", "material_slice") in relation_pairs
    changes = client.get("/api/topic-clusters/tc_promotion/promotion-changes")
    assert changes.status_code == 200
    assert changes.get_json()["data"]["items"][0]["action"] == "create_concept_from_lead"


def test_apply_create_new_registry_candidate_writes_candidate_sidecar(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    material_slice, promotion = _create_promotion(client)

    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={
            "action": "create_new_registry_candidate",
            "candidate": {
                "label": "代码知识图谱",
                "proposed_key": "code-knowledge-graph",
                "description": "代码语义、AST 与调用关系的图谱化表达。",
                "aliases": ["Code Knowledge Graph"],
            },
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["review_status"] == "candidate_created"
    candidate_id = data["candidate"]["candidate_id"]
    candidate_path = cluster_dir.parent / "concept_registry_candidates" / f"{candidate_id}.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert candidate["source_slice_id"] == material_slice["slice_id"]
    assert candidate["source_promotion_id"] == promotion["promotion_id"]
    assert candidate["source_article_id"] == "src_agent_harness"
    assert candidate["source_content_hash"] == "sha256:agentharness"
    assert candidate["linked_topic_cluster"] == "tc_promotion"
    assert candidate["review_status"] == "proposed"


def test_apply_add_as_project_evidence_links_slice_to_research_project(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    material_slice, promotion = _create_promotion(client)
    project_dir = cluster_dir.parent / "research_projects"
    _write_json(
        project_dir / "rp_aaaaaaaaaaaa.json",
        {
            "id": "rp_aaaaaaaaaaaa",
            "title": "Agent-ready 战略研究",
            "status": "active",
            "evidence_items": [],
        },
    )

    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={
            "action": "add_as_project_evidence",
            "target": {"research_project_id": "rp_aaaaaaaaaaaa"},
            "evidence": {"claim": "代码知识图谱可以作为 Agent Harness 的上下文组织方式。"},
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["review_status"] == "added_to_project_evidence"
    assert data["target"]["target_id"] == "rp_aaaaaaaaaaaa"
    project = json.loads((project_dir / "rp_aaaaaaaaaaaa.json").read_text(encoding="utf-8"))
    evidence = project["evidence_items"][0]
    assert evidence["evidence_type"] == "quote"
    assert evidence["status"] == "active"
    assert evidence["quality_state"] == "human_selected"
    assert evidence["review_state"] == "unreviewed"
    assert evidence["source_slice_id"] == material_slice["slice_id"]
    assert evidence["linked_material_slice_id"] == material_slice["slice_id"]
    assert evidence["source_promotion_id"] == promotion["promotion_id"]
    assert evidence["source_article_id"] == "src_agent_harness"
    assert evidence["source_markdown_path"].endswith("agent-harness.md")
    assert evidence["source_content_hash"] == "sha256:agentharness"
    assert evidence["source_quote"].startswith("代码知识图谱把 AST")
    assert evidence["linked_topic_cluster"] == "tc_promotion"
    changes = (cluster_dir.parent / "kfc_change_log" / "kfc_changes.jsonl").read_text(encoding="utf-8")
    assert "add_lead_as_project_evidence" in changes


def test_apply_ignore_promotion_preserves_trace_and_sets_ignored(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    material_slice, promotion = _create_promotion(client)

    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={"action": "ignore", "reason": "太泛，不进入 KFC"},
    )

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["review_status"] == "ignored"
    assert data["decision"] == "ignore"
    assert data["action_history"][-1]["reason"] == "太泛，不进入 KFC"
    changes = (cluster_dir.parent / "kfc_change_log" / "kfc_changes.jsonl").read_text(encoding="utf-8")
    assert "ignore_lead" in changes
    assert (cluster_dir.parent / "material_slices" / f"{material_slice['slice_id']}.json").exists()
    trace = client.get(f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}")
    assert trace.status_code == 200
    assert trace.get_json()["data"]["trace"]["slice_id"] == material_slice["slice_id"]


def test_concept_governance_update_deprecate_and_unlink(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)
    _material_slice, promotion = _create_promotion(client)
    created = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={"action": "deposit_as_new_concept", "concept": {"label": "代码知识图谱"}},
    ).get_json()["data"]
    concept_id = created["concept"]["concept_id"]

    patched = client.patch(
        f"/api/topic-clusters/kfc-concepts/{concept_id}",
        json={"definition": "人工修正后的定义。", "quality_state": "corrected", "review_state": "reviewed"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["definition"] == "人工修正后的定义。"
    assert patched.get_json()["data"]["quality_state"] == "corrected"

    unlinked = client.delete(
        f"/api/topic-clusters/kfc-concepts/{concept_id}/relations?target_type=topic_cluster&target_id=tc_promotion"
    )
    assert unlinked.status_code == 200
    assert unlinked.get_json()["data"]["removed"][0]["deleted"] is True

    deprecated = client.post(
        f"/api/topic-clusters/kfc-concepts/{concept_id}/deprecate",
        json={"reason": "自动沉淀错误"},
    )
    assert deprecated.status_code == 200
    assert deprecated.get_json()["data"]["lifecycle_status"] == "deprecated"
    assert deprecated.get_json()["data"]["review_state"] == "disputed"


def test_low_quality_markdown_filename_is_rejected_as_concept_lead(topic_cluster_client):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)

    resp = client.post(
        "/api/topic-clusters/tc_promotion/material-slices",
        json=_slice_payload(title="SKILL.md", source_quote="一行描述定生死：让你的 Skill 命中率飙升90%的秘籍"),
    )

    assert resp.status_code == 400
    assert resp.get_json()["code"] == "low_quality_concept_lead"


def test_promotion_routes_do_not_invoke_external_workers(topic_cluster_client, monkeypatch):
    client, cluster_dir, link_dir = topic_cluster_client
    _seed_promotion_cluster(cluster_dir, link_dir)

    def fail_external(*_args, **_kwargs):
        raise AssertionError("promotion routes must not invoke external processes")

    monkeypatch.setattr(subprocess, "run", fail_external)
    monkeypatch.setattr(subprocess, "Popen", fail_external)

    _material_slice, promotion = _create_promotion(client)
    resp = client.post(
        f"/api/topic-clusters/tc_promotion/lead-promotions/{promotion['promotion_id']}/actions",
        json={"action": "ignore", "reason": "not useful"},
    )

    assert resp.status_code == 200
