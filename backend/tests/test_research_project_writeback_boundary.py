from __future__ import annotations

from pathlib import Path


def test_p3_writeback_modules_do_not_introduce_execution_runtime():
    root = Path(__file__).resolve().parents[1] / "app"
    paths = [
        root / "api" / "routes" / "research_project_writeback.py",
        root / "models" / "research_project.py",
    ]
    forbidden = [
        "openai",
        "dashscope",
        "apscheduler",
        "celery",
        "subprocess",
        "threading.Thread",
        "cron",
        "model_router",
        "llm_client",
        "auto_execute",
        "dag_nodes",
        "dag_edges",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    for token in forbidden:
        assert token.lower() not in combined
