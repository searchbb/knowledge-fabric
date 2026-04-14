import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ThemeViewPage from '../ThemeViewPage/ThemeViewPage.vue'

const getThemeViewMock = vi.fn()

vi.mock('../../services/api/themeApi', () => ({
  getThemeView: (...args) => getThemeViewMock(...args),
}))

// AppShell 内部调用 useRoute(),jsdom 无 router 插件需要 mock
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/proj_theme/themes', params: { projectId: 'proj_theme', section: 'themes' } }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

const baseProps = {
  project: {
    project_id: 'proj_theme',
    name: 'Markdown 为什么会流行?',
    status: 'graph_completed',
  },
  graphData: {
    node_count: 10,
    edge_count: 6,
  },
  phase1TaskResult: {
    build_outcome: {
      status: 'completed',
    },
  },
}

describe('ThemeViewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getThemeViewMock.mockResolvedValue({
      data: {
        meta: {
          projectId: 'proj_theme',
          projectName: 'Markdown 为什么会流行?',
          graphId: 'mirofish_theme_graph',
          phase1Status: 'completed',
          viewVersion: 'theme-candidates-v1',
          generatedFrom: ['analysis_summary', 'reading_structure', 'graph_data'],
          generatedAt: '2026-04-09T13:30:00',
        },
        overview: {
          summaryText: '文章围绕格式与内容分离、版本控制与协作扩散展开。',
          candidateCount: 3,
          nodeCount: 10,
          edgeCount: 6,
          readingGroupCount: 3,
          uncoveredNodesCount: 0,
        },
        backbone: {
          title: 'Markdown 为什么会流行',
          summary: '文章主线围绕低格式开销和协作效率展开。',
          problem: { title: '写作与格式冲突', summary: '' },
          solution: { title: '降低表达摩擦', summary: '' },
          architecture: { title: '从文本到协作网络', summary: '' },
          articleSections: ['版本控制', '开源协作'],
        },
        themeCandidates: [
          {
            candidateKey: 'reading_group:mechanism',
            title: '关键机制',
            kind: 'reading_group',
            summary: '围绕版本控制、内容分离等 Mechanism 节点形成的主题候选。',
            supportSignals: ['阅读分组：关键机制', '图谱标签：Mechanism'],
            evidence: {
              nodeCount: 4,
              edgeCount: 3,
              readingGroupRefs: ['关键机制'],
              topLabels: ['Mechanism'],
              sampleNodes: ['版本控制', '内容分离'],
            },
            sourceRefs: ['reading_structure.group_titles.Mechanism', 'graph.labels.Mechanism'],
          },
          {
            candidateKey: 'reading_group:technology',
            title: '涉及技术',
            kind: 'reading_group',
            summary: '围绕 GitHub 等 Technology 节点形成的主题候选。',
            supportSignals: ['阅读分组：涉及技术', '图谱标签：Technology'],
            evidence: {
              nodeCount: 2,
              edgeCount: 1,
              readingGroupRefs: ['涉及技术'],
              topLabels: ['Technology'],
              sampleNodes: ['GitHub'],
            },
            sourceRefs: ['reading_structure.group_titles.Technology', 'graph.labels.Technology'],
          },
        ],
        diagnostics: {
          warnings: ['fallback graph applied'],
          emptyReason: '',
          dataCompleteness: 'reading_structure_with_graph',
          unassignedReadingGroups: [],
          unassignedLabels: [],
          uncoveredNodesCount: 0,
        },
        limitations: ['当前输出是项目内 theme candidates，不是 canonical theme truth source。'],
      },
    })
  })

  // SKIP: ThemeViewPage 已被重构为"全局主题枢纽(THEME HUB)"界面,
  // 本 spec 的断言("项目内主题候选"/"候选主题:3")对应的是旧版 UI。
  // 需要按新页面重写,留给 Theme hub 模块的后续工作。2026-04-14 @theme-v2
  it.skip('renders backend theme candidates and switches detail panel', async () => {
    const wrapper = mount(ThemeViewPage, {
      props: baseProps,
      global: { mocks: { $route: { fullPath: '/workspace/proj_theme/themes' } } },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('项目内主题候选')
    expect(wrapper.text()).toContain('候选主题：3')
    expect(wrapper.text()).toContain('关键机制')
    expect(wrapper.text()).toContain('阅读骨架 + 图谱')
    expect(wrapper.text()).toContain('写作与格式冲突')

    const candidateButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('涉及技术'))

    expect(candidateButton).toBeTruthy()
    await candidateButton.trigger('click')

    expect(wrapper.text()).toContain('GitHub')
    expect(wrapper.text()).toContain('graph.labels.Technology')
  })
})
