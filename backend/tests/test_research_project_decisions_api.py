from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_artifact_packs import research_project_artifact_packs_bp
from app.api.routes.research_project_decisions import research_project_decisions_bp
from app.api.routes.research_project_synthesis import research_project_synthesis_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def decision_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_synthesis_bp)
    app.register_blueprint(research_project_artifact_packs_bp)
    app.register_blueprint(research_project_decisions_bp)
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
            "idempotency_key": "p6-row-api",
            "question": "Q",
            "claim": "Agent Harness 是关键控制点。",
            "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        },
    ).get_json()["data"]["row"]
    card = client.post(
        f"/api/research-projects/{pid}/insight-cards",
        json={
            "idempotency_key": "p6-card-api",
            "title": "执行治理面是长期控制点",
            "claim": "控制点不在模型能力本身。",
            "implication": "升级企业级工程化平台。",
            "supporting_evidence_ids": ["ev_local_harness"],
            "matrix_row_ids": [row["id"]],
        },
    ).get_json()["data"]["insight_card"]
    draft = client.post(
        f"/api/research-projects/{pid}/artifact-drafts",
        json={
            "idempotency_key": "p6-draft-api",
            "artifact_type": "slide_outline",
            "title": "5 页战略材料大纲",
            "purpose": "形成材料输入。",
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness"],
        },
    ).get_json()["data"]["artifact_draft"]
    pack = client.post(
        f"/api/research-projects/{pid}/artifact-packs",
        json={
            "idempotency_key": "p6-pack-api",
            "title": "华为云 Agent-ready 战略材料包",
            "purpose": "面向领导汇报战略判断。",
            "source_artifact_draft_ids": [draft["id"]],
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness"],
        },
    ).get_json()["data"]["artifact_pack"]
    return pid, row, card, pack


def test_decision_api_huawei_agent_ready_flow(decision_client):
    pid, row, card, pack = _seed(decision_client)

    option_response = decision_client.post(
        f"/api/research-projects/{pid}/strategic-options",
        json={
            "idempotency_key": "p6-option-api",
            "title": "L2 Agent-ready 适配层 + L4 企业级 Harness 作为战略控制点",
            "summary": "将适配层和 Harness 作为华为云企业 Agent 控制面。",
            "source_insight_ids": [card["id"]],
            "source_evidence_matrix_row_ids": [row["id"]],
            "source_evidence_ids": ["ev_local_harness"],
            "source_artifact_pack_ids": [pack["pack_id"]],
            "assumptions": [{"statement": "企业客户更关注执行治理。", "criticality": "high"}],
            "risks": [{"statement": "首客深交付难以复用。", "severity": "high"}],
            "success_metrics": [{"name": "second_customer_adaptation_time", "target": "<= 4 weeks"}],
        },
    )
    assert option_response.status_code == 201
    option = option_response.get_json()["data"]["strategic_option"]

    plan_response = decision_client.post(
        f"/api/research-projects/{pid}/validation-plans",
        json={
            "idempotency_key": "p6-plan-api",
            "title": "90-day ERP/Test Harness pilot validation",
            "linked_option_ids": [option["option_id"]],
            "validation_questions": [
                {"question": "客户是否愿意接入真实权限和审批？"},
                {"question": "Harness 资产是否能在第二客户复用？"},
            ],
            "validation_methods": [
                {"method_type": "customer_pilot", "description": "ERP/Test Harness 试点", "execution_location": "external"},
            ],
            "milestones": [{"name": "Week 2 first business action", "status": "planned"}],
            "metrics": [{"name": "harness_reuse_ratio", "target": ">= 60%"}],
        },
    )
    assert plan_response.status_code == 201
    plan = plan_response.get_json()["data"]["validation_plan"]

    decision_response = decision_client.post(
        f"/api/research-projects/{pid}/leadership-decision-records",
        json={
            "idempotency_key": "p6-decision-api",
            "title": "Decision on Agent-ready enterprise software stack control point",
            "linked_option_ids": [option["option_id"]],
            "linked_validation_plan_ids": [plan["plan_id"]],
            "chosen_option_id": option["option_id"],
            "rationale": [{"statement": "L2 + L4 更贴近企业落地控制点。"}],
            "review_rounds": [{
                "reviewer": "VP-level reviewer",
                "decision": "needs_revision",
                "comments": "补充首客复用和交付毛利指标。",
                "blocking": True,
                "resolved": False,
            }],
        },
    )
    assert decision_response.status_code == 201
    decision = decision_response.get_json()["data"]["leadership_decision_record"]

    blocked = decision_client.patch(
        f"/api/research-projects/{pid}/leadership-decision-records/{decision['decision_id']}",
        json={"decision_status": "approved"},
    )
    assert blocked.status_code == 400
    assert "unresolved blocking review" in blocked.get_json()["error"]

    review_rounds = [{**decision["review_rounds"][0], "resolved": True}]
    approved = decision_client.patch(
        f"/api/research-projects/{pid}/leadership-decision-records/{decision['decision_id']}",
        json={"review_rounds": review_rounds, "decision_status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.get_json()["data"]["leadership_decision_record"]["decision_status"] == "approved"

    listed = decision_client.get(f"/api/research-projects/{pid}/strategic-options")
    assert listed.status_code == 200
    assert listed.get_json()["data"]["strategic_options"][0]["option_id"] == option["option_id"]


def test_decision_api_validation_errors(decision_client):
    missing = decision_client.post(
        "/api/research-projects/rp_000000000000/strategic-options",
        json={"idempotency_key": "missing", "title": "Option"},
    )
    assert missing.status_code == 404

    pid, _, _, _ = _seed(decision_client)
    bad_option = decision_client.post(
        f"/api/research-projects/{pid}/strategic-options",
        json={
            "idempotency_key": "bad-option",
            "title": "Bad",
            "source_insight_ids": ["ic_000000000000"],
        },
    )
    assert bad_option.status_code == 400

    runtime = decision_client.post(
        f"/api/research-projects/{pid}/validation-plans",
        json={"idempotency_key": "bad-runtime", "title": "Bad", "worker_id": "kfc_worker_1"},
    )
    assert runtime.status_code == 400
    assert "runtime execution fields" in runtime.get_json()["error"]
