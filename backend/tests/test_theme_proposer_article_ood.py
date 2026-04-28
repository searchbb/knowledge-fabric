"""Tests for article-level OOD pre-gate (v3 OOD fix, part 3).

If every concept's confidence is below member_threshold AND max confidence
is below 0.75, the entire article is treated as article-level OOD: skip
the candidate attaches, go straight to new-theme-candidate proposal.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_proposer import AutoThemeProposer


def _fake_theme(theme_id: str) -> dict:
    return {
        "theme_id": theme_id, "name": "T", "status": "active",
        "description": "", "keywords": [], "concept_memberships": [],
    }


def test_article_level_ood_skips_attaches_and_proposes_new_theme():
    """Uniformly weak LLM output (max conf < 0.75, zero members): no
    attach_concepts calls should happen; go straight to new-theme proposal."""
    proposer = AutoThemeProposer()

    concepts_payload = [
        {"entry_id": f"e{i}", "canonical_name": f"n-{i}", "concept_type": "Problem"}
        for i in range(5)
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]}
        for c in concepts_payload
    ]

    llm_assignments = [
        {"entry_id": f"e{i}", "attach_to_theme_id": "t1",
         "confidence": 0.6 + i * 0.02, "reason": "weak"}  # max = 0.68
        for i in range(5)
    ]

    attach_calls: list = []
    propose_calls: list = []

    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None, **kw: [_fake_theme("t1")] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts",
        side_effect=lambda *a, **kw: attach_calls.append((a, kw)),
    ), patch.object(
        AutoThemeProposer, "_propose_new_theme_candidate",
        side_effect=lambda *a, **kw: propose_calls.append(1) or {
            "theme_id": "t_new", "name": "New", "attached_count": 5,
        },
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
            article_title="OOD article",
        )

    assert not attach_calls, "article-level OOD must skip attach_concepts"
    assert propose_calls, "article-level OOD must propose new theme candidate"
    assert result.audit["article_level_ood"] is True
    assert result.audit["max_confidence"] < 0.75
    assert result.audit["member_count"] == 0


def test_near_member_confidence_does_not_trigger_ood_gate():
    """If max confidence is 0.76 (close to but below member threshold),
    do NOT trigger article-level OOD — fall through to normal path."""
    proposer = AutoThemeProposer()

    concepts_payload = [
        {"entry_id": f"e{i}", "canonical_name": f"n-{i}", "concept_type": "Topic"}
        for i in range(5)
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]}
        for c in concepts_payload
    ]

    llm_assignments = [
        {"entry_id": f"e{i}", "attach_to_theme_id": "t1",
         "confidence": 0.76 if i == 0 else 0.62, "reason": "ok"}
        for i in range(5)
    ]

    attach_calls: list = []

    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None, **kw: [_fake_theme("t1")] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts",
        side_effect=lambda *a, **kw: attach_calls.append((a, kw)),
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
        )

    assert result.audit["article_level_ood"] is False
    assert attach_calls, "normal path must attach the candidates"


def test_any_member_confidence_prevents_ood_gate():
    """If at least one concept has confidence >= 0.78 (member tier), OOD gate
    must NOT fire regardless of max, since at least one strong anchor exists."""
    proposer = AutoThemeProposer()

    concepts_payload = [
        {"entry_id": f"e{i}", "canonical_name": f"n-{i}", "concept_type": "Topic"}
        for i in range(5)
    ]
    fake_entries = [
        {"entry_id": c["entry_id"], "canonical_name": c["canonical_name"],
         "concept_type": c["concept_type"]}
        for c in concepts_payload
    ]

    llm_assignments = [
        {"entry_id": "e0", "attach_to_theme_id": "t1", "confidence": 0.9, "reason": "s"},
    ] + [
        {"entry_id": f"e{i}", "attach_to_theme_id": None, "confidence": 0.2, "reason": "n"}
        for i in range(1, 5)
    ]

    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None, **kw: [_fake_theme("t1")] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer, "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts", return_value=None,
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
        )

    assert result.audit["article_level_ood"] is False


def test_article_level_ood_new_candidate_uses_effective_project_domain():
    """Regression: process(project_domain=...) must carry that domain into
    new candidate creation, not fall back to the proposer's constructor default.
    """
    proposer = AutoThemeProposer(project_domain="tech")

    concepts_payload = [
        {"entry_id": f"e{i}", "canonical_name": f"n-{i}", "concept_type": "Principle"}
        for i in range(5)
    ]
    fake_entries = [
        {
            "entry_id": c["entry_id"],
            "canonical_name": c["canonical_name"],
            "concept_type": c["concept_type"],
        }
        for c in concepts_payload
    ]
    llm_assignments = [
        {
            "entry_id": f"e{i}",
            "attach_to_theme_id": "t1",
            "confidence": 0.6,
            "reason": "weak",
        }
        for i in range(5)
    ]
    created_domains: list[str | None] = []

    class FakeLLM:
        def chat_json(self, **kwargs):
            return {
                "name": "方法论新主题",
                "description": "desc",
                "keywords": ["k"],
            }

    def _capture_create_theme(**kwargs):
        created_domains.append(kwargs.get("domain"))
        return {"theme_id": "t_new", "name": kwargs["name"]}

    with patch(
        "app.services.auto.theme_proposer.themes.list_themes",
        side_effect=lambda *, status=None, **kw: [_fake_theme("t1")] if status in (None, "active") else [],
    ), patch(
        "app.services.auto.theme_proposer.registry.list_entries",
        return_value=fake_entries,
    ), patch.object(
        AutoThemeProposer,
        "_classify_via_llm",
        return_value={"assignments": llm_assignments},
    ), patch(
        "app.services.auto.theme_proposer.get_pipeline_llm_params",
        return_value={
            "api_key": "sk-test",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3.5-plus",
        },
    ), patch(
        "app.services.auto.theme_proposer.LLMClient",
        return_value=FakeLLM(),
    ), patch(
        "app.services.auto.theme_proposer.themes.create_theme",
        side_effect=_capture_create_theme,
    ), patch(
        "app.services.auto.theme_proposer.themes.attach_concepts",
        return_value=None,
    ):
        result = proposer.process(
            project_id="p",
            new_canonical_ids=[c["entry_id"] for c in concepts_payload],
            run_id="r",
            project_domain="methodology",
        )

    assert result.new_candidate_theme["theme_id"] == "t_new"
    assert created_domains == ["methodology"]
