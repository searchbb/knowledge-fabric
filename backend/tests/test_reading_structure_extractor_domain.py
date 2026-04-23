"""Tests for domain-aware reading structure extraction (v3 methodology fix)."""
from __future__ import annotations

from unittest.mock import patch

from app.services.reading_structure_extractor import (
    ReadingStructureExtractor,
    BACKBONE_LABELS_BY_DOMAIN,
    GROUP_TITLES_BY_DOMAIN,
    _build_system_prompt,
)


def test_backbone_labels_by_domain_has_tech_and_methodology():
    assert BACKBONE_LABELS_BY_DOMAIN["tech"] == ["Topic", "Problem", "Solution", "Architecture"]
    assert BACKBONE_LABELS_BY_DOMAIN["methodology"] == ["Topic", "Problem", "Principle", "Method"]


def test_group_titles_by_domain_methodology_has_step_case_antipattern_signal():
    mt = GROUP_TITLES_BY_DOMAIN["methodology"]
    assert "Step" in mt
    assert "Antipattern" in mt
    assert "Case" in mt
    assert "Signal" in mt
    # Tech-only labels must NOT appear in methodology titles
    assert "Technology" not in mt
    assert "Mechanism" not in mt


def test_system_prompt_for_methodology_differs_from_tech():
    tech_prompt = _build_system_prompt("tech")
    meth_prompt = _build_system_prompt("methodology")
    assert tech_prompt != meth_prompt
    # Tech prompt is framed as 技术文章 editor
    assert "技术文章编辑" in tech_prompt
    # Methodology prompt reframes and redefines problem/solution/architecture semantics
    assert "方法论文章编辑" in meth_prompt
    assert "Method" in meth_prompt  # methodology mentions Method
    assert "原则" in meth_prompt
    # Methodology group_titles must reference Step/Case/Antipattern/Signal
    assert "Step" in meth_prompt
    assert "Case" in meth_prompt


def test_system_prompt_unknown_domain_falls_back_to_tech():
    tech_prompt = _build_system_prompt("tech")
    unknown_prompt = _build_system_prompt("news")
    assert unknown_prompt == tech_prompt


def test_extract_threads_domain_into_system_prompt():
    """When extract(domain='methodology') is called, the LLM must receive the
    methodology system prompt — not tech."""
    captured: list[list[dict]] = []

    class FakeLLM:
        def chat_json(self, messages, **kwargs):
            captured.append(messages)
            return {
                "title": "t",
                "summary": "s",
                "problem": {"title": "p", "summary": "s"},
                "solution": {"title": "m", "summary": "s"},
                "architecture": {"title": "a", "summary": "s"},
                "group_titles": {},
                "article_sections": [],
            }

    extractor = ReadingStructureExtractor(llm_client=FakeLLM())
    extractor.extract(
        project_name="test",
        document_text="some body",
        analysis_summary="summary",
        ontology={"entity_types": [], "edge_types": []},
        graph_data={"nodes": [], "edges": []},
        domain="methodology",
    )
    assert captured
    system_content = captured[0][0]["content"]
    assert "方法论文章编辑" in system_content
