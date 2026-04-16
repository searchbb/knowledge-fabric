<template>
  <section class="phase2-page">
    <div class="section-badge">Review Queue</div>
    <h2 class="section-title">校验视图原型</h2>
    <p class="section-copy">
      这是第一版可运行原型：先用现有 Phase 1 信号和 mock task 验证 review 的主链路，再决定真实 `ReviewTask`
      API、审计写回和更复杂的审核流该怎么接。
    </p>

    <div class="summary-grid">
      <article class="card">
        <div class="card-title">当前上下文</div>
        <div class="metric-line">项目：{{ project?.name || '暂无' }}</div>
        <div class="metric-line">阶段：Phase 2 review prototype</div>
        <div class="metric-line">文章入口仍保留在左侧导航 article</div>
      </article>

      <article class="card">
        <div class="card-title">任务统计</div>
        <div class="metric-line">总任务：{{ summary.totalCount || reviewStore.items.length }}</div>
        <div class="metric-line">待处理：{{ pendingCount }}</div>
        <div class="metric-line">高优先级：{{ highPriorityCount }}</div>
        <div class="metric-line" v-if="approvedCount">已通过：{{ approvedCount }}</div>
        <div class="metric-line" v-if="questionedCount">已存疑：{{ questionedCount }}</div>
        <div class="metric-line" v-if="ignoredCount">已忽略：{{ ignoredCount }}</div>
      </article>

      <article class="card">
        <div class="card-title">当前信号源</div>
        <div class="metric-line">Warning：{{ warningCount }}</div>
        <div class="metric-line">图谱：{{ graphNodeCount }} 节点 / {{ graphEdgeCount }} 关系</div>
        <div class="metric-line">原文：{{ reviewStore.articleTextAvailable ? '已接入' : '未接入' }}</div>
        <div class="metric-line">跨文章扫描：{{ reviewStore.relatedProjectCount }} 个项目</div>
      </article>
    </div>

    <div class="review-layout">
      <ReviewQueuePanel
        :tasks="visibleTasks"
        :filters="filterItems"
        :active-filter="reviewStore.activeFilter"
        :active-task-id="reviewStore.selectedId"
        @change-filter="setReviewFilter"
        @select-task="selectReviewTask"
      />

      <ReviewEvidencePanel
        :task="reviewStore.selectedTask"
        :loading="reviewStore.loading"
        :error="reviewStore.error"
      />

      <ReviewActionPanel
        :task="reviewStore.selectedTask"
        :decisions="REVIEW_DECISIONS"
        :phase1-task-result="phase1Signals"
        @apply-decision="applyPrototypeDecision"
        @update-manual-note="updateReviewManualNote"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, watch } from 'vue'
import ReviewActionPanel from '../../components/review/ReviewActionPanel.vue'
import ReviewEvidencePanel from '../../components/review/ReviewEvidencePanel.vue'
import ReviewQueuePanel from '../../components/review/ReviewQueuePanel.vue'
import {
  REVIEW_DECISIONS,
  REVIEW_FILTERS,
  applyPrototypeDecision,
  getVisibleReviewTasks,
  loadReviewView,
  reviewStore,
  selectReviewTask,
  setReviewFilter,
  updateReviewManualNote,
} from '../../stores/reviewStore'
import { matchesReviewFilter } from '../../types/review'
import { appMode } from '../../runtime/appMode'

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

const summary = computed(() => reviewStore.summary || {})
const phase1Signals = computed(() => reviewStore.phase1Signals || props.phase1TaskResult || null)
const warningCount = computed(() => summary.value.warningCount ?? props.phase1TaskResult?.build_outcome?.warnings?.length ?? 0)
const graphNodeCount = computed(() => summary.value.graphNodeCount ?? props.graphData?.node_count ?? props.graphData?.nodes?.length ?? 0)
const graphEdgeCount = computed(() => summary.value.graphEdgeCount ?? props.graphData?.edge_count ?? props.graphData?.edges?.length ?? 0)
const visibleTasks = computed(() => getVisibleReviewTasks())
const pendingCount = computed(() => summary.value.pendingCount ?? reviewStore.items.filter((item) => item.status === 'pending').length)
const approvedCount = computed(() => summary.value.approvedCount ?? reviewStore.items.filter((item) => item.status === 'approved').length)
const questionedCount = computed(() => summary.value.questionedCount ?? reviewStore.items.filter((item) => item.status === 'questioned').length)
const ignoredCount = computed(() => summary.value.ignoredCount ?? reviewStore.items.filter((item) => item.status === 'ignored').length)
const highPriorityCount = computed(() => summary.value.highPriorityCount ?? reviewStore.items.filter((item) => item.severity === 'high').length)
const filterItems = computed(() =>
  REVIEW_FILTERS.map((filter) => ({
    ...filter,
    count: reviewStore.items.filter((item) => matchesReviewFilter(item, filter.key)).length,
  })),
)

watch(
  () => props.project?.project_id,
  async () => {
    await loadReviewView({
      projectId: props.project?.project_id,
      project: props.project,
    })
  },
  { immediate: true },
)

// Reload when live/demo flips.
watch(appMode, async () => {
  await loadReviewView({
    projectId: props.project?.project_id,
    project: props.project,
  })
})
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
  color: var(--accent-group-label);
  font-weight: 700;
}

.section-title {
  margin: 0;
  font-size: 28px;
  color: var(--text-primary);
}

.section-copy,
.metric-line {
  color: var(--text-secondary);
  line-height: 1.6;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.card {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 18px;
  padding: 18px;
}

.card-title {
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.review-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(260px, 320px);
  gap: 16px;
  align-items: start;
}

@media (max-width: 1240px) {
  .review-layout {
    grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  }
}

@media (max-width: 960px) {
  .review-layout {
    grid-template-columns: 1fr;
  }
}
</style>
