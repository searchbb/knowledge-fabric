import { describe, expect, it } from 'vitest'
import { buildGateReviewSnapshotAttentionContext } from '../gateReviewSnapshotAttentionContext'
import {
  expectedGoldenSnapshotSummaries,
  expectedGoldenSummary,
  expectedGoldenTargets,
  expectedGoldenTraceSlices,
  goldenGovernanceReview,
  goldenNotesBySnapshotId,
  goldenOptions,
  goldenSnapshots,
} from './fixtures/gateReviewAttentionGoldenCase'

function deepClone(value) {
  return JSON.parse(JSON.stringify(value))
}

function collectKeys(value, keys = new Set()) {
  if (Array.isArray(value)) {
    value.forEach((item) => collectKeys(item, keys))
    return keys
  }
  if (value && typeof value === 'object') {
    Object.keys(value).forEach((key) => {
      keys.add(key)
      collectKeys(value[key], keys)
    })
  }
  return keys
}

function buildGoldenContext() {
  return buildGateReviewSnapshotAttentionContext({
    governanceReview: goldenGovernanceReview,
    snapshots: goldenSnapshots,
    notesBySnapshotId: goldenNotesBySnapshotId,
    topNoteLimit: goldenOptions.topNoteLimit,
  })
}

function findSnapshot(context, snapshotId) {
  return context.snapshots.find((snapshot) => snapshot.snapshot_id === snapshotId)
}

function findNote(context, noteId) {
  return context.snapshots
    .flatMap((snapshot) => snapshot.top_attention_notes)
    .find((note) => note.note_id === noteId)
}

describe('gate review attention golden fixture', () => {
  it('matches the canonical summary slices without freezing the full helper output', () => {
    const context = buildGoldenContext()

    expect(context.governance_review_id).toBe(expectedGoldenSummary.governance_review_id)
    expect(context.linked_snapshot_count).toBe(expectedGoldenSummary.linked_snapshot_count)
    expect(context.related_snapshot_count).toBe(expectedGoldenSummary.related_snapshot_count)
    expect(context.snapshots.map((snapshot) => snapshot.snapshot_id)).toEqual(
      expectedGoldenSummary.included_snapshot_ids,
    )
    for (const snapshotId of expectedGoldenSummary.excluded_snapshot_ids) {
      expect(findSnapshot(context, snapshotId)).toBeUndefined()
    }
    expect(context.totals).toEqual(expectedGoldenSummary.totals)
  })

  it('keeps linked, resolved-only, and project-context inclusion semantics stable', () => {
    const context = buildGoldenContext()

    for (const [snapshotId, expected] of Object.entries(expectedGoldenSnapshotSummaries)) {
      const snapshot = findSnapshot(context, snapshotId)
      expect(snapshot).toBeTruthy()
      expect(snapshot.relation).toBe(expected.relation)
      expect(snapshot.note_rollup).toEqual(expect.objectContaining({
        total: expected.total,
        open: expected.open,
        acknowledged: expected.acknowledged,
        deferred: expected.deferred,
        resolved: expected.resolved,
        active_attention: expected.active_attention,
      }))
      expect(snapshot.top_attention_notes.map((note) => note.note_id)).toEqual(expected.active_note_ids)
    }

    expect(findSnapshot(context, 'rs_golden_project_resolved')).toBeUndefined()
  })

  it('keeps active note ordering and target labels stable for the golden evidence case', () => {
    const context = buildGoldenContext()

    for (const [noteId, targetLabel] of Object.entries(expectedGoldenTargets)) {
      const note = findNote(context, noteId)
      expect(note).toBeTruthy()
      expect(note.trace_ref.display.target).toBe(targetLabel)
    }
    expect(findNote(context, 'note-resolved-linked-newer')).toBeUndefined()
    expect(findNote(context, 'note-resolved-linked-only')).toBeUndefined()
  })

  it('preserves stable trace source, disposition, target, and read-only slices', () => {
    const context = buildGoldenContext()

    for (const [noteId, expected] of Object.entries(expectedGoldenTraceSlices)) {
      const note = findNote(context, noteId)
      expect(note).toBeTruthy()
      expect(note.disposition).toBe(expected.disposition)
      expect(note.trace_ref).toEqual(expect.objectContaining(expected))
      expect(note.trace_ref.display.reason).toBe('Trace only · active human attention · no gate readiness change')
    }
  })

  it('does not mutate source fixture data or acquire runtime capability fields', () => {
    const source = {
      governanceReview: goldenGovernanceReview,
      snapshots: goldenSnapshots,
      notesBySnapshotId: goldenNotesBySnapshotId,
    }
    const before = deepClone(source)
    const context = buildGoldenContext()

    expect(source).toEqual(before)

    const forbiddenKeys = [
      'assignee',
      'assignment',
      'task',
      'workflow',
      'readiness_verdict',
      'gate_decision',
      'route',
      'href',
      'edit_action',
      'mutation',
      'dataClient',
      'model_call',
      'scheduler',
      'worker',
      'queue',
      'dag',
    ]
    const keys = collectKeys(context)
    for (const key of forbiddenKeys) {
      expect(keys.has(key)).toBe(false)
    }
  })
})
