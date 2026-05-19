from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_synthesis import research_project_synthesis_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def synthesis_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_synthesis_bp)
    return app.test_client()


def _create_project(client):
    return client.post(
        "/api/research-projects",
        json={
            "title": "华为云 Agent-ready 企业软件栈战略研究",
            "evidence_items": [
                {
                    "evidence_id": "ev_local_harness",
                    "title": "企业级 Harness",
                    "status": "accepted",
                    "origin": "local_evidence_pack",
                    "scope": "C1_local",
                },
                {
                    "evidence_id": "ei_external_governance",
                    "title": "Agent governance",
                    "status": "accepted",
                    "origin": "external_research_pack",
                    "scope": "C2_external",
                },
            ],
        },
    ).get_json()["data"]


def test_synthesis_api_create_list_get_patch_flow(synthesis_client):
    project = _create_project(synthesis_client)

    row_resp = synthesis_client.post(
        f"/api/research-projects/{project['id']}/evidence-matrix/rows",
        json={
            "idempotency_key": "p4-row-api-001",
            "question": "华为云应控制企业软件栈哪一层？",
            "claim": "控制点在企业级 Harness 和执行控制面。",
            "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
            "confidence": "high",
        },
    )
    assert row_resp.status_code == 201
    row = row_resp.get_json()["data"]["row"]
    assert row["id"].startswith("emr_")

    replay = synthesis_client.post(
        f"/api/research-projects/{project['id']}/evidence-matrix/rows",
        json={
            "idempotency_key": "p4-row-api-001",
            "question": "华为云应控制企业软件栈哪一层？",
            "claim": "控制点在企业级 Harness 和执行控制面。",
            "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
            "confidence": "high",
        },
    )
    assert replay.status_code == 200
    assert replay.get_json()["idempotent_replay"] is True

    card_resp = synthesis_client.post(
        f"/api/research-projects/{project['id']}/insight-cards",
        json={
            "idempotency_key": "p4-card-api-001",
            "title": "执行控制面是长期控制点",
            "claim": "企业 Agent 的长期控制点在执行控制面。",
            "implication": "AgentArts 应升级为企业 Agent 工程化平台。",
            "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
            "matrix_row_ids": [row["id"]],
            "confidence": "high",
        },
    )
    assert card_resp.status_code == 201
    card = card_resp.get_json()["data"]["insight_card"]
    assert card["matrix_row_ids"] == [row["id"]]

    draft_resp = synthesis_client.post(
        f"/api/research-projects/{project['id']}/artifact-drafts",
        json={
            "idempotency_key": "p4-draft-api-001",
            "artifact_type": "slide_outline",
            "title": "5 页战略材料大纲",
            "purpose": "形成领导汇报材料输入。",
            "audience": "华为云战略部二层领导",
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness"],
            "outline": [{"section_id": "s1", "title": "战略判断", "source_insight_ids": [card["id"]]}],
        },
    )
    assert draft_resp.status_code == 201
    draft = draft_resp.get_json()["data"]["artifact_draft"]

    rows = synthesis_client.get(f"/api/research-projects/{project['id']}/evidence-matrix")
    assert rows.status_code == 200
    assert rows.get_json()["data"]["rows"][0]["id"] == row["id"]

    patched_row = synthesis_client.patch(
        f"/api/research-projects/{project['id']}/evidence-matrix/rows/{row['id']}",
        json={"status": "reviewed", "material_readiness": "usable"},
    )
    assert patched_row.status_code == 200
    assert patched_row.get_json()["data"]["row"]["status"] == "reviewed"

    patched_card = synthesis_client.patch(
        f"/api/research-projects/{project['id']}/insight-cards/{card['id']}",
        json={"status": "accepted"},
    )
    assert patched_card.status_code == 200
    assert patched_card.get_json()["data"]["insight_card"]["status"] == "accepted"

    patched_draft = synthesis_client.patch(
        f"/api/research-projects/{project['id']}/artifact-drafts/{draft['id']}",
        json={"material_readiness": "presentation_ready"},
    )
    assert patched_draft.status_code == 200
    assert patched_draft.get_json()["data"]["artifact_draft"]["material_readiness"] == "presentation_ready"

    get_project = synthesis_client.get(f"/api/research-projects/{project['id']}")
    project_data = get_project.get_json()["data"]
    assert project_data["evidence_matrix_rows"][0]["status"] == "reviewed"
    assert project_data["insight_cards"][0]["status"] == "accepted"
    assert project_data["artifact_drafts"][0]["material_readiness"] == "presentation_ready"


def test_synthesis_api_validation_errors(synthesis_client):
    missing_project = synthesis_client.post(
        "/api/research-projects/rp_000000000000/evidence-matrix/rows",
        json={"idempotency_key": "missing", "question": "Q", "claim": "C"},
    )
    assert missing_project.status_code == 404

    project = _create_project(synthesis_client)
    bad_ref = synthesis_client.post(
        f"/api/research-projects/{project['id']}/evidence-matrix/rows",
        json={
            "idempotency_key": "bad-ref",
            "question": "Q",
            "claim": "C",
            "supporting_evidence_ids": ["ev_missing"],
        },
    )
    assert bad_ref.status_code == 400
    assert "evidence references not accepted" in bad_ref.get_json()["error"]

    bad_patch = synthesis_client.patch(
        f"/api/research-projects/{project['id']}/evidence-matrix/rows/emr_000000000000",
        json={"run_model": True},
    )
    assert bad_patch.status_code == 400
    assert "unsupported fields" in bad_patch.get_json()["error"]
