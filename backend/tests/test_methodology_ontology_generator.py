"""Tests for MethodologyOntologyGenerator (v3 Stage 2).

Methodology ontology has 8 entity types + 8 edge types (GPT-specified):
Entities: Topic, Problem, Principle, Method, Step, Antipattern, Case, Signal
Edges: ADDRESSES, GUIDED_BY, COMPOSED_OF, PRECEDES, AVOIDS, ILLUSTRATED_BY,
       INDICATED_BY, CONTRASTS_WITH
"""
from __future__ import annotations

from unittest.mock import patch

from app.services.methodology_ontology_generator import (
    MethodologyOntologyGenerator,
    METHODOLOGY_ENTITY_TYPES,
    METHODOLOGY_EDGE_TYPES,
)


def test_methodology_entity_types_are_exactly_the_eight():
    """Lock in the 8-type canonical set so a future tweak can't silently
    drop/add types."""
    assert METHODOLOGY_ENTITY_TYPES == {
        "Topic", "Problem", "Principle", "Method",
        "Step", "Antipattern", "Case", "Signal",
    }


def test_methodology_edge_types_are_exactly_the_eight():
    assert METHODOLOGY_EDGE_TYPES == {
        "ADDRESSES", "GUIDED_BY", "COMPOSED_OF", "PRECEDES",
        "AVOIDS", "ILLUSTRATED_BY", "INDICATED_BY", "CONTRASTS_WITH",
    }


def test_generate_prompts_llm_with_methodology_system_prompt():
    """The system prompt must mention Principle/Method/Step/Antipattern
    so the LLM knows this is the methodology schema, not tech."""
    gen = MethodologyOntologyGenerator()
    captured: list[list[dict]] = []

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            captured.append(messages)
            return {
                "entity_types": [
                    {"name": t, "description": "d", "attributes": [], "examples": []}
                    for t in METHODOLOGY_ENTITY_TYPES
                ],
                "edge_types": [
                    {"name": e, "description": "d", "source_targets": [], "attributes": []}
                    for e in METHODOLOGY_EDGE_TYPES
                ],
                "analysis_summary": "test",
            }

    with patch("app.utils.llm_client.LLMClient", return_value=FakeLLM()):
        gen.generate(document_texts=["some methodology article text"])

    assert captured
    system_msg = captured[0][0]["content"]
    assert "方法论" in system_msg or "methodology" in system_msg.lower()
    for entity_type in ["Principle", "Method", "Step", "Antipattern", "Signal"]:
        assert entity_type in system_msg, f"{entity_type} missing from system prompt"
    assert "GUIDED_BY" in system_msg
    assert "COMPOSED_OF" in system_msg


def test_generate_normalizes_unknown_types_to_methodology_set():
    """If the LLM returns a type name not in METHODOLOGY_ENTITY_TYPES,
    it must be dropped or mapped via aliases. Alias map: Concept→Principle,
    Action→Step. Truly unknown → DROPPED (tech generator falls back to
    'Technology'; for methodology we drop instead)."""
    gen = MethodologyOntologyGenerator()

    class FakeLLM:
        def chat_json(self, *, messages, **kwargs):
            return {
                "entity_types": [
                    {"name": "Principle", "description": "d", "attributes": [], "examples": []},
                    {"name": "Concept", "description": "d", "attributes": [], "examples": []},
                    {"name": "Action", "description": "d", "attributes": [], "examples": []},
                    {"name": "RandomJunk", "description": "d", "attributes": [], "examples": []},
                ],
                "edge_types": [
                    {"name": "GUIDED_BY", "description": "d", "source_targets": [], "attributes": []},
                    {"name": "UNKNOWN_EDGE", "description": "d", "source_targets": [], "attributes": []},
                ],
                "analysis_summary": "test",
            }

    with patch("app.utils.llm_client.LLMClient", return_value=FakeLLM()):
        ontology = gen.generate(document_texts=["doc"])

    entity_names = {e["name"] for e in ontology["entity_types"]}
    assert "Principle" in entity_names
    assert "Step" in entity_names  # Action -> Step
    assert "RandomJunk" not in entity_names
    assert entity_names.issubset(METHODOLOGY_ENTITY_TYPES)

    edge_names = {e["name"] for e in ontology["edge_types"]}
    assert "GUIDED_BY" in edge_names
    assert "UNKNOWN_EDGE" not in edge_names
    assert edge_names.issubset(METHODOLOGY_EDGE_TYPES)
