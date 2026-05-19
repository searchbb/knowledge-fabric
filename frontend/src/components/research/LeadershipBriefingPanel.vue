<template>
  <section class="briefing-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Leadership Briefings</div>
        <p>把证据、洞察、选项、验证计划和决策记录组织成领导可读的汇报结构。这里保存结构、来源和评审状态，不生成材料、不导出文件。</p>
      </div>
      <button type="button" class="btn-primary" :disabled="loading || updating" @click="$emit('create-briefing')">
        新建 Readout
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在读取领导汇报...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ briefings.length }}</strong><span>Readouts</span></div>
        <div><strong>{{ selectedBriefing?.sections?.length || selectedIndex?.section_count || 0 }}</strong><span>Sections</span></div>
        <div><strong>{{ selectedBriefing?.decision_asks?.length || 0 }}</strong><span>Decision asks</span></div>
        <div><strong>{{ openBlockingReviews }}</strong><span>Blocking reviews</span></div>
      </div>

      <div v-if="!briefings.length" class="empty-state">暂无领导汇报结构</div>
      <template v-else>
        <div class="briefing-list">
          <button
            v-for="briefing in briefings"
            :key="briefing.briefing_id"
            type="button"
            class="briefing-row"
            :class="{ active: selectedId === briefing.briefing_id }"
            @click="selectBriefing(briefing.briefing_id)"
          >
            <strong>{{ briefing.title }}</strong>
            <span>{{ briefing.briefing_type }} · {{ briefing.status }} · {{ briefing.readiness }}</span>
          </button>
        </div>

        <div v-if="selectedBriefing" class="briefing-detail">
          <div class="asset-topline">
            <span class="status-pill">{{ selectedBriefing.status }}</span>
            <span class="status-pill">{{ selectedBriefing.readiness }}</span>
            <span class="status-pill">{{ selectedBriefing.audience }}</span>
            <span v-if="hasOpenBlockingReview(selectedBriefing)" class="status-pill danger">阻塞未解决</span>
          </div>

          <div class="preview-band">
            <div>
              <span>Headline</span>
              <h3>{{ selectedBriefing.executive_summary?.headline || selectedBriefing.title }}</h3>
            </div>
            <p>{{ selectedBriefing.executive_summary?.key_message }}</p>
            <strong>{{ selectedBriefing.executive_summary?.leadership_ask }}</strong>
          </div>

          <div class="actions">
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-briefing', selectedBriefing.briefing_id, { status: 'in_review', readiness: 'ready' })">
              标记 Ready
            </button>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('add-review', selectedBriefing.briefing_id)">
              添加阻塞评审
            </button>
            <button type="button" class="btn-secondary" :disabled="updating || !hasOpenBlockingReview(selectedBriefing)" @click="$emit('resolve-review', selectedBriefing)">
              解决阻塞
            </button>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-briefing', selectedBriefing.briefing_id, { status: 'approved', readiness: 'approved' })">
              批准 Readout
            </button>
          </div>

          <div class="readiness-grid">
            <div v-for="check in readinessItems" :key="check.key">
              <span>{{ check.label }}</span>
              <strong>{{ check.value ? 'OK' : '待补' }}</strong>
            </div>
          </div>

          <div class="section-list">
            <article v-for="section in orderedSections" :key="section.section_id" class="mini-card">
              <div class="asset-topline">
                <span class="status-pill">{{ section.order }}</span>
                <span class="status-pill">{{ section.section_type }}</span>
                <span class="status-pill">{{ section.review_state }}</span>
              </div>
              <h4>{{ section.title }}</h4>
              <p>{{ section.summary }}</p>
              <div class="trace-line">
                <span v-for="ref in section.source_refs || []" :key="`${ref.asset_type}:${ref.asset_id}`">
                  {{ ref.asset_type }} · {{ ref.asset_id }}
                </span>
              </div>
            </article>
          </div>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, watch, ref } from 'vue'

const props = defineProps({
  briefings: { type: Array, default: () => [] },
  selectedBriefing: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  updating: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits([
  'select-briefing',
  'create-briefing',
  'update-briefing',
  'add-review',
  'resolve-review',
])

const selectedId = ref('')

const selectedIndex = computed(() => props.briefings.find((item) => item.briefing_id === selectedId.value) || props.briefings[0] || null)

const orderedSections = computed(() => [...(props.selectedBriefing?.sections || [])].sort((a, b) => (a.order || 0) - (b.order || 0)))

const readinessItems = computed(() => {
  const checks = props.selectedBriefing?.readiness_checks || {}
  return [
    { key: 'summary', label: 'Executive summary', value: checks.has_executive_summary },
    { key: 'ask', label: 'Decision ask', value: checks.has_decision_ask },
    { key: 'sources', label: 'Required sources', value: checks.all_required_sources_resolved },
    { key: 'blockers', label: 'No blockers', value: !checks.has_blocking_review_decisions },
  ]
})

function hasOpenBlockingReview(briefing) {
  return (briefing?.review_rounds || []).some(
    (round) => round.blocking === true && ['changes_requested', 'rejected'].includes(round.decision) && !round.resolved,
  )
}

const openBlockingReviews = computed(() => (props.selectedBriefing && hasOpenBlockingReview(props.selectedBriefing) ? 1 : 0))

function selectBriefing(briefingId) {
  selectedId.value = briefingId
  emit('select-briefing', briefingId)
}

watch(() => props.briefings, (briefings) => {
  if (!briefings.some((briefing) => briefing.briefing_id === selectedId.value)) {
    selectedId.value = briefings[0]?.briefing_id || ''
    if (selectedId.value) {
      emit('select-briefing', selectedId.value)
    }
  }
}, { immediate: true })
</script>

<style scoped>
.briefing-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head,
.asset-topline,
.actions,
.trace-line {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-head {
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
.briefing-row span,
.preview-band p,
.mini-card p,
.trace-line {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.summary-grid,
.readiness-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid div,
.readiness-grid div,
.briefing-row,
.briefing-detail,
.preview-band,
.mini-card,
.empty-state,
.state-line {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
}

.summary-grid div,
.readiness-grid div,
.briefing-row,
.briefing-detail,
.preview-band,
.mini-card,
.empty-state,
.state-line {
  padding: 12px;
}

.summary-grid div,
.readiness-grid div,
.briefing-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-grid strong {
  font-size: 19px;
}

.summary-grid span,
.readiness-grid span,
.status-pill,
.trace-line {
  color: var(--text-muted);
  font-size: 12px;
}

.briefing-list,
.section-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.briefing-row {
  text-align: left;
  cursor: pointer;
}

.briefing-row.active {
  border-color: var(--accent-primary);
}

.briefing-detail {
  margin-top: 12px;
}

.preview-band {
  margin-top: 12px;
}

.preview-band span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}

.preview-band h3,
.mini-card h4 {
  margin: 4px 0 6px;
  color: var(--text-primary);
}

.status-pill {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  font-weight: 800;
}

.status-pill.danger {
  color: var(--danger-text, #b42318);
}

.actions {
  margin-top: 12px;
}

.btn-primary,
.btn-secondary {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.btn-primary {
  background: var(--accent-primary);
  color: white;
}

.btn-secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.inline-error {
  color: var(--danger-text, #b42318);
}

@media (max-width: 900px) {
  .panel-head,
  .summary-grid,
  .readiness-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
