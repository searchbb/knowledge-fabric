"""Evolution DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectEvolutionMetaSchema(BaseModel):
    projectId: str
    projectName: str = ""
    graphId: str | None = None
    phase1Status: str = "unknown"
    viewVersion: str = "evolution-snapshot-v1"
    generatedFrom: list[str] = Field(default_factory=list)
    generatedAt: str = ""


class ProjectEvolutionOverviewSchema(BaseModel):
    createdAt: str = ""
    updatedAt: str = ""
    hasGraph: bool = False
    graphNodeCount: int = 0
    graphEdgeCount: int = 0
    hasReadingStructure: bool = False
    hasAnalysisSummary: bool = False


class EvolutionEvidenceCountsSchema(BaseModel):
    nodes: int = 0
    edges: int = 0
    readingGroupsCount: int = 0
    warningsCount: int = 0


class ProjectEvolutionAssetSnapshotSchema(BaseModel):
    readingStructureStatus: str = "missing"
    analysisSummaryStatus: str = "missing"
    graphStatus: str = "missing"
    availableViews: list[str] = Field(default_factory=list)
    evidenceCounts: EvolutionEvidenceCountsSchema = Field(default_factory=EvolutionEvidenceCountsSchema)


class EvolutionTimeSignalsSchema(BaseModel):
    projectCreatedAt: str = ""
    projectUpdatedAt: str = ""
    nodeCreatedAtCoverage: str = "unknown"
    edgeCreatedAtCoverage: str = "unknown"


class EvolutionConfidenceFlagsSchema(BaseModel):
    historicalSeriesAvailable: bool = False
    nodeTimestampConsistency: str = "unknown"
    crossProjectComparisonSupported: bool = False


class ProjectEvolutionSignalQualitySchema(BaseModel):
    supportsTimeOrdering: str = "limited"
    timeSignals: EvolutionTimeSignalsSchema = Field(default_factory=EvolutionTimeSignalsSchema)
    derivationNotes: list[str] = Field(default_factory=list)
    confidenceFlags: EvolutionConfidenceFlagsSchema = Field(default_factory=EvolutionConfidenceFlagsSchema)


class ProjectEvolutionCapabilityGapSchema(BaseModel):
    missingCapabilities: list[str] = Field(default_factory=list)
    recommendedNextStep: str = ""
    readinessLevel: str = "snapshot_only"


class ProjectEvolutionDiagnosticsSchema(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    emptyReason: str = ""
    dataCompleteness: str = "empty"
    timestampSignalAvailable: bool = False


class ProjectEvolutionViewSchema(BaseModel):
    meta: ProjectEvolutionMetaSchema
    projectOverview: ProjectEvolutionOverviewSchema
    knowledgeAssetSnapshot: ProjectEvolutionAssetSnapshotSchema
    traceabilityAndSignalQuality: ProjectEvolutionSignalQualitySchema
    nextCapabilitiesGap: ProjectEvolutionCapabilityGapSchema
    diagnostics: ProjectEvolutionDiagnosticsSchema = Field(default_factory=ProjectEvolutionDiagnosticsSchema)
