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
const runGovernanceScanMock = vi.fn()
const getGovernanceRequestMock = vi.fn()

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
  // Governance (new):
  runGovernanceScan: (...a) => runGovernanceScanMock(...a),
  getGovernanceRequest: (...a) => getGovernanceRequestMock(...a),
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
    // Governance mocks — default to no pending request
    getGovernanceRequestMock.mockResolvedValue({ data: { pending: false, request: null } })
    runGovernanceScanMock.mockResolvedValue({
      data: { merge_scan: { merged: [] }, promotion_scan: { promoted: [] } },
    })
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

  // -----------------------------------------------------------------------
  // Governance scan button (Tests I–L)
  // -----------------------------------------------------------------------

  it('(I) renders the governance scan button in the topbar', async () => {
    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('治理扫描')
  })

  it('(J) button shows scanning label while scan is in flight', async () => {
    // Never resolves during the test → stays in scanning state
    runGovernanceScanMock.mockReturnValue(new Promise(() => {}))

    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()

    // Find the governance scan button and click it
    const btn = wrapper.findAll('button').find(b => b.text().includes('治理扫描'))
    expect(btn).toBeDefined()
    await btn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('扫描中')
  })

  it('(K) shows result banner with merge/promote counts after scan', async () => {
    // merged: array of merge-pair descriptors (length = # merges)
    // promoted: items must have { action: 'promoted' } — component filters by this field
    runGovernanceScanMock.mockResolvedValue({
      data: {
        merge_scan: { merged: ['pair_a'], review_queue: [] },
        promotion_scan: { promoted: [{ action: 'promoted', theme_id: 't1' }] },
      },
    })

    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()

    const btn = wrapper.findAll('button').find(b => b.text().includes('治理扫描'))
    await btn.trigger('click')
    await flushPromises()

    const text = wrapper.text()
    // scanMsg: "治理完成：合并 1 对主题，晋升 1 个候选，新增 0 个待审项"
    expect(text).toContain('治理完成')
    expect(text).toMatch(/合并\s*1/)
    expect(text).toMatch(/晋升\s*1/)
  })

  it('(L) shows pending-request banner when backend reports a pending request', async () => {
    getGovernanceRequestMock.mockResolvedValue({
      data: {
        pending: true,
        request: {
          requested: true,
          status: 'pending',
          requested_at: '2026-04-16T10:00:00',
          requested_reason: 'post_drain',
        },
      },
    })

    const wrapper = mount(ThemeViewPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes' } } },
    })
    await flushPromises()

    // Component renders: "有一次待执行的治理扫描（来源：post_drain，时间：...）"
    expect(wrapper.text()).toMatch(/待执行的治理扫描/)
  })
})
