from __future__ import annotations

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError


def _seed_p7(store: ResearchProjectStore):
    project = store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "evidence_items": [
            {"evidence_id": "ev_harness", "title": "企业级 Harness", "status": "accepted", "origin": "local", "scope": "C1_local"},
            {"evidence_id": "ei_governance", "title": "Agent governance", "status": "accepted", "origin": "external", "scope": "C2_external"},
        ],
    })
    row, _ = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "p7-row",
        "question": "控制点在哪里？",
        "claim": "控制点在执行治理面。",
        "supporting_evidence_ids": ["ev_harness", "ei_governance"],
    })
    card, _ = store.create_insight_card(project.id, {
        "idempotency_key": "p7-card",
        "title": "执行治理面是长期控制点",
        "claim": "控制点不在模型能力本身。",
        "implication": "AgentArts 应升级为工程化平台。",
        "supporting_evidence_ids": ["ev_harness"],
        "matrix_row_ids": [row["id"]],
    })
    draft, _ = store.create_artifact_draft(project.id, {
        "idempotency_key": "p7-draft",
        "artifact_type": "slide_outline",
        "title": "战略材料大纲",
        "purpose": "形成领导汇报材料输入。",
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
    })
    pack, _ = store.create_artifact_pack(project.id, {
        "idempotency_key": "p7-pack",
        "title": "战略材料包",
        "purpose": "面向领导汇报。",
        "source_artifact_draft_ids": [draft["id"]],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
    })
    option, _ = store.create_strategic_option(project.id, {
        "idempotency_key": "p7-option",
        "title": "L2 + L4 控制点选项",
        "source_insight_ids": [card["id"]],
        "source_evidence_matrix_row_ids": [row["id"]],
        "source_evidence_ids": ["ev_harness"],
    })
    plan, _ = store.create_validation_plan(project.id, {
        "idempotency_key": "p7-plan",
        "title": "90-day ERP/Test Harness pilot validation",
        "linked_option_ids": [option["option_id"]],
        "validation_questions": [{"question": "客户是否愿意接入真实权限？"}],
        "validation_methods": [{"method_type": "customer_pilot", "execution_location": "external"}],
        "metrics": [{"name": "harness_reuse_ratio", "target": ">= 60%"}],
    })
    decision, _ = store.create_leadership_decision_record(project.id, {
        "idempotency_key": "p7-decision",
        "title": "Decision on Agent-ready control point",
        "linked_option_ids": [option["option_id"]],
        "linked_validation_plan_ids": [plan["plan_id"]],
        "chosen_option_id": option["option_id"],
        "rationale": [{"statement": "L2 + L4 更贴近企业落地。"}],
    })
    return project.id, row, card, draft, pack, option, plan, decision


def _briefing_payload(card, option, plan, decision):
    return {
        "idempotency_key": "p7-briefing",
        "title": "Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout",
        "briefing_type": "strategic_readout",
        "audience": "cloud_strategy_leadership",
        "purpose": "Prepare leadership discussion on Agent-ready enterprise software stack strategy.",
        "executive_summary": {
            "headline": "Enterprise AI competition is moving to Agent-ready software stack control points.",
            "key_message": "Focus on L2 Agent-ready adaptation and L4 enterprise Harness.",
            "leadership_ask": "Approve 90-day ERP/Test Harness pilots.",
            "decision_required": True,
        },
        "source_asset_refs": [
            {"asset_type": "insight_card", "asset_id": card["id"], "required": True},
            {"asset_type": "strategic_option", "asset_id": option["option_id"], "required": True},
        ],
        "sections": [
            {
                "order": 1,
                "title": "Why now",
                "section_type": "context",
                "summary": "Agent operations are becoming a new enterprise software entry point.",
                "talking_points": ["Entry point shifts from UI navigation to agent-mediated operations."],
                "source_refs": [{"asset_type": "insight_card", "asset_id": card["id"], "required": True}],
            },
            {
                "order": 2,
                "title": "90-day validation plan",
                "section_type": "validation_plan",
                "summary": "Use ERP/Test Harness pilots to validate reusable control-layer assets.",
                "source_refs": [{"asset_type": "validation_plan", "asset_id": plan["plan_id"], "required": True}],
            },
        ],
        "decision_asks": [{
            "title": "Approve the first 90-day pilot path",
            "linked_option_ids": [option["option_id"]],
            "linked_validation_plan_ids": [plan["plan_id"]],
            "linked_decision_record_ids": [decision["decision_id"]],
        }],
    }


def test_leadership_briefing_sidecar_index_and_persistence(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, card, _, _, option, plan, decision = _seed_p7(store)

    briefing, replay = store.create_leadership_briefing(project_id, _briefing_payload(card, option, plan, decision))
    assert replay is False
    assert briefing["briefing_id"].startswith("lb_")
    assert briefing["sections"][0]["section_id"].startswith("lbs_")
    assert briefing["readiness_checks"]["has_executive_summary"] is True

    root = tmp_path / "research_projects" / project_id
    assert (root / "leadership_briefings" / f"{briefing['briefing_id']}.json").exists()

    listed = store.list_leadership_briefings(project_id)
    assert listed[0]["briefing_id"] == briefing["briefing_id"]
    assert "sections" not in listed[0]
    assert listed[0]["section_count"] == 2
    assert listed[0]["source_counts"]["insight_cards"] == 1

    reloaded = ResearchProjectStore(tmp_path / "research_projects")
    assert reloaded.get_leadership_briefing(project_id, briefing["briefing_id"])["title"] == briefing["title"]
    assert reloaded.get(project_id).leadership_briefings[0]["briefing_id"] == briefing["briefing_id"]


def test_leadership_briefing_validates_references_and_decision_asks(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, card, _, _, option, plan, decision = _seed_p7(store)
    payload = _briefing_payload(card, option, plan, decision)

    try:
        store.create_leadership_briefing(project_id, {
            **payload,
            "idempotency_key": "bad-ref",
            "source_asset_refs": [{"asset_type": "insight_card", "asset_id": "ic_missing", "required": True}],
        })
    except ResearchProjectStoreError as exc:
        assert "insight references not found" in str(exc)
    else:
        raise AssertionError("expected missing insight failure")

    try:
        store.create_leadership_briefing(project_id, {
            **payload,
            "idempotency_key": "bad-type",
            "source_asset_refs": [{"asset_type": "unknown", "asset_id": card["id"]}],
        })
    except ResearchProjectStoreError as exc:
        assert "asset_type" in str(exc)
    else:
        raise AssertionError("expected unknown asset type failure")

    try:
        store.create_leadership_briefing(project_id, {
            **payload,
            "idempotency_key": "bad-ask",
            "decision_asks": [{"title": "Bad ask", "linked_option_ids": ["so_missing"]}],
        })
    except ResearchProjectStoreError as exc:
        assert "linked_option_ids references not found" in str(exc)
    else:
        raise AssertionError("expected missing linked option failure")


def test_leadership_briefing_readiness_and_blocking_approval(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, card, _, _, option, plan, decision = _seed_p7(store)
    briefing, _ = store.create_leadership_briefing(project_id, _briefing_payload(card, option, plan, decision))

    ready = store.update_leadership_briefing(project_id, briefing["briefing_id"], {
        "status": "in_review",
        "readiness": "ready",
    })
    assert ready["readiness"] == "ready"

    blocked = store.update_leadership_briefing(project_id, briefing["briefing_id"], {
        "review_rounds": [{
            "reviewer": "strategy reviewer",
            "decision": "changes_requested",
            "comment": "Clarify AgentArts vs Harness boundary.",
            "blocking": True,
            "resolved": False,
        }],
    })
    try:
        store.update_leadership_briefing(project_id, briefing["briefing_id"], {
            "status": "approved",
            "readiness": "approved",
        })
    except ResearchProjectStoreError as exc:
        assert "unresolved blocking review" in str(exc)
    else:
        raise AssertionError("expected blocking review approval failure")

    reviews = [{**blocked["review_rounds"][0], "resolved": True}]
    approved = store.update_leadership_briefing(project_id, briefing["briefing_id"], {
        "review_rounds": reviews,
        "status": "approved",
        "readiness": "approved",
    })
    assert approved["status"] == "approved"
    assert approved["readiness_checks"]["has_blocking_review_decisions"] is False


def test_leadership_briefing_does_not_mutate_upstream_assets(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, card, _, _, option, plan, decision = _seed_p7(store)
    before = store.get(project_id).to_dict()
    store.create_leadership_briefing(project_id, _briefing_payload(card, option, plan, decision))
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
    ]:
        assert after[field] == before[field]
