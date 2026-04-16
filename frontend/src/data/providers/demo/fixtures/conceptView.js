// Demo concept-view fixture.
//
// Shape matches /api/concept/projects/{projectId}/view :
//   { meta, summary, candidateConcepts: [...], diagnostics }
//
// Candidates are derived from the workspace graph nodes so the demo
// concept page is consistent with what users see in article view.

import {
  PROJECT_OBSERVABILITY,
  PROJECT_AGENTIC,
  PROJECT_RETRIEVAL,
} from './entities'

function meta(projectId, projectName, graphId) {
  return {
    projectId,
    projectName,
    graphId,
    phase1Status: 'completed',
    sourceScope: 'project_graph',
    generatedAt: '2026-04-12T06:30:00Z',
  }
}

function summary(nodes, edges, candidates) {
  return {
    nodeCount: nodes,
    edgeCount: edges,
    typedNodeCount: candidates,
    candidateConceptCount: candidates,
    relationCount: edges,
    warningsCount: 0,
  }
}

function diagnostics(typeCounts) {
  return {
    warnings: [],
    emptyReason: '',
    dataCompleteness: 'complete',
    typeCounts,
  }
}

function candidate(key, displayName, conceptType, mentionCount, connectedCount, status = 'unreviewed') {
  return {
    key,
    displayName,
    conceptType,
    mentionCount,
    connectedCount,
    sampleEvidence: [
      { snippet: `示例证据：${displayName} 在文章中出现，作为 ${conceptType} 节点参与图谱构建。`, sourceNodeId: key },
    ],
    sourceNodeIds: [key],
    status,
    canonicalName: status === 'canonical' ? displayName : '',
    note: '',
  }
}

export const conceptViewFixturesByProjectId = {
  [PROJECT_OBSERVABILITY]: {
    success: true,
    data: {
      meta: meta(PROJECT_OBSERVABILITY, '可观测性平台调研', 'g-demo-observability'),
      summary: summary(8, 8, 6),
      candidateConcepts: [
        candidate('n-otel', 'OpenTelemetry', 'Technology', 12, 4, 'canonical'),
        candidate('n-prometheus', 'Prometheus', 'Technology', 9, 3, 'canonical'),
        candidate('n-traces', '调用链追踪', 'Layer', 15, 5, 'canonical'),
        candidate('n-metrics', '指标采集', 'Layer', 11, 3, 'canonical'),
        candidate('n-cardinality', '高基数维度', 'Problem', 6, 2),
        candidate('n-clickhouse', 'ClickHouse', 'Technology', 4, 2),
      ],
      diagnostics: diagnostics([
        { type: 'Technology', count: 3 },
        { type: 'Layer', count: 2 },
        { type: 'Problem', count: 1 },
      ]),
    },
  },
  [PROJECT_AGENTIC]: {
    success: true,
    data: {
      meta: meta(PROJECT_AGENTIC, 'Agentic Workflows 设计笔记', 'g-demo-agentic'),
      summary: summary(7, 7, 5),
      candidateConcepts: [
        candidate('n-planner', '规划-执行分离', 'Pattern', 14, 6, 'canonical'),
        candidate('n-toolcall', '工具调用', 'Mechanism', 10, 4, 'canonical'),
        candidate('n-memory', '上下文记忆', 'Mechanism', 8, 3),
        candidate('n-eval', '评估反馈闭环', 'Pattern', 9, 4, 'canonical'),
        candidate('n-drift', '长任务漂移', 'Problem', 5, 2),
      ],
      diagnostics: diagnostics([
        { type: 'Pattern', count: 2 },
        { type: 'Mechanism', count: 2 },
        { type: 'Problem', count: 1 },
      ]),
    },
  },
  [PROJECT_RETRIEVAL]: {
    success: true,
    data: {
      meta: meta(PROJECT_RETRIEVAL, '检索增强生成基准对比', 'g-demo-retrieval'),
      summary: summary(3, 2, 2),
      candidateConcepts: [
        candidate('n-recall', '召回率', 'Metric', 6, 1),
        candidate('n-latency', '端到端时延', 'Metric', 8, 1),
      ],
      diagnostics: diagnostics([
        { type: 'Metric', count: 2 },
      ]),
    },
  },
}
