from __future__ import annotations

from flask import Flask
import pytest

from app.api.routes.research_project_traceability import research_project_traceability_bp
from app.api.routes.research_projects import research_projects_bp
from app.models.research_project import ResearchProjectStore


@pytest.fixture()
def traceability_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_projects_bp)
    app.register_blueprint(research_project_traceability_bp)
    return app.test_client()


def _seed(store: ResearchProjectStore):
    project = store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "evidence_items": [{"evidence_id": "ev_harness", "title": "Harness", "status": "accepted"}],
    })
    row, _ = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "api-row",
        "question": "控制点在哪里？",
        "claim": "控制点在执行治理面。",
        "supporting_evidence_ids": ["ev_harness"],
    })
    card, _ = store.create_insight_card(project.id, {
        "idempotency_key": "api-card",
        "title": "执行治理面是长期控制点",
        "claim": "控制点不在模型能力本身。",
        "implication": "升级工程化平台。",
        "supporting_evidence_ids": ["ev_harness"],
        "matrix_row_ids": [row["id"]],
    })
    option, _ = store.create_strategic_option(project.id, {
        "idempotency_key": "api-option",
        "title": "L2 + L4 控制点选项",
        "source_insight_ids": [card["id"]],
    })
    plan, _ = store.create_validation_plan(project.id, {
        "idempotency_key": "api-plan",
        "title": "90-day pilot",
        "linked_option_ids": [option["option_id"]],
    })
    decision, _ = store.create_leadership_decision_record(project.id, {
        "idempotency_key": "api-decision",
        "title": "Decision",
        "linked_option_ids": [option["option_id"]],
        "linked_validation_plan_ids": [plan["plan_id"]],
    })
    briefing, _ = store.create_leadership_briefing(project.id, {
        "idempotency_key": "api-briefing",
        "title": "Leadership Readout",
        "audience": "strategy",
        "purpose": "review",
        "executive_summary": {"headline": "Control point", "decision_required": True},
        "source_asset_refs": [{"asset_type": "insight_card", "asset_id": card["id"], "required": True}],
        "sections": [{
            "order": 1,
            "title": "Why now",
            "section_type": "context",
            "summary": "Agent entry point shift.",
            "source_refs": [{"asset_type": "strategic_option", "asset_id": option["option_id"], "required": True}],
        }],
        "decision_asks": [{
            "title": "Approve pilot",
            "linked_option_ids": [option["option_id"]],
            "linked_validation_plan_ids": [plan["plan_id"]],
            "linked_decision_record_ids": [decision["decision_id"]],
        }],
    })
    return project.id, briefing["briefing_id"], card["id"]


def test_traceability_map_api_returns_computed_view(traceability_client):
    project_id, briefing_id, card_id = _seed(ResearchProjectStore())

    response = traceability_client.get(f"/api/research-projects/{project_id}/traceability-map")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["project_id"] == project_id
    assert data["view_type"] == "strategic_research_traceability_map"
    assert data["summary"]["node_count"] >= 7
    assert any(node["asset_id"] == briefing_id for node in data["nodes"])
    assert any(edge["to_node_id"] == f"insight_card:{card_id}" for edge in data["edges"])


def test_traceability_map_api_filters(traceability_client):
    project_id, briefing_id, _ = _seed(ResearchProjectStore())

    briefing_filtered = traceability_client.get(
        f"/api/research-projects/{project_id}/traceability-map?briefing_id={briefing_id}"
    ).get_json()["data"]
    assert any(node["asset_id"] == briefing_id for node in briefing_filtered["nodes"])

    insight_filtered = traceability_client.get(
        f"/api/research-projects/{project_id}/traceability-map?asset_type=insight_card"
    ).get_json()["data"]
    assert {node["asset_type"] for node in insight_filtered["nodes"]} == {"insight_card"}

    warning_filtered = traceability_client.get(
        f"/api/research-projects/{project_id}/traceability-map?issue_severity=warning"
    ).get_json()["data"]
    assert all(issue["severity"] == "warning" for issue in warning_filtered["issues"])


def test_traceability_map_api_missing_project_and_method_boundary(traceability_client):
    missing = traceability_client.get("/api/research-projects/rp_000000000000/traceability-map")
    assert missing.status_code == 404

    project_id, _, _ = _seed(ResearchProjectStore())
    assert traceability_client.post(f"/api/research-projects/{project_id}/traceability-map", json={}).status_code == 405
    assert traceability_client.patch(f"/api/research-projects/{project_id}/traceability-map", json={}).status_code == 405
    assert traceability_client.delete(f"/api/research-projects/{project_id}/traceability-map").status_code == 405
