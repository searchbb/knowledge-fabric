from __future__ import annotations

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError


def _project(store: ResearchProjectStore):
    return store.create({
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
            {
                "evidence_id": "ev_pending",
                "title": "待评审证据",
                "status": "candidate",
            },
        ],
    })


def test_synthesis_assets_are_sidecar_indexed_and_persistent(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)

    row, replay = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "p4-row-001",
        "question": "华为云应控制企业软件栈哪一层？",
        "claim": "控制点在执行控制面。",
        "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "confidence": "high",
    })
    assert replay is False
    assert row["id"].startswith("emr_")
    assert row["schema_version"] == 1
    assert row["status"] == "draft"

    card, _ = store.create_insight_card(project.id, {
        "idempotency_key": "p4-card-001",
        "title": "执行控制面是长期控制点",
        "claim": "企业 Agent 竞争的长期控制点在执行控制面。",
        "implication": "AgentArts 应向企业级工程化平台升级。",
        "supporting_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "matrix_row_ids": [row["id"]],
        "confidence": "high",
    })
    assert card["id"].startswith("ic_")

    draft, _ = store.create_artifact_draft(project.id, {
        "idempotency_key": "p4-draft-001",
        "artifact_type": "slide_outline",
        "title": "5 页战略材料大纲",
        "purpose": "向领导汇报华为云 Agent-ready 战略判断。",
        "audience": "华为云战略部二层领导",
        "source_insight_ids": [card["id"]],
        "source_evidence_ids": ["ev_local_harness", "ei_external_governance"],
        "outline": [{
            "section_id": "s1",
            "title": "战略判断",
            "key_message": "长期控制点上移到执行控制面。",
            "source_insight_ids": [card["id"]],
        }],
    })
    assert draft["id"].startswith("ad_")
    assert (tmp_path / "research_projects" / project.id / "evidence_matrix_rows" / f"{row['id']}.json").exists()
    assert (tmp_path / "research_projects" / project.id / "insight_cards" / f"{card['id']}.json").exists()
    assert (tmp_path / "research_projects" / project.id / "artifact_drafts" / f"{draft['id']}.json").exists()

    reloaded = ResearchProjectStore(tmp_path / "research_projects").get(project.id)
    assert reloaded.evidence_matrix_rows[0]["id"] == row["id"]
    assert reloaded.insight_cards[0]["id"] == card["id"]
    assert reloaded.artifact_drafts[0]["id"] == draft["id"]


def test_synthesis_idempotency_replay_and_conflict(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)
    payload = {
        "idempotency_key": "p4-row-001",
        "question": "战略窗口是什么？",
        "claim": "治理外壳成为窗口。",
        "supporting_evidence_ids": ["ev_local_harness"],
    }

    first, replay = store.create_evidence_matrix_row(project.id, payload)
    second, replay = store.create_evidence_matrix_row(project.id, payload)
    assert replay is True
    assert first["id"] == second["id"]
    assert len(store.list_evidence_matrix_rows(project.id)) == 1

    try:
        store.create_evidence_matrix_row(project.id, {**payload, "claim": "Changed"})
    except ResearchProjectStoreError as exc:
        assert "idempotency key conflict" in str(exc)
    else:
        raise AssertionError("expected idempotency conflict")


def test_synthesis_rejects_unaccepted_or_missing_evidence_refs(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)

    for evidence_id in ["ev_pending", "ev_missing"]:
        try:
            store.create_evidence_matrix_row(project.id, {
                "idempotency_key": f"bad-{evidence_id}",
                "question": "能否进材料？",
                "claim": "不能直接引用。",
                "supporting_evidence_ids": [evidence_id],
            })
        except ResearchProjectStoreError as exc:
            assert "evidence references not accepted in project" in str(exc)
        else:
            raise AssertionError("expected evidence reference failure")


def test_synthesis_patch_preserves_evidence_provenance(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)
    before = list(project.evidence_items)
    row, _ = store.create_evidence_matrix_row(project.id, {
        "idempotency_key": "p4-row-001",
        "question": "控制点在哪里？",
        "claim": "控制点在执行控制面。",
        "supporting_evidence_ids": ["ev_local_harness"],
    })

    patched = store.update_evidence_matrix_row(project.id, row["id"], {
        "status": "reviewed",
        "material_readiness": "usable",
        "updated_by": "human_reviewer",
    })
    assert patched["status"] == "reviewed"
    assert patched["material_readiness"] == "usable"
    assert store.get(project.id).evidence_items == before
