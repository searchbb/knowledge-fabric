"""Tests for domain-aware core concept types in theme_proposer (bug fix).

Bug: core_types was hardcoded to tech-era {Problem/Solution/Architecture/
Topic/Mechanism}. For methodology projects, Principle/Method/Case/Antipattern
weren't counted as 'core', blocking the new-theme gate even when methodology
articles had rich core-concept extraction.

Reproduced on proj_41e00efbe04b (比较管理学｜恨国是因为性格): 11 concepts
extracted (3 Principle + 2 Problem + 2 Method + 2 Case + 2 Antipattern),
only 2 counted as core → action=noop → no methodology theme created.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_proposer import (
    AutoThemeProposer,
    CORE_CONCEPT_TYPES_BY_DOMAIN,
)


def test_core_types_by_domain_has_tech_and_methodology():
    """The lookup must have both domain keys with non-empty sets."""
    assert "tech" in CORE_CONCEPT_TYPES_BY_DOMAIN
    assert "methodology" in CORE_CONCEPT_TYPES_BY_DOMAIN
    assert CORE_CONCEPT_TYPES_BY_DOMAIN["tech"] == {
        "Problem", "Solution", "Architecture", "Topic", "Mechanism",
    }
    # Methodology core: Topic/Problem/Principle/Method
    # (Step/Antipattern/Case/Signal are supporting types — don't count as core
    # for new-theme gate purposes)
    assert CORE_CONCEPT_TYPES_BY_DOMAIN["methodology"] == {
        "Topic", "Problem", "Principle", "Method",
    }


def test_methodology_project_counts_principle_method_as_core():
    """A methodology project's proposer must treat Principle/Method/Topic/Problem
    as core concept types when counting core_orphans for the new-theme gate."""
    proposer = AutoThemeProposer(project_domain="methodology")
    concepts = [
        {"entry_id": "e0", "canonical_name": "P1", "concept_type": "Principle"},
        {"entry_id": "e1", "canonical_name": "M1", "concept_type": "Method"},
        {"entry_id": "e2", "canonical_name": "T1", "concept_type": "Topic"},
        {"entry_id": "e3", "canonical_name": "Q1", "concept_type": "Problem"},
        {"entry_id": "e4", "canonical_name": "C1", "concept_type": "Case"},
        {"entry_id": "e5", "canonical_name": "A1", "concept_type": "Antipattern"},
        {"entry_id": "e6", "canonical_name": "S1", "concept_type": "Step"},
    ]
    # Principle, Method, Topic, Problem = core (4). Case/Antipattern/Step = non-core (3).
    core_count = sum(
        1 for c in concepts
        if proposer._is_core_concept_type(c["entry_id"], concepts)
    )
    assert core_count == 4


def test_tech_project_still_uses_tech_core_types():
    """Backward compat: tech domain keeps the old 5-type core set."""
    proposer = AutoThemeProposer(project_domain="tech")
    concepts = [
        {"entry_id": "e0", "canonical_name": "x", "concept_type": "Problem"},
        {"entry_id": "e1", "canonical_name": "x", "concept_type": "Solution"},
        {"entry_id": "e2", "canonical_name": "x", "concept_type": "Architecture"},
        {"entry_id": "e3", "canonical_name": "x", "concept_type": "Topic"},
        {"entry_id": "e4", "canonical_name": "x", "concept_type": "Mechanism"},
        {"entry_id": "e5", "canonical_name": "x", "concept_type": "Principle"},  # non-core for tech
        {"entry_id": "e6", "canonical_name": "x", "concept_type": "Case"},  # non-core for tech
    ]
    core_count = sum(
        1 for c in concepts
        if proposer._is_core_concept_type(c["entry_id"], concepts)
    )
    assert core_count == 5  # tech's 5 types


def test_methodology_cold_start_with_principle_method_triggers_new_theme():
    """Regression for proj_41e00efbe04b scenario: 3 Principle + 2 Method + 2 Problem
    concepts in a methodology project with no existing methodology themes.
    Must trigger the cold-start new-theme path (was action=noop before fix)."""
    from app.services.registry import global_concept_registry as cr

    concepts_payload = [
        {"entry_id": f"p{i}", "canonical_name": f"Principle {i}", "concept_type": "Principle"}
        for i in range(3)
    ] + [
        {"entry_id": f"m{i}", "canonical_name": f"Method {i}", "concept_type": "Method"}
        for i in range(2)
    ] + [
        {"entry_id": f"q{i}", "canonical_name": f"Problem {i}", "concept_type": "Problem"}
        for i in range(2)
    ]

    proposer = AutoThemeProposer(project_domain="methodology")

    propose_calls: list = []
    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        return_value=[],  # cold start: no existing themes
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=concepts_payload,
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate",
        side_effect=lambda *a, **kw: propose_calls.append(1) or {
            "theme_id": "t_new",
            "name": "Methodology Theme",
            "attached_count": 7,
        },
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
        )

    assert propose_calls, f"should have proposed new theme; action={result.action}, reason={result.reason}"
    assert result.action == "classified_with_new_candidate"
