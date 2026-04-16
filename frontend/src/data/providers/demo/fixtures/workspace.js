// Demo workspace fixture.
//
// Small-but-plausible sample graphs for each demo project. Keyed by the
// same project_id values used in the overview fixture, so clicking
// "工作台" in demo overview lands on a page that actually has something
// to show.
//
// Shape matches loadProjectWorkbenchState() return:
//   { project, graphData, phase1TaskResult }

// Light helper to keep the data readable below.
function node(uuid, name, labels, extra = {}) {
  return {
    uuid,
    name,
    labels: Array.isArray(labels) ? labels : [labels],
    properties: extra.properties || {},
    summary: extra.summary || '',
    ...extra,
  }
}

function edge(uuid, source, target, factType, name = factType) {
  return {
    uuid,
    source_node_uuid: source,
    target_node_uuid: target,
    fact_type: factType,
    name,
  }
}

// --- Project 1: observability platform ---------------------------------
const observabilityNodes = [
  node('n-observ-root', '可观测性平台调研', 'Topic', {
    summary: '对比 Grafana/Honeycomb/自研三种可观测性平台的调研文档。',
  }),
  node('n-metrics', '指标采集', 'Layer'),
  node('n-traces', '调用链追踪', 'Layer'),
  node('n-logs', '日志聚合', 'Layer'),
  node('n-otel', 'OpenTelemetry', 'Technology', {
    summary: 'CNCF 下的可观测性数据采集标准。',
  }),
  node('n-prometheus', 'Prometheus', 'Technology'),
  node('n-clickhouse', 'ClickHouse', 'Technology'),
  node('n-cardinality', '高基数维度', 'Problem'),
]

const observabilityEdges = [
  edge('e-1', 'n-observ-root', 'n-metrics', 'HAS_LAYER'),
  edge('e-2', 'n-observ-root', 'n-traces', 'HAS_LAYER'),
  edge('e-3', 'n-observ-root', 'n-logs', 'HAS_LAYER'),
  edge('e-4', 'n-metrics', 'n-prometheus', 'USES_TECHNOLOGY'),
  edge('e-5', 'n-traces', 'n-otel', 'USES_TECHNOLOGY'),
  edge('e-6', 'n-logs', 'n-clickhouse', 'USES_TECHNOLOGY'),
  edge('e-7', 'n-metrics', 'n-cardinality', 'HAS_PROBLEM'),
  edge('e-8', 'n-otel', 'n-traces', 'IMPLEMENTED_BY'),
]

// --- Project 2: agentic workflows --------------------------------------
const agenticNodes = [
  node('n-agent-root', 'Agentic Workflows 设计笔记', 'Topic', {
    summary: '关于多步智能体工作流的模式汇总。',
  }),
  node('n-planner', '规划-执行分离', 'Pattern'),
  node('n-toolcall', '工具调用', 'Mechanism'),
  node('n-memory', '上下文记忆', 'Mechanism'),
  node('n-hitl', '人类在环', 'Pattern'),
  node('n-eval', '评估反馈闭环', 'Pattern'),
  node('n-drift', '长任务漂移', 'Problem'),
]

const agenticEdges = [
  edge('a-1', 'n-agent-root', 'n-planner', 'HAS_PATTERN'),
  edge('a-2', 'n-agent-root', 'n-hitl', 'HAS_PATTERN'),
  edge('a-3', 'n-agent-root', 'n-eval', 'HAS_PATTERN'),
  edge('a-4', 'n-planner', 'n-toolcall', 'USES_MECHANISM'),
  edge('a-5', 'n-planner', 'n-memory', 'USES_MECHANISM'),
  edge('a-6', 'n-planner', 'n-drift', 'HAS_PROBLEM'),
  edge('a-7', 'n-eval', 'n-drift', 'SOLVES'),
]

// --- Project 3: retrieval benchmarks (building) ------------------------
const retrievalNodes = [
  node('n-rag-root', '检索增强生成基准对比', 'Topic'),
  node('n-recall', '召回率', 'Metric'),
  node('n-latency', '端到端时延', 'Metric'),
]

const retrievalEdges = [
  edge('r-1', 'n-rag-root', 'n-recall', 'HAS_METRIC'),
  edge('r-2', 'n-rag-root', 'n-latency', 'HAS_METRIC'),
]

// ---------------------------------------------------------------------

export const workspaceFixturesByProjectId = {
  'demo-observability-platform': {
    project: {
      id: 'demo-observability-platform',
      // Sub-view pages (ConceptViewPage / EvolutionViewPage / ReviewPage)
      // read props.project.project_id, so include both keys.
      project_id: 'demo-observability-platform',
      name: '可观测性平台调研',
      status: 'ready',
      graph_id: 'g-demo-observability',
      analysis_summary:
        '围绕指标、链路、日志三层分别比较开源方案，关注高基数维度下的成本问题。',
      reading_structure: null,
    },
    graphData: {
      nodes: observabilityNodes,
      edges: observabilityEdges,
    },
    phase1TaskResult: {
      success: true,
      node_count: observabilityNodes.length,
      edge_count: observabilityEdges.length,
    },
  },
  'demo-agentic-workflows': {
    project: {
      id: 'demo-agentic-workflows',
      project_id: 'demo-agentic-workflows',
      name: 'Agentic Workflows 设计笔记',
      status: 'ready',
      graph_id: 'g-demo-agentic',
      analysis_summary:
        '把 agentic 系统拆成规划/执行/评估三阶段，并梳理每阶段的典型失败模式。',
      reading_structure: null,
    },
    graphData: {
      nodes: agenticNodes,
      edges: agenticEdges,
    },
    phase1TaskResult: {
      success: true,
      node_count: agenticNodes.length,
      edge_count: agenticEdges.length,
    },
  },
  'demo-retrieval-benchmarks': {
    project: {
      id: 'demo-retrieval-benchmarks',
      project_id: 'demo-retrieval-benchmarks',
      name: '检索增强生成基准对比',
      status: 'building',
      graph_id: 'g-demo-retrieval',
      analysis_summary: '正在构建中，仅抽取了初步指标节点。',
      reading_structure: null,
    },
    graphData: {
      nodes: retrievalNodes,
      edges: retrievalEdges,
    },
    phase1TaskResult: {
      success: true,
      node_count: retrievalNodes.length,
      edge_count: retrievalEdges.length,
    },
  },
}
