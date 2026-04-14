import service from '../../api/index'

// -- CRUD ------------------------------------------------------------------

export function listRegistryConcepts(conceptType) {
  const params = conceptType ? { concept_type: conceptType } : {}
  return service({ url: '/api/registry/concepts', method: 'get', params })
}

export function getRegistryConcept(entryId) {
  return service({ url: `/api/registry/concepts/${entryId}`, method: 'get' })
}

export function createRegistryConcept({ canonical_name, concept_type, aliases, description }) {
  return service({
    url: '/api/registry/concepts',
    method: 'post',
    data: { canonical_name, concept_type, aliases, description },
  })
}

export function updateRegistryConcept(entryId, updates) {
  return service({
    url: `/api/registry/concepts/${entryId}`,
    method: 'put',
    data: updates,
  })
}

export function deleteRegistryConcept(entryId) {
  return service({ url: `/api/registry/concepts/${entryId}`, method: 'delete' })
}

// -- Link / unlink ---------------------------------------------------------

export function linkProjectConcept(entryId, { project_id, concept_key, project_name }) {
  return service({
    url: `/api/registry/concepts/${entryId}/links`,
    method: 'post',
    data: { project_id, concept_key, project_name },
  })
}

export function unlinkProjectConcept(entryId, { project_id, concept_key }) {
  return service({
    url: `/api/registry/concepts/${entryId}/links`,
    method: 'delete',
    data: { project_id, concept_key },
  })
}

// -- Search ----------------------------------------------------------------

export function searchRegistryConcepts(query, limit = 20) {
  return service({
    url: '/api/registry/concepts/search',
    method: 'get',
    params: { q: query, limit },
  })
}

// -- Suggest from project --------------------------------------------------

export function suggestFromProject(projectId) {
  return service({
    url: `/api/registry/suggest-from-project/${projectId}`,
    method: 'post',
  })
}

// -- Alignment -------------------------------------------------------------

export function getProjectAlignment(projectId) {
  return service({
    url: `/api/registry/projects/${projectId}/alignment`,
    method: 'get',
  })
}

// -- Cross-article relations (L3) ------------------------------------------

export function listCrossRelations(params = {}) {
  return service({ url: '/api/registry/cross-relations', method: 'get', params })
}

export function getCrossRelation(relationId) {
  return service({ url: `/api/registry/cross-relations/${relationId}`, method: 'get' })
}

export function createCrossRelation(data) {
  return service({ url: '/api/registry/cross-relations', method: 'post', data })
}

export function updateCrossRelation(relationId, data) {
  return service({ url: `/api/registry/cross-relations/${relationId}`, method: 'patch', data })
}

export function deleteCrossRelation(relationId) {
  return service({ url: `/api/registry/cross-relations/${relationId}`, method: 'delete' })
}

export function getCrossRelationCounts(entryIds) {
  return service({ url: '/api/registry/cross-relations/counts', method: 'post', data: { entry_ids: entryIds } })
}

export function getThemeCrossRelationsSummary(themeId) {
  return service({ url: `/api/registry/themes/${themeId}/cross-relations-summary`, method: 'get' })
}

export function discoverCrossRelations(data) {
  return service({ url: '/api/registry/cross-relations/discover', method: 'post', data })
}

// Phase C: Lookup canonical concept by project + node key
export function lookupConceptByProject(projectId, conceptKey, nodeName = '') {
  const params = { project_id: projectId }
  if (conceptKey) params.concept_key = conceptKey
  if (nodeName) params.node_name = nodeName
  return service({ url: '/api/registry/concepts/lookup', method: 'get', params })
}
