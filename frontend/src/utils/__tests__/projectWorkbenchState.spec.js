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
})
