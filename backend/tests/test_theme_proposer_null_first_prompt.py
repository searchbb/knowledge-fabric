"""Tests for null-first prompt discipline (v3 OOD fix).

Root cause of the proj_39a354d2c50e regression: the prompt's "优先复用已有主题"
pressure plus the LLM's reluctance to return null produced 0.6-0.7 force-fits
that looked classified but were semantically wrong. This test locks in that
the prompt now instructs the LLM to prefer abstention over weak matches.
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.auto.theme_proposer import AutoThemeProposer


def test_system_prompt_contains_null_first_instruction():
    """The LLM must be told that weak matches are worse than null."""
    proposer = AutoThemeProposer()
    captured_messages: list[list[dict]] = []

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            captured_messages.append(messages)
            return {"assignments": []}

    concepts = [
        {"entry_id": "e1", "canonical_name": "协作能力", "concept_type": "Mechanism"},
    ]
    themes = [
        {"theme_id": "t1", "name": "多智能体协作", "status": "active",
         "description": "", "keywords": [], "concept_memberships": []},
    ]

    with patch("app.utils.llm_client.LLMClient", return_value=FakeLLM()), \
         patch("app.services.auto.theme_proposer.registry.list_entries", return_value=[]):
        proposer._classify_via_llm(concepts, themes, "Some article")

    assert captured_messages, "LLM should have been called"
    system_msg = captured_messages[0][0]["content"]
    assert "null" in system_msg, f"system prompt missing null instruction: {system_msg!r}"
    assert ("勉强" in system_msg) or ("弱" in system_msg) or ("宁可" in system_msg), (
        f"system prompt missing weak-match-discouraged framing: {system_msg!r}"
    )


def test_system_prompt_removes_one_way_reuse_pressure():
    """The old '优先复用已有主题' phrasing created the force-fit bias. The new
    prompt should not contain unqualified reuse pressure."""
    proposer = AutoThemeProposer()
    captured_messages: list[list[dict]] = []

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            captured_messages.append(messages)
            return {"assignments": []}

    with patch("app.utils.llm_client.LLMClient", return_value=FakeLLM()), \
         patch("app.services.auto.theme_proposer.registry.list_entries", return_value=[]):
        proposer._classify_via_llm(
            [{"entry_id": "e1", "canonical_name": "n", "concept_type": "Topic"}],
            [{"theme_id": "t1", "name": "T", "status": "active",
              "description": "", "keywords": [], "concept_memberships": []}],
            "",
        )

    system_msg = captured_messages[0][0]["content"]
    assert "优先复用已有主题，谨慎提议新主题。" not in system_msg, (
        "unqualified reuse pressure must be removed or softened"
    )
