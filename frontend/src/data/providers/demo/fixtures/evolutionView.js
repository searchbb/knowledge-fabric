// Demo evolution-view fixture.
//
// Shape matches /api/evolution/projects/{projectId}/view :
//   { meta, projectOverview, knowledgeAssetSnapshot,
//     traceabilityAndSignalQuality, nextCapabilitiesGap, diagnostics }
//
// Per-project. Each project shows realistic completeness signals.

import {
  PROJECT_OBSERVABILITY,
  PROJECT_AGENTIC,
  PROJECT_RETRIEVAL,
} from './entities'

function makeFixture({ projectId, projectName, graphId, nodeCount, edgeCount, hasReadingStructure, hasAnalysisSummary, capabilityGap }) {
  return {
    success: true,
    data: {
      meta: {
        projectId,
        projectName,
        graphId,
        phase1Status: 'completed',
        viewVersion: 'evolution-snapshot-v1',
        generatedFrom: ['analysis_summary', 'reading_structure', 'graph_data'],
        generatedAt: '2026-04-12T07:00:00Z',
      },
      projectOverview: {
        createdAt: '2026-03-28T10:00:00Z',
        updatedAt: '2026-04-10T16:30:00Z',
        hasGraph: true,
        graphNodeCount: nodeCount,
        graphEdgeCount: edgeCount,
        hasReadingStructure,
        hasAnalysisSummary,
      },
      knowledgeAssetSnapshot: {
        readingStructureStatus: hasReadingStructure ? 'available' : 'missing',
        analysisSummaryStatus: hasAnalysisSummary ? 'available' : 'missing',
        graphStatus: 'available',
        availableViews: ['article', 'concepts', 'themes', 'review'],
        evidenceCounts: {
          nodes: nodeCount,
          edges: edgeCount,
          readingGroupsCount: hasReadingStructure ? 3 : 0,
          warningsCount: 0,
        },
      },
      traceabilityAndSignalQuality: {
        supportsTimeOrdering: 'partial',
        timeSignals: {
          projectCreatedAt: '2026-03-28T10:00:00Z',
          projectUpdatedAt: '2026-04-10T16:30:00Z',
          nodeCreatedAtCoverage: 'partial',
          edgeCreatedAtCoverage: 'partial',
        },
        derivationNotes: [
          '当前 demo 数据来自本地 fixture，时间戳为示意，便于演示演化视图。',
        ],
        confidenceFlags: {
          historicalSeriesAvailable: false,
          nodeTimestampConsistency: 'partial',
          crossProjectComparisonSupported: true,
        },
      },
      nextCapabilitiesGap: {
        missingCapabilities: capabilityGap,
        recommendedNextStep: capabilityGap[0] || '等待积累更多文章后再生成跨项目演化对比。',
        readinessLevel: capabilityGap.length ? 'snapshot_only' : 'production_ready',
      },
      diagnostics: {
        warnings: [],
        emptyReason: '',
        dataCompleteness: 'snapshot',
        timestampSignalAvailable: true,
      },
    },
  }
}

export const evolutionViewFixturesByProjectId = {
  [PROJECT_OBSERVABILITY]: makeFixture({
    projectId: PROJECT_OBSERVABILITY,
    projectName: '可观测性平台调研',
    graphId: 'g-demo-observability',
    nodeCount: 8,
    edgeCount: 8,
    hasReadingStructure: true,
    hasAnalysisSummary: true,
    capabilityGap: ['尚未积累跨项目历史数据，无法给出趋势对比。'],
  }),
  [PROJECT_AGENTIC]: makeFixture({
    projectId: PROJECT_AGENTIC,
    projectName: 'Agentic Workflows 设计笔记',
    graphId: 'g-demo-agentic',
    nodeCount: 7,
    edgeCount: 7,
    hasReadingStructure: true,
    hasAnalysisSummary: true,
    capabilityGap: ['尚未与历史 agentic 项目对比，待补充。'],
  }),
  [PROJECT_RETRIEVAL]: makeFixture({
    projectId: PROJECT_RETRIEVAL,
    projectName: '检索增强生成基准对比',
    graphId: 'g-demo-retrieval',
    nodeCount: 3,
    edgeCount: 2,
    hasReadingStructure: false,
    hasAnalysisSummary: true,
    capabilityGap: ['当前项目仍在构建中，演化视图为初始快照。'],
  }),
}
