"""Pydantic schemas for the global review task queue (Stage L)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewTaskSchema(BaseModel):
    task_id: str
    entity_type: str
    entity_id: str
    entity_name: str = ""
    action_required: str = "custom"
    status: str = "open"
    priority: str = "normal"
    project_id: str = ""
    note: str = ""
    resolution: str = ""
    created_at: str = ""
    updated_at: str = ""
    resolved_at: str = ""


class ReviewTaskListSchema(BaseModel):
    tasks: list[ReviewTaskSchema] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 100


class BatchResolveResultSchema(BaseModel):
    resolved: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    resolved_count: int = 0
    skipped_count: int = 0


class ReviewStatsSchema(BaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_entity_type: dict[str, int] = Field(default_factory=dict)
