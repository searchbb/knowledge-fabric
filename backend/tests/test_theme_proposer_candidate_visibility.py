"""Tests for the candidate-theme visibility fix (P1 M1).

GPT consult d10c98cab0b64a56 (2026-04-16) diagnosed the root cause of the
split-theme regression: `_propose_new_theme_candidate` creates themes with
``status="candidate"``, but `AutoThemeProposer.process()` was only loading
``list_themes(status="active")`` — so every subsequent article saw an empty
theme list and created its own island. Fix: load active + candidate and use
the union as the classifiable working set.

These tests lock the fix so a future refactor can't silently break it again.
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_proposer import (
    AutoThemeProposer,
    PROPOSER_VERSION,
)


def _fake_theme(theme_id: str, name: str, status: str, member_ids: list[str]) -> dict:
    return {
        "theme_id": theme_id,
        "name": name,
        "status": status,
        "description": f"desc for {name}",
        "keywords": [],
        "concept_memberships": [
            {"entry_id": eid, "role": "member", "score": 0.9} for eid in member_ids
        ],
    }


def test_process_loads_both_active_and_candidate_themes():
    """The working set must include candidate themes, not just active ones."""
    proposer = AutoThemeProposer()

    existing_active = _fake_theme("t_active", "Active Theme", "active", ["e_old1"])
    existing_candidate = _fake_theme("t_cand", "Candidate Theme", "candidate", ["e_old2"])

    # new_canonical_ids brings 2 new concepts that should be LLM-classified.
    new_ids = ["e_new1", "e_new2"]

    # Patch registry + themes + LLM so we don't need live storage.
    fake_entries = [
        {"entry_id": eid, "canonical_name": f"name-{eid}", "concept_type": "Topic"}
        for eid in ["e_old1", "e_old2", "e_new1", "e_new2"]
    ]

    def _list_themes(*, status=None):
        if status == "active":
            return [existing_active]
        if status == "candidate":
            return [existing_candidate]
        return [existing_active, existing_candidate]

    with (
        patch(
            "app.services.auto.theme_proposer.themes.list_themes",
            side_effect=_list_themes,
        ),
        patch(
            "app.services.auto.theme_proposer.registry.list_entries",
            return_value=fake_entries,
        ),
        # Stub the LLM: it "sees" both themes and decides to attach both new
        # concepts to the CANDIDATE theme (i.e. the fix lets the proposer
        # actually pick a candidate — the whole point of the bug fix).
        patch.object(
            AutoThemeProposer,
            "_classify_via_llm",
            return_value={
                "assignments": [
                    {"entry_id": "e_new1", "attach_to_theme_id": "t_cand",
                     "confidence": 0.85, "reason": "matches candidate theme"},
                    {"entry_id": "e_new2", "attach_to_theme_id": "t_cand",
                     "confidence": 0.82, "reason": "matches candidate theme"},
                ]
            },
        ),
        # Stub attach_concepts so we don't need a real theme store.
        patch(
            "app.services.auto.theme_proposer.themes.attach_concepts",
            return_value=None,
        ),
    ):
        result = proposer.process(
            project_id="proj_test",
            project_name="Test Project",
            new_canonical_ids=new_ids,
            run_id="r_test",
            article_title="Agent Systems",
        )

    # Audit exposes that the proposer saw both active and candidate pools —
    # this is the critical invariant.
    assert result.audit["visible_active_theme_count"] == 1
    assert result.audit["visible_candidate_theme_count"] == 1
    assert "t_cand" in result.audit["classifiable_theme_ids"]
    assert "t_active" in result.audit["classifiable_theme_ids"]
    assert result.audit["proposer_version"] == PROPOSER_VERSION
    assert result.audit["classification_source"] == "llm"

    # Both new concepts attached to the candidate theme — proves the proposer
    # was allowed to pick a candidate.
    assigned_themes = {a["theme_id"] for a in result.assignments}
    assert assigned_themes == {"t_cand"}


def test_process_records_skip_reason_when_too_few_concepts():
    """Early-exit path (below min_concepts_for_action) still emits audit."""
    proposer = AutoThemeProposer(min_concepts_for_action=3)
    result = proposer.process(
        project_id="p",
        new_canonical_ids=["only_one"],
    )
    assert result.action == "noop"
    assert result.audit["skip_reason"] == "below_min_concepts"
    assert result.audit["proposer_version"] == PROPOSER_VERSION
    assert result.audit["threshold_snapshot"]["member_threshold"] == 0.78


def test_process_cold_start_when_no_themes_exist_at_all():
    """If registry truly has no active AND no candidate themes, fall through
    to cold-start path. Audit must still populate correctly."""
    proposer = AutoThemeProposer()
    new_ids = ["e1", "e2", "e3", "e4", "e5"]
    fake_entries = [
        {"entry_id": eid, "canonical_name": f"name-{eid}", "concept_type": "Problem"}
        for eid in new_ids
    ]

    with (
        patch(
            "app.services.auto.theme_proposer.themes.list_themes",
            return_value=[],
        ),
        patch(
            "app.services.auto.theme_proposer.registry.list_entries",
            return_value=fake_entries,
        ),
        # _handle_no_themes will call _propose_new_theme_candidate → LLM →
        # create_theme. Stub the whole inner path with a minimal fake result.
        patch.object(
            AutoThemeProposer,
            "_propose_new_theme_candidate",
            return_value={
                "theme_id": "t_new",
                "name": "New Candidate",
                "attached_count": 5,
            },
        ),
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=new_ids,
        )

    assert result.audit["visible_active_theme_count"] == 0
    assert result.audit["visible_candidate_theme_count"] == 0
    assert result.audit["decision"] == "create_theme_cold_start"
