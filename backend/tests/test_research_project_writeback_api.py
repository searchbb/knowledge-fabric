from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_writeback import research_project_writeback_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def writeback_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_writeback_bp)
    return app.test_client()


def _create_project(client):
    return client.post(
        "/api/research-projects",
        json={
            "title": "华为云 Agent-ready 企业软件栈战略研究",
            "background": "P3 writeback API baseline。",
        },
    ).get_json()["data"]


def _pack_payload():
    return {
        "idempotency_key": "pack-api-001",
        "title": "Huawei Cloud Agent-ready external evidence pack",
        "source_type": "deep_research",
        "scope": "C2_external",
        "producer": {"kind": "codex_skill", "name": "deep_research_skill", "model": "GPT Pro"},
        "topic": "华为云 Agent-ready 企业软件栈战略研究",
        "source_refs": [{
            "source_id": "src_001",
            "type": "url",
            "title": "Agent governance source",
            "url": "https://example.com/agent-governance",
        }],
        "evidence_candidates": [{
            "external_id": "agent_harness_control_001",
            "claim": "企业级 Agent 的核心控制点在执行治理外壳。",
            "evidence_text": "企业 Agent 需要身份、权限、审批、日志、监控和补救机制。",
            "source_refs": ["src_001"],
            "confidence": 0.86,
        }],
    }


def test_research_run_consultation_and_pack_api_flow(writeback_client):
    project = _create_project(writeback_client)

    run_resp = writeback_client.post(
        f"/api/research-projects/{project['id']}/research-runs",
        json={
            "idempotency_key": "run-api-001",
            "stage": "P3",
            "phase": "writeback_contract_test",
            "title": "P3 writeback API test",
            "status": "completed",
        },
    )
    assert run_resp.status_code == 201
    run = run_resp.get_json()["data"]["research_run"]
    assert run["run_id"].startswith("rr_")

    replay = writeback_client.post(
        f"/api/research-projects/{project['id']}/research-runs",
        json={
            "idempotency_key": "run-api-001",
            "stage": "P3",
            "phase": "writeback_contract_test",
            "title": "P3 writeback API test",
            "status": "completed",
        },
    )
    assert replay.status_code == 200
    assert replay.get_json()["idempotent_replay"] is True

    conflict = writeback_client.post(
        f"/api/research-projects/{project['id']}/research-runs",
        json={
            "idempotency_key": "run-api-001",
            "stage": "P3",
            "phase": "writeback_contract_test",
            "title": "Changed",
        },
    )
    assert conflict.status_code == 409

    consult_resp = writeback_client.post(
        f"/api/research-projects/{project['id']}/consultation-logs",
        json={
            "idempotency_key": "consult-api-001",
            "kind": "gpt_design_review",
            "stage": "P3",
            "status": "complete",
            "run_id": run["run_id"],
            "answer_summary": "KFC should receive writeback only.",
        },
    )
    assert consult_resp.status_code == 201
    assert consult_resp.get_json()["data"]["consultation_log"]["consultation_id"].startswith("cl_")

    pack_resp = writeback_client.post(
        f"/api/research-projects/{project['id']}/external-research-packs/import",
        json=_pack_payload(),
    )
    assert pack_resp.status_code == 201
    pack = pack_resp.get_json()["data"]["external_research_pack"]
    candidate_id = pack["evidence_candidates"][0]["candidate_id"]

    accept = writeback_client.patch(
        f"/api/research-projects/{project['id']}/external-research-packs/{pack['pack_id']}/candidates/{candidate_id}",
        json={"review_status": "accepted", "review_note": "进入 P3 baseline"},
    )
    assert accept.status_code == 200
    data = accept.get_json()["data"]
    assert data["external_research_pack"]["accepted_candidate_ids"] == [candidate_id]
    assert data["evidence_items"][0]["origin"] == "external_research_pack"
    assert data["evidence_items"][0]["scope"] == "C2_external"

    get_project = writeback_client.get(f"/api/research-projects/{project['id']}")
    project_data = get_project.get_json()["data"]
    assert project_data["research_runs"][0]["run_id"] == run["run_id"]
    assert project_data["consultation_logs"][0]["kind"] == "gpt_design_review"
    assert project_data["external_research_packs"][0]["accepted_count"] == 1


def test_writeback_api_validation_errors(writeback_client):
    missing_project = writeback_client.post(
        "/api/research-projects/rp_000000000000/research-runs",
        json={"idempotency_key": "run-missing", "stage": "P3", "phase": "x", "title": "x"},
    )
    assert missing_project.status_code == 404

    project = _create_project(writeback_client)
    bad_run = writeback_client.post(
        f"/api/research-projects/{project['id']}/research-runs",
        json={"stage": "P3"},
    )
    assert bad_run.status_code == 400

    bad_pack = writeback_client.post(
        f"/api/research-projects/{project['id']}/external-research-packs/import",
        json={"idempotency_key": "bad-pack", "title": "Bad", "source_type": "deep_research"},
    )
    assert bad_pack.status_code == 400

    pack = writeback_client.post(
        f"/api/research-projects/{project['id']}/external-research-packs/import",
        json=_pack_payload(),
    ).get_json()["data"]["external_research_pack"]
    bad_status = writeback_client.patch(
        f"/api/research-projects/{project['id']}/external-research-packs/{pack['pack_id']}/candidates/missing",
        json={"review_status": "insight"},
    )
    assert bad_status.status_code == 400
