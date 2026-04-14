import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspacePage from '../WorkspacePage/WorkspacePage.vue'

const replaceMock = vi.fn()
const pushMock = vi.fn()
const loadProjectWorkbenchStateMock = vi.fn()

const routeState = {
  params: {
    projectId: 'proj_1',
    section: undefined,
  },
  path: '/workspace/proj_1/article',
  query: {},
}

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    replace: replaceMock,
    push: pushMock,
  }),
  RouterLink: {
    name: 'RouterLinkStub',
    template: '<a><slot /></a>',
  },
}))

vi.mock('../../utils/projectWorkbenchState', () => ({
  loadProjectWorkbenchState: (...args) => loadProjectWorkbenchStateMock(...args),
}))

describe('WorkspacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params.projectId = 'proj_1'
    routeState.params.section = undefined

    loadProjectWorkbenchStateMock.mockResolvedValue({
      project: {
        project_id: 'proj_1',
        name: 'Phase 2 Demo',
        status: 'ready',
      },
      graphData: {
        node_count: 3,
        edge_count: 2,
      },
      phase1TaskResult: {
        provider: 'local',
        build_outcome: {
          status: 'completed',
          success_ratio: 1,
        },
      },
    })
  })

  // WorkspacePage 模板里用 $route.fullPath 访问全局属性。
  // vi.mock('vue-router') 只替换了 useRoute 导出,
  // 所以需要在 mount 时单独注入 $route 全局属性。
  const mountOpts = () => ({
    global: {
      mocks: {
        $route: { fullPath: routeState.path || '/workspace/proj_1/article' },
      },
    },
  })

  it('canonicalizes an empty section to the article route', async () => {
    mount(WorkspacePage, mountOpts())

    await flushPromises()

    expect(replaceMock).toHaveBeenCalledWith({
      name: 'Workspace',
      params: {
        projectId: 'proj_1',
        section: 'article',
      },
    })
    expect(loadProjectWorkbenchStateMock).toHaveBeenCalledWith('proj_1')
  })

  it('keeps a valid article section without redirecting', async () => {
    routeState.params.section = 'article'

    mount(WorkspacePage, mountOpts())

    await flushPromises()

    expect(replaceMock).not.toHaveBeenCalled()
    expect(loadProjectWorkbenchStateMock).toHaveBeenCalledWith('proj_1')
  })
})
