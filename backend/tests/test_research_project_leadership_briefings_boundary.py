from __future__ import annotations

from pathlib import Path

from app.models.research_project import ResearchProjectStore

from test_research_project_leadership_briefings_store import _briefing_payload, _seed_p7


def test_p7_briefing_route_has_no_execution_or_generation_calls():
    route = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "api"
        / "routes"
        / "research_project_briefings.py"
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


def test_p7_briefing_creation_writes_only_briefing_sidecar(tmp_path):
    store = ResearchProjectStore(tmp_path / "research_projects")
    project_id, _, card, _, _, option, plan, decision = _seed_p7(store)
    before_files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    briefing, _ = store.create_leadership_briefing(project_id, _briefing_payload(card, option, plan, decision))

    after_files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())
    new_files = [path for path in after_files if path not in before_files]
    assert new_files == [f"research_projects/{project_id}/leadership_briefings/{briefing['briefing_id']}.json"]
    assert not list(tmp_path.rglob("*.pptx"))
    assert not list(tmp_path.rglob("*.pdf"))
