"""Conservative deterministic rules for auto-accepting concept candidates.

The decider runs locally with no LLM call. It only operates on fields that
``ConceptViewService`` already exposes (``conceptType``, ``connectedCount``,
``mentionCount``, ``displayName``, ``key``).

Decision matrix (revised 2026-04-11 evening after a real Harness-article
run where 0 of 45 candidates were accepted because the old hard-coded
``_ACCEPT_TYPES = {Topic, Solution, Technology}`` whitelist didn't match
the ontology the LLM actually emitted — it produced Architecture(15),
Problem(6), Mechanism(3), etc. None of which were in the whitelist):

| connectedCount | conceptType                                    | Decision |
| -------------- | ---------------------------------------------- | -------- |
| ``>= 2``       | anything NOT in ``_NEVER_ACCEPT``              | accepted |
| ``>= 2``       | ``Insight`` (interpretive take)                | pending  |
| ``1``          | any                                            | pending  |
| ``0``          | any                                            | ignore   |

The rule became **inverse** (accept-unless-blocked) instead of the old
**positive whitelist** because the LLM-driven ontology generator emits
a per-project vocabulary (Architecture, Mechanism, Problem, Metric,
Evidence, Example, Topic, Technology…). A fixed positive whitelist
always lags the real vocabulary; the inverse form is vocabulary-
agnostic and still protects ``Insight`` — the one type the user
explicitly wants to confirm by hand because it's interpretive, not
structural.

``connectedCount >= 2`` is the structural signal. Isolated nodes
(conn=0) get ``ignore``. Single-edge nodes (conn=1) stay ``pending``
in case the user wants to promote them manually.

Outputs include a human-readable ``reason`` so the audit log can show
why each decision was made.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

# Concept types that are NEVER auto-accepted regardless of signal
# strength — interpretive nodes that the user must confirm by hand.
# Auto-accept now uses the inverse rule: anything NOT in this set is
# eligible if it has enough connectivity.
_NEVER_ACCEPT: frozenset[str] = frozenset({"Insight"})


Decision = Literal["accepted", "pending", "ignore"]


@dataclass
class ConceptDecision:
    concept_key: str
    display_name: str
    concept_type: str
    decision: Decision
    reason: str
    connected_count: int
    mention_count: int


class AutoConceptDecider:
    """Apply the deterministic rules above to a list of concept candidates."""

    never_accept_types: frozenset[str]
    min_connected_for_accept: int

    def __init__(
        self,
        *,
        never_accept_types: Iterable[str] | None = None,
        min_connected_for_accept: int = 2,
        # Kept for backward compatibility with existing callers/tests
        # that explicitly pass a positive whitelist. If set, only these
        # types are eligible (the old behavior). If None (default), the
        # inverse rule applies: anything not in ``never_accept_types``.
        accept_types: Iterable[str] | None = None,
    ) -> None:
        self.never_accept_types = (
            frozenset(never_accept_types) if never_accept_types else _NEVER_ACCEPT
        )
        self.accept_types: frozenset[str] | None = (
            frozenset(accept_types) if accept_types else None
        )
        if min_connected_for_accept < 1:
            raise ValueError("min_connected_for_accept must be >= 1")
        self.min_connected_for_accept = min_connected_for_accept

    def decide(self, candidate: dict) -> ConceptDecision:
        """Apply the rules to a single ``candidateConcepts`` item."""
        concept_type = (candidate.get("conceptType") or "").strip()
        display_name = (candidate.get("displayName") or "").strip()
        key = (candidate.get("key") or "").strip()
        connected = int(candidate.get("connectedCount") or 0)
        mention = int(candidate.get("mentionCount") or 0)

        if connected == 0:
            return ConceptDecision(
                concept_key=key,
                display_name=display_name,
                concept_type=concept_type,
                decision="ignore",
                reason="connectedCount is 0",
                connected_count=connected,
                mention_count=mention,
            )

        if concept_type in self.never_accept_types:
            return ConceptDecision(
                concept_key=key,
                display_name=display_name,
                concept_type=concept_type,
                decision="pending",
                reason=f"type {concept_type} is never auto-accepted",
                connected_count=connected,
                mention_count=mention,
            )

        if not concept_type:
            # Missing/unclassified type from the ontology — weak signal,
            # hold for manual review even if connectivity is high.
            return ConceptDecision(
                concept_key=key,
                display_name=display_name,
                concept_type=concept_type,
                decision="pending",
                reason="concept type is empty / unclassified",
                connected_count=connected,
                mention_count=mention,
            )

        # Inverse rule (default): accept anything with enough connectivity
        # that is not in the never-accept set. A caller may opt into the
        # old positive-whitelist behavior by passing ``accept_types=...``.
        is_type_eligible = (
            self.accept_types is None or concept_type in self.accept_types
        )

        if is_type_eligible and connected >= self.min_connected_for_accept:
            return ConceptDecision(
                concept_key=key,
                display_name=display_name,
                concept_type=concept_type,
                decision="accepted",
                reason=(
                    f"type {concept_type} with connected={connected} >= "
                    f"{self.min_connected_for_accept}"
                ),
                connected_count=connected,
                mention_count=mention,
            )

        return ConceptDecision(
            concept_key=key,
            display_name=display_name,
            concept_type=concept_type,
            decision="pending",
            reason=(
                f"type {concept_type} or connected={connected} "
                "below auto-accept threshold"
            ),
            connected_count=connected,
            mention_count=mention,
        )

    def decide_all(self, candidates: list[dict]) -> list[ConceptDecision]:
        return [self.decide(c) for c in candidates]

    @staticmethod
    def summarize(decisions: list[ConceptDecision]) -> dict[str, int]:
        """Return ``{decision: count}`` for the given decisions."""
        out = {"accepted": 0, "pending": 0, "ignore": 0}
        for d in decisions:
            out[d.decision] = out.get(d.decision, 0) + 1
        return out
