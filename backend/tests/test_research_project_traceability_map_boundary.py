from __future__ import annotations

from pathlib import Path


def test_traceability_map_runtime_boundary():
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "app" / "services" / "research_traceability_map.py",
        root / "app" / "api" / "routes" / "research_project_traceability.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in targets)
    forbidden = [
        "open" + "ai",
        "bai" + "lian",
        "deep" + "_research",
        "gpt",
        "llm",
        "schedule" + "r",
        "work" + "er",
        "queue",
        "dag",
        "ppt",
        "draw" + ".io",
        "sub" + "process",
    ]
    assert [token for token in forbidden if token in text] == []
