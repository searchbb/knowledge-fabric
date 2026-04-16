import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getReviewViewMock = vi.fn()
const putReviewDecisionMock = vi.fn()
const deleteReviewDecisionMock = vi.fn()

vi.mock('../../services/api/reviewApi', () => ({
  getReviewView: (...args) => getReviewViewMock(...args),
  putReviewDecision: (...args) => putReviewDecisionMock(...args),
  deleteReviewDecision: (...args) => deleteReviewDecisionMock(...args),
}))

import ReviewPage from '../ReviewPage/ReviewPage.vue'
import { reviewStore } from '../../stores/reviewStore'
import { setMode } from '../../runtime/appMode'
import { PROJECT_OBSERVABILITY } from '../../data/providers/demo/fixtures/entities'

enableAutoUnmount(afterEach)

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

function liveFixture() {
  return {
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
          title: 'LIVEONLY-归一本篇核心概念到 canonical',
          kind: 'concept',
          kindLabel: '概念归一',
          severity: 'high',
          severityLabel: '高风险',
          status: 'pending',
          statusLabel: '未处理',
          summary: 'Live-mode summary',
          sourceLabel: '来自图谱节点快照与阅读骨架',
          confidenceLabel: '原型候选',
          documentLabel: 'MiroFish Prototype Project',
          rationale: 'Phase 2 核心。',
          evidence: [],
          suggestions: [],
          sourceSnippets: [],
          subgraph: { caption: '', nodes: [], edges: [] },
          crossArticleCandidates: [],
          focusTerms: [],
          manualNote: '',
          assistantPreview: '',
          lastDecisionLabel: '',
        },
        {
          id: 'relation-check',
          title: 'LIVEONLY-确认关系建议是否值得人工复核',
          kind: 'relation',
          kindLabel: '关系确认',
          severity: 'high',
          severityLabel: '高风险',
          status: 'pending',
          statusLabel: '未处理',
          summary: '关系确认型任务。',
          evidence: [],
          suggestions: [],
          sourceSnippets: [],
          subgraph: { caption: '', nodes: [], edges: [] },
          crossArticleCandidates: [],
          focusTerms: [],
          manualNote: '',
          assistantPreview: '',
          lastDecisionLabel: '',
        },
      ],
    },
  }
}

describe('ReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    getReviewViewMock.mockResolvedValue(liveFixture())
    putReviewDecisionMock.mockResolvedValue({ data: {} })
    deleteReviewDecisionMock.mockResolvedValue({ data: {} })
    // Reset store error from any previous test's demo-block trigger.
    reviewStore.error = ''
  })

  it('renders richer evidence and accepts manual guidance', async () => {
    const wrapper = mount(ReviewPage, { props: baseProps })
    await flushPromises()

    expect(wrapper.text()).toContain('校验视图原型')
    expect(wrapper.text()).toContain('LIVEONLY-归一本篇核心概念到 canonical')
    expect(wrapper.text()).toContain('LIVEONLY-确认关系建议是否值得人工复核')

    const questionButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '存疑')

    expect(questionButton).toBeTruthy()
    await questionButton.trigger('click')
    // In live mode, the store persists via the mocked api.
    expect(putReviewDecisionMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('已标记存疑')

    const noteInput = wrapper.find('textarea')
    await noteInput.setValue('把 Markdown 视为工具层 canonical，机制不要直接合并。')

    expect(wrapper.text()).toContain('把 Markdown 视为工具层 canonical')
  })

  // TC-E2E-28: live/demo roundtrip.
  it('live→demo→live roundtrip swaps the review queue each direction', async () => {
    const demoProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: PROJECT_OBSERVABILITY },
    }
    const wrapper = mount(ReviewPage, { props: demoProps })
    await flushPromises()
    expect(wrapper.text()).toContain('LIVEONLY-归一本篇核心概念到 canonical')
    expect(getReviewViewMock).toHaveBeenCalledTimes(1)

    // Flip to demo — the demo fixture for PROJECT_OBSERVABILITY has
    // a cardinality task and an OpenTelemetry relation task.
    setMode('demo')
    await flushPromises()
    expect(wrapper.text()).not.toContain('LIVEONLY-归一本篇核心概念到 canonical')
    expect(wrapper.text()).toContain('高基数维度合并到 canonical')
    // Demo read did NOT hit the live services/api mock.
    expect(getReviewViewMock).toHaveBeenCalledTimes(1)

    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('LIVEONLY-归一本篇核心概念到 canonical')
    expect(wrapper.text()).not.toContain('高基数维度合并到 canonical')
    expect(getReviewViewMock).toHaveBeenCalledTimes(2)
  })

  // TC-E2E-29: demo-mode write boundary — clicking a decision button
  // must NOT hit the live services/api layer and must NOT mutate the
  // task status (no fake "success" optimistic write).
  it('demo mode blocks decision writes — live API not called, status unchanged', async () => {
    setMode('demo')
    const demoProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: PROJECT_OBSERVABILITY },
    }
    const wrapper = mount(ReviewPage, { props: demoProps })
    await flushPromises()

    // Baseline: first task from demo fixture is pending.
    const firstTask = reviewStore.items[0]
    expect(firstTask).toBeTruthy()
    expect(firstTask.status).toBe('pending')

    // Click the "通过" (approve) decision button.
    const approveButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '通过')
    expect(approveButton).toBeTruthy()
    await approveButton.trigger('click')
    await flushPromises()

    // The live api module must never be touched in demo mode.
    expect(putReviewDecisionMock).not.toHaveBeenCalled()
    expect(deleteReviewDecisionMock).not.toHaveBeenCalled()
    // And the task status must remain pending — no fake success.
    const afterTask = reviewStore.items[0]
    expect(afterTask.status).toBe('pending')
    // Store surfaces the demo-readonly message for the app to show.
    expect(reviewStore.error).toMatch(/Demo 模式只读/)
  })

  // TC-E2E-30: demo degradation when no fixture exists for projectId.
  it('demo mode with unknown projectId surfaces a friendly error', async () => {
    setMode('demo')
    const unknownProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: 'proj_review_unknown' },
    }
    const wrapper = mount(ReviewPage, { props: unknownProps })
    await flushPromises()

    // Store error captured; page doesn't whitescreen.
    expect(reviewStore.error).toMatch(/Demo data not available/)
    // No stale live content left over.
    expect(wrapper.text()).not.toContain('LIVEONLY-归一本篇核心概念到 canonical')
    // Review queue is empty (no items from previous state).
    expect(reviewStore.items.length).toBe(0)
  })
})
