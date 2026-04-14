"""Local concept models for the Phase 2 scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LocalConcept:
    concept_id: str
    document_id: str
    name: str
    concept_type: str
    evidence_spans: list[str] = field(default_factory=list)
    candidate_entity_ids: list[str] = field(default_factory=list)
