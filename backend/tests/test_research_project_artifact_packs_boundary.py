from __future__ import annotations

from pathlib import Path


def test_p5_artifact_pack_route_has_no_execution_or_generation_calls():
    route = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "api"
        / "routes"
        / "research_project_artifact_packs.py"
    )
    text = route.read_text(encoding="utf-8").lower()
    forbidden = [
        "openai",
        "dashscope",
        "bailian",
        "scheduler",
        "worker",
        "queue",
        "cron",
        "threading",
        "asyncio.create_task",
        "subprocess",
        "pptx",
        "drawio_generate",
    ]
    for token in forbidden:
        assert token not in text
