export function createEmptyEvolutionViewModel() {
  return {
    meta: {
      projectId: '',
      projectName: '',
      graphId: null,
      phase1Status: 'unknown',
      viewVersion: 'evolution-snapshot-v1',
      generatedFrom: [],
      generatedAt: '',
    },
    projectOverview: {
      createdAt: '',
      updatedAt: '',
      hasGraph: false,
      graphNodeCount: 0,
      graphEdgeCount: 0,
      hasReadingStructure: false,
      hasAnalysisSummary: false,
    },
    knowledgeAssetSnapshot: {
      readingStructureStatus: 'missing',
      analysisSummaryStatus: 'missing',
      graphStatus: 'missing',
      availableViews: [],
      evidenceCounts: {
        nodes: 0,
        edges: 0,
        readingGroupsCount: 0,
        warningsCount: 0,
      },
    },
    traceabilityAndSignalQuality: {
      supportsTimeOrdering: 'limited',
      timeSignals: {
        projectCreatedAt: '',
        projectUpdatedAt: '',
        nodeCreatedAtCoverage: 'unknown',
        edgeCreatedAtCoverage: 'unknown',
      },
      derivationNotes: [],
      confidenceFlags: {
        historicalSeriesAvailable: false,
        nodeTimestampConsistency: 'unknown',
        crossProjectComparisonSupported: false,
      },
    },
    nextCapabilitiesGap: {
      missingCapabilities: [],
      recommendedNextStep: '',
      readinessLevel: 'snapshot_only',
    },
    diagnostics: {
      warnings: [],
      emptyReason: '',
      dataCompleteness: 'empty',
      timestampSignalAvailable: false,
    },
  }
}
