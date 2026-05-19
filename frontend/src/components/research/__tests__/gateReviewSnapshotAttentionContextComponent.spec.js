import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import GateReviewSnapshotAttentionContext from '../GateReviewSnapshotAttentionContext.vue'

describe('GateReviewSnapshotAttentionContext', () => {
  it('renders read-only linked snapshot attention without action controls', () => {
    const wrapper = mount(GateReviewSnapshotAttentionContext, {
      props: {
        context: {
          linked_snapshot_count: 1,
          totals: {
            total_notes: 4,
            open: 1,
            acknowledged: 1,
            resolved: 1,
            deferred: 1,
            active_attention: 3,
          },
          snapshots: [{
            snapshot_id: 'rs_demo',
            snapshot_title: 'P11 Gate Baseline',
            relation: 'linked_governance_review',
            latest_note_timestamp: '2026-04-28T00:03:00.000000',
            note_rollup: {
              total: 4,
              open: 1,
              acknowledged: 1,
              resolved: 1,
              deferred: 1,
              active_attention: 3,
            },
            top_attention_notes: [
              {
                note_id: 'srn_open',
                disposition: 'open',
                title: 'governance_gate',
                body_preview: 'Open note',
                trace_ref: {
                  display: {
                    source: 'P11 Gate Baseline · Linked snapshot · srn_open',
                    target: 'Section: governance_gate · Asset: governance_review / gr_demo · Field: gate_decision',
                    reason: 'Trace only · active human attention · no gate readiness change',
                  },
                },
              },
              {
                note_id: 'srn_deferred',
                disposition: 'deferred',
                title: 'review_history_activity',
                body_preview: 'Deferred note',
                trace_ref: {
                  display: {
                    source: 'P11 Gate Baseline · Linked snapshot · srn_deferred',
                    target: 'Section: review_history_activity',
                    reason: 'Trace only · active human attention · no gate readiness change',
                  },
                },
              },
            ],
          }],
        },
      },
    })

    expect(wrapper.text()).toContain('Snapshot note attention context')
    expect(wrapper.text()).toContain('Read-only context derived from manual snapshot review notes')
    expect(wrapper.text()).toContain('does not change gate readiness')
    expect(wrapper.text()).toContain('P11 Gate Baseline')
    expect(wrapper.text()).toContain('Linked snapshot')
    expect(wrapper.text()).toContain('Open note')
    expect(wrapper.text()).toContain('Deferred note')
    expect(wrapper.text()).toContain('Source')
    expect(wrapper.text()).toContain('P11 Gate Baseline · Linked snapshot · srn_open')
    expect(wrapper.text()).toContain('Target')
    expect(wrapper.text()).toContain('Section: governance_gate · Asset: governance_review / gr_demo · Field: gate_decision')
    expect(wrapper.text()).toContain('Trace')
    expect(wrapper.text()).toContain('Trace only · active human attention · no gate readiness change')
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.text()).not.toMatch(/resolve all|approve gate|mark ready|assign|remind|schedule|run workflow|generate repair/i)
  })

  it('renders empty state without implying readiness', () => {
    const wrapper = mount(GateReviewSnapshotAttentionContext, {
      props: {
        context: {
          linked_snapshot_count: 0,
          totals: {},
          snapshots: [],
        },
      },
    })

    expect(wrapper.text()).toContain('No active snapshot-note attention found')
    expect(wrapper.text()).toContain('This does not imply gate readiness')
  })
})
