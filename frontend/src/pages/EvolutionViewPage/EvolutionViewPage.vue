<template>
  <section class="phase2-page">
    <div class="section-badge">Evolution</div>
    <h2 class="section-title">演化就绪度快照</h2>
    <p class="section-copy">
      当前先做项目内演化就绪度快照，不假装已经具备完整的历史时间轴、canonical 演化日志或审计流。
    </p>

    <div class="summary-grid">
      <article class="card">
        <div class="card-title">时间锚点</div>
        <div class="metric-line">项目创建：{{ evolutionProjectOverview.createdAt || project?.created_at || '暂无' }}</div>
        <div class="metric-line">最近刷新：{{ evolutionMeta.generatedAt || project?.updated_at || '暂无' }}</div>
        <div class="metric-line">Phase 1 状态：{{ evolutionMeta.phase1Status || phase1TaskResult?.build_outcome?.status || 'unknown' }}</div>
      </article>

      <article class="card">
        <div class="card-title">项目基线</div>
        <div class="metric-line">节点：{{ evolutionProjectOverview.graphNodeCount || graphNodeCount }}</div>
        <div class="metric-line">关系：{{ evolutionProjectOverview.graphEdgeCount || graphEdgeCount }}</div>
        <div class="metric-line">时间信号：{{ timestampCoverageLabel }}</div>
      </article>

      <article class="card">
        <div class="card-title">可用来源</div>
        <div class="metric-line">来源：{{ generatedFromLabel }}</div>
        <div class="metric-line">完整度：{{ dataCompletenessLabel }}</div>
        <div class="metric-line">有阅读骨架：{{ evolutionProjectOverview.hasReadingStructure ? '是' : '否' }}</div>
      </article>
    </div>

    <div v-if="evolutionStore.error" class="state-card error-card">
      <div class="card-title">演化视图加载失败</div>
      <div class="metric-line">{{ evolutionStore.error }}</div>
    </div>

    <div v-else-if="evolutionStore.loading" class="state-card">
      <div class="card-title">正在聚合增长快照</div>
      <div class="metric-line">优先展示真实可用的时间锚点和图谱活动，不先伪造时间轴。</div>
    </div>

    <div v-else class="evolution-layout">
      <article class="card snapshot-card">
        <div class="card-title">Project Overview</div>
        <div class="metric-line">有图谱：{{ evolutionProjectOverview.hasGraph ? '是' : '否' }}</div>
        <div class="metric-line">有阅读骨架：{{ evolutionProjectOverview.hasReadingStructure ? '是' : '否' }}</div>
        <div class="metric-line">有分析摘要：{{ evolutionProjectOverview.hasAnalysisSummary ? '是' : '否' }}</div>
        <p class="section-copy mini-copy">
          当前这页回答的是“项目已经形成了哪些知识资产”，不是“这些资产如何随历史演化”。
        </p>
      </article>

      <article class="card asset-card">
        <div class="card-title">Knowledge Asset Snapshot</div>
        <div class="asset-grid">
          <div class="asset-item">
            <div class="metric-label">阅读骨架</div>
            <div class="metric-line">{{ evolutionAssetSnapshot.readingStructureStatus }}</div>
          </div>
          <div class="asset-item">
            <div class="metric-label">分析摘要</div>
            <div class="metric-line">{{ evolutionAssetSnapshot.analysisSummaryStatus }}</div>
          </div>
          <div class="asset-item">
            <div class="metric-label">图谱状态</div>
            <div class="metric-line">{{ evolutionAssetSnapshot.graphStatus }}</div>
          </div>
          <div class="asset-item">
            <div class="metric-label">可用视图</div>
            <div class="metric-line">{{ evolutionAssetSnapshot.availableViews.join(' / ') || '暂无' }}</div>
          </div>
        </div>

        <div class="subsection-title warning-title">Evidence Counts</div>
        <div class="metric-line">节点：{{ evolutionAssetSnapshot.evidenceCounts.nodes }}</div>
        <div class="metric-line">关系：{{ evolutionAssetSnapshot.evidenceCounts.edges }}</div>
        <div class="metric-line">阅读分组：{{ evolutionAssetSnapshot.evidenceCounts.readingGroupsCount }}</div>
        <div class="metric-line">Warnings：{{ evolutionAssetSnapshot.evidenceCounts.warningsCount }}</div>
      </article>

      <article class="card diagnostics-card">
        <div class="card-title">Traceability & Gaps</div>
        <div class="metric-line">supports_time_ordering：{{ evolutionSignalQuality.supportsTimeOrdering }}</div>
        <div class="metric-line">节点时间覆盖：{{ evolutionSignalQuality.timeSignals.nodeCreatedAtCoverage }}</div>
        <div class="metric-line">关系时间覆盖：{{ evolutionSignalQuality.timeSignals.edgeCreatedAtCoverage }}</div>
        <div class="metric-line">历史序列：{{ evolutionSignalQuality.confidenceFlags.historicalSeriesAvailable ? '有' : '无' }}</div>

        <div class="subsection-title warning-title">Derivation Notes</div>
        <ul class="signal-list">
          <li v-for="item in evolutionSignalQuality.derivationNotes" :key="item">{{ item }}</li>
        </ul>

        <div class="subsection-title warning-title">Warnings</div>
        <ul v-if="evolutionDiagnostics.warnings.length" class="signal-list">
          <li v-for="warning in evolutionDiagnostics.warnings" :key="warning">{{ warning }}</li>
        </ul>
        <div v-else class="empty-note">当前没有额外 warning。</div>

        <div class="diagnostic-block">
          <div class="subsection-title">Next Capability Gap</div>
          <div class="metric-line">readiness_level：{{ evolutionGap.readinessLevel }}</div>
          <div class="mini-copy">{{ evolutionGap.recommendedNextStep }}</div>
          <ul class="signal-list">
            <li v-for="item in evolutionGap.missingCapabilities" :key="item">{{ item }}</li>
          </ul>
        </div>

        <div class="diagnostic-block">
          <div class="subsection-title">当前边界</div>
          <ul class="signal-list">
            <li>{{ evolutionDiagnostics.emptyReason || '当前只提供项目内演化就绪度快照。' }}</li>
          </ul>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, watch } from 'vue'
import { evolutionStore, loadEvolutionView } from '../../stores/evolutionStore'

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
const evolutionMeta = computed(() => evolutionStore.meta || {})
const evolutionProjectOverview = computed(() => evolutionStore.projectOverview || {})
const evolutionAssetSnapshot = computed(() => evolutionStore.knowledgeAssetSnapshot || {})
const evolutionSignalQuality = computed(() => evolutionStore.traceabilityAndSignalQuality || {})
const evolutionGap = computed(() => evolutionStore.nextCapabilitiesGap || {})
const evolutionDiagnostics = computed(() => evolutionStore.diagnostics || {})

const dataCompletenessLabelMap = {
  empty: '未生成',
  project_metadata_only: '仅项目时间锚点',
  project_graph_no_timestamps: '图谱可用但缺少 created_at',
  snapshot_with_timestamp_diagnostics: '快照 + 时间诊断',
}

const generatedFromLabel = computed(() => (
  Array.isArray(evolutionMeta.value.generatedFrom) && evolutionMeta.value.generatedFrom.length
    ? evolutionMeta.value.generatedFrom.join(' / ')
    : '暂无'
))

const dataCompletenessLabel = computed(() => (
  dataCompletenessLabelMap[evolutionDiagnostics.value.dataCompleteness] || evolutionDiagnostics.value.dataCompleteness || 'unknown'
))

const timestampCoverageLabel = computed(() => (
  `${evolutionSignalQuality.value.timeSignals?.nodeCreatedAtCoverage || 'unknown'} / ${evolutionSignalQuality.value.timeSignals?.edgeCreatedAtCoverage || 'unknown'}`
))

watch(
  () => props.project?.project_id,
  async () => {
    await loadEvolutionView({
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

.mini-copy,
.detail-kicker,
.subsection-title,
.empty-note,
.empty-state,
.candidate-status,
.candidate-meta {
  color: #7a6956;
  font-size: 13px;
  line-height: 1.6;
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

.evolution-layout {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.asset-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.asset-item {
  border: 1px solid #eadfcb;
  background: rgba(255, 255, 255, 0.82);
  border-radius: 16px;
  padding: 14px;
}

.signal-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #4c4339;
  line-height: 1.7;
}

.warning-title,
.diagnostic-block {
  margin-top: 18px;
}

@media (max-width: 1240px) {
  .evolution-layout {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .evolution-layout {
    grid-template-columns: 1fr;
  }
}
</style>
