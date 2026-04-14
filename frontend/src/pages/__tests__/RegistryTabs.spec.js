import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// Mock axios service for all tabs
const serviceMock = vi.fn()
vi.mock('../../api/index', () => ({ default: (...args) => serviceMock(...args) }))

// Mock vue-router
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import ThemeTab from '../RegistryPage/tabs/ThemeTab.vue'
import EvolutionTab from '../RegistryPage/tabs/EvolutionTab.vue'
import ReviewTab from '../RegistryPage/tabs/ReviewTab.vue'

describe('ThemeTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    serviceMock.mockImplementation(({ url }) => {
      if (url === '/api/registry/themes') {
        return Promise.resolve({
          data: {
            themes: [
              { theme_id: 'gtheme_1', name: 'AI Safety', status: 'active', concept_entry_ids: ['c1'], source_project_clusters: [{ project_id: 'p1', cluster_id: 'tc_1', cluster_name: 'P1 Cluster' }] },
              { theme_id: 'gtheme_2', name: 'NLP Trends', status: 'active', concept_entry_ids: [], source_project_clusters: [] },
            ],
            total: 2,
          },
        })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders theme list and shows detail on click', async () => {
    const wrapper = mount(ThemeTab)
    await flushPromises()

    expect(wrapper.text()).toContain('AI Safety')
    expect(wrapper.text()).toContain('NLP Trends')

    const btn = wrapper.findAll('.candidate-button').find(b => b.text().includes('AI Safety'))
    await btn.trigger('click')

    expect(wrapper.text()).toContain('Global Theme')
    expect(wrapper.text()).toContain('P1 Cluster')
    expect(wrapper.text()).toContain('c1')
  })

  it('shows empty state when no themes', async () => {
    serviceMock.mockResolvedValue({ data: { themes: [], total: 0 } })
    const wrapper = mount(ThemeTab)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无全局主题')
  })

  it('creates a new theme', async () => {
    serviceMock.mockImplementation(({ url, method }) => {
      if (method === 'get') return Promise.resolve({ data: { themes: [], total: 0 } })
      if (method === 'post') return Promise.resolve({ data: { theme_id: 'new', name: 'New Theme', status: 'active', concept_entry_ids: [], source_project_clusters: [] } })
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(ThemeTab)
    await flushPromises()

    await wrapper.find('.btn-primary').trigger('click')
    await wrapper.find('.form-input').setValue('New Theme')
    const createBtn = wrapper.findAll('.btn-primary').find(b => b.text().includes('创建'))
    await createBtn.trigger('click')
    await flushPromises()

    expect(serviceMock).toHaveBeenCalledWith(expect.objectContaining({ method: 'post' }))
  })
})

describe('EvolutionTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    serviceMock.mockResolvedValue({
      data: {
        events: [
          { event_id: 'e1', event_type: 'created', entity_type: 'concept_entry', entity_id: 'c1', entity_name: 'ML', timestamp: '2026-04-09T12:00:00', project_id: '' },
          { event_id: 'e2', event_type: 'linked', entity_type: 'concept_entry', entity_id: 'c1', entity_name: 'ML', timestamp: '2026-04-09T13:00:00', project_id: 'proj_a' },
        ],
        total: 2,
      },
    })
  })

  it('renders event feed', async () => {
    const wrapper = mount(EvolutionTab)
    await flushPromises()

    expect(wrapper.text()).toContain('ML')
    expect(wrapper.text()).toContain('创建')
    expect(wrapper.text()).toContain('链接')
  })

  it('shows empty state', async () => {
    serviceMock.mockResolvedValue({ data: { events: [], total: 0 } })
    const wrapper = mount(EvolutionTab)
    await flushPromises()
    expect(wrapper.text()).toContain('暂无演化事件')
  })
})

describe('ReviewTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    serviceMock.mockImplementation(({ url }) => {
      if (url.includes('/stats')) {
        return Promise.resolve({ data: { total: 2, by_status: { open: 1, resolved: 1 }, by_priority: {}, by_entity_type: {} } })
      }
      if (url.includes('/review/tasks')) {
        return Promise.resolve({
          data: {
            tasks: [
              { task_id: 't1', entity_type: 'concept_entry', entity_id: 'c1', entity_name: 'ML', action_required: 'confirm_link', status: 'open', priority: 'high', note: '', resolution: '' },
              { task_id: 't2', entity_type: 'concept_entry', entity_id: 'c2', entity_name: 'DL', action_required: 'review_merge', status: 'resolved', priority: 'normal', note: '', resolution: 'approved' },
            ],
            total: 2,
          },
        })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders stats and task list', async () => {
    const wrapper = mount(ReviewTab)
    await flushPromises()

    expect(wrapper.text()).toContain('总任务')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('ML')
    expect(wrapper.text()).toContain('DL')
  })

  it('shows task detail on click', async () => {
    const wrapper = mount(ReviewTab)
    await flushPromises()

    const row = wrapper.findAll('.task-row').find(r => r.text().includes('ML'))
    await row.trigger('click')

    expect(wrapper.text()).toContain('Review Task')
    expect(wrapper.text()).toContain('confirm_link')
  })
})
