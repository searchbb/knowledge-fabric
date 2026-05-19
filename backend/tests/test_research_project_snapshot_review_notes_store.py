from __future__ import annotations

import json

import pytest

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError

from test_research_project_traceability_map_service import _seed_full_chain


def _snapshot(store: ResearchProjectStore, project_id: str):
    review, _ = store.create_governance_review(project_id, {
        "idempotency_key": "p13-review",
        "title": "P13 note baseline review",
        "seed_from_traceability_map": True,
    })
    return store.create_research_snapshot(project_id, {
        "title": "P13 Gate Baseline",
        "reason": "Freeze current state before manual annotation.",
        "gate_type": "p13_gate",
        "governance_review_id": review["review_id"],
    })


def _note_payload(**overrides):
    payload = {
        "target_ref": {
            "section_key": "governance_gate",
            "asset_kind": "governance_review",
            "asset_id": "gr_demo",
            "field": "gate_decision",
        },
        "note_type": "observation",
        "severity": "watch",
        "note": "Manual reviewer note on the governance gate movement.",
        "actor": {"actor_type": "manual_user", "display_name": "Reviewer"},
    }
    payload.update(overrides)
    return payload


def test_snapshot_review_note_creates_sidecar_index_and_exactly_one_history(tmp_path):
    root = tmp_path / "research_projects"
    store = ResearchProjectStore(root)
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    before_history = store.list_review_history(project_id)
    snapshot_path = root / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json"
    snapshot_before = json.loads(snapshot_path.read_text(encoding="utf-8"))

    result = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())
    note = result["snapshot_review_note"]
    history = result["review_history_entry"]
    project = store.get(project_id)
    after_history = store.list_review_history(project_id)

    assert note["note_id"].startswith("srn_")
    assert note["snapshot_id"] == snapshot["snapshot_id"]
    assert note["target_ref"]["section_key"] == "governance_gate"
    assert note["status"] == "open"
    assert (root / project_id / "snapshot_review_notes" / f"{note['note_id']}.json").exists()
    assert project.snapshot_review_notes[0]["note_id"] == note["note_id"]
    assert "note" not in project.snapshot_review_notes[0]
    assert len(after_history) == len(before_history) + 1
    assert history["event_type"] == "snapshot_review_note_created"
    assert history["asset_type"] == "snapshot_review_note"
    assert history["asset_id"] == note["note_id"]
    assert history["metadata"]["snapshot_id"] == snapshot["snapshot_id"]
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == snapshot_before


def test_snapshot_review_note_list_get_and_reads_are_side_effect_free(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    created = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())["snapshot_review_note"]
    before_history = store.list_review_history(project_id)

    listed = store.list_snapshot_review_notes(project_id, snapshot["snapshot_id"])
    detail = store.get_snapshot_review_note(project_id, snapshot["snapshot_id"], created["note_id"])
    after_history = store.list_review_history(project_id)

    assert listed[0]["note_id"] == created["note_id"]
    assert detail["note"] == created["note"]
    assert after_history == before_history


def test_snapshot_review_notes_are_snapshot_scoped(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    first = _snapshot(store, project_id)
    second = store.create_research_snapshot(project_id, {"title": "Second baseline"})
    first_note = store.create_snapshot_review_note(project_id, first["snapshot_id"], _note_payload())["snapshot_review_note"]
    second_note = store.create_snapshot_review_note(project_id, second["snapshot_id"], _note_payload(
        target_ref={"section_key": "leadership_briefing_readiness"},
        note="Manual note for second snapshot.",
    ))["snapshot_review_note"]

    first_notes = store.list_snapshot_review_notes(project_id, first["snapshot_id"])
    second_notes = store.list_snapshot_review_notes(project_id, second["snapshot_id"])

    assert [item["note_id"] for item in first_notes] == [first_note["note_id"]]
    assert [item["note_id"] for item in second_notes] == [second_note["note_id"]]


def test_snapshot_review_note_rejects_invalid_payloads(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)

    bad_payloads = [
        _note_payload(note=""),
        _note_payload(target_ref={"section_key": "gate_decision"}),
        _note_payload(note_type="approval"),
        _note_payload(severity="critical"),
        _note_payload(model_provider="bailian"),
        _note_payload(target_ref={"section_key": "raw_diff", "workflow_id": "wf_1"}),
        _note_payload(status="resolved"),
    ]

    for payload in bad_payloads:
        with pytest.raises(ResearchProjectStoreError):
            store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], payload)


def test_snapshot_review_note_rejects_missing_snapshot(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)

    with pytest.raises(ResearchProjectStoreError, match="research snapshot not found"):
        store.create_snapshot_review_note(project_id, "rs_000000000000", _note_payload())


def test_snapshot_review_note_disposition_updates_sidecar_and_history(tmp_path):
    root = tmp_path / "research_projects"
    store = ResearchProjectStore(root)
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    note = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())["snapshot_review_note"]
    before_history = store.list_review_history(project_id)
    snapshot_before = json.loads((root / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json").read_text(encoding="utf-8"))

    result = store.update_snapshot_review_note(project_id, snapshot["snapshot_id"], note["note_id"], {
        "status": "acknowledged",
        "owner": "Reviewer A",
        "resolution_note": "Known evidence gap; track manually.",
        "actor": {"actor_type": "manual_user", "display_name": "Reviewer A"},
    })
    updated = result["snapshot_review_note"]
    history = result["review_history_entry"]
    after_history = store.list_review_history(project_id)

    assert updated["status"] == "acknowledged"
    assert updated["owner"] == "Reviewer A"
    assert updated["resolution_note"] == "Known evidence gap; track manually."
    assert updated["resolved_at"] == ""
    assert updated["resolved_by"] == ""
    assert len(after_history) == len(before_history) + 1
    assert history["event_type"] == "snapshot_review_note_disposition_updated"
    assert history["asset_id"] == note["note_id"]
    assert history["metadata"]["status_before"] == "open"
    assert history["metadata"]["status_after"] == "acknowledged"
    assert {field["path"] for field in history["changed_fields"]} == {
        "snapshot_review_notes.status",
        "snapshot_review_notes.owner",
        "snapshot_review_notes.resolution_note",
    }
    assert json.loads((root / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json").read_text(encoding="utf-8")) == snapshot_before


def test_snapshot_review_note_resolved_metadata_and_reopen(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    note = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())["snapshot_review_note"]

    resolved = store.update_snapshot_review_note(project_id, snapshot["snapshot_id"], note["note_id"], {
        "status": "resolved",
        "resolution_note": "Manual reviewer confirmed the diff is acceptable.",
        "actor": "Reviewer B",
    })["snapshot_review_note"]

    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"]
    assert resolved["resolved_by"] == "Reviewer B"

    reopened = store.update_snapshot_review_note(project_id, snapshot["snapshot_id"], note["note_id"], {
        "status": "open",
        "actor": "Reviewer C",
    })["snapshot_review_note"]

    assert reopened["status"] == "open"
    assert reopened["resolved_at"] == ""
    assert reopened["resolved_by"] == ""
    assert reopened["resolution_note"] == "Manual reviewer confirmed the diff is acceptable."


def test_snapshot_review_note_noop_update_writes_no_history(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    note = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())["snapshot_review_note"]
    before_history = store.list_review_history(project_id)

    result = store.update_snapshot_review_note(project_id, snapshot["snapshot_id"], note["note_id"], {
        "status": "open",
        "actor": "Reviewer",
    })

    assert result["review_history_entry"] is None
    assert store.list_review_history(project_id) == before_history


def test_snapshot_review_note_update_rejects_invalid_payloads(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    note = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())["snapshot_review_note"]

    bad_payloads = [
        {"status": "closed", "actor": "Reviewer"},
        {"status": "acknowledged"},
        {"status": "acknowledged", "actor": ""},
        {"note": "edit original note", "actor": "Reviewer"},
        {"workflow_id": "wf_1", "actor": "Reviewer"},
        {"snapshot_id": "rs_000000000000", "actor": "Reviewer"},
    ]

    for payload in bad_payloads:
        with pytest.raises(ResearchProjectStoreError):
            store.update_snapshot_review_note(project_id, snapshot["snapshot_id"], note["note_id"], payload)


def test_snapshot_review_note_update_does_not_mutate_upstream_assets(tmp_path):
    root = tmp_path / "research_projects"
    store = ResearchProjectStore(root)
    project_id, assets = _seed_full_chain(store)
    snapshot = _snapshot(store, project_id)
    note = store.create_snapshot_review_note(project_id, snapshot["snapshot_id"], _note_payload())["snapshot_review_note"]
    snapshot_before = json.loads((root / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json").read_text(encoding="utf-8"))
    review_before = store.get_governance_review(project_id, snapshot["linked_governance_review"]["governance_review_id"])
    briefing_before = store.get_leadership_briefing(project_id, assets["briefing"]["briefing_id"])

    store.update_snapshot_review_note(project_id, snapshot["snapshot_id"], note["note_id"], {
        "status": "deferred",
        "owner": "Reviewer D",
        "actor": "Reviewer D",
    })

    assert json.loads((root / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json").read_text(encoding="utf-8")) == snapshot_before
    assert store.get_governance_review(project_id, snapshot["linked_governance_review"]["governance_review_id"]) == review_before
    assert store.get_leadership_briefing(project_id, assets["briefing"]["briefing_id"]) == briefing_before
