<template>
  <section class="phase2-page">
    <div class="section-badge">Concept Registry</div>
    <h2 class="section-title">项目内概念总览</h2>
    <p class="section-copy">
      这一页先固定成 `project-scoped` 的只读概念候选总览，不提前承诺 canonical 写回、跨项目归一或自动 merge。
    </p>

    <div class="summary-grid">
      <article class="card">
        <div class="card-title">当前上下文</div>
        <div class="metric-line">项目：{{ conceptMeta.projectName || project?.name || '暂无' }}</div>
        <div class="metric-line">来源范围：{{ conceptMeta.sourceScope || 'project_graph' }}</div>
        <div class="metric-line">Phase 1 状态：{{ conceptMeta.phase1Status || phase1TaskResult?.build_outcome?.status || 'unknown' }}</div>
      </article>

      <article class="card">
        <div class="card-title">概念候选统计</div>
        <div class="metric-line">候选概念：{{ conceptSummary.candidateConceptCount }}</div>
        <div class="metric-line">类型化节点：{{ conceptSummary.typedNodeCount }}</div>
        <div class="metric-line">Warning：{{ conceptSummary.warningsCount }}</div>
      </article>

      <article class="card">
        <div class="card-title">当前图谱快照</div>
        <div class="metric-line">节点：{{ conceptSummary.nodeCount || graphNodeCount }}</div>
        <div class="metric-line">关系：{{ conceptSummary.edgeCount || graphEdgeCount }}</div>
        <div class="metric-line">完整度：{{ dataCompletenessLabel }}</div>
      </article>
    </div>

    <div v-if="conceptStore.error" class="state-card error-card">
      <div class="card-title">概念视图加载失败</div>
      <div class="metric-line">{{ conceptStore.error }}</div>
    </div>

    <div v-else-if="conceptStore.loading" class="state-card">
      <div class="card-title">正在聚合概念候选</div>
      <div class="metric-line">复用当前项目图谱，先把 project-scoped 候选概念汇总出来。</div>
    </div>

    <div v-else class="concept-layout">
      <article class="card queue-card">
        <div class="card-header">
          <div class="card-title">候选概念</div>
          <div class="pill">{{ conceptStore.items.length }}</div>
        </div>
        <p class="section-copy mini-copy">
          这里先展示当前项目图谱里最值得进入概念治理的候选项，不直接生成 canonical 决策。
        </p>

        <div v-if="!conceptStore.items.length" class="empty-state">
          {{ conceptDiagnostics.emptyReason || '当前项目还没有足够的图谱节点用于生成概念候选。' }}
        </div>

        <div v-else class="candidate-list">
          <button
            v-for="item in conceptStore.items"
            :key="item.key"
            type="button"
            class="candidate-button"
            :class="{ active: item.key === conceptStore.selectedId }"
            @click="selectConcept(item.key)"
          >
            <div class="candidate-topline">
              <span class="candidate-name">{{ item.displayName }}</span>
              <span :class="['candidate-status', statusChipClass(item.status)]">{{ statusLabel(item.status) }}</span>
            </div>
            <div class="candidate-meta">{{ item.conceptType }} · 提及 {{ item.mentionCount }} 次 · 连接 {{ item.connectedCount }}</div>
          </button>
        </div>
      </article>

      <article class="card detail-card">
        <div class="card-header">
          <div>
            <div class="detail-kicker">Selected Candidate</div>
            <h3 class="detail-title">{{ selectedConcept.displayName || '未选择候选概念' }}</h3>
          </div>
          <div class="detail-badges">
            <span class="chip">{{ selectedConcept.conceptType || 'Node' }}</span>
            <span :class="['chip', statusChipClass(selectedConcept.status)]">{{ statusLabel(selectedConcept.status) }}</span>
          </div>
        </div>

        <div v-if="selectedConcept.key" class="detail-grid">
          <div class="metric-card">
            <div class="metric-label">提及次数</div>
            <div class="metric-value">{{ selectedConcept.mentionCount }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">连接强度</div>
            <div class="metric-value">{{ selectedConcept.connectedCount }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">来源节点</div>
            <div class="metric-value">{{ selectedConcept.sourceNodeIds.length }}</div>
          </div>
        </div>

        <div v-if="selectedConcept.key" class="detail-sections">
          <section class="detail-section">
            <div class="subsection-title">候选证据</div>
            <ul class="evidence-list">
              <li v-for="item in selectedConcept.sampleEvidence" :key="item">{{ item }}</li>
            </ul>
            <div v-if="!selectedConcept.sampleEvidence.length" class="empty-note">当前候选还没有可展示的摘要证据。</div>
          </section>

          <section class="detail-section">
            <div class="subsection-title">来源节点 ID</div>
            <div class="chip-wrap">
              <span v-for="nodeId in selectedConcept.sourceNodeIds" :key="nodeId" class="chip soft">{{ nodeId }}</span>
            </div>
            <div v-if="!selectedConcept.sourceNodeIds.length" class="empty-note">暂无来源节点 ID。</div>
          </section>
        </div>

        <div v-else class="empty-state">
          当前还没有可选的概念候选。先等图谱构建完成，或者补充 Phase 1 快照后再进入概念治理。
        </div>
      </article>

      <article class="card diagnostics-card">
        <div class="card-title">诊断信息</div>
        <div class="metric-line">数据完整度：{{ dataCompletenessLabel }}</div>
        <div class="metric-line">候选类型分布：</div>
        <div class="chip-wrap">
          <span
            v-for="item in conceptDiagnostics.typeCounts"
            :key="`${item.type}-${item.count}`"
            class="chip soft"
          >
            {{ item.type }} {{ item.count }}
          </span>
        </div>

        <div class="subsection-title warning-title">Phase 1 Warnings</div>
        <ul v-if="conceptDiagnostics.warnings.length" class="warning-list">
          <li v-for="warning in conceptDiagnostics.warnings" :key="warning">{{ warning }}</li>
        </ul>
        <div v-else class="empty-note">当前没有额外 warning。</div>

        <div v-if="conceptDiagnostics.emptyReason" class="diagnostic-block">
          <div class="subsection-title">空结果说明</div>
          <p class="section-copy mini-copy">{{ conceptDiagnostics.emptyReason }}</p>
        </div>

        <div class="diagnostic-block">
          <div class="subsection-title">当前边界</div>
          <p class="section-copy mini-copy">
            这是项目内候选概念视图，不是 canonical registry 真相源，也不负责自动合并、跨项目写回和人工审核动作。
          </p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, watch } from 'vue'
import { conceptStore, loadConceptView, selectConcept } from '../../stores/conceptStore'

const props = defineProps({
  project: {
    type: Object,
    default: null,
  },
  graphData: {
    type: Object,
    default: null,
  },
  phase1TaskResult: {
    type: Object,
    default: null,
  },
})

const graphNodeCount = computed(() => props.graphData?.node_count ?? props.graphData?.nodes?.length ?? 0)
const graphEdgeCount = computed(() => props.graphData?.edge_count ?? props.graphData?.edges?.length ?? 0)
const conceptMeta = computed(() => conceptStore.meta || {})
const conceptSummary = computed(() => conceptStore.summary || {})
const conceptDiagnostics = computed(() => conceptStore.diagnostics || {})
const selectedConcept = computed(() => conceptStore.selectedConcept || {})

const dataCompletenessLabelMap = {
  empty: '未生成',
  graph_empty: '图谱为空',
  graph_only: '仅图谱',
  graph_with_phase1_snapshot: '图谱 + Phase 1 快照',
}

const dataCompletenessLabel = computed(() => (
  dataCompletenessLabelMap[conceptDiagnostics.value.dataCompleteness] || conceptDiagnostics.value.dataCompleteness || 'unknown'
))

// Map backend status → Chinese label shown on chips.
// The backend concept_decisions writeback path uses accepted / canonical /
// rejected / pending / unreviewed. 'reviewed' is an older label kept for
// backwards compatibility with pre-2026-04 projects.
const STATUS_LABEL_MAP = {
  accepted: '已接受',
  canonical: '已接受',
  rejected: '已拒绝',
  pending: '待定',
  unreviewed: '未处理',
  reviewed: '已处理',
}

// Chip color class for the status badge. Tied to the new CSS rules at the
// bottom of the file so green = accepted/canonical, red = rejected,
// orange = pending, gray = unreviewed / reviewed / unknown.
const STATUS_CHIP_CLASS_MAP = {
  accepted: 'status-accepted',
  canonical: 'status-accepted',
  rejected: 'status-rejected',
  pending: 'status-pending',
  unreviewed: 'status-unreviewed',
  reviewed: 'status-unreviewed',
}

function statusLabel(status) {
  return STATUS_LABEL_MAP[status] || '未处理'
}

function statusChipClass(status) {
  return STATUS_CHIP_CLASS_MAP[status] || 'status-unreviewed'
}

watch(
  () => props.project?.project_id,
  async () => {
    await loadConceptView({
      projectId: props.project?.project_id,
      project: props.project,
    })
  },
  { immediate: true },
)
</script>

<style scoped>
.phase2-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #966a31;
  font-weight: 700;
}

.section-title {
  margin: 0;
  font-size: 28px;
  color: #181818;
}

.section-copy,
.metric-line {
  color: #62584d;
  line-height: 1.6;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.card,
.state-card {
  border: 1px solid #eadfcb;
  background: linear-gradient(180deg, #fffdfa 0%, #fff7eb 100%);
  border-radius: 18px;
  padding: 18px;
}

.error-card {
  border-color: #e2b0a8;
  background: #fff8f6;
}

.card-title {
  font-weight: 700;
  color: #211c18;
  margin-bottom: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.mini-copy {
  font-size: 13px;
  margin: 0;
}

.pill,
.chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid #e7d0ad;
  color: #8f6c38;
  background: rgba(255, 250, 241, 0.95);
  font-size: 12px;
  font-weight: 600;
}

.chip.soft {
  background: rgba(255, 255, 255, 0.72);
  color: #6e5d48;
}

.concept-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(240px, 300px);
  gap: 16px;
  align-items: start;
}

.queue-card,
.detail-card,
.diagnostics-card {
  min-height: 100%;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.candidate-button {
  width: 100%;
  text-align: left;
  border: 1px solid #eadfcb;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 16px;
  padding: 14px;
  cursor: pointer;
  transition: border-color 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}

.candidate-button:hover,
.candidate-button.active {
  border-color: #d39c4a;
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(65, 42, 15, 0.08);
}

.candidate-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.candidate-name {
  color: #1e1813;
  font-weight: 700;
}

.candidate-status,
.candidate-meta,
.detail-kicker,
.metric-label,
.subsection-title,
.empty-note,
.empty-state {
  color: #7a6956;
  font-size: 13px;
  line-height: 1.6;
}

/* Status chip color variants (Gap #5 fix). Applied to both the list-row
   .candidate-status span and the detail-panel .chip span via v-bind. */
.candidate-status.status-accepted,
.chip.status-accepted {
  color: #166534;
  background: rgba(22, 163, 74, 0.14);
  border: 1px solid rgba(22, 163, 74, 0.35);
  border-radius: 10px;
  padding: 2px 8px;
  font-weight: 600;
}
.candidate-status.status-rejected,
.chip.status-rejected {
  color: #9b1c1c;
  background: rgba(220, 38, 38, 0.12);
  border: 1px solid rgba(220, 38, 38, 0.35);
  border-radius: 10px;
  padding: 2px 8px;
  font-weight: 600;
}
.candidate-status.status-pending,
.chip.status-pending {
  color: #9a3412;
  background: rgba(234, 88, 12, 0.12);
  border: 1px solid rgba(234, 88, 12, 0.35);
  border-radius: 10px;
  padding: 2px 8px;
  font-weight: 600;
}
.candidate-status.status-unreviewed,
.chip.status-unreviewed {
  color: #52525b;
  background: rgba(82, 82, 91, 0.08);
  border: 1px solid rgba(82, 82, 91, 0.25);
  border-radius: 10px;
  padding: 2px 8px;
}

.detail-title {
  margin: 6px 0 0;
  font-size: 28px;
  color: #1a1713;
}

.detail-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.metric-card {
  border: 1px solid #eadfcb;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.62);
  padding: 14px;
}

.metric-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
  color: #1b1712;
}

.detail-sections {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 18px;
}

.evidence-list,
.warning-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #4c4339;
  line-height: 1.7;
}

.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.warning-title,
.diagnostic-block {
  margin-top: 18px;
}

@media (max-width: 1240px) {
  .concept-layout {
    grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  }

  .diagnostics-card {
    grid-column: span 2;
  }
}

@media (max-width: 960px) {
  .concept-layout {
    grid-template-columns: 1fr;
  }

  .diagnostics-card {
    grid-column: auto;
  }
}
</style>
