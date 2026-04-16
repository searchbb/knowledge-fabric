"""Tests for the incremental scope gate in CrossConceptDiscoverer.

The gate (added 2026-04-16 per GPT consult f09fb61ce5e8a061) makes the inline
pipeline discover phase cheap by dropping pairs that don't touch the "new
article's" entry_ids before they ever reach the LLM. Without this gate,
every article would re-pay for old×old pairs at ingestion time.
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


def _concept(entry_id: str, project_id: str, ctype: str = "Topic") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": f"name-{entry_id}",
        "concept_type": ctype,
        "description": "",
        "source_links": [{"project_id": project_id, "project_name": project_id}],
    }


def test_recall_drops_pairs_without_new_endpoint():
    """Old × old pairs are gated out when require_endpoint_in is set."""
    d = CrossConceptDiscoverer()
    concepts = [
        _concept("e_old1", "p1", "Problem"),
        _concept("e_old2", "p2", "Solution"),  # complementary type, diff article
        _concept("e_new1", "p3", "Technology"),
    ]
    # No dedupe lookups so we don't depend on the registry layer.
    with patch(
        "app.services.auto.cross_concept_discoverer.has_dedupe_key",
        return_value=False,
    ):
        all_pairs = d._recall_candidates(concepts, exclude_existing=False)
        incremental = d._recall_candidates(
            concepts,
            exclude_existing=False,
            require_endpoint_in={"e_new1"},
        )

    # Without gate: 3 valid cross-article pairs (old1-old2, old1-new1, old2-new1).
    assert len(all_pairs) == 3
    # With gate: only the 2 pairs touching e_new1 survive.
    pair_ids = {
        tuple(sorted([c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]]))
        for c in incremental
    }
    assert pair_ids == {("e_new1", "e_old1"), ("e_new1", "e_old2")}


def test_recall_no_gate_when_set_is_empty_or_none():
    """Empty/None set means 'no incremental filter' — all pairs flow through."""
    d = CrossConceptDiscoverer()
    concepts = [_concept("a", "p1"), _concept("b", "p2")]
    with patch(
        "app.services.auto.cross_concept_discoverer.has_dedupe_key",
        return_value=False,
    ):
        none_gate = d._recall_candidates(concepts, exclude_existing=False, require_endpoint_in=None)
        # The discover() method explicitly converts an empty set to None before
        # calling _recall_candidates, so we don't test the empty-set path here
        # — only document that None means pass-through.
    assert len(none_gate) == 1


def test_discover_returns_split_theme_reason_when_only_one_article():
    """Locking in the GPT-consult-e297dd59ad8ab94b diagnostic enhancement.

    When all theme members come from the same article (a "split theme" — the
    article got bucketed into a theme by itself), the incremental discover
    must surface a clear reason explaining that this is upstream-bucketing,
    not a discover bug. Before this fix the reason was generic
    'No candidate pairs after recall filtering' which made it look like
    discover was broken.
    """
    d = CrossConceptDiscoverer()

    # Patch theme + registry so we don't need a live store.
    fake_theme = {
        "concept_memberships": [{"entry_id": "e1"}, {"entry_id": "e2"}, {"entry_id": "e3"}],
    }
    fake_entries = [
        _concept("e1", "proj_solo", "Problem"),
        _concept("e2", "proj_solo", "Solution"),
        _concept("e3", "proj_solo", "Topic"),
    ]
    with (
        patch(
            "app.services.auto.cross_concept_discoverer.themes.get_theme",
            return_value=fake_theme,
        ),
        patch(
            "app.services.auto.cross_concept_discoverer.registry.list_entries",
            return_value=fake_entries,
        ),
        patch(
            "app.services.auto.cross_concept_discoverer.has_dedupe_key",
            return_value=False,
        ),
    ):
        result = d.discover(
            theme_id="t_solo",
            new_entry_ids=["e1", "e2", "e3"],
            run_id="r_test",
        )

    assert result["candidates_count"] == 0
    assert result["theme_member_count"] == 3
    assert result["theme_article_count"] == 1
    assert result["eligible_entry_count"] == 3
    assert "Split-theme" in result["reason"]
    assert result["scope"]["incremental"] is True
    assert result["scope"]["different_article_required"] is True


def test_discover_returns_generic_no_pair_reason_when_multiple_articles():
    """Multi-article theme with no eligible new pairs gets the generic reason
    (not the split-theme one) — to avoid mis-blaming theme_proposer."""
    d = CrossConceptDiscoverer()
    fake_theme = {
        "concept_memberships": [{"entry_id": "e1"}, {"entry_id": "e2"}],
    }
    fake_entries = [
        _concept("e1", "proj_a", "Problem"),
        _concept("e2", "proj_b", "Solution"),
    ]
    with (
        patch(
            "app.services.auto.cross_concept_discoverer.themes.get_theme",
            return_value=fake_theme,
        ),
        patch(
            "app.services.auto.cross_concept_discoverer.registry.list_entries",
            return_value=fake_entries,
        ),
        # Pretend every pair is already deduped so candidates collapses to 0.
        patch(
            "app.services.auto.cross_concept_discoverer.has_dedupe_key",
            return_value=True,
        ),
    ):
        result = d.discover(
            theme_id="t_multi",
            new_entry_ids=["e1"],
            run_id="r_test",
        )

    assert result["candidates_count"] == 0
    assert result["theme_article_count"] == 2
    assert "Split-theme" not in result["reason"]
    assert "No candidate pairs after recall filtering" in result["reason"]
