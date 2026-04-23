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
    """The LLM must be told that weak matches are worse than null, and must
    get an explicit numeric threshold consistent with candidate_threshold."""
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

    # The weak-match-is-worse framing must be present (this is the real
    # behavior-change instruction — "null" alone is too weak; the old v2
    # prompt also contained the word "null" in its return-format description).
    assert ("勉强" in system_msg) or ("宁可" in system_msg), (
        f"system prompt missing weak-match-discouraged framing: {system_msg!r}"
    )
    # The null threshold must be explicitly stated and aligned with the
    # configured candidate_threshold (0.55). A stricter bar (0.6) would
    # push legitimate 0.55-0.60 in-domain attaches to null and fragment themes.
    assert "0.55" in system_msg, (
        f"system prompt must reference the 0.55 candidate_threshold explicitly: {system_msg!r}"
    )
    # The null option must be named in an instructional context, not just
    # in the return-format description. Check that "null" is mentioned near
    # "必须" or "返回" within the discipline section.
    import re
    if not re.search(r"(必须|返回).{0,30}null|null.{0,30}(必须|返回)", system_msg):
        raise AssertionError(
            f"'null' must appear in an imperative instruction (必须/返回), "
            f"not only in return-format description: {system_msg!r}"
        )


def test_system_prompt_does_not_contain_unconditional_reuse_pressure():
    """Any mention of '优先复用' must be paired with a null-caveat in the
    same discipline block. Old v2 phrasing was bare reuse pressure; new v3
    must not reintroduce it in any form."""
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

    # If the prompt mentions "优先复用" anywhere, there must be a null-caveat
    # nearby ("null" or "若真的相关" or similar qualifier) — bare reuse
    # pressure is the exact bug v3 is fixing.
    if "优先复用" in system_msg or "优先归" in system_msg:
        # Look at the paragraph containing the reuse phrase.
        # Paragraphs are separated by blank lines (\n\n).
        paragraphs = system_msg.split("\n\n")
        for para in paragraphs:
            if "优先复用" in para or "优先归" in para:
                assert (
                    "null" in para
                    or "若真的相关" in para
                    or "真的相关" in para
                ), (
                    f"paragraph with reuse pressure lacks null-caveat or "
                    f"'真的相关' qualifier: {para!r}"
                )
