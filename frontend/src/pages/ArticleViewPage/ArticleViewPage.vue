<template>
  <section class="article-view">
    <!-- Compact project metadata bar (replaces the old 3-card grid) -->
    <header class="meta-bar">
      <div class="meta-group">
        <span class="meta-label">项目</span>
        <span class="meta-value" :title="project?.name">{{ project?.name || '—' }}</span>
      </div>
      <div class="meta-group">
        <span class="meta-label">图谱</span>
        <span class="meta-value">{{ graphNodeCount }} 节点 · {{ graphEdgeCount }} 关系</span>
      </div>
      <div class="meta-group">
        <span class="meta-label">状态</span>
        <span class="meta-value" :class="`status-${project?.status || 'unknown'}`">{{ project?.status || 'unknown' }}</span>
      </div>
      <div class="meta-group">
        <span class="meta-label">构建</span>
        <span class="meta-value">{{ buildStatus }}{{ successRatio ? ` · ${successRatio}` : '' }}</span>
      </div>
      <button
        class="refresh-btn"
        :disabled="refreshing"
        @click="$emit('refresh')"
        title="重新拉取项目状态和图谱"
      >
        <span class="icon">⟳</span>
        <span class="label">{{ refreshing ? '刷新中...' : '刷新' }}</span>
      </button>
    </header>

    <!-- 子 tab:图谱视图 / 文章原文。懒加载原文 — 只在切到原文 tab 时才拉 raw API。 -->
    <nav class="sub-tabs" aria-label="文章视图">
      <button
        class="sub-tab"
        :class="{ active: subTab === 'graph' }"
        @click="subTab = 'graph'"
      >图谱视图</button>
      <button
        class="sub-tab"
        :class="{ active: subTab === 'raw' }"
        @click="subTab = 'raw'"
      >文章原文</button>
    </nav>

    <!-- 图谱子 tab:摘要 + 失败面板 + GraphPanel -->
    <template v-if="subTab === 'graph'">
      <!-- Failure panel — only shows when build is not clean -->
      <article v-if="hasFailureDetails" :class="['failure-panel', failureSeverityClass]">
        <div class="failure-head">
          <span class="failure-icon" aria-hidden="true">{{ failureIcon }}</span>
          <span class="failure-heading">{{ failureHeading }}</span>
        </div>
        <p v-if="failureReason" class="failure-reason">{{ failureReason }}</p>
        <div v-if="failureAbortInfo" class="metric-line">{{ failureAbortInfo }}</div>
        <div v-if="failureWarnings.length" class="failure-warnings">
          <div class="subsection-title">告警 ({{ failureWarnings.length }})</div>
          <ul>
            <li v-for="(warning, index) in failureWarnings" :key="index">{{ warning }}</li>
          </ul>
        </div>
        <div v-if="failureSuccessRatio" class="metric-line">
          已完成比例：{{ failureSuccessRatio }}
        </div>
      </article>

      <!-- Analysis summary (compact) -->
      <article v-if="project?.analysis_summary" class="summary-panel">
        <div class="summary-label">分析摘要</div>
        <p class="summary-text">{{ project.analysis_summary }}</p>
      </article>

      <!-- Interactive graph panel — the new P2 addition that closes T1 path -->
      <div v-if="hasGraph" class="graph-wrapper">
        <GraphPanel
          :graphData="graphData"
          :loading="false"
          :currentPhase="4"
          :initialView="currentView"
          :readingStructure="project?.reading_structure || null"
          :schemaEntityTypes="project?.ontology?.entity_types || []"
          :schemaRelationTypes="project?.ontology?.edge_types || []"
          :focusNodeKey="focusNodeKey"
          :fromSource="fromSource"
          :domain="project?.domain || 'tech'"
          @refresh="$emit('refresh')"
          @view-change="handleViewChange"
        />
      </div>
      <div v-else class="graph-empty">
        <div class="empty-icon">🗺️</div>
        <div class="empty-title">暂无图谱数据</div>
        <p class="empty-body">
          项目尚未构建图谱。请先在自动处理队列提交抽取任务，或刷新查看最新构建状态。
        </p>
        <div class="empty-actions">
          <button class="empty-btn primary" :disabled="refreshing" @click="$emit('refresh')">
            <span class="icon">⟳</span> {{ refreshing ? '刷新中...' : '刷新状态' }}
          </button>
          <router-link to="/workspace/auto" class="empty-btn">进入自动处理队列 →</router-link>
        </div>
        <p class="empty-footer">
          旧版 5 步流程仍可通过
          <router-link :to="`/process/${project?.project_id}`" class="inline-link">旧版流程页 ↗</router-link>
          访问（过渡期保留）。
        </p>
      </div>
    </template>

    <!-- 文章原文子 tab:懒加载 — 只在用户切到这个 tab 时 ArticleRawPanel onMounted 才拉 API。 -->
    <ArticleRawPanel
      v-else-if="subTab === 'raw' && project?.project_id"
      :project-id="project.project_id"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../../components/GraphPanel.vue'
import ArticleRawPanel from './ArticleRawPanel.vue'
import { normalizeGraphPanelView } from '../../utils/workbenchLayout'

// 图谱 vs 原文 子 tab。默认图谱(保持原有行为);原文懒加载。
const subTab = ref('graph')

const props = defineProps({
  project: { type: Object, default: null },
  graphData: { type: Object, default: null },
  phase1TaskResult: { type: Object, default: null },
  refreshing: { type: Boolean, default: false },
  // Parent WorkspacePage passes embedded=true so we inherit its AppShell — ArticleViewPage
  // itself never wraps in AppShell, so this prop is just absorbed here as a no-op marker.
  embedded: { type: Boolean, default: false },
})

defineEmits(['refresh'])

const route = useRoute()
const router = useRouter()

const graphNodeCount = computed(() => props.graphData?.node_count ?? props.graphData?.nodes?.length ?? 0)
const graphEdgeCount = computed(() => props.graphData?.edge_count ?? props.graphData?.edges?.length ?? 0)
const hasGraph = computed(() => graphNodeCount.value > 0 || (Array.isArray(props.graphData?.nodes) && props.graphData.nodes.length > 0))

const successRatio = computed(() => {
  const raw = props.phase1TaskResult?.build_outcome?.success_ratio
  return typeof raw === 'number' ? `${Math.round(raw * 100)}%` : ''
})
const buildStatus = computed(() => props.phase1TaskResult?.build_outcome?.status || 'unknown')

// URL state: `?view=graph|reading` controls which GraphPanel mode renders.
// `?focus=nodeKey` targets a specific node (used by cross-layer links like
// "打开来源文章" from ConceptDetailPage).
const currentView = computed(() => normalizeGraphPanelView(route.query.view))
const focusNodeKey = computed(() => route.query.focus || route.query.focusNode || '')
const fromSource = computed(() => route.query.from || '')

function handleViewChange(nextView) {
  const normalized = normalizeGraphPanelView(nextView)
  if (normalized === route.query.view) return
  // Preserve other query params (focus, from) so deep-links survive view toggles.
  router.replace({ query: { ...route.query, view: normalized } })
}

// ---------------------------------------------------------------------------
// Failure panel (kept from original ArticleViewPage — still useful info)
// ---------------------------------------------------------------------------
const FAILURE_STATUS_META = {
  failed: { heading: '构建失败', icon: '✖', severity: 'failure-panel--error' },
  cancelled: { heading: '已取消', icon: '⊘', severity: 'failure-panel--cancel' },
  timeout: { heading: '超时中止', icon: '⏱', severity: 'failure-panel--error' },
  completed_with_warnings: { heading: '完成但有告警', icon: '⚠', severity: 'failure-panel--warn' },
}

const buildOutcome = computed(() => props.phase1TaskResult?.build_outcome || null)
const diagnostics = computed(() => props.phase1TaskResult?.diagnostics || null)

const hasFailureDetails = computed(() => {
  const status = buildOutcome.value?.status
  return status && status in FAILURE_STATUS_META
})
const failureMeta = computed(() => FAILURE_STATUS_META[buildOutcome.value?.status] || null)
const failureHeading = computed(() => failureMeta.value?.heading || '构建异常')
const failureIcon = computed(() => failureMeta.value?.icon || '!')
const failureSeverityClass = computed(() => failureMeta.value?.severity || 'failure-panel--warn')

const failureReason = computed(() => {
  const raw = buildOutcome.value?.reason
  return typeof raw === 'string' && raw.trim() ? raw.trim() : ''
})
const failureWarnings = computed(() => {
  const raw = buildOutcome.value?.warnings
  if (!Array.isArray(raw)) return []
  return raw.filter((w) => typeof w === 'string' && w.trim()).map((w) => w.trim())
})
const failureAbortInfo = computed(() => {
  const d = diagnostics.value
  if (!d) return ''
  const parts = []
  if (typeof d.aborted_chunk_index === 'number') parts.push(`中止于 chunk ${d.aborted_chunk_index + 1}`)
  if (d.aborted_due_to_rate_limit) parts.push('触发上游限流')
  if (d.abort_reason) parts.push(`原因：${d.abort_reason}`)
  return parts.join(' · ')
})
const failureSuccessRatio = computed(() => {
  const raw = buildOutcome.value?.success_ratio
  return typeof raw === 'number' ? `${Math.round(raw * 100)}%` : ''
})
</script>

<style scoped>
/* Inherits height via flex:1 chain from AppShell → WorkspacePage.
   min-height: 0 lets the graph wrapper (another flex:1 descendant) actually
   fill remaining space without overflowing its siblings. */
.article-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

/* Compact meta bar — replaces the old 3-card grid, saves ~120px vertical */
.meta-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
  padding: 10px 16px;
  border: 1px solid var(--border-default);
  background: rgba(255, 255, 255, 0.75);
  border-radius: 12px;
}
.meta-group {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.meta-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-group-label);
}
.meta-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-graph_completed { color: #2e7d32; }
.status-graph_building { color: #e65100; }
.status-failed { color: #c62828; }

/* 子 tab(图谱 / 原文)— 视觉上比 WorkspacePage 的一级 tab 轻量 */
.sub-tabs {
  display: flex;
  gap: 4px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid var(--border-default);
  border-radius: 10px;
  width: fit-content;
}
.sub-tab {
  padding: 6px 16px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
  transition: background 120ms ease, color 120ms ease;
}
.sub-tab:hover { color: var(--accent-primary-hover); }
.sub-tab.active {
  background: var(--accent-primary);
  color: #fff;
  font-weight: 700;
}

.refresh-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: #fff;
  color: var(--accent-primary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.refresh-btn:hover:not(:disabled) { background: var(--bg-muted); border-color: var(--border-strong); }
.refresh-btn:disabled { opacity: 0.6; cursor: wait; }

/* Graph fills remaining vertical space via the flex chain. `min-height: 480px`
   is a floor so the graph is legible on short viewports (meta-bar + failure
   panel + summary could otherwise squeeze it below usable size). When a floor
   kicks in, AppShell's overflow-y:auto lets the page scroll. On tall monitors
   flex:1 takes over and gives the graph the full remainder. */
.graph-wrapper {
  flex: 1;
  min-height: 480px;
  border: 1px solid var(--border-default);
  border-radius: 16px;
  background: #fff;
  overflow: hidden;
  display: flex;
}
.graph-wrapper > :deep(.graph-panel) {
  flex: 1;
  min-width: 0;
}

/* Empty state */
.graph-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 20px;
  border: 1px dashed var(--border-default);
  border-radius: 16px;
  text-align: center;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.6);
}
.empty-icon { font-size: 36px; }
.empty-title { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.empty-body { font-size: 13px; margin: 0; max-width: 420px; line-height: 1.6; }
.empty-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  flex-wrap: wrap;
  justify-content: center;
}
.empty-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 10px;
  border: 1px solid var(--border-default);
  background: #fff;
  color: var(--accent-primary);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
}
.empty-btn:hover:not(:disabled) { background: var(--bg-muted); border-color: var(--border-strong); }
.empty-btn.primary {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: #fff;
}
.empty-btn.primary:hover:not(:disabled) { background: var(--accent-primary-hover); border-color: var(--accent-primary-hover); }
.empty-btn:disabled { opacity: 0.6; cursor: wait; }
.empty-footer {
  font-size: 11px;
  color: var(--text-muted);
  margin: 12px 0 0;
  max-width: 420px;
}
.inline-link { color: var(--accent-primary); text-decoration: underline; }

/* Analysis summary */
.summary-panel {
  padding: 12px 16px;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: rgba(255, 253, 250, 0.9);
}
.summary-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-group-label);
  margin-bottom: 4px;
}
.summary-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-primary);
}

/* Failure panel */
.failure-panel {
  padding: 14px 18px;
  border: 1px solid var(--border-default);
  border-left-width: 4px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
}
.failure-panel--error {
  border-left-color: #b91c1c;
  background: linear-gradient(180deg, #fff5f5 0%, #ffecec 100%);
}
.failure-panel--cancel {
  border-left-color: #6b21a8;
  background: linear-gradient(180deg, #faf5ff 0%, #f3e8ff 100%);
}
.failure-panel--warn {
  border-left-color: #b45309;
  background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
}
.failure-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-weight: 700;
  color: var(--text-primary);
}
.failure-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.08);
  font-size: 13px;
}
.failure-reason {
  margin: 4px 0 6px;
  color: #3b2a1f;
  font-size: 13px;
}
.metric-line {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.failure-warnings .subsection-title {
  font-size: 11px;
  color: #6b4a24;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 8px 0 4px;
}
.failure-warnings ul { margin: 0; padding-left: 18px; }
.failure-warnings li { color: #4a3425; line-height: 1.55; font-size: 12px; }
</style>
