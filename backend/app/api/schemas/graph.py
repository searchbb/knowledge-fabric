"""Graph DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphNodeSchema(BaseModel):
    uuid: str
    name: str
    labels: list[str] = Field(default_factory=list)
    summary: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeSchema(BaseModel):
    uuid: str = ""
    source_node_uuid: str
    target_node_uuid: str
    name: str = ""
    fact_type: str = ""
    fact: str = ""


class GraphStatsSchema(BaseModel):
    graph_id: str = ""
    node_count: int = 0
    edge_count: int = 0
