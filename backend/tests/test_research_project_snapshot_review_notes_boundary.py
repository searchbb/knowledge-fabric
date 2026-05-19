from __future__ import annotations

from pathlib import Path


def test_snapshot_review_note_route_keeps_manual_annotation_boundary():
    route_text = Path("app/api/routes/research_project_snapshot_review_notes.py").read_text(encoding="utf-8")

    forbidden = [
        "deep_research",
        "bailian",
        "scheduler",
        " queue",
        "worker",
        "dag",
        "auto_fix",
        "rollback",
        "restore",
        "export",
        "generate",
        "approve",
        "reject",
        "repair",
    ]
    lowered = route_text.lower()

    for token in forbidden:
        assert token not in lowered
