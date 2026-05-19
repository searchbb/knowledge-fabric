from __future__ import annotations

import pytest
from flask import Flask

from app.api.routes.research_project_governance import research_project_governance_bp
from app.api.routes.research_project_snapshot_review_notes import research_project_snapshot_review_notes_bp
from app.api.routes.research_project_snapshots import research_project_snapshots_bp
from app.models.research_project import ResearchProjectStore

from test_research_project_traceability_map_service import _seed_full_chain


@pytest.fixture
def notes_client(tmp_path, monkeypatch):
    monkeypatch.setattr(ResearchProjectStore, "ROOT_DIR", tmp_path / "research_projects")
    app = Flask(__name__)
    app.register_blueprint(research_project_governance_bp)
    app.register_blueprint(research_project_snapshots_bp)
    app.register_blueprint(research_project_snapshot_review_notes_bp)
    return app.test_client()


def _create_snapshot(client, project_id):
    review = client.post(f"/api/research-projects/{project_id}/governance-reviews", json={
        "idempotency_key": "p13-api-review",
        "title": "P13 API governance review",
        "seed_from_traceability_map": True,
    }).get_json()["data"]["governance_review"]
    return client.post(f"/api/research-projects/{project_id}/snapshots", json={
        "title": "P13 API Gate Baseline",
        "governance_review_id": review["review_id"],
    }).get_json()["data"]["snapshot"]


def _payload():
    return {
        "target_ref": {
            "section_key": "governance_gate",
            "asset_kind": "governance_review",
            "asset_id": "gr_demo",
            "field": "gate_decision",
        },
        "note_type": "question",
        "severity": "watch",
        "note": "Manual reviewer question about the gate movement.",
    }


def test_snapshot_review_note_api_create_list_get(notes_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    snapshot = _create_snapshot(notes_client, project_id)
    before_history = len(ResearchProjectStore().list_review_history(project_id))

    created = notes_client.post(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes",
        json=_payload(),
    )
    assert created.status_code == 201
    body = created.get_json()["data"]
    note = body["snapshot_review_note"]
    assert note["note_id"].startswith("srn_")
    assert body["review_history_entry_id"].startswith("rhe_")
    assert len(ResearchProjectStore().list_review_history(project_id)) == before_history + 1

    listed = notes_client.get(f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes")
    assert listed.status_code == 200
    assert listed.get_json()["data"]["snapshot_review_notes"][0]["note_id"] == note["note_id"]

    detail = notes_client.get(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{note['note_id']}"
    )
    assert detail.status_code == 200
    assert detail.get_json()["data"]["snapshot_review_note"]["note"] == note["note"]


def test_snapshot_review_note_api_reads_are_side_effect_free(notes_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    snapshot = _create_snapshot(notes_client, project_id)
    created = notes_client.post(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes",
        json=_payload(),
    ).get_json()["data"]["snapshot_review_note"]
    before = ResearchProjectStore().list_review_history(project_id)

    notes_client.get(f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes")
    notes_client.get(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{created['note_id']}"
    )
    after = ResearchProjectStore().list_review_history(project_id)

    assert after == before


def test_snapshot_review_note_api_validation(notes_client):
    missing = notes_client.get("/api/research-projects/rp_000000000000/snapshots/rs_000000000000/review-notes")
    assert missing.status_code == 404

    project_id, _ = _seed_full_chain(ResearchProjectStore())
    snapshot = _create_snapshot(notes_client, project_id)
    bad = notes_client.post(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes",
        json={**_payload(), "note_type": "approval"},
    )
    assert bad.status_code == 400

    missing_note = notes_client.get(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/srn_000000000000"
    )
    assert missing_note.status_code == 404


def test_snapshot_review_note_api_patch_updates_disposition(notes_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    snapshot = _create_snapshot(notes_client, project_id)
    note = notes_client.post(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes",
        json=_payload(),
    ).get_json()["data"]["snapshot_review_note"]
    before_history = len(ResearchProjectStore().list_review_history(project_id))

    response = notes_client.patch(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{note['note_id']}",
        json={
            "status": "resolved",
            "owner": "Reviewer A",
            "resolution_note": "Manual resolution recorded.",
            "actor": "Reviewer A",
        },
    )

    assert response.status_code == 200
    body = response.get_json()["data"]
    updated = body["snapshot_review_note"]
    assert body["history_recorded"] is True
    assert body["review_history_entry_id"].startswith("rhe_")
    assert updated["status"] == "resolved"
    assert updated["owner"] == "Reviewer A"
    assert updated["resolution_note"] == "Manual resolution recorded."
    assert updated["resolved_by"] == "Reviewer A"
    assert updated["resolved_at"]
    assert len(ResearchProjectStore().list_review_history(project_id)) == before_history + 1

    listed = notes_client.get(f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes")
    assert listed.get_json()["data"]["snapshot_review_notes"][0]["status"] == "resolved"


def test_snapshot_review_note_api_patch_noop_writes_no_history(notes_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    snapshot = _create_snapshot(notes_client, project_id)
    note = notes_client.post(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes",
        json=_payload(),
    ).get_json()["data"]["snapshot_review_note"]
    before_history = len(ResearchProjectStore().list_review_history(project_id))

    response = notes_client.patch(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{note['note_id']}",
        json={"status": "open", "actor": "Reviewer"},
    )

    assert response.status_code == 200
    body = response.get_json()["data"]
    assert body["history_recorded"] is False
    assert body["review_history_entry_id"] == ""
    assert len(ResearchProjectStore().list_review_history(project_id)) == before_history


def test_snapshot_review_note_api_patch_validation(notes_client):
    project_id, _ = _seed_full_chain(ResearchProjectStore())
    snapshot = _create_snapshot(notes_client, project_id)
    note = notes_client.post(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes",
        json=_payload(),
    ).get_json()["data"]["snapshot_review_note"]

    bad_status = notes_client.patch(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{note['note_id']}",
        json={"status": "closed", "actor": "Reviewer"},
    )
    assert bad_status.status_code == 400

    unknown_field = notes_client.patch(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{note['note_id']}",
        json={"workflow_id": "wf_1", "actor": "Reviewer"},
    )
    assert unknown_field.status_code == 400

    missing_actor = notes_client.patch(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/{note['note_id']}",
        json={"status": "acknowledged"},
    )
    assert missing_actor.status_code == 400

    missing_note = notes_client.patch(
        f"/api/research-projects/{project_id}/snapshots/{snapshot['snapshot_id']}/review-notes/srn_000000000000",
        json={"status": "acknowledged", "actor": "Reviewer"},
    )
    assert missing_note.status_code == 404
