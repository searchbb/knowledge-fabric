import { describe, expect, it } from 'vitest'
import {
  buildSnapshotReviewNoteRollup,
  formatSnapshotReviewNoteStatusLabel,
  getSnapshotReviewNoteAttentionNotes,
} from '../snapshotReviewNoteRollup'

describe('snapshotReviewNoteRollup', () => {
  it('returns a stable empty rollup', () => {
    const rollup = buildSnapshotReviewNoteRollup([])

    expect(rollup.total_notes).toBe(0)
    expect(rollup.status_counts).toEqual({ open: 0, acknowledged: 0, resolved: 0, deferred: 0 })
    expect(rollup.attention_counts).toEqual({ unresolved: 0, deferred: 0, active_attention: 0 })
    expect(rollup.attention_notes).toEqual([])
    expect(rollup.source).toEqual(expect.objectContaining({
      derived_from: 'snapshot_review_notes',
      read_only: true,
      mutates_gate_state: false,
      mutates_snapshot: false,
      mutates_governance_review: false,
    }))
  })

  it('counts mixed note statuses and excludes resolved notes from active attention', () => {
    const rollup = buildSnapshotReviewNoteRollup([
      { note_id: 'srn_resolved', status: 'resolved', note: 'Resolved note', updated_at: '2026-04-28T00:03:00' },
      { note_id: 'srn_open', status: 'open', note: 'Open note', updated_at: '2026-04-28T00:01:00' },
      { note_id: 'srn_deferred', status: 'deferred', note: 'Deferred note', updated_at: '2026-04-28T00:04:00' },
      { note_id: 'srn_ack', status: 'acknowledged', note: 'Acknowledged note', updated_at: '2026-04-28T00:02:00' },
    ])

    expect(rollup.total_notes).toBe(4)
    expect(rollup.status_counts).toEqual({ open: 1, acknowledged: 1, resolved: 1, deferred: 1 })
    expect(rollup.attention_counts.unresolved).toBe(2)
    expect(rollup.attention_counts.active_attention).toBe(3)
    expect(rollup.attention_notes.map((note) => note.note_id)).toEqual(['srn_open', 'srn_ack', 'srn_deferred'])
    expect(rollup.deferred_notes.map((note) => note.note_id)).toEqual(['srn_deferred'])
  })

  it('normalizes unknown statuses to open and formats labels', () => {
    const rollup = buildSnapshotReviewNoteRollup([
      { note_id: 'srn_unknown', status: 'triaged', note: 'Unknown status note' },
    ])

    expect(rollup.status_counts.open).toBe(1)
    expect(getSnapshotReviewNoteAttentionNotes(rollup)[0].status).toBe('open')
    expect(formatSnapshotReviewNoteStatusLabel('resolved')).toBe('Resolved')
    expect(formatSnapshotReviewNoteStatusLabel('triaged')).toBe('Open')
  })

  it('truncates long note previews deterministically', () => {
    const rollup = buildSnapshotReviewNoteRollup([
      { note_id: 'srn_long', status: 'open', note: 'x'.repeat(160) },
    ])

    expect(rollup.attention_notes[0].body_preview).toHaveLength(143)
    expect(rollup.attention_notes[0].body_preview.endsWith('...')).toBe(true)
  })
})
