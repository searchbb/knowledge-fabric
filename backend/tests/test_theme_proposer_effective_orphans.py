"""Tests for effective-orphan counting (v3 OOD fix, part 2).

When a run produces zero member-role attachments, the candidate-role
attachments must count as effective orphans for the new-theme trigger.
This unblocks the orphan_ratio >= 0.6 gate on all-candidate OOD runs.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_proposer import AutoThemeProposer


def _fake_theme(theme_id: str, name: str, status: str = "active") -> dict:
    return {
        "theme_id": theme_id, "name": name, "status": status,
        "description": "", "keywords": [], "concept_memberships": [],
    }


def test_all_candidate_run_with_zero_members_triggers_new_theme():
    """20 concepts all at candidate confidence (0.6-0.7), zero members:
    orphan_ratio should count unmembered candidates as effective orphans,
    pushing the ratio over 0.6 and triggering _propose_new_theme_candidate."""
    proposer = AutoThemeProposer()

    concepts_payload = [
        {"entry_id": f"e{i}", "canonical_name": f"name-{i}",
         "concept_type": "Problem" if i % 2 else "Solution"}
        for i in range(20)
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]}
        for c in concepts_payload
    ]

    existing_theme = _fake_theme("t_existing", "Existing")
    llm_assignments = [
        {"entry_id": f"e{i}", "attach_to_theme_id": "t_existing",
         "confidence": 0.65, "reason": "weak match"}
        for i in range(20)
    ]

    propose_calls: list = []
    def _capture_propose(orphans, concepts, run_id, article_title):
        propose_calls.append({"orphan_count": len(orphans)})
        return {"theme_id": "t_new", "name": "New", "attached_count": len(orphans)}

    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None: [existing_theme] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts", return_value=None,
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate", side_effect=_capture_propose,
    ):
        result = proposer.process(
            project_id="proj_test",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r_test",
            article_title="OOD article",
        )

    # Audit must show the new fields
    assert result.audit["member_count"] == 0
    assert result.audit["candidate_count"] == 20
    assert result.audit["effective_orphan_count"] == 20
    # And the new-theme path was reached
    assert propose_calls, "new-theme candidate should have been proposed"
    assert result.action == "classified_with_new_candidate"


def test_mixed_run_with_some_members_uses_real_orphan_count():
    """If at least one member-role attachment lands, the old behavior holds:
    orphan_ratio = real_orphans / total, candidates do NOT count as orphans."""
    proposer = AutoThemeProposer()

    concepts_payload = [
        {"entry_id": f"e{i}", "canonical_name": f"n-{i}", "concept_type": "Problem"}
        for i in range(10)
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]}
        for c in concepts_payload
    ]

    existing_theme = _fake_theme("t_existing", "Existing")
    # 3 members (>=0.78), 5 candidates (0.6), 2 real orphans (null)
    llm_assignments = (
        [{"entry_id": f"e{i}", "attach_to_theme_id": "t_existing",
          "confidence": 0.85, "reason": "strong"} for i in range(3)]
        + [{"entry_id": f"e{i}", "attach_to_theme_id": "t_existing",
            "confidence": 0.6, "reason": "weak"} for i in range(3, 8)]
        + [{"entry_id": f"e{i}", "attach_to_theme_id": None,
            "confidence": 0.2, "reason": "no fit"} for i in range(8, 10)]
    )

    propose_calls: list = []
    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None: [existing_theme] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts", return_value=None,
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate",
        side_effect=lambda *a, **kw: propose_calls.append(1) or None,
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
        )

    # 3 members → member_count>0 → candidates stay classified, ratio = 2/10 = 0.2
    assert result.audit["member_count"] == 3
    assert result.audit["effective_orphan_count"] == 2
    assert not propose_calls, "new-theme should NOT be triggered when members exist"
    assert result.action == "classified"


def test_all_candidate_run_below_core_orphan_threshold_does_not_trigger():
    """member_count == 0 and effective orphans all candidates, but fewer
    than min_core_orphans_for_new_theme (default 3) core-type concepts:
    gate must NOT fire. Guards against tiny-article false positives."""
    proposer = AutoThemeProposer()  # min_core_orphans_for_new_theme = 3

    # Only 2 core concepts, both attached as candidates. Effective orphans = 2.
    # orphan_ratio = 2/2 = 1.0 (passes ratio gate), but core_orphan_count = 2 (< 3)
    concepts_payload = [
        {"entry_id": "e0", "canonical_name": "c0", "concept_type": "Problem"},
        {"entry_id": "e1", "canonical_name": "c1", "concept_type": "Solution"},
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]} for c in concepts_payload
    ]
    existing_theme = _fake_theme("t_existing", "Existing")
    llm_assignments = [
        {"entry_id": "e0", "attach_to_theme_id": "t_existing",
         "confidence": 0.65, "reason": "weak"},
        {"entry_id": "e1", "attach_to_theme_id": "t_existing",
         "confidence": 0.7, "reason": "weak"},
    ]

    propose_calls: list = []
    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None: [existing_theme] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts", return_value=None,
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate",
        side_effect=lambda *a, **kw: propose_calls.append(1) or None,
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
        )

    assert result.audit["member_count"] == 0
    assert result.audit["effective_orphan_count"] == 2
    assert result.audit["core_orphan_count"] == 2
    # Ratio gate passes (1.0 >= 0.6), core gate fails (2 < 3), so no new theme
    assert not propose_calls, "core_orphan_count < 3 must block new-theme"
    assert result.action == "classified"


def test_empty_llm_assignments_produces_classified_with_zero_counts():
    """LLM returns {'assignments': []}: degenerate case, no attaches, no
    orphans, no new-theme proposal. Audit must still be populated with zeros
    (not KeyError). The max(len(assignments_raw), 1) guard must prevent
    zero-division in orphan_ratio."""
    proposer = AutoThemeProposer()

    concepts_payload = [
        {"entry_id": "e0", "canonical_name": "c0", "concept_type": "Problem"},
        {"entry_id": "e1", "canonical_name": "c1", "concept_type": "Solution"},
        {"entry_id": "e2", "canonical_name": "c2", "concept_type": "Topic"},
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]} for c in concepts_payload
    ]
    existing_theme = _fake_theme("t_existing", "Existing")

    propose_calls: list = []
    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None: [existing_theme] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": []},  # empty
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts", return_value=None,
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate",
        side_effect=lambda *a, **kw: propose_calls.append(1) or None,
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
        )

    # Graceful degradation: all zero counts, no crashes
    assert result.audit["member_count"] == 0
    assert result.audit["candidate_count"] == 0
    assert result.audit["effective_orphan_count"] == 0
    assert result.audit["orphan_ratio"] == 0.0
    assert result.audit["core_orphan_count"] == 0
    assert not propose_calls
    assert result.action == "classified"
