from __future__ import annotations

from pathlib import Path

from app.models.research_project import ResearchProjectStore
from app.services.research_traceability_map import build_traceability_map

from test_research_project_traceability_map_service import _seed_full_chain


def test_p10_review_history_route_has_no_execution_or_generation_calls():
    route = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "api"
        / "routes"
        / "research_project_review_history.py"
    )
    text = route.read_text(encoding="utf-8").lower()
    forbidden = [
        "openai",
        "dashscope",
        "bailian",
        "deep_research",
        "scheduler",
        "worker",
        "queue",
        "threading",
        "asyncio.create_task",
        "subprocess",
        "pptx",
        "drawio",
    ]
    for token in forbidden:
        assert token not in text


def test_p10_traceability_read_writes_no_review_history(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    build_traceability_map(project_id, store=store)

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    assert after == before
    assert not list((tmp_path / "research_projects" / project_id).glob("review_history/*.json"))


def test_p10_manual_note_writes_only_history_sidecar(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    review, _ = store.create_governance_review(project_id, {
        "idempotency_key": "p10-boundary-review",
        "title": "P10 review history source review",
        "seed_from_traceability_map": True,
    })
    before_files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    before_review = store.get_governance_review(project_id, review["review_id"])

    note = store.create_review_history_note(project_id, {
        "asset_type": "governance_review",
        "asset_id": review["review_id"],
        "note": "Manual note only.",
    })

    after_files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    new_files = [path for path in after_files if path not in before_files]
    assert new_files == [f"research_projects/{project_id}/review_history/{note['history_entry_id']}.json"]
    assert store.get_governance_review(project_id, review["review_id"]) == before_review
