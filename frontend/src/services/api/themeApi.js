import service from '../../api/index'

export function getThemeView(projectId) {
  return service({
    url: `/api/theme/projects/${projectId}/view`,
    method: 'get',
  })
}

export function putThemeDecision(projectId, candidateKey, { status, note }) {
  return service({
    url: `/api/theme/projects/${projectId}/decisions/${encodeURIComponent(candidateKey)}`,
    method: 'put',
    data: { status, note },
  })
}

export function deleteThemeDecision(projectId, candidateKey) {
  return service({
    url: `/api/theme/projects/${projectId}/decisions/${encodeURIComponent(candidateKey)}`,
    method: 'delete',
  })
}

// Stage G: Theme Cluster API
export function listThemeClusters(projectId) {
  return service({ url: `/api/theme/projects/${projectId}/clusters`, method: 'get' })
}

export function createThemeCluster(projectId, { name, summary, source_theme_keys }) {
  return service({ url: `/api/theme/projects/${projectId}/clusters`, method: 'post', data: { name, summary, source_theme_keys } })
}

export function updateThemeCluster(projectId, clusterId, updates) {
  return service({ url: `/api/theme/projects/${projectId}/clusters/${clusterId}`, method: 'put', data: updates })
}

export function attachConceptsToCluster(projectId, clusterId, concept_ids) {
  return service({ url: `/api/theme/projects/${projectId}/clusters/${clusterId}/concepts:attach`, method: 'post', data: { concept_ids } })
}

export function detachConceptsFromCluster(projectId, clusterId, concept_ids) {
  return service({ url: `/api/theme/projects/${projectId}/clusters/${clusterId}/concepts:detach`, method: 'post', data: { concept_ids } })
}

export function attachEvidenceToCluster(projectId, clusterId, evidence_refs) {
  return service({ url: `/api/theme/projects/${projectId}/clusters/${clusterId}/evidence:attach`, method: 'post', data: { evidence_refs } })
}

// ====== Global Theme Hub-and-Spoke API (2026-04-12 redesign) ======

export function listGlobalThemes() {
  return service({ url: '/api/registry/themes', method: 'get' })
}

export function createGlobalTheme({ name, description, keywords }) {
  return service({ url: '/api/registry/themes', method: 'post', data: { name, description, keywords } })
}

export function getThemeHubView(themeId) {
  return service({ url: `/api/registry/themes/${themeId}/view`, method: 'get' })
}

export function attachMembers(themeId, conceptEntryIds, { role = 'member', score = 1.0 } = {}) {
  return service({ url: `/api/registry/themes/${themeId}/members`, method: 'post', data: { concept_entry_ids: conceptEntryIds, role, score } })
}

export function detachMembers(themeId, conceptEntryIds) {
  return service({ url: `/api/registry/themes/${themeId}/members`, method: 'delete', data: { concept_entry_ids: conceptEntryIds } })
}

export function promoteCandidate(themeId, conceptEntryIds) {
  return service({ url: `/api/registry/themes/${themeId}/candidates/promote`, method: 'post', data: { concept_entry_ids: conceptEntryIds } })
}

export function rejectCandidate(themeId, conceptEntryIds) {
  return service({ url: `/api/registry/themes/${themeId}/candidates/reject`, method: 'post', data: { concept_entry_ids: conceptEntryIds } })
}

export function getOrphans(limit = 200) {
  return service({ url: '/api/registry/themes/orphans', method: 'get', params: { limit } })
}

export function mergeThemes(sourceThemeId, targetThemeId) {
  return service({ url: '/api/registry/themes/merge', method: 'post', data: { source_theme_id: sourceThemeId, target_theme_id: targetThemeId } })
}

// Phase B: Theme panorama
export function getThemePanorama(themeId) {
  return service({ url: `/api/registry/themes/${themeId}/panorama`, method: 'get' })
}

// P1 governance
export function runGovernanceScan({ dryRun = false, enableLlmAdjudication = true } = {}) {
  return service({
    url: '/api/registry/themes/governance-scan',
    method: 'post',
    data: { dry_run: dryRun, enable_llm_adjudication: enableLlmAdjudication },
  })
}

export function getGovernanceRequest() {
  return service({ url: '/api/registry/themes/governance-request', method: 'get' })
}
