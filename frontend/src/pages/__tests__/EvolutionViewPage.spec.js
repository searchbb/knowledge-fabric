import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getEvolutionViewMock = vi.fn()

vi.mock('../../services/api/evolutionApi', () => ({
  getEvolutionView: (...args) => getEvolutionViewMock(...args),
}))

import EvolutionViewPage from '../EvolutionViewPage/EvolutionViewPage.vue'
import { setMode } from '../../runtime/appMode'
import { PROJECT_OBSERVABILITY } from '../../data/providers/demo/fixtures/entities'

enableAutoUnmount(afterEach)

const baseProps = {
  project: {
    project_id: 'proj_evolution',
    name: 'Markdown 为什么会流行?',
    created_at: '2026-04-08T08:55:00',
    updated_at: '2026-04-08T09:30:00',
  },
  graphData: {
    node_count: 8,
    edge_count: 5,
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
        projectId: 'proj_evolution',
        projectName: 'Markdown 为什么会流行?',
        graphId: 'mirofish_evolution_graph',
        phase1Status: 'completed_with_warnings',
        viewVersion: 'evolution-snapshot-v1',
        generatedFrom: ['project_metadata', 'phase1_task_result', 'graph_data', 'graph_created_at'],
        generatedAt: '2026-04-08T09:30:00',
      },
      projectOverview: {
        createdAt: '2026-04-08T08:55:00',
        updatedAt: '2026-04-08T09:30:00',
        hasGraph: true,
        graphNodeCount: 8,
        graphEdgeCount: 5,
        hasReadingStructure: true,
        hasAnalysisSummary: true,
      },
      knowledgeAssetSnapshot: {
        readingStructureStatus: 'generated',
        analysisSummaryStatus: 'available',
        graphStatus: 'available',
        availableViews: ['article', 'concept', 'theme', 'review', 'evolution'],
        evidenceCounts: {
          nodes: 8,
          edges: 5,
          readingGroupsCount: 4,
          warningsCount: 1,
        },
      },
      traceabilityAndSignalQuality: {
        supportsTimeOrdering: 'limited',
        timeSignals: {
          projectCreatedAt: '2026-04-08T08:55:00',
          projectUpdatedAt: '2026-04-08T09:30:00',
          nodeCreatedAtCoverage: 'partial',
          edgeCreatedAtCoverage: 'partial',
        },
        derivationNotes: [
          '当前页面基于 LIVEONLY-MiroFish 项目级元数据生成。',
        ],
        confidenceFlags: {
          historicalSeriesAvailable: false,
          nodeTimestampConsistency: 'partial',
          crossProjectComparisonSupported: false,
        },
      },
      nextCapabilitiesGap: {
        missingCapabilities: ['LIVEONLY-per-project snapshot history'],
        recommendedNextStep: '先补 project snapshot persistence。',
        readinessLevel: 'snapshot_only',
      },
      diagnostics: {
        warnings: ['fallback graph applied'],
        emptyReason: '',
        dataCompleteness: 'snapshot_with_timestamp_diagnostics',
        timestampSignalAvailable: true,
      },
    },
  }
}

describe('EvolutionViewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    getEvolutionViewMock.mockResolvedValue(liveFixture())
  })

  it('renders evolution readiness snapshot instead of a fake timeline', async () => {
    const wrapper = mount(EvolutionViewPage, { props: baseProps })
    await flushPromises()

    expect(wrapper.text()).toContain('演化就绪度快照')
    expect(wrapper.text()).toContain('快照 + 时间诊断')
    expect(wrapper.text()).toContain('generated')
    expect(wrapper.text()).toContain('LIVEONLY-per-project snapshot history')
    expect(wrapper.text()).toContain('当前页面基于 LIVEONLY-MiroFish 项目级元数据生成。')
    expect(wrapper.text()).toContain('fallback graph applied')
  })

  // TC-E2E-25: live/demo roundtrip.
  it('live→demo→live roundtrip swaps timeline-like snapshot each direction', async () => {
    const demoProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: PROJECT_OBSERVABILITY },
    }
    const wrapper = mount(EvolutionViewPage, { props: demoProps })
    await flushPromises()
    expect(wrapper.text()).toContain('LIVEONLY-per-project snapshot history')
    expect(getEvolutionViewMock).toHaveBeenCalledTimes(1)

    // Flip to demo — fixture's derivationNotes string lands on screen.
    setMode('demo')
    await flushPromises()
    expect(wrapper.text()).not.toContain('LIVEONLY-per-project snapshot history')
    expect(wrapper.text()).toMatch(/demo 数据来自本地 fixture/)
    expect(getEvolutionViewMock).toHaveBeenCalledTimes(1)

    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('LIVEONLY-per-project snapshot history')
    expect(wrapper.text()).not.toMatch(/demo 数据来自本地 fixture/)
    expect(getEvolutionViewMock).toHaveBeenCalledTimes(2)
  })

  // TC-E2E-26: demo degradation when no fixture exists for projectId.
  it('demo mode with unknown projectId surfaces a friendly error', async () => {
    setMode('demo')
    const unknownProps = {
      ...baseProps,
      project: { ...baseProps.project, project_id: 'proj_evolution_unknown' },
    }
    const wrapper = mount(EvolutionViewPage, { props: unknownProps })
    await flushPromises()

    // The live-only string must not linger from before the flip.
    expect(wrapper.text()).not.toContain('LIVEONLY-per-project snapshot history')
    // Store error is surfaced; page doesn't whitescreen.
    expect(wrapper.text()).toMatch(/Demo data not available/)
  })
})
