from __future__ import annotations

import pytest
from flask import Flask

from app.api.routes.research_project_governance import research_project_governance_bp
from app.models.research_project import ResearchProjectStore

from test_research_project_traceability_map_service import _seed_full_chain


@pytest.fixture
def governance_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_project_governance_bp)
    return app.test_client()


def test_governance_review_api_flow(governance_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())

    created = governance_client.post(f"/api/research-projects/{project_id}/governance-reviews", json={
        "idempotency_key": "p9-api-review",
        "title": "P9 strategic research governance review",
        "seed_from_traceability_map": True,
    })
    assert created.status_code == 201
    review = created.get_json()["data"]["governance_review"]
    assert review["review_id"].startswith("gr_")
    assert review["review_summary"]["failed_required_count"] >= 1

    listed = governance_client.get(f"/api/research-projects/{project_id}/governance-reviews")
    assert listed.status_code == 200
    index_item = listed.get_json()["data"]["governance_reviews"][0]
    assert index_item["review_id"] == review["review_id"]
    assert index_item["checklist_count"] == len(review["checklist_items"])

    detail = governance_client.get(f"/api/research-projects/{project_id}/governance-reviews/{review['review_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["governance_review"]["title"] == review["title"]

    patched = governance_client.patch(
        f"/api/research-projects/{project_id}/governance-reviews/{review['review_id']}",
        json={"status": "in_review", "readiness": "partial"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["governance_review"]["status"] == "in_review"


def test_governance_review_api_validation(governance_client):
    missing = governance_client.post(
        "/api/research-projects/rp_000000000000/governance-reviews",
        json={"title": "Missing key"},
    )
    assert missing.status_code == 400

    not_found = governance_client.get("/api/research-projects/rp_000000000000/governance-reviews")
    assert not_found.status_code == 404

    project_id, _ = _seed_full_chain(ResearchProjectStore())
    bad_patch = governance_client.post(f"/api/research-projects/{project_id}/governance-reviews", json={
        "idempotency_key": "p9-api-bad",
        "title": "P9 strategic research governance review",
        "seed_from_traceability_map": True,
    }).get_json()["data"]["governance_review"]

    response = governance_client.patch(
        f"/api/research-projects/{project_id}/governance-reviews/{bad_patch['review_id']}",
        json={"gate_decision": "ready"},
    )
    assert response.status_code == 400
    assert "ready governance reviews require" in response.get_json()["error"]
