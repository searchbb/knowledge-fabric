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

// Reusable builder so individual tests can override one endpoint while
// leaving the default empty-queue behaviour in place for the others.
function makeMockRouter(overrides = {}) {
  return async ({ url, method = 'get' }) => {
    const m = String(method).toLowerCase()
    const key = `${m} ${url}`
    if (overrides[key] !== undefined) {
      const stub = overrides[key]
      return typeof stub === 'function' ? stub() : stub
    }
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
    // Default discover stats/list endpoints: empty queue. Individual
    // tests override via `overrides` to exercise populated / error paths.
    if (m === 'get' && url === '/api/auto/discover-jobs/stats') {
      return { success: true, data: { total: 0, by_status: {} } }
    }
    if (m === 'get' && url.startsWith('/api/auto/discover-jobs?')) {
      return { success: true, data: { jobs: [], total: 0 } }
    }
    if (m === 'get' && url.startsWith('/api/auto/discover-jobs/recent-skips')) {
      return {
        success: true,
        data: { skips: [], stats: { total: 0, by_kind: {} }, window_seconds: 3600 },
      }
    }
    throw new Error(`unhandled ${m} ${url}`)
  }
}

function configureLiveMocks() {
  serviceMock.mockImplementation(makeMockRouter())
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

  it('renders NotePasteCard below the URL input', async () => {
    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()
    // Exercises mounting of the paste-entry card on the same page.
    expect(wrapper.find('[data-test="note-editor"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="note-title"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="note-submit"]').exists()).toBe(true)
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

  // ---------------------------------------------------------------------
  // Discover V2 panel (P1.4 / the "UI shows 0 when API returned 1" bug).
  //
  // Regression intent: the axios wrapper in api/index.js auto-unwraps
  // `response.data` via its response interceptor, so callers receive the
  // backend envelope directly as {success, data, …}. An early version
  // of this page did `res.data.data`, which silently produced `undefined
  // || 0 = 0` and stuck the panel at zero even when the backend returned
  // real counts. These tests drive the full fetch→interceptor→ref→DOM
  // chain so any future regression re-introducing the double-unwrap (or
  // any similar silent read error) fails loudly.
  // ---------------------------------------------------------------------

  it('renders discover queue counts from /api/auto/discover-jobs/stats', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: {
            total: 4,
            by_status: { pending: 1, running: 2, completed: 1 },
          },
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    // Discover content now lives inside <CollapsibleCard>. We forward
    // `data-test="discover-card"` onto its <details> root so tests can
    // scope assertions to this card only.
    const discoverCard = wrapper.find('[data-test="discover-card"]')
    expect(discoverCard.exists()).toBe(true)
    expect(discoverCard.text()).toContain('共 4 条')

    // Each dc-metric row is "<label><value>" — we want explicit
    // label/value pairing so a silent zero on a wrong key fails.
    const pairs = discoverCard.findAll('.dc-metric').map((row) => ({
      label: row.find('.dc-label').text(),
      value: row.find('.dc-value').text(),
    }))
    expect(pairs).toEqual([
      { label: '待办', value: '1' },
      { label: '运行中', value: '2' },
      { label: '完成', value: '1' },
      { label: '部分完成', value: '0' },
      { label: '失败', value: '0' },
    ])
  })

  it('treats the backend envelope as res.data, not res.data.data (interceptor regression)', async () => {
    // Spec the exact shape the real backend + interceptor produces.
    // If anyone re-adds `res.data.data`, this test will see total=0
    // and the assertion below will fail.
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 7, by_status: { running: 7 } },
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const discoverCard = wrapper.find('[data-test="discover-card"]')
    expect(discoverCard.text()).toContain('共 7 条')
    // Spot-check the specific counter so a wrong by_status key path
    // (e.g. reading res.data.data.by_status) would miss the 7.
    const running = discoverCard
      .findAll('.dc-metric')
      .find((r) => r.find('.dc-label').text() === '运行中')
    expect(running.find('.dc-value').text()).toBe('7')
  })

  it('stays at 0 safely when discover stats endpoint is unavailable', async () => {
    // Network / 404 must not crash the page or flash NaN — the panel is
    // informational and should silently hold its last good value.
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': () => {
          throw new Error('discover service unavailable')
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    expect(wrapper.find('[data-test="discover-card"]').text()).toContain('共 0 条')
    // Rest of the page still renders (URL queue, mode card, etc.).
    expect(wrapper.text()).toContain('live.example.com/a')
  })

  it('manual run-once posts to /api/auto/discover-jobs/run-once and surfaces the outcome', async () => {
    const calls = []
    serviceMock.mockImplementation(async (config) => {
      calls.push(config)
      const router = makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { pending: 1 } },
        },
        'post /api/auto/discover-jobs/run-once': {
          success: true,
          data: {
            executed: true,
            outcome: {
              job_id: 'djob_abc123',
              status: 'completed',
              stats: { discovered: 5 },
              error: null,
            },
          },
        },
      })
      return router(config)
    })

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    // The body-level "手动运行一条" button was removed to avoid
    // duplicating the always-visible summary button; drive the flow
    // through the summary-extra "运行一条" button instead. Scope to the
    // Discover card so an unrelated button with the same text can't be
    // picked up accidentally.
    const discoverCard = wrapper.find('[data-test="discover-card"]')
    const runBtn = discoverCard
      .findAll('button')
      .find((b) => b.text().includes('运行一条'))
    expect(runBtn).toBeTruthy()
    expect(runBtn.attributes('disabled')).toBeUndefined()

    await runBtn.trigger('click')
    await flushPromises()

    // POST hit the right endpoint.
    const postCall = calls.find(
      (c) =>
        String(c.method).toLowerCase() === 'post' &&
        c.url === '/api/auto/discover-jobs/run-once',
    )
    expect(postCall).toBeTruthy()

    // Outcome surfaced in the UI.
    expect(discoverCard.text()).toContain('djob_abc123')
    expect(discoverCard.text()).toContain('completed')
    expect(discoverCard.text()).toContain('5')
  })

  it('run-once on empty queue reports "队列为空" without surfacing an error', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        // Pending > 0 so the button enables and we can exercise the flow.
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { pending: 1 } },
        },
        // But by the time run-once fires, the worker already drained it.
        'post /api/auto/discover-jobs/run-once': {
          success: true,
          data: { executed: false },
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const discoverCard = wrapper.find('[data-test="discover-card"]')
    const runBtn = discoverCard
      .findAll('button')
      .find((b) => b.text().includes('运行一条'))
    await runBtn.trigger('click')
    await flushPromises()

    expect(discoverCard.text()).toContain('队列为空')
  })

  // ---------------------------------------------------------------------
  // Per-job retry / cancel (P4 productization cut 1).
  //
  // The panel surfaces attention-worthy jobs (partial/failed/cancelled
  // get a retry button; pending gets cancel; running is read-only). The
  // flows below make sure:
  //   - the attention list filters out "completed" noise
  //   - each row shows the right buttons for its status
  //   - clicking retry / cancel POSTs to the right endpoint and refreshes
  //   - backend 409 conflicts surface a readable error text
  // ---------------------------------------------------------------------

  function jobFactory(overrides = {}) {
    return {
      job_id: 'djob_test123',
      status: 'partial',
      theme_id: 'gtheme_x',
      trigger_project_id: 'proj_x',
      new_entry_ids: ['canon_a', 'canon_b'],
      attempt_count: 1,
      max_attempts: 3,
      created_at: '2026-04-17T10:00:00',
      started_at: '2026-04-17T10:00:01',
      finished_at: '2026-04-17T10:02:00',
      heartbeat_at: '2026-04-17T10:02:00',
      last_error: null,
      stats: { discovered: 2 },
      ...overrides,
    }
  }

  it('attention list hides completed, keeps partial/failed/cancelled/pending/running', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 5, by_status: { completed: 1, partial: 1, failed: 1, pending: 1, running: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [
              jobFactory({ job_id: 'djob_comp', status: 'completed' }),
              jobFactory({ job_id: 'djob_part', status: 'partial', last_error: 'chunk 1 failed: timeout' }),
              jobFactory({ job_id: 'djob_fail', status: 'failed', last_error: 'bailian down' }),
              jobFactory({ job_id: 'djob_pend', status: 'pending' }),
              jobFactory({ job_id: 'djob_run', status: 'running' }),
            ],
            total: 5,
          },
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const rows = wrapper.findAll('.discover-job-row')
    // 4 attention-worthy jobs; completed is filtered out.
    expect(rows.length).toBe(4)
    const listedIds = rows.map((r) => r.find('.dj-id').text())
    expect(listedIds).not.toContain('djob_comp')
    // Shortened form — long enough to be unique but elided.
    expect(listedIds.some((s) => s.startsWith('djob_part'))).toBe(true)
  })

  it('partial / failed rows expose a retry button, pending exposes cancel, running exposes neither', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 4, by_status: { partial: 1, failed: 1, pending: 1, running: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [
              jobFactory({ job_id: 'djob_partial', status: 'partial' }),
              jobFactory({ job_id: 'djob_failed', status: 'failed' }),
              jobFactory({ job_id: 'djob_pending', status: 'pending' }),
              jobFactory({ job_id: 'djob_running', status: 'running' }),
            ],
            total: 4,
          },
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const rows = wrapper.findAll('.discover-job-row')
    const byId = Object.fromEntries(
      rows.map((r) => [r.find('.dj-id').text().replace('…', ''), r]),
    )

    // Retry on partial.
    const partialButtons = byId['djob_partial']
      .findAll('button')
      .map((b) => b.text())
    expect(partialButtons).toContain('重试')
    expect(partialButtons).not.toContain('取消')

    // Retry on failed.
    const failedButtons = byId['djob_failed']
      .findAll('button')
      .map((b) => b.text())
    expect(failedButtons).toContain('重试')

    // Cancel on pending.
    const pendingButtons = byId['djob_pending']
      .findAll('button')
      .map((b) => b.text())
    expect(pendingButtons).toContain('取消')
    expect(pendingButtons).not.toContain('重试')

    // Running: neither — the worker owns it.
    const runningButtons = byId['djob_running']
      .findAll('button')
      .map((b) => b.text())
    expect(runningButtons).toEqual([])
  })

  it('clicking retry POSTs to /retry and refreshes the list', async () => {
    const calls = []
    serviceMock.mockImplementation(async (config) => {
      calls.push(config)
      return makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { partial: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [jobFactory({ job_id: 'djob_retry_me', status: 'partial' })],
            total: 1,
          },
        },
        'post /api/auto/discover-jobs/djob_retry_me/retry': {
          success: true,
          data: jobFactory({ job_id: 'djob_retry_me', status: 'pending' }),
        },
      })(config)
    })

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const retryBtn = wrapper
      .findAll('.discover-job-row')[0]
      .findAll('button')
      .find((b) => b.text().includes('重试'))
    expect(retryBtn).toBeTruthy()
    await retryBtn.trigger('click')
    await flushPromises()

    const postCall = calls.find(
      (c) =>
        String(c.method).toLowerCase() === 'post' &&
        c.url === '/api/auto/discover-jobs/djob_retry_me/retry',
    )
    expect(postCall).toBeTruthy()

    // After retry, both stats and jobs list get re-fetched.
    const refetches = calls.filter(
      (c) =>
        String(c.method).toLowerCase() === 'get' &&
        (c.url === '/api/auto/discover-jobs/stats' ||
          c.url === '/api/auto/discover-jobs?limit=20'),
    )
    // At least one of each re-fetch happened after the POST.
    const postIdx = calls.indexOf(postCall)
    const refetchAfter = refetches.filter((c) => calls.indexOf(c) > postIdx)
    expect(refetchAfter.length).toBeGreaterThanOrEqual(2)

    // UI surfaces a success note.
    expect(wrapper.text()).toContain('已重新入队')
  })

  it('clicking cancel on a pending job POSTs to /cancel', async () => {
    const calls = []
    serviceMock.mockImplementation(async (config) => {
      calls.push(config)
      return makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { pending: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [jobFactory({ job_id: 'djob_cancel_me', status: 'pending', last_error: null })],
            total: 1,
          },
        },
        'post /api/auto/discover-jobs/djob_cancel_me/cancel': {
          success: true,
          data: jobFactory({ job_id: 'djob_cancel_me', status: 'cancelled' }),
        },
      })(config)
    })

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const cancelBtn = wrapper
      .findAll('.discover-job-row')[0]
      .findAll('button')
      .find((b) => b.text().includes('取消'))
    expect(cancelBtn).toBeTruthy()
    await cancelBtn.trigger('click')
    await flushPromises()

    const postCall = calls.find(
      (c) =>
        String(c.method).toLowerCase() === 'post' &&
        c.url === '/api/auto/discover-jobs/djob_cancel_me/cancel',
    )
    expect(postCall).toBeTruthy()
    // Scope to the Discover card: "已取消" also appears in the errored
    // bucket when a cancelled URL is surfaced, so a whole-wrapper match
    // would collide.
    expect(wrapper.find('[data-test="discover-card"]').text()).toContain('已取消')
  })

  it('retry failure surfaces a readable error without crashing the panel', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { partial: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [jobFactory({ job_id: 'djob_conflict', status: 'partial' })],
            total: 1,
          },
        },
        'post /api/auto/discover-jobs/djob_conflict/retry': () => {
          throw new Error('Request failed with status code 409')
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const retryBtn = wrapper
      .findAll('.discover-job-row')[0]
      .findAll('button')
      .find((b) => b.text().includes('重试'))
    await retryBtn.trigger('click')
    await flushPromises()

    // Scope to the Discover card: the errored URL bucket has its own
    // "一键重试" header action and per-row retry notes, so the raw
    // string could collide on the whole wrapper.
    expect(wrapper.find('[data-test="discover-card"]').text()).toContain('重试失败')
  })

  // ---------------------------------------------------------------------
  // Throttle alert (P4 audit follow-up 2026-04-17)
  // ---------------------------------------------------------------------

  it('renders throttle alert when recent-skips reports non-zero total', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/recent-skips?within_seconds=3600&limit=5': {
          success: true,
          data: {
            stats: { total: 3, by_kind: { theme_cooldown: 2, daily_budget: 1 } },
            skips: [
              {
                skipped_at: '2026-04-17T22:10:11',
                reason: 'theme cooldown: 11 in the last hour (cap=10)',
                kind: 'theme_cooldown',
                theme_id: 'gtheme_hot',
              },
            ],
            window_seconds: 3600,
          },
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const alert = wrapper.find('.discover-skip-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('过去 1 小时有 3 次调度被拦截')
    expect(alert.text()).toContain('主题冷却 2')
    expect(alert.text()).toContain('日预算 1')
    expect(alert.text()).toContain('cooldown')
  })

  it('hides throttle alert when no recent skips', async () => {
    // Default mock already returns total=0 → alert should be absent.
    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()
    expect(wrapper.find('.discover-skip-alert').exists()).toBe(false)
  })

  // ---------------------------------------------------------------------
  // Job detail drawer (P4 step 9).
  // ---------------------------------------------------------------------

  it('clicking a job row opens the drawer and fetches detail', async () => {
    const calls = []
    serviceMock.mockImplementation(async (config) => {
      calls.push(config)
      const router = makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { partial: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [jobFactory({ job_id: 'djob_detail_me', status: 'partial' })],
            total: 1,
          },
        },
        'get /api/auto/discover-jobs/djob_detail_me': {
          success: true,
          data: jobFactory({
            job_id: 'djob_detail_me',
            status: 'partial',
            stats: {
              discovered: 3,
              llm_chunks_total: 2,
              llm_chunks_succeeded: 1,
              llm_chunks_failed: 1,
              errors: ['chunk 0 failed: boom'],
              funnel: {
                raw_pairs: 20,
                after_incremental_gate: 10,
                after_cross_article: 8,
                after_dedupe_filter: 6,
                final: 6,
                sent_to_llm: 6,
                llm_accepted: 4,
                deduped_on_commit: 1,
                committed: 3,
              },
            },
          }),
        },
      })
      return router(config)
    })

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    // Row is present; click it.
    const row = wrapper.find('.discover-job-row')
    expect(row.exists()).toBe(true)
    await row.trigger('click')
    await flushPromises()

    // Drawer open; funnel and chunk info visible.
    const drawer = wrapper.find('.job-drawer-panel')
    expect(drawer.exists()).toBe(true)
    const text = drawer.text()
    expect(text).toContain('djob_detail_me')
    expect(text).toContain('候选漏斗')
    // Funnel numbers rendered.
    expect(text).toContain('20')  // raw_pairs
    expect(text).toContain('8')   // after_cross_article
    expect(text).toContain('最终写入')
    // Chunks row surfaced too.
    expect(text).toContain('分片与重试')
    expect(text).toContain('chunk 0 failed: boom')

    // Detail fetch actually happened.
    const fetched = calls.find(
      (c) =>
        String(c.method).toLowerCase() === 'get' &&
        c.url === '/api/auto/discover-jobs/djob_detail_me',
    )
    expect(fetched).toBeTruthy()
  })

  it('clicking retry inside a row does not open the drawer (stopPropagation)', async () => {
    const calls = []
    serviceMock.mockImplementation(async (config) => {
      calls.push(config)
      const router = makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { partial: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [jobFactory({ job_id: 'djob_no_leak', status: 'partial' })],
            total: 1,
          },
        },
        'post /api/auto/discover-jobs/djob_no_leak/retry': {
          success: true,
          data: jobFactory({ job_id: 'djob_no_leak', status: 'pending' }),
        },
      })
      return router(config)
    })

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    const retryBtn = wrapper
      .find('.discover-job-row')
      .findAll('button')
      .find((b) => b.text().includes('重试'))
    await retryBtn.trigger('click')
    await flushPromises()

    // No drawer opened: nobody GET'd the detail URL.
    const detailCall = calls.find(
      (c) =>
        String(c.method).toLowerCase() === 'get' &&
        c.url === '/api/auto/discover-jobs/djob_no_leak',
    )
    expect(detailCall).toBeFalsy()
    // Drawer DOM absent.
    expect(wrapper.find('.job-drawer-panel').exists()).toBe(false)
  })

  it('closing the drawer clears state', async () => {
    serviceMock.mockImplementation(
      makeMockRouter({
        'get /api/auto/discover-jobs/stats': {
          success: true,
          data: { total: 1, by_status: { partial: 1 } },
        },
        'get /api/auto/discover-jobs?limit=20': {
          success: true,
          data: {
            jobs: [jobFactory({ job_id: 'djob_close_me', status: 'partial' })],
            total: 1,
          },
        },
        'get /api/auto/discover-jobs/djob_close_me': {
          success: true,
          data: jobFactory({ job_id: 'djob_close_me', status: 'partial' }),
        },
      }),
    )

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    await wrapper.find('.discover-job-row').trigger('click')
    await flushPromises()
    expect(wrapper.find('.job-drawer-panel').exists()).toBe(true)

    await wrapper.find('.jd-close').trigger('click')
    await flushPromises()
    expect(wrapper.find('.job-drawer-panel').exists()).toBe(false)
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

  it('sorts all four buckets newest-first', async () => {
    const router = makeMockRouter({
      'get /api/auto/pending-urls': {
        data: {
          pending: [
            { url_fingerprint: 'a', url: 'https://old.example/a', created_at: '2026-04-10T00:00:00' },
            { url_fingerprint: 'b', url: 'https://new.example/b', created_at: '2026-04-18T00:00:00' },
          ],
          in_flight: [
            { url_fingerprint: 'c', url: 'https://c', claimed_at: '2026-04-19T00:00:00' },
            { url_fingerprint: 'd', url: 'https://d', claimed_at: '2026-04-20T00:00:00' },
          ],
          processed: [
            { url_fingerprint: 'e', url: 'https://e', finished_at: '2026-04-15T00:00:00' },
            { url_fingerprint: 'f', url: 'https://f', finished_at: '2026-04-20T00:00:00' },
          ],
          errored: [
            { url_fingerprint: 'g', url: 'https://err-old', finished_at: '2026-04-10T00:00:00', error: 'x' },
            { url_fingerprint: 'h', url: 'https://err-new', finished_at: '2026-04-20T00:00:00', error: 'y' },
          ],
        },
      },
    })
    serviceMock.mockImplementation(router)
    setMode('live')

    const wrapper = mount(AutoPipelinePage, {
      global: { mocks: { $route: { fullPath: '/workspace/auto' } } },
    })
    await flushPromises()

    // Task 6 (2026-04-20): 待处理 stays as <article class="bucket-card">
    // (primary actionable queue); the other three are wrapped in
    // <CollapsibleCard> and scoped via `data-test`.
    const pending = wrapper.find('.bucket-card .bucket-list')
    const errored = wrapper.find('[data-test="bucket-errored"] .bucket-list')
    const inFlight = wrapper.find('[data-test="bucket-in-flight"] .bucket-list')
    const processed = wrapper.find('[data-test="bucket-processed"] .bucket-list')
    expect(pending.text()).toMatch(/new\.example\/b[\s\S]*old\.example\/a/)
    expect(errored.text()).toMatch(/err-new[\s\S]*err-old/)
    expect(inFlight.text()).toMatch(/https:\/\/d[\s\S]*https:\/\/c/)
    expect(processed.text()).toMatch(/https:\/\/f[\s\S]*https:\/\/e/)
  })
})
