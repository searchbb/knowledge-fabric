<template>
  <section class="history-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Review History</div>
        <p>记录审查状态、门禁结论、汇报材料状态和人工备注的可追溯历史。</p>
      </div>
      <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('refresh')">
        刷新历史
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <p v-if="noteError" class="inline-error">{{ noteError }}</p>

    <div class="summary-grid">
      <div><strong>{{ entries.length }}</strong><span>Timeline</span></div>
      <div><strong>{{ governanceCount }}</strong><span>Governance</span></div>
      <div><strong>{{ briefingCount }}</strong><span>Briefing</span></div>
      <div><strong>{{ noteCount }}</strong><span>Notes</span></div>
    </div>

    <div class="history-layout">
      <div class="timeline-column">
        <div v-if="loading" class="state-line">正在加载审查历史...</div>
        <div v-else-if="!entries.length" class="empty-state">暂无审查历史</div>
        <article v-for="entry in entries" v-else :key="entry.history_entry_id" class="history-row">
          <div class="asset-topline">
            <span class="status-pill">{{ entry.asset_type }}</span>
            <span class="status-pill">{{ entry.event_type }}</span>
          </div>
          <strong>{{ entry.asset_title || entry.asset_id }}</strong>
          <p>{{ entry.summary || entry.note || entry.history_entry_id }}</p>
          <small>{{ entry.asset_id }} · {{ entry.created_at }}</small>
        </article>
      </div>

      <div class="asset-column">
        <div class="asset-history-head">
          <div>
            <h3>{{ selectedAsset?.asset_title || '当前审查资产' }}</h3>
            <p>{{ selectedAsset?.asset_type || 'governance_review' }} · {{ selectedAsset?.asset_id || '未选择' }}</p>
          </div>
          <button
            type="button"
            class="btn-secondary"
            :disabled="!selectedAsset?.asset_id || loading"
            @click="$emit('load-asset-history', selectedAsset)"
          >
            查看资产历史
          </button>
        </div>

        <form class="note-form" @submit.prevent="submitNote">
          <label>
            <span>人工备注</span>
            <textarea v-model="noteText" rows="3" :disabled="!selectedAsset?.asset_id || updating" placeholder="记录审查判断、风险接受或领导反馈" />
          </label>
          <button type="submit" class="btn-primary" :disabled="!canSubmitNote">
            {{ updating ? '记录中...' : '记录备注' }}
          </button>
        </form>

        <div v-if="!assetEntries.length" class="empty-state">暂无当前资产历史</div>
        <article v-for="entry in assetEntries" :key="entry.history_entry_id" class="history-row detail">
          <div class="asset-topline">
            <span class="status-pill">{{ entry.event_type }}</span>
            <span class="status-pill">{{ entry.actor?.display_name || entry.actor?.actor_type || 'Reviewer' }}</span>
          </div>
          <strong>{{ entry.summary || entry.note || entry.history_entry_id }}</strong>
          <p v-if="entry.note">{{ entry.note }}</p>
          <ul v-if="(entry.changed_fields || []).length" class="change-list">
            <li v-for="change in entry.changed_fields" :key="`${entry.history_entry_id}-${change.path}`">
              <span>{{ change.path }}</span>
              <code>{{ formatValue(change.old_value) }}</code>
              <code>{{ formatValue(change.new_value) }}</code>
            </li>
          </ul>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  entries: { type: Array, default: () => [] },
  assetEntries: { type: Array, default: () => [] },
  selectedAsset: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  updating: { type: Boolean, default: false },
  error: { type: String, default: '' },
  noteError: { type: String, default: '' },
})

const emit = defineEmits(['refresh', 'load-asset-history', 'create-note'])

const noteText = ref('')
const governanceCount = computed(() => props.entries.filter((entry) => entry.asset_type === 'governance_review').length)
const briefingCount = computed(() => props.entries.filter((entry) => entry.asset_type === 'leadership_briefing').length)
const noteCount = computed(() => props.entries.filter((entry) => entry.event_type === 'review_note_added').length)
const canSubmitNote = computed(() => Boolean(props.selectedAsset?.asset_id && noteText.value.trim() && !props.updating))

function formatValue(value) {
  if (value == null || value === '') return 'empty'
  if (Array.isArray(value)) return `${value.length} items`
  if (typeof value === 'object') {
    if (value.truncated) return value.preview ? `${String(value.preview).slice(0, 57)}...` : (value.hash || 'large value')
    const keys = Object.keys(value)
    return keys.length ? `{${keys.slice(0, 3).join(', ')}}` : '{}'
  }
  const text = String(value)
  if (text.length > 80) return `${text.slice(0, 77)}...`
  return text
}

function submitNote() {
  if (!canSubmitNote.value) return
  emit('create-note', {
    ...props.selectedAsset,
    note: noteText.value.trim(),
  })
}

watch(() => props.selectedAsset?.asset_id, () => {
  noteText.value = ''
})
</script>

<style scoped>
.history-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head,
.asset-topline,
.asset-history-head {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-head,
.asset-history-head {
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
.asset-history-head p,
.history-row p,
.history-row small {
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
.history-row,
.note-form {
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

.history-layout {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.6fr);
  gap: 12px;
  margin-top: 14px;
}

.timeline-column,
.asset-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-row,
.note-form {
  padding: 12px;
}

.history-row strong,
.history-row small {
  display: block;
  overflow-wrap: anywhere;
}

.history-row strong {
  margin: 8px 0 4px;
}

.asset-history-head h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.note-form {
  display: grid;
  gap: 10px;
}

.note-form label {
  display: grid;
  gap: 6px;
}

.note-form span {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 700;
}

.note-form textarea {
  width: 100%;
  resize: vertical;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 10px;
  box-sizing: border-box;
}

.change-list {
  list-style: none;
  padding: 0;
  margin: 10px 0 0;
  display: grid;
  gap: 6px;
}

.change-list li {
  display: grid;
  grid-template-columns: minmax(80px, 0.7fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 6px;
  align-items: center;
  font-size: 12px;
}

.change-list span {
  color: var(--text-muted);
  overflow-wrap: anywhere;
}

.change-list code {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 4px 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  overflow-wrap: anywhere;
  min-width: 0;
}

@media (max-width: 900px) {
  .summary-grid,
  .history-layout,
  .change-list li {
    grid-template-columns: 1fr;
  }
}
</style>
