import service from '../../api/index'

export function getReviewView(projectId) {
  return service({
    url: `/api/review/projects/${projectId}/view`,
    method: 'get',
  })
}

export function putReviewDecision(projectId, itemId, { status, note }) {
  return service({
    url: `/api/review/projects/${projectId}/items/${itemId}`,
    method: 'put',
    data: { status, note },
  })
}

export function deleteReviewDecision(projectId, itemId) {
  return service({
    url: `/api/review/projects/${projectId}/items/${itemId}`,
    method: 'delete',
  })
}
