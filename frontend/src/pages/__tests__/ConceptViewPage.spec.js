import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// The page is backed by conceptStore → dataClient.getConceptView →
// live provider (which wraps services/api/conceptApi) OR demo provider
// (which reads fixtures directly). We mock the live API for
// determinism and let the real demo fixture run so we exercise the
// full dispatch path.
const getConceptViewMock = vi.fn()

vi.mock('../../services/api/conceptApi', () => ({
  getConceptView: (...args) => getConceptViewMock(...args),
  putConceptDecision: vi.fn(),
  deleteConceptDecision: vi.fn(),
  postConceptMergeSuggest: vi.fn(),
  postConceptNormalize: vi.fn(),
}))

import ConceptViewPage from '../ConceptViewPage/ConceptViewPage.vue'
import { setMode } from '../../runtime/appMode'
import { PROJECT_OBSERVABILITY } from '../../data/providers/demo/fixtures/entities'

enableAutoUnmount(afterEach)

const baseProps = {
  project: {
    project_id: 'proj_concept',
    name: 'Markdown 为什么会流行?',
    status: 'graph_completed',
  },
  graphData: {
    node_count: 12,
    edge_count: 8,
  },
  phase1TaskResult: {
    build_outcome: {
      status: 'completed_with_warnings',
    },
  },
}

function liveFixture() {
  return {
    data: {
      meta: {
        projectId: 'proj_concept',
        projectName: 'Markdown 为什么会流行?',
        graphId: 'mirofish_graph',
        phase1Status: 'completed_with_warnings',
        sourceScope: 'project_graph',
        generatedAt: '2026-04-09T12:00:00',
      },
      summary: {
        nodeCount: 12,
        edgeCount: 8,
        typedNodeCount: 10,
        candidateConceptCount: 3,
        relationCount: 8,
        warningsCount: 1,
      },
      diagnostics: {
        warnings: ['fallback graph applied'],
        emptyReason: '',
        dataCompleteness: 'graph_with_phase1_snapshot',
        typeCounts: [
          { type: 'Topic', count: 1 },
          { type: 'Mechanism', count: 1 },
        ],
      },
      candidateConcepts: [
        {
          key: 'Topic:markdown',
          displayName: 'LiveOnly-Markdown',
          conceptType: 'Topic',
          mentionCount: 2,
          connectedCount: 5,
          sampleEvidence: ['Markdown 强调格式与内容分离。'],
          sourceNodeIds: ['n1', 'n2'],
          status: 'unreviewed',
        },
        {
          key: 'Mechanism:version-control',
          displayName: 'LiveOnly-版本控制',
          conceptType: 'Mechanism',
          mentionCount: 1,
          connectedCount: 3,
          sampleEvidence: ['关联节点：GitHub'],
          sourceNodeIds: ['n3'],
          status: 'unreviewed',
        },
      ],
    },
  }
}

describe('ConceptViewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    getConceptViewMock.mockResolvedValue(liveFixture())
  })

  it('renders backend concept summary and switches candidate detail', async () => {
    const wrapper = mount(ConceptViewPage, { props: baseProps })
    await flushPromises()

    expect(wrapper.text()).toContain('项目内概念总览')
    expect(wrapper.text()).toContain('候选概念：3')
    expect(wrapper.text()).toContain('LiveOnly-Markdown')
    expect(wrapper.text()).toContain('fallback graph applied')
    expect(wrapper.text()).toContain('图谱 + Phase 1 快照')

    const candidateButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('LiveOnly-版本控制'))

    expect(candidateButton).toBeTruthy()
    await candidateButton.trigger('click')

    expect(wrapper.text()).toContain('Selected Candidate')
    expect(wrapper.text()).toContain('LiveOnly-版本控制')
    expect(wrapper.text()).toContain('关联节点：GitHub')
  })

  // TC-E2E-21: live/demo roundtrip at the page level.
  it('live→demo→live roundtrip swaps candidate content each direction', async () => {
    // Start in live with a unique live candidate name.
    const demoProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: PROJECT_OBSERVABILITY },
    }
    const wrapper = mount(ConceptViewPage, { props: demoProps })
    await flushPromises()
    expect(wrapper.text()).toContain('LiveOnly-Markdown')
    expect(getConceptViewMock).toHaveBeenCalledTimes(1)

    // Flip to demo — watch(appMode, ...) reloads via demo provider.
    setMode('demo')
    await flushPromises()
    // Live-only label must be gone — page must not show stale live content.
    expect(wrapper.text()).not.toContain('LiveOnly-Markdown')
    // And an observability-fixture concept must now appear.
    expect(wrapper.text()).toContain('OpenTelemetry')
    // Demo path must NOT call the live services/api mock.
    expect(getConceptViewMock).toHaveBeenCalledTimes(1)

    // Flip back to live — watch triggers a re-fetch.
    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('LiveOnly-Markdown')
    expect(wrapper.text()).not.toContain('OpenTelemetry')
    expect(getConceptViewMock).toHaveBeenCalledTimes(2)
  })

  // TC-E2E-22: selected detail re-hydrates after mode flip instead of
  // keeping the previous mode's selection data on screen.
  it('selected candidate detail re-hydrates after mode flip', async () => {
    const demoProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: PROJECT_OBSERVABILITY },
    }
    const wrapper = mount(ConceptViewPage, { props: demoProps })
    await flushPromises()

    // Pick a non-first candidate in live so stale-detail bug would show.
    const versionBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('LiveOnly-版本控制'))
    await versionBtn.trigger('click')
    expect(wrapper.text()).toContain('LiveOnly-版本控制')

    setMode('demo')
    await flushPromises()
    // Selected detail must reflect demo fixture, not the live candidate.
    expect(wrapper.text()).not.toContain('LiveOnly-版本控制')
    expect(wrapper.text()).toContain('OpenTelemetry')
  })

  // TC-E2E-23: demo degradation when no fixture exists.
  it('demo mode with unknown projectId surfaces a friendly error', async () => {
    setMode('demo')
    const unknownProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: 'proj_concept_unknown' },
    }
    const wrapper = mount(ConceptViewPage, { props: unknownProps })
    await flushPromises()

    // Error card is visible. Store captured the provider's "Demo data
    // not available" throw.
    expect(wrapper.text()).toContain('概念视图加载失败')
    expect(wrapper.text()).toMatch(/Demo data not available/)
    // Candidate list is cleared — no stale rows from a previous view.
    expect(wrapper.text()).not.toContain('LiveOnly-Markdown')
  })
})
