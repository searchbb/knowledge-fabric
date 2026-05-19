<template>
  <section class="synthesis-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">战略合成</div>
        <p>管理证据矩阵、洞察卡片和材料草稿，保留每个判断到证据的追溯关系。</p>
      </div>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在读取战略合成资产...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ rows.length }}</strong><span>矩阵判断</span></div>
        <div><strong>{{ cards.length }}</strong><span>洞察卡片</span></div>
        <div><strong>{{ drafts.length }}</strong><span>材料草稿</span></div>
        <div><strong>{{ readyCount }}</strong><span>可进材料</span></div>
      </div>

      <div class="tabs" role="tablist" aria-label="战略合成视图">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="activeTab === 'matrix'" class="asset-list">
        <div v-if="!rows.length" class="empty-state">暂无证据矩阵</div>
        <article v-for="row in rows" v-else :key="row.id" class="asset-card">
          <div class="asset-topline">
            <span class="status-pill">{{ row.status }}</span>
            <span class="status-pill">{{ row.confidence }}</span>
            <span class="status-pill">{{ row.material_readiness }}</span>
          </div>
          <h3>{{ row.claim }}</h3>
          <p>{{ row.question }}</p>
          <div class="trace-line">
            <span>本证据 {{ row.supporting_evidence_ids?.length || 0 }}</span>
            <span>反证 {{ row.counter_evidence_ids?.length || 0 }}</span>
          </div>
          <div class="asset-actions">
            <button
              type="button"
              class="btn-secondary"
              :disabled="updatingId === row.id"
              @click="$emit('patch-row', row.id, { status: 'reviewed' })"
            >
              标记已审
            </button>
            <button
              type="button"
              class="btn-secondary"
              :disabled="updatingId === row.id"
              @click="$emit('patch-row', row.id, { material_readiness: 'presentation_ready' })"
            >
              可进材料
            </button>
          </div>
        </article>
      </div>

      <div v-if="activeTab === 'insights'" class="asset-list board">
        <div v-if="!cards.length" class="empty-state">暂无洞察卡片</div>
        <article v-for="card in cards" v-else :key="card.id" class="asset-card">
          <div class="asset-topline">
            <span class="status-pill">{{ card.status }}</span>
            <span class="status-pill">{{ card.confidence }}</span>
          </div>
          <h3>{{ card.title }}</h3>
          <p>{{ card.claim }}</p>
          <p class="implication">{{ card.implication }}</p>
          <div class="trace-line">
            <span>证据 {{ card.supporting_evidence_ids?.length || 0 }}</span>
            <span>矩阵 {{ card.matrix_row_ids?.length || 0 }}</span>
          </div>
          <div class="asset-actions">
            <button
              type="button"
              class="btn-secondary"
              :disabled="updatingId === card.id"
              @click="$emit('patch-card', card.id, { status: 'accepted' })"
            >
              采纳
            </button>
            <button
              type="button"
              class="btn-secondary danger"
              :disabled="updatingId === card.id"
              @click="$emit('patch-card', card.id, { status: 'rejected' })"
            >
              废弃
            </button>
          </div>
        </article>
      </div>

      <div v-if="activeTab === 'artifacts'" class="asset-list">
        <div v-if="!drafts.length" class="empty-state">暂无材料草稿</div>
        <article v-for="draft in drafts" v-else :key="draft.id" class="asset-card">
          <div class="asset-topline">
            <span class="status-pill">{{ draft.artifact_type }}</span>
            <span class="status-pill">{{ draft.status }}</span>
            <span class="status-pill">{{ draft.material_readiness }}</span>
          </div>
          <h3>{{ draft.title }}</h3>
          <p>{{ draft.purpose }}</p>
          <div class="outline-list">
            <div v-for="section in draft.outline || []" :key="section.section_id" class="outline-row">
              <strong>{{ section.title }}</strong>
              <span>{{ section.key_message }}</span>
            </div>
          </div>
          <div class="trace-line">
            <span>洞察 {{ draft.source_insight_ids?.length || 0 }}</span>
            <span>证据 {{ draft.source_evidence_ids?.length || 0 }}</span>
          </div>
          <div class="asset-actions">
            <button
              type="button"
              class="btn-secondary"
              :disabled="updatingId === draft.id"
              @click="$emit('patch-draft', draft.id, { material_readiness: 'presentation_ready' })"
            >
              可汇报
            </button>
            <button
              type="button"
              class="btn-secondary"
              :disabled="updatingId === draft.id"
              @click="$emit('patch-draft', draft.id, { status: 'reviewed' })"
            >
              标记已审
            </button>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  cards: { type: Array, default: () => [] },
  drafts: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  updatingId: { type: String, default: '' },
  error: { type: String, default: '' },
})

defineEmits(['patch-row', 'patch-card', 'patch-draft'])

const activeTab = ref('matrix')
const tabs = [
  { key: 'matrix', label: 'Evidence Matrix' },
  { key: 'insights', label: 'Insight Board' },
  { key: 'artifacts', label: 'Artifact Studio' },
]

const readyCount = computed(() => (
  props.rows.filter((row) => row.material_readiness === 'presentation_ready').length
  + props.cards.filter((card) => ['accepted', 'used_in_artifact'].includes(card.status)).length
  + props.drafts.filter((draft) => draft.material_readiness === 'presentation_ready').length
))
</script>

<style scoped>
.synthesis-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.panel-head p,
.asset-card p,
.trace-line,
.outline-row span {
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
.asset-card,
.empty-state,
.state-line {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
}

.summary-grid div {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-grid strong {
  font-size: 19px;
}

.summary-grid span,
.status-pill,
.trace-line,
.outline-row span {
  font-size: 12px;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  border-bottom: 1px solid var(--border-default);
}

.tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  padding: 8px 2px;
  font-weight: 800;
  cursor: pointer;
}

.tabs button.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
}

.asset-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.asset-list.board {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.asset-card {
  padding: 12px;
}

.asset-card h3 {
  margin: 8px 0 6px;
  font-size: 15px;
  color: var(--text-primary);
}

.asset-topline,
.trace-line,
.asset-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.trace-line {
  margin-top: 10px;
}

.status-pill {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  color: var(--text-muted);
  font-weight: 800;
}

.implication {
  margin-top: 8px;
  color: var(--text-secondary);
}

.outline-list {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.outline-row {
  display: grid;
  gap: 3px;
  padding: 8px;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface);
}

.asset-actions {
  margin-top: 12px;
}

.btn-secondary {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 8px 12px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.btn-secondary.danger,
.inline-error {
  color: var(--danger-text, #b42318);
}

.empty-state,
.state-line {
  padding: 12px;
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .summary-grid,
  .asset-list.board {
    grid-template-columns: 1fr;
  }
}
</style>
