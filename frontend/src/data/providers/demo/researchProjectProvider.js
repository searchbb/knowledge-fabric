import { demoResearchProjects } from './fixtures/researchProjects'

function clone(value) {
  if (value === undefined) return undefined
  return JSON.parse(JSON.stringify(value))
}

const demoState = clone(demoResearchProjects)

function readonlyError() {
  const err = new Error('Demo 模式为只读，不能创建或修改战略研究项目')
  err.isDemoReadonlyBlock = true
  throw err
}

function findProject(projectId) {
  const project = demoState.find((item) => item.id === projectId)
  if (!project) {
    throw new Error(`Demo data not available for research project: ${projectId}`)
  }
  return project
}

function emptyPack() {
  return {
    status: 'not_generated',
    candidates: [],
    accepted_evidence_ids: [],
    rejected_evidence_ids: [],
    summary: {
      candidate_count: 0,
      accepted_count: 0,
      degraded_count: 0,
      source_project_count: 0,
      concept_count: 0,
      theme_count: 0,
    },
  }
}

function rebuildSummary(pack) {
  const candidates = pack?.candidates || []
  const sourceProjects = new Set()
  for (const candidate of candidates) {
    for (const ref of candidate.source_refs || []) {
      if (ref.project_id) sourceProjects.add(ref.project_id)
    }
  }
  return {
    candidate_count: candidates.length,
    accepted_count: candidates.filter((item) => item.status === 'accepted').length,
    degraded_count: candidates.filter((item) => (item.source_refs || []).some((ref) => ref.degraded)).length,
    source_project_count: sourceProjects.size,
    concept_count: candidates.filter((item) => item.evidence_type === 'concept').length,
    theme_count: candidates.filter((item) => item.evidence_type === 'theme').length,
  }
}

function syncEvidenceItems(project, candidate, status) {
  project.evidence_items = (project.evidence_items || []).filter(
    (item) => item.evidence_id !== candidate.evidence_id,
  )
  if (status === 'accepted') {
    project.evidence_items.push({
      evidence_id: candidate.evidence_id,
      title: candidate.title,
      summary: candidate.summary,
      evidence_type: candidate.evidence_type,
      status: 'accepted',
      pack_id: project.local_evidence_pack?.pack_id || '',
      source_registry: candidate.source?.registry || '',
      degraded: (candidate.source_refs || []).some((ref) => ref.degraded),
      accepted_at: '2026-04-28T00:00:00.000000',
    })
  }
}

function syncExternalEvidenceItems(project, pack, candidate, status) {
  const evidenceId = `ei_${candidate.candidate_id || candidate.external_id}`
  project.evidence_items = (project.evidence_items || []).filter(
    (item) => item.evidence_id !== evidenceId,
  )
  if (status === 'accepted') {
    project.evidence_items.push({
      evidence_id: evidenceId,
      origin: 'external_research_pack',
      source_type: pack.source_type,
      scope: pack.scope || 'C2_external',
      pack_id: pack.pack_id,
      candidate_id: candidate.candidate_id,
      claim: candidate.claim,
      title: candidate.claim,
      summary: candidate.evidence_text,
      evidence_text: candidate.evidence_text,
      source_refs: candidate.source_refs || [],
      confidence: candidate.confidence,
      review_status: 'accepted',
      status: 'accepted',
      created_by: 'codex',
      accepted_at: '2026-04-28T00:00:00.000000',
      provenance: {
        producer_kind: pack.producer?.kind || '',
        producer_name: pack.producer?.name || '',
        model: pack.producer?.model || '',
      },
    })
  }
}

function updateIndexedAsset(project, field, id, patch) {
  const assets = project[field] || []
  const index = assets.findIndex((item) => item.id === id)
  if (index < 0) {
    throw new Error(`Demo data not available for research asset: ${id}`)
  }
  assets[index] = {
    ...assets[index],
    ...patch,
    updated_at: '2026-04-28T00:00:00.000000',
  }
  project[field] = assets
  return assets[index]
}

function updateAssetByField(project, field, idField, id, patch) {
  const assets = project[field] || []
  const index = assets.findIndex((item) => item[idField] === id)
  if (index < 0) {
    throw new Error(`Demo data not available for research asset: ${id}`)
  }
  assets[index] = {
    ...assets[index],
    ...patch,
    updated_at: '2026-04-28T00:00:00.000000',
  }
  project[field] = assets
  return assets[index]
}

function historyValue(value) {
  if (typeof value === 'string' && value.length > 160) {
    return { preview: value.slice(0, 160), truncated: true }
  }
  return clone(value)
}

function recordReviewHistory(project, { assetType, assetId, before, after, eventType = '', note = '' }) {
  const changedFields = Object.keys({ ...before, ...after })
    .filter((key) => !['created_at', 'updated_at', 'payload_hash'].includes(key))
    .filter((key) => JSON.stringify(before?.[key]) !== JSON.stringify(after?.[key]))
    .map((key) => ({
      path: key,
      old_value: historyValue(before?.[key]),
      new_value: historyValue(after?.[key]),
    }))
  if (!changedFields.length && !note) return null
  const entry = {
    history_entry_id: `rhe_demo_${String((project.review_history_entries || []).length + 1).padStart(8, '0')}`,
    schema_version: 1,
    project_id: project.id,
    asset_type: assetType,
    asset_id: assetId,
    asset_title: after?.title || before?.title || assetId,
    event_type: eventType || (changedFields.some((item) => item.path === 'gate_decision')
      ? 'gate_decision_changed'
      : changedFields.some((item) => item.path === 'readiness')
        ? 'readiness_changed'
        : changedFields.some((item) => item.path === 'status')
          ? 'status_changed'
          : 'asset_updated'),
    event_source: note ? 'manual_review_note' : 'demo_patch',
    actor: { actor_type: 'manual_user', display_name: after?.updated_by || 'Reviewer' },
    changed_fields: changedFields,
    related_asset_refs: [],
    note,
    summary: note ? `Manual note added to ${assetType}` : `${assetType} updated`,
    created_at: '2026-04-28T00:00:00.000000',
  }
  project.review_history_entries = [entry, ...(project.review_history_entries || [])]
  return entry
}

function snapshotIndex(snapshot) {
  return {
    snapshot_id: snapshot.snapshot_id,
    title: snapshot.title,
    reason: snapshot.reason,
    gate_type: snapshot.gate_type,
    actor: snapshot.actor,
    included_asset_kinds: snapshot.included_asset_kinds,
    asset_counts: Object.fromEntries(
      Object.entries(snapshot.asset_kind_summaries || {}).map(([kind, summary]) => [kind, summary.count || 0]),
    ),
    linked_governance_review: snapshot.linked_governance_review || {},
    linked_leadership_briefing: snapshot.linked_leadership_briefing || {},
    review_history_watermark: snapshot.review_history_watermark || {},
    snapshot_fingerprint: snapshot.snapshot_fingerprint,
    created_at: snapshot.created_at,
  }
}

function buildDemoSnapshot(project, payload = {}) {
  const snapshotId = `rs_demo_${String((project.research_snapshots || []).length + 1).padStart(8, '0')}`
  const included = payload.included_asset_kinds || [
    'project',
    'evidence_items',
    'evidence_matrix_rows',
    'insight_cards',
    'artifact_drafts',
    'artifact_packs',
    'strategic_options',
    'validation_plans',
    'leadership_decision_records',
    'leadership_briefings',
    'governance_reviews',
    'review_history',
  ]
  const assetKindSummaries = {}
  const assetFingerprints = {}
  for (const kind of included) {
    if (kind === 'project') continue
    const source = kind === 'review_history' ? project.review_history_entries : project[kind]
    const rows = (source || []).map((item) => {
      const id = item.evidence_id || item.id || item.pack_id || item.option_id || item.plan_id || item.decision_id || item.briefing_id || item.review_id || item.history_entry_id
      const compact = {
        asset_id: id,
        asset_type: kind.replace(/s$/, ''),
        title: item.title || item.question || item.claim || id,
        status: item.status || item.review_status || item.decision_status || '',
        readiness: item.readiness || item.review_state || item.approval_state || '',
        gate_decision: item.gate_decision || '',
        updated_at: item.updated_at || item.created_at || '',
      }
      compact.fingerprint = `demo:${JSON.stringify(compact)}`
      return compact
    })
    assetFingerprints[kind] = rows
    assetKindSummaries[kind] = {
      count: rows.length,
      status_counts: {},
      readiness_counts: {},
      gate_decision_counts: {},
      latest_updated_at: rows[0]?.updated_at || '',
      kind_fingerprint: `demo:${kind}:${rows.length}`,
    }
  }
  const history = project.review_history_entries || []
  const latestHistory = history[0] || {}
  const governance = (project.governance_reviews || []).find((item) => item.review_id === payload.governance_review_id) || (project.governance_reviews || [])[0] || {}
  const briefing = (project.leadership_briefings || [])[0] || {}
  return {
    schema_version: 1,
    snapshot_id: snapshotId,
    project_id: project.id,
    title: payload.title || 'P11 Gate Baseline',
    reason: payload.reason || '',
    gate_type: payload.gate_type || 'manual_gate',
    actor: payload.actor || { actor_type: 'manual_user', display_name: 'Reviewer' },
    created_at: '2026-04-28T00:00:00.000000',
    included_asset_kinds: included,
    project_summary: { project_id: project.id, title: project.title, status: project.status, updated_at: project.updated_at },
    asset_kind_summaries: assetKindSummaries,
    asset_fingerprints: assetFingerprints,
    review_history_watermark: {
      latest_entry_id: latestHistory.history_entry_id || '',
      latest_created_at: latestHistory.created_at || '',
      entry_count: history.length,
    },
    linked_governance_review: governance.review_id ? {
      governance_review_id: governance.review_id,
      gate_decision: governance.gate_decision || '',
      readiness: governance.readiness || '',
      ready_for_next_stage: governance.review_summary?.ready_for_next_stage === true,
    } : {},
    linked_leadership_briefing: briefing.briefing_id ? {
      briefing_id: briefing.briefing_id,
      readiness: briefing.readiness || '',
      status: briefing.status || '',
      approval_state: briefing.approval_state || '',
    } : {},
    snapshot_fingerprint: `demo:${snapshotId}`,
  }
}

function findPack(project, packId) {
  const pack = (project.artifact_packs || []).find((item) => item.pack_id === packId)
  if (!pack) {
    throw new Error(`Demo data not available for artifact pack: ${packId}`)
  }
  return pack
}

function emptyTraceabilityMap(projectId) {
  return {
    project_id: projectId,
    generated_at: '2026-04-28T00:00:00Z',
    view_type: 'strategic_research_traceability_map',
    traceability_readiness: 'ready',
    summary: {
      node_count: 0,
      edge_count: 0,
      blocking_issue_count: 0,
      warning_issue_count: 0,
      orphan_node_count: 0,
      missing_reference_count: 0,
      briefing_coverage: {
        leadership_briefing_count: 0,
        briefings_with_required_refs: 0,
        briefings_with_blocking_issues: 0,
      },
    },
    lanes: [],
    nodes: [],
    edges: [],
    issues: [],
    orphans: [],
    filters: { briefing_id: '', asset_type: '', issue_severity: '' },
  }
}

function governanceReviewIndex(review) {
  const summary = review.review_summary || {}
  return {
    review_id: review.review_id,
    title: review.title,
    review_type: review.review_type,
    status: review.status,
    gate_decision: review.gate_decision,
    readiness: review.readiness,
    checklist_count: (review.checklist_items || []).length,
    finding_count: (review.findings || []).length,
    signoff_count: (review.signoffs || []).length,
    blocker_count: summary.blocker_count || 0,
    major_open_count: summary.major_open_count || 0,
    failed_required_count: summary.failed_required_count || 0,
    ready_for_next_stage: summary.ready_for_next_stage === true,
    created_at: review.created_at,
    updated_at: review.updated_at,
  }
}

function filterTraceabilityMap(map, params = {}) {
  const filtered = clone(map)
  const briefingId = params.briefing_id || ''
  const assetType = params.asset_type || ''
  const issueSeverity = params.issue_severity || ''
  if (briefingId) {
    const connected = new Set([`leadership_briefing:${briefingId}`])
    let changed = true
    while (changed) {
      changed = false
      for (const edge of filtered.edges || []) {
        if (connected.has(edge.from_node_id) && !connected.has(edge.to_node_id)) {
          connected.add(edge.to_node_id)
          changed = true
        }
        if (connected.has(edge.to_node_id) && !connected.has(edge.from_node_id)) {
          connected.add(edge.from_node_id)
          changed = true
        }
      }
    }
    filtered.nodes = filtered.nodes.filter((node) => connected.has(node.node_id))
    filtered.edges = filtered.edges.filter((edge) => connected.has(edge.from_node_id) && connected.has(edge.to_node_id))
    filtered.issues = filtered.issues.filter((issue) => connected.has(`${issue.asset_type}:${issue.asset_id}`))
    filtered.orphans = filtered.orphans.filter((orphan) => connected.has(orphan.node_id))
  }
  if (assetType) {
    const keep = new Set(filtered.nodes.filter((node) => node.asset_type === assetType).map((node) => node.node_id))
    filtered.nodes = filtered.nodes.filter((node) => keep.has(node.node_id))
    filtered.edges = filtered.edges.filter((edge) => keep.has(edge.from_node_id) || keep.has(edge.to_node_id))
    filtered.issues = filtered.issues.filter((issue) => issue.asset_type === assetType)
    filtered.orphans = filtered.orphans.filter((orphan) => keep.has(orphan.node_id))
  }
  if (issueSeverity) {
    filtered.issues = filtered.issues.filter((issue) => issue.severity === issueSeverity)
  }
  filtered.filters = { briefing_id: briefingId, asset_type: assetType, issue_severity: issueSeverity }
  filtered.summary = {
    ...filtered.summary,
    node_count: filtered.nodes.length,
    edge_count: filtered.edges.length,
    blocking_issue_count: filtered.issues.filter((issue) => issue.severity === 'blocking').length,
    warning_issue_count: filtered.issues.filter((issue) => issue.severity === 'warning').length,
    orphan_node_count: filtered.orphans.length,
    missing_reference_count: filtered.issues.filter((issue) => issue.issue_type === 'missing_reference').length,
  }
  filtered.traceability_readiness = filtered.summary.blocking_issue_count
    ? 'blocked'
    : (filtered.summary.warning_issue_count ? 'needs_review' : 'ready')
  return filtered
}

export async function listResearchProjects() {
  return {
    success: true,
    data: {
      projects: clone(demoState),
      total: demoState.length,
    },
  }
}

export async function getResearchProject(projectId) {
  return { success: true, data: clone(findProject(projectId)) }
}

export async function createResearchProject() {
  readonlyError()
}

export async function updateResearchProject() {
  readonlyError()
}

export async function getLocalEvidencePack(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      local_evidence_pack: clone(project.local_evidence_pack || emptyPack()),
    },
  }
}

export async function searchLocalEvidencePack(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      local_evidence_pack: clone(project.local_evidence_pack || emptyPack()),
    },
  }
}

export async function updateLocalEvidenceCandidate(projectId, evidenceId, payload = {}) {
  const status = payload.status
  if (!['candidate', 'accepted', 'rejected'].includes(status)) {
    throw new Error('status must be candidate, accepted, or rejected')
  }
  const project = findProject(projectId)
  const pack = project.local_evidence_pack
  const candidate = (pack?.candidates || []).find((item) => item.evidence_id === evidenceId)
  if (!candidate) {
    throw new Error(`Demo data not available for local evidence candidate: ${evidenceId}`)
  }
  candidate.status = status
  candidate.review_note = payload.note || ''
  candidate.reviewed_at = '2026-04-28T00:00:00.000000'
  const accepted = new Set(pack.accepted_evidence_ids || [])
  const rejected = new Set(pack.rejected_evidence_ids || [])
  accepted.delete(evidenceId)
  rejected.delete(evidenceId)
  if (status === 'accepted') accepted.add(evidenceId)
  if (status === 'rejected') rejected.add(evidenceId)
  pack.accepted_evidence_ids = Array.from(accepted).sort()
  pack.rejected_evidence_ids = Array.from(rejected).sort()
  pack.summary = rebuildSummary(pack)
  pack.updated_at = '2026-04-28T00:00:00.000000'
  syncEvidenceItems(project, candidate, status)
  return {
    success: true,
    data: {
      project_id: projectId,
      local_evidence_pack: clone(pack),
      evidence_items: clone(project.evidence_items || []),
    },
  }
}

export async function listResearchRuns(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      research_runs: clone(project.research_runs || []),
      total: (project.research_runs || []).length,
    },
  }
}

export async function listConsultationLogs(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      consultation_logs: clone(project.consultation_logs || []),
      total: (project.consultation_logs || []).length,
    },
  }
}

export async function listExternalResearchPacks(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      external_research_packs: clone(project.external_research_packs || []),
      total: (project.external_research_packs || []).length,
    },
  }
}

export async function updateExternalResearchCandidate(projectId, packId, candidateId, payload = {}) {
  const status = payload.review_status
  if (!['pending', 'accepted', 'rejected'].includes(status)) {
    throw new Error('review_status must be pending, accepted, or rejected')
  }
  const project = findProject(projectId)
  const pack = (project.external_research_packs || []).find((item) => item.pack_id === packId)
  if (!pack) {
    throw new Error(`Demo data not available for external research pack: ${packId}`)
  }
  const candidate = (pack.evidence_candidates || []).find(
    (item) => item.candidate_id === candidateId || item.external_id === candidateId,
  )
  if (!candidate) {
    throw new Error(`Demo data not available for external evidence candidate: ${candidateId}`)
  }
  candidate.review_status = status
  candidate.review_note = payload.review_note || ''
  candidate.reviewed_at = '2026-04-28T00:00:00.000000'
  pack.accepted_count = (pack.evidence_candidates || []).filter((item) => item.review_status === 'accepted').length
  pack.updated_at = '2026-04-28T00:00:00.000000'
  syncExternalEvidenceItems(project, pack, candidate, status)
  return {
    success: true,
    data: {
      project_id: projectId,
      external_research_pack: clone(pack),
      evidence_items: clone(project.evidence_items || []),
    },
  }
}

export async function listEvidenceMatrixRows(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      rows: clone(project.evidence_matrix_rows || []),
      total: (project.evidence_matrix_rows || []).length,
    },
  }
}

export async function createEvidenceMatrixRow() {
  readonlyError()
}

export async function updateEvidenceMatrixRow(projectId, rowId, payload = {}) {
  const project = findProject(projectId)
  const row = updateIndexedAsset(project, 'evidence_matrix_rows', rowId, payload)
  return {
    success: true,
    data: {
      project_id: projectId,
      row: clone(row),
    },
  }
}

export async function listInsightCards(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      insight_cards: clone(project.insight_cards || []),
      total: (project.insight_cards || []).length,
    },
  }
}

export async function createInsightCard() {
  readonlyError()
}

export async function updateInsightCard(projectId, cardId, payload = {}) {
  const project = findProject(projectId)
  const card = updateIndexedAsset(project, 'insight_cards', cardId, payload)
  return {
    success: true,
    data: {
      project_id: projectId,
      insight_card: clone(card),
    },
  }
}

export async function listArtifactDrafts(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      artifact_drafts: clone(project.artifact_drafts || []),
      total: (project.artifact_drafts || []).length,
    },
  }
}

export async function createArtifactDraft() {
  readonlyError()
}

export async function updateArtifactDraft(projectId, draftId, payload = {}) {
  const project = findProject(projectId)
  const draft = updateIndexedAsset(project, 'artifact_drafts', draftId, payload)
  return {
    success: true,
    data: {
      project_id: projectId,
      artifact_draft: clone(draft),
    },
  }
}

export async function listArtifactPacks(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      artifact_packs: clone(project.artifact_packs || []),
      total: (project.artifact_packs || []).length,
    },
  }
}

export async function createArtifactPack() {
  readonlyError()
}

export async function updateArtifactPack(projectId, packId, payload = {}) {
  const project = findProject(projectId)
  const pack = findPack(project, packId)
  Object.assign(pack, payload, { updated_at: '2026-04-28T00:00:00.000000' })
  return { success: true, data: { project_id: projectId, artifact_pack: clone(pack) } }
}

export async function addArtifactPackItem(projectId, packId, payload = {}) {
  const project = findProject(projectId)
  const pack = findPack(project, packId)
  pack.items = pack.items || []
  pack.items.push({
    item_id: `api_demo_${pack.items.length + 1}`,
    status: 'included',
    sequence: pack.items.length + 1,
    ...payload,
    created_at: '2026-04-28T00:00:00.000000',
    updated_at: '2026-04-28T00:00:00.000000',
  })
  pack.updated_at = '2026-04-28T00:00:00.000000'
  return { success: true, data: { project_id: projectId, artifact_pack: clone(pack) } }
}

export async function addArtifactPackPage(projectId, packId, payload = {}) {
  const project = findProject(projectId)
  const pack = findPack(project, packId)
  pack.pages = pack.pages || []
  pack.pages.push({
    page_id: `pg_demo_${pack.pages.length + 1}`,
    sequence: pack.pages.length + 1,
    page_type: 'argument',
    key_messages: [],
    source_insight_ids: [],
    source_evidence_ids: [],
    source_matrix_row_ids: [],
    material_status: 'planned',
    review_status: 'unreviewed',
    ...payload,
    created_at: '2026-04-28T00:00:00.000000',
    updated_at: '2026-04-28T00:00:00.000000',
  })
  pack.updated_at = '2026-04-28T00:00:00.000000'
  return { success: true, data: { project_id: projectId, artifact_pack: clone(pack) } }
}

export async function addArtifactPackFileRef(projectId, packId, payload = {}) {
  const project = findProject(projectId)
  const pack = findPack(project, packId)
  pack.file_refs = pack.file_refs || []
  pack.file_refs.push({
    file_ref_id: `fr_demo_${pack.file_refs.length + 1}`,
    linked_page_ids: [],
    linked_artifact_draft_ids: [],
    ...payload,
    created_at: '2026-04-28T00:00:00.000000',
  })
  pack.updated_at = '2026-04-28T00:00:00.000000'
  return { success: true, data: { project_id: projectId, artifact_pack: clone(pack) } }
}

export async function addArtifactPackReviewRound(projectId, packId, payload = {}) {
  const project = findProject(projectId)
  const pack = findPack(project, packId)
  pack.review_rounds = pack.review_rounds || []
  const decisions = (payload.decisions || []).map((decision, index) => ({
    decision_id: `rd_demo_${pack.review_rounds.length + 1}_${index + 1}`,
    severity: 'minor',
    resolved: false,
    ...decision,
    created_at: '2026-04-28T00:00:00.000000',
  }))
  for (const decision of decisions) {
    if (decision.target_type === 'page') {
      const page = (pack.pages || []).find((item) => item.page_id === decision.target_id)
      if (page && ['accepted', 'needs_revision', 'rejected'].includes(decision.decision)) {
        page.review_status = decision.decision
      }
    }
  }
  pack.review_rounds.push({
    review_round_id: `rv_demo_${pack.review_rounds.length + 1}`,
    status: 'completed',
    ...payload,
    decisions,
    created_at: '2026-04-28T00:00:00.000000',
    updated_at: '2026-04-28T00:00:00.000000',
  })
  pack.updated_at = '2026-04-28T00:00:00.000000'
  return { success: true, data: { project_id: projectId, artifact_pack: clone(pack) } }
}

export async function listStrategicOptions(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      strategic_options: clone(project.strategic_options || []),
      total: (project.strategic_options || []).length,
    },
  }
}

export async function createStrategicOption() {
  readonlyError()
}

export async function updateStrategicOption(projectId, optionId, payload = {}) {
  const project = findProject(projectId)
  const option = updateAssetByField(project, 'strategic_options', 'option_id', optionId, payload)
  return { success: true, data: { project_id: projectId, strategic_option: clone(option) } }
}

export async function listValidationPlans(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      validation_plans: clone(project.validation_plans || []),
      total: (project.validation_plans || []).length,
    },
  }
}

export async function createValidationPlan() {
  readonlyError()
}

export async function updateValidationPlan(projectId, planId, payload = {}) {
  const project = findProject(projectId)
  const plan = updateAssetByField(project, 'validation_plans', 'plan_id', planId, payload)
  return { success: true, data: { project_id: projectId, validation_plan: clone(plan) } }
}

export async function listLeadershipDecisionRecords(projectId) {
  const project = findProject(projectId)
  return {
    success: true,
    data: {
      project_id: projectId,
      leadership_decision_records: clone(project.leadership_decision_records || []),
      total: (project.leadership_decision_records || []).length,
    },
  }
}

export async function createLeadershipDecisionRecord() {
  readonlyError()
}

export async function updateLeadershipDecisionRecord(projectId, decisionId, payload = {}) {
  const project = findProject(projectId)
  const record = updateAssetByField(project, 'leadership_decision_records', 'decision_id', decisionId, payload)
  return { success: true, data: { project_id: projectId, leadership_decision_record: clone(record) } }
}

export async function listLeadershipBriefings(projectId) {
  const project = findProject(projectId)
  const briefings = (project.leadership_briefings || []).map((briefing) => ({
    briefing_id: briefing.briefing_id,
    title: briefing.title,
    briefing_type: briefing.briefing_type,
    audience: briefing.audience,
    status: briefing.status,
    readiness: briefing.readiness,
    section_count: (briefing.sections || []).length,
    source_counts: briefing.source_counts || {},
    created_at: briefing.created_at,
    updated_at: briefing.updated_at,
  }))
  return {
    success: true,
    data: {
      project_id: projectId,
      leadership_briefings: clone(briefings),
      total: briefings.length,
    },
  }
}

export async function getLeadershipBriefing(projectId, briefingId) {
  const project = findProject(projectId)
  const briefing = (project.leadership_briefings || []).find((item) => item.briefing_id === briefingId)
  if (!briefing) {
    throw new Error(`Demo data not available for leadership briefing: ${briefingId}`)
  }
  return { success: true, data: { project_id: projectId, leadership_briefing: clone(briefing) } }
}

export async function createLeadershipBriefing() {
  readonlyError()
}

export async function updateLeadershipBriefing(projectId, briefingId, payload = {}) {
  const project = findProject(projectId)
  const before = clone((project.leadership_briefings || []).find((item) => item.briefing_id === briefingId))
  const briefing = updateAssetByField(project, 'leadership_briefings', 'briefing_id', briefingId, payload)
  recordReviewHistory(project, {
    assetType: 'leadership_briefing',
    assetId: briefingId,
    before,
    after: briefing,
  })
  return { success: true, data: { project_id: projectId, leadership_briefing: clone(briefing) } }
}

export async function getTraceabilityMap(projectId, params = {}) {
  const project = findProject(projectId)
  const map = project.traceability_map || emptyTraceabilityMap(projectId)
  return { success: true, data: filterTraceabilityMap(map, params) }
}

export async function listGovernanceReviews(projectId) {
  const project = findProject(projectId)
  const reviews = (project.governance_reviews || []).map(governanceReviewIndex)
  return {
    success: true,
    data: {
      project_id: projectId,
      governance_reviews: clone(reviews),
      total: reviews.length,
    },
  }
}

export async function createGovernanceReview() {
  readonlyError()
}

export async function getGovernanceReview(projectId, reviewId) {
  const project = findProject(projectId)
  const review = (project.governance_reviews || []).find((item) => item.review_id === reviewId)
  if (!review) {
    throw new Error(`Demo data not available for governance review: ${reviewId}`)
  }
  return { success: true, data: { project_id: projectId, governance_review: clone(review) } }
}

export async function updateGovernanceReview(projectId, reviewId, payload = {}) {
  const project = findProject(projectId)
  const before = clone((project.governance_reviews || []).find((item) => item.review_id === reviewId))
  const review = updateAssetByField(project, 'governance_reviews', 'review_id', reviewId, payload)
  recordReviewHistory(project, {
    assetType: 'governance_review',
    assetId: reviewId,
    before,
    after: review,
  })
  return { success: true, data: { project_id: projectId, governance_review: clone(review) } }
}

export async function listReviewHistory(projectId, params = {}) {
  const project = findProject(projectId)
  let entries = project.review_history_entries || []
  if (params.asset_type) entries = entries.filter((item) => item.asset_type === params.asset_type)
  if (params.asset_id) entries = entries.filter((item) => item.asset_id === params.asset_id)
  if (params.event_type) entries = entries.filter((item) => item.event_type === params.event_type)
  const limit = Number(params.limit || 50)
  entries = entries.slice(0, Number.isFinite(limit) ? limit : 50)
  return { success: true, data: { project_id: projectId, review_history_entries: clone(entries), total: entries.length } }
}

export async function getAssetReviewHistory(projectId, assetType, assetId, params = {}) {
  const response = await listReviewHistory(projectId, { ...params, asset_type: assetType, asset_id: assetId, limit: params.limit || 100 })
  return {
    success: true,
    data: {
      project_id: projectId,
      asset_type: assetType,
      asset_id: assetId,
      review_history_entries: response.data.review_history_entries,
      total: response.data.total,
    },
  }
}

export async function getReviewHistoryEntry(projectId, historyEntryId) {
  const project = findProject(projectId)
  const entry = (project.review_history_entries || []).find((item) => item.history_entry_id === historyEntryId)
  if (!entry) {
    throw new Error(`Demo data not available for review history entry: ${historyEntryId}`)
  }
  return { success: true, data: { project_id: projectId, review_history_entry: clone(entry) } }
}

export async function createReviewHistoryNote(projectId, payload = {}) {
  const project = findProject(projectId)
  const assetType = payload.asset_type || payload.asset_ref?.asset_type
  const assetId = payload.asset_id || payload.asset_ref?.asset_id
  if (!assetType || !assetId) {
    throw new Error('asset_type and asset_id are required')
  }
  const entry = recordReviewHistory(project, {
    assetType,
    assetId,
    before: {},
    after: { title: payload.asset_title || assetId, updated_by: payload.actor?.display_name },
    eventType: 'review_note_added',
    note: String(payload.note || '').trim(),
  })
  return { success: true, data: { project_id: projectId, review_history_entry: clone(entry) } }
}

export async function listResearchSnapshots(projectId) {
  const project = findProject(projectId)
  const snapshots = project.research_snapshots || []
  return { success: true, data: { project_id: projectId, snapshots: clone(snapshots), total: snapshots.length } }
}

export async function createResearchSnapshot(projectId, payload = {}) {
  const project = findProject(projectId)
  if (!payload.title) {
    throw new Error('title is required')
  }
  const snapshot = buildDemoSnapshot(project, payload)
  project.research_snapshot_details = {
    ...(project.research_snapshot_details || {}),
    [snapshot.snapshot_id]: snapshot,
  }
  project.research_snapshots = [snapshotIndex(snapshot), ...(project.research_snapshots || [])]
  recordReviewHistory(project, {
    assetType: 'research_snapshot',
    assetId: snapshot.snapshot_id,
    before: { snapshot_count: Math.max(0, project.research_snapshots.length - 1) },
    after: { snapshot_count: project.research_snapshots.length, title: snapshot.title, updated_by: snapshot.actor?.display_name },
    eventType: 'research_snapshot_created',
    note: snapshot.reason,
  })
  return { success: true, data: { project_id: projectId, snapshot: clone(snapshot) } }
}

export async function getResearchSnapshot(projectId, snapshotId) {
  const project = findProject(projectId)
  const snapshot = project.research_snapshot_details?.[snapshotId]
  if (!snapshot) {
    throw new Error(`Demo data not available for research snapshot: ${snapshotId}`)
  }
  return { success: true, data: { project_id: projectId, snapshot: clone(snapshot) } }
}

export async function diffResearchSnapshot(projectId, snapshotId) {
  const project = findProject(projectId)
  const snapshot = project.research_snapshot_details?.[snapshotId]
  if (!snapshot) {
    throw new Error(`Demo data not available for research snapshot: ${snapshotId}`)
  }
  const current = buildDemoSnapshot(project, {
    title: snapshot.title,
    included_asset_kinds: snapshot.included_asset_kinds,
    governance_review_id: snapshot.linked_governance_review?.governance_review_id,
  })
  const changes = {}
  let assetsAdded = 0
  let assetsChanged = 0
  for (const kind of Object.keys(snapshot.asset_fingerprints || {})) {
    const before = Object.fromEntries((snapshot.asset_fingerprints[kind] || []).map((item) => [item.asset_id, item]))
    const after = Object.fromEntries((current.asset_fingerprints[kind] || []).map((item) => [item.asset_id, item]))
    const added = Object.keys(after).filter((id) => !before[id])
    const changed = Object.keys(after).filter((id) => before[id] && before[id].fingerprint !== after[id].fingerprint)
    if (added.length || changed.length) {
      changes[kind] = {
        added,
        removed: Object.keys(before).filter((id) => !after[id]),
        changed,
      }
      assetsAdded += added.length
      assetsChanged += changed.length
    }
  }
  const reviewHistoryChanged = snapshot.review_history_watermark.entry_count !== current.review_history_watermark.entry_count
  const governanceChanged = snapshot.linked_governance_review?.gate_decision !== current.linked_governance_review?.gate_decision
  const briefingChanged = snapshot.linked_leadership_briefing?.readiness !== current.linked_leadership_briefing?.readiness
  return {
    success: true,
    data: {
      project_id: projectId,
      snapshot_diff: {
        project_id: projectId,
        snapshot_id: snapshotId,
        snapshot_created_at: snapshot.created_at,
        compared_at: '2026-04-28T00:00:00.000000',
        summary: {
          has_changes: Boolean(Object.keys(changes).length || reviewHistoryChanged || governanceChanged || briefingChanged),
          asset_kinds_changed: Object.keys(changes).length,
          assets_added: assetsAdded,
          assets_removed: 0,
          assets_changed: assetsChanged,
          review_history_changed: reviewHistoryChanged,
          governance_gate_decision_changed: governanceChanged,
          leadership_briefing_readiness_changed: briefingChanged,
        },
        asset_id_changes: changes,
        asset_state_changes: {},
        review_history_change: {
          from_entry_count: snapshot.review_history_watermark.entry_count,
          to_entry_count: current.review_history_watermark.entry_count,
          changed: reviewHistoryChanged,
        },
        governance_change: {
          from_gate_decision: snapshot.linked_governance_review?.gate_decision || '',
          to_gate_decision: current.linked_governance_review?.gate_decision || '',
          changed: governanceChanged,
        },
        leadership_briefing_change: {
          from_readiness: snapshot.linked_leadership_briefing?.readiness || '',
          to_readiness: current.linked_leadership_briefing?.readiness || '',
          changed: briefingChanged,
        },
      },
    },
  }
}

export async function listSnapshotReviewNotes(projectId, snapshotId) {
  const project = findProject(projectId)
  const notes = (project.snapshot_review_notes || []).filter((note) => note.snapshot_id === snapshotId)
  notes.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
  return { success: true, data: { project_id: projectId, snapshot_id: snapshotId, snapshot_review_notes: clone(notes), total: notes.length } }
}

export async function createSnapshotReviewNote(projectId, snapshotId, payload = {}) {
  const project = findProject(projectId)
  if (!project.research_snapshot_details?.[snapshotId]) {
    throw new Error(`Demo data not available for research snapshot: ${snapshotId}`)
  }
  const noteText = String(payload.note || '').trim()
  if (!noteText) {
    throw new Error('note is required')
  }
  const targetRef = payload.target_ref || {}
  if (!targetRef.section_key) {
    throw new Error('target_ref.section_key is required')
  }
  const note = {
    schema_version: 1,
    note_id: `srn_demo_${String((project.snapshot_review_notes || []).length + 1).padStart(8, '0')}`,
    project_id: projectId,
    snapshot_id: snapshotId,
    target_ref: {
      section_key: targetRef.section_key,
      asset_kind: targetRef.asset_kind || '',
      asset_id: targetRef.asset_id || '',
      field: targetRef.field || '',
    },
    note_type: payload.note_type || 'observation',
    severity: payload.severity || 'watch',
    status: 'open',
    owner: '',
    resolution_note: '',
    resolved_at: '',
    resolved_by: '',
    note: noteText,
    actor: payload.actor || { actor_type: 'manual_user', display_name: 'Reviewer' },
    created_at: '2026-04-28T00:00:00.000000',
    updated_at: '2026-04-28T00:00:00.000000',
    source: {
      kind: 'snapshot_diff_review',
      snapshot_id: snapshotId,
      created_from: 'snapshot_evidence_review_panel',
    },
  }
  project.snapshot_review_notes = [note, ...(project.snapshot_review_notes || [])]
  const history = recordReviewHistory(project, {
    assetType: 'snapshot_review_note',
    assetId: note.note_id,
    before: { note_count: Math.max(0, project.snapshot_review_notes.length - 1) },
    after: { note_count: project.snapshot_review_notes.length, title: note.note_id, updated_by: note.actor?.display_name },
    eventType: 'snapshot_review_note_created',
    note: note.note,
  })
  return {
    success: true,
    data: {
      project_id: projectId,
      snapshot_id: snapshotId,
      snapshot_review_note: clone(note),
      review_history_entry_id: history?.history_entry_id || '',
    },
  }
}

export async function getSnapshotReviewNote(projectId, snapshotId, noteId) {
  const project = findProject(projectId)
  const note = (project.snapshot_review_notes || []).find((item) => item.snapshot_id === snapshotId && item.note_id === noteId)
  if (!note) {
    throw new Error(`Demo data not available for snapshot review note: ${noteId}`)
  }
  return { success: true, data: { project_id: projectId, snapshot_id: snapshotId, snapshot_review_note: clone(note) } }
}

export async function updateSnapshotReviewNote(projectId, snapshotId, noteId, payload = {}) {
  const project = findProject(projectId)
  if (!project.research_snapshot_details?.[snapshotId]) {
    throw new Error(`Demo data not available for research snapshot: ${snapshotId}`)
  }
  const note = (project.snapshot_review_notes || []).find((item) => item.snapshot_id === snapshotId && item.note_id === noteId)
  if (!note) {
    throw new Error(`Demo data not available for snapshot review note: ${noteId}`)
  }
  const allowed = new Set(['status', 'owner', 'resolution_note', 'actor'])
  const unknown = Object.keys(payload).filter((key) => !allowed.has(key))
  if (unknown.length) {
    throw new Error(`Unsupported snapshot review note update fields: ${unknown.join(', ')}`)
  }
  const statuses = new Set(['open', 'acknowledged', 'resolved', 'deferred'])
  if (payload.status && !statuses.has(payload.status)) {
    throw new Error('status must be one of open, acknowledged, resolved, deferred')
  }
  const actor = typeof payload.actor === 'string'
    ? { actor_type: 'manual_user', display_name: payload.actor }
    : (payload.actor || { actor_type: 'manual_user', display_name: 'Reviewer' })
  const actorName = actor.display_name || actor.actor_id || 'Reviewer'
  const before = clone(note)
  if (Object.hasOwn(payload, 'status')) note.status = payload.status
  if (Object.hasOwn(payload, 'owner')) note.owner = String(payload.owner || '').trim()
  if (Object.hasOwn(payload, 'resolution_note')) note.resolution_note = String(payload.resolution_note || '').trim()
  if (before.status !== 'resolved' && note.status === 'resolved') {
    note.resolved_at = '2026-04-28T00:00:00.000000'
    note.resolved_by = actorName
  } else if (before.status === 'resolved' && note.status !== 'resolved') {
    note.resolved_at = ''
    note.resolved_by = ''
  }
  const after = clone(note)
  const changed = ['status', 'owner', 'resolution_note', 'resolved_at', 'resolved_by']
    .some((field) => JSON.stringify(before[field] || '') !== JSON.stringify(after[field] || ''))
  let history = null
  if (changed) {
    note.updated_at = '2026-04-28T00:00:00.000000'
    history = recordReviewHistory(project, {
      assetType: 'snapshot_review_note',
      assetId: note.note_id,
      before,
      after: { ...clone(note), updated_by: actorName },
      eventType: 'snapshot_review_note_disposition_updated',
      note: note.resolution_note || '',
    })
  }
  return {
    success: true,
    data: {
      project_id: projectId,
      snapshot_id: snapshotId,
      snapshot_review_note: clone(note),
      review_history_entry_id: history?.history_entry_id || '',
      history_recorded: Boolean(history),
    },
  }
}
