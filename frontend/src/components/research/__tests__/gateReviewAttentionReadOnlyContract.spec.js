import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import GateReviewSnapshotAttentionContext from '../GateReviewSnapshotAttentionContext.vue'
import { buildGateReviewSnapshotAttentionContext } from '../gateReviewSnapshotAttentionContext'

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

function contextFixture() {
  const governanceReview = { review_id: 'gr_contract', title: 'Contract governance review', readiness: 'partial' }
  const snapshots = [
    {
      snapshot_id: 'rs_linked_active',
      title: 'Linked active baseline',
      linked_governance_review: { governance_review_id: 'gr_contract' },
      created_at: '2026-04-30T00:00:00.000000',
    },
    {
      snapshot_id: 'rs_linked_resolved',
      title: 'Linked resolved baseline',
      linked_governance_review: { governance_review_id: 'gr_contract' },
      created_at: '2026-04-29T00:00:00.000000',
    },
    {
      snapshot_id: 'rs_project_active',
      title: 'Project context baseline',
      linked_governance_review: { governance_review_id: 'gr_other' },
      created_at: '2026-04-28T00:00:00.000000',
    },
    {
      snapshot_id: 'rs_project_resolved',
      title: 'Project resolved baseline',
      linked_governance_review: {},
      created_at: '2026-04-27T00:00:00.000000',
    },
  ]
  const notesBySnapshotId = {
    rs_linked_active: [
      {
        note_id: 'srn_open',
        status: 'open',
        severity: 'watch',
        note: 'Open source trace note',
        target_ref: { section_key: 'evidence_coverage', asset_kind: 'evidence', asset_id: 'ev_123', field: 'source_text' },
        updated_at: '2026-04-30T00:04:00.000000',
      },
      {
        note_id: 'srn_ack',
        status: 'acknowledged',
        note: 'Acknowledged source trace note',
        target_ref: { section_key: 'raw_diff', asset_kind: 'snapshot', asset_id: 'rs_source' },
        updated_at: '2026-04-30T00:03:00.000000',
      },
      {
        note_id: 'srn_deferred',
        status: 'deferred',
        severity: 'info',
        note: 'Deferred source trace note',
        target_ref: { section_key: 'review_history_activity' },
        updated_at: '2026-04-30T00:05:00.000000',
      },
      {
        note_id: 'srn_resolved',
        status: 'resolved',
        note: 'Resolved source trace note',
        target_ref: { section_key: 'other' },
        updated_at: '2026-04-30T00:06:00.000000',
      },
    ],
    rs_linked_resolved: [
      { note_id: 'srn_linked_done', status: 'resolved', note: 'Linked done note', target_ref: { section_key: 'other' } },
    ],
    rs_project_active: [
      { status: 'open', note: 'Missing id and target note' },
      { note_id: 'srn_section_only', status: 'acknowledged', note: 'Section only note', target_ref: { section_key: 'leadership_readiness' } },
    ],
    rs_project_resolved: [
      { note_id: 'srn_project_done', status: 'resolved', note: 'Project done note', target_ref: { section_key: 'other' } },
    ],
  }
  return { governanceReview, snapshots, notesBySnapshotId }
}

describe('gate review attention read-only contract', () => {
  it('preserves snapshot inclusion, disposition, trace, and top-note-limit semantics', () => {
    const fixture = contextFixture()
    const before = deepClone(fixture)
    const context = buildGateReviewSnapshotAttentionContext({
      ...fixture,
      topNoteLimit: 2,
    })

    expect(context.snapshots.map((snapshot) => snapshot.snapshot_id)).toEqual([
      'rs_linked_active',
      'rs_linked_resolved',
      'rs_project_active',
    ])
    expect(context.snapshots.find((snapshot) => snapshot.snapshot_id === 'rs_project_resolved')).toBeUndefined()
    expect(context.linked_snapshot_count).toBe(2)
    expect(context.related_snapshot_count).toBe(3)
    expect(context.totals).toEqual({
      total_notes: 7,
      open: 2,
      acknowledged: 2,
      resolved: 2,
      deferred: 1,
      active_attention: 5,
    })

    const linkedActive = context.snapshots[0]
    expect(linkedActive.note_rollup.active_attention).toBe(3)
    expect(linkedActive.note_rollup.resolved).toBe(1)
    expect(linkedActive.top_attention_notes.map((note) => note.note_id)).toEqual(['srn_open', 'srn_ack'])
    expect(linkedActive.top_attention_notes.map((note) => note.note_id)).not.toContain('srn_resolved')
    expect(linkedActive.top_attention_notes[0].trace_ref).toEqual(expect.objectContaining({
      source_kind: 'snapshot_review_note',
      source_label: 'Snapshot review note',
      snapshot_id: 'rs_linked_active',
      snapshot_title: 'Linked active baseline',
      relation_label: 'Linked snapshot',
      note_id: 'srn_open',
      disposition: 'open',
      severity: 'watch',
      readonly: true,
      affects_gate_readiness: false,
    }))
    expect(linkedActive.top_attention_notes[0].trace_ref.target).toEqual({
      section_key: 'evidence_coverage',
      asset_kind: 'evidence',
      asset_id: 'ev_123',
      field: 'source_text',
    })
    expect(linkedActive.top_attention_notes[0].trace_ref.display.target).toBe(
      'Section: evidence_coverage · Asset: evidence / ev_123 · Field: source_text',
    )

    const linkedResolved = context.snapshots[1]
    expect(linkedResolved.snapshot_id).toBe('rs_linked_resolved')
    expect(linkedResolved.note_rollup.active_attention).toBe(0)
    expect(linkedResolved.top_attention_notes).toEqual([])

    expect(fixture).toEqual(before)
  })

  it('handles missing note id, severity, and target metadata without fabricating workflow state', () => {
    const fixture = contextFixture()
    const context = buildGateReviewSnapshotAttentionContext({
      ...fixture,
      topNoteLimit: 5,
    })
    const projectContext = context.snapshots.find((snapshot) => snapshot.snapshot_id === 'rs_project_active')

    expect(projectContext.relation).toBe('project_snapshot_context')
    expect(projectContext.top_attention_notes).toHaveLength(2)
    const missing = projectContext.top_attention_notes.find((note) => note.note_id === '')
    expect(missing.trace_ref).toEqual(expect.objectContaining({
      note_id: '',
      severity: '',
      readonly: true,
      affects_gate_readiness: false,
    }))
    expect(missing.trace_ref.display.source).toBe('Project context baseline · Project context · unknown note')
    expect(missing.trace_ref.target).toEqual({
      section_key: 'Unspecified section',
      asset_kind: '',
      asset_id: '',
      field: '',
    })
    expect(missing.trace_ref.display.target).toBe('Section: Unspecified section')

    const sectionOnly = projectContext.top_attention_notes.find((note) => note.note_id === 'srn_section_only')
    expect(sectionOnly.trace_ref.display.target).toBe('Section: leadership_readiness')
  })

  it('keeps helper output free of workflow, runtime, and mutation capability fields', () => {
    const context = buildGateReviewSnapshotAttentionContext({
      ...contextFixture(),
      topNoteLimit: 5,
    })
    const keys = collectKeys(context)
    const forbiddenKeys = [
      'assignee',
      'assigned_to',
      'due_at',
      'reminder',
      'schedule',
      'worker',
      'queue',
      'workflow',
      'dag',
      'task_id',
      'job_id',
      'model',
      'llm',
      'deep_research',
      'readiness_verdict',
      'auto_decision',
      'repair',
      'rollback',
      'export',
      'generate',
      'href',
      'route',
      'selected_note_id',
      'can_update',
      'action',
    ]

    for (const key of forbiddenKeys) {
      expect(keys.has(key)).toBe(false)
    }
  })

  it('renders the attention context as passive text only', () => {
    const context = buildGateReviewSnapshotAttentionContext({
      ...contextFixture(),
      topNoteLimit: 3,
    })
    const wrapper = mount(GateReviewSnapshotAttentionContext, {
      props: { context },
    })

    expect(wrapper.text()).toContain('Snapshot note attention context')
    expect(wrapper.text()).toContain('Read-only context derived from manual snapshot review notes')
    expect(wrapper.text()).toContain('Source')
    expect(wrapper.text()).toContain('Target')
    expect(wrapper.text()).toContain('Trace')
    expect(wrapper.text()).toContain('Trace only · active human attention · no gate readiness change')
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.findAll('[href]')).toHaveLength(0)
    expect(wrapper.findAll('[role="button"]')).toHaveLength(0)
    expect(wrapper.emitted()).toEqual({})
    expect(wrapper.text()).not.toMatch(/Assign|Resolve all|Approve gate|Mark ready|Remind|Schedule|Run workflow|Repair|Export|Generate|Jump to edit/i)
  })

  it('does not import runtime, router, dataClient, or workflow surfaces in the P15-P17 read-only production files', () => {
    const root = resolve(process.cwd(), 'src')
    const files = [
      'components/research/snapshotReviewNoteRollup.js',
      'components/research/gateReviewSnapshotAttentionContext.js',
      'components/research/GateReviewSnapshotAttentionContext.vue',
    ]
    const forbiddenPatterns = [
      /dataClient/,
      /useRouter|RouterLink|href=/,
      /scheduler|worker|queue|workflow|deepResearch|deep_research|Bailian|OpenAI|modelClient/,
      /createReviewHistory|updateGovernanceReview|updateSnapshotReviewNote|createSnapshotReviewNote/,
    ]

    for (const file of files) {
      const source = readFileSync(resolve(root, file), 'utf8')
      for (const pattern of forbiddenPatterns) {
        expect(source).not.toMatch(pattern)
      }
    }
  })
})
