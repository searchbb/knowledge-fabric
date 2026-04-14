"""Concept DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConceptSummarySchema(BaseModel):
    canonical_id: str
    title: str
    concept_type: str
    confidence: float | None = None


class ConceptViewSchema(BaseModel):
    concept: ConceptSummarySchema
    aliases: list[str] = Field(default_factory=list)
    mentions: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)


class ConceptTypeCountSchema(BaseModel):
    type: str
    count: int = 0


class ConceptCandidateSchema(BaseModel):
    key: str
    displayName: str
    conceptType: str
    mentionCount: int = 0
    connectedCount: int = 0
    sampleEvidence: list[str] = Field(default_factory=list)
    sourceNodeIds: list[str] = Field(default_factory=list)
    status: str = "unreviewed"
    note: str = ""
    canonicalName: str = ""
    mergeTo: str = ""
    resolvedMergeTo: str = ""
    aliases: list[str] = Field(default_factory=list)
    decisionUpdatedAt: str | None = None


class ProjectConceptMetaSchema(BaseModel):
    projectId: str
    projectName: str = ""
    graphId: str | None = None
    phase1Status: str = "unknown"
    sourceScope: str = "project_graph"
    generatedAt: str = ""


class ProjectConceptSummarySchema(BaseModel):
    nodeCount: int = 0
    edgeCount: int = 0
    typedNodeCount: int = 0
    candidateConceptCount: int = 0
    acceptedCount: int = 0
    rejectedCount: int = 0
    mergedCount: int = 0
    canonicalCount: int = 0
    unreviewedCount: int = 0
    relationCount: int = 0
    warningsCount: int = 0


class ProjectConceptDiagnosticsSchema(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    emptyReason: str = ""
    dataCompleteness: str = "empty"
    typeCounts: list[ConceptTypeCountSchema] = Field(default_factory=list)


class ProjectConceptViewSchema(BaseModel):
    meta: ProjectConceptMetaSchema
    conceptDecisionsVersion: int = 0
    summary: ProjectConceptSummarySchema
    candidateConcepts: list[ConceptCandidateSchema] = Field(default_factory=list)
    diagnostics: ProjectConceptDiagnosticsSchema = Field(default_factory=ProjectConceptDiagnosticsSchema)
