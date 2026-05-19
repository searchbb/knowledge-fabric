from __future__ import annotations

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError


def _seed_p4(store: ResearchProjectStore):
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
            {"evidence_id": "ev_pending", "title": "Pending", "status": "candidate"},
        ],
    })
    row, _ = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "p5-row",
        "question": "控制点在哪里？",
        "claim": "控制点在执行控制面。",
        "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
    })
    card, _ = store.create_insight_card(project.id, {
        "idempotency_key": "p5-card",
        "title": "执行控制面是长期控制点",
        "claim": "长期控制点在执行控制面。",
        "implication": "AgentArts 应升级为工程化平台。",
        "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "matrix_row_ids": [row["id"]],
    })
    draft, _ = store.create_artifact_draft(project.id, {
        "idempotency_key": "p5-draft",
        "artifact_type": "slide_outline",
        "title": "5 页战略材料大纲",
        "purpose": "形成领导汇报材料输入。",
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_local_harness"],
    })
    return project.id, row, card, draft


def test_artifact_pack_sidecar_flow(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, row, card, draft = _seed_p4(store)

    pack, replay = store.create_artifact_pack(project_id, {
        "idempotency_key": "p5-pack",
        "title": "华为云 Agent-ready 企业软件栈战略汇报材料包",
        "purpose": "面向领导汇报战略判断。",
        "audience": "华为云战略部二层领导",
        "source_artifact_draft_ids": [draft["id"]],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "readiness": "outline_ready",
    })
    assert replay is False
    assert pack["pack_id"].startswith("ap_")

    pack = store.add_artifact_pack_item(project_id, pack["pack_id"], {
        "artifact_draft_id": draft["id"],
        "artifact_type": "slide_outline",
        "title": "主汇报材料",
        "role_in_pack": "main_deck",
    })
    assert pack["items"][0]["item_id"].startswith("api_")

    pack = store.add_artifact_pack_page(project_id, pack["pack_id"], {
        "page_title": "Harness 是企业执行控制面",
        "page_type": "framework",
        "page_claim": "权限、审批、日志、评测和回写构成企业控制面。",
        "source_artifact_draft_id": draft["id"],
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "source_matrix_row_ids": [row["id"]],
        "key_messages": ["控制点上移", "资产可复用"],
    })
    page_id = pack["pages"][0]["page_id"]

    pack = store.add_artifact_pack_file_ref(project_id, pack["pack_id"], {
        "file_kind": "drawio",
        "title": "五层架构图 v0.1",
        "relative_path": "artifact_files/agent_ready_stack_v0_1.drawio",
        "linked_page_ids": [page_id],
        "linked_artifact_draft_ids": [draft["id"]],
    })
    assert pack["file_refs"][0]["file_ref_id"].startswith("fr_")

    pack = store.add_artifact_pack_review_round(project_id, pack["pack_id"], {
        "round_name": "P5 internal review round 1",
        "reviewer": "human",
        "decisions": [{
            "target_type": "page",
            "target_id": page_id,
            "decision": "needs_revision",
            "severity": "major",
            "comment": "控制点与 L2/L4 层级需要更明确对齐。",
        }],
    })
    assert pack["review_rounds"][0]["review_round_id"].startswith("rv_")
    assert pack["pages"][0]["review_status"] == "needs_revision"

    reloaded = ResearchProjectStore(tmp_path / "research_projects")
    project = reloaded.get(project_id)
    assert project.artifact_packs[0]["pack_id"] == pack["pack_id"]
    assert project.artifact_packs[0]["page_count"] == 1
    assert (tmp_path / "research_projects" / project_id / "artifact_packs" / f"{pack['pack_id']}.json").exists()


def test_artifact_pack_idempotency_and_reference_validation(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, _, draft = _seed_p4(store)
    payload = {
        "idempotency_key": "p5-pack",
        "title": "Pack",
        "purpose": "Purpose",
        "source_artifact_draft_ids": [draft["id"]],
    }
    first, replay = store.create_artifact_pack(project_id, payload)
    second, replay = store.create_artifact_pack(project_id, payload)
    assert replay is True
    assert first["pack_id"] == second["pack_id"]

    try:
        store.create_artifact_pack(project_id, {**payload, "title": "Changed"})
    except ResearchProjectStoreError as exc:
        assert "idempotency key conflict" in str(exc)
    else:
        raise AssertionError("expected idempotency conflict")

    try:
        store.create_artifact_pack(project_id, {
            "idempotency_key": "bad-evidence",
            "title": "Bad",
            "purpose": "Bad",
            "source_evidence_ids": ["ev_pending"],
        })
    except ResearchProjectStoreError as exc:
        assert "evidence references not accepted" in str(exc)
    else:
        raise AssertionError("expected evidence reference failure")


def test_artifact_pack_rejects_unsafe_file_path_and_blocking_approval(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, _, draft = _seed_p4(store)
    pack, _ = store.create_artifact_pack(project_id, {
        "idempotency_key": "p5-pack",
        "title": "Pack",
        "purpose": "Purpose",
        "source_artifact_draft_ids": [draft["id"]],
    })
    page_pack = store.add_artifact_pack_page(project_id, pack["pack_id"], {
        "page_title": "Page",
        "page_claim": "Claim",
    })
    page_id = page_pack["pages"][0]["page_id"]

    try:
        store.add_artifact_pack_file_ref(project_id, pack["pack_id"], {
            "file_kind": "drawio",
            "title": "Unsafe",
            "relative_path": "../secret.drawio",
        })
    except ResearchProjectStoreError as exc:
        assert "relative_path" in str(exc)
    else:
        raise AssertionError("expected unsafe path failure")

    store.add_artifact_pack_review_round(project_id, pack["pack_id"], {
        "round_name": "Blocking review",
        "reviewer": "human",
        "decisions": [{
            "target_type": "page",
            "target_id": page_id,
            "decision": "needs_revision",
            "severity": "blocking",
        }],
    })
    try:
        store.update_artifact_pack(project_id, pack["pack_id"], {"status": "approved"})
    except ResearchProjectStoreError as exc:
        assert "cannot be approved" in str(exc)
    else:
        raise AssertionError("expected blocking review approval failure")
