import { describe, expect, it } from 'vitest'
import {
  buildGateReviewSnapshotAttentionContext,
  hasActiveSnapshotAttention,
} from '../gateReviewSnapshotAttentionContext'

const governanceReview = { review_id: 'gr_demo', title: 'P9 governance review' }
const snapshots = [
  {
    snapshot_id: 'rs_linked',
    title: 'Linked gate baseline',
    linked_governance_review: { governance_review_id: 'gr_demo' },
    created_at: '2026-04-28T00:00:00.000000',
  },
  {
    snapshot_id: 'rs_project',
    title: 'Project baseline',
    linked_governance_review: { governance_review_id: 'gr_other' },
    created_at: '2026-04-27T00:00:00.000000',
  },
  {
    snapshot_id: 'rs_resolved',
    title: 'Resolved baseline',
    linked_governance_review: {},
    created_at: '2026-04-26T00:00:00.000000',
  },
]

describe('gateReviewSnapshotAttentionContext', () => {
  it('returns a read-only empty context when no snapshots exist', () => {
    const context = buildGateReviewSnapshotAttentionContext({ governanceReview })

    expect(context.governance_review_id).toBe('gr_demo')
    expect(context.snapshots).toEqual([])
    expect(context.totals.active_attention).toBe(0)
    expect(context.disclaimers).toEqual(expect.objectContaining({
      read_only: true,
      does_not_change_gate_readiness: true,
      does_not_mutate_governance_review: true,
      does_not_mutate_snapshot: true,
    }))
    expect(hasActiveSnapshotAttention(context)).toBe(false)
  })

  it('aggregates linked and project snapshot note attention without mutating inputs', () => {
    const originalSnapshots = structuredClone(snapshots)
    const notesBySnapshotId = {
      rs_linked: [
        { note_id: 'srn_open', status: 'open', severity: 'watch', note: 'Open note', target_ref: { section_key: 'governance_gate', asset_kind: 'governance_review', asset_id: 'gr_demo', field: 'gate_decision' }, created_at: '2026-04-28T00:00:00.000000' },
        { note_id: 'srn_ack', status: 'acknowledged', severity: 'info', note: 'Acknowledged note', target_ref: { section_key: 'raw_diff' }, updated_at: '2026-04-29T00:00:00.000000' },
        { note_id: 'srn_resolved', status: 'resolved', note: 'Resolved note', target_ref: { section_key: 'other' } },
      ],
      rs_project: [
        { note_id: 'srn_deferred', status: 'deferred', severity: 'blocker', note: 'Deferred note', target_ref: { section_key: 'review_history_activity' }, created_at: '2026-04-30T00:00:00.000000' },
      ],
      rs_resolved: [
        { note_id: 'srn_done', status: 'resolved', note: 'Done', target_ref: { section_key: 'other' } },
      ],
    }

    const context = buildGateReviewSnapshotAttentionContext({
      governanceReview,
      snapshots,
      notesBySnapshotId,
      topNoteLimit: 2,
    })

    expect(context.linked_snapshot_count).toBe(1)
    expect(context.related_snapshot_count).toBe(2)
    expect(context.snapshots.map((row) => row.snapshot_id)).toEqual(['rs_linked', 'rs_project'])
    expect(context.totals).toEqual({
      total_notes: 4,
      open: 1,
      acknowledged: 1,
      resolved: 1,
      deferred: 1,
      active_attention: 3,
    })
    expect(context.snapshots[0].relation).toBe('linked_governance_review')
    expect(context.snapshots[0].note_rollup).toEqual(expect.objectContaining({
      mutates_gate_state: false,
      mutates_snapshot: false,
      mutates_governance_review: false,
    }))
    expect(context.snapshots[0].latest_note_timestamp).toBe('2026-04-29T00:00:00.000000')
    expect(context.snapshots[0].top_attention_notes.map((note) => note.note_id)).toEqual(['srn_open', 'srn_ack'])
    expect(context.snapshots[0].top_attention_notes[0]).toEqual(expect.objectContaining({
      disposition: 'open',
      severity: 'watch',
      title: 'governance_gate',
    }))
    expect(context.snapshots[0].top_attention_notes[0].trace_ref).toEqual(expect.objectContaining({
      source_kind: 'snapshot_review_note',
      source_label: 'Snapshot review note',
      snapshot_id: 'rs_linked',
      snapshot_title: 'Linked gate baseline',
      relation_label: 'Linked snapshot',
      note_id: 'srn_open',
      disposition: 'open',
      severity: 'watch',
      readonly: true,
      affects_gate_readiness: false,
    }))
    expect(context.snapshots[0].top_attention_notes[0].trace_ref.target).toEqual({
      section_key: 'governance_gate',
      asset_kind: 'governance_review',
      asset_id: 'gr_demo',
      field: 'gate_decision',
    })
    expect(context.snapshots[0].top_attention_notes[0].trace_ref.display.target).toBe(
      'Section: governance_gate · Asset: governance_review / gr_demo · Field: gate_decision',
    )
    expect(context.snapshots[0].top_attention_notes.map((note) => note.trace_ref.note_id)).not.toContain('srn_resolved')
    expect(hasActiveSnapshotAttention(context)).toBe(true)
    expect(snapshots).toEqual(originalSnapshots)
  })

  it('keeps a linked snapshot visible even when it has no active notes', () => {
    const context = buildGateReviewSnapshotAttentionContext({
      governanceReview,
      snapshots: [snapshots[0]],
      notesBySnapshotId: {
        rs_linked: [{ note_id: 'srn_done', status: 'resolved', note: 'Done' }],
      },
    })

    expect(context.snapshots).toHaveLength(1)
    expect(context.snapshots[0].note_rollup.resolved).toBe(1)
    expect(context.snapshots[0].note_rollup.active_attention).toBe(0)
    expect(context.snapshots[0].top_attention_notes).toEqual([])
  })

  it('builds safe trace metadata when target_ref is missing', () => {
    const context = buildGateReviewSnapshotAttentionContext({
      governanceReview,
      snapshots: [snapshots[0]],
      notesBySnapshotId: {
        rs_linked: [{ note_id: 'srn_missing_target', status: 'open', note: 'Missing target note' }],
      },
    })

    const trace = context.snapshots[0].top_attention_notes[0].trace_ref
    expect(trace.target).toEqual({
      section_key: 'Unspecified section',
      asset_kind: '',
      asset_id: '',
      field: '',
    })
    expect(trace.display.target).toBe('Section: Unspecified section')
    expect(trace.display.reason).toBe('Trace only · active human attention · no gate readiness change')
  })
})
