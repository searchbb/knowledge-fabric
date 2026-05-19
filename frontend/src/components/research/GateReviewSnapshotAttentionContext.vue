<template>
  <section class="snapshot-attention-context">
    <div class="context-head">
      <div>
        <h4>Snapshot note attention context</h4>
        <p>Read-only context derived from manual snapshot review notes. It does not change gate readiness.</p>
      </div>
      <span class="status-pill">read-only</span>
    </div>

    <div class="context-summary">
      <div><strong>{{ totals.active_attention || 0 }}</strong><span>Active attention</span></div>
      <div><strong>{{ totals.open || 0 }}</strong><span>Open</span></div>
      <div><strong>{{ totals.acknowledged || 0 }}</strong><span>Acknowledged</span></div>
      <div><strong>{{ totals.deferred || 0 }}</strong><span>Deferred</span></div>
      <div><strong>{{ totals.resolved || 0 }}</strong><span>Resolved</span></div>
      <div><strong>{{ context.linked_snapshot_count || 0 }}</strong><span>Linked snapshots</span></div>
    </div>

    <p v-if="!snapshots.length" class="empty-line">
      No active snapshot-note attention found for this governance review. This does not imply gate readiness.
    </p>
    <p v-else-if="!context.linked_snapshot_count" class="empty-line">
      No snapshots are directly linked to this governance review. Showing project snapshot context only.
    </p>

    <article
      v-for="snapshot in snapshots"
      :key="snapshot.snapshot_id"
      class="snapshot-context-row"
    >
      <div class="snapshot-topline">
        <div>
          <strong>{{ snapshot.snapshot_title }}</strong>
          <p>{{ snapshot.snapshot_id }}</p>
        </div>
        <span class="status-pill" :class="{ warn: snapshot.relation === 'project_snapshot_context' }">
          {{ relationLabel(snapshot.relation) }}
        </span>
      </div>

      <div class="count-row">
        <span>total {{ snapshot.note_rollup.total }}</span>
        <span>open {{ snapshot.note_rollup.open }}</span>
        <span>ack {{ snapshot.note_rollup.acknowledged }}</span>
        <span>deferred {{ snapshot.note_rollup.deferred }}</span>
        <span>resolved {{ snapshot.note_rollup.resolved }}</span>
      </div>
      <small>Latest note {{ snapshot.latest_note_timestamp || 'none' }}</small>

      <div v-if="snapshot.top_attention_notes.length" class="attention-notes">
        <article
          v-for="note in snapshot.top_attention_notes"
          :key="note.note_id"
          class="attention-note"
        >
          <span class="status-pill" :class="{ warn: note.disposition === 'open' || note.disposition === 'deferred' }">
            {{ note.disposition }}
          </span>
          <strong>{{ note.title }}</strong>
          <p>{{ note.body_preview }}</p>
          <dl v-if="note.trace_ref" class="trace-meta">
            <div>
              <dt>Source</dt>
              <dd>{{ note.trace_ref.display?.source || note.trace_ref.source_label }}</dd>
            </div>
            <div>
              <dt>Target</dt>
              <dd>{{ note.trace_ref.display?.target || 'Section: Unspecified section' }}</dd>
            </div>
            <div>
              <dt>Trace</dt>
              <dd>{{ note.trace_ref.display?.reason || 'Trace only · no gate readiness change' }}</dd>
            </div>
          </dl>
        </article>
      </div>
      <p v-else class="empty-line">Resolved notes are counted but there is no active note preview.</p>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  context: { type: Object, default: () => ({ snapshots: [], totals: {} }) },
})

const totals = computed(() => props.context?.totals || {})
const snapshots = computed(() => props.context?.snapshots || [])

function relationLabel(relation) {
  return relation === 'linked_governance_review' ? 'Linked snapshot' : 'Project context'
}
</script>

<style scoped>
.snapshot-attention-context {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
  padding: 12px;
  margin: 12px 0;
}

.context-head,
.snapshot-topline,
.count-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.context-head,
.snapshot-topline {
  justify-content: space-between;
}

.context-head h4 {
  margin: 0 0 4px;
}

.context-head p,
.snapshot-context-row p,
.snapshot-context-row small,
.empty-line {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.context-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
  gap: 8px;
  margin: 12px 0;
}

.context-summary div,
.snapshot-context-row,
.attention-note {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
}

.context-summary div {
  padding: 10px;
}

.context-summary strong {
  display: block;
}

.context-summary span,
.count-row,
.attention-note p {
  color: var(--text-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.snapshot-context-row {
  padding: 10px;
  margin-top: 10px;
}

.count-row {
  margin: 8px 0;
}

.attention-notes {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.attention-note {
  padding: 8px;
}

.attention-note strong {
  display: block;
  margin: 4px 0;
}

.trace-meta {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
}

.trace-meta div {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 6px;
}

.trace-meta dt,
.trace-meta dd {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
}

.trace-meta dt {
  color: var(--text-muted);
}

.trace-meta dd {
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.status-pill.warn {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

@media (max-width: 900px) {
  .context-summary {
    grid-template-columns: repeat(2, minmax(112px, 1fr));
  }
}
</style>
