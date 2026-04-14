"""Review task models for the Phase 2 scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ReviewTask:
    review_id: str
    review_type: str
    status: str
    title: str
    evidence_ids: list[str] = field(default_factory=list)
    suggestion_ids: list[str] = field(default_factory=list)
