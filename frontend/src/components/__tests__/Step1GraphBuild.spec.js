import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Step1GraphBuild from '../Step1GraphBuild.vue'

const pushMock = vi.fn()
const createSimulationMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}))

vi.mock('../../api/simulation', () => ({
  createSimulation: (...args) => createSimulationMock(...args),
}))

const baseProps = {
  currentPhase: 2,
  projectData: {
    project_id: 'proj_1',
    graph_id: 'graph_1',
    ontology: {
      entity_types: [],
      edge_types: [],
    },
  },
  buildProgress: {
    result: {
      provider: 'local',
      build_outcome: { status: 'completed' },
      reading_structure_status: { status: 'generated' },
    },
  },
  graphData: {
    node_count: 3,
    edge_count: 1,
  },
  systemLogs: [],
}

describe('Step1GraphBuild phase-1 completion CTA prototype', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createSimulationMock.mockResolvedValue({
      success: true,
      data: {
        simulation_id: 'sim_1',
      },
    })
  })

  it('offers both workspace and legacy experimental paths', async () => {
    const wrapper = mount(Step1GraphBuild, {
      props: baseProps,
    })

    expect(wrapper.text()).toContain('进入 Phase 2 工作台')
    expect(wrapper.text()).toContain('旧环境搭建流程（实验）')

    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'Workspace',
      params: {
        projectId: 'proj_1',
        section: 'article',
      },
    })

    await buttons[1].trigger('click')

    expect(createSimulationMock).toHaveBeenCalledWith({
      project_id: 'proj_1',
      graph_id: 'graph_1',
      enable_twitter: true,
      enable_reddit: true,
    })
    expect(pushMock).toHaveBeenCalledWith({
      name: 'Simulation',
      params: { simulationId: 'sim_1' },
    })
  })
})
