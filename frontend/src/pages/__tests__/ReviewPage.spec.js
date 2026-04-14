import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ReviewPage from '../ReviewPage/ReviewPage.vue'

const getReviewViewMock = vi.fn()

vi.mock('../../services/api/reviewApi', () => ({
  getReviewView: (...args) => getReviewViewMock(...args),
}))

const baseProps = {
  project: {
    project_id: 'proj_review',
    name: 'MiroFish Prototype Project',
    analysis_summary: '围绕知识工作台 Phase 2 的结构化升级。',
    reading_structure: {
      title: '从单篇抽取走向多文章治理',
    },
  },
  graphData: {
    node_count: 9,
    edge_count: 5,
  },
  phase1TaskResult: {
    provider: 'local',
    diagnostics: {
      chunk_count: 4,
      processed_chunk_count: 4,
      fallback_graph_applied: true,
    },
    build_outcome: {
      status: 'completed_with_warnings',
      warnings: ['阅读骨架状态: generated', 'fallback graph applied'],
    },
    reading_structure_status: {
      status: 'generated',
    },
  },
}

describe('ReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getReviewViewMock.mockResolvedValue({
      data: {
        prototypeMode: true,
        summary: {
          totalCount: 3,
          pendingCount: 3,
          highPriorityCount: 2,
          warningCount: 0,
          graphNodeCount: 9,
          graphEdgeCount: 5,
          articleTextAvailable: true,
          relatedProjectCount: 1,
        },
        phase1Signals: {
          provider: 'local',
          build_outcome: {
            status: 'completed_with_warnings',
            warnings: [],
          },
        },
        items: [
          {
            id: 'concept-alignment',
            title: '归一本篇核心概念到 canonical',
            kind: 'concept',
            kindLabel: '概念归一',
            severity: 'high',
            severityLabel: '高风险',
            status: 'pending',
            statusLabel: '未处理',
            summary: '用当前文章的局部图谱预演 local concept -> canonical 的人工确认入口，不提前绑定真实归一算法。',
            sourceLabel: '来自图谱节点快照与阅读骨架',
            confidenceLabel: '原型候选',
            documentLabel: 'MiroFish Prototype Project',
            rationale: 'Phase 2 的核心不是继续堆单篇抽取，而是让局部概念进入可确认、可写回的全局治理链路。',
            evidence: [
              { label: '单篇图谱节点', value: '9 个节点' },
              { label: '阅读骨架标题', value: '从单篇抽取走向多文章治理' },
            ],
            suggestions: ['将高频局部概念合并到已有 canonical。'],
            sourceSnippets: [
              {
                id: 'snippet-1',
                heading: '版本控制',
                text: 'Markdown 适合 Git 版本控制，适合进入 canonical 与 theme 治理链路。',
                matchedTerms: ['Markdown'],
              },
            ],
            subgraph: {
              caption: '局部子图只展示当前任务最相关的一小圈节点和关系。',
              nodes: [
                { id: 'n1', name: 'Markdown', label: 'Topic', isFocus: true },
                { id: 'n2', name: '版本控制', label: 'Mechanism', isFocus: true },
              ],
              edges: [
                { id: 'e1', source: 'n1', target: 'n2', label: 'ENABLES', fact: 'Markdown 帮助版本控制协作' },
              ],
            },
            crossArticleCandidates: [
              {
                projectId: 'proj_markdown_2',
                name: 'Markdown 在 AI 时代的第二次生命',
                status: 'graph_completed',
                summary: '文章讨论 Markdown 与 AI、人机协作和结构透明性之间的关系。',
                matchedTerms: ['Markdown'],
                reason: '命中 Markdown，适合当作跨文章候选参考。',
              },
            ],
            focusTerms: ['Markdown', '版本控制'],
            manualNote: '',
            assistantPreview: '建议先围绕 Markdown / 版本控制 检查原文片段、局部子图和 Markdown 在 AI 时代的第二次生命 的候选信息，再决定是合并、关联还是暂不处理。',
            lastDecisionLabel: '',
          },
          {
            id: 'relation-check',
            title: '确认关系建议是否值得人工复核',
            kind: 'relation',
            kindLabel: '关系确认',
            severity: 'high',
            severityLabel: '高风险',
            status: 'pending',
            statusLabel: '未处理',
            summary: '关系确认型任务需要在 review 页中占一个明确位置。',
            evidence: [],
            suggestions: [],
            sourceSnippets: [],
            subgraph: { caption: '', nodes: [], edges: [] },
            crossArticleCandidates: [],
            focusTerms: ['关系确认'],
            manualNote: '',
            assistantPreview: '建议先围绕关系确认检查原文片段、局部子图和当前单篇证据的候选信息，再决定是合并、关联还是暂不处理。',
            lastDecisionLabel: '',
          },
          {
            id: 'theme-assignment',
            title: '确认主题归属是否成立',
            kind: 'theme',
            kindLabel: '主题归属',
            severity: 'low',
            severityLabel: '低风险',
            status: 'pending',
            statusLabel: '未处理',
            summary: '用阅读骨架和分析摘要预演 theme / cluster 的人工治理入口。',
            evidence: [],
            suggestions: [],
            sourceSnippets: [],
            subgraph: { caption: '', nodes: [], edges: [] },
            crossArticleCandidates: [],
            focusTerms: ['主题归属'],
            manualNote: '',
            assistantPreview: '建议先围绕主题归属检查原文片段、局部子图和当前单篇证据的候选信息，再决定是合并、关联还是暂不处理。',
            lastDecisionLabel: '',
          },
        ],
      },
    })
  })

  it('renders richer evidence and accepts manual guidance', async () => {
    const wrapper = mount(ReviewPage, {
      props: baseProps,
    })

    await flushPromises()

    expect(wrapper.text()).toContain('校验视图原型')
    expect(wrapper.text()).toContain('归一本篇核心概念到 canonical')
    expect(wrapper.text()).toContain('确认关系建议是否值得人工复核')
    expect(wrapper.text()).toContain('原文片段')
    expect(wrapper.text()).toContain('局部子图')
    expect(wrapper.text()).toContain('Markdown 在 AI 时代的第二次生命')

    const questionButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '存疑')

    expect(questionButton).toBeTruthy()
    await questionButton.trigger('click')

    expect(wrapper.text()).toContain('已标记存疑')

    const noteInput = wrapper.find('textarea')
    await noteInput.setValue('把 Markdown 视为工具层 canonical，机制不要直接合并。')

    expect(wrapper.text()).toContain('把 Markdown 视为工具层 canonical')
  })
})
