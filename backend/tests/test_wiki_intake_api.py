from __future__ import annotations

import json
import sys
from pathlib import Path

from flask import Flask
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts" / "wiki_intake"))

from app.api.routes.wiki_intake import wiki_intake_bp
from app.services.topic_cluster_refresh_request_store import TopicClusterRefreshRequestStore
from app.services.topic_cluster_store import TopicClusterStore
from app.wiki_intake.store import WikiIntakeStore
from import_legacy_wiki_state import import_state


@pytest.fixture()
def wiki_intake_client(tmp_path):
    clippings = tmp_path / "Clippings"
    data_root = tmp_path / "wiki_intake"
    clippings.mkdir()
    assets = clippings / "assets"
    assets.mkdir()
    image_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00"
        b"\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (assets / "test.png").write_bytes(image_bytes)
    (assets / "encoded space.png").write_bytes(image_bytes)
    source = clippings / "agent-harness.md"
    source.write_text(
        "---\nsource_url: https://example.com/agent\nworkflow: clippings_archive\n---\n# Agent Harness\n\n正文 agent harness codex\n\n![Image](assets/test.png)",
        encoding="utf-8",
    )
    app = Flask(__name__)
    app.register_blueprint(wiki_intake_bp)
    return app.test_client(), clippings, data_root, source


def test_scan_writes_repo_local_manifest_and_keeps_clippings_readonly(wiki_intake_client, monkeypatch):
    client, clippings, data_root, source = wiki_intake_client
    before = source.read_bytes()
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)

    resp = client.post("/api/wiki-intake/scan", json={})

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["markdown_count"] == 1
    assert (data_root / "manifest.jsonl").exists()
    assert (data_root / "events.jsonl").exists()
    assert source.read_bytes() == before
    rows = [json.loads(line) for line in (data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["title"] == "Agent Harness"
    assert rows[0]["scanner_side_effects"]["modified_obsidian_source"] is False


def test_candidates_detail_and_decision_append(wiki_intake_client, monkeypatch):
    client, clippings, data_root, _ = wiki_intake_client
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    client.post("/api/wiki-intake/scan", json={})

    listed = client.get("/api/wiki-intake/candidates")
    assert listed.status_code == 200
    item = listed.get_json()["data"]["items"][0]
    assert item["status"] == "pending"

    detail = client.get(f"/api/wiki-intake/candidates/{item['candidate_id']}")
    assert detail.status_code == 200
    assert "Agent Harness" in detail.get_json()["data"]["content"]

    decision = client.post(
        "/api/wiki-intake/decisions",
        json={
            "candidate_id": item["candidate_id"],
            "decision": "accepted",
            "target": "wiki",
            "note": "确认进入 wiki",
            "operator": "human",
        },
    )
    assert decision.status_code == 201
    decision_data = decision.get_json()["data"]
    assert decision_data["enqueue"]["status"] == "queued"
    assert (data_root / "auto_jobs" / "queued").exists()
    rows = [json.loads(line) for line in (data_root / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["decision_status"] == "accepted"
    assert rows[0]["gate1_destination"] == "llm_wiki_only"
    assert rows[0]["side_effects"]["created_kfc_project"] is False

    relisted = client.get("/api/wiki-intake/candidates?status=accepted")
    assert relisted.get_json()["data"]["total"] == 1


def test_candidate_asset_endpoint_serves_relative_image_readonly(wiki_intake_client, monkeypatch):
    client, clippings, data_root, source = wiki_intake_client
    before = source.read_bytes()
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    client.post("/api/wiki-intake/scan", json={})
    item = client.get("/api/wiki-intake/candidates").get_json()["data"]["items"][0]

    resp = client.get(
        f"/api/wiki-intake/candidates/{item['candidate_id']}/assets",
        query_string={"path": "assets/test.png"},
    )

    assert resp.status_code == 200
    assert resp.content_type == "image/png"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.data.startswith(b"\x89PNG")
    assert source.read_bytes() == before


def test_candidate_asset_endpoint_rejects_traversal(wiki_intake_client, monkeypatch):
    client, clippings, data_root, _ = wiki_intake_client
    (clippings.parent / "secret.png").write_bytes(b"not allowed")
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    client.post("/api/wiki-intake/scan", json={})
    item = client.get("/api/wiki-intake/candidates").get_json()["data"]["items"][0]

    resp = client.get(
        f"/api/wiki-intake/candidates/{item['candidate_id']}/assets",
        query_string={"path": "../secret.png"},
    )

    assert resp.status_code == 400
    assert resp.get_json()["code"] == "invalid_asset_path"


def test_candidate_asset_endpoint_decodes_markdown_url_paths(wiki_intake_client, monkeypatch):
    client, clippings, data_root, _ = wiki_intake_client
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    client.post("/api/wiki-intake/scan", json={})
    item = client.get("/api/wiki-intake/candidates").get_json()["data"]["items"][0]

    resp = client.get(
        f"/api/wiki-intake/candidates/{item['candidate_id']}/assets",
        query_string={"path": "assets/encoded%20space.png"},
    )

    assert resp.status_code == 200
    assert resp.content_type == "image/png"


def test_auto_processed_sidecar_marks_candidate_completed(wiki_intake_client, monkeypatch):
    client, clippings, data_root, source = wiki_intake_client
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "topic_id": "agent-harness",
                "processed_at": "2026-05-12T11:53:36+08:00",
                "raw_article_path": "/tmp/kfc-wiki-hub/topics/agent-harness/raw/articles/agent-harness.md",
                "verified_digest_md_path": "/tmp/kfc-wiki-hub/topics/agent-harness/digests/verified_digest/agent-harness.md",
                "compile_run_id": "compile_test",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    listed = client.get("/api/wiki-intake/candidates")
    item = listed.get_json()["data"]["items"][0]

    assert item["status"] == "completed"
    assert item["has_processing_result"] is True
    assert item["auto_processed"]["topic_id"] == "agent-harness"


def test_processed_result_reads_sidecar_files_without_running_pipeline(wiki_intake_client, monkeypatch, tmp_path):
    client, clippings, data_root, source = wiki_intake_client
    wiki_hub = tmp_path / "wiki_hub"
    topic_dir = wiki_hub / "topics" / "agent-harness"
    digest_dir = topic_dir / "digests" / "verified_digest"
    ledger_dir = topic_dir / "digests" / "claim_ledger"
    raw_dir = topic_dir / "raw" / "articles"
    digest_dir.mkdir(parents=True)
    ledger_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    digest_path = digest_dir / "agent-harness.json"
    digest_md_path = digest_dir / "agent-harness.md"
    claim_path = ledger_dir / "agent-harness.jsonl"
    sources_path = ledger_dir / "agent-harness.sources.json"
    raw_path = raw_dir / "agent-harness.md"
    digest_path.write_text(
        json.dumps(
            {
                "routing_decision": {
                    "route_mode": "auto_created_topic",
                    "resolved_topic_id": "agent-harness",
                    "resolved_topic_label": "Agent Harness",
                },
                "source_summary": "Harness digest summary",
                "safe_wiki_wording": "Use attributed wording.",
                "core_concepts": [
                    {
                        "concept": "Agent 经济",
                        "summary": "以能执行任务、接管流程或生成专用软件的 AI Agent 为核心的新商业组织方式。",
                        "kfc_action_hint": "review_for_kfc",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    digest_md_path.write_text("# Agent Harness\n\nDigest markdown.", encoding="utf-8")
    claim_path.write_text(
        json.dumps(
            {
                "claim_id": "c001",
                "claim_text": "Harness coordinates tools.",
                "verification_status": "verified",
                "supporting_urls": ["https://example.com/agent"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    sources_path.write_text(
        json.dumps({"schema_version": "verification_sources_v1", "sources": [{"title": "Agent", "url": "https://example.com/agent"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    raw_path.write_text("# Agent Harness\n\nRaw article.", encoding="utf-8")
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "source_key": f"{row['candidate_id']}|{row['content_hash']}",
                "topic_id": "agent-harness",
                "route_mode": "auto_created_topic",
                "processed_at": "2026-05-12T11:53:36+08:00",
                "raw_article_path": str(raw_path),
                "verified_digest_json_path": str(digest_path),
                "verified_digest_md_path": str(digest_md_path),
                "claim_ledger_path": str(claim_path),
                "sources_path": str(sources_path),
                "compile_run_id": "compile_test",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    resp = client.get(f"/api/wiki-intake/candidates/{row['candidate_id']}/processed-result")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "complete"
    assert data["auto_processed"]["route_mode"] == "auto_created_topic"
    assert data["verified_digest"]["json"]["source_summary"] == "Harness digest summary"
    assert data["verified_digest"]["md"].startswith("# Agent Harness")
    assert data["claim_ledger"][0]["verification_status"] == "verified"
    assert data["sources"]["sources"][0]["title"] == "Agent"
    assert "Raw article" in data["raw_article_preview"]
    semantic = data["semantic_result"]
    assert semantic["recommended_topic"]["topic_id"] == "agent-harness"
    assert semantic["recommended_topic"]["auto_created_topic"] is True
    assert semantic["article_digest"]["one_sentence_summary"] == "Harness digest summary"
    assert semantic["candidate_concepts"][0]["name"] == "Agent 经济"
    assert semantic["candidate_concepts"][0]["summary"].startswith("以能执行任务")
    assert semantic["candidate_concepts"][0]["candidate_status"] == "candidate_only"
    assert semantic["verification"]["verified_count"] == 1
    assert semantic["safe_wiki"]["summary"] == "Use attributed wording."
    assert semantic["kfc_action_hints"]["readonly"] is True
    assert "created_concept_id" not in json.dumps(semantic)
    assert "registry_mutation" not in json.dumps(semantic)


def test_processed_result_falls_back_to_manifest_when_digest_files_are_missing(wiki_intake_client, monkeypatch, tmp_path):
    client, clippings, data_root, source = wiki_intake_client
    wiki_hub = tmp_path / "wiki_hub"
    wiki_hub.mkdir()
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    missing_digest = wiki_hub / "topics" / "agent-harness" / "digests" / "verified_digest" / "missing.json"
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "topic_id": "agent-harness",
                "processed_at": "2026-05-12T11:53:36+08:00",
                "verified_digest_json_path": str(missing_digest),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    resp = client.get(f"/api/wiki-intake/candidates/{row['candidate_id']}/processed-result")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "manifest_only"
    assert data["verified_digest"]["json"] is None
    assert data["auto_processed"]["topic_id"] == "agent-harness"
    assert data["read_errors"]["verified_digest_json_path"] == "missing_file"
    assert data["semantic_result"]["status"] == "manifest_only"
    assert data["semantic_result"]["audit"]["read_errors"]["verified_digest_json_path"] == "missing_file"


def test_candidate_primary_topic_can_be_changed_and_unlinked(wiki_intake_client, monkeypatch, tmp_path):
    client, clippings, data_root, source = wiki_intake_client
    wiki_hub = tmp_path / "wiki_hub"
    for topic_id, label in [
        ("agent-harness", "Agent Harness"),
        ("cloud-data-ai-platform", "Cloud Data and AI Platform"),
    ]:
        topic_dir = wiki_hub / "topics" / topic_id
        topic_dir.mkdir(parents=True)
        (topic_dir / "topic_profile.json").write_text(
            json.dumps({"topic_id": topic_id, "display_name": label}, ensure_ascii=False),
            encoding="utf-8",
        )
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "source_key": f"{row['candidate_id']}|{row['content_hash']}",
                "topic_id": "agent-harness",
                "processed_at": "2026-05-12T11:53:36+08:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    changed = client.patch(
        f"/api/wiki-intake/candidates/{row['candidate_id']}/topic-associations/primary",
        json={"topic_id": "cloud-data-ai-platform", "reason": "Data+AI correction"},
    )

    assert changed.status_code == 200
    changed_data = changed.get_json()["data"]
    assert changed_data["association"]["topic_id"] == "cloud-data-ai-platform"
    assert changed_data["association"]["previous_topic_id"] == "agent-harness"
    assert changed_data["detail"]["candidate"]["auto_processed"]["topic_id"] == "cloud-data-ai-platform"
    assert changed_data["detail"]["topic_context"]["topic_id"] == "cloud-data-ai-platform"

    invalid = client.patch(
        f"/api/wiki-intake/candidates/{row['candidate_id']}/topic-associations/primary",
        json={"topic_id": "missing-topic", "reason": "should fail"},
    )
    assert invalid.status_code == 404
    still_changed = client.get(f"/api/wiki-intake/candidates/{row['candidate_id']}").get_json()["data"]
    assert still_changed["candidate"]["auto_processed"]["topic_id"] == "cloud-data-ai-platform"

    unlinked = client.post(
        f"/api/wiki-intake/candidates/{row['candidate_id']}/topic-associations/unlink-primary",
        json={"reason": "Wrong topic"},
    )

    assert unlinked.status_code == 200
    unlinked_data = unlinked.get_json()["data"]
    assert unlinked_data["association"]["topic_id"] == ""
    assert unlinked_data["association"]["association_status"] == "unlinked"
    assert unlinked_data["detail"]["topic_context"] is None
    listed = client.get("/api/wiki-intake/candidates").get_json()["data"]["items"][0]
    assert listed["status"] == "needs_human_review"
    events = [json.loads(line) for line in (data_root / "topic_association_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == ["topic_primary_changed", "topic_primary_unlinked"]


def test_wiki_topic_overview_articles_and_candidate_context(wiki_intake_client, monkeypatch, tmp_path):
    client, clippings, data_root, source = wiki_intake_client
    wiki_hub = tmp_path / "wiki_hub"
    topic_dir = wiki_hub / "topics" / "agent-harness"
    digest_dir = topic_dir / "digests" / "verified_digest"
    digest_dir.mkdir(parents=True)
    (topic_dir / "topic_profile.json").write_text(
        json.dumps(
            {
                "topic_id": "agent-harness",
                "display_name": "Agent Harness",
                "concept_seeds": ["agent runtime"],
                "topic_keywords": ["tool calling"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    digest_path = digest_dir / "agent-harness.json"
    digest_path.write_text(
        json.dumps(
            {
                "title": "Agent Harness",
                "original_source_url": "https://example.com/agent",
                "summary": "Harness digest summary",
                "core_concepts": ["agent runtime", "tool calling"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    monkeypatch.setattr(TopicClusterStore, "CLUSTER_DIR", tmp_path / "topic_clusters")
    monkeypatch.setattr(TopicClusterStore, "LINK_DIR", tmp_path / "topic_cluster_links")
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "source_key": f"{row['candidate_id']}|{row['content_hash']}",
                "topic_id": "agent-harness",
                "processed_at": "2026-05-12T11:53:36+08:00",
                "raw_article_path": str(topic_dir / "raw" / "articles" / "agent-harness.md"),
                "verified_digest_json_path": str(digest_path),
                "verified_digest_md_path": str(digest_path.with_suffix(".md")),
                "sources_path": str(topic_dir / "digests" / "claim_ledger" / "agent.sources.json"),
                "compile_run_id": "compile_test",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    store = TopicClusterStore()
    store.create_cluster({"cluster_id": "tc_wiki_agent-harness", "title": "Agent Harness"})
    store.create_cluster_link(
        "tc_wiki_agent-harness",
        {
            "link_id": "tcl_tc_wiki_agent-harness_agent-harness",
            "target_type": "wiki_topic",
            "target_id": "agent-harness",
            "target_title": "Agent Harness",
            "role": "primary",
            "status": "accepted",
        },
    )

    topics_resp = client.get("/api/wiki-intake/topics")
    assert topics_resp.status_code == 200
    topics = topics_resp.get_json()["data"]
    assert topics[0]["topic_id"] == "agent-harness"
    assert topics[0]["title"] == "Agent Harness"
    assert topics[0]["article_count"] == 1
    assert topics[0]["completed_count"] == 1
    assert topics[0]["cluster_ids"] == ["tc_wiki_agent-harness"]
    assert topics[0]["top_concepts"][:2] == ["agent runtime", "tool calling"]

    coverage_resp = client.get("/api/wiki-intake/topics?include_coverage=1")
    coverage_data = coverage_resp.get_json()["data"]
    assert coverage_data["coverage_counts"]["linked"] == 1
    assert coverage_data["topics"][0]["cluster_coverage_status"] == "linked"
    assert coverage_data["topics"][0]["cluster_coverage"]["linked_clusters"][0]["cluster_id"] == "tc_wiki_agent-harness"

    articles_resp = client.get("/api/wiki-intake/topics/agent-harness/articles")
    assert articles_resp.status_code == 200
    detail = articles_resp.get_json()["data"]
    assert detail["topic"]["article_count"] == 1
    assert detail["articles"][0]["title"] == "Agent Harness"
    assert detail["articles"][0]["digest_summary"] == "Harness digest summary"
    assert detail["articles"][0]["top_concepts"] == ["agent runtime", "tool calling"]

    candidate_detail = client.get(f"/api/wiki-intake/candidates/{row['candidate_id']}").get_json()["data"]
    assert candidate_detail["topic_context"]["topic_id"] == "agent-harness"
    assert candidate_detail["topic_context"]["article_count"] == 1
    assert candidate_detail["topic_context"]["cluster_ids"] == ["tc_wiki_agent-harness"]
    assert candidate_detail["topic_context"]["recent_same_topic_articles"][0]["title"] == "Agent Harness"


def test_wiki_topic_cluster_coverage_candidate_override_link_and_proposal(wiki_intake_client, monkeypatch, tmp_path):
    client, clippings, data_root, source = wiki_intake_client
    wiki_hub = tmp_path / "wiki_hub"
    topic_dir = wiki_hub / "topics" / "cloud-data-ai-platform"
    topic_dir.mkdir(parents=True)
    (topic_dir / "topic_profile.json").write_text(
        json.dumps(
            {
                "topic_id": "cloud-data-ai-platform",
                "display_name": "Cloud Data and AI Platform",
                "concept_seeds": ["cloud data", "AI platform"],
                "topic_keywords": ["cloud", "ai", "platform"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    monkeypatch.setattr(TopicClusterStore, "CLUSTER_DIR", tmp_path / "topic_clusters")
    monkeypatch.setattr(TopicClusterStore, "LINK_DIR", tmp_path / "topic_cluster_links")
    monkeypatch.setattr(TopicClusterRefreshRequestStore, "ROOT_DIR", tmp_path / "topic_cluster_refresh_requests")
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "source_key": f"{row['candidate_id']}|{row['content_hash']}",
                "topic_id": "cloud-data-ai-platform",
                "processed_at": "2026-05-14T11:53:36+08:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    store = TopicClusterStore()
    store.create_cluster(
        {
            "cluster_id": "tc_ai_cloud_infra",
            "title": "AI Cloud Infrastructure & Business",
            "description": "AI cloud platform and infrastructure strategy",
        }
    )
    before_source = source.read_bytes()
    assert not (tmp_path / "research_projects").exists()

    coverage = client.get("/api/wiki-intake/topics/cloud-data-ai-platform/cluster-coverage").get_json()["data"]
    assert coverage["status"] == "candidate"
    assert coverage["candidate_clusters"][0]["cluster_id"] == "tc_ai_cloud_infra"
    assert not list((tmp_path / "topic_cluster_links").glob("*.json"))

    override = client.post(
        "/api/wiki-intake/topics/cloud-data-ai-platform/cluster-coverage/override",
        json={"status": "watch", "note": "article count is still low"},
    )
    assert override.status_code == 200
    assert override.get_json()["data"]["coverage"]["status"] == "watch"
    assert (data_root / "topic_cluster_coverage.jsonl").exists()
    assert not list((tmp_path / "topic_cluster_links").glob("*.json"))

    linked = client.post(
        "/api/wiki-intake/topics/cloud-data-ai-platform/cluster-coverage/link",
        json={"cluster_id": "tc_ai_cloud_infra", "rationale": "human confirmed"},
    )
    assert linked.status_code == 201
    assert linked.get_json()["data"]["coverage"]["status"] == "linked"
    link_files = list((tmp_path / "topic_cluster_links").glob("*.json"))
    assert len(link_files) == 1
    saved_link = json.loads(link_files[0].read_text(encoding="utf-8"))
    assert saved_link["status"] == "accepted"
    assert saved_link["source"] == "human_topic_cluster_coverage"

    duplicate = client.post(
        "/api/wiki-intake/topics/cloud-data-ai-platform/cluster-coverage/link",
        json={"cluster_id": "tc_ai_cloud_infra"},
    )
    assert duplicate.status_code == 200
    assert len(list((tmp_path / "topic_cluster_links").glob("*.json"))) == 1

    proposal = client.post(
        "/api/wiki-intake/topics/cloud-data-ai-platform/cluster-coverage/proposals",
        json={"suggested_title": "AI-native Data Platform", "rationale": "new strategic direction"},
    )
    assert proposal.status_code == 201
    request = proposal.get_json()["data"]["request"]
    assert request["scope"] == "wiki_topic"
    assert request["topic_id"] == "cloud-data-ai-platform"
    assert request["rules"]["proposal_only"] is True
    assert len(list((tmp_path / "topic_clusters").glob("*.json"))) == 1
    assert len(list((tmp_path / "topic_cluster_links").glob("*.json"))) == 1
    assert not (tmp_path / "research_projects").exists()
    assert source.read_bytes() == before_source


def test_wiki_topic_articles_rejects_unsafe_topic_id(wiki_intake_client, monkeypatch):
    client, clippings, data_root, _ = wiki_intake_client
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)

    resp = client.get("/api/wiki-intake/topics/bad..topic/articles")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_auto_processed_sidecar_takes_precedence_over_accepted_decision(wiki_intake_client, monkeypatch):
    client, clippings, data_root, source = wiki_intake_client
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    client.post("/api/wiki-intake/scan", json={})
    row = json.loads((data_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    client.post(
        "/api/wiki-intake/decisions",
        json={
            "candidate_id": row["candidate_id"],
            "decision": "accepted",
            "target": "wiki",
            "operator": "human",
        },
    )
    (data_root / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_md": str(source),
                "source_key": f"{row['candidate_id']}|{row['content_hash']}",
                "topic_id": "agent-harness",
                "processed_at": "2026-05-12T11:53:36+08:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    listed = client.get("/api/wiki-intake/candidates")
    item = listed.get_json()["data"]["items"][0]

    assert item["latest_decision"]["decision_status"] == "accepted"
    assert item["status"] == "completed"


def test_process_next_runs_repo_local_auto_intake_and_keeps_clippings_readonly(wiki_intake_client, monkeypatch, tmp_path):
    client, clippings, data_root, source = wiki_intake_client
    wiki_hub = tmp_path / "wiki_hub"
    cluster_dir = tmp_path / "topic_clusters"
    link_dir = tmp_path / "topic_cluster_links"
    before = source.read_bytes()
    monkeypatch.setattr(WikiIntakeStore, "CLIPPINGS_ROOT", clippings)
    monkeypatch.setattr(WikiIntakeStore, "DATA_ROOT", data_root)
    monkeypatch.setattr(TopicClusterStore, "CLUSTER_DIR", cluster_dir)
    monkeypatch.setattr(TopicClusterStore, "LINK_DIR", link_dir)
    monkeypatch.setenv("KFC_WIKI_HUB_ROOT", str(wiki_hub))
    client.post("/api/wiki-intake/scan", json={})

    resp = client.post("/api/wiki-intake/process-next", json={"adapter": "deterministic", "timeout_seconds": 60})

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["adapter"] == "deterministic"
    assert data["result"]["status"] == "completed"
    assert source.read_bytes() == before
    processed = [json.loads(line) for line in (data_root / "auto_processed_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert processed[0]["raw_article_path"].startswith(str(wiki_hub))
    assert (wiki_hub / "topics" / "agent-harness" / "compile_runs.jsonl").exists()
    assert data["topic_cluster_sync"]["status"] == "coverage_only"
    assert data["topic_cluster_sync"]["side_effects"]["created_topic_cluster"] is False
    assert data["topic_cluster_sync"]["side_effects"]["created_topic_cluster_link"] is False
    assert not cluster_dir.exists()
    assert not link_dir.exists()

    listed = client.get("/api/wiki-intake/candidates?status=completed")
    assert listed.get_json()["data"]["total"] == 1


def test_import_legacy_wiki_state_remaps_processed_manifest_and_topic_link(tmp_path):
    legacy_root = tmp_path / "legacy_wiki"
    legacy_intake = legacy_root / "intake"
    legacy_topic = legacy_root / "topics" / "agent-harness"
    legacy_digest = legacy_topic / "digests" / "verified_digest"
    legacy_intake.mkdir(parents=True)
    legacy_digest.mkdir(parents=True)
    (legacy_topic / "topic_profile.json").write_text(
        json.dumps({"topic_id": "agent-harness", "display_name": "Agent Harness"}, ensure_ascii=False),
        encoding="utf-8",
    )
    digest_path = legacy_digest / "agent.md"
    digest_path.write_text("# Digest", encoding="utf-8")
    (legacy_intake / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_id": "src_agent",
                "source_md": "/Users/mac/Downloads/OB笔记/Clippings/agent.md",
                "topic_id": "agent-harness",
                "processed_at": "2026-05-12T11:53:36+08:00",
                "verified_digest_md_path": str(digest_path),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    kfc_data_root = tmp_path / "kfc_data"

    result = import_state(legacy_wiki_root=legacy_root, kfc_data_root=kfc_data_root)

    assert result["remapped_rows"] == 1
    processed = [
        json.loads(line)
        for line in (kfc_data_root / "wiki_intake" / "auto_processed_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert processed[0]["candidate_id"] == "src_agent"
    assert processed[0]["backfilled_from"].endswith("auto_processed_manifest.jsonl")
    assert processed[0]["verified_digest_md_path"].startswith(str(kfc_data_root / "wiki_hub" / "topics"))
    assert (kfc_data_root / "wiki_hub" / "topics" / "agent-harness" / "topic_profile.json").exists()
    assert (kfc_data_root / "topic_clusters" / "tc_wiki_agent-harness.json").exists()
    assert (kfc_data_root / "topic_cluster_links" / "tcl_tc_wiki_agent-harness_agent-harness.json").exists()


def test_import_legacy_wiki_state_merges_without_overwriting_kfc_rows(tmp_path):
    legacy_root = tmp_path / "legacy_wiki"
    legacy_intake = legacy_root / "intake"
    legacy_topic = legacy_root / "topics" / "agent-harness"
    legacy_topic.mkdir(parents=True)
    legacy_intake.mkdir(parents=True)
    (legacy_topic / "topic_profile.json").write_text(
        json.dumps({"topic_id": "agent-harness", "display_name": "Agent Harness"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (legacy_intake / "auto_processed_manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "auto-processed-source.v1",
                        "source_key": "src_existing|sha256:existing",
                        "source_id": "src_existing",
                        "source_md": "/Users/mac/Downloads/OB笔记/Clippings/existing.md",
                        "topic_id": "agent-harness",
                        "processed_at": "2026-05-12T11:53:36+08:00",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "schema_version": "auto-processed-source.v1",
                        "source_key": "src_new|sha256:new",
                        "source_id": "src_new",
                        "source_md": "/Users/mac/Downloads/OB笔记/Clippings/new.md",
                        "topic_id": "agent-harness",
                        "processed_at": "2026-05-13T11:53:36+08:00",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    kfc_data_root = tmp_path / "kfc_data"
    kfc_intake = kfc_data_root / "wiki_intake"
    kfc_intake.mkdir(parents=True)
    (kfc_intake / "auto_processed_manifest.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "auto-processed-source.v1",
                "source_key": "src_existing|sha256:existing",
                "source_id": "src_existing",
                "source_md": "/kfc/local/existing.md",
                "topic_id": "agent-harness",
                "processed_at": "2026-05-14T11:53:36+08:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = import_state(legacy_wiki_root=legacy_root, kfc_data_root=kfc_data_root)

    assert result["existing_processed_rows"] == 1
    assert result["added_processed_rows"] == 1
    assert result["skipped_existing_rows"] == 1
    processed = [
        json.loads(line)
        for line in (kfc_intake / "auto_processed_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(processed) == 2
    existing = next(row for row in processed if row["source_id"] == "src_existing")
    assert existing["source_md"] == "/kfc/local/existing.md"
    added = next(row for row in processed if row["source_id"] == "src_new")
    assert added["source_md"] == "/Users/mac/Downloads/OB笔记/Clippings/new.md"
