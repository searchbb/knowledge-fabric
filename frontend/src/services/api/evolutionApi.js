import service from '../../api/index'

export function getEvolutionView(projectId) {
  return service({
    url: `/api/evolution/projects/${projectId}/view`,
    method: 'get',
  })
}
