"""Theme DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ThemeSummarySchema(BaseModel):
    theme_id: str
    title: str
    description: str = ""


class ThemeViewSchema(BaseModel):
    theme: ThemeSummarySchema
    concepts: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)


class ThemeBackboneStageSchema(BaseModel):
    title: str = ""
    summary: str = ""


class ProjectThemeMetaSchema(BaseModel):
    projectId: str
    projectName: str = ""
    graphId: str | None = None
    phase1Status: str = "unknown"
    viewVersion: str = "theme-candidates-v1"
    generatedFrom: list[str] = Field(default_factory=list)
    generatedAt: str = ""


class ProjectThemeOverviewSchema(BaseModel):
    summaryText: str = ""
    candidateCount: int = 0
    confirmedCount: int = 0
    dismissedCount: int = 0
    nodeCount: int = 0
    edgeCount: int = 0
    readingGroupCount: int = 0
    uncoveredNodesCount: int = 0


class ProjectThemeBackboneSchema(BaseModel):
    title: str = ""
    summary: str = ""
    problem: ThemeBackboneStageSchema = Field(default_factory=ThemeBackboneStageSchema)
    solution: ThemeBackboneStageSchema = Field(default_factory=ThemeBackboneStageSchema)
    architecture: ThemeBackboneStageSchema = Field(default_factory=ThemeBackboneStageSchema)
    articleSections: list[str] = Field(default_factory=list)


class ThemeCandidateEvidenceSchema(BaseModel):
    nodeCount: int = 0
    edgeCount: int = 0
    readingGroupRefs: list[str] = Field(default_factory=list)
    topLabels: list[str] = Field(default_factory=list)
    sampleNodes: list[str] = Field(default_factory=list)


class ThemeCandidateSchema(BaseModel):
    candidateKey: str
    title: str
    kind: str = "reading_group"
    summary: str = ""
    supportSignals: list[str] = Field(default_factory=list)
    evidence: ThemeCandidateEvidenceSchema = Field(default_factory=ThemeCandidateEvidenceSchema)
    sourceRefs: list[str] = Field(default_factory=list)
    status: str = "unreviewed"
    note: str = ""
    decisionUpdatedAt: str | None = None


class ProjectThemeDiagnosticsSchema(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    emptyReason: str = ""
    dataCompleteness: str = "empty"
    unassignedReadingGroups: list[str] = Field(default_factory=list)
    unassignedLabels: list[str] = Field(default_factory=list)
    uncoveredNodesCount: int = 0


class ThemeClusterSchema(BaseModel):
    id: str
    name: str
    status: str = "active"
    summary: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    snippet_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_theme_keys: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ProjectThemeViewSchema(BaseModel):
    meta: ProjectThemeMetaSchema
    themeDecisionsVersion: int = 0
    overview: ProjectThemeOverviewSchema
    backbone: ProjectThemeBackboneSchema = Field(default_factory=ProjectThemeBackboneSchema)
    themeCandidates: list[ThemeCandidateSchema] = Field(default_factory=list)
    diagnostics: ProjectThemeDiagnosticsSchema = Field(default_factory=ProjectThemeDiagnosticsSchema)
    limitations: list[str] = Field(default_factory=list)
    clusters: list[ThemeClusterSchema] = Field(default_factory=list)
