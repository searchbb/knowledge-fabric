<template>
  <section class="snapshot-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Gate Snapshot</div>
        <p>手工冻结当前研究资产状态，并用只读对比查看后续变化。</p>
      </div>
      <button type="button" class="btn-secondary" :disabled="loading" @click="$emit('refresh')">
        刷新基线
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <p v-if="createError" class="inline-error">{{ createError }}</p>

    <div class="summary-grid">
      <div><strong>{{ snapshots.length }}</strong><span>Snapshots</span></div>
      <div><strong>{{ selectedSnapshot?.asset_counts?.governance_reviews || 0 }}</strong><span>Reviews</span></div>
      <div><strong>{{ selectedSnapshot?.asset_counts?.leadership_briefings || 0 }}</strong><span>Briefings</span></div>
      <div><strong>{{ diff?.summary?.has_changes ? 'yes' : 'no' }}</strong><span>Changed</span></div>
    </div>

    <div class="snapshot-layout">
      <div class="snapshot-list">
        <form class="create-form" @submit.prevent="submitSnapshot">
          <label>
            <span>基线标题</span>
            <input v-model="form.title" :disabled="creating" type="text" placeholder="P11 Gate Baseline" />
          </label>
          <label>
            <span>原因</span>
            <textarea v-model="form.reason" :disabled="creating" rows="2" placeholder="冻结当前状态用于后续审查" />
          </label>
          <button type="submit" class="btn-primary" :disabled="!canCreate">
            {{ creating ? '创建中...' : '创建基线' }}
          </button>
        </form>

        <div v-if="loading" class="state-line">正在加载基线...</div>
        <div v-else-if="!snapshots.length" class="empty-state">暂无基线快照</div>
        <button
          v-for="snapshot in snapshots"
          v-else
          :key="snapshot.snapshot_id"
          type="button"
          class="snapshot-row"
          :class="{ active: snapshot.snapshot_id === selectedId }"
          @click="selectSnapshot(snapshot.snapshot_id)"
        >
          <strong>{{ snapshot.title }}</strong>
          <span>{{ snapshot.gate_type }} · {{ snapshot.snapshot_id }}</span>
          <small>{{ snapshot.created_at }}</small>
        </button>
      </div>

      <div class="snapshot-detail">
        <div v-if="selectedSnapshot" class="detail-card">
          <div class="detail-head">
            <div>
              <h3>{{ selectedSnapshot.title }}</h3>
              <p>{{ selectedSnapshot.reason || selectedSnapshot.snapshot_id }}</p>
            </div>
            <button type="button" class="btn-secondary" :disabled="diffing" @click="$emit('diff-snapshot', selectedSnapshot.snapshot_id)">
              对比当前
            </button>
          </div>

          <div class="meta-grid">
            <div><span>Gate</span><strong>{{ selectedSnapshot.gate_type || 'manual_gate' }}</strong></div>
            <div><span>History</span><strong>{{ selectedSnapshot.review_history_watermark?.entry_count || 0 }}</strong></div>
            <div><span>Governance</span><strong>{{ selectedSnapshot.linked_governance_review?.gate_decision || 'none' }}</strong></div>
            <div><span>Briefing</span><strong>{{ selectedSnapshot.linked_leadership_briefing?.readiness || 'none' }}</strong></div>
          </div>

          <div class="fingerprint">Fingerprint · {{ shortFingerprint(selectedSnapshot.snapshot_fingerprint) }}</div>
        </div>

        <div v-if="diffing" class="state-line">正在对比当前状态...</div>
        <SnapshotEvidenceReviewPanel
          v-if="selectedSnapshot && diff"
          :snapshot="selectedSnapshot"
          :diff="diff"
          :notes="reviewNotes"
          :notes-loading="notesLoading"
          :creating-note="creatingNote"
          :updating-note="updatingNote"
          :note-error="noteError"
          @create-note="$emit('create-review-note', $event)"
          @update-note="$emit('update-review-note', $event)"
        />

        <div v-if="diff" class="detail-card diff-card">
          <h3>原始差异明细</h3>
          <div class="asset-topline">
            <span class="status-pill" :class="{ warn: diff.summary?.has_changes }">{{ diff.summary?.has_changes ? 'changed' : 'unchanged' }}</span>
            <span class="status-pill">added {{ diff.summary?.assets_added || 0 }}</span>
            <span class="status-pill">changed {{ diff.summary?.assets_changed || 0 }}</span>
            <span class="status-pill">history {{ diff.summary?.review_history_changed ? 'changed' : 'same' }}</span>
          </div>

          <section v-if="Object.keys(diff.asset_id_changes || {}).length" class="diff-section">
            <h4>Asset IDs</h4>
            <article v-for="(change, kind) in diff.asset_id_changes" :key="kind" class="compact-row">
              <strong>{{ kind }}</strong>
              <p>Added {{ (change.added || []).join(', ') || 'none' }}</p>
              <p>Removed {{ (change.removed || []).join(', ') || 'none' }}</p>
            </article>
          </section>

          <section v-if="Object.keys(diff.asset_state_changes || {}).length" class="diff-section">
            <h4>State Changes</h4>
            <article v-for="(rows, kind) in diff.asset_state_changes" :key="kind" class="compact-row">
              <strong>{{ kind }}</strong>
              <p>{{ rows.length }} changed assets</p>
            </article>
          </section>

          <div class="compact-row">
            <strong>Governance</strong>
            <p>{{ diff.governance_change?.from_gate_decision || 'none' }} → {{ diff.governance_change?.to_gate_decision || 'none' }}</p>
          </div>
          <div class="compact-row">
            <strong>Leadership Briefing</strong>
            <p>{{ diff.leadership_briefing_change?.from_readiness || 'none' }} → {{ diff.leadership_briefing_change?.to_readiness || 'none' }}</p>
          </div>
        </div>

        <div v-if="!selectedSnapshot" class="empty-state">选择或创建一个基线快照</div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import SnapshotEvidenceReviewPanel from './SnapshotEvidenceReviewPanel.vue'

const props = defineProps({
  snapshots: { type: Array, default: () => [] },
  selectedSnapshot: { type: Object, default: null },
  diff: { type: Object, default: null },
  reviewNotes: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  creating: { type: Boolean, default: false },
  diffing: { type: Boolean, default: false },
  notesLoading: { type: Boolean, default: false },
  creatingNote: { type: Boolean, default: false },
  updatingNote: { type: Boolean, default: false },
  error: { type: String, default: '' },
  createError: { type: String, default: '' },
  noteError: { type: String, default: '' },
})

const emit = defineEmits(['refresh', 'create-snapshot', 'select-snapshot', 'diff-snapshot', 'create-review-note', 'update-review-note'])

const selectedId = ref('')
const form = reactive({
  title: 'P11 Gate Baseline',
  reason: 'Freeze current research state before next stage.',
  gate_type: 'p11_gate',
})
const canCreate = computed(() => Boolean(form.title.trim() && !props.creating))

function selectSnapshot(snapshotId) {
  selectedId.value = snapshotId
  emit('select-snapshot', snapshotId)
}

function submitSnapshot() {
  if (!canCreate.value) return
  emit('create-snapshot', {
    title: form.title.trim(),
    reason: form.reason,
    gate_type: form.gate_type,
  })
}

function shortFingerprint(value) {
  return value ? `${String(value).slice(0, 18)}...` : 'none'
}

watch(() => props.snapshots, (snapshots) => {
  if (!snapshots.some((snapshot) => snapshot.snapshot_id === selectedId.value)) {
    selectedId.value = snapshots[0]?.snapshot_id || ''
    if (selectedId.value) emit('select-snapshot', selectedId.value)
  }
}, { immediate: true })

watch(() => props.selectedSnapshot?.snapshot_id, (snapshotId) => {
  if (snapshotId) selectedId.value = snapshotId
})
</script>

<style scoped>
.snapshot-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head,
.detail-head,
.asset-topline {
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
.snapshot-row span,
.snapshot-row small,
.detail-card p,
.fingerprint,
.compact-row p {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.summary-grid,
.meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid div,
.meta-grid div,
.snapshot-row,
.create-form,
.detail-card,
.compact-row {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
}

.summary-grid div,
.meta-grid div {
  padding: 10px;
}

.summary-grid strong,
.meta-grid strong {
  display: block;
  font-size: 18px;
}

.summary-grid span,
.meta-grid span {
  color: var(--text-muted);
  font-size: 12px;
}

.snapshot-layout {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.6fr);
  gap: 12px;
  margin-top: 14px;
}

.snapshot-list,
.snapshot-detail,
.create-form,
.diff-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.snapshot-row {
  text-align: left;
  padding: 10px;
  color: var(--text-primary);
  cursor: pointer;
}

.snapshot-row.active {
  border-color: var(--accent-primary);
}

.snapshot-row strong,
.snapshot-row span,
.snapshot-row small {
  display: block;
  overflow-wrap: anywhere;
}

.create-form,
.detail-card,
.compact-row {
  padding: 12px;
}

.create-form label {
  display: grid;
  gap: 6px;
}

.create-form span,
.diff-section h4 {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.create-form input,
.create-form textarea {
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 10px;
  box-sizing: border-box;
}

.detail-card h3,
.diff-section h4 {
  margin: 0 0 6px;
}

.fingerprint {
  margin-top: 10px;
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .summary-grid,
  .meta-grid,
  .snapshot-layout {
    grid-template-columns: 1fr;
  }
}
</style>
