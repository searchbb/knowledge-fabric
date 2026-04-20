"""Stage 1 recall behaviour tests with P1.5 dedupe preload.

Two jobs for this file:

1. Semantic equivalence: the P1.5 refactor of ``_recall_candidates``
   (has_dedupe_key-per-pair → preloaded set) must produce the same
   candidate list as before for the same inputs. We pin a few
   representative inputs and check every dedupe-existence path.

2. Disk-read regression guard: Stage 1 must read the relations store
   at most ONCE per call, regardless of how many pairs it considers.
   This was the point of the optimisation — without a test, a later
   refactor could quietly reintroduce the per-pair read pattern.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.auto.cross_concept_discoverer import CrossConceptDiscoverer


def _concept(entry_id: str, *, ctype: str = "Topic", projects=None, desc: str = "") -> dict:
    return {
        "entry_id": entry_id,
        "canonical_name": entry_id,
        "concept_type": ctype,
        "description": desc,
        "source_links": [{"project_id": p} for p in (projects or [entry_id])],
    }


@pytest.fixture
def isolated_relations(tmp_path: Path, monkeypatch):
    from app import config as config_module

    uploads = tmp_path / "uploads"
    (uploads / "projects").mkdir(parents=True)
    monkeypatch.setattr(config_module.Config, "UPLOAD_FOLDER", str(uploads))
    return uploads / "projects" / "cross_concept_relations.json"


def _seed_relations(relations_file: Path, dedupe_keys: list[str]):
    rels = {}
    for i, key in enumerate(dedupe_keys):
        src, rtype, tgt = key.split("|")
        rels[f"crel_{i}"] = {
            "relation_id": f"crel_{i}",
            "source_entry_id": src,
            "target_entry_id": tgt,
            "relation_type": rtype,
            "dedupe_key": key,
            "status": "active",
        }
    relations_file.write_text(
        json.dumps({"version": 1, "relations": rels}, ensure_ascii=False, indent=2)
    )


class TestSemanticEquivalence:
    """Same inputs → same output, regardless of the dedupe-check path."""

    def test_no_existing_relations_returns_all_cross_article_pairs(
        self, isolated_relations
    ):
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", ctype="Problem", projects=["proj_1"]),
            _concept("b", ctype="Solution", projects=["proj_2"]),
            _concept("c", ctype="Topic", projects=["proj_3"]),
        ]
        out = d._recall_candidates(concepts, exclude_existing=True)
        ids = {(c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]) for c in out}
        # All 3 pairs cross articles and none are dedup'd.
        assert ids == {("a", "b"), ("a", "c"), ("b", "c")}

    def test_existing_dedupe_keys_filter_matching_pairs(self, isolated_relations):
        """Seeding a dedupe_key for (a, design_inspiration, b) must drop
        that pair from Stage 1 output, regardless of direction or type
        in the pair's forward/reverse lookup."""
        _seed_relations(
            isolated_relations,
            ["a|design_inspiration|b"],
        )
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
            _concept("c", projects=["proj_3"]),
        ]
        out = d._recall_candidates(concepts, exclude_existing=True)
        ids = {(c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]) for c in out}
        # (a, b) dropped; (a, c) and (b, c) remain.
        assert ids == {("a", "c"), ("b", "c")}

    def test_reverse_direction_also_filters(self, isolated_relations):
        """If b→a is known, (a, b) should still be filtered — dedupe
        checks both directions."""
        _seed_relations(isolated_relations, ["b|problem_solution|a"])
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
        ]
        out = d._recall_candidates(concepts, exclude_existing=True)
        assert out == []

    def test_exclude_existing_false_keeps_dedup_pairs(self, isolated_relations):
        """When the caller disables the dedupe filter, even known pairs
        come through — used by manual rerun flows that want to reconsider."""
        _seed_relations(isolated_relations, ["a|design_inspiration|b"])
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
        ]
        out = d._recall_candidates(concepts, exclude_existing=False)
        ids = {(c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]) for c in out}
        assert ids == {("a", "b")}

    def test_same_article_pair_is_always_skipped(self, isolated_relations):
        """Two concepts from the same project list shouldn't pair up — this
        is an orthogonal rule, not affected by dedupe preload."""
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_same"]),
            _concept("b", projects=["proj_same"]),
        ]
        out = d._recall_candidates(concepts, exclude_existing=True)
        assert out == []

    def test_require_endpoint_in_gates_to_new_only(self, isolated_relations):
        """Incremental discover: at least one endpoint must be in the
        new_entry_ids set. Seed nothing so dedupe isn't the reason a pair
        is dropped."""
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),  # "old"
            _concept("b", projects=["proj_2"]),  # "old"
            _concept("c", projects=["proj_3"]),  # "new"
        ]
        out = d._recall_candidates(
            concepts, exclude_existing=True, require_endpoint_in={"c"}
        )
        ids = {(c["concept_a"]["entry_id"], c["concept_b"]["entry_id"]) for c in out}
        # Only pairs touching c pass; (a, b) is pure-old and drops.
        assert ids == {("a", "c"), ("b", "c")}


class TestFunnelCounts:
    """P4 step 1 — Stage 1 should report how many pairs were dropped at
    each filter so downstream A/B analysis (e.g. embedding recall) can
    compare the same funnel buckets apples-to-apples.

    Expected funnel keys:
      - raw_pairs:             N*(N-1)/2 combinations considered
      - after_incremental_gate: kept after require_endpoint_in filter
      - after_cross_article:   kept after "different project" rule
      - after_dedupe_filter:   kept after existing-key set
      - final:                 what gets returned (same as len(candidates))
    """

    def test_funnel_counts_match_filter_cascade(self, isolated_relations):
        _seed_relations(isolated_relations, [])
        d = CrossConceptDiscoverer()
        # 4 concepts across 3 articles:
        #   a -> proj_1, b -> proj_2, c -> proj_3, d -> proj_1 (same as a).
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
            _concept("c", projects=["proj_3"]),
            _concept("d", projects=["proj_1"]),
        ]
        candidates, funnel = d._recall_candidates(
            concepts, exclude_existing=True, return_funnel=True
        )
        # 4 concepts → 6 raw pairs.
        assert funnel["raw_pairs"] == 6
        # No incremental gate → all 6 carry through.
        assert funnel["after_incremental_gate"] == 6
        # (a,d) shares proj_1 → drops. Others all span different projects.
        assert funnel["after_cross_article"] == 5
        # No existing relations → no dedupe drop.
        assert funnel["after_dedupe_filter"] == 5
        assert funnel["final"] == 5
        assert len(candidates) == 5

    def test_funnel_counts_with_incremental_gate(self, isolated_relations):
        _seed_relations(isolated_relations, [])
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
            _concept("c", projects=["proj_3"]),
        ]
        # 3 concepts → 3 raw pairs, but only pairs touching 'c' pass.
        _, funnel = d._recall_candidates(
            concepts,
            exclude_existing=True,
            require_endpoint_in={"c"},
            return_funnel=True,
        )
        assert funnel["raw_pairs"] == 3
        # Pairs: (a,b), (a,c), (b,c). Only (a,c) and (b,c) touch c.
        assert funnel["after_incremental_gate"] == 2
        assert funnel["after_cross_article"] == 2
        assert funnel["final"] == 2

    def test_funnel_counts_with_dedupe_hits(self, isolated_relations):
        _seed_relations(isolated_relations, ["a|design_inspiration|b"])
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
            _concept("c", projects=["proj_3"]),
        ]
        _, funnel = d._recall_candidates(
            concepts, exclude_existing=True, return_funnel=True
        )
        # 3 raw pairs, all cross-article, but (a,b) deduped.
        assert funnel["raw_pairs"] == 3
        assert funnel["after_cross_article"] == 3
        assert funnel["after_dedupe_filter"] == 2
        assert funnel["final"] == 2

    def test_recall_still_returns_plain_list_by_default(self, isolated_relations):
        """Backward-compat: callers that don't opt into funnel should get
        the historical plain-list return shape so existing code keeps
        compiling without changes."""
        _seed_relations(isolated_relations, [])
        d = CrossConceptDiscoverer()
        concepts = [
            _concept("a", projects=["proj_1"]),
            _concept("b", projects=["proj_2"]),
        ]
        candidates = d._recall_candidates(concepts, exclude_existing=True)
        assert isinstance(candidates, list)
        assert len(candidates) == 1


class TestDiskReadBudget:
    """P1.5 contract: at most ONE relations-store read per Stage 1 call."""

    def test_stage1_reads_relations_file_at_most_once(self, isolated_relations):
        # 20 concepts → 190 candidate pairs → previously up to 190×12 = 2280
        # has_dedupe_key calls, each re-reading the JSON. Now must be 1.
        _seed_relations(isolated_relations, [])
        concepts = [
            _concept(f"c{i}", projects=[f"proj_{i}"]) for i in range(20)
        ]
        d = CrossConceptDiscoverer()

        from app.services.registry import cross_concept_relations as rel_mod

        with patch.object(
            rel_mod, "_load_relations", wraps=rel_mod._load_relations
        ) as spy:
            d._recall_candidates(concepts, exclude_existing=True)
        assert spy.call_count <= 1, (
            f"Stage 1 should read relations store at most once, got {spy.call_count}"
        )

    def test_stage1_skips_read_when_dedupe_disabled(self, isolated_relations):
        """A tiny micro-optimisation: when ``exclude_existing=False`` we
        don't need the set at all, so we shouldn't pay for the read.
        Regression guard so this stays cheap."""
        concepts = [
            _concept(f"c{i}", projects=[f"proj_{i}"]) for i in range(5)
        ]
        d = CrossConceptDiscoverer()

        from app.services.registry import cross_concept_relations as rel_mod

        with patch.object(
            rel_mod, "_load_relations", wraps=rel_mod._load_relations
        ) as spy:
            d._recall_candidates(concepts, exclude_existing=False)
        assert spy.call_count == 0
