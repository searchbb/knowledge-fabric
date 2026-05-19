from __future__ import annotations

from app.models.research_project import ResearchProjectStore
from app.services.research_traceability_map import build_traceability_map


def _seed_full_chain(store: ResearchProjectStore):
    project = store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "evidence_items": [
            {"evidence_id": "ev_harness", "title": "企业级 Harness", "status": "accepted", "origin": "local"},
            {"evidence_id": "ei_governance", "title": "Agent governance", "status": "accepted", "origin": "external"},
        ],
    })
    row, _ = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "p8-row",
        "question": "控制点在哪里？",
        "claim": "控制点在企业执行治理面。",
        "supporting_evidence_ids": ["ev_harness", "ei_governance"],
    })
    card, _ = store.create_insight_card(project.id, {
        "idempotency_key": "p8-card",
        "title": "执行治理面是长期控制点",
        "claim": "控制点不在模型能力本身。",
        "implication": "AgentArts 应升级为工程化平台。",
        "supporting_evidence_ids": ["ev_harness"],
        "matrix_row_ids": [row["id"]],
    })
    draft, _ = store.create_artifact_draft(project.id, {
        "idempotency_key": "p8-draft",
        "artifact_type": "slide_outline",
        "title": "战略材料大纲",
        "purpose": "形成领导汇报材料输入。",
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
    })
    pack, _ = store.create_artifact_pack(project.id, {
        "idempotency_key": "p8-pack",
        "title": "战略材料包",
        "purpose": "面向领导汇报。",
        "source_artifact_draft_ids": [draft["id"]],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
        "pages": [{
            "page_id": "pg_manual",
            "page_title": "控制点判断",
            "source_artifact_draft_id": draft["id"],
            "source_insight_ids": [card["id"]],
        }],
    })
    option, _ = store.create_strategic_option(project.id, {
        "idempotency_key": "p8-option",
        "title": "L2 + L4 控制点选项",
        "source_insight_ids": [card["id"]],
        "source_evidence_matrix_row_ids": [row["id"]],
        "source_evidence_ids": ["ev_harness"],
        "source_artifact_draft_ids": [draft["id"]],
        "source_artifact_pack_ids": [pack["pack_id"]],
    })
    plan, _ = store.create_validation_plan(project.id, {
        "idempotency_key": "p8-plan",
        "title": "90-day ERP/Test Harness pilot validation",
        "linked_option_ids": [option["option_id"]],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_harness"],
        "source_artifact_pack_ids": [pack["pack_id"]],
        "validation_questions": [{"question": "客户是否愿意接入真实权限？"}],
    })
    decision, _ = store.create_leadership_decision_record(project.id, {
        "idempotency_key": "p8-decision",
        "title": "Decision on Agent-ready control point",
        "linked_option_ids": [option["option_id"]],
        "linked_validation_plan_ids": [plan["plan_id"]],
        "source_insight_ids": [card["id"]],
        "source_artifact_pack_ids": [pack["pack_id"]],
        "chosen_option_id": option["option_id"],
        "rationale": [{"statement": "L2 + L4 更贴近企业落地。", "source_evidence_ids": ["ev_harness"]}],
    })
    briefing, _ = store.create_leadership_briefing(project.id, {
        "idempotency_key": "p8-briefing",
        "title": "Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout",
        "audience": "cloud_strategy_leadership",
        "purpose": "Prepare leadership readout.",
        "status": "approved",
        "readiness": "approved",
        "executive_summary": {
            "headline": "Agent-ready stack control points are moving to enterprise execution.",
            "key_message": "L2 + L4 are the strategic control layers.",
            "leadership_ask": "Approve the first 90-day validation path.",
            "decision_required": True,
        },
        "source_asset_refs": [
            {"asset_type": "insight_card", "asset_id": card["id"], "required": True},
            {"asset_type": "artifact_pack", "asset_id": pack["pack_id"], "required": True},
        ],
        "sections": [{
            "order": 1,
            "title": "Control-layer thesis",
            "section_type": "recommendation",
            "summary": "L2 + L4 are control points.",
            "source_refs": [{"asset_type": "strategic_option", "asset_id": option["option_id"], "required": True}],
        }],
        "decision_asks": [{
            "title": "Approve pilot path",
            "linked_option_ids": [option["option_id"]],
            "linked_validation_plan_ids": [plan["plan_id"]],
            "linked_decision_record_ids": [decision["decision_id"]],
        }],
    })
    return project.id, {
        "row": row,
        "card": card,
        "draft": draft,
        "pack": pack,
        "option": option,
        "plan": plan,
        "decision": decision,
        "briefing": briefing,
    }


def _snapshot_files(root):
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in root.rglob("*.json")
    }


def test_traceability_map_builds_full_chain_and_summary(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)

    result = build_traceability_map(project_id, store=store)

    node_ids = {node["node_id"] for node in result["nodes"]}
    assert "evidence_item:ev_harness" in node_ids
    assert f"insight_card:{assets['card']['id']}" in node_ids
    assert f"strategic_option:{assets['option']['option_id']}" in node_ids
    assert f"leadership_briefing:{assets['briefing']['briefing_id']}" in node_ids
    assert result["summary"]["node_count"] == 10
    assert result["summary"]["edge_count"] >= 12
    assert result["summary"]["blocking_issue_count"] == 0
    assert result["traceability_readiness"] in {"ready", "needs_review"}

    edge_ids = {edge["edge_id"] for edge in result["edges"]}
    assert f"evidence_item:ev_harness->insight_card:{assets['card']['id']}:supporting_evidence_ids" in edge_ids
    assert f"insight_card:{assets['card']['id']}->strategic_option:{assets['option']['option_id']}:source_insight_ids" in edge_ids
    assert f"strategic_option:{assets['option']['option_id']}->validation_plan:{assets['plan']['plan_id']}:linked_option_ids" in edge_ids
    assert f"leadership_decision_record:{assets['decision']['decision_id']}->leadership_briefing:{assets['briefing']['briefing_id']}:decision_asks[0].linked_decision_record_ids" in edge_ids


def test_traceability_map_detects_missing_refs_and_unsupported_assets(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)
    option = {**assets["option"], "source_insight_ids": ["ic_missing"]}
    store._atomic_write(store._asset_path(project_id, "strategic_options", option["option_id"]), option)
    store._write_index_item(store.get(project_id), "strategic_options", "option_id", store._strategic_option_index(option))

    insight, _ = store.create_insight_card(project_id, {
        "idempotency_key": "unsupported",
        "title": "Unsupported insight",
        "claim": "Unsupported claim",
        "implication": "Needs review",
    })

    result = build_traceability_map(project_id, store=store)
    issues = {(issue["issue_type"], issue["asset_type"], issue["asset_id"]) for issue in result["issues"]}

    assert ("missing_reference", "strategic_option", option["option_id"]) in issues
    assert ("unsupported_insight", "insight_card", insight["id"]) in issues
    assert result["summary"]["missing_reference_count"] == 1
    assert result["traceability_readiness"] == "needs_review"


def test_traceability_map_filters_and_does_not_mutate_files(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, assets = _seed_full_chain(store)
    root = tmp_path / "research_projects"
    before = _snapshot_files(root)

    result = build_traceability_map(project_id, store=store, briefing_id=assets["briefing"]["briefing_id"])
    after = _snapshot_files(root)

    assert before == after
    assert any(node["asset_type"] == "leadership_briefing" for node in result["nodes"])
    assert all(
        assets["briefing"]["briefing_id"] in node["node_id"]
        or any(node["node_id"] in {edge["from_node_id"], edge["to_node_id"]} for edge in result["edges"])
        for node in result["nodes"]
    )

    only_insights = build_traceability_map(project_id, store=store, asset_type="insight_card")
    assert only_insights["nodes"]
    assert {node["asset_type"] for node in only_insights["nodes"]} == {"insight_card"}


def test_traceability_map_empty_project_is_valid_and_deterministic(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = store.create({"title": "Empty traceability project"})

    first = build_traceability_map(project.id, store=store)
    second = build_traceability_map(project.id, store=store)

    first["generated_at"] = "fixed"
    second["generated_at"] = "fixed"
    assert first == second
    assert first["summary"]["node_count"] == 0
    assert first["traceability_readiness"] == "ready"


def test_traceability_map_treats_other_project_asset_as_missing(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    other = store.create({
        "title": "Other",
        "evidence_items": [{"evidence_id": "ev_shared", "title": "Other evidence", "status": "accepted"}],
    })
    project = store.create({"title": "Current"})
    row = {
        "id": "emr_111111111111",
        "idempotency_key": "manual",
        "question": "Cross project?",
        "claim": "Should not resolve",
        "supporting_evidence_ids": ["ev_shared"],
        "created_at": "2026-04-29T00:00:00",
        "updated_at": "2026-04-29T00:00:00",
    }
    store._atomic_write(store._asset_path(project.id, "evidence_matrix_rows", row["id"]), row)
    store._write_index_item(store.get(project.id), "evidence_matrix_rows", "id", row)

    result = build_traceability_map(project.id, store=store)

    assert other.id != project.id
    assert result["summary"]["missing_reference_count"] == 1
    assert result["issues"][0]["missing_ref"] == "ev_shared"
