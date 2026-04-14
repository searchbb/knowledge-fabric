import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import EvolutionViewPage from '../EvolutionViewPage/EvolutionViewPage.vue'

const getEvolutionViewMock = vi.fn()

vi.mock('../../services/api/evolutionApi', () => ({
  getEvolutionView: (...args) => getEvolutionViewMock(...args),
}))

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

describe('EvolutionViewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getEvolutionViewMock.mockResolvedValue({
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
            '当前页面基于项目级元数据和当前图谱快照生成。',
            '当前结果不代表历史版本序列，也不代表 concept/theme 的真实时间演化。',
          ],
          confidenceFlags: {
            historicalSeriesAvailable: false,
            nodeTimestampConsistency: 'partial',
            crossProjectComparisonSupported: false,
          },
        },
        nextCapabilitiesGap: {
          missingCapabilities: ['per-project snapshot history', 'review audit history'],
          recommendedNextStep: '先补 project snapshot persistence 或 audit 历史，再考虑真正的 evolution timeline。',
          readinessLevel: 'snapshot_only',
        },
        diagnostics: {
          warnings: ['fallback graph applied'],
          emptyReason: '',
          dataCompleteness: 'snapshot_with_timestamp_diagnostics',
          timestampSignalAvailable: true,
        },
      },
    })
  })

  it('renders evolution readiness snapshot instead of a fake timeline', async () => {
    const wrapper = mount(EvolutionViewPage, {
      props: baseProps,
    })

    await flushPromises()

    expect(wrapper.text()).toContain('演化就绪度快照')
    expect(wrapper.text()).toContain('快照 + 时间诊断')
    expect(wrapper.text()).toContain('generated')
    expect(wrapper.text()).toContain('per-project snapshot history')
    expect(wrapper.text()).toContain('当前页面基于项目级元数据和当前图谱快照生成。')
    expect(wrapper.text()).toContain('fallback graph applied')
  })
})
