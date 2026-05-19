from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_artifact_packs import research_project_artifact_packs_bp
from app.api.routes.research_project_synthesis import research_project_synthesis_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def pack_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_synthesis_bp)
    app.register_blueprint(research_project_artifact_packs_bp)
    return app.test_client()


def _seed(client):
    project = client.post(
        "/api/research-projects",
        json={
            "title": "华为云 Agent-ready 企业软件栈战略研究",
            "evidence_items": [
                {"evidence_id": "ev_local_harness", "title": "Harness", "status": "accepted", "origin": "local_evidence_pack", "scope": "C1_local"},
                {"evidence_id": "ei_external_governance", "title": "Governance", "status": "accepted", "origin": "external_research_pack", "scope": "C2_external"},
            ],
        },
    ).get_json()["data"]
    pid = project["id"]
    row = client.post(
        f"/api/research-projects/{pid}/evidence-matrix/rows",
        json={
            "idempotency_key": "p5-row-api",
            "question": "Q",
            "claim": "控制点在执行控制面。",
            "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        },
    ).get_json()["data"]["row"]
    card = client.post(
        f"/api/research-projects/{pid}/insight-cards",
        json={
            "idempotency_key": "p5-card-api",
            "title": "执行控制面是长期控制点",
            "claim": "长期控制点在执行控制面。",
            "implication": "升级工程化平台。",
            "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
            "matrix_row_ids": [row["id"]],
        },
    ).get_json()["data"]["insight_card"]
    draft = client.post(
        f"/api/research-projects/{pid}/artifact-drafts",
        json={
            "idempotency_key": "p5-draft-api",
            "artifact_type": "slide_outline",
            "title": "5 页战略材料大纲",
            "purpose": "形成材料输入。",
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness"],
        },
    ).get_json()["data"]["artifact_draft"]
    return pid, row, card, draft


def test_artifact_pack_api_flow(pack_client):
    pid, row, card, draft = _seed(pack_client)

    created = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs",
        json={
            "idempotency_key": "p5-pack-api",
            "title": "华为云 Agent-ready 企业软件栈战略汇报材料包",
            "purpose": "面向领导汇报战略判断。",
            "pack_type": "leadership_deck",
            "source_artifact_draft_ids": [draft["id"]],
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        },
    )
    assert created.status_code == 201
    pack = created.get_json()["data"]["artifact_pack"]
    assert pack["pack_id"].startswith("ap_")

    item = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs/{pack['pack_id']}/items",
        json={
            "artifact_draft_id": draft["id"],
            "artifact_type": "slide_outline",
            "title": "主汇报材料",
            "role_in_pack": "main_deck",
        },
    )
    assert item.status_code == 201

    page = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs/{pack['pack_id']}/pages",
        json={
            "page_title": "Harness 是企业执行控制面",
            "page_type": "framework",
            "page_claim": "权限、审批、日志、评测和回写构成企业控制面。",
            "source_artifact_draft_id": draft["id"],
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness", "ei_external_governance"],
            "source_matrix_row_ids": [row["id"]],
        },
    )
    assert page.status_code == 201
    pack = page.get_json()["data"]["artifact_pack"]
    page_id = pack["pages"][0]["page_id"]

    file_ref = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs/{pack['pack_id']}/file-refs",
        json={
            "file_kind": "drawio",
            "title": "五层架构图 v0.1",
            "relative_path": "artifact_files/agent_ready_stack_v0_1.drawio",
            "linked_page_ids": [page_id],
            "linked_artifact_draft_ids": [draft["id"]],
        },
    )
    assert file_ref.status_code == 201

    review = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs/{pack['pack_id']}/review-rounds",
        json={
            "round_name": "P5 review round 1",
            "reviewer": "human",
            "decisions": [{
                "target_type": "page",
                "target_id": page_id,
                "decision": "needs_revision",
                "severity": "major",
            }],
        },
    )
    assert review.status_code == 201
    pack = review.get_json()["data"]["artifact_pack"]
    assert pack["pages"][0]["review_status"] == "needs_revision"

    listed = pack_client.get(f"/api/research-projects/{pid}/artifact-packs")
    assert listed.status_code == 200
    assert len(listed.get_json()["data"]["artifact_packs"][0]["pages"]) == 1

    patched = pack_client.patch(
        f"/api/research-projects/{pid}/artifact-packs/{pack['pack_id']}",
        json={"readiness": "review_ready", "status": "in_review"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["artifact_pack"]["readiness"] == "review_ready"


def test_artifact_pack_api_validation_errors(pack_client):
    missing = pack_client.post(
        "/api/research-projects/rp_000000000000/artifact-packs",
        json={"idempotency_key": "missing", "title": "Pack", "purpose": "Purpose"},
    )
    assert missing.status_code == 404

    pid, _, _, draft = _seed(pack_client)
    bad_ref = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs",
        json={
            "idempotency_key": "bad-ref",
            "title": "Pack",
            "purpose": "Purpose",
            "source_artifact_draft_ids": ["ad_000000000000"],
        },
    )
    assert bad_ref.status_code in {400, 404}

    pack = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs",
        json={
            "idempotency_key": "valid-pack",
            "title": "Pack",
            "purpose": "Purpose",
            "source_artifact_draft_ids": [draft["id"]],
        },
    ).get_json()["data"]["artifact_pack"]
    unsafe = pack_client.post(
        f"/api/research-projects/{pid}/artifact-packs/{pack['pack_id']}/file-refs",
        json={"file_kind": "drawio", "title": "Unsafe", "relative_path": "/tmp/a.drawio"},
    )
    assert unsafe.status_code == 400
    assert "relative_path" in unsafe.get_json()["error"]
