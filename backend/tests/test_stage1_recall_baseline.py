"""Frozen Stage 1 recall fixture — the A/B cutover baseline (P4 step 4).

Per GPT consult 2026-04-17: before swapping Stage 1 from rule-based pair
enumeration to embedding nearest-neighbour recall, we need a golden
fixture whose funnel numbers are known. Otherwise "the embedding recall
is better" is pure vibes — we'd be comparing different candidate
distributions on different themes on different days.

This file builds one deterministic theme setup (20 concepts, 5 articles,
varied types, curated overlaps) and pins the full funnel dict. Step 6
will add the same fixture's output under the embedding flag and diff the
two sides. If step 6 lowers ``sent_to_llm`` by >30% *without* a matching
drop in ``llm_accepted`` (once plugged in), that's the success signal.

If you find yourself editing these numbers, stop and ask:
    - did I intentionally change Stage 1 semantics (scoring / filters)?
    - or is this a drift I shouldn't be absorbing silently?
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


@pytest.fixture
def isolated_relations(tmp_path: Path, monkeypatch):
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))


# ---------------------------------------------------------------------------
# Fixture: 20 concepts across 5 articles, designed to exercise every branch.
#
# Types chosen to hit _COMPLEMENTARY_TYPE_PAIRS: Problem↔Solution,
# Topic↔Technology, Constraint↔Solution, etc. Descriptions share overlapping
# tokens so the description-overlap scoring engages on some pairs.
# Articles overlap in ownership (a & b both live in proj_1) so the
# same-article drop rule triggers on some combos.
#
# Any change to this fixture invalidates every baseline expectation below.
# ---------------------------------------------------------------------------


def _c(entry_id: str, projects: list[str], ctype: str, desc: str = "") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": entry_id,
        "concept_type": ctype,
        "description": desc,
        "source_links": [{"project_id": p} for p in projects],
    }


def _fixture_concepts() -> list[dict]:
    return [
        # Article 1 (proj_1): 4 concepts, Problem + Topic + Solution + Evidence
        _c("c01", ["proj_1"], "Problem", "llm local inference stalls and fails"),
        _c("c02", ["proj_1"], "Topic", "local inference workflow for llm"),
        _c("c03", ["proj_1"], "Solution", "route stalls to cloud inference"),
        _c("c04", ["proj_1"], "Evidence", "benchmark shows local stalls often"),
        # Article 2 (proj_2): 4 concepts, Problem/Solution/Topic/Technology
        _c("c05", ["proj_2"], "Problem", "inference latency grows with traffic"),
        _c("c06", ["proj_2"], "Solution", "autoscale cloud workers on demand"),
        _c("c07", ["proj_2"], "Topic", "cloud inference autoscaling"),
        _c("c08", ["proj_2"], "Technology", "kubernetes hpa autoscale"),
        # Article 3 (proj_3): 4 concepts, Constraint/Solution/Topic/Example
        _c("c09", ["proj_3"], "Constraint", "cost budget limits cloud workers"),
        _c("c10", ["proj_3"], "Solution", "quantize model to cut cloud cost"),
        _c("c11", ["proj_3"], "Topic", "model quantization methods"),
        _c("c12", ["proj_3"], "Example", "Llama-3 8B quantized 4bit"),
        # Article 4 (proj_4): 4 concepts, Topic/Technology/Problem/Solution
        _c("c13", ["proj_4"], "Topic", "prompt caching for inference cost"),
        _c("c14", ["proj_4"], "Technology", "anthropic prompt cache api"),
        _c("c15", ["proj_4"], "Problem", "prompt cache misses hurt latency"),
        _c("c16", ["proj_4"], "Solution", "warm cache with prefetch"),
        # Article 5 (proj_5): 4 concepts, same set of types + Evidence
        _c("c17", ["proj_5"], "Topic", "evaluating inference quality offline"),
        _c("c18", ["proj_5"], "Problem", "quality regression after quantization"),
        _c("c19", ["proj_5"], "Solution", "diff golden prompts before deploy"),
        _c("c20", ["proj_5"], "Evidence", "ab test shows 2pct quality drop"),
    ]


# ---------------------------------------------------------------------------
# Baseline assertions
# ---------------------------------------------------------------------------


class TestBaselineFunnel:
    """Full-theme, no incremental gate, no dedupe — the maximal recall case."""

    def test_baseline_full_theme_funnel(self, isolated_relations):
        d = CrossConceptDiscoverer()
        concepts = _fixture_concepts()

        _, funnel = d._recall_candidates(
            concepts, exclude_existing=True, return_funnel=True
        )

        # 20 concepts → 20 choose 2 = 190 raw pairs.
        assert funnel["raw_pairs"] == 190
        # No incremental gate → everything passes this filter.
        assert funnel["after_incremental_gate"] == 190
        # Each article has 4 concepts → 4 choose 2 = 6 same-article drops per
        # article × 5 articles = 30. Cross-article = 190 − 30 = 160.
        assert funnel["after_cross_article"] == 160
        # No seeded relations → dedupe drops nothing.
        assert funnel["after_dedupe_filter"] == 160
        assert funnel["final"] == 160

    def test_baseline_with_incremental_gate_three_new_concepts(
        self, isolated_relations
    ):
        """Simulates the P1 inline-pipeline use-case: "article 5 just landed,
        bridge its 4 concepts to the rest". Only pairs touching article 5's
        concepts survive the incremental gate."""
        d = CrossConceptDiscoverer()
        concepts = _fixture_concepts()
        new_ids = {"c17", "c18", "c19", "c20"}

        _, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in=new_ids,
            return_funnel=True,
        )

        assert funnel["raw_pairs"] == 190
        # New×Old pairs = 4 new × 16 old = 64. New×New pairs = 4C2 = 6.
        # Total = 70.
        assert funnel["after_incremental_gate"] == 70
        # Of those 70: new×new (6) share proj_5, so drop all 6.
        # New×old (64) all cross articles → keep.
        assert funnel["after_cross_article"] == 64
        assert funnel["after_dedupe_filter"] == 64
        assert funnel["final"] == 64

    def test_baseline_with_seeded_dedupe_hits(self, isolated_relations, tmp_path):
        """Seed two existing xrels for pairs in the fixture. Recall should
        drop exactly those two (and only those two) from the output."""
        from app import config as config_module
        uploads = Path(config_module.Config.UPLOAD_FOLDER)
        (uploads / "projects").mkdir(parents=True, exist_ok=True)
        rels_file = uploads / "projects" / "cross_concept_relations.json"
        # Seed two **cross-article** pairs so dedupe actually engages
        # (same-article pairs get dropped by the cross-article rule first).
        rels_file.write_text(json.dumps({
            "version": 1,
            "relations": {
                "crel_1": {
                    "relation_id": "crel_1",
                    "dedupe_key": "c01|problem_solution|c06",
                    "status": "active",
                    "source_entry_id": "c01",
                    "target_entry_id": "c06",
                    "relation_type": "problem_solution",
                },
                "crel_2": {
                    "relation_id": "crel_2",
                    "dedupe_key": "c05|pattern_reuse|c15",
                    "status": "active",
                    "source_entry_id": "c05",
                    "target_entry_id": "c15",
                    "relation_type": "pattern_reuse",
                },
            },
        }))

        d = CrossConceptDiscoverer()
        concepts = _fixture_concepts()

        _, funnel = d._recall_candidates(
            concepts, exclude_existing=True, return_funnel=True
        )

        # Both seeded pairs are cross-article (proj_1↔proj_2, proj_2↔proj_4)
        # so same-article rule doesn't touch them; dedupe drops exactly 2.
        assert funnel["after_cross_article"] == 160
        assert funnel["after_dedupe_filter"] == 158
        assert funnel["final"] == 158


class TestBaselineScoringOrder:
    """Lock in the ordering contract so future rerank-rule edits are visible."""

    def test_top_ranked_candidate_pairs_complementary_types(self, isolated_relations):
        """The highest-recall-score pair should be type-complementary. Tokens
        the fixture includes in multiple Problem/Solution descriptions push
        those pairs above pure Topic/Topic pairs."""
        d = CrossConceptDiscoverer()
        concepts = _fixture_concepts()

        candidates = d._recall_candidates(concepts, exclude_existing=True)

        # The #1 candidate should have a non-trivial score (complementary
        # types + token overlap both engaged).
        top = candidates[0]
        assert top["recall_score"] >= 2.0, (
            f"top candidate score degraded: {top['recall_score']} "
            f"({top['concept_a']['entry_id']} x {top['concept_b']['entry_id']})"
        )
