from __future__ import annotations

from pathlib import Path

from app.models.research_project import ResearchProjectStore

from test_research_project_traceability_map_service import _seed_full_chain


def test_p9_governance_route_has_no_execution_or_generation_calls():
    route = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "api"
        / "routes"
        / "research_project_governance.py"
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
    ]
    for token in forbidden:
        assert token not in text


def test_p9_governance_creation_writes_only_review_sidecar(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _ = _seed_full_chain(store)
    before_files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    review, _ = store.create_governance_review(project_id, {
        "idempotency_key": "p9-boundary-review",
        "title": "P9 strategic research governance review",
        "seed_from_traceability_map": True,
    })

    after_files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    new_files = [path for path in after_files if path not in before_files]
    assert new_files == [f"research_projects/{project_id}/governance_reviews/{review['review_id']}.json"]
    assert not list(tmp_path.rglob("*.pptx"))
    assert not list(tmp_path.rglob("*.drawio"))
    assert not list(tmp_path.rglob("*.pdf"))
