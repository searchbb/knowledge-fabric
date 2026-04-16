import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Without this, mounted components from earlier tests stay alive and
// their watch(appMode, ...) callbacks fire on later setMode() calls,
// inflating the service-mock counters in unrelated tests.
enableAutoUnmount(afterEach)

const serviceMock = vi.fn()
vi.mock('../../api/index', () => ({ default: (...args) => serviceMock(...args) }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/overview', params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import OverviewPage from '../OverviewPage/OverviewPage.vue'
import { setMode } from '../../runtime/appMode'

describe('OverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    serviceMock.mockResolvedValue({
      data: {
        projects: [
          {
            project_id: 'proj_a', project_name: 'Project A', status: 'graph_completed',
            updated_at: '2026-04-09', concept_count: 10, accepted_concept_count: 5,
            linked_concept_count: 3, alignment_coverage: 0.6,
            theme_cluster_count: 2, pending_review_count: 1, evolution_event_count: 8,
          },
        ],
        project_count: 1,
        global_stats: { registry_entries: 12, global_themes: 3, pending_reviews: 1, total_evolution_events: 42 },
      },
    })
  })

  it('renders global stats and project table', async () => {
    const wrapper = mount(OverviewPage)
    await flushPromises()

    expect(wrapper.text()).toContain('项目总览')
    expect(wrapper.text()).toContain('12')  // registry entries
    expect(wrapper.text()).toContain('3')   // global themes
    expect(wrapper.text()).toContain('Project A')
    expect(wrapper.text()).toContain('60%')  // alignment coverage
  })

  it('shows empty state', async () => {
    serviceMock.mockResolvedValue({
      data: { projects: [], project_count: 0, global_stats: { registry_entries: 0, global_themes: 0, pending_reviews: 0, total_evolution_events: 0 } },
    })
    const wrapper = mount(OverviewPage)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无项目')
  })

  it('renders demo fixture data in demo mode without calling the live service', async () => {
    setMode('demo')
    const wrapper = mount(OverviewPage)
    await flushPromises()

    // Page is populated from the demo fixture, not from the axios mock.
    expect(serviceMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('项目总览')
    // One of the fixture project names — proves fixture actually reached the DOM.
    expect(wrapper.text()).toContain('可观测性平台调研')
    expect(wrapper.text()).toContain('Agentic Workflows 设计笔记')
  })

  it('switches data source when appMode flips — no white screen', async () => {
    setMode('live')
    const wrapper = mount(OverviewPage)
    await flushPromises()
    expect(wrapper.text()).toContain('Project A')
    expect(serviceMock).toHaveBeenCalledTimes(1)

    setMode('demo')
    await flushPromises()
    // Content swapped to demo fixture; no crash.
    expect(wrapper.text()).toContain('可观测性平台调研')
    expect(wrapper.text()).not.toContain('Project A')

    setMode('live')
    await flushPromises()
    // Back to live; live service called again.
    expect(wrapper.text()).toContain('Project A')
    expect(serviceMock).toHaveBeenCalledTimes(2)
  })
})
