from __future__ import annotations

from pathlib import Path


def test_p6_decision_route_has_no_execution_or_generation_calls():
    route = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "api"
        / "routes"
        / "research_project_decisions.py"
    )
    text = route.read_text(encoding="utf-8").lower()
    forbidden = [
        "openai",
        "dashscope",
        "bailian",
        "scheduler",
        "threading",
        "asyncio.create_task",
        "subprocess",
        "drawio_generate",
    ]
    for token in forbidden:
        assert token not in text
