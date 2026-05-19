from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_artifact_packs import research_project_artifact_packs_bp
from app.api.routes.research_project_briefings import research_project_briefings_bp
from app.api.routes.research_project_decisions import research_project_decisions_bp
from app.api.routes.research_project_synthesis import research_project_synthesis_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def briefing_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_synthesis_bp)
    app.register_blueprint(research_project_artifact_packs_bp)
    app.register_blueprint(research_project_decisions_bp)
    app.register_blueprint(research_project_briefings_bp)
    return app.test_client()


def _seed(client):
    project = client.post(
        "/api/research-projects",
        json={
            "title": "华为云 Agent-ready 企业软件栈战略研究",
            "evidence_items": [
                {"evidence_id": "ev_harness", "title": "Harness", "status": "accepted", "origin": "local", "scope": "C1_local"},
                {"evidence_id": "ei_governance", "title": "Governance", "status": "accepted", "origin": "external", "scope": "C2_external"},
            ],
        },
    ).get_json()["data"]
    pid = project["id"]
    row = client.post(f"/api/research-projects/{pid}/evidence-matrix/rows", json={
        "idempotency_key": "p7-api-row",
        "question": "Q",
        "claim": "控制点在执行治理面。",
        "supporting_evidence_ids": ["ev_harness", "ei_governance"],
    }).get_json()["data"]["row"]
    card = client.post(f"/api/research-projects/{pid}/insight-cards", json={
        "idempotency_key": "p7-api-card",
        "title": "执行治理面是长期控制点",
        "claim": "控制点不在模型能力本身。",
        "implication": "升级工程化平台。",
        "supporting_evidence_ids": ["ev_harness"],
        "matrix_row_ids": [row["id"]],
    }).get_json()["data"]["insight_card"]
    draft = client.post(f"/api/research-projects/{pid}/artifact-drafts", json={
        "idempotency_key": "p7-api-draft",
        "artifact_type": "slide_outline",
        "title": "战略材料大纲",
        "purpose": "形成材料输入。",
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
    }).get_json()["data"]["artifact_draft"]
    pack = client.post(f"/api/research-projects/{pid}/artifact-packs", json={
        "idempotency_key": "p7-api-pack",
        "title": "战略材料包",
        "purpose": "面向领导汇报。",
        "source_artifact_draft_ids": [draft["id"]],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
    }).get_json()["data"]["artifact_pack"]
    option = client.post(f"/api/research-projects/{pid}/strategic-options", json={
        "idempotency_key": "p7-api-option",
        "title": "L2 + L4 控制点选项",
        "source_insight_ids": [card["id"]],
        "source_evidence_matrix_row_ids": [row["id"]],
        "source_evidence_ids": ["ev_harness"],
        "source_artifact_pack_ids": [pack["pack_id"]],
    }).get_json()["data"]["strategic_option"]
    plan = client.post(f"/api/research-projects/{pid}/validation-plans", json={
        "idempotency_key": "p7-api-plan",
        "title": "90-day ERP/Test Harness pilot validation",
        "linked_option_ids": [option["option_id"]],
        "validation_questions": [{"question": "客户是否愿意接入真实权限？"}],
        "validation_methods": [{"method_type": "customer_pilot", "execution_location": "external"}],
        "metrics": [{"name": "harness_reuse_ratio", "target": ">= 60%"}],
    }).get_json()["data"]["validation_plan"]
    decision = client.post(f"/api/research-projects/{pid}/leadership-decision-records", json={
        "idempotency_key": "p7-api-decision",
        "title": "Decision on Agent-ready control point",
        "linked_option_ids": [option["option_id"]],
        "linked_validation_plan_ids": [plan["plan_id"]],
        "chosen_option_id": option["option_id"],
        "rationale": [{"statement": "L2 + L4 更贴近企业落地。"}],
    }).get_json()["data"]["leadership_decision_record"]
    return pid, card, option, plan, decision


def _payload(card, option, plan, decision):
    return {
        "idempotency_key": "p7-api-briefing",
        "title": "Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout",
        "briefing_type": "strategic_readout",
        "audience": "cloud_strategy_leadership",
        "purpose": "Prepare leadership discussion on Agent-ready enterprise software stack strategy.",
        "executive_summary": {
            "headline": "Enterprise AI competition is moving to Agent-ready software stack control points.",
            "key_message": "Focus on L2 Agent-ready adaptation and L4 enterprise Harness.",
            "leadership_ask": "Approve 90-day ERP/Test Harness pilots.",
            "decision_required": True,
        },
        "source_asset_refs": [{"asset_type": "insight_card", "asset_id": card["id"], "required": True}],
        "sections": [{
            "order": 1,
            "title": "Why now",
            "section_type": "context",
            "summary": "Agent operations are becoming a new enterprise software entry point.",
            "source_refs": [{"asset_type": "strategic_option", "asset_id": option["option_id"], "required": True}],
        }],
        "decision_asks": [{
            "title": "Approve the first 90-day pilot path",
            "linked_option_ids": [option["option_id"]],
            "linked_validation_plan_ids": [plan["plan_id"]],
            "linked_decision_record_ids": [decision["decision_id"]],
        }],
    }


def test_leadership_briefing_api_flow(briefing_client):
    pid, card, option, plan, decision = _seed(briefing_client)
    created = briefing_client.post(f"/api/research-projects/{pid}/leadership-briefings", json=_payload(card, option, plan, decision))
    assert created.status_code == 201
    briefing = created.get_json()["data"]["leadership_briefing"]
    assert briefing["briefing_id"].startswith("lb_")

    listed = briefing_client.get(f"/api/research-projects/{pid}/leadership-briefings")
    assert listed.status_code == 200
    index_item = listed.get_json()["data"]["leadership_briefings"][0]
    assert index_item["briefing_id"] == briefing["briefing_id"]
    assert "sections" not in index_item

    detail = briefing_client.get(f"/api/research-projects/{pid}/leadership-briefings/{briefing['briefing_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["leadership_briefing"]["sections"][0]["title"] == "Why now"

    patched = briefing_client.patch(
        f"/api/research-projects/{pid}/leadership-briefings/{briefing['briefing_id']}",
        json={"status": "in_review", "readiness": "ready"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["leadership_briefing"]["readiness"] == "ready"


def test_leadership_briefing_api_validation_and_blocking_approval(briefing_client):
    missing = briefing_client.post(
        "/api/research-projects/rp_000000000000/leadership-briefings",
        json={"idempotency_key": "missing", "title": "Briefing", "audience": "a", "purpose": "p"},
    )
    assert missing.status_code == 404

    pid, card, option, plan, decision = _seed(briefing_client)
    bad_ref = briefing_client.post(
        f"/api/research-projects/{pid}/leadership-briefings",
        json={**_payload(card, option, plan, decision), "idempotency_key": "bad-ref", "source_asset_refs": [{"asset_type": "insight_card", "asset_id": "ic_missing"}]},
    )
    assert bad_ref.status_code == 400

    created = briefing_client.post(f"/api/research-projects/{pid}/leadership-briefings", json=_payload(card, option, plan, decision))
    briefing = created.get_json()["data"]["leadership_briefing"]
    blocked = briefing_client.patch(
        f"/api/research-projects/{pid}/leadership-briefings/{briefing['briefing_id']}",
        json={
            "review_rounds": [{
                "reviewer": "strategy reviewer",
                "decision": "changes_requested",
                "blocking": True,
                "resolved": False,
            }],
        },
    ).get_json()["data"]["leadership_briefing"]
    approval = briefing_client.patch(
        f"/api/research-projects/{pid}/leadership-briefings/{briefing['briefing_id']}",
        json={"status": "approved", "readiness": "approved"},
    )
    assert approval.status_code == 400
    assert "unresolved blocking review" in approval.get_json()["error"]

    reviews = [{**blocked["review_rounds"][0], "resolved": True}]
    approved = briefing_client.patch(
        f"/api/research-projects/{pid}/leadership-briefings/{briefing['briefing_id']}",
        json={"review_rounds": reviews, "status": "approved", "readiness": "approved"},
    )
    assert approved.status_code == 200
    assert approved.get_json()["data"]["leadership_briefing"]["status"] == "approved"
