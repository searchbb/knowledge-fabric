import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import SimulationView from '../SimulationView.vue'

const pushMock = vi.fn()
const getSimulationMock = vi.fn()
const getEnvStatusMock = vi.fn()
const closeSimulationEnvMock = vi.fn()
const stopSimulationMock = vi.fn()
const getProjectMock = vi.fn()
const getGraphDataMock = vi.fn()
const getTaskStatusMock = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { simulationId: 'sim_1' },
  }),
  useRouter: () => ({
    push: pushMock,
  }),
}))

vi.mock('../../components/GraphPanel.vue', () => ({
  default: {
    name: 'GraphPanelStub',
    template: '<div class="graph-panel-stub"></div>',
  },
}))

vi.mock('../../components/Step2EnvSetup.vue', () => ({
  default: {
    name: 'Step2EnvSetupStub',
    template: '<div class="step2-stub"></div>',
  },
}))

vi.mock('../../api/simulation', () => ({
  getSimulation: (...args) => getSimulationMock(...args),
  stopSimulation: (...args) => stopSimulationMock(...args),
  getEnvStatus: (...args) => getEnvStatusMock(...args),
  closeSimulationEnv: (...args) => closeSimulationEnvMock(...args),
}))

vi.mock('../../api/graph', () => ({
  getProject: (...args) => getProjectMock(...args),
  getGraphData: (...args) => getGraphDataMock(...args),
  getTaskStatus: (...args) => getTaskStatusMock(...args),
}))

describe('SimulationView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    getEnvStatusMock.mockResolvedValue({
      success: true,
      data: { env_alive: false },
    })

    getSimulationMock.mockResolvedValue({
      success: true,
      data: { project_id: 'proj_1' },
    })

    getProjectMock.mockResolvedValue({
      success: true,
      data: {
        project_id: 'proj_1',
        graph_id: 'graph_1',
        graph_build_task_id: 'task_1',
        reading_structure: {
          title: '阅读主线',
        },
        ontology: {
          entity_types: [],
          edge_types: [],
        },
      },
    })

    getTaskStatusMock.mockResolvedValue({
      success: true,
      data: {
        result: {
          contract_version: 'phase1.v1',
          provider: 'local',
          diagnostics: {
            provider: 'local',
            chunk_count: 4,
            processed_chunk_count: 4,
            fallback_graph_applied: false,
          },
          build_outcome: {
            status: 'completed_with_warnings',
            success_ratio: 1,
            warnings: ['阅读骨架状态: generated'],
          },
          reading_structure_status: {
            status: 'generated',
            reason: '',
          },
        },
      },
    })

    getGraphDataMock.mockResolvedValue({
      success: true,
      data: {
        graph_id: 'graph_1',
        node_count: 2,
        edge_count: 1,
        nodes: [],
        edges: [],
      },
    })
  })

  it('restores phase-1 task result and renders the summary strip', async () => {
    const wrapper = mount(SimulationView)

    await flushPromises()

    expect(getSimulationMock).toHaveBeenCalledWith('sim_1')
    expect(getProjectMock).toHaveBeenCalledWith('proj_1')
    expect(getTaskStatusMock).toHaveBeenCalledWith('task_1')
    expect(getGraphDataMock).toHaveBeenCalledWith('graph_1')

    const text = wrapper.text()
    expect(text).toContain('LEGACY SURFACE')
    expect(text).toContain('旧模拟环境搭建流程')
    expect(text).toContain('PHASE-1')
    expect(text).toContain('知识工作台抽取状态')
    expect(text).toContain('Provider · LOCAL')
    expect(text).toContain('构建 · 完成但有告警')
    expect(text).toContain('阅读骨架 · 已生成')
  })
})
