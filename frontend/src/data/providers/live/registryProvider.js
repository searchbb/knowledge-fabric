// Live registry provider — thin wrappers around the existing
// services/api/registryApi functions so the axios path is preserved.

import {
  listRegistryConcepts as apiListRegistryConcepts,
  getRegistryConcept as apiGetRegistryConcept,
  listCrossRelations as apiListCrossRelations,
  getCrossRelation as apiGetCrossRelation,
  getCrossRelationCounts as apiGetCrossRelationCounts,
} from '../../../services/api/registryApi'

export function listRegistryConcepts(conceptType) {
  return apiListRegistryConcepts(conceptType)
}

export function getRegistryConcept(entryId) {
  return apiGetRegistryConcept(entryId)
}

export function listCrossRelations(params = {}) {
  return apiListCrossRelations(params)
}

export function getCrossRelation(relationId) {
  return apiGetCrossRelation(relationId)
}

export function getCrossRelationCounts(entryIds) {
  return apiGetCrossRelationCounts(entryIds)
}
