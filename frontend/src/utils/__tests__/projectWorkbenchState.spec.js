import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadProjectWorkbenchState } from '../projectWorkbenchState'

const getProjectMock = vi.fn()
const getGraphDataMock = vi.fn()
const getTaskStatusMock = vi.fn()

vi.mock('../../api/graph', () => ({
  getProject: (...args) => getProjectMock(...args),
  getGraphData: (...args) => getGraphDataMock(...args),
  getTaskStatus: (...args) => getTaskStatusMock(...args),
}))

describe('loadProjectWorkbenchState', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('falls back to persisted phase1 snapshot when task lookup fails', async () => {
    getProjectMock.mockResolvedValue({
      success: true,
      data: {
        project_id: 'proj_1',
        graph_id: 'graph_1',
        graph_build_task_id: 'task_1',
        phase1_task_result: {
          provider: 'local',
          build_outcome: {
            status: 'completed_with_warnings',
          },
        },
      },
    })
    getTaskStatusMock.mockRejectedValue(new Error('task cache lost'))
    getGraphDataMock.mockResolvedValue({
      success: true,
      data: {
        graph_id: 'graph_1',
        node_count: 2,
        edge_count: 1,
      },
    })

    const result = await loadProjectWorkbenchState('proj_1')

    expect(result.phase1TaskResult).toEqual({
      provider: 'local',
      build_outcome: {
        status: 'completed_with_warnings',
      },
    })
    expect(result.graphData.graph_id).toBe('graph_1')
    expect(getGraphDataMock).toHaveBeenCalledWith('graph_1', { timeout: 8000 })
  })

  it('prefers live task result when it is still available', async () => {
    getProjectMock.mockResolvedValue({
      success: true,
      data: {
        project_id: 'proj_1',
        graph_id: null,
        graph_build_task_id: 'task_1',
        phase1_task_result: {
          provider: 'local',
          build_outcome: {
            status: 'completed',
          },
        },
      },
    })
    getTaskStatusMock.mockResolvedValue({
      success: true,
      data: {
        result: {
          provider: 'zep',
          build_outcome: {
            status: 'failed',
          },
        },
      },
    })

    const result = await loadProjectWorkbenchState('proj_1')

    expect(result.phase1TaskResult).toEqual({
      provider: 'zep',
      build_outcome: {
        status: 'failed',
      },
    })
  })

  it('keeps project and reading state available when graph backend is down', async () => {
    getProjectMock.mockResolvedValue({
      success: true,
      data: {
        project_id: 'proj_1',
        graph_id: 'graph_1',
        graph_build_task_id: null,
        reading_structure: {
          title: '持久化阅读骨架',
        },
        phase1_task_result: {
          artifacts: {
            graph: {
              graph_id: 'graph_1',
              node_count: 46,
              edge_count: 33,
            },
          },
          reading_structure_status: {
            status: 'generated',
          },
        },
      },
    })
    getGraphDataMock.mockRejectedValue(new Error('Neo4j unavailable'))

    const result = await loadProjectWorkbenchState('proj_1')

    expect(result.project.reading_structure.title).toBe('持久化阅读骨架')
    expect(result.phase1TaskResult.reading_structure_status.status).toBe('generated')
    expect(result.graphData).toMatchObject({
      graph_id: 'graph_1',
      node_count: 46,
      edge_count: 33,
      unavailable: true,
      unavailable_reason: 'Neo4j unavailable',
    })
  })

  it('uses persisted phase1 snapshot for completed projects without probing stale task ids', async () => {
    getProjectMock.mockResolvedValue({
      success: true,
      data: {
        project_id: 'proj_1',
        status: 'graph_completed',
        graph_id: 'graph_1',
        graph_build_task_id: 'stale_task_1',
        phase1_task_result: {
          provider: 'persisted',
          reading_structure_status: {
            status: 'generated',
          },
        },
      },
    })
    getGraphDataMock.mockResolvedValue({
      success: true,
      data: {
        graph_id: 'graph_1',
        node_count: 46,
        edge_count: 33,
      },
    })

    const result = await loadProjectWorkbenchState('proj_1')

    expect(getTaskStatusMock).not.toHaveBeenCalled()
    expect(result.phase1TaskResult.provider).toBe('persisted')
  })
})
