"""Article-facing DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .graph import GraphStatsSchema


class ArticleSummarySchema(BaseModel):
    project_id: str
    name: str
    status: str
    graph_id: str | None = None


class ArticleViewSchema(BaseModel):
    article: ArticleSummarySchema
    graph: GraphStatsSchema | None = None
    reading_structure: dict[str, Any] = Field(default_factory=dict)
    analysis_summary: str = ""
