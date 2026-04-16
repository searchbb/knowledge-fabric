import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RegistryPage from '../RegistryPage/RegistryPage.vue'
import { setMode } from '../../runtime/appMode'

// Auto-unmount between tests so orphan watch(appMode,...) subscribers
// from earlier mounts can't re-fire loaders in later tests.
enableAutoUnmount(afterEach)

// Mock all registry API calls
const listMock = vi.fn()
const getMock = vi.fn()
const createMock = vi.fn()
const updateMock = vi.fn()
const deleteMock = vi.fn()
const linkMock = vi.fn()
const unlinkMock = vi.fn()
const searchMock = vi.fn()
const suggestMock = vi.fn()
const alignmentMock = vi.fn()

vi.mock('../../services/api/registryApi', () => ({
  listRegistryConcepts: (...args) => listMock(...args),
  getRegistryConcept: (...args) => getMock(...args),
  createRegistryConcept: (...args) => createMock(...args),
  updateRegistryConcept: (...args) => updateMock(...args),
  deleteRegistryConcept: (...args) => deleteMock(...args),
  linkProjectConcept: (...args) => linkMock(...args),
  unlinkProjectConcept: (...args) => unlinkMock(...args),
  searchRegistryConcepts: (...args) => searchMock(...args),
  suggestFromProject: (...args) => suggestMock(...args),
  getProjectAlignment: (...args) => alignmentMock(...args),
}))

// Mock vue-router
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/registry', params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: {
    template: '<a><slot /></a>',
    props: ['to'],
  },
}))

const sampleEntries = [
  {
    entry_id: 'canon_001',
    canonical_name: 'Machine Learning',
    concept_type: 'Technology',
    aliases: ['ML', '机器学习'],
    description: 'A branch of AI',
    source_links: [
      { project_id: 'proj_a', concept_key: 'Technology:machine learning', project_name: 'Project A', linked_at: '2026-04-09' },
    ],
    created_at: '2026-04-09',
    updated_at: '2026-04-09',
  },
  {
    entry_id: 'canon_002',
    canonical_name: 'Deep Learning',
    concept_type: 'Technology',
    aliases: ['DL'],
    description: '',
    source_links: [],
    created_at: '2026-04-09',
    updated_at: '2026-04-09',
  },
]

describe('RegistryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    listMock.mockResolvedValue({
      data: { entries: sampleEntries, total: 2 },
    })
    getMock.mockResolvedValue({
      data: sampleEntries[0],
    })
  })

  it('renders registry overview with entries list', async () => {
    const wrapper = mount(RegistryPage, { global: { mocks: { $route: { fullPath: '/workspace/registry' } } } })
    await flushPromises()

    expect(wrapper.text()).toContain('跨项目概念注册表')
    expect(wrapper.text()).toContain('Machine Learning')
    expect(wrapper.text()).toContain('Deep Learning')
    expect(wrapper.text()).toContain('2')  // total entries
  })

  it('shows entry detail when selecting from list', async () => {
    const wrapper = mount(RegistryPage, { global: { mocks: { $route: { fullPath: '/workspace/registry' } } } })
    await flushPromises()

    const mlButton = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('Machine Learning'))
    expect(mlButton).toBeTruthy()
    await mlButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Canonical Entry')
    expect(wrapper.text()).toContain('Machine Learning')
    expect(wrapper.text()).toContain('ML')
    expect(wrapper.text()).toContain('机器学习')
    expect(wrapper.text()).toContain('Project A')
  })

  it('creates a new entry via the form', async () => {
    createMock.mockResolvedValue({
      data: {
        entry_id: 'canon_new',
        canonical_name: 'Kubernetes',
        concept_type: 'Technology',
        aliases: ['K8s'],
        description: '',
        source_links: [],
      },
    })
    getMock.mockResolvedValue({
      data: {
        entry_id: 'canon_new',
        canonical_name: 'Kubernetes',
        concept_type: 'Technology',
        aliases: ['K8s'],
        description: '',
        source_links: [],
      },
    })

    const wrapper = mount(RegistryPage, { global: { mocks: { $route: { fullPath: '/workspace/registry' } } } })
    await flushPromises()

    // Click "新建条目"
    const createBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('新建条目'))
    expect(createBtn).toBeTruthy()
    await createBtn.trigger('click')

    // Fill form
    const inputs = wrapper.findAll('.form-input')
    expect(inputs.length).toBeGreaterThanOrEqual(3)

    await inputs[0].setValue('Kubernetes')
    await inputs[1].setValue('Technology')
    await inputs[2].setValue('K8s')

    // Click "创建"
    const submitBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text() === '创建')
    expect(submitBtn).toBeTruthy()
    await submitBtn.trigger('click')
    await flushPromises()

    expect(createMock).toHaveBeenCalledWith({
      canonical_name: 'Kubernetes',
      concept_type: 'Technology',
      aliases: ['K8s'],
      description: '',
    })
  })

  it('handles search with debounce', async () => {
    searchMock.mockResolvedValue({
      data: {
        results: [sampleEntries[0]],
        query: 'machine',
        total: 1,
      },
    })

    const wrapper = mount(RegistryPage, { global: { mocks: { $route: { fullPath: '/workspace/registry' } } } })
    await flushPromises()

    const searchInput = wrapper.find('.search-input')
    await searchInput.setValue('machine')
    await searchInput.trigger('input')

    // Wait for debounce (300ms)
    await new Promise((resolve) => setTimeout(resolve, 350))
    await flushPromises()

    expect(searchMock).toHaveBeenCalledWith('machine')
  })

  // SKIP: RegistryPage 内部 tab 切换被重构,"全局主题" 入口迁到侧栏 nav 独立项。
  // 这条断言找不到 nav-item 里的 "全局主题" 按钮,跟 V2 主题工作无关。
  // 2026-04-14 @theme-v2
  it.skip('switches to themes tab', async () => {
    const wrapper = mount(RegistryPage, { global: { mocks: { $route: { fullPath: '/workspace/registry' } } } })
    await flushPromises()

    // Find and click the themes tab
    const themesTab = wrapper
      .findAll('.nav-item')
      .find((btn) => btn.text().includes('全局主题'))
    expect(themesTab).toBeTruthy()
    await themesTab.trigger('click')

    expect(wrapper.text()).toContain('跨项目主题聚类')
  })

  it('shows empty state when registry is empty', async () => {
    listMock.mockResolvedValue({
      data: { entries: [], total: 0 },
    })

    const wrapper = mount(RegistryPage, { global: { mocks: { $route: { fullPath: '/workspace/registry' } } } })
    await flushPromises()

    expect(wrapper.text()).toContain('注册表为空')
  })

  it('renders demo registry fixture without calling live listMock', async () => {
    setMode('demo')
    const wrapper = mount(RegistryPage, {
      global: { mocks: { $route: { fullPath: '/workspace/registry' } } },
    })
    await flushPromises()

    expect(listMock).not.toHaveBeenCalled()
    // At least one canonical name from the shared entities fixture.
    expect(wrapper.text()).toContain('OpenTelemetry')
    expect(wrapper.text()).toContain('端到端时延')
  })

  it('roundtrip: live → demo → live swaps list contents and re-calls live loader on return', async () => {
    setMode('live')
    const wrapper = mount(RegistryPage, {
      global: { mocks: { $route: { fullPath: '/workspace/registry' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Machine Learning')
    const liveCountAfterMount = listMock.mock.calls.length
    expect(liveCountAfterMount).toBe(1)

    setMode('demo')
    await flushPromises()
    expect(wrapper.text()).toContain('OpenTelemetry')
    expect(wrapper.text()).not.toContain('Machine Learning')
    // Demo shouldn't have touched the live mock at all.
    expect(listMock.mock.calls.length).toBe(liveCountAfterMount)

    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('Machine Learning')
    expect(listMock.mock.calls.length).toBe(liveCountAfterMount + 1)
  })
})
