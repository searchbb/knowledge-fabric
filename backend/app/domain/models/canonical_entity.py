"""Canonical entity models for the Phase 2 scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CanonicalEntity:
    entity_id: str
    title: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    source_concept_ids: list[str] = field(default_factory=list)
