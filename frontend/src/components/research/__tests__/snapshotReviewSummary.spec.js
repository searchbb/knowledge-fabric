import { describe, expect, it } from 'vitest'
import { buildSnapshotReviewSummary } from '../snapshotReviewSummary'

const snapshot = {
  snapshot_id: 'rs_demo',
  title: 'P11 Gate Baseline',
  created_at: '2026-04-28T00:00:00.000000',
}

describe('buildSnapshotReviewSummary', () => {
  it('returns a safe unchanged summary for empty diffs', () => {
    const summary = buildSnapshotReviewSummary(snapshot, {
      snapshot_id: 'rs_demo',
      summary: { has_changes: false },
      review_history_change: { changed: false, from_entry_count: 2, to_entry_count: 2 },
    })

    expect(summary.overall.has_changes).toBe(false)
    expect(summary.attention_items).toEqual([])
    expect(summary.snapshot_id).toBe('rs_demo')
  })

  it('marks governance gate movement as a needs-review attention item', () => {
    const summary = buildSnapshotReviewSummary(snapshot, {
      snapshot_id: 'rs_demo',
      summary: { has_changes: true },
      governance_change: {
        from_gate_decision: 'not_decided',
        to_gate_decision: 'ready_with_risks',
        gate_decision_changed: true,
        changed: true,
      },
    })

    expect(summary.movements.governance_gate).toEqual([
      expect.objectContaining({
        field: 'gate_decision',
        baseline_value: 'not_decided',
        current_value: 'ready_with_risks',
        status: 'attention',
      }),
    ])
    expect(summary.attention_items).toContainEqual(expect.objectContaining({
      title: 'Governance gate decision changed',
      status: 'needs_review',
    }))
  })

  it('marks leadership briefing readiness movement as a needs-review attention item', () => {
    const summary = buildSnapshotReviewSummary(snapshot, {
      snapshot_id: 'rs_demo',
      summary: { has_changes: true },
      leadership_briefing_change: {
        from_readiness: 'ready',
        to_readiness: 'needs_review',
        readiness_changed: true,
        changed: true,
      },
    })

    expect(summary.movements.leadership_briefing_readiness).toContainEqual(expect.objectContaining({
      field: 'readiness',
      baseline_value: 'ready',
      current_value: 'needs_review',
    }))
    expect(summary.attention_items).toContainEqual(expect.objectContaining({
      title: 'Leadership briefing readiness changed',
    }))
  })

  it('counts review-history activity without treating it as an approval decision', () => {
    const summary = buildSnapshotReviewSummary(snapshot, {
      snapshot_id: 'rs_demo',
      summary: { has_changes: true, review_history_changed: true },
      review_history_change: {
        changed: true,
        from_entry_count: 2,
        to_entry_count: 4,
        from_latest_entry_id: 'rhe_2',
        to_latest_entry_id: 'rhe_4',
      },
    })

    expect(summary.review_history_activity).toEqual(expect.objectContaining({
      changed: true,
      added_entries_count: 2,
    }))
    expect(summary.attention_items).toContainEqual(expect.objectContaining({
      title: 'Review history changed since baseline',
      status: 'attention',
    }))
  })

  it('groups added, removed, and changed asset counts by kind', () => {
    const summary = buildSnapshotReviewSummary(snapshot, {
      snapshot_id: 'rs_demo',
      summary: { has_changes: true, assets_added: 1, assets_removed: 1, assets_changed: 1 },
      asset_id_changes: {
        insight_cards: { added: ['ic_new'], removed: ['ic_old'] },
      },
      asset_state_changes: {
        strategic_options: [{ asset_id: 'so_1', changed_fields: { decision_status: { from: 'draft', to: 'selected' } } }],
      },
    })

    expect(summary.counts_by_kind).toContainEqual(expect.objectContaining({
      asset_kind: 'insight_cards',
      added: 1,
      removed: 1,
      status: 'changed',
    }))
    expect(summary.counts_by_kind).toContainEqual(expect.objectContaining({
      asset_kind: 'strategic_options',
      changed: 1,
    }))
  })

  it('handles unknown asset kinds and malformed partial diffs', () => {
    const summary = buildSnapshotReviewSummary(snapshot, {
      asset_id_changes: {
        custom_assets: { added: ['custom_1'] },
      },
    })

    expect(summary.overall.has_changes).toBe(true)
    expect(summary.counts_by_kind).toContainEqual(expect.objectContaining({
      asset_kind: 'custom_assets',
      added: 1,
      status: 'changed',
    }))
  })
})
