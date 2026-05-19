export const goldenGovernanceReview = {
  review_id: 'gr_attention_golden',
  project_id: 'rp_attention_golden',
  title: 'Golden attention evidence consistency review',
}

export const goldenSnapshots = [
  {
    snapshot_id: 'rs_golden_linked_active',
    project_id: 'rp_attention_golden',
    title: 'Linked active evidence snapshot',
    linked_governance_review: { governance_review_id: 'gr_attention_golden' },
    created_at: '2026-04-30T09:00:00.000000',
  },
  {
    snapshot_id: 'rs_golden_linked_resolved',
    project_id: 'rp_attention_golden',
    title: 'Linked resolved-only snapshot',
    linked_governance_review: { governance_review_id: 'gr_attention_golden' },
    created_at: '2026-04-30T09:10:00.000000',
  },
  {
    snapshot_id: 'rs_golden_project_active',
    project_id: 'rp_attention_golden',
    title: 'Project active context snapshot',
    linked_governance_review: { governance_review_id: 'gr_other' },
    created_at: '2026-04-30T09:20:00.000000',
  },
  {
    snapshot_id: 'rs_golden_project_resolved',
    project_id: 'rp_attention_golden',
    title: 'Project resolved-only context snapshot',
    linked_governance_review: {},
    created_at: '2026-04-30T09:30:00.000000',
  },
]

export const goldenNotesBySnapshotId = {
  rs_golden_linked_active: [
    {
      note_id: 'note-open-linked-section',
      status: 'open',
      severity: 'watch',
      note: 'Open linked note that targets evidence consistency at section level.',
      target_ref: { section_key: 'evidence_consistency' },
      created_at: '2026-04-30T09:01:00.000000',
      updated_at: '2026-04-30T09:04:00.000000',
    },
    {
      note_id: 'note-deferred-linked-field',
      status: 'deferred',
      severity: 'info',
      note: 'Deferred linked note that preserves field-level target evidence.',
      target_ref: {
        section_key: 'evidence_consistency',
        asset_kind: 'snapshot',
        asset_id: 'rs_source_field',
        field: 'severity',
      },
      created_at: '2026-04-30T09:02:00.000000',
      updated_at: '2026-04-30T09:03:00.000000',
    },
    {
      note_id: 'note-resolved-linked-newer',
      status: 'resolved',
      severity: 'info',
      note: 'Resolved linked note has the newest timestamp but must not appear as active attention.',
      target_ref: { section_key: 'evidence_consistency' },
      created_at: '2026-04-30T09:03:00.000000',
      updated_at: '2026-04-30T10:00:00.000000',
      resolved_at: '2026-04-30T10:01:00.000000',
    },
  ],
  rs_golden_linked_resolved: [
    {
      note_id: 'note-resolved-linked-only',
      status: 'resolved',
      severity: 'info',
      note: 'Resolved-only linked snapshot remains included for counts.',
      target_ref: { section_key: 'linked_resolved' },
      created_at: '2026-04-30T09:11:00.000000',
      updated_at: '2026-04-30T09:12:00.000000',
    },
  ],
  rs_golden_project_active: [
    {
      note_id: 'note-ack-project-asset',
      status: 'acknowledged',
      severity: 'watch',
      note: 'Acknowledged project context note with asset-level target.',
      target_ref: {
        section_key: 'evidence_consistency',
        asset_kind: 'evidence',
        asset_id: 'ev_project_asset',
      },
      created_at: '2026-04-30T09:21:00.000000',
      updated_at: '2026-04-30T09:25:00.000000',
    },
    {
      note_id: 'note-unknown-project-missing-target',
      status: 'needs_review',
      note: 'Unknown status should be normalized into open active attention without inventing target metadata.',
      created_at: '2026-04-30T09:22:00.000000',
      updated_at: '2026-04-30T09:26:00.000000',
    },
    {
      status: 'open',
      note: 'Open project context note without an id or target metadata.',
      created_at: '2026-04-30T09:23:00.000000',
      updated_at: '2026-04-30T09:24:00.000000',
    },
  ],
  rs_golden_project_resolved: [
    {
      note_id: 'note-resolved-project-only',
      status: 'resolved',
      severity: 'info',
      note: 'Resolved-only project context snapshot is excluded from GovernanceReview attention context.',
      target_ref: { section_key: 'project_resolved' },
      created_at: '2026-04-30T09:31:00.000000',
      updated_at: '2026-04-30T09:32:00.000000',
    },
  ],
}

export const goldenOptions = {
  topNoteLimit: 4,
}

export const expectedGoldenSummary = {
  governance_review_id: 'gr_attention_golden',
  linked_snapshot_count: 2,
  related_snapshot_count: 3,
  included_snapshot_ids: [
    'rs_golden_linked_active',
    'rs_golden_linked_resolved',
    'rs_golden_project_active',
  ],
  excluded_snapshot_ids: [
    'rs_golden_project_resolved',
  ],
  totals: {
    total_notes: 7,
    open: 3,
    acknowledged: 1,
    resolved: 2,
    deferred: 1,
    active_attention: 5,
  },
}

export const expectedGoldenSnapshotSummaries = {
  rs_golden_linked_active: {
    relation: 'linked_governance_review',
    total: 3,
    open: 1,
    acknowledged: 0,
    deferred: 1,
    resolved: 1,
    active_attention: 2,
    active_note_ids: ['note-open-linked-section', 'note-deferred-linked-field'],
  },
  rs_golden_linked_resolved: {
    relation: 'linked_governance_review',
    total: 1,
    open: 0,
    acknowledged: 0,
    deferred: 0,
    resolved: 1,
    active_attention: 0,
    active_note_ids: [],
  },
  rs_golden_project_active: {
    relation: 'project_snapshot_context',
    total: 3,
    open: 2,
    acknowledged: 1,
    deferred: 0,
    resolved: 0,
    active_attention: 3,
    active_note_ids: [
      'note-unknown-project-missing-target',
      '',
      'note-ack-project-asset',
    ],
  },
}

export const expectedGoldenTargets = {
  'note-open-linked-section': 'Section: evidence_consistency',
  'note-deferred-linked-field': 'Section: evidence_consistency · Asset: snapshot / rs_source_field · Field: severity',
  'note-ack-project-asset': 'Section: evidence_consistency · Asset: evidence / ev_project_asset',
  'note-unknown-project-missing-target': 'Section: Unspecified section',
  '': 'Section: Unspecified section',
}

export const expectedGoldenTraceSlices = {
  'note-open-linked-section': {
    source_kind: 'snapshot_review_note',
    source_label: 'Snapshot review note',
    snapshot_id: 'rs_golden_linked_active',
    snapshot_title: 'Linked active evidence snapshot',
    note_id: 'note-open-linked-section',
    disposition: 'open',
    severity: 'watch',
    readonly: true,
    affects_gate_readiness: false,
  },
  'note-deferred-linked-field': {
    source_kind: 'snapshot_review_note',
    source_label: 'Snapshot review note',
    snapshot_id: 'rs_golden_linked_active',
    snapshot_title: 'Linked active evidence snapshot',
    note_id: 'note-deferred-linked-field',
    disposition: 'deferred',
    severity: 'info',
    readonly: true,
    affects_gate_readiness: false,
  },
  'note-ack-project-asset': {
    source_kind: 'snapshot_review_note',
    source_label: 'Snapshot review note',
    snapshot_id: 'rs_golden_project_active',
    snapshot_title: 'Project active context snapshot',
    note_id: 'note-ack-project-asset',
    disposition: 'acknowledged',
    severity: 'watch',
    readonly: true,
    affects_gate_readiness: false,
  },
  'note-unknown-project-missing-target': {
    source_kind: 'snapshot_review_note',
    source_label: 'Snapshot review note',
    snapshot_id: 'rs_golden_project_active',
    snapshot_title: 'Project active context snapshot',
    note_id: 'note-unknown-project-missing-target',
    disposition: 'open',
    severity: '',
    readonly: true,
    affects_gate_readiness: false,
  },
  '': {
    source_kind: 'snapshot_review_note',
    source_label: 'Snapshot review note',
    snapshot_id: 'rs_golden_project_active',
    snapshot_title: 'Project active context snapshot',
    note_id: '',
    disposition: 'open',
    severity: '',
    readonly: true,
    affects_gate_readiness: false,
  },
}
