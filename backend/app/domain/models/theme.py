"""Theme models for the Phase 2 scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Theme:
    theme_id: str
    title: str
    description: str = ""
    concept_ids: list[str] = field(default_factory=list)
