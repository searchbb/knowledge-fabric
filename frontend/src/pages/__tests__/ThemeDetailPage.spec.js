// ThemeDetailPage live/demo roundtrip + degradation.
//
// Mock the API MODULES, not dataClient, so the real dataClient routes
// based on appMode.

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getThemePanoramaMock = vi.fn()
vi.mock('../../services/api/themeApi', () => ({
  getThemePanorama: (...a) => getThemePanoramaMock(...a),
  listGlobalThemes: vi.fn(),
  getThemeHubView: vi.fn(),
  getOrphans: vi.fn(),
  createGlobalTheme: vi.fn(),
  promoteCandidate: vi.fn(),
  rejectCandidate: vi.fn(),
}))

vi.mock('../../services/api/registryApi', () => ({
  discoverCrossRelations: vi.fn(),
  updateCrossRelation: vi.fn(),
  deleteCrossRelation: vi.fn(),
  listRegistryConcepts: vi.fn(),
  getRegistryConcept: vi.fn(),
  listCrossRelations: vi.fn(),
  getCrossRelation: vi.fn(),
  getCrossRelationCounts: vi.fn(),
}))

const routeState = {
  params: { themeId: 'live_theme_1' },
  query: {},
  path: '/workspace/themes/live_theme_1',
}
vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

// Light stub so the sub-component import chain doesn't pull the full
// CrossRelationCard tree.
vi.mock('../../components/CrossRelationCard.vue', () => ({
  default: { template: '<div class="stub-relation-card"><slot /></div>' },
}))

import ThemeDetailPage from '../ThemeDetailPage/ThemeDetailPage.vue'
import { setMode } from '../../runtime/appMode'

enableAutoUnmount(afterEach)

function makeLivePanorama(themeName) {
  return {
    data: {
      theme: {
        theme_id: 'live_theme_1',
        name: themeName,
        description: 'live panorama description',
        keywords: ['live'],
      },
      stats: { concept_count: 2, article_count: 2, relation_count: 0 },
      grouped_concepts: {
        core: [
          {
            entry_id: 'entry_live',
            canonical_name: 'Live Concept',
            concept_type: 'Technology',
            description: 'live concept description',
            source_links: [
              {
                project_id: 'proj_current',
                project_name: 'Current source article',
                concept_key: 'Technology:live concept',
              },
              {
                project_id: 'proj_archive',
                project_name: 'Archive source article with a long title',
                concept_key: 'Technology:live concept',
              },
              {
                project_id: 'proj_hidden',
                project_name: 'Hidden source article',
                concept_key: 'Technology:live concept',
              },
            ],
            role: 'core',
            xrel_count: 0,
            description_degraded: false,
          },
          {
            entry_id: 'entry_other',
            canonical_name: 'Other Concept',
            concept_type: 'Method',
            description: 'other concept description',
            source_links: [
              {
                project_id: 'proj_other',
                project_name: 'Other article',
                concept_key: 'Method:other concept',
              },
            ],
            role: 'core',
            xrel_count: 0,
            description_degraded: false,
          },
        ],
        bridge: [],
        peripheral: [],
      },
      bridge_relations: [],
      suggested_memberships: [],
      silent_failures: {
        xrels_with_partial_source: 0,
        xrels_with_no_readable_source: 0,
        descriptions_degraded: 0,
        concepts_missing_source_links: 0,
        bridge_without_xrels: 0,
      },
      discovery_coverage: { last_run_at: '', discovered: 0 },
    },
  }
}

describe('ThemeDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    routeState.params.themeId = 'live_theme_1'
    routeState.query = {}
    getThemePanoramaMock.mockResolvedValue(makeLivePanorama('Live Theme Alpha'))
  })

  it('renders the live panorama on mount', async () => {
    const wrapper = mount(ThemeDetailPage, {
      global: { mocks: { $route: { fullPath: routeState.path } } },
    })
    await flushPromises()
    expect(getThemePanoramaMock).toHaveBeenCalledWith('live_theme_1')
    expect(wrapper.text()).toContain('Live Theme Alpha')
    expect(wrapper.text()).toContain('Live Concept')
  })

  it('shows compact source article links on concept cards', async () => {
    const wrapper = mount(ThemeDetailPage, {
      global: { mocks: { $route: { fullPath: routeState.path } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('来源文章')
    expect(wrapper.text()).toContain('3 篇')
    expect(wrapper.text()).toContain('Current source article')
    expect(wrapper.text()).toContain('Archive source article with a long title')
    expect(wrapper.text()).toContain('+1')

    const sourceLinks = wrapper.findAll('a.td-source-link')
    expect(sourceLinks.some((link) => link.text() === 'Hidden source article')).toBe(false)
    expect(sourceLinks[0].attributes('href')).toBe(
      '/workspace/proj_current/article?view=reading&focusNode=Technology%3Alive+concept&from=registry',
    )
    expect(sourceLinks[0].attributes('target')).toBe('_blank')
    expect(sourceLinks[0].attributes('rel')).toBe('noopener noreferrer')

    const more = wrapper.find('.td-source-more')
    expect(more.text()).toBe('+1')
    expect(more.attributes('title')).toBe('Hidden source article')
  })

  it('highlights concepts contributed by the current project context', async () => {
    routeState.query = { project_id: 'proj_current', from: 'project-theme-signals' }
    const wrapper = mount(ThemeDetailPage, {
      global: { mocks: { $route: { fullPath: `${routeState.path}?project_id=proj_current` } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('当前文章贡献的概念')
    expect(wrapper.text()).toContain('1 / 2 来自当前文章')
    expect(wrapper.text()).toContain('Current source article')
    expect(wrapper.text()).toContain('Technology:live concept')
    expect(wrapper.text()).toContain('该主题的其他全局概念')
    expect(wrapper.text()).toContain('Other Concept')
  })

  it('demo mode loads a real fixture theme panorama (live mock not called)', async () => {
    routeState.params.themeId = 'theme-observability'
    setMode('demo')
    const wrapper = mount(ThemeDetailPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes/theme-observability' } } },
    })
    await flushPromises()
    expect(getThemePanoramaMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('可观测性三支柱')
  })

  it('degrades gracefully when demo has no fixture for themeId', async () => {
    routeState.params.themeId = 'theme-does-not-exist'
    setMode('demo')
    const wrapper = mount(ThemeDetailPage, {
      global: { mocks: { $route: { fullPath: '/workspace/themes/theme-does-not-exist' } } },
    })
    await flushPromises()
    // Page surfaces an error state instead of crashing.
    expect(wrapper.text()).toMatch(/Demo data not available/)
  })

  it('roundtrip live(valid) → demo(missing) → live(valid) shows right content each way', async () => {
    // live_theme_1 is valid on live; missing on demo (no fixture).
    routeState.params.themeId = 'live_theme_1'
    const wrapper = mount(ThemeDetailPage, {
      global: { mocks: { $route: { fullPath: routeState.path } } },
    })
    await flushPromises()
    expect(getThemePanoramaMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Live Theme Alpha')

    setMode('demo')
    await flushPromises()
    // Live mock stays untouched; demo surfaces degradation message.
    expect(getThemePanoramaMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toMatch(/Demo data not available/)

    setMode('live')
    await flushPromises()
    expect(getThemePanoramaMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Live Theme Alpha')
  })
})
