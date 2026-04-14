import service from '../../api/index'

export function getConceptView(projectId) {
  return service({
    url: `/api/concept/projects/${projectId}/view`,
    method: 'get',
  })
}

export function putConceptDecision(projectId, conceptKey, { status, note, canonical_name }) {
  return service({
    url: `/api/concept/projects/${projectId}/decisions/${encodeURIComponent(conceptKey)}`,
    method: 'put',
    data: { status, note, canonical_name },
  })
}

export function deleteConceptDecision(projectId, conceptKey) {
  return service({
    url: `/api/concept/projects/${projectId}/decisions/${encodeURIComponent(conceptKey)}`,
    method: 'delete',
  })
}

export function postConceptMergeSuggest(projectId) {
  return service({
    url: `/api/concept/projects/${projectId}/merge-suggest`,
    method: 'post',
  })
}

export function postConceptNormalize(projectId) {
  return service({
    url: `/api/concept/projects/${projectId}/normalize`,
    method: 'post',
  })
}
