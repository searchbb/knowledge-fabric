"""Review DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewEvidenceSchema(BaseModel):
    label: str
    value: str


class ReviewSnippetSchema(BaseModel):
    id: str
    heading: str
    text: str
    matchedTerms: list[str] = Field(default_factory=list)


class ReviewCandidateSchema(BaseModel):
    projectId: str | None = None
    name: str | None = None
    status: str | None = None
    summary: str = ""
    matchedTerms: list[str] = Field(default_factory=list)
    reason: str = ""


class ReviewSubgraphNodeSchema(BaseModel):
    id: str | None = None
    name: str | None = None
    label: str = "Node"
    isFocus: bool = False


class ReviewSubgraphEdgeSchema(BaseModel):
    id: str | None = None
    source: str | None = None
    target: str | None = None
    label: str = "RELATED"
    fact: str = ""


class ReviewSubgraphSchema(BaseModel):
    caption: str = ""
    focusTerms: list[str] = Field(default_factory=list)
    nodes: list[ReviewSubgraphNodeSchema] = Field(default_factory=list)
    edges: list[ReviewSubgraphEdgeSchema] = Field(default_factory=list)


class ReviewTaskSchema(BaseModel):
    review_id: str
    task_type: str
    status: str
    title: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)


class ReviewTaskViewSchema(BaseModel):
    id: str
    title: str
    kind: str
    kindLabel: str = ""
    severity: str = "medium"
    severityLabel: str = ""
    status: str = "pending"
    statusLabel: str = ""
    summary: str = ""
    sourceLabel: str = ""
    confidenceLabel: str = ""
    documentLabel: str = ""
    rationale: str = ""
    evidence: list[ReviewEvidenceSchema] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    sourceSnippets: list[ReviewSnippetSchema] = Field(default_factory=list)
    subgraph: ReviewSubgraphSchema = Field(default_factory=ReviewSubgraphSchema)
    crossArticleCandidates: list[ReviewCandidateSchema] = Field(default_factory=list)
    focusTerms: list[str] = Field(default_factory=list)
    note: str = ""
    manualNote: str = ""
    assistantPreview: str = ""
    lastDecisionLabel: str = ""
    decisionUpdatedAt: str | None = None
    decisionUpdatedBy: str | None = None


class ReviewSummarySchema(BaseModel):
    totalCount: int = 0
    pendingCount: int = 0
    approvedCount: int = 0
    questionedCount: int = 0
    ignoredCount: int = 0
    highPriorityCount: int = 0
    warningCount: int = 0
    graphNodeCount: int = 0
    graphEdgeCount: int = 0
    articleTextAvailable: bool = False
    relatedProjectCount: int = 0


class ReviewPhase1SignalsSchema(BaseModel):
    provider: str = "unknown"
    build_outcome: dict[str, Any] = Field(default_factory=dict)
    reading_structure_status: dict[str, Any] = Field(default_factory=dict)


class ReviewViewSchema(BaseModel):
    project: dict[str, Any] = Field(default_factory=dict)
    prototypeMode: bool = True
    reviewDecisionsVersion: int = 0
    summary: ReviewSummarySchema = Field(default_factory=ReviewSummarySchema)
    phase1Signals: ReviewPhase1SignalsSchema = Field(default_factory=ReviewPhase1SignalsSchema)
    items: list[ReviewTaskViewSchema] = Field(default_factory=list)
