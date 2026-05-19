import { buildSnapshotReviewNoteRollup } from './snapshotReviewNoteRollup'

function snapshotReviewId(snapshot = {}) {
  return snapshot.linked_governance_review?.governance_review_id || ''
}

function snapshotTitle(snapshot = {}) {
  return snapshot.title || snapshot.snapshot_id || 'Untitled snapshot'
}

function relationLabel(relation) {
  return relation === 'linked_governance_review' ? 'Linked snapshot' : 'Project context'
}

function sourceNoteById(notes = []) {
  return new Map(notes.filter(Boolean).map((note) => [note.note_id || '', note]))
}

function targetRef(note = {}) {
  const target = note.target_ref || {}
  return {
    section_key: target.section_key || 'Unspecified section',
    asset_kind: target.asset_kind || '',
    asset_id: target.asset_id || '',
    field: target.field || '',
  }
}

function targetLabel(target = {}) {
  const parts = [`Section: ${target.section_key || 'Unspecified section'}`]
  if (target.asset_kind || target.asset_id) {
    parts.push(`Asset: ${target.asset_kind || 'unknown'} / ${target.asset_id || 'unknown'}`)
  }
  if (target.field) parts.push(`Field: ${target.field}`)
  return parts.join(' · ')
}

function traceRef({ note, snapshot, relation }) {
  const title = snapshotTitle(snapshot)
  const target = targetRef(note)
  const label = relationLabel(relation)
  return {
    source_kind: 'snapshot_review_note',
    source_label: 'Snapshot review note',
    snapshot_id: snapshot.snapshot_id || '',
    snapshot_title: title,
    relation_label: label,
    note_id: note.note_id || '',
    disposition: note.status || 'open',
    severity: note.severity || '',
    target,
    readonly: true,
    affects_gate_readiness: false,
    display: {
      source: `${title} · ${label} · ${note.note_id || 'unknown note'}`,
      target: targetLabel(target),
      reason: 'Trace only · active human attention · no gate readiness change',
    },
  }
}

function topAttentionNotes(rollup, notes = [], limit = 3, snapshot = {}, relation = 'project_snapshot_context') {
  const byId = sourceNoteById(notes)
  return (rollup.attention_notes || []).slice(0, limit).map((note) => {
    const source = byId.get(note.note_id) || {}
    const traceNote = { ...source, note_id: note.note_id, status: note.status }
    return {
      note_id: note.note_id,
      disposition: note.status,
      severity: source.severity || '',
      title: note.title,
      body_preview: note.body_preview,
      created_at: note.created_at,
      updated_at: note.updated_at,
      trace_ref: traceRef({ note: traceNote, snapshot, relation }),
    }
  })
}

function snapshotContext(snapshot, notes, governanceReviewId, limit) {
  const rollup = buildSnapshotReviewNoteRollup(notes, {
    snapshot_id: snapshot.snapshot_id || '',
  })
  const linked = Boolean(governanceReviewId && snapshotReviewId(snapshot) === governanceReviewId)
  const relation = linked ? 'linked_governance_review' : 'project_snapshot_context'
  return {
    snapshot_id: snapshot.snapshot_id || '',
    snapshot_title: snapshotTitle(snapshot),
    snapshot_created_at: snapshot.created_at || '',
    relation,
    note_rollup: {
      total: rollup.total_notes,
      open: rollup.status_counts.open,
      acknowledged: rollup.status_counts.acknowledged,
      resolved: rollup.status_counts.resolved,
      deferred: rollup.status_counts.deferred,
      active_attention: rollup.attention_counts.active_attention,
      mutates_gate_state: rollup.source.mutates_gate_state === true,
      mutates_snapshot: rollup.source.mutates_snapshot === true,
      mutates_governance_review: rollup.source.mutates_governance_review === true,
    },
    latest_note_timestamp: rollup.latest_note_updated_at || null,
    top_attention_notes: topAttentionNotes(rollup, notes, limit, snapshot, relation),
  }
}

export function buildGateReviewSnapshotAttentionContext({
  governanceReview = null,
  snapshots = [],
  notesBySnapshotId = {},
  topNoteLimit = 3,
} = {}) {
  const governanceReviewId = governanceReview?.review_id || ''
  const rows = snapshots
    .filter(Boolean)
    .map((snapshot) => {
      const notes = Array.isArray(notesBySnapshotId[snapshot.snapshot_id])
        ? notesBySnapshotId[snapshot.snapshot_id]
        : Array.isArray(snapshot.snapshot_review_notes)
          ? snapshot.snapshot_review_notes
          : []
      return snapshotContext(snapshot, notes, governanceReviewId, topNoteLimit)
    })
    .filter((row) => row.relation === 'linked_governance_review' || row.note_rollup.active_attention > 0)
    .sort((a, b) => {
      if (a.relation !== b.relation) return a.relation === 'linked_governance_review' ? -1 : 1
      return String(b.latest_note_timestamp || b.snapshot_created_at || '').localeCompare(
        String(a.latest_note_timestamp || a.snapshot_created_at || ''),
      )
    })

  const totals = rows.reduce((acc, row) => {
    acc.total_notes += row.note_rollup.total
    acc.open += row.note_rollup.open
    acc.acknowledged += row.note_rollup.acknowledged
    acc.resolved += row.note_rollup.resolved
    acc.deferred += row.note_rollup.deferred
    acc.active_attention += row.note_rollup.active_attention
    return acc
  }, {
    total_notes: 0,
    open: 0,
    acknowledged: 0,
    resolved: 0,
    deferred: 0,
    active_attention: 0,
  })

  return {
    governance_review_id: governanceReviewId || null,
    linked_snapshot_count: rows.filter((row) => row.relation === 'linked_governance_review').length,
    related_snapshot_count: rows.length,
    snapshots: rows,
    totals,
    disclaimers: {
      read_only: true,
      does_not_change_gate_readiness: true,
      does_not_mutate_governance_review: true,
      does_not_mutate_snapshot: true,
    },
  }
}

export function hasActiveSnapshotAttention(context = {}) {
  return (context.totals?.active_attention || 0) > 0
}
