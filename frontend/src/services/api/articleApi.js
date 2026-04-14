import service from '../../api/index'

export function getArticleView(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get',
  })
}

export function getArticleGraph(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get',
  })
}
