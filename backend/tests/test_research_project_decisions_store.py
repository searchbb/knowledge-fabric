from __future__ import annotations

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError


def _seed_p6(store: ResearchProjectStore):
    project = store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "evidence_items": [
            {
                "evidence_id": "ev_local_harness",
                "title": "企业级 Harness",
                "status": "accepted",
                "origin": "local_evidence_pack",
                "scope": "C1_local",
            },
            {
                "evidence_id": "ei_external_governance",
                "title": "Agent governance",
                "status": "accepted",
                "origin": "external_research_pack",
                "scope": "C2_external",
            },
        ],
    })
    row, _ = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "p6-row",
        "question": "控制点在哪里？",
        "claim": "Agent Harness 是企业级 Agent-ready 软件栈的关键控制点。",
        "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "confidence": "high",
    })
    card, _ = store.create_insight_card(project.id, {
        "idempotency_key": "p6-card",
        "title": "执行治理面是长期控制点",
        "claim": "控制点不在模型能力本身，而在企业执行治理面。",
        "implication": "AgentArts 应升级为企业 Agent 工程化平台。",
        "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "matrix_row_ids": [row["id"]],
        "confidence": "high",
    })
    draft, _ = store.create_artifact_draft(project.id, {
        "idempotency_key": "p6-draft",
        "artifact_type": "slide_outline",
        "title": "5 页战略材料大纲",
        "purpose": "形成领导汇报材料输入。",
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_local_harness"],
    })
    pack, _ = store.create_artifact_pack(project.id, {
        "idempotency_key": "p6-pack",
        "title": "华为云 Agent-ready 战略材料包",
        "purpose": "面向领导汇报战略判断。",
        "source_artifact_draft_ids": [draft["id"]],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_local_harness", "ei_external_governance"],
    })
    return project.id, row, card, draft, pack


def test_decision_assets_are_sidecar_indexed_and_persistent(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, row, card, draft, pack = _seed_p6(store)

    option, replay = store.create_strategic_option(project_id, {
        "idempotency_key": "p6-option",
        "title": "L2 Agent-ready 适配层 + L4 企业级 Harness 作为战略控制点",
        "summary": "用适配层和 Harness 承接企业执行治理。",
        "source_insight_ids": [card["id"]],
        "source_evidence_matrix_row_ids": [row["id"]],
        "source_evidence_ids": ["ev_local_harness"],
        "source_artifact_draft_ids": [draft["id"]],
        "source_artifact_pack_ids": [pack["pack_id"]],
        "risks": [{"statement": "首客深交付可能难以复用。", "severity": "high"}],
        "success_metrics": [{"name": "harness_reuse_ratio", "target": ">= 60%"}],
    })
    assert replay is False
    assert option["option_id"].startswith("so_")

    plan, _ = store.create_validation_plan(project_id, {
        "idempotency_key": "p6-plan",
        "title": "90-day ERP/Test Harness pilot validation",
        "linked_option_ids": [option["option_id"]],
        "validation_questions": [{"question": "客户是否愿意接入真实权限和审批？"}],
        "validation_methods": [{"method_type": "customer_pilot", "description": "ERP 试点", "execution_location": "external"}],
        "metrics": [{"name": "connected_systems", "target": ">= 3"}],
    })
    assert plan["plan_id"].startswith("vp_")

    decision, _ = store.create_leadership_decision_record(project_id, {
        "idempotency_key": "p6-decision",
        "title": "Decision: prioritize Agent Harness as enterprise control layer",
        "linked_option_ids": [option["option_id"]],
        "linked_validation_plan_ids": [plan["plan_id"]],
        "chosen_option_id": option["option_id"],
        "rationale": [{
            "statement": "L2 + L4 比模型层更贴近企业落地控制点。",
            "source_insight_ids": [card["id"]],
            "source_evidence_ids": ["ev_local_harness"],
        }],
    })
    assert decision["decision_id"].startswith("ldr_")

    root = tmp_path / "research_projects" / project_id
    assert (root / "strategic_options" / f"{option['option_id']}.json").exists()
    assert (root / "validation_plans" / f"{plan['plan_id']}.json").exists()
    assert (root / "leadership_decision_records" / f"{decision['decision_id']}.json").exists()

    reloaded = ResearchProjectStore(tmp_path / "research_projects").get(project_id)
    assert reloaded.strategic_options[0]["option_id"] == option["option_id"]
    assert reloaded.validation_plans[0]["plan_id"] == plan["plan_id"]
    assert reloaded.leadership_decision_records[0]["decision_id"] == decision["decision_id"]


def test_decision_assets_validate_references_and_runtime_boundary(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, _, _, _ = _seed_p6(store)

    try:
        store.create_strategic_option(project_id, {
            "idempotency_key": "bad-option",
            "title": "Bad",
            "source_insight_ids": ["ic_missing"],
        })
    except ResearchProjectStoreError as exc:
        assert "insight references not found" in str(exc)
    else:
        raise AssertionError("expected missing insight failure")

    try:
        store.create_validation_plan(project_id, {
            "idempotency_key": "bad-plan",
            "title": "Bad",
            "linked_option_ids": ["so_missing"],
        })
    except ResearchProjectStoreError as exc:
        assert "linked_option_ids references not found" in str(exc)
    else:
        raise AssertionError("expected missing option failure")

    try:
        store.create_validation_plan(project_id, {
            "idempotency_key": "bad-runtime",
            "title": "Bad",
            "model_provider": "gpt",
        })
    except ResearchProjectStoreError as exc:
        assert "runtime execution fields" in str(exc)
    else:
        raise AssertionError("expected runtime boundary failure")


def test_decision_status_transitions_require_traceability_and_resolved_review(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, card, _, _ = _seed_p6(store)
    option, _ = store.create_strategic_option(project_id, {
        "idempotency_key": "traceable-option",
        "title": "Traceable Option",
        "source_insight_ids": [card["id"]],
    })
    draft_option, _ = store.create_strategic_option(project_id, {
        "idempotency_key": "untraceable-option",
        "title": "No refs yet",
    })

    try:
        store.update_strategic_option(project_id, draft_option["option_id"], {"status": "validated"})
    except ResearchProjectStoreError as exc:
        assert "require traceability" in str(exc)
    else:
        raise AssertionError("expected traceability failure")

    plan, _ = store.create_validation_plan(project_id, {
        "idempotency_key": "incomplete-plan",
        "title": "Incomplete",
        "linked_option_ids": [option["option_id"]],
    })
    try:
        store.update_validation_plan(project_id, plan["plan_id"], {"status": "approved", "approval_state": "approved"})
    except ResearchProjectStoreError as exc:
        assert "validation_questions" in str(exc)
    else:
        raise AssertionError("expected incomplete plan approval failure")

    plan = store.update_validation_plan(project_id, plan["plan_id"], {
        "validation_questions": [{"question": "是否愿意接入真实权限？"}],
        "validation_methods": [{"method_type": "customer_pilot", "execution_location": "external"}],
        "metrics": [{"name": "connected_systems", "target": ">= 3"}],
        "status": "approved",
        "approval_state": "approved",
    })
    assert plan["status"] == "approved"

    decision, _ = store.create_leadership_decision_record(project_id, {
        "idempotency_key": "blocked-decision",
        "title": "Blocked decision",
        "linked_option_ids": [option["option_id"]],
        "linked_validation_plan_ids": [plan["plan_id"]],
        "chosen_option_id": option["option_id"],
        "rationale": [{"statement": "执行治理面是控制点。"}],
        "review_rounds": [{
            "reviewer": "VP-level reviewer",
            "decision": "needs_revision",
            "blocking": True,
            "resolved": False,
        }],
    })
    try:
        store.update_leadership_decision_record(project_id, decision["decision_id"], {"decision_status": "approved"})
    except ResearchProjectStoreError as exc:
        assert "unresolved blocking review" in str(exc)
    else:
        raise AssertionError("expected blocking review failure")

    review_rounds = [{**decision["review_rounds"][0], "resolved": True}]
    approved = store.update_leadership_decision_record(project_id, decision["decision_id"], {
        "review_rounds": review_rounds,
        "decision_status": "approved",
    })
    assert approved["decision_status"] == "approved"
