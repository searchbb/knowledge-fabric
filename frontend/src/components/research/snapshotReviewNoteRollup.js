const STATUSES = ['open', 'acknowledged', 'resolved', 'deferred']
const ATTENTION_STATUSES = new Set(['open', 'acknowledged', 'deferred'])
const STATUS_PRIORITY = {
  open: 0,
  acknowledged: 1,
  deferred: 2,
  resolved: 3,
}

function normalizeStatus(status) {
  return STATUSES.includes(status) ? status : 'open'
}

function preview(value, limit = 140) {
  const text = String(value || '').trim()
  if (text.length <= limit) return text
  return `${text.slice(0, limit)}...`
}

function sortNotes(a, b) {
  const statusDelta = STATUS_PRIORITY[a.status] - STATUS_PRIORITY[b.status]
  if (statusDelta !== 0) return statusDelta
  const aTime = a.updated_at || a.created_at || ''
  const bTime = b.updated_at || b.created_at || ''
  const timeDelta = String(bTime).localeCompare(String(aTime))
  if (timeDelta !== 0) return timeDelta
  return String(a.note_id || '').localeCompare(String(b.note_id || ''))
}

function rollupNote(note) {
  return {
    note_id: note.note_id || '',
    status: normalizeStatus(note.status),
    title: note.target_ref?.section_key || 'other',
    body_preview: preview(note.note),
    owner: note.owner || '',
    resolution_note: note.resolution_note || '',
    created_at: note.created_at || '',
    updated_at: note.updated_at || '',
    resolved_at: note.resolved_at || '',
    resolved_by: note.resolved_by || '',
  }
}

export function buildSnapshotReviewNoteRollup(notes = [], options = {}) {
  const snapshotId = options.snapshot_id || notes.find((note) => note?.snapshot_id)?.snapshot_id || ''
  const projectId = options.project_id || notes.find((note) => note?.project_id)?.project_id || ''
  const normalized = notes.filter(Boolean).map(rollupNote)
  const statusCounts = {
    open: 0,
    acknowledged: 0,
    resolved: 0,
    deferred: 0,
  }
  for (const note of normalized) {
    statusCounts[note.status] += 1
  }
  const attentionNotes = normalized
    .filter((note) => ATTENTION_STATUSES.has(note.status))
    .sort(sortNotes)
  const deferredNotes = normalized
    .filter((note) => note.status === 'deferred')
    .sort(sortNotes)
  const latest = normalized
    .map((note) => note.updated_at || note.created_at || '')
    .filter(Boolean)
    .sort()
    .at(-1) || ''

  return {
    snapshot_id: snapshotId,
    project_id: projectId,
    total_notes: normalized.length,
    status_counts: statusCounts,
    attention_counts: {
      unresolved: statusCounts.open + statusCounts.acknowledged,
      deferred: statusCounts.deferred,
      active_attention: statusCounts.open + statusCounts.acknowledged + statusCounts.deferred,
    },
    attention_notes: attentionNotes,
    deferred_notes: deferredNotes,
    latest_note_updated_at: latest,
    source: {
      derived_from: 'snapshot_review_notes',
      read_only: true,
      mutates_gate_state: false,
      mutates_snapshot: false,
      mutates_governance_review: false,
    },
  }
}

export function getSnapshotReviewNoteAttentionNotes(rollup) {
  return rollup?.attention_notes || []
}

export function formatSnapshotReviewNoteStatusLabel(status) {
  return {
    open: 'Open',
    acknowledged: 'Acknowledged',
    resolved: 'Resolved',
    deferred: 'Deferred',
  }[normalizeStatus(status)]
}
