"""Tests for ``app.services.auto.concept_decider``."""

from __future__ import annotations

from app.services.auto.concept_decider import AutoConceptDecider, ConceptDecision


def _candidate(**kwargs):
    base = {
        "key": "Topic:demo",
        "displayName": "Demo",
        "conceptType": "Topic",
        "connectedCount": 3,
        "mentionCount": 1,
    }
    base.update(kwargs)
    return base


class TestDecideOne:
    def setup_method(self):
        self.decider = AutoConceptDecider()

    def test_topic_with_high_connected_is_accepted(self):
        result = self.decider.decide(_candidate(conceptType="Topic", connectedCount=5))
        assert result.decision == "accepted"
        assert "Topic" in result.reason

    def test_technology_with_threshold_connected_is_accepted(self):
        result = self.decider.decide(_candidate(conceptType="Technology", connectedCount=2))
        assert result.decision == "accepted"

    def test_solution_with_high_connected_is_accepted(self):
        result = self.decider.decide(_candidate(conceptType="Solution", connectedCount=4))
        assert result.decision == "accepted"

    def test_insight_never_accepted_even_when_high_connected(self):
        result = self.decider.decide(_candidate(conceptType="Insight", connectedCount=10))
        assert result.decision == "pending"
        assert "never auto-accepted" in result.reason

    def test_problem_with_high_connected_is_accepted_under_inverse_rule(self):
        # Before 2026-04-11 the decider used a positive whitelist
        # {Topic, Solution, Technology}. A real Harness-article run
        # exposed the flaw: the LLM ontology generator emitted types
        # like Architecture, Problem, Mechanism that were all absent
        # from the whitelist, so 0 of 45 candidates got accepted.
        # The rule is now inverse: accept any non-Insight type with
        # enough connectivity. Problem with conn=10 must be accepted.
        result = self.decider.decide(_candidate(conceptType="Problem", connectedCount=10))
        assert result.decision == "accepted"
        assert "Problem" in result.reason

    def test_architecture_with_high_connected_is_accepted(self):
        # Same shape as the Harness bug: Architecture(15) is the top
        # concept by connectivity in that article's graph and must
        # not be silently dropped.
        result = self.decider.decide(_candidate(conceptType="Architecture", connectedCount=15))
        assert result.decision == "accepted"

    def test_mechanism_with_threshold_connected_is_accepted(self):
        result = self.decider.decide(_candidate(conceptType="Mechanism", connectedCount=2))
        assert result.decision == "accepted"

    def test_positive_whitelist_still_honored_when_explicit(self):
        # Back-compat: if a caller passes an explicit whitelist, the
        # decider falls back to the old positive-whitelist semantics.
        whitelisted = AutoConceptDecider(accept_types={"Topic", "Technology"})
        # Problem is NOT on the whitelist → pending
        result = whitelisted.decide(_candidate(conceptType="Problem", connectedCount=10))
        assert result.decision == "pending"
        # Topic IS on the whitelist → accepted
        result = whitelisted.decide(_candidate(conceptType="Topic", connectedCount=10))
        assert result.decision == "accepted"

    def test_below_threshold_connected_is_pending(self):
        result = self.decider.decide(_candidate(conceptType="Topic", connectedCount=1))
        assert result.decision == "pending"

    def test_zero_connected_is_ignore(self):
        result = self.decider.decide(_candidate(conceptType="Topic", connectedCount=0))
        assert result.decision == "ignore"

    def test_empty_concept_type_is_ignored_or_pending(self):
        result = self.decider.decide(_candidate(conceptType="", connectedCount=3))
        # Empty type is not in accept list, so should be pending
        assert result.decision == "pending"


class TestDecideAll:
    def test_summarize_counts(self):
        decider = AutoConceptDecider()
        decisions = decider.decide_all(
            [
                _candidate(conceptType="Topic", connectedCount=5),
                _candidate(conceptType="Technology", connectedCount=2, key="Technology:foo"),
                _candidate(conceptType="Insight", connectedCount=10, key="Insight:foo"),
                _candidate(conceptType="Problem", connectedCount=0, key="Problem:foo"),
                _candidate(conceptType="Topic", connectedCount=1, key="Topic:lonely"),
            ]
        )
        summary = AutoConceptDecider.summarize(decisions)
        assert summary["accepted"] == 2  # Topic+Tech with connected>=2
        assert summary["pending"] == 2  # Insight + lonely Topic
        assert summary["ignore"] == 1  # Problem with 0 connected


class TestConfiguration:
    def test_custom_min_connected(self):
        decider = AutoConceptDecider(min_connected_for_accept=3)
        # connected=2 should NOT be enough now
        result = decider.decide(_candidate(conceptType="Topic", connectedCount=2))
        assert result.decision == "pending"
        # connected=3 should still pass
        result = decider.decide(_candidate(conceptType="Topic", connectedCount=3))
        assert result.decision == "accepted"

    def test_invalid_min_raises(self):
        import pytest
        with pytest.raises(ValueError):
            AutoConceptDecider(min_connected_for_accept=0)
