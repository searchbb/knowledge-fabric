// AutoPipelinePage — live/demo roundtrip, degradation, write-gate.
//
// The page has three read endpoints (pending-urls / graph-tasks /
// llm-mode) plus various write-action buttons. We mock the live axios
// service so the live provider can be driven deterministically, and
// let the real demo provider run (it just reads fixture JSON).

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const serviceMock = vi.fn()
vi.mock('../../api/index', () => ({ default: (...args) => serviceMock(...args) }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/workspace/auto' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import AutoPipelinePage from '../AutoPipelinePage/AutoPipelinePage.vue'
import { setMode } from '../../runtime/appMode'

enableAutoUnmount(afterEach)

function configureLiveMocks() {
  // Router calls by endpoint.
  serviceMock.mockImplementation(async ({ url, method = 'get' }) => {
    const m = String(method).toLowerCase()
    if (m === 'get' && url === '/api/auto/pending-urls') {
      return {
        data: {
          pending: [{ url: 'https://live.example.com/a', project_id: 'proj_live', run_id: 'live-1', phase: 'queued', attempt: 0, duration_ms: 0, url_fingerprint: 'fp-live-1', error: '' }],
          in_flight: [],
          processed: [],
          errored: [],
        },
      }
    }
    if (m === 'get' && url === '/api/graph/tasks') return { data: [] }
    if (m === 'get' && url === '/api/config/llm-mode') {
      return { data: { mode: 'local', local_model: 'live-model', local_semaphore: 2, bailian_model: '', bailian_semaphore: 0, bailian_configured: false, updated_at: '', in_flight_count: 0 } }
    }
    throw new Error(`unhandled ${m} ${url}`)
  })
}

describe('AutoPipelinePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    configureLiveMocks()
  })

  it('renders live pending URL on mount', async () => {
    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('live.example.com/a')
  })

  it('demo mode loads real demo fixture without calling live service', async () => {
    setMode('demo')
    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()
    // Live service must NOT be called for any read — all 3 reads go
    // through dataClient → demo provider.
    expect(serviceMock).not.toHaveBeenCalled()
    // Fixture URL from pipeline.js fixture appears somewhere.
    expect(wrapper.text()).toMatch(/demo\.example\.com/)
  })

  it('roundtrip live → demo → live swaps content each way', async () => {
    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('live.example.com')
    const liveHits = serviceMock.mock.calls.length

    setMode('demo')
    await flushPromises()
    expect(wrapper.text()).not.toContain('live.example.com')
    expect(wrapper.text()).toMatch(/demo\.example\.com/)
    // Demo provider did NOT route through serviceMock.
    expect(serviceMock.mock.calls.length).toBe(liveHits)

    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('live.example.com')
    // Three read endpoints re-hit on return.
    expect(serviceMock.mock.calls.length).toBeGreaterThan(liveHits)
  })
})
