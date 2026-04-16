// Demo review-view fixture.
//
// Shape matches /api/review/projects/{projectId}/view :
//   { summary, items: [...task], prototypeMode, phase1Signals,
//     articleTextAvailable, relatedProjectCount }
//
// Each item shape mirrors what decorateReviewTask() in src/types/review.js
// expects (id, title, kind, severity, status, summary, evidence, ...).

import {
  PROJECT_OBSERVABILITY,
  PROJECT_AGENTIC,
  PROJECT_RETRIEVAL,
} from './entities'

function task({ id, title, kind, severity, status, summary, evidence = [], suggestions = [] }) {
  return {
    id,
    title,
    kind,
    severity,
    status,
    summary,
    sourceLabel: 'demo fixture',
    confidenceLabel: '示例',
    documentLabel: title,
    rationale:
      '该 review 任务来自 demo fixture，演示工作台对该项目可用的人工治理入口形态。',
    evidence,
    suggestions,
    sourceSnippets: [],
    subgraph: { nodes: [], edges: [], caption: '' },
    crossArticleCandidates: [],
    focusTerms: [],
    manualNote: '',
  }
}

function viewWithItems({ pendingCount, totalCount, items }) {
  return {
    success: true,
    data: {
      summary: {
        totalCount,
        pendingCount,
        articleTextAvailable: true,
        relatedProjectCount: 2,
      },
      items,
      prototypeMode: false,
      phase1Signals: {
        warningsCount: 0,
        chunkCount: 12,
        processedChunkCount: 12,
      },
      articleTextAvailable: true,
      relatedProjectCount: 2,
    },
  }
}

export const reviewViewFixturesByProjectId = {
  [PROJECT_OBSERVABILITY]: viewWithItems({
    totalCount: 2,
    pendingCount: 2,
    items: [
      task({
        id: 'review-observ-cardinality',
        title: '高基数维度合并到 canonical',
        kind: 'concept',
        severity: 'high',
        status: 'pending',
        summary: '本项目「高基数维度」节点是否归并到全局 canonical 概念，需要人工确认。',
        evidence: [
          { label: '本地节点', value: '高基数维度 (Problem)' },
          { label: '候选 canonical', value: 'reg-cardinality（全局已有）' },
          { label: '出现次数', value: '6' },
        ],
        suggestions: ['确认归并到 reg-cardinality；如有冲突可创建新的 canonical 种子。'],
      }),
      task({
        id: 'review-observ-otel-impl',
        title: '确认 OpenTelemetry → 调用链追踪 关系',
        kind: 'relation',
        severity: 'medium',
        status: 'pending',
        summary: '是否承认这条 implements 类型跨项目关系。',
        evidence: [
          { label: '关系类型', value: 'implements (置信 0.92)' },
          { label: '来源', value: 'LLM 自动发现' },
        ],
        suggestions: ['通过：纳入全局图谱；存疑：保留待进一步证据。'],
      }),
    ],
  }),
  [PROJECT_AGENTIC]: viewWithItems({
    totalCount: 2,
    pendingCount: 1,
    items: [
      task({
        id: 'review-agentic-eval-loop-theme',
        title: '将「评估反馈闭环」纳入主题「Agentic 可靠性模式」',
        kind: 'theme',
        severity: 'medium',
        status: 'pending',
        summary: '主题归属候选，需要人工确认是否成立。',
        evidence: [
          { label: '建议主题', value: 'Agentic 可靠性模式' },
          { label: '已有成员', value: '工具调用 / 上下文记忆 / 长任务漂移' },
        ],
        suggestions: ['通过：写入 theme 成员；忽略：保留为单独节点。'],
      }),
      task({
        id: 'review-agentic-drift-warning',
        title: '核对长任务漂移高风险标记',
        kind: 'warning',
        severity: 'high',
        status: 'approved',
        summary: '已被人工通过，作为 demo 中"已处理"任务的示例。',
        evidence: [{ label: '处理时间', value: '2026-04-11 15:22' }],
      }),
    ],
  }),
  [PROJECT_RETRIEVAL]: viewWithItems({
    totalCount: 1,
    pendingCount: 1,
    items: [
      task({
        id: 'review-retrieval-build-warning',
        title: '当前项目仍在构建，请确认是否继续等待',
        kind: 'warning',
        severity: 'low',
        status: 'pending',
        summary: '示例项目处于 building 状态，review 队列里只有一条系统提示。',
        evidence: [{ label: '项目状态', value: 'building' }],
      }),
    ],
  }),
}
