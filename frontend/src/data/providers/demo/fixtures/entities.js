// Canonical demo entities shared across registry / theme / relation
// fixtures so cross-references are internally consistent:
//
//   - registry entries reference the demo project_ids from overview.js
//   - themes reference real registry entry_ids
//   - cross-relations reference real registry entry_ids
//
// If something's ID appears here, every other fixture uses the same ID.
// That's how the registry/theme/relation pages all agree on the same
// tiny world in demo mode.

// Project IDs — must match the overview.js fixture.
export const PROJECT_OBSERVABILITY = 'demo-observability-platform'
export const PROJECT_AGENTIC = 'demo-agentic-workflows'
export const PROJECT_RETRIEVAL = 'demo-retrieval-benchmarks'

// Registry entries — the "canonical concepts" surfaced in the global
// concept registry page. Each entry may be sourced from one or more
// projects; cross-project entries are the interesting ones (e.g. latency
// appears in both observability and retrieval).
export const registryEntries = [
  {
    entry_id: 'reg-otel',
    canonical_name: 'OpenTelemetry',
    concept_type: 'Technology',
    aliases: ['OTEL', 'OTel'],
    description: 'CNCF 下的可观测性数据采集标准，覆盖 metrics/traces/logs。',
    source_links: [
      { project_id: PROJECT_OBSERVABILITY, project_name: '可观测性平台调研', concept_key: 'n-otel' },
    ],
  },
  {
    entry_id: 'reg-prometheus',
    canonical_name: 'Prometheus',
    concept_type: 'Technology',
    aliases: ['普罗米修斯'],
    description: '时间序列数据库，常用于指标采集与告警。',
    source_links: [
      { project_id: PROJECT_OBSERVABILITY, project_name: '可观测性平台调研', concept_key: 'n-prometheus' },
    ],
  },
  {
    entry_id: 'reg-tracing',
    canonical_name: '调用链追踪',
    concept_type: 'Layer',
    aliases: ['Distributed Tracing', 'Tracing'],
    description: '跨服务的请求链路追踪能力，是可观测性的核心支柱之一。',
    source_links: [
      { project_id: PROJECT_OBSERVABILITY, project_name: '可观测性平台调研', concept_key: 'n-traces' },
    ],
  },
  {
    entry_id: 'reg-cardinality',
    canonical_name: '高基数维度',
    concept_type: 'Problem',
    aliases: ['High Cardinality'],
    description: '指标标签组合爆炸导致的存储/查询成本问题。',
    source_links: [
      { project_id: PROJECT_OBSERVABILITY, project_name: '可观测性平台调研', concept_key: 'n-cardinality' },
    ],
  },
  {
    entry_id: 'reg-tool-call',
    canonical_name: '工具调用',
    concept_type: 'Mechanism',
    aliases: ['Tool Use', 'Function Calling'],
    description: 'Agent 通过结构化工具描述调用外部函数/服务的机制。',
    source_links: [
      { project_id: PROJECT_AGENTIC, project_name: 'Agentic Workflows 设计笔记', concept_key: 'n-toolcall' },
    ],
  },
  {
    entry_id: 'reg-memory',
    canonical_name: '上下文记忆',
    concept_type: 'Mechanism',
    aliases: ['Context Memory'],
    description: '跨轮保留关键信息的工作记忆/长期记忆策略。',
    source_links: [
      { project_id: PROJECT_AGENTIC, project_name: 'Agentic Workflows 设计笔记', concept_key: 'n-memory' },
    ],
  },
  {
    entry_id: 'reg-eval-loop',
    canonical_name: '评估反馈闭环',
    concept_type: 'Pattern',
    aliases: ['Eval Loop'],
    description: '在 agentic 工作流末尾加入自动评估并把结果反馈给规划器。',
    source_links: [
      { project_id: PROJECT_AGENTIC, project_name: 'Agentic Workflows 设计笔记', concept_key: 'n-eval' },
    ],
  },
  {
    entry_id: 'reg-drift',
    canonical_name: '长任务漂移',
    concept_type: 'Problem',
    aliases: ['Goal Drift'],
    description: '长任务在多轮推理中逐渐偏离初始目标的失败模式。',
    source_links: [
      { project_id: PROJECT_AGENTIC, project_name: 'Agentic Workflows 设计笔记', concept_key: 'n-drift' },
    ],
  },
  {
    entry_id: 'reg-recall',
    canonical_name: '召回率',
    concept_type: 'Metric',
    aliases: ['Recall'],
    description: '检索系统中相关文档被召回的比例。',
    source_links: [
      { project_id: PROJECT_RETRIEVAL, project_name: '检索增强生成基准对比', concept_key: 'n-recall' },
    ],
  },
  {
    // Cross-project concept — appears in BOTH observability and retrieval.
    // This one is the most interesting entry in the registry because it
    // demonstrates alignment across projects.
    entry_id: 'reg-latency',
    canonical_name: '端到端时延',
    concept_type: 'Metric',
    aliases: ['End-to-end Latency', 'P95 延迟'],
    description: '从用户请求到最终响应的总耗时，是可观测性与 RAG 评估共同关心的指标。',
    source_links: [
      { project_id: PROJECT_RETRIEVAL, project_name: '检索增强生成基准对比', concept_key: 'n-latency' },
      { project_id: PROJECT_OBSERVABILITY, project_name: '可观测性平台调研', concept_key: 'n-observ-root' },
    ],
  },
]

// Global themes. Each membership refers to a registryEntry.entry_id
// above. `role` values mirror production: 'core' (central), 'bridge'
// (spans themes), 'peripheral' (context).
export const themes = [
  {
    theme_id: 'theme-observability',
    name: '可观测性三支柱',
    description: '围绕指标/链路/日志三层的可观测性核心概念集合。',
    keywords: ['观测性', 'metrics', 'traces', 'logs'],
    status: 'active',
    concept_memberships: [
      { entry_id: 'reg-otel', role: 'core', score: 0.95 },
      { entry_id: 'reg-tracing', role: 'core', score: 0.9 },
      { entry_id: 'reg-prometheus', role: 'core', score: 0.85 },
      { entry_id: 'reg-cardinality', role: 'peripheral', score: 0.6 },
      { entry_id: 'reg-latency', role: 'bridge', score: 0.8 },
    ],
  },
  {
    theme_id: 'theme-agentic-reliability',
    name: 'Agentic 可靠性模式',
    description: '让 agentic 工作流在长任务中保持目标一致性的模式与机制。',
    keywords: ['agent', '规划', '评估'],
    status: 'active',
    concept_memberships: [
      { entry_id: 'reg-tool-call', role: 'core', score: 0.9 },
      { entry_id: 'reg-memory', role: 'core', score: 0.85 },
      { entry_id: 'reg-eval-loop', role: 'core', score: 0.88 },
      { entry_id: 'reg-drift', role: 'peripheral', score: 0.65 },
    ],
  },
  {
    theme_id: 'theme-rag-eval',
    name: 'RAG 评估指标',
    description: '评估检索增强生成系统质量的核心指标。',
    keywords: ['RAG', 'retrieval', 'eval'],
    status: 'candidate',
    concept_memberships: [
      { entry_id: 'reg-recall', role: 'core', score: 0.9 },
      { entry_id: 'reg-latency', role: 'bridge', score: 0.75 },
    ],
  },
]

// Cross-article relations (L3) — aligned concept → concept links that
// span projects. `source_entry_id` / `target_entry_id` must be valid
// registryEntries IDs.
export const crossRelations = [
  {
    relation_id: 'rel-otel-tracing',
    source_entry_id: 'reg-otel',
    target_entry_id: 'reg-tracing',
    relation_type: 'implements',
    confidence: 0.92,
    source: 'llm',
    review_status: 'approved',
    reason: 'OpenTelemetry 是 distributed tracing 的事实标准实现。',
    created_at: '2026-04-10T09:15:00Z',
    directionality: 'directed',
  },
  {
    relation_id: 'rel-cardinality-prometheus',
    source_entry_id: 'reg-cardinality',
    target_entry_id: 'reg-prometheus',
    relation_type: 'affects',
    confidence: 0.85,
    source: 'llm',
    review_status: 'approved',
    reason: 'Prometheus 存储按 label 组合建 series，高基数直接推高内存。',
    created_at: '2026-04-10T09:20:00Z',
    directionality: 'directed',
  },
  {
    relation_id: 'rel-drift-evalloop',
    source_entry_id: 'reg-eval-loop',
    target_entry_id: 'reg-drift',
    relation_type: 'solves',
    confidence: 0.8,
    source: 'llm',
    review_status: 'pending',
    reason: '评估反馈闭环把漂移在早期检测出来并重新规划。',
    created_at: '2026-04-11T03:42:00Z',
    directionality: 'directed',
  },
  {
    relation_id: 'rel-toolcall-memory',
    source_entry_id: 'reg-tool-call',
    target_entry_id: 'reg-memory',
    relation_type: 'depends_on',
    confidence: 0.7,
    source: 'llm',
    review_status: 'pending',
    reason: '多轮工具调用需要记忆上一轮的参数与结果。',
    created_at: '2026-04-11T04:10:00Z',
    directionality: 'directed',
  },
  {
    // Interesting cross-project relation: latency (retrieval ↔ observability)
    // links back to tracing (observability-only). This is the bridge
    // relation that makes the theme-rag-eval "bridge" role meaningful.
    relation_id: 'rel-latency-tracing',
    source_entry_id: 'reg-latency',
    target_entry_id: 'reg-tracing',
    relation_type: 'observed_via',
    confidence: 0.88,
    source: 'user',
    review_status: 'approved',
    reason: 'RAG 端到端时延需要通过 distributed tracing 才能归因到具体阶段。',
    created_at: '2026-04-12T06:00:00Z',
    directionality: 'directed',
  },
  {
    relation_id: 'rel-recall-latency',
    source_entry_id: 'reg-recall',
    target_entry_id: 'reg-latency',
    relation_type: 'trades_off_with',
    confidence: 0.72,
    source: 'llm',
    review_status: 'pending',
    reason: '提高召回率通常意味着更大的检索候选集，端到端时延随之上升。',
    created_at: '2026-04-12T06:20:00Z',
    directionality: 'undirected',
  },
]

// Convenience lookups.
export const entriesById = Object.fromEntries(
  registryEntries.map((e) => [e.entry_id, e]),
)

export function findEntry(entryId) {
  return entriesById[entryId] || null
}

export function findTheme(themeId) {
  return themes.find((t) => t.theme_id === themeId) || null
}

export function findRelation(relationId) {
  return crossRelations.find((r) => r.relation_id === relationId) || null
}

export function crossRelationsForEntry(entryId) {
  return crossRelations.filter(
    (r) => r.source_entry_id === entryId || r.target_entry_id === entryId,
  )
}
