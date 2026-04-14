import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const serviceMock = vi.fn()
vi.mock('../../api/index', () => ({ default: (...args) => serviceMock(...args) }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/overview', params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import OverviewPage from '../OverviewPage/OverviewPage.vue'

describe('OverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
})
