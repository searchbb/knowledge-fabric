from __future__ import annotations

from app.models.research_project import ResearchProjectStore
from app.services.research_traceability_map import build_traceability_map

from test_research_project_traceability_map_service import _seed_full_chain


def _review(store: ResearchProjectStore, project_id: str):
    review, _ = store.create_governance_review(project_id, {
        "idempotency_key": "p10-review",
        "title": "P10 review history source review",
        "seed_from_traceability_map": True,
    })
    return review


def test_review_history_records_governance_review_patch_and_persists(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    review = _review(store, project_id)

    updated = store.update_governance_review(project_id, review["review_id"], {
        "status": "in_review",
        "gate_decision": "blocked",
        "readiness": "not_ready",
    })
    entries = store.list_review_history(project_id)

    assert updated["gate_decision"] == "blocked"
    assert len(entries) == 1
    assert entries[0]["history_entry_id"].startswith("rhe_")
    assert entries[0]["asset_type"] == "governance_review"
    assert entries[0]["event_type"] == "gate_decision_changed"
    assert any(change["path"] == "gate_decision" for change in entries[0]["changed_fields"])
    assert (tmp_path / "research_projects" / project_id / "review_history" / f"{entries[0]['history_entry_id']}.json").exists()
    assert store.get(project_id).review_history_entries[0]["history_entry_id"] == entries[0]["history_entry_id"]


def test_review_history_records_leadership_briefing_patch_as_second_asset_type(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)

    store.update_leadership_briefing(project_id, assets["briefing"]["briefing_id"], {
        "status": "in_review",
        "readiness": "needs_review",
    })
    entries = store.list_review_history(project_id, asset_type="leadership_briefing")

    assert len(entries) == 1
    assert entries[0]["asset_id"] == assets["briefing"]["briefing_id"]
    assert entries[0]["event_type"] in {"status_changed", "readiness_changed"}


def test_review_history_noop_patch_and_read_views_are_side_effect_free(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    review = _review(store, project_id)

    assert store.list_review_history(project_id) == []
    store.update_governance_review(project_id, review["review_id"], {"status": review["status"]})
    assert store.list_review_history(project_id) == []

    build_traceability_map(project_id, store=store)
    assert store.list_review_history(project_id) == []

    store.list_review_history(project_id)
    assert store.list_review_history(project_id) == []


def test_manual_review_note_creates_history_without_mutating_asset(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    review = _review(store, project_id)
    before = store.get_governance_review(project_id, review["review_id"])

    note = store.create_review_history_note(project_id, {
        "asset_type": "governance_review",
        "asset_id": review["review_id"],
        "note": "Accepted remaining risk for leadership readout.",
        "actor": {"actor_type": "manual_user", "display_name": "Reviewer"},
    })
    after = store.get_governance_review(project_id, review["review_id"])

    assert note["event_type"] == "review_note_added"
    assert note["note"] == "Accepted remaining risk for leadership readout."
    assert before == after
    assert store.list_review_history(project_id, asset_id=review["review_id"])[0]["history_entry_id"] == note["history_entry_id"]


def test_review_history_large_text_diff_is_truncated(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)
    large_summary = "x" * 1200

    store.update_leadership_briefing(project_id, assets["briefing"]["briefing_id"], {
        "executive_summary": {
            "headline": large_summary,
            "key_message": "Updated message",
            "leadership_ask": "Approve",
            "decision_required": True,
        },
    })
    entry = store.list_review_history(project_id, asset_type="leadership_briefing")[0]
    executive_change = next(change for change in entry["changed_fields"] if change["path"] == "executive_summary")

    assert executive_change["new_value"]["truncated"] is True
    assert executive_change["new_value"]["hash"].startswith("sha256:")
