import { getProject, getGraphData, getTaskStatus } from '../api/graph'

export async function loadProjectWorkbenchState(projectId) {
  const projectResponse = await getProject(projectId)
  if (!projectResponse.success || !projectResponse.data) {
    throw new Error(projectResponse.error || '项目加载失败')
  }

  const project = projectResponse.data
  let graphData = null
  let phase1TaskResult = project.phase1_task_result || null

  if (project.graph_build_task_id) {
    try {
      const taskResponse = await getTaskStatus(project.graph_build_task_id)
      if (taskResponse.success) {
        phase1TaskResult = taskResponse.data?.result || phase1TaskResult
      }
    } catch (error) {
      console.warn('加载 phase-1 task result 失败:', error)
    }
  }

  if (project.graph_id) {
    const graphResponse = await getGraphData(project.graph_id)
    if (!graphResponse.success) {
      throw new Error(graphResponse.error || '图谱加载失败')
    }
    graphData = graphResponse.data || null
  }

  return {
    project,
    graphData,
    phase1TaskResult,
  }
}
