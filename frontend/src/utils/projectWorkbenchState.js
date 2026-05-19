import { getProject, getGraphData, getTaskStatus } from '../api/graph'

const WORKSPACE_GRAPH_LOAD_TIMEOUT_MS = 8000

function buildUnavailableGraphData(project, error) {
  const graphArtifact = project.phase1_task_result?.artifacts?.graph || {}
  return {
    graph_id: project.graph_id || graphArtifact.graph_id || null,
    nodes: [],
    edges: [],
    node_count: graphArtifact.node_count || 0,
    edge_count: graphArtifact.edge_count || 0,
    unavailable: true,
    unavailable_reason: error?.message || '图谱后端暂不可用',
  }
}

export async function loadProjectWorkbenchState(projectId) {
  const projectResponse = await getProject(projectId)
  if (!projectResponse.success || !projectResponse.data) {
    throw new Error(projectResponse.error || '项目加载失败')
  }

  const project = projectResponse.data
  let graphData = null
  let phase1TaskResult = project.phase1_task_result || null
  const shouldRefreshTaskResult = project.graph_build_task_id && (
    !phase1TaskResult || project.status !== 'graph_completed'
  )

  if (shouldRefreshTaskResult) {
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
    try {
      const graphResponse = await getGraphData(project.graph_id, {
        timeout: WORKSPACE_GRAPH_LOAD_TIMEOUT_MS,
      })
      if (!graphResponse.success) {
        throw new Error(graphResponse.error || '图谱加载失败')
      }
      graphData = graphResponse.data || null
    } catch (error) {
      console.warn('加载项目图谱失败，将继续复用项目和阅读骨架状态:', error)
      graphData = buildUnavailableGraphData(project, error)
    }
  }

  return {
    project,
    graphData,
    phase1TaskResult,
  }
}
