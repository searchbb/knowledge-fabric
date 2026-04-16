// ThemeHub (ThemeViewPage) live/demo roundtrip.
//
// We mock the BACKEND API module (services/api/themeApi), not the
// dataClient — that way the real dataClient performs real dispatch
// based on appMode, the live path hits the mock, and the demo path
// runs the real fixtures.

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listGlobalThemesMock = vi.fn()
const getThemeHubViewMock = vi.fn()
const getOrphansMock = vi.fn()

vi.mock('../../services/api/themeApi', () => ({
  // Reads (what the live provider wraps):
  listGlobalThemes: (...a) => listGlobalThemesMock(...a),
  getThemeHubView: (...a) => getThemeHubViewMock(...a),
  getOrphans: (...a) => getOrphansMock(...a),
  getThemePanorama: vi.fn(),
  // Writes (stay on the live path — just stub):
  createGlobalTheme: vi.fn(),
  promoteCandidate: vi.fn(),
  rejectCandidate: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/themes', params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import ThemeViewPage from '../ThemeViewPage/ThemeViewPage.vue'
import { setMode } from '../../runtime/appMode'

enableAutoUnmount(afterEach)

const liveThemes = [
  {
    theme_id: 'theme_live_1',
    name: 'Live Theme One',
    description: 'live desc 1',
    status: 'active',
    keywords: ['alpha'],
    concept_memberships: [],
  },
  {
    theme_id: 'theme_live_2',
    name: 'Live Theme Two',
    description: 'live desc 2',
    status: 'candidate',
    keywords: ['beta'],
    concept_memberships: [],
  },
]

describe('ThemeViewPage (hub)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    listGlobalThemesMock.mockResolvedValue({ data: { themes: liveThemes } })
    getOrphansMock.mockResolvedValue({ data: { orphans: [] } })
    getThemeHubViewMock.mockResolvedValue({ data: { theme: {}, members: [], stats: {} } })
  })

  it('renders live themes on mount via dataClient → live provider → api mock', async () => {
    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()
    expect(listGlobalThemesMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Live Theme One')
    expect(wrapper.text()).toContain('Live Theme Two')
  })

  it('demo mode uses real demo provider — live api mock is NOT called', async () => {
    setMode('demo')
    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()
    expect(listGlobalThemesMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toMatch(/(可观测性三支柱|Agentic 可靠性模式|RAG 评估指标)/)
  })

  it('roundtrip live → demo → live swaps list contents each way', async () => {
    setMode('live')
    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Live Theme One')
    const liveCalls = listGlobalThemesMock.mock.calls.length
    expect(liveCalls).toBe(1)

    setMode('demo')
    await flushPromises()
    expect(wrapper.text()).not.toContain('Live Theme One')
    expect(wrapper.text()).toMatch(/(可观测性三支柱|RAG 评估指标)/)
    expect(listGlobalThemesMock.mock.calls.length).toBe(liveCalls) // untouched

    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('Live Theme One')
    expect(listGlobalThemesMock.mock.calls.length).toBe(liveCalls + 1)
  })
})
