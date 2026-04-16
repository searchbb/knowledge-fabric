import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Auto-unmount after each test. Otherwise orphan components from earlier
// tests keep their watch(appMode, ...) subscriptions alive and re-trigger
// the workbench loader when later tests flip the mode.
enableAutoUnmount(afterEach)

import WorkspacePage from '../WorkspacePage/WorkspacePage.vue'
import { setMode } from '../../runtime/appMode'

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
    window.localStorage.clear()
    setMode('live')
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

  it('loads demo fixture project in demo mode without calling live loader', async () => {
    routeState.params.section = 'article'
    routeState.params.projectId = 'demo-observability-platform'
    setMode('demo')

    const wrapper = mount(WorkspacePage, {
      global: {
        mocks: {
          $route: { fullPath: '/workspace/demo-observability-platform/article' },
        },
      },
    })
    await flushPromises()

    // Demo mode should NOT reach the live loader at all.
    expect(loadProjectWorkbenchStateMock).not.toHaveBeenCalled()
    // Demo fixture project name surfaces in the page header.
    expect(wrapper.text()).toContain('可观测性平台调研')
  })

  it('degrades gracefully (no white screen) when demo has no fixture for this projectId', async () => {
    routeState.params.section = 'article'
    routeState.params.projectId = 'proj_not_in_demo'
    setMode('demo')

    const wrapper = mount(WorkspacePage, {
      global: {
        mocks: {
          $route: { fullPath: '/workspace/proj_not_in_demo/article' },
        },
      },
    })
    await flushPromises()

    // Error state card is shown, not a blank page.
    expect(wrapper.text()).toContain('加载失败')
    expect(wrapper.text()).toContain('Demo data not available')
  })

  it('flips data source on appMode change — live → demo → live roundtrip', async () => {
    routeState.params.section = 'article'
    routeState.params.projectId = 'demo-observability-platform'
    setMode('live')

    const wrapper = mount(WorkspacePage, {
      global: {
        mocks: {
          $route: { fullPath: '/workspace/demo-observability-platform/article' },
        },
      },
    })
    await flushPromises()
    expect(loadProjectWorkbenchStateMock).toHaveBeenCalledTimes(1)
    // Header shows live-loader project name.
    expect(wrapper.text()).toContain('Phase 2 Demo')

    setMode('demo')
    await flushPromises()
    // Demo fixture now; live loader was NOT called again.
    expect(loadProjectWorkbenchStateMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('可观测性平台调研')

    setMode('live')
    await flushPromises()
    // Back to live — loader called again (count becomes 2).
    expect(loadProjectWorkbenchStateMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Phase 2 Demo')
  })
})
