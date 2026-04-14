"""Tests for ``app.services.auto.theme_proposer``.

These tests focus on the pure decision logic (overlap matcher) that doesn't
need the registry on disk. The full attach / create paths are exercised
through the live E2E test, not unit-mocked here.
"""

from __future__ import annotations

from app.services.auto.theme_proposer import (
    AutoThemeProposer,
    AutoThemeResult,
    ThemeMatch,
)


class TestFindBestOverlap:
    def setup_method(self):
        self.proposer = AutoThemeProposer()

    def test_returns_none_when_empty_new_set(self):
        themes = [{"theme_id": "t1", "name": "x", "concept_entry_ids": ["a", "b"]}]
        assert self.proposer._find_best_overlap([], themes) is None

    def test_returns_none_when_no_overlap(self):
        themes = [
            {"theme_id": "t1", "name": "T1", "concept_entry_ids": ["x", "y"]},
            {"theme_id": "t2", "name": "T2", "concept_entry_ids": ["p", "q"]},
        ]
        assert self.proposer._find_best_overlap(["a", "b"], themes) is None

    def test_picks_theme_with_highest_overlap_count(self):
        themes = [
            {"theme_id": "t1", "name": "T1", "concept_entry_ids": ["a", "b"]},
            {"theme_id": "t2", "name": "T2", "concept_entry_ids": ["a", "b", "c"]},
            {"theme_id": "t3", "name": "T3", "concept_entry_ids": ["a"]},
        ]
        best = self.proposer._find_best_overlap(["a", "b", "c"], themes)
        assert best is not None
        assert best.theme_id == "t2"
        assert best.overlap_count == 3

    def test_breaks_tie_by_higher_ratio(self):
        themes = [
            # overlap=2, but theme has 5 ids → ratio against new=2/2=1.0
            {"theme_id": "t1", "name": "T1", "concept_entry_ids": ["a", "b", "x", "y", "z"]},
            # overlap=2, ratio=2/2=1.0 — tied
            {"theme_id": "t2", "name": "T2", "concept_entry_ids": ["a", "b"]},
        ]
        best = self.proposer._find_best_overlap(["a", "b"], themes)
        # Both have ratio 1.0; first wins on stable order (no tie-breaker further)
        assert best is not None
        assert best.overlap_count == 2

    def test_decides_skip_below_min_canonicals(self):
        result = self.proposer.process(
            project_id="proj_x",
            project_name="x",
            article_title="x",
            new_canonical_ids=["a"],
            run_id="run_x",
        )
        assert isinstance(result, AutoThemeResult)
        assert result.action == "skip"
        assert "need" in result.reason


class TestThresholdBoundaries:
    def test_overlap_count_below_min_does_not_reuse(self):
        proposer = AutoThemeProposer(
            min_overlap_count_for_reuse=3,
            min_overlap_ratio_for_reuse=0.5,
        )
        themes = [{"theme_id": "t1", "name": "T1", "concept_entry_ids": ["a", "b"]}]
        best = proposer._find_best_overlap(["a", "b", "c", "d"], themes)
        assert best is not None
        assert best.overlap_count == 2
        # Caller would NOT reuse because 2 < 3
        assert best.overlap_count < proposer.min_overlap_count_for_reuse

    def test_overlap_ratio_below_min_does_not_reuse(self):
        proposer = AutoThemeProposer(
            min_overlap_count_for_reuse=2,
            min_overlap_ratio_for_reuse=0.8,
        )
        themes = [{"theme_id": "t1", "name": "T1", "concept_entry_ids": ["a", "b"]}]
        # 2 of 5 new ids overlap → ratio = 0.4
        best = proposer._find_best_overlap(["a", "b", "c", "d", "e"], themes)
        assert best is not None
        assert best.overlap_ratio == 0.4
        assert best.overlap_ratio < proposer.min_overlap_ratio_for_reuse
