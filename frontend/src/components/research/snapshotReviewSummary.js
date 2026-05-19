const CRITICAL_FIELDS = new Set([
  'gate_decision',
  'readiness',
  'approval_state',
  'review_state',
  'decision_status',
  'source_ref_count',
])

function asNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function uniqueKinds(diff = {}) {
  return Array.from(new Set([
    ...Object.keys(diff.asset_id_changes || {}),
    ...Object.keys(diff.asset_state_changes || {}),
    ...Object.keys(diff.asset_count_changes || {}),
    diff.review_history_change?.changed ? 'review_history' : '',
    diff.governance_change?.changed ? 'governance_reviews' : '',
    diff.leadership_briefing_change?.changed ? 'leadership_briefings' : '',
  ].filter(Boolean))).sort()
}

function fieldLabel(field) {
  return String(field || '').replaceAll('_', ' ')
}

function formatValue(value) {
  if (value === undefined || value === null || value === '') return 'none'
  if (Array.isArray(value)) return `${value.length} items`
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function kindCounts(kind, diff = {}) {
  const idChange = diff.asset_id_changes?.[kind] || {}
  const stateRows = diff.asset_state_changes?.[kind] || []
  const countChange = diff.asset_count_changes?.[kind] || {}
  const added = asNumber(idChange.added?.length)
  const removed = asNumber(idChange.removed?.length)
  const changed = asNumber(idChange.changed?.length) + asNumber(stateRows.length)
  const delta = asNumber(countChange.delta)
  return {
    asset_kind: kind,
    added,
    removed,
    changed,
    delta,
    status: kind === 'governance_reviews' || kind === 'leadership_briefings' || kind === 'review_history'
      ? 'attention'
      : (added || removed || changed || delta ? 'changed' : 'unchanged'),
  }
}

function makeAttentionItem({ key, assetKind, assetId, title, reason, baselineValue, currentValue, field, status = 'needs_review' }) {
  return {
    key,
    asset_kind: assetKind,
    asset_id: assetId || '',
    title,
    reason,
    field,
    baseline_value: formatValue(baselineValue),
    current_value: formatValue(currentValue),
    status,
    source: 'snapshot_diff',
  }
}

function governanceMovements(diff = {}) {
  const change = diff.governance_change || {}
  const rows = []
  if (change.gate_decision_changed || change.from_gate_decision !== change.to_gate_decision) {
    rows.push({
      asset_kind: 'governance_review',
      asset_id: change.governance_review_id || '',
      field: 'gate_decision',
      baseline_value: formatValue(change.from_gate_decision),
      current_value: formatValue(change.to_gate_decision),
      status: 'attention',
    })
  }
  if (change.readiness_changed || change.from_readiness !== change.to_readiness) {
    rows.push({
      asset_kind: 'governance_review',
      asset_id: change.governance_review_id || '',
      field: 'readiness',
      baseline_value: formatValue(change.from_readiness),
      current_value: formatValue(change.to_readiness),
      status: 'attention',
    })
  }
  return rows
}

function briefingMovements(diff = {}) {
  const change = diff.leadership_briefing_change || {}
  const rows = []
  if (change.readiness_changed || change.from_readiness !== change.to_readiness) {
    rows.push({
      asset_kind: 'leadership_briefing',
      asset_id: change.briefing_id || '',
      field: 'readiness',
      baseline_value: formatValue(change.from_readiness),
      current_value: formatValue(change.to_readiness),
      status: 'attention',
    })
  }
  if (change.status_changed || change.from_status !== change.to_status) {
    rows.push({
      asset_kind: 'leadership_briefing',
      asset_id: change.briefing_id || '',
      field: 'status',
      baseline_value: formatValue(change.from_status),
      current_value: formatValue(change.to_status),
      status: 'attention',
    })
  }
  return rows
}

function stateAttentionItems(diff = {}) {
  const items = []
  for (const [kind, rows] of Object.entries(diff.asset_state_changes || {})) {
    for (const row of rows || []) {
      const changedFields = row.changed_fields || {}
      for (const [field, values] of Object.entries(changedFields)) {
        if (!CRITICAL_FIELDS.has(field)) continue
        items.push(makeAttentionItem({
          key: `${kind}:${row.asset_id}:${field}`,
          assetKind: kind,
          assetId: row.asset_id,
          field,
          title: `${fieldLabel(field)} changed`,
          reason: `${fieldLabel(field)} changed since baseline.`,
          baselineValue: values?.from,
          currentValue: values?.to,
        }))
      }
    }
  }
  return items
}

export function buildSnapshotReviewSummary(snapshot = {}, diff = {}) {
  const summary = diff.summary || {}
  const countsByKind = uniqueKinds(diff).map((kind) => kindCounts(kind, diff))
  const governance = governanceMovements(diff)
  const briefing = briefingMovements(diff)
  const reviewHistoryChange = diff.review_history_change || {}
  const attentionItems = [
    ...governance.map((row) => makeAttentionItem({
      key: `governance:${row.field}`,
      assetKind: 'governance_review',
      assetId: row.asset_id,
      field: row.field,
      title: row.field === 'gate_decision' ? 'Governance gate decision changed' : 'Governance readiness changed',
      reason: 'Governance review field changed since baseline.',
      baselineValue: row.baseline_value,
      currentValue: row.current_value,
    })),
    ...briefing.map((row) => makeAttentionItem({
      key: `leadership_briefing:${row.field}`,
      assetKind: 'leadership_briefing',
      assetId: row.asset_id,
      field: row.field,
      title: row.field === 'readiness' ? 'Leadership briefing readiness changed' : 'Leadership briefing status changed',
      reason: 'Leadership briefing field changed since baseline.',
      baselineValue: row.baseline_value,
      currentValue: row.current_value,
    })),
    ...stateAttentionItems(diff),
  ]

  if (reviewHistoryChange.changed) {
    attentionItems.push(makeAttentionItem({
      key: 'review_history:activity',
      assetKind: 'review_history',
      field: 'entry_count',
      title: 'Review history changed since baseline',
      reason: 'Review history has activity after the baseline snapshot.',
      baselineValue: reviewHistoryChange.from_entry_count,
      currentValue: reviewHistoryChange.to_entry_count,
      status: 'attention',
    }))
  }

  const totalAdded = asNumber(summary.assets_added)
  const totalRemoved = asNumber(summary.assets_removed)
  const totalChanged = asNumber(summary.assets_changed)
  const hasKindChanges = countsByKind.some((row) => row.added || row.removed || row.changed || row.delta)
  const hasChanges = Boolean(summary.has_changes || totalAdded || totalRemoved || totalChanged || hasKindChanges || attentionItems.length)

  return {
    snapshot_id: snapshot.snapshot_id || diff.snapshot_id || '',
    baseline_label: snapshot.title || snapshot.snapshot_id || diff.snapshot_id || 'Snapshot baseline',
    baseline_created_at: snapshot.created_at || diff.snapshot_created_at || '',
    current_compared_at: diff.compared_at || '',
    overall: {
      has_changes: hasChanges,
      total_added: totalAdded,
      total_removed: totalRemoved,
      total_changed: totalChanged,
      attention_count: attentionItems.length,
      needs_review_count: attentionItems.filter((item) => item.status === 'needs_review').length,
    },
    counts_by_kind: countsByKind,
    movements: {
      governance_gate: governance,
      leadership_briefing_readiness: briefing,
    },
    review_history_activity: {
      changed: Boolean(reviewHistoryChange.changed),
      added_entries_count: Math.max(0, asNumber(reviewHistoryChange.to_entry_count) - asNumber(reviewHistoryChange.from_entry_count)),
      from_entry_count: asNumber(reviewHistoryChange.from_entry_count),
      to_entry_count: asNumber(reviewHistoryChange.to_entry_count),
      from_latest_entry_id: reviewHistoryChange.from_latest_entry_id || '',
      to_latest_entry_id: reviewHistoryChange.to_latest_entry_id || '',
    },
    attention_items: attentionItems,
    raw_diff_available: Boolean(diff && Object.keys(diff).length),
  }
}
