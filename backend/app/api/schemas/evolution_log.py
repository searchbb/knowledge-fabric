"""Pydantic schemas for the global evolution log (Stage K)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvolutionEventSchema(BaseModel):
    event_id: str
    event_type: str
    entity_type: str
    entity_id: str
    entity_name: str = ""
    project_id: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""
    # Audit fields (added 2026-04-11 for the auto URL pipeline MVP).
    # Pre-existing events get the ``human`` defaults at read time.
    actor_type: str = "human"
    actor_id: str = ""
    run_id: str = ""
    source: str = "workspace_ui"


class EvolutionFeedSchema(BaseModel):
    events: list[EvolutionEventSchema] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class EntityTimelineSchema(BaseModel):
    entity_type: str
    entity_id: str
    events: list[EvolutionEventSchema] = Field(default_factory=list)
    total: int = 0


class ProjectFeedSchema(BaseModel):
    project_id: str
    events: list[EvolutionEventSchema] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50
