import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ArticleViewPage from '../ArticleViewPage/ArticleViewPage.vue'

enableAutoUnmount(afterEach)

const replaceMock = vi.fn()
const routeState = {
  query: {
    view: 'reading',
    focusNode: 'Problem:agent',
  },
}

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ replace: replaceMock }),
  RouterLink: {
    name: 'RouterLinkStub',
    template: '<a><slot /></a>',
    props: ['to'],
  },
}))

const GraphPanelStub = {
  name: 'GraphPanel',
  template: `
    <div class="graph-panel-stub">
      <button type="button" class="maximize-trigger" @click="$emit('toggle-maximize')">maximize</button>
      <button type="button" class="view-trigger" @click="$emit('view-change', 'graph')">view</button>
      <button
        type="button"
        class="node-select-trigger"
        @click="$emit('node-select', { key: 'Method:FDE 模式', uuid: 'uuid-fde', name: 'FDE 模式', labels: ['Method'], readingSectionLabel: '关键方法', summary: 'FDE 模式 summary' })"
      >node</button>
    </div>
  `,
  props: [
    'graphData',
    'loading',
    'currentPhase',
    'initialView',
    'readingStructure',
    'schemaEntityTypes',
    'schemaRelationTypes',
    'focusNodeKey',
    'fromSource',
    'domain',
  ],
}

const ArticleRawPanelStub = {
  name: 'ArticleRawPanel',
  template: '<div class="article-raw-panel-stub">{{ focusTarget?.name }}</div>',
  props: ['projectId', 'focusTarget', 'autoScroll'],
}

describe('ArticleViewPage', () => {
  const baseProps = {
    project: {
      project_id: 'proj_1',
      name: 'Project One',
      status: 'graph_completed',
      reading_structure: {},
      ontology: { entity_types: [], edge_types: [] },
    },
    graphData: {
      nodes: [{ name: 'agent', labels: ['Problem'] }],
      edges: [],
      node_count: 1,
      edge_count: 0,
    },
    phase1TaskResult: {
      build_outcome: { status: 'completed', success_ratio: 1 },
    },
  }

  beforeEach(() => {
    replaceMock.mockClear()
    routeState.query = {
      view: 'reading',
      focusNode: 'Problem:agent',
    }
  })

  function mountArticleView() {
    return mount(ArticleViewPage, {
      props: baseProps,
      global: {
        stubs: {
          GraphPanel: GraphPanelStub,
          ArticleRawPanel: ArticleRawPanelStub,
          RouterLink: { template: '<a><slot /></a>', props: ['to'] },
          'router-link': { template: '<a><slot /></a>', props: ['to'] },
        },
      },
    })
  }

  it('keeps normal article graph routes embedded by default', () => {
    const wrapper = mountArticleView()

    expect(wrapper.find('.graph-wrapper').classes()).not.toContain('graph-wrapper--maximized')
  })

  it('defaults source article focus routes from the registry to a maximized graph', () => {
    routeState.query = {
      view: 'reading',
      focusNode: 'Problem:agent',
      from: 'registry',
    }

    const wrapper = mountArticleView()

    expect(wrapper.find('.graph-wrapper').classes()).toContain('graph-wrapper--maximized')
    expect(wrapper.find('.article-maximized-workspace').exists()).toBe(true)
    expect(wrapper.findComponent(ArticleRawPanelStub).exists()).toBe(true)
    expect(wrapper.findComponent(ArticleRawPanelStub).props('autoScroll')).toBe(true)
    expect(wrapper.findComponent(ArticleRawPanelStub).props('focusTarget')).toMatchObject({
      nodeKey: 'Problem:agent',
      name: 'agent',
      labels: ['Problem'],
    })
  })

  it('does not show the raw companion for ordinary graph routes', () => {
    routeState.query = {
      view: 'graph',
    }

    const wrapper = mountArticleView()

    expect(wrapper.find('.graph-wrapper').classes()).not.toContain('graph-wrapper--with-raw')
    expect(wrapper.find('.article-maximized-workspace').exists()).toBe(false)
    expect(wrapper.findComponent(ArticleRawPanelStub).exists()).toBe(false)
  })

  it('updates the raw companion focus when GraphPanel selects another node', async () => {
    routeState.query = {
      view: 'reading',
      focusNode: 'Problem:agent',
      from: 'registry',
    }

    const wrapper = mountArticleView()
    await wrapper.find('.node-select-trigger').trigger('click')

    expect(wrapper.findComponent(ArticleRawPanelStub).props('focusTarget')).toMatchObject({
      nodeKey: 'Method:FDE 模式',
      uuid: 'uuid-fde',
      name: 'FDE 模式',
      labels: ['Method'],
      readingSectionLabel: '关键方法',
    })
  })

  it('toggles the graph wrapper maximized state and notifies the graph to resize', async () => {
    const resizeSpy = vi.fn()
    window.addEventListener('resize', resizeSpy)

    const wrapper = mountArticleView()

    expect(wrapper.find('.graph-wrapper').classes()).not.toContain('graph-wrapper--maximized')

    await wrapper.find('.maximize-trigger').trigger('click')
    expect(wrapper.find('.graph-wrapper').classes()).toContain('graph-wrapper--maximized')
    expect(resizeSpy).toHaveBeenCalledTimes(1)

    await wrapper.find('.maximize-trigger').trigger('click')
    expect(wrapper.find('.graph-wrapper').classes()).not.toContain('graph-wrapper--maximized')
    expect(resizeSpy).toHaveBeenCalledTimes(2)

    window.removeEventListener('resize', resizeSpy)
  })

  it('lets users restore a registry source article graph after it opens maximized', async () => {
    routeState.query = {
      view: 'reading',
      focusNode: 'Problem:agent',
      from: 'registry',
    }
    const resizeSpy = vi.fn()
    window.addEventListener('resize', resizeSpy)

    const wrapper = mountArticleView()

    expect(wrapper.find('.graph-wrapper').classes()).toContain('graph-wrapper--maximized')

    await wrapper.find('.maximize-trigger').trigger('click')
    expect(wrapper.find('.graph-wrapper').classes()).not.toContain('graph-wrapper--maximized')
    expect(resizeSpy).toHaveBeenCalledTimes(1)

    window.removeEventListener('resize', resizeSpy)
  })
})
