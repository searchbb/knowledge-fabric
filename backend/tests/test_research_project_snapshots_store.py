from __future__ import annotations

import json

import pytest

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError

from test_research_project_traceability_map_service import _seed_full_chain


def _review(store: ResearchProjectStore, project_id: str):
    review, _ = store.create_governance_review(project_id, {
        "idempotency_key": "p11-review",
        "title": "P11 gate baseline review",
        "seed_from_traceability_map": True,
    })
    return review


def _snapshot(store: ResearchProjectStore, project_id: str, review_id: str = ""):
    return store.create_research_snapshot(project_id, {
        "title": "P11 Gate Baseline",
        "reason": "Freeze current state before follow-up changes.",
        "gate_type": "p11_gate",
        "actor": {"actor_type": "manual_user", "display_name": "Reviewer"},
        "governance_review_id": review_id,
    })


def _json_files(root):
    return sorted(str(path.relative_to(root)) for path in root.rglob("*.json"))


def test_research_snapshot_creates_sidecar_index_and_history_event(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    review = _review(store, project_id)
    before_history = store.list_review_history(project_id)

    snapshot = _snapshot(store, project_id, review["review_id"])
    project = store.get(project_id)
    history = store.list_review_history(project_id, asset_type="research_snapshot")

    assert snapshot["snapshot_id"].startswith("rs_")
    assert snapshot["snapshot_fingerprint"].startswith("sha256:")
    assert snapshot["review_history_watermark"]["entry_count"] == len(before_history)
    assert snapshot["linked_governance_review"]["governance_review_id"] == review["review_id"]
    assert snapshot["asset_kind_summaries"]["governance_reviews"]["count"] == 1
    assert (tmp_path / "research_projects" / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json").exists()
    assert project.research_snapshots[0]["snapshot_id"] == snapshot["snapshot_id"]
    assert len(history) == 1
    assert history[0]["event_type"] == "research_snapshot_created"


def test_research_snapshot_diff_detects_added_asset_and_gate_change(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)
    review = _review(store, project_id)
    snapshot = _snapshot(store, project_id, review["review_id"])

    store.create_insight_card(project_id, {
        "idempotency_key": "p11-added-card",
        "title": "New post-baseline insight",
        "claim": "A new claim after baseline.",
        "implication": "Diff should show an added insight.",
        "supporting_evidence_ids": ["ev_harness"],
    })
    store.update_governance_review(project_id, review["review_id"], {
        "gate_decision": "blocked",
        "readiness": "not_ready",
    })
    store.update_leadership_briefing(project_id, assets["briefing"]["briefing_id"], {
        "readiness": "needs_review",
    })

    diff = store.diff_research_snapshot_to_current(project_id, snapshot["snapshot_id"])

    assert diff["summary"]["has_changes"] is True
    assert diff["summary"]["assets_added"] >= 1
    assert diff["summary"]["governance_gate_decision_changed"] is True
    assert diff["summary"]["leadership_briefing_readiness_changed"] is True
    assert diff["asset_id_changes"]["insight_cards"]["added"]
    assert diff["governance_change"]["to_gate_decision"] == "blocked"
    assert diff["review_history_change"]["changed"] is True


def test_snapshot_reads_and_diff_are_side_effect_free(tmp_path):
    root = tmp_path / "research_projects"
    store = ResearchProjectStore(root)
    project_id, _ = _seed_full_chain(store)
    review = _review(store, project_id)
    snapshot = _snapshot(store, project_id, review["review_id"])
    before_files = _json_files(root)
    before_history = store.list_review_history(project_id)

    store.list_research_snapshots(project_id)
    store.get_research_snapshot(project_id, snapshot["snapshot_id"])
    first_diff = store.diff_research_snapshot_to_current(project_id, snapshot["snapshot_id"])
    second_diff = store.diff_research_snapshot_to_current(project_id, snapshot["snapshot_id"])

    assert _json_files(root) == before_files
    assert store.list_review_history(project_id) == before_history
    assert first_diff["summary"]["has_changes"] == second_diff["summary"]["has_changes"]


def test_snapshot_sidecar_is_not_rewritten_by_later_history(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    review = _review(store, project_id)
    snapshot = _snapshot(store, project_id, review["review_id"])
    path = tmp_path / "research_projects" / project_id / "research_snapshots" / f"{snapshot['snapshot_id']}.json"
    before = json.loads(path.read_text(encoding="utf-8"))

    store.create_review_history_note(project_id, {
        "asset_type": "governance_review",
        "asset_id": review["review_id"],
        "note": "Post-baseline note.",
    })
    after = json.loads(path.read_text(encoding="utf-8"))

    assert after == before
    assert after["review_history_watermark"] == snapshot["review_history_watermark"]


def test_snapshot_rejects_unknown_asset_kind_and_bad_review_ref(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)

    with pytest.raises(ResearchProjectStoreError, match="included_asset_kinds"):
        store.create_research_snapshot(project_id, {
            "title": "Bad snapshot",
            "included_asset_kinds": ["project", "unknown_kind"],
        })

    with pytest.raises(ResearchProjectStoreError, match="governance_review_id"):
        store.create_research_snapshot(project_id, {
            "title": "Bad review ref",
            "governance_review_id": "gr_000000000000",
        })
