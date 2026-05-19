import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SnapshotEvidenceReviewPanel from '../SnapshotEvidenceReviewPanel.vue'

const snapshot = {
  snapshot_id: 'rs_demo',
  title: 'P11 Gate Baseline',
  created_at: '2026-04-28T00:00:00.000000',
}

const diff = {
  snapshot_id: 'rs_demo',
  compared_at: '2026-04-29T00:00:00.000000',
  summary: {
    has_changes: true,
    assets_added: 1,
    assets_removed: 0,
    assets_changed: 1,
    review_history_changed: true,
    governance_gate_decision_changed: true,
    leadership_briefing_readiness_changed: true,
  },
  asset_id_changes: {
    insight_cards: { added: ['ic_new'], removed: [] },
  },
  asset_state_changes: {
    governance_reviews: [{ asset_id: 'gr_demo', changed_fields: { gate_decision: { from: 'not_decided', to: 'ready_with_risks' } } }],
  },
  governance_change: {
    from_gate_decision: 'not_decided',
    to_gate_decision: 'ready_with_risks',
    gate_decision_changed: true,
    changed: true,
  },
  leadership_briefing_change: {
    from_readiness: 'ready',
    to_readiness: 'needs_review',
    readiness_changed: true,
    changed: true,
  },
  review_history_change: {
    from_entry_count: 2,
    to_entry_count: 4,
    changed: true,
  },
}

describe('SnapshotEvidenceReviewPanel', () => {
  it('renders read-only review copy and deterministic movement sections', async () => {
    const wrapper = mount(SnapshotEvidenceReviewPanel, { props: { snapshot, diff } })

    expect(wrapper.text()).toContain('基线快照审阅')
    expect(wrapper.text()).toContain('不会修改快照、项目资产或评审历史')
    expect(wrapper.text()).toContain('治理门禁变化')
    expect(wrapper.text()).toContain('not_decided -> ready_with_risks')
    expect(wrapper.text()).toContain('领导汇报就绪度变化')
    expect(wrapper.text()).toContain('ready -> needs_review')
    expect(wrapper.text()).toContain('基线后的评审历史活动')
    expect(wrapper.text()).toContain('needs_review')
    expect(wrapper.text()).toContain('审阅备注处理状态')
    expect(wrapper.text()).toContain('该快照暂无需要关注的人工备注。')

    const buttonTexts = wrapper.findAll('button').map((button) => button.text())
    expect(buttonTexts).toContain('添加人工备注')
    expect(buttonTexts).toContain('展开原始差异')
    expect(buttonTexts.join(' ')).not.toMatch(/Approve|Reject|Rollback|Fix|Generate|Export|批准|否决|回滚|修复|生成|导出/)

    await wrapper.findAll('button').find((button) => button.text() === '展开原始差异').trigger('click')
    expect(wrapper.text()).toContain('"snapshot_id": "rs_demo"')
  })

  it('renders existing manual notes and emits create-note for manual annotations', async () => {
    const wrapper = mount(SnapshotEvidenceReviewPanel, {
      props: {
        snapshot,
        diff,
        notes: [{
          note_id: 'srn_demo',
          target_ref: { section_key: 'governance_gate' },
          note_type: 'observation',
          severity: 'watch',
          status: 'open',
          owner: 'Strategy reviewer',
          resolution_note: 'Track before next gate.',
          note: 'Manual reviewer note.',
          actor: { display_name: 'Reviewer' },
          created_at: '2026-04-28T00:00:00.000000',
        }],
      },
    })

    expect(wrapper.text()).toContain('人工审阅备注')
    expect(wrapper.text()).toContain('备注不会修改快照、关卡决策或项目资产')
    expect(wrapper.text()).toContain('Manual reviewer note.')
    expect(wrapper.text()).toContain('Open')
    expect(wrapper.text()).toContain('Owner: Strategy reviewer')
    expect(wrapper.text()).toContain('Track before next gate.')
    expect(wrapper.text()).toContain('仍需关注')
    expect(wrapper.text()).toContain('governance_gate')

    await wrapper.find('textarea').setValue('Please verify this movement.')
    await wrapper.find('.note-form').trigger('submit')

    expect(wrapper.emitted('create-note')?.[0]?.[0]).toEqual(expect.objectContaining({
      target_ref: { section_key: 'governance_gate' },
      note_type: 'observation',
      severity: 'watch',
      note: 'Please verify this movement.',
    }))

    const selects = wrapper.findAll('.disposition-form select')
    await selects[0].setValue('resolved')
    await wrapper.find('.disposition-form input').setValue('Reviewer B')
    await wrapper.find('.disposition-form textarea').setValue('Manual resolution.')
    await wrapper.find('.disposition-form').trigger('submit')

    expect(wrapper.emitted('update-note')?.[0]?.[0]).toEqual(expect.objectContaining({
      note_id: 'srn_demo',
      status: 'resolved',
      owner: 'Reviewer B',
      resolution_note: 'Manual resolution.',
    }))
  })

  it('renders a stable unchanged state without attention items', () => {
    const wrapper = mount(SnapshotEvidenceReviewPanel, {
      props: {
        snapshot,
        diff: {
          snapshot_id: 'rs_demo',
          summary: { has_changes: false },
          review_history_change: { changed: false, from_entry_count: 2, to_entry_count: 2 },
        },
      },
    })

    expect(wrapper.text()).toContain('无变化')
    expect(wrapper.text()).toContain('状态无变化')
    expect(wrapper.text()).not.toContain('待关注项')
  })

  it('rolls up mixed manual note disposition without exposing gate actions', () => {
    const wrapper = mount(SnapshotEvidenceReviewPanel, {
      props: {
        snapshot,
        diff,
        notes: [
          { note_id: 'srn_open', status: 'open', note: 'Open note', target_ref: { section_key: 'raw_diff' } },
          { note_id: 'srn_ack', status: 'acknowledged', note: 'Acknowledged note', target_ref: { section_key: 'governance_gate' } },
          { note_id: 'srn_resolved', status: 'resolved', note: 'Resolved note', target_ref: { section_key: 'other' } },
          { note_id: 'srn_deferred', status: 'deferred', note: 'Deferred note', target_ref: { section_key: 'review_history_activity' } },
        ],
      },
    })

    expect(wrapper.text()).toContain('审阅备注处理状态')
    expect(wrapper.text()).toContain('仍需关注')
    expect(wrapper.text()).toContain('Open note')
    expect(wrapper.text()).toContain('Acknowledged note')
    expect(wrapper.text()).toContain('Deferred note')
    expect(wrapper.find('.note-rollup').text()).not.toContain('Resolved note')
    expect(wrapper.find('.note-rollup').text()).toContain('该汇总来自人工快照审阅备注')
    expect(wrapper.find('.note-rollup').findAll('button')).toHaveLength(0)
  })
})
