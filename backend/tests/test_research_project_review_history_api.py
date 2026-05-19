from __future__ import annotations

import pytest
from flask import Flask

from app.api.routes.research_project_governance import research_project_governance_bp
from app.api.routes.research_project_review_history import research_project_review_history_bp
from app.models.research_project import ResearchProjectStore

from test_research_project_traceability_map_service import _seed_full_chain


@pytest.fixture
def history_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_project_governance_bp)
    app.register_blueprint(research_project_review_history_bp)
    return app.test_client()


def test_review_history_api_lists_filters_and_gets_asset_history(history_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    review = history_client.post(f"/api/research-projects/{project_id}/governance-reviews", json={
        "idempotency_key": "p10-api-review",
        "title": "P10 review history source review",
        "seed_from_traceability_map": True,
    }).get_json()["data"]["governance_review"]

    history_client.patch(
        f"/api/research-projects/{project_id}/governance-reviews/{review['review_id']}",
        json={"status": "in_review", "gate_decision": "blocked"},
    )

    listed = history_client.get(f"/api/research-projects/{project_id}/review-history?asset_type=governance_review")
    assert listed.status_code == 200
    entry = listed.get_json()["data"]["review_history_entries"][0]
    assert entry["asset_type"] == "governance_review"
    assert entry["event_type"] == "gate_decision_changed"

    detail = history_client.get(f"/api/research-projects/{project_id}/review-history/{entry['history_entry_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["review_history_entry"]["history_entry_id"] == entry["history_entry_id"]

    asset_history = history_client.get(
        f"/api/research-projects/{project_id}/review-history/assets/governance_review/{review['review_id']}"
    )
    assert asset_history.status_code == 200
    assert asset_history.get_json()["data"]["total"] == 1


def test_review_history_note_api_does_not_mutate_governance_review(history_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    review = history_client.post(f"/api/research-projects/{project_id}/governance-reviews", json={
        "idempotency_key": "p10-api-note-review",
        "title": "P10 review history note review",
        "seed_from_traceability_map": True,
    }).get_json()["data"]["governance_review"]
    before = history_client.get(
        f"/api/research-projects/{project_id}/governance-reviews/{review['review_id']}"
    ).get_json()["data"]["governance_review"]

    created = history_client.post(f"/api/research-projects/{project_id}/review-history/notes", json={
        "asset_type": "governance_review",
        "asset_id": review["review_id"],
        "note": "Accepted remaining risk for leadership readout.",
        "actor": {"actor_type": "manual_user", "display_name": "Reviewer"},
    })
    assert created.status_code == 201
    assert created.get_json()["data"]["review_history_entry"]["event_type"] == "review_note_added"

    after = history_client.get(
        f"/api/research-projects/{project_id}/governance-reviews/{review['review_id']}"
    ).get_json()["data"]["governance_review"]
    assert after == before


def test_review_history_api_missing_project_and_bad_limit(history_client):
    missing = history_client.get("/api/research-projects/rp_000000000000/review-history")
    assert missing.status_code == 404

    project_id, _ = _seed_full_chain(ResearchProjectStore())
    bad = history_client.get(f"/api/research-projects/{project_id}/review-history?limit=nope")
    assert bad.status_code == 400
