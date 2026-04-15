"""Regression tests for MiniMaxLLMClient edge-key alias normalization.

Root cause story (see 2026-04-15 profile-root-cause session):
  Bailian qwen3.5-plus (and possibly other qwen3 models) returns
  {"facts": [...]} instead of {"edges": [...]} under Graphiti's
  ExtractedEdges prompt — the prompt text says "extracts fact triples"
  and each record has a `fact` field, so the top-level key leaks too.
  Without the alias, _normalize_for_model silently produces `edges: []`,
  pydantic accepts it (list[Edge] is fine with empty list), and the
  graph ends up with 0 edges.

These tests lock the alias table so that regression cannot sneak back in
if someone later "cleans up" the aliases.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.graph_builder import MiniMaxLLMClient  # noqa: E402


# Mirror the relevant shape of graphiti_core.prompts.extract_edges.ExtractedEdges
# without depending on the real symbol (it's stable across 0.28–0.29).
class _Edge(BaseModel):
    source_entity_name: str
    target_entity_name: str
    relation_type: str
    fact: str
    valid_at: str | None = None
    invalid_at: str | None = None


class _ExtractedEdges(BaseModel):
    edges: list[_Edge]


def _client() -> MiniMaxLLMClient:
    """Create a bare MiniMaxLLMClient without touching OpenAI — we only need
    the class methods for normalization."""
    return MiniMaxLLMClient.__new__(MiniMaxLLMClient)


def _sample_edge_payload(key: str) -> dict:
    """Return {key: [<one valid edge>]}. Used to test each alias."""
    return {
        key: [
            {
                "source_entity_name": "A",
                "target_entity_name": "B",
                "relation_type": "HAS_TOPIC",
                "fact": "A has topic B.",
            }
        ]
    }


# ----- Table-level lock ------------------------------------------------


def test_root_field_aliases_edges_contains_facts():
    """Regression: `facts` must stay in the edges alias tuple.

    If this ever fails, it means someone removed the alias and the
    pipeline will silently drop Bailian qwen3-family edges again.
    """
    assert "facts" in MiniMaxLLMClient.ROOT_FIELD_ALIASES["edges"]


def test_root_field_aliases_edges_full_set():
    """Lock the full alias set — changes need an explicit test update."""
    assert MiniMaxLLMClient.ROOT_FIELD_ALIASES["edges"] == (
        "relations", "relationships", "triples", "extracted_edges", "facts",
    )


# ----- Functional end-to-end normalization ----------------------------


@pytest.mark.parametrize(
    "alias_key",
    ["facts", "relations", "relationships", "triples", "extracted_edges"],
)
def test_normalize_maps_alias_to_edges(alias_key):
    """Every known alias key must produce a non-empty `edges` field after
    _normalize_for_model — this is the behavior that was silently broken
    before the facts alias was added."""
    client = _client()
    payload = _sample_edge_payload(alias_key)
    normalized = client._normalize_for_model(
        payload,
        _ExtractedEdges,
        entity_type_lookup={},
        entity_name_lookup=[],
    )
    assert isinstance(normalized, dict)
    assert "edges" in normalized, (
        f"alias {alias_key!r} did not get mapped to 'edges'; "
        f"normalized keys: {list(normalized.keys())}"
    )
    assert len(normalized["edges"]) == 1
    assert normalized["edges"][0]["source_entity_name"] == "A"
    assert normalized["edges"][0]["relation_type"] == "HAS_TOPIC"


def test_normalize_facts_alias_survives_pydantic_validation():
    """Full path: alias -> normalize -> pydantic validate. This is the
    exact production code path that was silently dropping edges."""
    client = _client()
    payload = _sample_edge_payload("facts")
    normalized = client._normalize_for_model(
        payload,
        _ExtractedEdges,
        entity_type_lookup={},
        entity_name_lookup=[],
    )
    # The real _generate_response call pydantic-validates after normalize.
    validated = _ExtractedEdges.model_validate(normalized)
    assert len(validated.edges) == 1
    assert validated.edges[0].source_entity_name == "A"


def test_normalize_empty_edges_does_not_crash():
    """Edge case: {"facts": []} should produce {"edges": []} cleanly."""
    client = _client()
    normalized = client._normalize_for_model(
        {"facts": []},
        _ExtractedEdges,
        entity_type_lookup={},
        entity_name_lookup=[],
    )
    assert normalized == {"edges": []}


def test_normalize_prefers_edges_over_alias_if_both_present():
    """If the LLM returns both `edges` and `facts`, the real `edges` key
    wins (we don't accidentally overwrite it)."""
    client = _client()
    payload = {
        "edges": [
            {
                "source_entity_name": "real_source",
                "target_entity_name": "real_target",
                "relation_type": "HAS_TOPIC",
                "fact": "real",
            }
        ],
        "facts": [
            {
                "source_entity_name": "alias_source",
                "target_entity_name": "alias_target",
                "relation_type": "HAS_TOPIC",
                "fact": "alias",
            }
        ],
    }
    normalized = client._normalize_for_model(
        payload,
        _ExtractedEdges,
        entity_type_lookup={},
        entity_name_lookup=[],
    )
    assert len(normalized["edges"]) == 1
    assert normalized["edges"][0]["source_entity_name"] == "real_source"
