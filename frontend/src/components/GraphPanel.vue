<template>
  <div class="graph-panel">
    <!-- 从注册表跳转过来的返回提示 + 概念定位信息 -->
    <div v-if="focusNodeKey" class="focus-banner">
      <span class="focus-banner-text">
        正在查看概念：<strong>{{ focusNodeDisplayName }}</strong>
        <template v-if="focusNodeSection"> · 位于：{{ focusNodeSection }}</template>
      </span>
      <span v-if="!focusNodeFound" class="focus-banner-warn">（未在图谱中找到该节点）</span>
      <span class="focus-banner-hint">查看完毕可直接关闭此页面</span>
    </div>
    <div class="panel-header">
      <span class="panel-title">{{ panelTitle }}</span>
      <!-- 顶部工具栏 (Internal Top Right) -->
      <div class="header-tools">
        <div class="view-mode-switch">
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'graph' }"
            @click="viewMode = 'graph'"
          >
            关系图
          </button>
          <button
            class="mode-btn"
            :class="{ active: viewMode === 'reading' }"
            @click="viewMode = 'reading'"
          >
            阅读视图
          </button>
        </div>
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" title="刷新图谱">
          <span class="icon-refresh" :class="{ 'spinning': loading }">↻</span>
          <span class="btn-text">Refresh</span>
        </button>
        <button class="tool-btn" @click="$emit('toggle-maximize')" title="最大化/还原">
          <span class="icon-maximize">⛶</span>
        </button>
      </div>
    </div>
    
    <div class="graph-container" ref="graphContainer">
      <!-- 图谱可视化 -->
      <div v-if="graphData" class="graph-view">
        <svg ref="graphSvg" class="graph-svg"></svg>
        
        <!-- 构建中/模拟中提示 -->
        <div v-if="currentPhase === 1 || isSimulating" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          {{ isSimulating ? 'GraphRAG长短期记忆实时更新中' : '实时更新中...' }}
        </div>
        
        <!-- 模拟结束后的提示 -->
        <div v-if="showSimulationFinishedHint" class="graph-building-hint finished-hint">
          <div class="hint-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="hint-icon">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <span class="hint-text">还有少量内容处理中，建议稍后手动刷新图谱</span>
          <button class="hint-close-btn" @click="dismissFinishedHint" title="关闭提示">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        <!-- 节点/边详情面板 -->
        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? 'Node Details' : 'Relationship' }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
                {{ selectedItem.entityTypeLabel }}
            </span>
            <button class="detail-close" @click="closeDetailPanel">×</button>
          </div>
          
          <!-- 节点详情 -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">Name:</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">UUID:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">Created:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>

            <div class="detail-section">
              <div class="section-title">Schema</div>
              <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">
                  <span class="schema-pill" :class="`status-${selectedItem.schemaStatus}`">
                    {{ selectedItem.entityTypeLabel }}
                  </span>
                </span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span class="detail-value">{{ selectedItem.schemaStatusLabel }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Raw Labels:</span>
                <span class="detail-value">
                  <span v-if="selectedItem.rawLabels && selectedItem.rawLabels.length">
                    {{ selectedItem.rawLabels.join(', ') }}
                  </span>
                  <span v-else class="detail-value-muted">None</span>
                </span>
              </div>
              <div
                v-if="selectedItem.schemaStatus !== 'matched'"
                class="schema-hint"
                :class="`status-${selectedItem.schemaStatus}`"
              >
                {{ getNodeSchemaHint(selectedItem) }}
              </div>
            </div>
            
            <!-- Properties -->
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">Properties:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || 'None' }}</span>
                </div>
              </div>
            </div>
            
            <!-- Summary -->
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">Summary:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>

            <!-- Phase C: Global concept link -->
            <div class="detail-section global-concept-section" v-if="registryLookup">
              <div class="section-title">全局概念</div>
              <div class="global-concept-card">
                <div class="gc-name">{{ registryLookup.canonical_name }}</div>
                <div class="gc-meta">
                  <span class="gc-type">{{ registryLookup.concept_type }}</span>
                  <span v-if="registryLookup.xrel_count" class="gc-xrel">x-rel {{ registryLookup.xrel_count }}</span>
                </div>
                <p v-if="registryLookup.description" class="gc-desc">{{ registryLookup.description.slice(0, 120) }}{{ registryLookup.description.length > 120 ? '...' : '' }}</p>
                <div class="gc-actions">
                  <a class="gc-btn" :href="`/workspace/entry/${registryLookup.entry_id}`" target="_blank">
                    查看全局概念 ↗
                  </a>
                  <a v-if="registryLookup.xrel_count > 0" class="gc-btn gc-btn-secondary"
                     :href="`/workspace/entry/${registryLookup.entry_id}#xrel`" target="_blank">
                    查看跨文关联 ({{ registryLookup.xrel_count }}) ↗
                  </a>
                </div>
              </div>
            </div>
            <div class="detail-section" v-else-if="registryLookupLoading">
              <div class="gc-loading">查询全局概念...</div>
            </div>
          </div>
          
          <!-- 边详情 -->
          <div v-else class="detail-content">
            <!-- 自环组详情 -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                {{ selectedItem.data.source_name }} - Self Relations
                <span class="self-loop-count">{{ selectedItem.data.selfLoopCount }} items</span>
              </div>
              
              <div class="self-loop-list">
                <div 
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges" 
                  :key="loop.uuid || idx" 
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <div 
                    class="self-loop-item-header"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </div>
                  
                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <div class="detail-row" v-if="loop.uuid">
                      <span class="detail-label">UUID:</span>
                      <span class="detail-value uuid-text">{{ loop.uuid }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact">
                      <span class="detail-label">Fact:</span>
                      <span class="detail-value fact-text">{{ loop.fact }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact_type">
                      <span class="detail-label">Type:</span>
                      <span class="detail-value">{{ loop.fact_type }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.created_at">
                      <span class="detail-label">Created:</span>
                      <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                    </div>
                    <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                      <span class="detail-label">Episodes:</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            
            <!-- 普通边详情 -->
            <template v-else>
              <div class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED_TO' }} → {{ selectedItem.data.target_name }}
              </div>
              
              <div class="detail-row">
                <span class="detail-label">UUID:</span>
                <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Label:</span>
                <span class="detail-value">{{ selectedItem.data.name || 'RELATED_TO' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">{{ selectedItem.data.fact_type || 'Unknown' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Schema:</span>
                <span class="detail-value">{{ getEdgeSchemaMeta(selectedItem.data).statusLabel }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.fact">
                <span class="detail-label">Fact:</span>
                <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
              </div>
              
              <!-- Episodes -->
              <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
                <div class="section-title">Episodes:</div>
                <div class="episodes-list">
                  <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                    {{ ep }}
                  </span>
                </div>
              </div>
              
              <div class="detail-row" v-if="selectedItem.data.created_at">
                <span class="detail-label">Created:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.valid_at">
                <span class="detail-label">Valid From:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>
      
      <!-- 加载状态 -->
      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>图谱数据加载中...</p>
      </div>
      
      <!-- 等待/空状态 -->
      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">等待本体生成...</p>
      </div>
    </div>

    <div v-if="graphData && hasSchemaDefinition && viewMode === 'graph'" class="schema-summary">
      <span class="schema-summary-title">Schema Fit</span>
      <div class="schema-summary-pills">
        <span class="schema-summary-pill ok">命中 {{ schemaDiagnostics.matchedNodes }}/{{ schemaDiagnostics.totalNodes }}</span>
        <span v-if="schemaDiagnostics.untypedNodes" class="schema-summary-pill warn">未归类 {{ schemaDiagnostics.untypedNodes }}</span>
        <span v-if="schemaDiagnostics.unexpectedNodes" class="schema-summary-pill danger">越界类型 {{ schemaDiagnostics.unexpectedNodes }}</span>
        <span v-if="schemaDiagnostics.unexpectedEdges" class="schema-summary-pill danger">越界关系 {{ schemaDiagnostics.unexpectedEdges }}</span>
      </div>
    </div>

    <!-- 底部图例 (Bottom Left) -->
    <div v-if="graphData && entityTypes.length && viewMode === 'graph'" class="graph-legend">
      <span class="legend-title">{{ legendTitle }}</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.label }} · {{ type.count }}</span>
        </div>
      </div>
    </div>
    
    <!-- 显示边标签开关 -->
    <div v-if="graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">Show Edge Labels</span>
    </div>

    <div v-if="graphData && viewMode === 'reading'" class="reading-options">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showAuxiliaryLinks" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">Show Auxiliary Links</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import * as d3 from 'd3'
import { lookupConceptByProject } from '../services/api/registryApi'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean,
  initialView: {
    type: String,
    default: 'graph'
  },
  readingStructure: {
    type: Object,
    default: null
  },
  schemaEntityTypes: {
    type: Array,
    default: () => []
  },
  schemaRelationTypes: {
    type: Array,
    default: () => []
  },
  focusNodeKey: {
    type: String,
    default: ''
  },
  fromSource: {
    type: String,
    default: ''
  },
  domain: {
    type: String,
    default: 'tech',  // tech-safe default
  },
})

const emit = defineEmits(['refresh', 'toggle-maximize', 'view-change'])

const UNCLASSIFIED_NODE_TYPE = 'Unclassified'
const DEFAULT_NODE_LABELS = new Set(['Entity', 'Node', '__Entity__'])
const TECHNICAL_SCHEMA_ORDER = [
  'Topic',
  'Problem',
  'Solution',
  'Architecture',
  'Layer',
  'Mechanism',
  'Decision',
  'Technology',
  'Metric',
  'Evidence',
  'Insight',
  'Example',
]

const TYPE_LABEL_MAP = {
  Topic: '主题',
  Problem: '问题',
  Solution: '方案',
  Architecture: '架构',
  Layer: '层级',
  Mechanism: '机制',
  Decision: '决策',
  Technology: '技术',
  Metric: '指标',
  Evidence: '证据',
  Insight: '洞察',
  Example: '案例',
  // methodology types (v3 domain-scoped ontology)
  Principle: '原则',
  Method: '方法',
  Step: '步骤',
  Antipattern: '反模式',
  Case: '案例',
  Signal: '信号',
  // Synthetic type for methodology's third reading backbone section
  // (replaces 'Architecture' chip when domain=methodology)
  ReasoningPath: '论证路径',
  Entity: '实体',
  Unclassified: '未归类'
}

const DEFAULT_GROUP_TITLES = {
  Layer: '架构层级',
  Mechanism: '关键机制',
  Decision: '关键决策',
  Technology: '涉及技术',
  Metric: '验证指标',
  Evidence: '关键证据',
  Insight: '核心洞察',
  Example: '案例证据',
}

const TYPE_STATUS_LABEL_MAP = {
  matched: '命中当前本体',
  untyped: '未命中类型标签',
  unexpected: '超出当前本体',
  projection: '阅读视图投影',
}

const KNOWN_TYPE_COLORS = {
  Topic: '#8E7DBE',
  Problem: '#0B61A4',
  Solution: '#C5283D',
  Architecture: '#B56B45',
  Layer: '#4B9CD3',
  Mechanism: '#1A936F',
  Decision: '#9158C2',
  Technology: '#E9724C',
  Metric: '#7B2D8E',
  Evidence: '#D4A843',
  Insight: '#2E86AB',
  Example: '#2FA84F',
  // methodology colors (v3)
  Principle: '#6A994E',    // green — stable upper principle
  Method: '#BC4749',       // red — actionable method
  Step: '#386641',         // darker green — step progression
  Antipattern: '#D88C26',  // amber/warning — avoid
  Signal: '#6D98BA',       // blue-grey — observational
  ReasoningPath: '#B56B45', // same warm brown as Architecture (similar function)
  Unclassified: '#A0A7B4',
}

const FALLBACK_TYPE_COLORS = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']

const RELATION_TREE_PRIORITY = {
  HAS_TOPIC: 0,
  HAS_PROBLEM: 1,
  SOLVES: 2,
  IMPLEMENTED_BY: 3,
  HAS_LAYER: 4,
  USES_MECHANISM: 5,
  USES_TECHNOLOGY: 6,
  JUSTIFIED_BY: 7,
  HAS_EXAMPLE: 8,
  EVIDENCED_BY: 9,
  PRODUCES: 10,
}

const TYPE_READING_PRIORITY = {
  Topic: 0,
  Problem: 1,
  Solution: 2,
  Architecture: 3,
  Layer: 4,
  Mechanism: 5,
  Technology: 6,
  Decision: 6,
  Metric: 7,
  Evidence: 7,
  Insight: 7,
  Example: 8,
  Unclassified: 9,
  Entity: 10,
}

const ROOT_TYPE_PRIORITY = ['Topic', 'Solution', 'Architecture', 'Problem', 'Layer', 'Mechanism', 'Technology', 'Decision', 'Metric', 'Evidence', 'Insight', 'Example', UNCLASSIFIED_NODE_TYPE, 'Entity']
const TOPIC_BRANCH_TYPES = new Set(['Problem', 'Solution', 'Architecture'])
const SUPPORT_TYPES = new Set(['Mechanism', 'Technology', 'Decision', 'Metric', 'Evidence', 'Insight', 'Example'])
const SYNTHETIC_RELATION = 'READING_SPINE'

const TYPE_KEYWORDS = {
  Topic: ['topic', '主题', '体系', '建设', '领域', '全链路', 'observability', '可观测'],
  Problem: ['problem', '问题', '痛点', '挑战', '黑盒', '不可见', '困境', 'debug', 'difficulty', 'uncertainty'],
  Solution: ['solution', '方案', '插件', 'plugin', 'system', '系统', 'platform', '平台', '可观测插件', 'observability plugin'],
  Architecture: ['architecture', '架构', '整体设计', '分层', 'layered'],
  Layer: ['layer', '层', '视图', '采集层', '建模层', '存储层', '分析层', '展示'],
  Mechanism: ['mechanism', '机制', 'hook', 'trace', 'lineage', '异步', '队列', '策略', '拦截', 'stream'],
  Decision: ['decision', '选择', '选型', 'tradeoff', '权衡', '不选', 'why'],
  Technology: ['technology', 'duckdb', 'sqlite', 'json', 'http', 'gateway', 'llm', 'prompt', 'rds', 'sql', 'database', '数据库', '框架', '协议', '工具'],
  Metric: ['metric', '指标', '延迟', '耗时', '失败率', 'frequency', 'latency', 'token', 'throughput', '异常', 'records'],
  Example: ['example', 'case', '案例', '场景', 'record', 'reply', '回复', '企业内网', 'observations'],
}

const FALLBACK_PARENT_TYPES = {
  Problem: ['Topic'],
  Solution: ['Problem', 'Topic'],
  Architecture: ['Solution'],
  Layer: ['Architecture', 'Solution'],
  Mechanism: ['Layer', 'Architecture', 'Solution'],
  Technology: ['Layer', 'Architecture', 'Solution'],
  Decision: ['Solution', 'Architecture'],
  Metric: ['Solution', 'Problem', 'Architecture'],
  Example: ['Solution', 'Architecture', 'Problem'],
}

const RELATION_DIRECTION_RESOLVERS = {
  HAS_TOPIC: edge => ({ parentId: edge.target_node_uuid, childId: edge.source_node_uuid }),
  HAS_PROBLEM: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
  SOLVES: edge => ({ parentId: edge.target_node_uuid, childId: edge.source_node_uuid }),
  IMPLEMENTED_BY: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
  HAS_LAYER: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
  USES_MECHANISM: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
  USES_TECHNOLOGY: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
  JUSTIFIED_BY: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
  HAS_EXAMPLE: edge => ({ parentId: edge.source_node_uuid, childId: edge.target_node_uuid }),
}

const READING_GROUP_META = {
  Problem: {
    title: '补充问题',
    parentTypes: ['Topic', 'Problem'],
    description: 'Additional problem statements related to the article topic.',
  },
  Solution: {
    title: '补充方案',
    parentTypes: ['Problem', 'Solution', 'Topic'],
    description: 'Additional solution branches related to the main topic.',
  },
  Architecture: {
    title: '架构分支',
    parentTypes: ['Solution', 'Architecture'],
    description: 'Additional architecture branches derived from the article graph.',
  },
  Layer: {
    title: '扩展层级',
    parentTypes: ['Architecture', 'Layer', 'Solution'],
    description: 'Additional structural layers collapsed from the full graph.',
  },
  Mechanism: {
    title: '关键机制',
    parentTypes: ['Architecture', 'Solution', 'Layer'],
    description: 'Mechanisms that support the main solution or architecture.',
  },
  Decision: {
    title: '关键决策',
    parentTypes: ['Solution', 'Architecture'],
    description: 'Decision or tradeoff nodes supporting the main solution.',
  },
  Technology: {
    title: '涉及技术',
    parentTypes: ['Solution', 'Architecture', 'Layer'],
    description: 'Technologies, tools, and components involved in the implementation.',
  },
  Metric: {
    title: '验证指标',
    parentTypes: ['Solution', 'Problem', 'Architecture'],
    description: 'Metrics or evaluation signals used to validate the solution.',
  },
  Example: {
    title: '案例证据',
    parentTypes: ['Solution', 'Architecture', 'Problem'],
    description: 'Examples and evidence nodes collapsed from the detailed graph.',
  },
}

const READING_SUMMARY_TYPES_BY_DOMAIN = {
  tech: {
    solution: 'Solution',
    architecture: 'Architecture',
  },
  methodology: {
    solution: 'Method',
    architecture: 'ReasoningPath',
  },
}

const getReadingSummaryType = (section) =>
  (READING_SUMMARY_TYPES_BY_DOMAIN[props.domain] || READING_SUMMARY_TYPES_BY_DOMAIN.tech)[section] ||
  READING_SUMMARY_TYPES_BY_DOMAIN.tech[section]

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const normalizePanelView = (value) => (value === 'reading' ? 'reading' : 'graph')
const viewMode = ref(normalizePanelView(props.initialView))
const showEdgeLabels = ref(true) // 默认显示边标签
const showAuxiliaryLinks = ref(false)
const expandedReadingGroups = ref(new Set())
const expandedSelfLoops = ref(new Set()) // 展开的自环项
const showSimulationFinishedHint = ref(false) // 模拟结束后的提示
const wasSimulating = ref(false) // 追踪之前是否在模拟中

const schemaEntityTypeNames = computed(() =>
  (props.schemaEntityTypes || [])
    .map(item => typeof item === 'string' ? item : item?.name)
    .filter(Boolean)
)

const schemaRelationTypeNames = computed(() =>
  (props.schemaRelationTypes || [])
    .map(item => typeof item === 'string' ? item : item?.name)
    .filter(Boolean)
)

const schemaEntityTypeSet = computed(() => new Set(schemaEntityTypeNames.value))
const schemaRelationTypeSet = computed(() => new Set(schemaRelationTypeNames.value))
const hasSchemaDefinition = computed(() =>
  schemaEntityTypeNames.value.length > 0 || schemaRelationTypeNames.value.length > 0
)

const panelTitle = computed(() =>
  viewMode.value === 'reading' ? 'Reading Structure View' : 'Graph Relationship Visualization'
)

const legendTitle = computed(() =>
  hasSchemaDefinition.value ? 'Schema Types' : 'Entity Types'
)

const normalizeReadingStage = (value, fallbackTitle) => {
  if (!value || typeof value !== 'object') {
    return { title: fallbackTitle, summary: '' }
  }
  return {
    title: String(value.title || fallbackTitle).trim() || fallbackTitle,
    summary: String(value.summary || '').trim(),
  }
}

const readingStructureMeta = computed(() => {
  if (!props.readingStructure || typeof props.readingStructure !== 'object') {
    return null
  }

  const groupTitles = { ...DEFAULT_GROUP_TITLES }
  const rawGroupTitles = props.readingStructure.group_titles || props.readingStructure.groupTitles || {}
  // Merge defaults with LLM-provided titles
  Object.keys(groupTitles).forEach((key) => {
    const rawValue = rawGroupTitles[key]
    if (typeof rawValue === 'string' && rawValue.trim()) {
      groupTitles[key] = rawValue.trim()
    }
  })
  // Accept any extra keys from LLM (forward compatibility for new types)
  Object.keys(rawGroupTitles).forEach((key) => {
    if (!(key in groupTitles)) {
      const rawValue = rawGroupTitles[key]
      if (typeof rawValue === 'string' && rawValue.trim()) {
        groupTitles[key] = rawValue.trim()
      }
    }
  })

  const title = typeof props.readingStructure.title === 'string'
    ? props.readingStructure.title.trim()
    : ''
  const summary = typeof props.readingStructure.summary === 'string'
    ? props.readingStructure.summary.trim()
    : ''
  const rawNodeOrderHints = props.readingStructure.node_order_hints || props.readingStructure.nodeOrderHints || {}
  const nodeOrderHints = {}
  Object.entries(rawNodeOrderHints).forEach(([key, value]) => {
    const numericValue = Number(value)
    if (Number.isFinite(numericValue)) {
      nodeOrderHints[key] = numericValue
    }
  })

  return {
    title,
    summary,
    problem: normalizeReadingStage(props.readingStructure.problem, '核心问题'),
    solution: normalizeReadingStage(props.readingStructure.solution, '核心方案'),
    architecture: normalizeReadingStage(props.readingStructure.architecture, '结构路径'),
    groupTitles,
    nodeOrderHints,
  }
})

// 关闭模拟结束提示
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// 监听 isSimulating 变化，检测模拟结束
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue) {
    // 从模拟中变为非模拟状态，显示结束提示
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// 切换自环项展开/折叠状态
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

const toggleReadingGroup = (id) => {
  const next = new Set(expandedReadingGroups.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedReadingGroups.value = next
}

const getRawNodeLabels = (node) =>
  (node?.labels || []).filter(label => !DEFAULT_NODE_LABELS.has(label))

const isSyntheticProjectionNode = (node) => {
  const generatedBy = node?.attributes?.generated_by
  return generatedBy === 'reading_structure' || generatedBy === 'reading_projection'
}

const getNodeTypeMeta = (node) => {
  const rawLabels = getRawNodeLabels(node)
  const schemaTypes = schemaEntityTypeSet.value

  if (rawLabels.length > 0) {
    if (schemaTypes.size === 0) {
      const type = rawLabels[0]
      return {
        type,
        label: TYPE_LABEL_MAP[type] || type,
        status: 'matched',
        statusLabel: TYPE_STATUS_LABEL_MAP.matched,
        rawLabels,
      }
    }

    const matchedType = rawLabels.find(label => schemaTypes.has(label))
    if (matchedType) {
      return {
        type: matchedType,
        label: TYPE_LABEL_MAP[matchedType] || matchedType,
        status: 'matched',
        statusLabel: TYPE_STATUS_LABEL_MAP.matched,
        rawLabels,
      }
    }

    const unexpectedType = rawLabels[0]
    if (isSyntheticProjectionNode(node)) {
      return {
        type: unexpectedType,
        label: TYPE_LABEL_MAP[unexpectedType] || unexpectedType,
        status: 'projection',
        statusLabel: TYPE_STATUS_LABEL_MAP.projection,
        rawLabels,
      }
    }

    return {
      type: unexpectedType,
      label: TYPE_LABEL_MAP[unexpectedType] || unexpectedType,
      status: 'unexpected',
      statusLabel: TYPE_STATUS_LABEL_MAP.unexpected,
      rawLabels,
    }
  }

  return {
    type: UNCLASSIFIED_NODE_TYPE,
    label: TYPE_LABEL_MAP[UNCLASSIFIED_NODE_TYPE],
    status: 'untyped',
    statusLabel: TYPE_STATUS_LABEL_MAP.untyped,
    rawLabels: [],
  }
}

const getEdgeRelationName = (edge) => edge?.fact_type || edge?.name || 'RELATED_TO'

const getEdgeSchemaMeta = (edge) => {
  const relationName = getEdgeRelationName(edge)
  if (schemaRelationTypeSet.value.size === 0) {
    return {
      relation: relationName,
      status: 'matched',
      statusLabel: TYPE_STATUS_LABEL_MAP.matched,
    }
  }

  const matched = schemaRelationTypeSet.value.has(relationName)
  return {
    relation: relationName,
    status: matched ? 'matched' : 'unexpected',
    statusLabel: matched ? TYPE_STATUS_LABEL_MAP.matched : TYPE_STATUS_LABEL_MAP.unexpected,
  }
}

const getNodeSchemaHint = (item) => {
  if (item.schemaStatus === 'untyped') {
    if (item.projectedType && item.projectedType !== UNCLASSIFIED_NODE_TYPE) {
      return `该节点原始数据没有落到本体定义的类型标签中；阅读视图中暂按语义投影归为「${item.projectedTypeLabel || item.projectedType}」。`
    }
    return '该节点没有落到本体定义的类型标签中，当前仅作为未归类节点展示。'
  }
  if (item.schemaStatus === 'unexpected') {
    return '该节点带有标签，但这个标签不在当前页面使用的本体定义中。'
  }
  if (item.schemaStatus === 'projection') {
    return '这是阅读视图合成的导航节点，用于组织文章主线；不作为原始图谱本体类型校验。'
  }
  return '该节点已命中当前本体定义。'
}

const typeColorMap = computed(() => {
  const colors = { ...KNOWN_TYPE_COLORS }
  let fallbackIndex = 0
  const seenTypes = []

  ;(props.graphData?.nodes || []).forEach((node) => {
    const { type } = getNodeTypeMeta(node)
    if (!seenTypes.includes(type)) {
      seenTypes.push(type)
    }
  })

  seenTypes.forEach((type) => {
    if (!colors[type]) {
      colors[type] = FALLBACK_TYPE_COLORS[fallbackIndex % FALLBACK_TYPE_COLORS.length]
      fallbackIndex += 1
    }
  })

  return colors
})

const getTypeColor = (type) => typeColorMap.value[type] || '#A0A7B4'

// 计算实体类型用于图例
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  
  props.graphData.nodes.forEach(node => {
    const meta = getNodeTypeMeta(node)
    const type = meta.type
    if (!typeMap[type]) {
      typeMap[type] = {
        name: type,
        label: meta.label,
        count: 0,
        color: getTypeColor(type)
      }
    }
    typeMap[type].count++
  })

  const orderedNames = [
    ...TECHNICAL_SCHEMA_ORDER.filter(name => typeMap[name]),
    ...schemaEntityTypeNames.value.filter(name => !TECHNICAL_SCHEMA_ORDER.includes(name) && typeMap[name]),
    ...Object.keys(typeMap)
      .filter(name => !TECHNICAL_SCHEMA_ORDER.includes(name) && !schemaEntityTypeSet.value.has(name) && name !== UNCLASSIFIED_NODE_TYPE)
      .sort((a, b) => a.localeCompare(b, 'zh-CN')),
  ]

  if (typeMap[UNCLASSIFIED_NODE_TYPE]) {
    orderedNames.push(UNCLASSIFIED_NODE_TYPE)
  }

  return orderedNames.map(name => typeMap[name]).filter(Boolean)
})

const schemaDiagnostics = computed(() => {
  const nodes = props.graphData?.nodes || []
  const edges = props.graphData?.edges || []

  const counts = {
    totalNodes: nodes.length,
    matchedNodes: 0,
    untypedNodes: 0,
    unexpectedNodes: 0,
    totalEdges: edges.length,
    unexpectedEdges: 0,
  }

  nodes.forEach((node) => {
    const meta = getNodeTypeMeta(node)
    if (meta.status === 'matched') counts.matchedNodes += 1
    else if (meta.status === 'untyped') counts.untypedNodes += 1
    else counts.unexpectedNodes += 1
  })

  edges.forEach((edge) => {
    if (getEdgeSchemaMeta(edge).status === 'unexpected') {
      counts.unexpectedEdges += 1
    }
  })

  counts.coverage = counts.totalNodes ? Math.round((counts.matchedNodes / counts.totalNodes) * 100) : 0
  return counts
})

// 格式化时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true 
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  registryLookup.value = null
  expandedSelfLoops.value = new Set() // 重置展开状态
}

// Phase C: Registry lookup for selected node
const route = useRoute()
const registryLookup = ref(null)
const registryLookupLoading = ref(false)

watch(selectedItem, async (item) => {
  registryLookup.value = null
  if (!item || item.type !== 'node') return

  const projectId = route.params.projectId
  if (!projectId) return

  // Build concept_key from node labels + name
  const nodeData = item.data || {}
  const rawLabels = (nodeData.labels || []).filter(l => !['Entity', 'Node', '__Entity__'].includes(l))
  const typePart = rawLabels[0] || item.entityTypeLabel || 'Concept'
  const namePart = (nodeData.name || '').toLowerCase()
  const conceptKey = `${typePart}:${namePart}`

  registryLookupLoading.value = true
  try {
    const res = await lookupConceptByProject(projectId, conceptKey, namePart)
    registryLookup.value = res.data
  } catch {
    registryLookup.value = null
  } finally {
    registryLookupLoading.value = false
  }
})

const withAlpha = (colorValue, alpha) => {
  const color = d3.color(colorValue)
  if (!color) return colorValue
  color.opacity = alpha
  return color.formatRgb()
}

const buildSelectedNodeItem = (rawNode, overrideMeta = null) => {
  const meta = getNodeTypeMeta(rawNode)
  const displayType = overrideMeta?.type || meta.type
  const displayLabel = overrideMeta?.label || meta.label
  return {
    type: 'node',
    data: rawNode,
    entityType: displayType,
    entityTypeLabel: displayLabel,
    color: getTypeColor(displayType),
    schemaStatus: meta.status,
    schemaStatusLabel: meta.statusLabel,
    rawLabels: meta.rawLabels,
    projectedType: overrideMeta?.type || null,
    projectedTypeLabel: overrideMeta?.label || null,
  }
}

const getNodeDegree = (nodeId, edges) =>
  edges.reduce((count, edge) => {
    if (edge.sourceId === nodeId || edge.targetId === nodeId) {
      return count + 1
    }
    return count
  }, 0)

const getNodeTextBlob = (node) => {
  const values = Object.values(node?.attributes || {})
    .filter(value => typeof value === 'string' && value.trim())
  return [
    node?.name || '',
    node?.summary || '',
    ...values,
  ].join(' ').toLowerCase()
}

const countKeywordHits = (text, keywords) =>
  keywords.reduce((count, keyword) => count + (text.includes(keyword.toLowerCase()) ? 1 : 0), 0)

const buildReadingProjection = (graphData) => {
  const rawNodes = graphData?.nodes || []
  const rawEdges = graphData?.edges || []

  const relationStatsByNode = {}
  const ensureStats = (nodeId) => {
    if (!relationStatsByNode[nodeId]) {
      relationStatsByNode[nodeId] = {
        incoming: {},
        outgoing: {},
        neighbors: new Set(),
      }
    }
    return relationStatsByNode[nodeId]
  }

  rawNodes.forEach((node) => ensureStats(node.uuid))
  rawEdges.forEach((edge) => {
    const relation = getEdgeRelationName(edge)
    const sourceStats = ensureStats(edge.source_node_uuid)
    const targetStats = ensureStats(edge.target_node_uuid)
    sourceStats.outgoing[relation] = (sourceStats.outgoing[relation] || 0) + 1
    targetStats.incoming[relation] = (targetStats.incoming[relation] || 0) + 1
    sourceStats.neighbors.add(edge.target_node_uuid)
    targetStats.neighbors.add(edge.source_node_uuid)
  })

  const inferNodeType = (node, rawMeta) => {
    const stats = relationStatsByNode[node.uuid] || { incoming: {}, outgoing: {}, neighbors: new Set() }
    const text = getNodeTextBlob(node)
    const scores = Object.fromEntries(TECHNICAL_SCHEMA_ORDER.map(type => [type, 0]))

    const outgoing = stats.outgoing
    const incoming = stats.incoming

    if ((outgoing.HAS_LAYER || 0) > 0) {
      scores.Solution += 8
      scores.Architecture += 6
    }
    if ((incoming.HAS_LAYER || 0) > 0) scores.Layer += 10
    if ((incoming.USES_MECHANISM || 0) > 0) scores.Mechanism += 8
    if ((incoming.USES_TECHNOLOGY || 0) > 0) scores.Technology += 8
    if ((incoming.HAS_EXAMPLE || 0) > 0) scores.Example += 8
    if ((incoming.HAS_TOPIC || 0) > 0) scores.Topic += 10
    if ((outgoing.HAS_TOPIC || 0) > 0) {
      scores.Solution += 3
      scores.Problem += 2
      scores.Technology += 1
    }
    if ((outgoing.SOLVES || 0) > 0) scores.Solution += 6
    if ((incoming.SOLVES || 0) > 0) scores.Problem += 6
    if ((outgoing.JUSTIFIED_BY || 0) > 0) {
      scores.Decision += 4
      scores.Solution += 2
    }
    if ((incoming.JUSTIFIED_BY || 0) > 0) {
      scores.Metric += 2
      scores.Mechanism += 2
      scores.Technology += 2
    }

    TECHNICAL_SCHEMA_ORDER.forEach((type) => {
      const hits = countKeywordHits(text, TYPE_KEYWORDS[type] || [])
      scores[type] += hits * (type === 'Topic' ? 2 : 3)
    })

    if (/(层|layer|view|视图)$/i.test(node.name || '')) scores.Layer += 6
    if (/(架构|architecture)/i.test(node.name || '')) scores.Architecture += 6
    if (/(插件|plugin|方案|system|平台|platform)/i.test(text)) scores.Solution += 4
    if (/(duckdb|sqlite|json|http|llm|rds|数据库|框架|协议|prompt)/i.test(text)) scores.Technology += 4
    if (/(hook|trace|lineage|异步|队列|策略|拦截)/i.test(text)) scores.Mechanism += 4
    if (/(延迟|耗时|失败率|token|latency|frequency|异常|metrics?)/i.test(text)) scores.Metric += 4
    if (/(案例|场景|example|reply|回复|企业内网|record)/i.test(text)) scores.Example += 3
    if (/(问题|黑盒|不可见|困境|difficulty|uncertainty|debug)/i.test(text)) scores.Problem += 4

    const ranked = Object.entries(scores).sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1]
      return (TYPE_READING_PRIORITY[a[0]] ?? 99) - (TYPE_READING_PRIORITY[b[0]] ?? 99)
    })
    const [bestType, bestScore] = ranked[0]
    if (!bestType || bestScore < 4) {
      return {
        type: UNCLASSIFIED_NODE_TYPE,
        label: TYPE_LABEL_MAP[UNCLASSIFIED_NODE_TYPE],
        source: rawMeta.status === 'unexpected' ? 'unexpected' : 'untyped',
        score: bestScore || 0,
      }
    }
    return {
      type: bestType,
      label: TYPE_LABEL_MAP[bestType] || bestType,
      source: 'inferred',
      score: bestScore,
    }
  }

  const nodes = rawNodes.map((node) => {
    const rawMeta = getNodeTypeMeta(node)
    const inferred = rawMeta.status === 'matched'
      ? {
          type: rawMeta.type,
          label: rawMeta.label,
          source: 'explicit',
          score: 100,
        }
      : inferNodeType(node, rawMeta)

    return {
      id: node.uuid,
      name: node.name || 'Unnamed',
      type: inferred.type,
      typeLabel: inferred.label,
      projectionSource: inferred.source,
      projectionScore: inferred.score,
      rawType: rawMeta.type,
      rawStatus: rawMeta.status,
      rawData: node,
    }
  })

  const nodeMap = Object.fromEntries(nodes.map(node => [node.id, node]))
  const edges = rawEdges
    .filter(edge => nodeMap[edge.source_node_uuid] && nodeMap[edge.target_node_uuid])
    .map(edge => ({
      id: edge.uuid || `${edge.source_node_uuid}-${edge.target_node_uuid}-${edge.name || edge.fact_type || 'edge'}`,
      relation: getEdgeRelationName(edge),
      rawData: edge,
      sourceId: edge.source_node_uuid,
      targetId: edge.target_node_uuid,
      sourceNode: nodeMap[edge.source_node_uuid],
      targetNode: nodeMap[edge.target_node_uuid],
    }))

  return {
    nodes,
    edges,
    nodeMap,
    relationStatsByNode,
  }
}

const createSyntheticNode = (id, name, type, options = {}) => ({
  id,
  name,
  type,
  typeLabel: TYPE_LABEL_MAP[type] || type,
  isGroup: Boolean(options.isGroup),
  preserveChildOrder: Boolean(options.preserveChildOrder),
  collapsibleChildIds: options.collapsibleChildIds || [],
  expandOnNodeClick: Boolean(options.expandOnNodeClick),
  projectionSource: 'synthetic',
  projectionScore: 100,
  rawType: UNCLASSIFIED_NODE_TYPE,
  rawStatus: 'untyped',
  rawData: {
    uuid: id,
    name,
    labels: [type],
    attributes: {
      generated_by: 'reading_projection',
      ...(options.attributes || {}),
    },
    summary: options.summary || `${name} is a synthesized ${type} anchor derived from the graph structure for reading layout.`,
    created_at: null,
  },
})

const createReadingSummaryNode = (id, name, type, summary = '', attributes = {}, options = {}) =>
  createSyntheticNode(id, name, type, {
    summary,
    preserveChildOrder: true,
    ...options,
    attributes: {
      generated_by: 'reading_structure',
      ...attributes,
    },
  })

const scoreSpineCandidate = (node, type, edges, relationStatsByNode) => {
  const stats = relationStatsByNode[node.id] || { incoming: {}, outgoing: {}, neighbors: new Set() }
  let score = getNodeDegree(node.id, edges)

  if (node.projectionSource === 'explicit') score += 8
  if (type === 'Topic') score += (stats.incoming.HAS_TOPIC || 0) * 6 + stats.neighbors.size
  if (type === 'Problem') score += (stats.incoming.SOLVES || 0) * 4 + countKeywordHits(getNodeTextBlob(node.rawData), TYPE_KEYWORDS.Problem)
  if (type === 'Solution') score += (stats.outgoing.HAS_LAYER || 0) * 10 + (stats.outgoing.USES_MECHANISM || 0) * 3 + (stats.outgoing.USES_TECHNOLOGY || 0) * 2 + countKeywordHits(getNodeTextBlob(node.rawData), TYPE_KEYWORDS.Solution)
  if (type === 'Architecture') score += (stats.outgoing.HAS_LAYER || 0) * 10 + countKeywordHits(getNodeTextBlob(node.rawData), TYPE_KEYWORDS.Architecture)

  return score
}

const buildReadingTreeData = (graphData, readingStructure = null) => {
  const { nodes, edges, nodeMap, relationStatsByNode } = buildReadingProjection(graphData)
  if (!nodes.length) {
    return null
  }
  const nodeOrderHints = readingStructure?.nodeOrderHints || {}

  const nodesByType = {}
  nodes.forEach((node) => {
    if (!nodesByType[node.type]) {
      nodesByType[node.type] = []
    }
    nodesByType[node.type].push(node)
  })

  const sortByScore = (items, type) =>
    [...(items || [])].sort((a, b) => {
      const scoreDiff = scoreSpineCandidate(b, type, edges, relationStatsByNode) - scoreSpineCandidate(a, type, edges, relationStatsByNode)
      if (scoreDiff !== 0) return scoreDiff
      const orderDiff = getNodeArticleOrder(a) - getNodeArticleOrder(b)
      if (orderDiff !== 0) return orderDiff
      return a.name.localeCompare(b.name, 'zh-CN')
    })

  function getNodeArticleOrder(node) {
    const hintedValue = nodeOrderHints[node.id]
    if (Number.isFinite(hintedValue)) {
      return hintedValue
    }
    return Number.MAX_SAFE_INTEGER
  }

  const LAYER_SEQUENCE_KEYWORDS = [
    ['collection', 'collect', '采集', 'ingest', 'capture'],
    ['model', '建模', 'lineage', 'trace'],
    ['storage', 'store', '存储', 'warehouse', 'db', 'database'],
    ['display', 'analysis', '展示', '分析', 'view', 'dashboard'],
  ]

  const getLayerStageOrder = (node) => {
    const blob = getNodeTextBlob(node.rawData || node)
    const matchedIndex = LAYER_SEQUENCE_KEYWORDS.findIndex((keywords) =>
      keywords.some((keyword) => blob.includes(keyword.toLowerCase()))
    )
    return matchedIndex >= 0 ? matchedIndex : Number.MAX_SAFE_INTEGER
  }

  const sortNodesForReading = (items, type) =>
    [...(items || [])].sort((a, b) => {
      if (type === 'Layer') {
        const stageDiff = getLayerStageOrder(a) - getLayerStageOrder(b)
        if (stageDiff !== 0) return stageDiff
      }

      const orderDiff = getNodeArticleOrder(a) - getNodeArticleOrder(b)
      if (orderDiff !== 0) return orderDiff

      const scoreDiff = scoreSpineCandidate(b, type, edges, relationStatsByNode) - scoreSpineCandidate(a, type, edges, relationStatsByNode)
      if (scoreDiff !== 0) return scoreDiff

      if (a.projectionSource !== b.projectionSource) {
        return a.projectionSource === 'explicit' ? -1 : 1
      }

      return a.name.localeCompare(b.name, 'zh-CN')
    })

  const topicRoot = sortByScore(nodesByType.Topic, 'Topic')[0] || sortByScore(nodesByType.Solution, 'Solution')[0] || nodes[0]
  const problemCandidates = sortByScore(nodesByType.Problem, 'Problem').filter(node => node.id !== topicRoot.id)
  const solutionCandidates = sortByScore(nodesByType.Solution, 'Solution').filter(node => node.id !== topicRoot.id)
  const architectureCandidates = sortByScore(nodesByType.Architecture, 'Architecture').filter(node => node.id !== topicRoot.id)
  const rawLayerCandidates = sortNodesForReading(nodesByType.Layer, 'Layer')

  const primaryProblem = problemCandidates[0] || null
  const primarySolution = solutionCandidates[0] || (topicRoot.type === 'Solution' ? topicRoot : null)

  let primaryArchitecture = architectureCandidates[0] || null
  const primarySolutionStats = primarySolution ? relationStatsByNode[primarySolution.id] || { outgoing: {}, incoming: {}, neighbors: new Set() } : null
  if (!primaryArchitecture && primarySolution && (primarySolutionStats.outgoing.HAS_LAYER || 0) > 0) {
    primaryArchitecture = createSyntheticNode(
      `synthetic-architecture-${primarySolution.id}`,
      '实施架构',
      'Architecture',
    )
    nodeMap[primaryArchitecture.id] = primaryArchitecture
  }

  const getNodeStats = (nodeId) =>
    relationStatsByNode[nodeId] || { outgoing: {}, incoming: {}, neighbors: new Set() }

  const hasStrongTopicSignal = (node) => {
    if (!node || node.type !== 'Topic') return false
    const stats = getNodeStats(node.id)
    const topicRelationEvidence = (stats.incoming.HAS_TOPIC || 0) + (stats.outgoing.HAS_TOPIC || 0)
    if (node.projectionSource === 'explicit') return true
    return topicRelationEvidence > 0 && node.projectionScore >= 8
  }

  const rootNode = primaryProblem || primarySolution || primaryArchitecture || topicRoot

  const isStructuralLayer = (node) => {
    const stats = getNodeStats(node.id)
    return node.rawStatus === 'matched'
      || (stats.incoming.HAS_LAYER || 0) > 0
      || (stats.outgoing.HAS_LAYER || 0) > 0
      || /(层|layer)$/i.test(node.name || '')
  }

  let structuralLayers = rawLayerCandidates.filter(isStructuralLayer)
  if (!structuralLayers.length) {
    structuralLayers = rawLayerCandidates
  }
  structuralLayers = sortNodesForReading(structuralLayers, 'Layer')

  const usedNodeIds = new Set()
  const usedEdgeIds = new Set()
  const treeLinks = []
  const childrenMap = {}

  const ensureChildren = (nodeId) => {
    if (!childrenMap[nodeId]) {
      childrenMap[nodeId] = []
    }
  }

  const addTreeNode = (parentNode, childNode, relation = SYNTHETIC_RELATION, rawData = null, synthetic = true) => {
    if (!parentNode || !childNode || parentNode.id === childNode.id) return
    ensureChildren(parentNode.id)
    if (!childrenMap[parentNode.id].includes(childNode.id)) {
      childrenMap[parentNode.id].push(childNode.id)
    }
    treeLinks.push({
      id: rawData?.uuid || `${parentNode.id}-${childNode.id}-${relation}`,
      relation,
      rawData,
      synthetic,
      parentId: parentNode.id,
      childId: childNode.id,
      parentNode,
      childNode,
    })
    if (rawData?.uuid) {
      usedEdgeIds.add(rawData.uuid)
    }
    usedNodeIds.add(parentNode.id)
    usedNodeIds.add(childNode.id)
  }

  const edgeIndexByPair = {}
  edges.forEach((edge) => {
    edgeIndexByPair[`${edge.sourceId}->${edge.targetId}->${edge.relation}`] = edge
  })

  const findConnectingEdge = (parentNode, childNode) => {
    const preferred = [
      `${parentNode.id}->${childNode.id}->HAS_PROBLEM`,
      `${parentNode.id}->${childNode.id}->IMPLEMENTED_BY`,
      `${parentNode.id}->${childNode.id}->HAS_LAYER`,
      `${parentNode.id}->${childNode.id}->USES_MECHANISM`,
      `${parentNode.id}->${childNode.id}->USES_TECHNOLOGY`,
      `${parentNode.id}->${childNode.id}->JUSTIFIED_BY`,
      `${parentNode.id}->${childNode.id}->HAS_EXAMPLE`,
      `${parentNode.id}->${childNode.id}->SOLVES`,
      `${childNode.id}->${parentNode.id}->SOLVES`,
      `${childNode.id}->${parentNode.id}->HAS_TOPIC`,
      `${parentNode.id}->${childNode.id}->HAS_TOPIC`,
    ]
    for (const key of preferred) {
      if (edgeIndexByPair[key]) return edgeIndexByPair[key]
    }
    return edges.find((edge) =>
      (edge.sourceId === parentNode.id && edge.targetId === childNode.id) ||
      (edge.sourceId === childNode.id && edge.targetId === parentNode.id)
    ) || null
  }

  let displayRoot = rootNode
  let problemAnchor = rootNode
  let solutionAnchor = rootNode
  let architectureAnchor = rootNode
  let displayRepresentative = rootNode
  let problemRepresentative = primaryProblem
  let solutionRepresentative = primarySolution
  let architectureRepresentative = primaryArchitecture
  const attachedRepresentativeIds = new Set()

  const attachRepresentativeChild = (summaryNode, representativeNode) => {
    if (!summaryNode || !representativeNode || summaryNode.id === representativeNode.id) return
    if (attachedRepresentativeIds.has(representativeNode.id)) return
    if (!summaryNode.collapsibleChildIds) {
      summaryNode.collapsibleChildIds = []
    }
    if (!summaryNode.collapsibleChildIds.includes(representativeNode.id)) {
      summaryNode.collapsibleChildIds.push(representativeNode.id)
    }
    summaryNode.expandOnNodeClick = true
    summaryNode.preserveChildOrder = true
    addTreeNode(summaryNode, representativeNode, SYNTHETIC_RELATION, null, true)
    attachedRepresentativeIds.add(representativeNode.id)
  }

  if (readingStructure?.title) {
    displayRoot = createReadingSummaryNode(
      `reading-article-root-${rootNode.id}`,
      readingStructure.title,
      'Topic',
      readingStructure.summary,
      {
        representative_node: rootNode.name,
      }
    )
    nodeMap[displayRoot.id] = displayRoot
    usedNodeIds.add(displayRoot.id)

    const problemSummaryNode = createReadingSummaryNode(
      `reading-problem-${rootNode.id}`,
      readingStructure.problem.title,
      'Problem',
      readingStructure.problem.summary,
      {
        representative_node: primaryProblem?.name || rootNode.name,
      }
    )
    nodeMap[problemSummaryNode.id] = problemSummaryNode
    addTreeNode(displayRoot, problemSummaryNode, SYNTHETIC_RELATION, null, true)
    problemAnchor = problemSummaryNode
    attachRepresentativeChild(problemSummaryNode, problemRepresentative)

    const solutionSummaryNode = createReadingSummaryNode(
      `reading-solution-${rootNode.id}`,
      readingStructure.solution.title,
      getReadingSummaryType('solution'),
      readingStructure.solution.summary,
      {
        representative_node: primarySolution?.name || rootNode.name,
      }
    )
    nodeMap[solutionSummaryNode.id] = solutionSummaryNode
    addTreeNode(problemAnchor, solutionSummaryNode, SYNTHETIC_RELATION, null, true)
    solutionAnchor = solutionSummaryNode
    attachRepresentativeChild(solutionSummaryNode, solutionRepresentative)

    const architectureSummaryNode = createReadingSummaryNode(
      `reading-architecture-${rootNode.id}`,
      readingStructure.architecture.title,
      getReadingSummaryType('architecture'),
      readingStructure.architecture.summary,
      {
        representative_node: primaryArchitecture?.name || primarySolution?.name || rootNode.name,
      }
    )
    nodeMap[architectureSummaryNode.id] = architectureSummaryNode
    addTreeNode(solutionAnchor, architectureSummaryNode, SYNTHETIC_RELATION, null, true)
    architectureAnchor = architectureSummaryNode
    attachRepresentativeChild(architectureSummaryNode, architectureRepresentative)
    attachRepresentativeChild(displayRoot, displayRepresentative)

    ;[rootNode, primaryProblem, primarySolution, primaryArchitecture]
      .filter(Boolean)
      .forEach((node) => usedNodeIds.add(node.id))
  } else {
    usedNodeIds.add(rootNode.id)

    if (primaryProblem && primaryProblem.id !== rootNode.id) {
      const bridge = findConnectingEdge(rootNode, primaryProblem) || findConnectingEdge(topicRoot, primaryProblem)
      addTreeNode(rootNode, primaryProblem, bridge?.relation || SYNTHETIC_RELATION, bridge?.rawData || null, !bridge)
      problemAnchor = primaryProblem
    } else if (primaryProblem) {
      problemAnchor = primaryProblem
    }

    solutionAnchor = rootNode
    if (primarySolution && primarySolution.id !== rootNode.id && primarySolution.id !== problemAnchor.id) {
      const bridge = findConnectingEdge(problemAnchor, primarySolution) || findConnectingEdge(rootNode, primarySolution)
      addTreeNode(problemAnchor, primarySolution, bridge?.relation || SYNTHETIC_RELATION, bridge?.rawData || null, !bridge)
      solutionAnchor = primarySolution
    } else if (primarySolution) {
      solutionAnchor = primarySolution
    }

    architectureAnchor = solutionAnchor
    if (primaryArchitecture && primaryArchitecture.id !== solutionAnchor?.id && primaryArchitecture.id !== problemAnchor.id && primaryArchitecture.id !== rootNode.id) {
      const bridge = findConnectingEdge(solutionAnchor, primaryArchitecture) || findConnectingEdge(rootNode, primaryArchitecture)
      addTreeNode(solutionAnchor, primaryArchitecture, bridge?.relation || SYNTHETIC_RELATION, bridge?.rawData || null, !bridge)
      architectureAnchor = primaryArchitecture
    } else if (primaryArchitecture) {
      architectureAnchor = primaryArchitecture
    }
  }

  const secondaryProblems = sortNodesForReading(
    problemCandidates.filter(node => node.id !== primaryProblem?.id),
    'Problem'
  )
  const secondarySolutions = sortNodesForReading(
    solutionCandidates.filter(node => node.id !== primarySolution?.id),
    'Solution'
  )

  const groupedCandidatesByType = {}
  const addGroupedCandidate = (node) => {
    if (!node || usedNodeIds.has(node.id) || node.type === UNCLASSIFIED_NODE_TYPE || node.type === 'Topic') return
    if (!groupedCandidatesByType[node.type]) {
      groupedCandidatesByType[node.type] = []
    }
    if (!groupedCandidatesByType[node.type].some(item => item.id === node.id)) {
      groupedCandidatesByType[node.type].push(node)
    }
  }

  const uniqueMembersPreview = (members) =>
    [...new Set(members.map(item => item.name).filter(Boolean))].slice(0, 5)

  const createGroupedSummaryNode = (type, members, titleOverride = null) => {
    const groupMeta = READING_GROUP_META[type] || {
      title: `${TYPE_LABEL_MAP[type] || type}节点`,
      description: `Collapsed ${type} nodes from the detailed graph.`,
    }
    const preview = uniqueMembersPreview(members)
    const displayTitle = titleOverride || readingStructure?.groupTitles?.[type] || groupMeta.title
    return createSyntheticNode(
      `reading-group-${type}-${rootNode.id}-${members.length}-${titleOverride || 'default'}`,
      `${displayTitle} · ${members.length}`,
      type,
      {
        isGroup: true,
        preserveChildOrder: true,
        attributes: {
          member_count: String(members.length),
          representative_members: preview.join('、') || 'N/A',
          member_names: members.map(item => item.name).join(' | '),
          collapsed_type: type,
        },
        summary: `${groupMeta.description} 当前阅读视图折叠了 ${members.length} 个${TYPE_LABEL_MAP[type] || type}节点。${preview.length ? ` 代表节点：${preview.join('、')}。` : ''}`,
      }
    )
  }

  const attachGroupChildren = (groupNode, members) => {
    members.forEach((member) => {
      addTreeNode(groupNode, member, SYNTHETIC_RELATION, null, true)
    })
  }

  if (structuralLayers.length) {
    const layerParent = architectureAnchor || solutionAnchor || displayRoot
    const layerGroupNode = createGroupedSummaryNode('Layer', structuralLayers, readingStructure?.groupTitles?.Layer || '架构层级')
    nodeMap[layerGroupNode.id] = layerGroupNode
    addTreeNode(layerParent, layerGroupNode, SYNTHETIC_RELATION, null, true)
    attachGroupChildren(layerGroupNode, structuralLayers)
  }

  secondaryProblems.forEach(addGroupedCandidate)
  secondarySolutions.forEach(addGroupedCandidate)
  nodes
    .filter(node => !usedNodeIds.has(node.id))
    .forEach(addGroupedCandidate)

  const resolveGroupedParent = (type) => {
    const parentTypeOrder = READING_GROUP_META[type]?.parentTypes || FALLBACK_PARENT_TYPES[type] || []
    const anchorPool = [
      architectureAnchor,
      solutionAnchor,
      problemAnchor,
      displayRoot,
    ].filter(Boolean)

    for (const preferredType of parentTypeOrder) {
      const match = anchorPool.find(anchor => anchor.type === preferredType)
      if (match) return match
    }
    return anchorPool[0] || displayRoot
  }

  Object.entries(groupedCandidatesByType)
    .sort((a, b) => (TYPE_READING_PRIORITY[a[0]] ?? 99) - (TYPE_READING_PRIORITY[b[0]] ?? 99))
    .forEach(([type, members]) => {
      const orderedMembers = sortNodesForReading(members, type)
      if (!orderedMembers.length) return
      const parent = resolveGroupedParent(type)
      if (!parent) return
      if (orderedMembers.length === 1) {
        addTreeNode(parent, orderedMembers[0], SYNTHETIC_RELATION, null, true)
        return
      }
      const groupNode = createGroupedSummaryNode(type, orderedMembers)
      nodeMap[groupNode.id] = groupNode
      addTreeNode(parent, groupNode, SYNTHETIC_RELATION, null, true)
      attachGroupChildren(groupNode, orderedMembers)
    })

  const buildHierarchyNode = (nodeId) => {
    const node = nodeMap[nodeId]
    let children = (childrenMap[nodeId] || []).map(childId => buildHierarchyNode(childId))
    if (!node?.preserveChildOrder) {
      children = children.sort((a, b) => {
        const typeDiff = (TYPE_READING_PRIORITY[a.type] ?? 99) - (TYPE_READING_PRIORITY[b.type] ?? 99)
        if (typeDiff !== 0) return typeDiff
        const orderDiff = getNodeArticleOrder(a) - getNodeArticleOrder(b)
        if (orderDiff !== 0) return orderDiff
        return a.name.localeCompare(b.name, 'zh-CN')
      })
    }

    return {
      ...node,
      children,
    }
  }

  const auxLinks = edges.filter(edge => !usedEdgeIds.has(edge.rawData?.uuid))

  return {
    rootId: displayRoot.id,
    hierarchy: buildHierarchyNode(displayRoot.id),
    treeLinks,
    auxLinks,
    nodeMap,
  }
}

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null
// Reading graph references for focus-node zoom
let _readingZoomBehavior = null
let _readingSvg = null
let _readingNodeGroup = null
let _readingPositionedNodes = {}

const collectExpandableIds = (node) => {
  const ids = []
  if (node.isGroup || node.collapsibleChildIds?.length) {
    ids.push(node.id)
  }
  for (const child of (node.children || [])) {
    ids.push(...collectExpandableIds(child))
  }
  return ids
}

const buildVisibleReadingHierarchy = (node) => {
  const expanded = expandedReadingGroups.value.has(node.id)
  let visibleChildren = node.children || []
  if (node.isGroup && !expanded) {
    visibleChildren = []
  } else if (!expanded && node.collapsibleChildIds?.length) {
    const hiddenChildren = new Set(node.collapsibleChildIds)
    visibleChildren = visibleChildren.filter(child => !hiddenChildren.has(child.id))
  }
  const nextChildren = visibleChildren.map(child => buildVisibleReadingHierarchy(child))

  return {
    ...node,
    children: nextChildren,
  }
}

const hasExpandableChildren = (node) =>
  Boolean(node?.data?.isGroup || (node?.data?.collapsibleChildIds && node.data.collapsibleChildIds.length))

const renderForceGraph = () => {
  if (!graphSvg.value || !props.graphData) return
  
  // 停止之前的仿真
  if (currentSimulation) {
    currentSimulation.stop()
  }
  
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  
  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    
  svg.selectAll('*').remove()
  
  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []
  
  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)
  
  const nodes = nodesData.map(n => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: getNodeTypeMeta(n).type,
    rawData: n
  }))
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // 处理边数据，计算同一对节点间的边数量和索引
  const edgePairCount = {}
  const selfLoopEdges = {} // 按节点分组的自环边
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))
  
  // 统计每对节点之间的边数量，收集自环边
  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      // 自环 - 收集到数组中
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })
  
  // 记录当前处理到每对节点的第几条边
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set() // 已处理的自环节点
  
  const edges = []
  
  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid
    
    if (isSelfLoop) {
      // 自环边 - 每个节点只添加一条合并的自环
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return // 已处理过，跳过
      }
      processedSelfLoopNodes.add(e.source_node_uuid)
      
      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'
      
      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops // 存储所有自环边的详细信息
        }
      })
      return
    }
    
    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1
    
    // 判断边的方向是否与标准化方向一致（源UUID < 目标UUID）
    const isReversed = e.source_node_uuid > e.target_node_uuid
    
    // 计算曲率：多条边时分散开，单条边为直线
    let curvature = 0
    if (totalCount > 1) {
      // 均匀分布曲率，确保明显区分
      // 曲率范围根据边数量增加，边越多曲率范围越大
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      
      // 如果边的方向与标准化方向相反，翻转曲率
      // 这样确保所有边在同一参考系下分布，不会因方向不同而重叠
      if (isReversed) {
        curvature = -curvature
      }
    }
    
    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })
    
  // Color scale
  const colorMap = {}
  entityTypes.value.forEach(t => colorMap[t.name] = t.color)
  const getColor = (type) => colorMap[type] || getTypeColor(type)

  // Simulation - 根据边数量动态调整节点间距
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      // 根据这对节点之间的边数量动态调整距离
      // 基础距离 150，每多一条边增加 40
      const baseDistance = 150
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    // 添加向中心的引力，让独立的节点群聚集到中心区域
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
  
  currentSimulation = simulation

  const g = svg.append('g')
  
  // Zoom
  svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 4]).on('zoom', (event) => {
    g.attr('transform', event.transform)
  }))

  // Links - 使用 path 支持曲线
  const linkGroup = g.append('g').attr('class', 'links')
  
  // 计算曲线路径
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // 检测自环
    if (d.isSelfLoop) {
      // 自环：绘制一个圆弧从节点出发再返回
      const loopRadius = 30
      // 从节点右侧出发，绕一圈回来
      const x1 = sx + 8  // 起点偏移
      const y1 = sy - 4
      const x2 = sx + 8  // 终点偏移
      const y2 = sy + 4
      // 使用圆弧绘制自环（sweep-flag=1 顺时针）
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }
    
    if (d.curvature === 0) {
      // 直线
      return `M${sx},${sy} L${tx},${ty}`
    }
    
    // 计算曲线控制点 - 根据边数量和距离动态调整
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    // 垂直于连线方向的偏移，根据距离比例计算，保证曲线明显可见
    // 边越多，偏移量占距离的比例越大
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // 基础25%，每多一条边增加5%
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }
  
  // 计算曲线中点（用于标签定位）
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // 检测自环
    if (d.isSelfLoop) {
      // 自环标签位置：节点右侧
      return { x: sx + 70, y: sy }
    }
    
    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }
    
    // 二次贝塞尔曲线的中点 t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    // 二次贝塞尔曲线公式 B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    
    return { x: midX, y: midY }
  }
  
  const link = linkGroup.selectAll('path')
    .data(edges)
    .enter().append('path')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      // 重置之前选中边的样式
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // 高亮当前选中的边
      d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels background (白色背景使文字更清晰)
  const linkLabelBg = linkGroup.selectAll('rect')
    .data(edges)
    .enter().append('rect')
    .attr('fill', 'rgba(255,255,255,0.95)')
    .attr('rx', 3)
    .attr('ry', 3)
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // 高亮对应的边
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', 'rgba(52, 152, 219, 0.1)')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('font-size', '9px')
    .attr('fill', '#666')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // 高亮对应的边
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', '#3498db')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })
  
  // 保存引用供外部控制显隐
  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  // Nodes group
  const nodeGroup = g.append('g').attr('class', 'nodes')
  
  // Node circles
  const node = nodeGroup.selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', 10)
    .attr('fill', d => getColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        // 只记录位置，不重启仿真（区分点击和拖拽）
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // 检测是否真正开始拖拽（移动超过阈值）
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (!d._isDragging && distance > 3) {
          // 首次检测到真正拖拽，才重启仿真
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // 只有真正拖拽过才让仿真逐渐停止
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      // 重置所有节点样式
      node.attr('stroke', '#fff').attr('stroke-width', 2.5)
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      // 高亮选中节点
      d3.select(event.target).attr('stroke', '#E91E63').attr('stroke-width', 4)
      // 高亮与此节点相连的边
      link.filter(l => l.source.id === d.id || l.target.id === d.id)
        .attr('stroke', '#E91E63')
        .attr('stroke-width', 2.5)
      
      selectedItem.value = buildSelectedNodeItem(d.rawData)
    })
    .on('mouseenter', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#333').attr('stroke-width', 3)
      }
    })
    .on('mouseleave', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#fff').attr('stroke-width', 2.5)
      }
    })

  // Node Labels
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > 8 ? d.name.substring(0, 8) + '…' : d.name)
    .attr('font-size', '11px')
    .attr('fill', '#333')
    .attr('font-weight', '500')
    .attr('dx', 14)
    .attr('dy', 4)
    .style('pointer-events', 'none')
    .style('font-family', 'system-ui, sans-serif')

  simulation.on('tick', () => {
    // 更新曲线路径
    link.attr('d', d => getLinkPath(d))
    
    // 更新边标签位置（无旋转，水平显示更清晰）
    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
        .attr('transform', '') // 移除旋转，保持水平
    })
    
    // 更新边标签背景
    linkLabelBg.each(function(d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
        .attr('transform', '') // 移除旋转
    })

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })
  
  // 点击空白处关闭详情面板
  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', '#fff').attr('stroke-width', 2.5)
    linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
    linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
    linkLabels.attr('fill', '#666')
  })
}

const renderReadingGraph = () => {
  if (!graphSvg.value || !props.graphData) return

  if (currentSimulation) {
    currentSimulation.stop()
    currentSimulation = null
  }

  const readingData = buildReadingTreeData(props.graphData, readingStructureMeta.value)
  if (!readingData?.hierarchy) return

  // Auto-expand all groups on first render (when set is empty)
  if (expandedReadingGroups.value.size === 0) {
    const allExpandable = collectExpandableIds(readingData.hierarchy)
    if (allExpandable.length > 0) {
      expandedReadingGroups.value = new Set(allExpandable)
    }
  }

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  svg.selectAll('*').remove()

  const colorMap = {}
  entityTypes.value.forEach(type => {
    colorMap[type.name] = type.color
  })
  const getColor = (type) => colorMap[type] || getTypeColor(type)

  const zoomLayer = svg.append('g')
  const graphLayer = zoomLayer.append('g')

  const hierarchyRoot = d3.hierarchy(buildVisibleReadingHierarchy(readingData.hierarchy))
  const nodeCount = hierarchyRoot.descendants().length
  const rowSpacing = Math.max(48, Math.min(58, height / Math.max(nodeCount * 0.42, 6)))
  // colSpacing must exceed the widest node card to prevent horizontal overlap
  const maxCardWidth = hierarchyRoot.descendants().reduce((max, node) => {
    const maxLen = hasExpandableChildren(node) ? 18 : 22
    const dispLen = Math.min(node.data.name.length, maxLen + 1)
    const expPad = hasExpandableChildren(node) ? 34 : 0
    const w = Math.min(Math.max(dispLen * 11 + 52 + expPad, 132), 280)
    return Math.max(max, w)
  }, 132)
  const colSpacing = maxCardWidth + 24

  d3.tree().nodeSize([rowSpacing, colSpacing])(hierarchyRoot)

  const descendants = hierarchyRoot.descendants()
  const minX = d3.min(descendants, node => node.x) ?? 0
  const maxX = d3.max(descendants, node => node.x) ?? 0
  const minY = d3.min(descendants, node => node.y) ?? 0
  const maxY = d3.max(descendants, node => node.y) ?? 0
  const verticalSpan = maxX - minX
  const horizontalSpan = maxY - minY
  const padding = 40
  const scaleX = (width - padding * 2) / Math.max(horizontalSpan + 320, 1)
  const scaleY = (height - padding * 2) / Math.max(verticalSpan + 60, 1)
  const fitScale = Math.min(scaleX, scaleY, 1)
  // Keep text readable: at least 0.65, but use fit scale if it's larger
  const autoScale = Math.max(0.65, fitScale)
  // Root node is at (y=0, x=0) in tree space; position it at left-center of viewport
  const offsetX = height / 2
  const offsetY = padding

  const zoomBehavior = d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.2, 3]).on('zoom', (event) => {
    zoomLayer.attr('transform', event.transform)
  })
  svg.call(zoomBehavior)
  svg.call(zoomBehavior.transform, d3.zoomIdentity.translate(offsetY, offsetX).scale(autoScale))

  // Store refs for focus-node zoom
  _readingZoomBehavior = zoomBehavior
  _readingSvg = svg

  const positionedNodes = {}
  descendants.forEach((node) => {
    positionedNodes[node.data.id] = node
  })
  _readingPositionedNodes = positionedNodes

  const treeLinkIndex = {}
  readingData.treeLinks.forEach((link) => {
    treeLinkIndex[`${link.parentId}-${link.childId}`] = link
  })

  const treeLinks = hierarchyRoot.links().map((link) => ({
    ...link,
    meta: treeLinkIndex[`${link.source.data.id}-${link.target.data.id}`],
  }))

  const getTreePath = (link) => {
    const { source, target } = link
    const bendX = source.y + Math.max(48, (target.y - source.y) * 0.45)
    return `M${source.y},${source.x} C${bendX},${source.x} ${bendX},${target.x} ${target.y},${target.x}`
  }

  const getAuxPath = (edge) => {
    const sourceNode = positionedNodes[edge.parentId || edge.sourceId]
    const targetNode = positionedNodes[edge.childId || edge.targetId]
    if (!sourceNode || !targetNode) return null
    const midY = (sourceNode.y + targetNode.y) / 2
    return `M${sourceNode.y},${sourceNode.x} C${midY},${sourceNode.x} ${midY},${targetNode.x} ${targetNode.y},${targetNode.x}`
  }

  const auxEdges = showAuxiliaryLinks.value
    ? readingData.auxLinks.filter((edge) => {
        const sourceNode = positionedNodes[edge.parentId || edge.sourceId]
        const targetNode = positionedNodes[edge.childId || edge.targetId]
        return sourceNode && targetNode
      })
    : []

  const auxGroup = graphLayer.append('g').attr('class', 'reading-aux-links')
  auxGroup.selectAll('path')
    .data(auxEdges)
    .enter()
    .append('path')
    .attr('d', edge => getAuxPath(edge))
    .attr('fill', 'none')
    .attr('stroke', '#CFCFD6')
    .attr('stroke-width', 1.2)
    .attr('stroke-dasharray', '5 4')
    .attr('opacity', 0.9)
    .style('cursor', 'pointer')
    .on('click', (event, edge) => {
      event.stopPropagation()
      selectedItem.value = {
        type: 'edge',
        data: edge.rawData,
      }
    })

  const treeLinkGroup = graphLayer.append('g').attr('class', 'reading-tree-links')
  const treeLink = treeLinkGroup.selectAll('path')
    .data(treeLinks)
    .enter()
    .append('path')
    .attr('d', link => getTreePath(link))
    .attr('fill', 'none')
    .attr('stroke', link => withAlpha(getColor(link.source.data.type), 0.35))
    .attr('stroke-width', link => link.meta?.synthetic ? 1.5 : 2.4)
    .attr('stroke-dasharray', link => link.meta?.synthetic ? '4 4' : null)
    .attr('stroke-linecap', 'round')
    .style('cursor', 'pointer')
    .on('click', (event, link) => {
      event.stopPropagation()
      selectedItem.value = {
        type: 'edge',
        data: link.meta?.rawData || link.meta,
      }
    })

  const labelData = treeLinks
    .filter(link =>
      !link.meta?.synthetic
      && (link.meta?.relation || link.meta?.name)
      && (link.target.depth <= 3 || ['HAS_PROBLEM', 'SOLVES', 'IMPLEMENTED_BY'].includes(link.meta?.relation))
    )
    .map((link) => ({
      x: (link.source.y + link.target.y) / 2,
      y: (link.source.x + link.target.x) / 2,
      name: link.meta?.relation || link.meta?.name,
      rawData: link.meta?.rawData,
    }))

  const linkLabelBg = graphLayer.append('g')
    .selectAll('rect')
    .data(labelData)
    .enter()
    .append('rect')
    .attr('fill', 'rgba(255,255,255,0.92)')
    .attr('rx', 4)
    .attr('ry', 4)
    .style('display', showEdgeLabels.value ? 'block' : 'none')

  const linkLabels = graphLayer.append('g')
    .selectAll('text')
    .data(labelData)
    .enter()
    .append('text')
    .text(item => item.name)
    .attr('x', item => item.x)
    .attr('y', item => item.y)
    .attr('font-size', '10px')
    .attr('fill', '#6B6B75')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .style('pointer-events', 'none')

  linkLabels.each(function(item, index) {
    const bbox = this.getBBox()
    d3.select(linkLabelBg.nodes()[index])
      .attr('x', item.x - bbox.width / 2 - 5)
      .attr('y', item.y - bbox.height / 2 - 3)
      .attr('width', bbox.width + 10)
      .attr('height', bbox.height + 6)
  })

  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  const nodeGroup = graphLayer.append('g').attr('class', 'reading-nodes')
  _readingNodeGroup = nodeGroup
  const nodeCards = nodeGroup.selectAll('g')
    .data(descendants)
    .enter()
    .append('g')
    .attr('transform', node => `translate(${node.y},${node.x})`)
    .style('cursor', 'pointer')
    .on('click', (event, node) => {
      event.stopPropagation()
      if (node.data.expandOnNodeClick || node.data.isGroup) {
        toggleReadingGroup(node.data.id)
      }
      selectedItem.value = buildSelectedNodeItem(node.data.rawData, {
        type: node.data.type,
        label: node.data.typeLabel,
      })

      nodeGroup.selectAll('rect').attr('stroke', '#E2E2E8').attr('stroke-width', 1.4)
      d3.select(event.currentTarget).select('rect')
        .attr('stroke', '#111')
        .attr('stroke-width', 2.4)

      if (node.data.expandOnNodeClick || node.data.isGroup) {
        nextTick(renderGraph)
      }
    })

  const getNodeWidth = (node) => {
    const maxLength = hasExpandableChildren(node) ? 18 : 22
    const displayLength = Math.min(node.data.name.length, maxLength + 1)
    const expandablePadding = hasExpandableChildren(node) ? 34 : 0
    return Math.min(Math.max(displayLength * 11 + 52 + expandablePadding, 132), 280)
  }

  const getTypeBadgeWidth = (node) => {
    const label = TYPE_LABEL_MAP[node.data.type] || node.data.type
    // Chinese chars are wider than ASCII; allow up to 72px to fit "论证路径" / "反模式"
    return Math.max(38, Math.min(72, label.length * 12 + 12))
  }

  const getTypeBadgeOffsetX = (node) => {
    return 30
  }

  const getToggleOffset = (node) => getNodeWidth(node) - 22

  nodeCards.append('rect')
    .attr('x', 0)
    .attr('y', -20)
    .attr('width', getNodeWidth)
    .attr('height', 40)
    .attr('rx', 14)
    .attr('ry', 14)
    .attr('fill', node => {
      if (node.depth === 0) return 'rgba(255,245,237,0.98)'
      if (node.data.isGroup) return withAlpha(getColor(node.data.type), 0.08)
      return 'rgba(255,255,255,0.98)'
    })
    .attr('stroke', node => node.data.isGroup ? withAlpha(getColor(node.data.type), 0.32) : '#E2E2E8')
    .attr('stroke-width', 1.4)
    .attr('filter', 'drop-shadow(0 2px 6px rgba(0,0,0,0.06))')

  nodeCards.append('circle')
    .attr('cx', 16)
    .attr('cy', 0)
    .attr('r', 6)
    .attr('fill', node => getColor(node.data.type))

  nodeCards.append('text')
    .attr('x', 30)
    .attr('y', 4)
    .attr('fill', '#222')
    .attr('font-size', '12px')
    .attr('font-weight', node => node.depth === 0 ? 700 : 600)
    .style('font-family', 'Space Grotesk, Noto Sans SC, system-ui, sans-serif')
    .text(node => {
      const maxLength = hasExpandableChildren(node) ? 18 : 22
      return node.data.name.length > maxLength ? `${node.data.name.slice(0, maxLength)}…` : node.data.name
    })

  const typeBadges = nodeCards.append('g')
    .attr('transform', node => `translate(${-getTypeBadgeWidth(node) - 6}, 0)`)

  typeBadges.append('rect')
    .attr('x', 0)
    .attr('y', -9)
    .attr('width', getTypeBadgeWidth)
    .attr('height', 18)
    .attr('rx', 9)
    .attr('fill', node => withAlpha(getColor(node.data.type), 0.14))

  typeBadges.append('text')
    .attr('x', node => getTypeBadgeWidth(node) / 2)
    .attr('y', 3)
    .attr('text-anchor', 'middle')
    .attr('fill', node => getColor(node.data.type))
    .attr('font-size', '9px')
    .attr('font-weight', 700)
    .style('font-family', 'JetBrains Mono, monospace')
    .text(node => {
      const label = TYPE_LABEL_MAP[node.data.type] || node.data.type
      // Allow up to 4 chars to fit "论证路径" without truncation; English fallbacks stay readable
      return label.length > 4 ? `${label.slice(0, 4)}` : label
    })

  const groupToggles = nodeCards
    .filter(node => hasExpandableChildren(node))
    .append('g')
    .attr('transform', node => `translate(${getToggleOffset(node)}, 0)`)
    .style('cursor', 'pointer')
    .on('click', (event, node) => {
      event.stopPropagation()
      toggleReadingGroup(node.data.id)
      nextTick(renderGraph)
    })

  groupToggles.append('rect')
    .attr('x', -16)
    .attr('y', -16)
    .attr('width', 32)
    .attr('height', 32)
    .attr('rx', 16)
    .attr('fill', 'rgba(255,255,255,0.01)')

  groupToggles.append('circle')
    .attr('r', 12)
    .attr('fill', '#FFF')
    .attr('stroke', node => withAlpha(getColor(node.data.type), 0.42))
    .attr('stroke-width', 1.4)
    .attr('filter', 'drop-shadow(0 2px 5px rgba(0,0,0,0.06))')

  groupToggles.append('text')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('y', 1)
    .attr('fill', node => getColor(node.data.type))
    .attr('font-size', '14px')
    .attr('font-weight', 700)
    .style('font-family', 'JetBrains Mono, monospace')
    .text(node => expandedReadingGroups.value.has(node.data.id) ? '−' : '+')

  svg.on('click', () => {
    selectedItem.value = null
    nodeGroup.selectAll('rect').attr('stroke', '#E2E2E8').attr('stroke-width', 1.4)
  })
}

const renderGraph = () => {
  if (viewMode.value === 'reading') {
    renderReadingGraph()
    return
  }
  renderForceGraph()
}

watch(() => props.graphData, () => {
  expandedReadingGroups.value = new Set()
  nextTick(renderGraph)
}, { deep: true, immediate: true })

watch(() => props.initialView, (nextView) => {
  const normalized = normalizePanelView(nextView)
  if (viewMode.value !== normalized) {
    viewMode.value = normalized
  }
})

watch(readingStructureMeta, () => {
  expandedReadingGroups.value = new Set()
  if (viewMode.value === 'reading') {
    nextTick(renderGraph)
  }
}, { deep: true })

watch(viewMode, () => {
  selectedItem.value = null
  emit('view-change', viewMode.value)
  nextTick(renderGraph)
})

// 监听边标签显示开关
watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
  if (linkLabelBgRef) {
    linkLabelBgRef.style('display', newVal ? 'block' : 'none')
  }
})

watch(showAuxiliaryLinks, () => {
  if (viewMode.value === 'reading') {
    nextTick(renderGraph)
  }
})

const handleResize = () => {
  nextTick(renderGraph)
}

// ── Focus node from URL (concept deep link) ──────────────────

const focusNodeFound = ref(false)
const focusNodeSection = ref('')
const focusNodeDisplayName = computed(() => {
  if (!props.focusNodeKey) return ''
  // concept_key format: "Type:name"
  const parts = props.focusNodeKey.split(':')
  return parts.length > 1 ? parts.slice(1).join(':') : props.focusNodeKey
})

function tryAutoFocusFromRoute() {
  if (!props.focusNodeKey || !props.graphData?.nodes?.length) return

  const conceptKey = props.focusNodeKey // e.g. "Technology:虚幻引擎5"
  const parts = conceptKey.split(':')
  const targetType = parts.length > 1 ? parts[0] : ''
  const targetName = parts.length > 1 ? parts.slice(1).join(':') : conceptKey

  // Find matching node in graph data
  const nodes = props.graphData.nodes || []
  let found = null

  // 1. Exact match by name + type label
  for (const node of nodes) {
    const nodeName = (node.name || '').toLowerCase()
    const nodeLabels = (node.labels || []).map(l => l.toLowerCase())
    if (
      nodeName === targetName.toLowerCase() &&
      (!targetType || nodeLabels.includes(targetType.toLowerCase()))
    ) {
      found = node
      break
    }
  }

  // 2. Fallback: name-only match
  if (!found) {
    for (const node of nodes) {
      if ((node.name || '').toLowerCase() === targetName.toLowerCase()) {
        found = node
        break
      }
    }
  }

  // 3. Fallback: fuzzy / contains match
  if (!found) {
    const target = targetName.toLowerCase()
    for (const node of nodes) {
      const name = (node.name || '').toLowerCase()
      if (name.includes(target) || target.includes(name)) {
        found = node
        break
      }
    }
  }

  if (found) {
    focusNodeFound.value = true

    // Select the node (open Node Details)
    const entityType = (found.labels || []).find(
      l => !['Entity', 'Node', '__Entity__'].includes(l)
    ) || 'Entity'
    selectedItem.value = {
      type: 'node',
      data: found,
      entityType,
      entityTypeLabel: TYPE_LABEL_MAP[entityType] || entityType,
    }

    // Find reading structure section this node belongs to
    // Strategy: use group_titles (maps entity type → group name in reading view)
    // and also check problem/solution/architecture summaries
    if (props.readingStructure) {
      const rs = props.readingStructure

      // 1. Try group_titles: entity type → reading group label
      const groupTitles = rs.group_titles || {}
      if (entityType && groupTitles[entityType]) {
        focusNodeSection.value = groupTitles[entityType]
      }

      // 2. Try problem/solution/architecture summary text match
      if (!focusNodeSection.value) {
        const nodeName = (found.name || '').toLowerCase()
        for (const [section, label] of [['problem', '核心问题'], ['solution', '核心方案'], ['architecture', '结构路径']]) {
          const sData = rs[section]
          if (!sData) continue
          const summary = (typeof sData === 'string' ? sData : sData.summary || '').toLowerCase()
          if (summary && nodeName.length >= 2 && summary.includes(nodeName)) {
            focusNodeSection.value = label
            break
          }
        }
      }
    }

    // Visual highlight + zoom to node in reading graph
    setTimeout(() => {
      if (_readingNodeGroup && _readingPositionedNodes) {
        // Find the D3 tree node matching this entity
        const nodeName = (found.name || '').toLowerCase()
        let targetTreeNode = null
        for (const [id, treeNode] of Object.entries(_readingPositionedNodes)) {
          if ((treeNode.data?.name || '').toLowerCase() === nodeName) {
            targetTreeNode = treeNode
            break
          }
        }

        // Highlight: reset all node borders, then highlight the target
        _readingNodeGroup.selectAll('rect')
          .attr('stroke', '#E2E2E8')
          .attr('stroke-width', 1.4)

        if (targetTreeNode && _readingZoomBehavior && _readingSvg) {
          // Find the <g> element for this node and highlight its rect
          _readingNodeGroup.selectAll('g').each(function(d) {
            if (d && d.data && (d.data.name || '').toLowerCase() === nodeName) {
              d3.select(this).select('rect')
                .attr('stroke', '#e53e3e')
                .attr('stroke-width', 3)
                .attr('filter', 'drop-shadow(0 0 6px rgba(229, 62, 62, 0.4))')
            }
          })

          // Zoom/pan to center the target node
          const container = _readingSvg.node()
          if (container) {
            const width = container.clientWidth || container.getBoundingClientRect().width || 800
            const height = container.clientHeight || container.getBoundingClientRect().height || 600
            const scale = 0.9
            const tx = width / 2 - targetTreeNode.y * scale
            const ty = height / 2 - targetTreeNode.x * scale
            const transform = d3.zoomIdentity.translate(tx, ty).scale(scale)
            _readingSvg.transition().duration(600).call(_readingZoomBehavior.transform, transform)
          }
        }
      }
    }, 600)
  } else {
    focusNodeFound.value = false
  }
}

// Trigger auto-focus after graph data loads and renders
watch(() => props.graphData, () => {
  if (props.focusNodeKey) {
    setTimeout(tryAutoFocusFromRoute, 800) // wait for D3 render
  }
}, { deep: true })

// Initial render is handled by the `watch(graphData, {immediate: true})` above,
// which runs on setup and again on every data change — both "already populated
// before mount" and "async-arrives-after-mount" go through the same path.
// renderGraph itself early-returns when graphSvg / graphData are missing.
onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (props.focusNodeKey && props.graphData?.nodes?.length) {
    setTimeout(tryAutoFocusFromRoute, 1000)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(255,255,255,0.95), rgba(255,255,255,0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.view-mode-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border: 1px solid #E0E0E0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}

.mode-btn {
  border: none;
  background: transparent;
  color: #666;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
  font-family: 'JetBrains Mono', monospace;
}

.mode-btn:hover {
  color: #222;
  background: rgba(0,0,0,0.04);
}

.mode-btn.active {
  color: #111;
  background: linear-gradient(135deg, rgba(255,107,53,0.14), rgba(0,78,137,0.1));
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.05);
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  font-size: 13px;
}

.tool-btn:hover {
  background: #F5F5F5;
  color: #000;
  border-color: #CCC;
}

.tool-btn .btn-text {
  font-size: 12px;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view, .graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

/* Entity Types Legend - Bottom Left */
.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}

.schema-summary {
  position: absolute;
  left: 24px;
  bottom: 126px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 360px;
  padding: 12px 14px;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  background: rgba(255,255,255,0.96);
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}

.schema-summary-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #555;
}

.schema-summary-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.schema-summary-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: #555;
  background: #F4F5F7;
  border: 1px solid #E3E5E8;
}

.schema-summary-pill.ok {
  color: #13653D;
  background: #EDF8F1;
  border-color: #C8E8D2;
}

.schema-summary-pill.warn {
  color: #8A5900;
  background: #FFF6E6;
  border-color: #F4D28E;
}

.schema-summary-pill.danger {
  color: #9E2A2B;
  background: #FFF1F1;
  border-color: #F1C8C8;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #555;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

/* Edge Labels Toggle - Top Right */
.edge-labels-toggle {
  position: absolute;
  top: 60px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #FFF;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  z-index: 10;
}

.reading-options {
  position: absolute;
  top: 108px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #FFF;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  z-index: 10;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #E0E0E0;
  border-radius: 22px;
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

input:checked + .slider {
  background-color: #7B2D8E;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.toggle-label {
  font-size: 12px;
  color: #666;
}

/* Detail Panel - Right Side */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  overflow: hidden;
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #FAFAFA;
  border-bottom: 1px solid #EEE;
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.detail-type-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  margin-left: auto;
  margin-right: 12px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #999;
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: #333;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: #888;
  font-size: 12px;
  font-weight: 500;
  min-width: 80px;
}

.detail-value {
  color: #333;
  flex: 1;
  word-break: break-word;
}

.detail-value-muted {
  color: #999;
}

.detail-value.uuid-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #666;
}

.detail-value.fact-text {
  line-height: 1.5;
  color: #444;
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #F0F0F0;
}

.schema-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid transparent;
}

.schema-pill.status-matched {
  color: #13653D;
  background: #EDF8F1;
  border-color: #C8E8D2;
}

.schema-pill.status-untyped {
  color: #6B7280;
  background: #F2F4F7;
  border-color: #D8DCE3;
}

.schema-pill.status-unexpected {
  color: #9E2A2B;
  background: #FFF1F1;
  border-color: #F1C8C8;
}

.schema-pill.status-projection {
  color: #245C7A;
  background: #EEF7FB;
  border-color: #C9E3EF;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 10px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: #888;
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: #333;
  flex: 1;
}

.summary-text {
  line-height: 1.6;
  color: #444;
  font-size: 12px;
}

/* Phase C: Global concept link card */
.global-concept-section { margin-top: 12px; }
.global-concept-card {
  background: #f8f9fc;
  border: 1px solid #d4dce8;
  border-left: 3px solid #6366f1;
  border-radius: 8px;
  padding: 10px 12px;
}
.gc-name { font-weight: 600; font-size: 13px; color: #1d1d1d; margin-bottom: 4px; }
.gc-meta { display: flex; gap: 8px; font-size: 11px; color: #6b7280; margin-bottom: 6px; }
.gc-type { background: #f3f4f6; padding: 1px 6px; border-radius: 4px; }
.gc-xrel { color: #6366f1; font-weight: 600; }
.gc-desc { font-size: 11px; color: #374151; line-height: 1.5; margin: 0 0 8px; }
.gc-actions { display: flex; flex-direction: column; gap: 6px; }
.gc-btn {
  display: inline-block; font-size: 12px; padding: 5px 10px; border-radius: 6px;
  background: #4a6fa5; color: #fff; text-decoration: none; text-align: center;
  transition: background 0.15s;
}
.gc-btn:hover { background: #3b5998; }
.gc-btn-secondary { background: #eef2ff; color: #4338ca; }
.gc-btn-secondary:hover { background: #e0e7ff; }
.gc-loading { font-size: 11px; color: #9ca3af; }

.schema-hint {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.55;
}

.schema-hint.status-untyped {
  color: #5F6368;
  background: #F6F7F9;
  border: 1px solid #E1E4EA;
}

.schema-hint.status-unexpected {
  color: #8A2D2D;
  background: #FFF4F4;
  border: 1px solid #F0D0D0;
}

.schema-hint.status-projection {
  color: #245C7A;
  background: #F2FAFD;
  border: 1px solid #CFE8F2;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  display: inline-block;
  padding: 4px 12px;
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  border-radius: 16px;
  font-size: 11px;
  color: #555;
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px 10px;
  background: #F8F8F8;
  border: 1px solid #E8E8E8;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #666;
  word-break: break-all;
}

/* Edge relation header */
.edge-relation-header {
  background: #F8F8F8;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  line-height: 1.5;
  word-break: break-word;
}

/* Building hint */
.graph-building-hint {
  position: absolute;
  bottom: 160px; /* Moved up from 80px */
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-weight: 500;
  letter-spacing: 0.5px;
  z-index: 100;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 18px;
  height: 18px;
  color: #4CAF50;
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(76, 175, 80, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(76, 175, 80, 0.6)); }
}

/* 模拟结束后的提示样式 */
.graph-building-hint.finished-hint {
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 18px;
  height: 18px;
  color: #FFF;
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: #FFF;
  transition: all 0.2s;
  margin-left: 8px;
  flex-shrink: 0;
}

.hint-close-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: scale(1.1);
}

/* Loading spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0E0E0;
  border-top-color: #7B2D8E;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

/* Self-loop styles */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #E8F5E9 0%, #F1F8E9 100%);
  border: 1px solid #C8E6C9;
}

.self-loop-count {
  margin-left: auto;
  font-size: 11px;
  color: #666;
  background: rgba(255,255,255,0.8);
  padding: 2px 8px;
  border-radius: 10px;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-loop-item {
  background: #FAFAFA;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #F5F5F5;
  cursor: pointer;
  transition: background 0.2s;
}

.self-loop-item-header:hover {
  background: #EEEEEE;
}

.self-loop-item.expanded .self-loop-item-header {
  background: #E8E8E8;
}

.self-loop-index {
  font-size: 10px;
  font-weight: 600;
  color: #888;
  background: #E0E0E0;
  padding: 2px 6px;
  border-radius: 4px;
}

.self-loop-name {
  font-size: 12px;
  font-weight: 500;
  color: #333;
  flex: 1;
}

.self-loop-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #888;
  background: #E0E0E0;
  border-radius: 4px;
  transition: all 0.2s;
}

.self-loop-item.expanded .self-loop-toggle {
  background: #D0D0D0;
  color: #666;
}

.self-loop-item-content {
  padding: 12px;
  border-top: 1px solid #EAEAEA;
}

.self-loop-item-content .detail-row {
  margin-bottom: 8px;
}

.self-loop-item-content .detail-label {
  font-size: 11px;
  min-width: 60px;
}

.self-loop-item-content .detail-value {
  font-size: 12px;
}

.self-loop-episodes {
  margin-top: 8px;
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
}

.episode-tag.small {
  padding: 3px 6px;
  font-size: 9px;
}

/* Focus banner (concept deep link from registry) */
.focus-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: linear-gradient(90deg, #eef3ff 0%, #f0f4ff 100%);
  border-bottom: 1px solid #c4d5f0;
  font-size: 13px;
  color: #2c5282;
  flex-wrap: wrap;
}
.focus-banner-text {
  flex: 1;
}
.focus-banner-text strong {
  color: #1a365d;
}
.focus-banner-warn {
  color: #c62828;
  font-size: 12px;
}
.focus-banner-hint {
  font-size: 11px;
  color: #7a8090;
  margin-left: auto;
}
</style>
