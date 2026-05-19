from __future__ import annotations

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError

from test_research_project_traceability_map_service import _seed_full_chain


def _review_payload(suffix: str = "p9-review"):
    return {
        "idempotency_key": suffix,
        "title": "P9 strategic research governance review",
        "review_type": "stage_gate",
        "seed_from_traceability_map": True,
    }


def _pass_required_checks(review):
    return [
        {
            **item,
            "status": "pass" if item.get("required") else item.get("status", "open"),
        }
        for item in review.get("checklist_items") or []
    ]


def test_governance_review_seeds_from_traceability_and_persists(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    store.create_insight_card(project_id, {
        "idempotency_key": "p9-unsupported",
        "title": "Unsupported watch insight",
        "claim": "A watch item without support.",
        "implication": "Governance should triage this before stage exit.",
    })

    review, replay = store.create_governance_review(project_id, _review_payload())

    assert replay is False
    assert review["review_id"].startswith("gr_")
    assert review["traceability_map_version"]["node_count"] >= 10
    assert any(item["item_id"] == "chk_manual_signoff" for item in review["checklist_items"])
    assert any(finding["source"] == "traceability_map" for finding in review["findings"])
    assert review["review_summary"]["failed_required_count"] >= 1

    root = tmp_path / "research_projects" / project_id
    assert (root / "governance_reviews" / f"{review['review_id']}.json").exists()
    listed = store.list_governance_reviews(project_id)
    assert listed[0]["review_id"] == review["review_id"]
    assert "findings" not in listed[0]
    assert listed[0]["finding_count"] == len(review["findings"])

    replayed, is_replay = store.create_governance_review(project_id, _review_payload())
    assert is_replay is True
    assert replayed["review_id"] == review["review_id"]


def test_governance_review_gate_rules_require_resolved_findings_and_signoff(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)
    review, _ = store.create_governance_review(project_id, {
        **_review_payload("p9-gate-rules"),
        "findings": [{
            "finding_id": "gf_manual_major",
            "finding_type": "manual_gap",
            "severity": "major",
            "status": "open",
            "asset_ref": {"asset_type": "leadership_briefing", "asset_id": assets["briefing"]["briefing_id"]},
            "description": "Leadership ask needs explicit KPI wording.",
            "source": "manual",
        }],
    })

    try:
        store.update_governance_review(project_id, review["review_id"], {"gate_decision": "ready"})
    except ResearchProjectStoreError as exc:
        assert "ready governance reviews require" in str(exc)
    else:
        raise AssertionError("expected ready gate failure")

    accepted_findings = [
        {**finding, "status": "accepted_risk"}
        for finding in review["findings"]
    ]
    signed = store.update_governance_review(project_id, review["review_id"], {
        "status": "signed_off",
        "gate_decision": "ready_with_risks",
        "readiness": "ready",
        "checklist_items": _pass_required_checks(review),
        "findings": accepted_findings,
        "review_summary": {"summary_note": "Known risks accepted for next-stage planning."},
        "signoffs": [{
            "role": "strategy_owner",
            "name": "P9 reviewer",
            "decision": "approved_with_risks",
            "comment": "Proceed with documented risks.",
        }],
    })

    assert signed["review_summary"]["ready_for_next_stage"] is True
    assert signed["gate_decision"] == "ready_with_risks"


def test_governance_review_rejects_runtime_fields_and_preserves_upstream_assets(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    before = store.get(project_id).to_dict()

    try:
        store.create_governance_review(project_id, {
            **_review_payload("p9-runtime"),
            "llm_client": "forbidden",
        })
    except ResearchProjectStoreError as exc:
        assert "runtime execution fields" in str(exc)
    else:
        raise AssertionError("expected runtime field failure")

    store.create_governance_review(project_id, _review_payload("p9-no-mutate"))
    after = store.get(project_id).to_dict()

    for field in [
        "evidence_items",
        "evidence_matrix_rows",
        "insight_cards",
        "artifact_drafts",
        "artifact_packs",
        "strategic_options",
        "validation_plans",
        "leadership_decision_records",
        "leadership_briefings",
    ]:
        assert after[field] == before[field]
