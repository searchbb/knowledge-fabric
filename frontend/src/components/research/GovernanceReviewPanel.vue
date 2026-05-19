<template>
  <section class="governance-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Governance Review</div>
        <p>基于追踪图沉淀人工审查、风险处置、签署和阶段门禁。</p>
      </div>
      <button type="button" class="btn-primary" :disabled="loading || updating" @click="$emit('create-review')">
        新建审查
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在加载治理审查...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ reviews.length }}</strong><span>Reviews</span></div>
        <div><strong>{{ selectedReview?.review_summary?.major_open_count || selectedIndex?.major_open_count || 0 }}</strong><span>Major open</span></div>
        <div><strong>{{ selectedReview?.review_summary?.failed_required_count || selectedIndex?.failed_required_count || 0 }}</strong><span>Required failed</span></div>
        <div><strong>{{ selectedReview?.review_summary?.ready_for_next_stage ? 'yes' : 'no' }}</strong><span>Next stage</span></div>
      </div>

      <div v-if="!reviews.length" class="empty-state">暂无治理审查资产</div>
      <div v-else class="review-layout">
        <div class="review-list">
          <button
            v-for="review in reviews"
            :key="review.review_id"
            type="button"
            class="review-row"
            :class="{ active: selectedId === review.review_id }"
            @click="selectReview(review.review_id)"
          >
            <strong>{{ review.title }}</strong>
            <span>{{ review.status }} · {{ review.gate_decision }} · {{ review.readiness }}</span>
          </button>
        </div>

        <div v-if="selectedReview" class="review-detail">
          <div class="detail-head">
            <div>
              <h3>{{ selectedReview.title }}</h3>
              <p>{{ selectedReview.review_id }}</p>
            </div>
            <span class="status-pill" :class="{ good: selectedReview.review_summary?.ready_for_next_stage }">
              {{ selectedReview.review_summary?.overall_readiness || selectedReview.readiness }}
            </span>
          </div>

          <div class="trace-version">
            <span>Traceability</span>
            <strong>{{ traceVersion.readiness || 'unknown' }}</strong>
            <span>{{ traceVersion.node_count || 0 }} nodes · {{ traceVersion.edge_count || 0 }} edges</span>
          </div>

          <GateReviewSnapshotAttentionContext :context="snapshotAttentionContext" />

          <div class="action-row">
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-review', selectedReview.review_id, { status: 'in_review', readiness: 'partial' })">
              开始审查
            </button>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('accept-risks', selectedReview)">
              接受风险并签署
            </button>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('block-review', selectedReview.review_id)">
              标记阻塞
            </button>
          </div>

          <section class="detail-section">
            <h4>Checklist</h4>
            <article v-for="item in selectedReview.checklist_items || []" :key="item.item_id" class="compact-row">
              <div class="asset-topline">
                <span class="status-pill" :class="{ danger: item.status === 'fail', good: item.status === 'pass' }">{{ item.status }}</span>
                <span class="status-pill">{{ item.severity }}</span>
                <span v-if="item.required" class="status-pill">required</span>
              </div>
              <strong>{{ item.label }}</strong>
              <p>{{ item.notes || item.category }}</p>
            </article>
          </section>

          <section class="detail-section">
            <h4>Findings</h4>
            <div v-if="!(selectedReview.findings || []).length" class="empty-state">无审查发现</div>
            <article v-for="finding in selectedReview.findings || []" :key="finding.finding_id" class="compact-row">
              <div class="asset-topline">
                <span class="status-pill" :class="{ danger: finding.severity === 'blocker', warn: finding.severity === 'major' }">{{ finding.severity }}</span>
                <span class="status-pill">{{ finding.status }}</span>
              </div>
              <strong>{{ finding.finding_type }}</strong>
              <p>{{ finding.description }}</p>
              <small>{{ finding.asset_ref?.asset_type }} · {{ finding.asset_ref?.asset_id }}</small>
            </article>
          </section>

          <section class="detail-section">
            <h4>Signoffs</h4>
            <div v-if="!(selectedReview.signoffs || []).length" class="empty-state">暂无签署</div>
            <article v-for="signoff in selectedReview.signoffs || []" :key="signoff.signoff_id" class="compact-row">
              <strong>{{ signoff.role }} · {{ signoff.decision }}</strong>
              <p>{{ signoff.name || signoff.comment }}</p>
            </article>
          </section>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import GateReviewSnapshotAttentionContext from './GateReviewSnapshotAttentionContext.vue'

const props = defineProps({
  reviews: { type: Array, default: () => [] },
  selectedReview: { type: Object, default: null },
  snapshotAttentionContext: { type: Object, default: () => ({ snapshots: [], totals: {} }) },
  loading: { type: Boolean, default: false },
  updating: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['select-review', 'create-review', 'update-review', 'accept-risks', 'block-review'])

const selectedId = ref('')
const selectedIndex = computed(() => props.reviews.find((item) => item.review_id === selectedId.value) || props.reviews[0] || null)
const traceVersion = computed(() => props.selectedReview?.traceability_map_version || {})

function selectReview(reviewId) {
  selectedId.value = reviewId
  emit('select-review', reviewId)
}

watch(() => props.reviews, (reviews) => {
  if (!reviews.some((review) => review.review_id === selectedId.value)) {
    selectedId.value = reviews[0]?.review_id || ''
    if (selectedId.value) emit('select-review', selectedId.value)
  }
}, { immediate: true })

watch(() => props.selectedReview?.review_id, (reviewId) => {
  if (reviewId) selectedId.value = reviewId
})
</script>

<style scoped>
.governance-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head,
.asset-topline,
.action-row,
.detail-head,
.trace-version {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-head,
.detail-head {
  justify-content: space-between;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.panel-head p,
.review-row span,
.review-detail p,
.compact-row p,
.compact-row small,
.trace-version span {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid div,
.review-row,
.review-detail,
.compact-row,
.trace-version {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
}

.summary-grid div {
  padding: 10px;
}

.summary-grid strong {
  display: block;
  font-size: 18px;
}

.summary-grid span {
  color: var(--text-muted);
  font-size: 12px;
}

.review-layout {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.7fr);
  gap: 12px;
  margin-top: 14px;
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-row {
  text-align: left;
  padding: 10px;
  color: var(--text-primary);
  cursor: pointer;
}

.review-row strong,
.review-row span {
  display: block;
  overflow-wrap: anywhere;
}

.review-row strong {
  margin-bottom: 4px;
}

.review-row.active {
  border-color: var(--accent-primary);
}

.review-detail,
.compact-row,
.trace-version {
  padding: 12px;
}

.review-detail h3,
.detail-section h4 {
  margin: 0 0 6px;
}

.action-row {
  margin: 12px 0;
}

.detail-section {
  margin-top: 12px;
}

.compact-row + .compact-row {
  margin-top: 8px;
}

.status-pill.good {
  background: rgba(35, 134, 54, 0.12);
  color: #238636;
}

.status-pill.warn {
  background: rgba(181, 118, 20, 0.14);
  color: #9a6700;
}

.status-pill.danger {
  background: rgba(218, 54, 51, 0.12);
  color: #da3633;
}

@media (max-width: 900px) {
  .summary-grid,
  .review-layout {
    grid-template-columns: 1fr;
  }
}
</style>
