from __future__ import annotations

import pytest
from flask import Flask

from app.api.routes.research_project_governance import research_project_governance_bp
from app.api.routes.research_project_snapshots import research_project_snapshots_bp
from app.models.research_project import ResearchProjectStore

from test_research_project_traceability_map_service import _seed_full_chain


@pytest.fixture
def snapshot_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_project_governance_bp)
    app.register_blueprint(research_project_snapshots_bp)
    return app.test_client()


def test_snapshot_api_create_list_get_and_diff(snapshot_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    review = snapshot_client.post(f"/api/research-projects/{project_id}/governance-reviews", json={
        "idempotency_key": "p11-api-review",
        "title": "P11 API review",
        "seed_from_traceability_map": True,
    }).get_json()["data"]["governance_review"]

    created = snapshot_client.post(f"/api/research-projects/{project_id}/snapshots", json={
        "title": "P11 API Gate Baseline",
        "reason": "Freeze API state.",
        "gate_type": "p11_gate",
        "governance_review_id": review["review_id"],
    })
    assert created.status_code == 201
    snapshot = created.get_json()["data"]["snapshot"]
    assert snapshot["snapshot_id"].startswith("rs_")

    listed = snapshot_client.get(f"/api/research-projects/{project_id}/snapshots")
    assert listed.status_code == 200
    assert listed.get_json()["data"]["snapshots"][0]["snapshot_id"] == snapshot["snapshot_id"]

    detail = snapshot_client.get(f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["snapshot"]["snapshot_fingerprint"] == snapshot["snapshot_fingerprint"]

    diff = snapshot_client.get(f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/diff")
    assert diff.status_code == 200
    body = diff.get_json()["data"]["snapshot_diff"]
    assert body["snapshot_id"] == snapshot["snapshot_id"]
    assert body["summary"]["review_history_changed"] is True


def test_snapshot_api_missing_project_and_bad_payload(snapshot_client):
    missing = snapshot_client.get("/api/research-projects/rp_000000000000/snapshots")
    assert missing.status_code == 404

    project_id, _ = _seed_full_chain(ResearchProjectStore())
    bad = snapshot_client.post(f"/api/research-projects/{project_id}/snapshots", json={
        "reason": "missing title",
    })
    assert bad.status_code == 400

    bad_kind = snapshot_client.post(f"/api/research-projects/{project_id}/snapshots", json={
        "title": "Bad kind",
        "included_asset_kinds": ["project", "nope"],
    })
    assert bad_kind.status_code == 400


def test_snapshot_api_read_diff_does_not_create_history(snapshot_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    created = snapshot_client.post(f"/api/research-projects/{project_id}/snapshots", json={
        "title": "P11 side-effect baseline",
    }).get_json()["data"]["snapshot"]

    store = ResearchProjectStore()
    before = store.list_review_history(project_id)
    snapshot_client.get(f"/api/research-projects/{project_id}/snapshots")
    snapshot_client.get(f"/api/research-projects/{project_id}/snapshots/{created['snapshot_id']}")
    snapshot_client.get(f"/api/research-projects/{project_id}/snapshots/{created['snapshot_id']}/diff")
    after = store.list_review_history(project_id)

    assert after == before
