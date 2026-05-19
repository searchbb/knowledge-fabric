from __future__ import annotations

from app.models.research_project import ResearchProjectStore, ResearchProjectStoreError


def _project(store: ResearchProjectStore):
    return store.create({
        "title": "华为云 Agent-ready 企业软件栈战略研究",
        "background": "验证 P3 Codex writeback。",
    })


def _pack_payload():
    return {
        "idempotency_key": "p3-huawei-agent-ready-pack",
        "title": "Huawei Cloud Agent-ready external evidence pack",
        "source_type": "deep_research",
        "scope": "C2_external",
        "producer": {
            "kind": "codex_skill",
            "name": "deep_research_skill",
            "version": "0.1.0",
            "model": "GPT Pro",
        },
        "topic": "华为云 Agent-ready 企业软件栈战略研究",
        "summary": "外部研究围绕治理、执行控制和行业资产。",
        "source_refs": [{
            "source_id": "src_001",
            "type": "url",
            "title": "Agent governance source",
            "url": "https://example.com/agent-governance",
        }],
        "evidence_candidates": [{
            "external_id": "agent_harness_control_001",
            "claim": "企业级 Agent 的核心控制点在执行治理外壳。",
            "evidence_text": "企业 Agent 需要身份、权限、审批、日志、监控和补救机制。",
            "source_refs": ["src_001"],
            "confidence": 0.86,
            "tags": ["Harness", "Agent-ready", "治理"],
        }],
    }


def test_research_run_and_consultation_log_are_sidecar_indexed(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)

    run, replay = store.create_research_run(project.id, {
        "idempotency_key": "run-001",
        "stage": "P3",
        "phase": "writeback_contract_test",
        "title": "P3 writeback dry run",
        "status": "completed",
        "summary": "Validated dry-run payload.",
    })
    assert replay is False
    assert run["run_id"].startswith("rr_")
    assert (tmp_path / "research_projects" / project.id / "research_runs" / f"{run['run_id']}.json").exists()

    log, replay = store.create_consultation_log(project.id, {
        "idempotency_key": "consult-001",
        "kind": "gpt_design_review",
        "stage": "P3",
        "status": "complete",
        "run_id": run["run_id"],
        "answer_summary": "P3 should be a writeback receiver.",
    })
    assert replay is False
    assert log["consultation_id"].startswith("cl_")

    reloaded = ResearchProjectStore(tmp_path / "research_projects").get(project.id)
    assert reloaded.research_runs[0]["run_id"] == run["run_id"]
    assert reloaded.consultation_logs[0]["consultation_id"] == log["consultation_id"]


def test_writeback_idempotency_replay_and_conflict(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)
    payload = {
        "idempotency_key": "run-001",
        "stage": "P3",
        "phase": "writeback",
        "title": "Run",
    }

    first, replay = store.create_research_run(project.id, payload)
    second, replay = store.create_research_run(project.id, payload)
    assert replay is True
    assert first["run_id"] == second["run_id"]
    assert len(store.list_research_runs(project.id)) == 1

    try:
        store.create_research_run(project.id, {**payload, "title": "Changed"})
    except ResearchProjectStoreError as exc:
        assert "idempotency key conflict" in str(exc)
    else:
        raise AssertionError("expected idempotency conflict")


def test_external_pack_accept_syncs_c2_evidence_item(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)
    pack, replay = store.import_external_research_pack(project.id, _pack_payload())
    assert replay is False
    assert pack["pack_id"].startswith("erp_")
    assert pack["scope"] == "C2_external"
    assert pack["evidence_candidates"][0]["candidate_id"].startswith("ec_")

    candidate_id = pack["evidence_candidates"][0]["candidate_id"]
    updated_pack, updated_project = store.update_external_research_candidate_status(
        project.id,
        pack["pack_id"],
        candidate_id,
        review_status="accepted",
        review_note="用于 P3 baseline。",
    )

    assert updated_pack["accepted_candidate_ids"] == [candidate_id]
    assert updated_project.external_research_packs[0]["accepted_count"] == 1
    assert len(updated_project.evidence_items) == 1
    evidence = updated_project.evidence_items[0]
    assert evidence["origin"] == "external_research_pack"
    assert evidence["scope"] == "C2_external"
    assert evidence["source_type"] == "deep_research"
    assert evidence["pack_id"] == pack["pack_id"]
    assert evidence["provenance"]["producer_name"] == "deep_research_skill"


def test_reject_external_candidate_removes_synced_evidence(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project = _project(store)
    pack, _ = store.import_external_research_pack(project.id, _pack_payload())
    candidate_id = pack["evidence_candidates"][0]["candidate_id"]
    store.update_external_research_candidate_status(
        project.id,
        pack["pack_id"],
        candidate_id,
        review_status="accepted",
    )
    _, project_after_reject = store.update_external_research_candidate_status(
        project.id,
        pack["pack_id"],
        candidate_id,
        review_status="rejected",
    )
    assert project_after_reject.evidence_items == []
