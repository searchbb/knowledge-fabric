<template>
  <section class="snapshot-review-panel">
    <div class="review-head">
      <div>
        <div class="eyebrow">快照证据审阅</div>
        <h3>基线快照审阅</h3>
        <p>该视图仅解释当前状态相对所选快照的变化，不会修改快照、项目资产或评审历史。</p>
      </div>
      <span class="read-only-badge">只读</span>
    </div>

    <div class="review-summary">
      <div>
        <span>基线</span>
        <strong>{{ review.baseline_label }}</strong>
        <small>{{ review.baseline_created_at || '无' }}</small>
      </div>
      <div>
        <span>状态</span>
        <strong>{{ review.overall.has_changes ? '有变化' : '无变化' }}</strong>
        <small>{{ review.current_compared_at || '当前' }}</small>
      </div>
      <div>
        <span>待关注</span>
        <strong>{{ review.overall.attention_count }}</strong>
        <small>需要审阅</small>
      </div>
      <div>
        <span>资产</span>
        <strong>{{ review.overall.total_added }}/{{ review.overall.total_changed }}</strong>
        <small>新增/变化</small>
      </div>
    </div>

    <p v-if="!review.overall.has_changes" class="safe-state">无变化：当前项目状态与该快照未检测到差异。</p>
    <p v-else class="attention-copy">检测到变化：以下项目仅作为人工审阅提示，不代表自动批准或自动否决。</p>

    <section v-if="review.counts_by_kind.length" class="review-section">
      <h4>变化资产计数</h4>
      <div class="kind-table">
        <div class="table-row table-head">
          <span>资产类型</span>
          <span>新增</span>
          <span>移除</span>
          <span>变化</span>
          <span>状态</span>
        </div>
        <div v-for="row in review.counts_by_kind" :key="row.asset_kind" class="table-row">
          <strong>{{ row.asset_kind }}</strong>
          <span>{{ row.added }}</span>
          <span>{{ row.removed }}</span>
          <span>{{ row.changed }}</span>
          <span class="status-pill" :class="{ warn: row.status === 'attention' }">{{ row.status }}</span>
        </div>
      </div>
    </section>

    <section v-if="review.movements.governance_gate.length" class="review-section">
      <h4>治理门禁变化</h4>
      <p>以下字段相对基线发生变化，请人工确认其依据是否仍然成立。</p>
      <article v-for="row in review.movements.governance_gate" :key="`governance-${row.field}`" class="movement-row">
        <strong>{{ row.field }}</strong>
        <span>{{ row.baseline_value }} -> {{ row.current_value }}</span>
        <em>待关注</em>
      </article>
    </section>

    <section v-if="review.movements.leadership_briefing_readiness.length" class="review-section">
      <h4>领导汇报就绪度变化</h4>
      <p>以下领导汇报状态相对基线发生变化，仅作为审阅提示，不代表自动批准。</p>
      <article v-for="row in review.movements.leadership_briefing_readiness" :key="`briefing-${row.field}`" class="movement-row">
        <strong>{{ row.field }}</strong>
        <span>{{ row.baseline_value }} -> {{ row.current_value }}</span>
        <em>待关注</em>
      </article>
    </section>

    <section v-if="review.review_history_activity.changed" class="review-section">
      <h4>基线后的评审历史活动</h4>
      <p>以下计数来自基线后的评审历史变化，用于帮助审核人回看人工变更轨迹。</p>
      <div class="movement-row">
        <strong>entry_count</strong>
        <span>{{ review.review_history_activity.from_entry_count }} -> {{ review.review_history_activity.to_entry_count }}</span>
        <em>已变化</em>
      </div>
    </section>

    <section v-if="review.attention_items.length" class="review-section">
      <h4>待关注项</h4>
      <article v-for="item in review.attention_items" :key="item.key" class="attention-row">
        <strong>{{ item.title }}</strong>
        <p>{{ item.reason }}</p>
        <span>{{ item.baseline_value }} -> {{ item.current_value }}</span>
        <em>{{ item.status }}</em>
      </article>
    </section>

    <section class="review-section note-rollup">
      <h4>审阅备注处理状态</h4>
      <p>该汇总来自人工快照审阅备注；不会批准、拒绝或改变关卡就绪度。</p>
      <div class="rollup-grid">
        <div><strong>{{ noteRollup.total_notes }}</strong><span>总数</span></div>
        <div><strong>{{ noteRollup.status_counts.open }}</strong><span>未处理</span></div>
        <div><strong>{{ noteRollup.status_counts.acknowledged }}</strong><span>已确认</span></div>
        <div><strong>{{ noteRollup.status_counts.resolved }}</strong><span>已解决</span></div>
        <div><strong>{{ noteRollup.status_counts.deferred }}</strong><span>已延后</span></div>
        <div><strong>{{ noteRollup.attention_counts.active_attention }}</strong><span>仍需关注</span></div>
      </div>
      <div v-if="noteRollup.attention_notes.length" class="attention-note-list">
        <article v-for="note in noteRollup.attention_notes" :key="`rollup-${note.note_id}`" class="attention-note">
          <span class="status-pill" :class="{ warn: note.status === 'open' || note.status === 'deferred' }">{{ noteStatusLabel(note.status) }}</span>
          <strong>{{ note.title }}</strong>
          <p>{{ note.body_preview }}</p>
          <small>{{ note.owner || '未分配' }} · {{ note.updated_at || note.created_at || '无时间戳' }}</small>
        </article>
      </div>
      <p v-else class="notes-empty">该快照暂无需要关注的人工备注。</p>
    </section>

    <section class="review-section manual-notes">
      <h4>人工审阅备注</h4>
      <p>给这段快照差异附加人工备注；备注不会修改快照、关卡决策或项目资产。</p>

      <form class="note-form" @submit.prevent="submitNote">
        <label>
          <span>目标分区</span>
          <select v-model="noteForm.section_key" :disabled="creatingNote">
            <option value="governance_gate">governance_gate</option>
            <option value="leadership_briefing_readiness">leadership_briefing_readiness</option>
            <option value="review_history_activity">review_history_activity</option>
            <option value="asset_kind_counts">asset_kind_counts</option>
            <option value="raw_diff">raw_diff</option>
            <option value="other">other</option>
          </select>
        </label>
        <label>
          <span>类型</span>
          <select v-model="noteForm.note_type" :disabled="creatingNote">
            <option value="observation">observation</option>
            <option value="question">question</option>
            <option value="accepted_change">accepted_change</option>
            <option value="needs_follow_up">needs_follow_up</option>
          </select>
        </label>
        <label>
          <span>严重度</span>
          <select v-model="noteForm.severity" :disabled="creatingNote">
            <option value="info">info</option>
            <option value="watch">watch</option>
            <option value="blocker">blocker</option>
          </select>
        </label>
        <label class="note-text">
          <span>人工备注</span>
          <textarea v-model="noteForm.note" :disabled="creatingNote" rows="3" placeholder="为这段快照差异写一条人工审核备注。" />
        </label>
        <button type="submit" class="btn-primary" :disabled="!canSubmitNote">
          {{ creatingNote ? '添加中...' : '添加人工备注' }}
        </button>
      </form>
      <p v-if="noteError" class="inline-error">{{ noteError }}</p>

      <div v-if="notesLoading" class="notes-empty">正在加载人工备注...</div>
      <div v-else-if="!notes.length" class="notes-empty">这段快照差异尚未添加人工备注。</div>
      <article v-for="note in notes" v-else :key="note.note_id" class="note-row">
        <div>
          <strong>{{ note.target_ref?.section_key || 'other' }}</strong>
          <span>{{ note.note_type }} · {{ note.severity }}</span>
        </div>
        <span class="status-pill" :class="{ warn: note.status === 'open' || note.status === 'deferred' }">{{ noteStatusLabel(note.status) }}</span>
        <p>{{ note.note }}</p>
        <small>{{ note.actor?.display_name || 'Reviewer' }} · {{ note.created_at }}</small>
        <div class="note-meta">
          <span>Owner: {{ note.owner || 'unassigned' }}</span>
          <span v-if="note.resolved_by">Resolved by {{ note.resolved_by }}</span>
          <span v-if="note.resolved_at">{{ note.resolved_at }}</span>
        </div>
        <p v-if="note.resolution_note" class="resolution-note">{{ note.resolution_note }}</p>
        <form class="disposition-form" @submit.prevent="submitDisposition(note)">
          <label>
            <span>Disposition</span>
            <select v-model="formFor(note).status" :disabled="updatingNote">
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
              <option value="deferred">Deferred</option>
            </select>
          </label>
          <label>
            <span>Owner</span>
            <input v-model="formFor(note).owner" :disabled="updatingNote" type="text" placeholder="Reviewer name" />
          </label>
          <label class="note-text">
            <span>Resolution note</span>
            <textarea v-model="formFor(note).resolution_note" :disabled="updatingNote" rows="2" placeholder="Manual disposition note." />
          </label>
          <button type="submit" class="btn-secondary" :disabled="updatingNote">
            {{ updatingNote ? 'Saving...' : 'Save disposition' }}
          </button>
        </form>
      </article>
    </section>

    <button type="button" class="btn-secondary raw-toggle" @click="showRaw = !showRaw">
      {{ showRaw ? '收起原始差异' : '展开原始差异' }}
    </button>
    <pre v-if="showRaw" class="raw-diff">{{ JSON.stringify(diff, null, 2) }}</pre>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { buildSnapshotReviewSummary } from './snapshotReviewSummary'
import { buildSnapshotReviewNoteRollup } from './snapshotReviewNoteRollup'

const props = defineProps({
  snapshot: { type: Object, required: true },
  diff: { type: Object, required: true },
  notes: { type: Array, default: () => [] },
  notesLoading: { type: Boolean, default: false },
  creatingNote: { type: Boolean, default: false },
  updatingNote: { type: Boolean, default: false },
  noteError: { type: String, default: '' },
})

const emit = defineEmits(['create-note', 'update-note'])

const showRaw = ref(false)
const dispositionForms = reactive({})
const noteForm = reactive({
  section_key: 'governance_gate',
  note_type: 'observation',
  severity: 'watch',
  note: '',
})
const review = computed(() => buildSnapshotReviewSummary(props.snapshot, props.diff))
const noteRollup = computed(() => buildSnapshotReviewNoteRollup(props.notes, {
  snapshot_id: props.snapshot?.snapshot_id || '',
}))
const canSubmitNote = computed(() => Boolean(noteForm.note.trim() && !props.creatingNote))

function submitNote() {
  if (!canSubmitNote.value) return
  emit('create-note', {
    target_ref: {
      section_key: noteForm.section_key,
    },
    note_type: noteForm.note_type,
    severity: noteForm.severity,
    note: noteForm.note.trim(),
  })
  noteForm.note = ''
}

function formFor(note) {
  if (!dispositionForms[note.note_id]) {
    dispositionForms[note.note_id] = {
      status: note.status || 'open',
      owner: note.owner || '',
      resolution_note: note.resolution_note || '',
    }
  }
  return dispositionForms[note.note_id]
}

function submitDisposition(note) {
  const form = formFor(note)
  emit('update-note', {
    note_id: note.note_id,
    status: form.status,
    owner: form.owner.trim(),
    resolution_note: form.resolution_note.trim(),
  })
}

function noteStatusLabel(status) {
  return {
    open: 'Open',
    acknowledged: 'Acknowledged',
    resolved: 'Resolved',
    deferred: 'Deferred',
  }[status || 'open'] || status
}
</script>

<style scoped>
.snapshot-review-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
  padding: 14px;
}

.review-head,
.movement-row,
.attention-row {
  display: flex;
  gap: 10px;
}

.review-head {
  justify-content: space-between;
  align-items: flex-start;
}

.eyebrow {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.review-head h3,
.review-section h4 {
  margin: 4px 0 6px;
}

.review-head p,
.review-section p,
.attention-row p,
.review-summary small {
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

.read-only-badge,
.status-pill,
.movement-row em,
.attention-row em {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  color: var(--text-muted);
  font-size: 12px;
  font-style: normal;
  padding: 3px 8px;
  white-space: nowrap;
}

.status-pill.warn,
.movement-row em,
.attention-row em {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.review-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.rollup-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.review-summary div,
.rollup-grid div,
.review-section,
.attention-row,
.movement-row {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
}

.review-summary div,
.rollup-grid div,
.review-section {
  padding: 12px;
}

.review-summary span,
.rollup-grid span,
.table-head {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.review-summary strong {
  display: block;
  margin: 4px 0;
}

.rollup-grid strong {
  display: block;
  margin-bottom: 4px;
}

.safe-state,
.attention-copy {
  margin: 0 0 12px;
  color: var(--text-muted);
}

.review-section {
  margin-top: 10px;
}

.kind-table {
  display: grid;
  gap: 6px;
}

.table-row {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) repeat(3, minmax(42px, 0.45fr)) minmax(68px, 0.65fr);
  gap: 8px;
  align-items: center;
}

.table-row > * {
  min-width: 0;
  overflow-wrap: anywhere;
}

.movement-row,
.attention-row {
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  padding: 10px;
}

.attention-row {
  align-items: flex-start;
  flex-direction: column;
}

.attention-note-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.attention-note {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  padding: 10px;
}

.attention-note p {
  margin: 6px 0;
}

.attention-note small {
  color: var(--text-muted);
}

.note-form,
.disposition-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.note-form label,
.disposition-form label {
  display: grid;
  gap: 6px;
}

.note-form span,
.disposition-form span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.note-form select,
.note-form textarea,
.disposition-form select,
.disposition-form input,
.disposition-form textarea {
  width: 100%;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 9px;
  box-sizing: border-box;
}

.note-text {
  grid-column: 1 / -1;
}

.note-form button,
.disposition-form button {
  justify-self: start;
}

.notes-empty,
.note-row {
  margin-top: 10px;
}

.notes-empty {
  color: var(--text-muted);
}

.note-row {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  padding: 10px;
}

.note-row > .status-pill {
  display: inline-block;
  margin-top: 8px;
}

.note-row div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.note-row span,
.note-row small {
  color: var(--text-muted);
}

.note-row p {
  margin: 8px 0;
}

.note-meta {
  flex-wrap: wrap;
  margin-top: 8px;
}

.resolution-note {
  border-left: 3px solid var(--accent-primary);
  padding-left: 8px;
}

.raw-toggle {
  margin-top: 12px;
}

.raw-diff {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  margin: 10px 0 0;
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .review-summary,
  .rollup-grid,
  .table-row,
  .note-form,
  .disposition-form {
    grid-template-columns: 1fr;
  }
}
</style>
