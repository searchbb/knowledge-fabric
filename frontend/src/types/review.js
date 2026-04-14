export const REVIEW_FILTERS = [
  { key: 'all', label: '全部任务' },
  { key: 'pending', label: '待处理' },
  { key: 'high', label: '高优先级' },
  { key: 'done', label: '已标记' },
]

export const REVIEW_DECISIONS = [
  { key: 'approve', label: '通过', status: 'approved', tone: 'primary' },
  { key: 'question', label: '存疑', status: 'questioned', tone: 'secondary' },
  { key: 'ignore', label: '忽略', status: 'ignored', tone: 'ghost' },
]

const REVIEW_KIND_META = {
  warning: { label: '构建告警' },
  concept: { label: '概念归一' },
  relation: { label: '关系确认' },
  theme: { label: '主题归属' },
}

const REVIEW_SEVERITY_META = {
  high: { label: '高风险' },
  medium: { label: '中风险' },
  low: { label: '低风险' },
}

const REVIEW_STATUS_META = {
  pending: { label: '未处理' },
  approved: { label: '已通过' },
  questioned: { label: '已标记存疑' },
  ignored: { label: '已忽略' },
}

export function createEmptyReviewTaskViewModel() {
  return {
    id: '',
    title: '',
    kind: 'warning',
    kindLabel: REVIEW_KIND_META.warning.label,
    severity: 'medium',
    severityLabel: REVIEW_SEVERITY_META.medium.label,
    status: 'pending',
    statusLabel: REVIEW_STATUS_META.pending.label,
    summary: '',
    sourceLabel: '',
    confidenceLabel: '',
    documentLabel: '',
    rationale: '',
    evidence: [],
    suggestions: [],
    sourceSnippets: [],
    subgraph: {
      nodes: [],
      edges: [],
      caption: '',
    },
    crossArticleCandidates: [],
    focusTerms: [],
    manualNote: '',
    assistantPreview: '',
    actions: REVIEW_DECISIONS,
    lastDecisionLabel: '',
  }
}

export function decorateReviewTask(task) {
  const kind = REVIEW_KIND_META[task.kind] || REVIEW_KIND_META.warning
  const severity = REVIEW_SEVERITY_META[task.severity] || REVIEW_SEVERITY_META.medium
  const status = REVIEW_STATUS_META[task.status] || REVIEW_STATUS_META.pending

  return {
    ...task,
    kindLabel: kind.label,
    severityLabel: severity.label,
    statusLabel: status.label,
    actions: task.actions?.length ? task.actions : REVIEW_DECISIONS,
  }
}

export function matchesReviewFilter(task, filterKey) {
  if (filterKey === 'pending') return task.status === 'pending'
  if (filterKey === 'high') return task.severity === 'high'
  if (filterKey === 'done') return task.status !== 'pending'
  return true
}

function buildWarningTask({ warning, index, project, graphData, phase1TaskResult }) {
  const fallbackApplied = Boolean(phase1TaskResult?.diagnostics?.fallback_graph_applied)
  const graphNodeCount = graphData?.node_count ?? graphData?.nodes?.length ?? 0
  const graphEdgeCount = graphData?.edge_count ?? graphData?.edges?.length ?? 0

  return decorateReviewTask({
    id: `warning-${index + 1}`,
    title: `核对构建告警 #${index + 1}`,
    kind: 'warning',
    severity: fallbackApplied || index === 0 ? 'high' : 'medium',
    status: 'pending',
    summary: warning,
    sourceLabel: '来自 Phase 1 build_outcome.warnings',
    confidenceLabel: fallbackApplied ? '优先级上调' : '人工确认',
    documentLabel: project?.name || '当前文章',
    rationale: '先把系统认为不稳定的单篇信号收进 review 队列，再决定哪些需要升级成真实 ReviewTask。',
    evidence: [
      {
        label: '原始 warning',
        value: warning,
      },
      {
        label: '构建状态',
        value: phase1TaskResult?.build_outcome?.status || 'unknown',
      },
      {
        label: '阅读骨架状态',
        value: phase1TaskResult?.reading_structure_status?.status || 'unknown',
      },
      {
        label: '图谱快照',
        value: `${graphNodeCount} 节点 / ${graphEdgeCount} 关系`,
      },
    ],
    suggestions: [
      '如果这个 warning 会影响 canonical/theme 判断，应升级为真实人工任务。',
      '如果只是一次性抽取噪声，后续可以在规则层直接消化，不必进入长期队列。',
    ],
  })
}

function buildConceptTask({ project, graphData, phase1TaskResult }) {
  const graphNodeCount = graphData?.node_count ?? graphData?.nodes?.length ?? 0

  return decorateReviewTask({
    id: 'concept-alignment',
    title: '归一本篇核心概念到 canonical',
    kind: 'concept',
    severity: graphNodeCount > 6 ? 'high' : 'medium',
    status: 'pending',
    summary: '用当前文章的局部图谱预演 local concept -> canonical 的人工确认入口，不提前绑定真实归一算法。',
    sourceLabel: '来自图谱节点快照与阅读骨架',
    confidenceLabel: '原型候选',
    documentLabel: project?.name || '当前文章',
    rationale: 'Phase 2 的核心不是继续堆单篇抽取，而是让局部概念进入可确认、可写回的全局治理链路。',
    evidence: [
      {
        label: '单篇图谱节点',
        value: `${graphNodeCount} 个节点`,
      },
      {
        label: '阅读骨架标题',
        value: project?.reading_structure?.title || '暂无',
      },
      {
        label: 'Provider',
        value: phase1TaskResult?.provider || 'unknown',
      },
      {
        label: '系统判断理由',
        value: '如果当前文章里出现高频或桥接概念，后续应进入 canonical entity 对齐与人工确认流程。',
      },
    ],
    suggestions: [
      '将高频局部概念合并到已有 canonical。',
      '没有可靠候选时，为它建立新的 canonical 种子。',
    ],
  })
}

function buildRelationTask({ project, graphData, phase1TaskResult }) {
  const graphEdgeCount = graphData?.edge_count ?? graphData?.edges?.length ?? 0
  const processed = phase1TaskResult?.diagnostics?.processed_chunk_count || 0
  const total = phase1TaskResult?.diagnostics?.chunk_count || 0

  return decorateReviewTask({
    id: 'relation-check',
    title: '确认关系建议是否值得人工复核',
    kind: 'relation',
    severity: graphEdgeCount > 8 ? 'high' : 'medium',
    status: 'pending',
    summary: '关系确认型任务需要在 review 页中占一个明确位置，否则后续很容易重新堆回 Phase 1 调试页。',
    sourceLabel: '来自关系数量与 chunk 处理诊断',
    confidenceLabel: total ? `${processed}/${total} chunks` : '待确认',
    documentLabel: project?.name || '当前文章',
    rationale: '关系修正和概念归一不同，应该在同一个 review 心智模型里有自己的任务类型，而不是塞进日志或 warning 文案。',
    evidence: [
      {
        label: '单篇关系数',
        value: `${graphEdgeCount} 条`,
      },
      {
        label: 'chunk 处理进度',
        value: total ? `${processed}/${total}` : '暂无',
      },
      {
        label: 'Fallback 图谱',
        value: phase1TaskResult?.diagnostics?.fallback_graph_applied ? '已触发' : '未触发',
      },
      {
        label: '系统判断理由',
        value: '如果关系抽取存在噪声，review 视图应让人直接看到证据并决定是通过、存疑还是忽略。',
      },
    ],
    suggestions: [
      '把低置信关系放进待确认队列，而不是直接写入全局图。',
      '对高价值桥接关系保留人工确认入口。',
    ],
  })
}

function buildThemeTask({ project, phase1TaskResult }) {
  const warnings = phase1TaskResult?.build_outcome?.warnings || []

  return decorateReviewTask({
    id: 'theme-assignment',
    title: '确认主题归属是否成立',
    kind: 'theme',
    severity: warnings.length ? 'medium' : 'low',
    status: 'pending',
    summary: '用阅读骨架和分析摘要预演 theme / cluster 的人工治理入口，验证 review 页是否足以承载主题归属判断。',
    sourceLabel: '来自阅读骨架与分析摘要',
    confidenceLabel: warnings.length ? '需要人工看证据' : '候选稳定',
    documentLabel: project?.name || '当前文章',
    rationale: '主题判断通常跨多篇文章演化，先把这个任务类型放进 prototype，后续接真实 theme 聚类结果时不必重做信息架构。',
    evidence: [
      {
        label: '阅读骨架标题',
        value: project?.reading_structure?.title || '暂无',
      },
      {
        label: '分析摘要',
        value: project?.analysis_summary || '当前项目尚未记录分析摘要。',
      },
      {
        label: '当前 warning 数',
        value: `${warnings.length}`,
      },
      {
        label: '系统判断理由',
        value: '主题归属不是图渲染附带信息，而是需要独立校验、可写回和可追踪的治理动作。',
      },
    ],
    suggestions: [
      '保留 theme 作为工作台一级对象，不要继续塞回文章页。',
      '主题归属低置信时进入人工校验，而不是直接自动聚类定稿。',
    ],
  })
}

export function createPrototypeReviewTasks({ project, graphData, phase1TaskResult }) {
  const warnings = phase1TaskResult?.build_outcome?.warnings || []
  const warningTasks = warnings.slice(0, 2).map((warning, index) =>
    buildWarningTask({ warning, index, project, graphData, phase1TaskResult }),
  )

  const tasks = [
    ...warningTasks,
    buildConceptTask({ project, graphData, phase1TaskResult }),
    buildRelationTask({ project, graphData, phase1TaskResult }),
    buildThemeTask({ project, phase1TaskResult }),
  ]

  return tasks.length ? tasks : [decorateReviewTask(createEmptyReviewTaskViewModel())]
}
