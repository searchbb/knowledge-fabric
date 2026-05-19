<template>
  <section class="evidence-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">本地证据包</div>
        <p>从 KFC 本地主题、概念和来源片段中检索候选证据。</p>
      </div>
      <button
        type="button"
        class="btn-primary"
        :disabled="!projectId || searching"
        @click="$emit('search')"
      >
        {{ searching ? '检索中...' : '检索本地证据' }}
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在读取本地证据包...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ summary.candidate_count || 0 }}</strong><span>候选</span></div>
        <div><strong>{{ summary.accepted_count || 0 }}</strong><span>已采纳</span></div>
        <div><strong>{{ summary.source_project_count || 0 }}</strong><span>来源项目</span></div>
        <div><strong>{{ summary.degraded_count || 0 }}</strong><span>降级引用</span></div>
      </div>

      <div v-if="isNotGenerated" class="empty-state">
        尚未生成本地证据包。
      </div>
      <div v-else-if="isEmpty" class="empty-state">
        {{ pack.empty_reason || '没有匹配到本地证据。' }}
      </div>
      <div v-else class="candidate-list">
        <article
          v-for="candidate in candidates"
          :key="candidate.evidence_id"
          class="candidate-card"
          :class="candidate.status"
        >
          <div class="candidate-main">
            <div class="candidate-topline">
              <span class="type-pill">{{ labelForType(candidate.evidence_type) }}</span>
              <span class="score">score {{ candidate.score }}</span>
              <span class="status-pill">{{ statusLabel(candidate.status) }}</span>
            </div>
            <h3>{{ candidate.title }}</h3>
            <p>{{ candidate.summary }}</p>
            <div class="match-row">
              <span v-for="reason in candidate.why_matched || []" :key="reason">{{ reason }}</span>
            </div>
            <div class="source-row">
              <span>{{ candidate.source?.registry || 'local_registry' }}</span>
              <span v-if="candidate.theme_refs?.length">
                {{ candidate.theme_refs.map((item) => item.name).join(' / ') }}
              </span>
            </div>
            <div v-if="candidate.source_refs?.length" class="refs">
              <div
                v-for="(ref, index) in candidate.source_refs.slice(0, 2)"
                :key="`${candidate.evidence_id}-${index}`"
                class="ref-row"
                :class="{ degraded: ref.degraded }"
              >
                <strong>{{ ref.project_name || ref.project_id || '本地来源' }}</strong>
                <span>{{ ref.source_text || ref.degraded_reason || '来源片段暂不可用' }}</span>
              </div>
            </div>
          </div>
          <div class="candidate-actions">
            <button
              type="button"
              class="btn-secondary"
              :disabled="reviewingId === candidate.evidence_id"
              @click="$emit('review', candidate.evidence_id, 'accepted')"
            >
              采纳
            </button>
            <button
              type="button"
              class="btn-secondary danger"
              :disabled="reviewingId === candidate.evidence_id"
              @click="$emit('review', candidate.evidence_id, 'rejected')"
            >
              废弃
            </button>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  projectId: {
    type: String,
    default: '',
  },
  pack: {
    type: Object,
    default: () => ({
      status: 'not_generated',
      candidates: [],
      summary: {},
    }),
  },
  loading: {
    type: Boolean,
    default: false,
  },
  searching: {
    type: Boolean,
    default: false,
  },
  reviewingId: {
    type: String,
    default: '',
  },
  error: {
    type: String,
    default: '',
  },
})

defineEmits(['search', 'review'])

const candidates = computed(() => props.pack?.candidates || [])
const summary = computed(() => props.pack?.summary || {})
const isNotGenerated = computed(() => props.pack?.status === 'not_generated')
const isEmpty = computed(() => props.pack?.status === 'empty' || candidates.value.length === 0)

function labelForType(type) {
  return type === 'theme' ? '主题' : '概念'
}

function statusLabel(status) {
  if (status === 'accepted') return '已采纳'
  if (status === 'rejected') return '已废弃'
  return '候选'
}
</script>

<style scoped>
.evidence-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.panel-head p {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
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
  color: var(--button-primary-text, #fff);
  border-color: var(--accent-primary);
}

.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.6;
  cursor: wait;
}

.btn-secondary {
  background: var(--bg-surface-2);
  color: var(--text-primary);
}

.btn-secondary.danger {
  color: var(--danger-text, #b42318);
}

.inline-error {
  margin: 10px 0 0;
  color: var(--danger-text, #b42318);
  font-size: 12px;
}

.state-line,
.empty-state {
  margin-top: 12px;
  padding: 12px;
  color: var(--text-muted);
  background: var(--bg-surface-2);
  border-radius: 6px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid div {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 10px;
  background: var(--bg-surface-2);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-grid strong {
  font-size: 19px;
}

.summary-grid span {
  color: var(--text-muted);
  font-size: 12px;
}

.candidate-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.candidate-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-surface-2);
}

.candidate-card.accepted {
  border-color: var(--success-border, #7cc58d);
}

.candidate-card.rejected {
  opacity: 0.72;
}

.candidate-topline,
.match-row,
.source-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.type-pill,
.status-pill,
.score,
.match-row span,
.source-row span {
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 800;
}

.score {
  color: var(--accent-primary);
}

.candidate-main h3 {
  margin: 8px 0 4px;
  font-size: 15px;
}

.candidate-main p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.source-row {
  margin-top: 8px;
}

.refs {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.ref-row {
  border-left: 3px solid var(--accent-primary);
  padding: 6px 8px;
  background: var(--bg-surface);
  display: grid;
  gap: 3px;
}

.ref-row.degraded {
  border-left-color: var(--warning-border, #d99a2b);
}

.ref-row strong {
  font-size: 12px;
}

.ref-row span {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.candidate-actions {
  display: flex;
  gap: 8px;
  align-self: start;
}

@media (max-width: 900px) {
  .panel-head,
  .candidate-card,
  .candidate-actions {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
