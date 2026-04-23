"""Regression test for proj_39a354d2c50e (得到精选 article).

Before v3 fix: 20 core-type concepts, LLM returned 16 candidate-tier
attaches (max_conf=0.75) + 4 null/orphans, zero members. orphan_ratio =
4/20 = 0.20 fell below the 0.6 gate → no new theme proposed → all
concepts invisible in the project-theme view.

With v3: either Task 3's article-level OOD gate fires (if max_conf < 0.75
is evaluated strictly), OR Task 2's effective-orphan counting kicks in
(member_count=0 → candidates count as effective orphans → ratio=1.0 →
core_orphans>=3 → new-theme proposed). Either way, this article now
produces a new theme proposal instead of silently being absorbed.

This test locks in that proj_39a354d2c50e produces a new theme,
regardless of which branch (Task 2 or Task 3) claims it.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_proposer import AutoThemeProposer


# Frozen from evolution_log.json entry evt_5d520b84b8 (auto_run_98dcb3ac45).
# 16 LLM assignments + 4 null entries. Confidences are the real LLM outputs.
REAL_LLM_ASSIGNMENTS = [
    {"entry_id": "canon_dec3f01607", "attach_to_theme_id": "gtheme_720b2284ce",
     "confidence": 0.7, "reason": "协作能力是多智能体协作主题的核心机制"},
    {"entry_id": "canon_8fa6bcbc81", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.65, "reason": "听众无法转述..."},
    {"entry_id": "canon_c1ebaf3ae6", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.6, "reason": "..."},
    {"entry_id": "canon_cb4d56a449", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.6, "reason": "..."},
    {"entry_id": "canon_382a982936", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.65, "reason": "..."},
    {"entry_id": "canon_5eaa7d7d04", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.7, "reason": "..."},
    {"entry_id": "canon_0ecdbbe4fb", "attach_to_theme_id": "gtheme_a296c8e189",
     "confidence": 0.75, "reason": "..."},
    {"entry_id": "canon_631b2573f1", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.7, "reason": "..."},
    {"entry_id": "canon_d3b365b181", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.65, "reason": "..."},
    {"entry_id": "canon_9a13d63096", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.6, "reason": "..."},
    {"entry_id": "canon_c7bb723eed", "attach_to_theme_id": "gtheme_909078a767",
     "confidence": 0.7, "reason": "..."},
    {"entry_id": "canon_387a8be035", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.65, "reason": "..."},
    {"entry_id": "canon_74e3581aeb", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.6, "reason": "..."},
    {"entry_id": "canon_9813e7d08e", "attach_to_theme_id": "gtheme_c1bd913fa0",
     "confidence": 0.6, "reason": "..."},
    {"entry_id": "canon_4602e8d1a7", "attach_to_theme_id": "gtheme_909078a767",
     "confidence": 0.75, "reason": "..."},
    {"entry_id": "canon_d5c91074b2", "attach_to_theme_id": "gtheme_909078a767",
     "confidence": 0.7, "reason": "..."},
    # 4 real orphans (LLM returned null)
    {"entry_id": "canon_741bd48ea5", "attach_to_theme_id": None,
     "confidence": 0.3, "reason": "no match"},
    {"entry_id": "canon_eeb02e7049", "attach_to_theme_id": None,
     "confidence": 0.3, "reason": "no match"},
    {"entry_id": "canon_3607f25d4b", "attach_to_theme_id": None,
     "confidence": 0.3, "reason": "no match"},
    {"entry_id": "canon_e7d101d69a", "attach_to_theme_id": None,
     "confidence": 0.3, "reason": "no match"},
]

# Concept types from the project's concept_decisions section in project.json.
CONCEPT_TYPES_BY_ID = {
    "canon_dec3f01607": "Mechanism", "canon_8fa6bcbc81": "Problem",
    "canon_c1ebaf3ae6": "Problem", "canon_cb4d56a449": "Problem",
    "canon_382a982936": "Topic", "canon_5eaa7d7d04": "Solution",
    "canon_0ecdbbe4fb": "Mechanism", "canon_631b2573f1": "Solution",
    "canon_d3b365b181": "Topic", "canon_9a13d63096": "Problem",
    "canon_c7bb723eed": "Mechanism", "canon_387a8be035": "Topic",
    "canon_74e3581aeb": "Problem", "canon_9813e7d08e": "Problem",
    "canon_4602e8d1a7": "Solution", "canon_d5c91074b2": "Problem",
    "canon_741bd48ea5": "Example", "canon_eeb02e7049": "Example",
    "canon_3607f25d4b": "Example", "canon_e7d101d69a": "Topic",
}

# Existing themes (9 AI/tech themes) from evolution_log.json audit.
EXISTING_THEME_IDS = [
    "gtheme_c09dba17d5", "gtheme_dd9e8de17f", "gtheme_9276388a4b",
    "gtheme_720b2284ce", "gtheme_a296c8e189", "gtheme_c1bd913fa0",
    "gtheme_909078a767", "gtheme_41c8361674", "gtheme_c87ef00a11",
]


def test_proj_39a354d2c50e_produces_new_theme_candidate():
    """The real proj_39a354d2c50e LLM output, replayed against v3 proposer,
    must produce a new theme candidate (not the silent-absorb it did under v2)."""
    proposer = AutoThemeProposer()

    fake_entries = [
        {"entry_id": eid, "canonical_name": f"n-{eid}",
         "concept_type": CONCEPT_TYPES_BY_ID[eid]}
        for eid in CONCEPT_TYPES_BY_ID
    ]
    active_themes = [
        {"theme_id": tid, "name": f"Theme-{tid}", "status": "active",
         "description": "", "keywords": [], "concept_memberships": []}
        for tid in EXISTING_THEME_IDS
    ]

    propose_calls: list = []
    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None: active_themes if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": REAL_LLM_ASSIGNMENTS},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts", return_value=None,
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate",
        side_effect=lambda *a, **kw: propose_calls.append(1) or {
            "theme_id": "t_new", "name": "沟通与表达方法论",
            "attached_count": 20,
        },
    ):
        result = proposer.process(
            project_id="proj_39a354d2c50e",
            project_name="得到精选",
            new_canonical_ids=list(CONCEPT_TYPES_BY_ID.keys()),
            run_id="r_regression",
            article_title="得到精选",
        )

    # The critical assertion: under v3, this article DOES produce a new
    # theme proposal. Under v2 it silently absorbed into existing themes.
    assert propose_calls, (
        f"proj_39a354d2c50e scenario must trigger new-theme proposal; "
        f"audit: {result.audit}"
    )
    assert result.action == "classified_with_new_candidate"
    assert result.new_candidate_theme is not None
    assert result.new_candidate_theme["theme_id"] == "t_new"
