"""Tests for DomainClassifier (v3 Stage 4).

Classifier prompt (GPT-specified):
- Input: title + first 2000 chars
- Output JSON: {primary, confidence, secondary, secondary_confidence, reason}
- primary must be 'tech' or 'methodology'
- fallback threshold (in caller/dispatcher): confidence < 0.65 → tech
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.domain_classifier import DomainClassifier


def test_classifier_sends_title_and_first_2000_chars():
    """Must only send title + first 2000 chars of body, regardless of length."""
    classifier = DomainClassifier()
    captured: list[list[dict]] = []

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            captured.append(messages)
            return {
                "primary": "tech",
                "confidence": 0.9,
                "secondary": None,
                "secondary_confidence": 0.0,
                "reason": "stub",
            }

    # Build text with a unique suffix that won't appear in any truncated prefix
    early = "early_content_section " * 100   # first ~2200 chars
    late_marker = "LATE_UNIQUE_MARKER_XYZ_99999"
    late = " late_tail_content" * 300 + late_marker
    long_text = early + late  # total ~7400 chars; first 2000 are all "early_content_section"
    with patch("app.services.domain_classifier.LLMClient", return_value=FakeLLM()):
        classifier.classify(title="My Article", text=long_text)

    user_msg = captured[0][1]["content"]
    assert "My Article" in user_msg
    assert len(user_msg) < len(long_text), "classifier should truncate body"
    # First 2000 chars of body should be in the prompt
    body_sample = long_text[:2000]
    # The prompt includes title + 前2000字 label + body; body_sample must be present
    assert body_sample[:1000] in user_msg  # early portion present
    # But the unique late marker is NOT present (truncated)
    assert late_marker not in user_msg


def test_classifier_returns_structured_result():
    classifier = DomainClassifier()

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            return {
                "primary": "methodology",
                "confidence": 0.82,
                "secondary": "tech",
                "secondary_confidence": 0.35,
                "reason": "主体讲方法论",
            }

    with patch("app.services.domain_classifier.LLMClient", return_value=FakeLLM()):
        result = classifier.classify(title="t", text="some text")

    assert result["primary"] == "methodology"
    assert result["confidence"] == 0.82
    assert result["secondary"] == "tech"
    assert result["reason"] == "主体讲方法论"


def test_classifier_system_prompt_distinguishes_tech_from_methodology():
    classifier = DomainClassifier()
    captured: list[list[dict]] = []

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            captured.append(messages)
            return {"primary": "tech", "confidence": 0.9,
                    "secondary": None, "secondary_confidence": 0.0, "reason": ""}

    with patch("app.services.domain_classifier.LLMClient", return_value=FakeLLM()):
        classifier.classify(title="t", text="body")

    system_msg = captured[0][0]["content"]
    assert "tech" in system_msg
    assert "methodology" in system_msg
    # Must mention the tech-safe fallback guidance (GPT's phrasing "fallback" or "安全默认")
    assert "fallback" in system_msg.lower() or "安全默认" in system_msg


def test_classifier_gracefully_handles_bad_llm_json():
    """If LLM errors/returns malformed JSON, classifier must return low-confidence
    tech (so dispatcher falls back to tech) rather than crash."""
    classifier = DomainClassifier()

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            raise ValueError("JSON parse failed")

    with patch("app.services.domain_classifier.LLMClient", return_value=FakeLLM()):
        result = classifier.classify(title="t", text="body")

    assert result["primary"] == "tech"
    assert result["confidence"] == 0.0


def test_classifier_normalizes_unknown_primary_to_tech():
    """If LLM hallucinates 'news' as primary, classifier must coerce to
    tech with low confidence (tech-safe default)."""
    classifier = DomainClassifier()

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            return {
                "primary": "news",  # not in enum
                "confidence": 0.7,
                "secondary": None,
                "secondary_confidence": 0.0,
                "reason": "",
            }

    with patch("app.services.domain_classifier.LLMClient", return_value=FakeLLM()):
        result = classifier.classify(title="t", text="body")

    assert result["primary"] == "tech"
    assert result["confidence"] == 0.0
