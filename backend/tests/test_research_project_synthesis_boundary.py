from __future__ import annotations

from pathlib import Path


def test_p4_synthesis_layer_has_no_execution_or_model_runtime_calls():
    root = Path(__file__).resolve().parents[1] / "app"
    files = [root / "api" / "routes" / "research_project_synthesis.py"]
    forbidden = [
        "openai",
        "dashscope",
        "百炼",
        "deep_research",
        "subprocess",
        "threading",
        "scheduler",
        "worker",
        "ask_gpt",
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)

    for token in forbidden:
        assert token not in text
