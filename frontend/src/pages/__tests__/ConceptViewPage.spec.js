import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ConceptViewPage from '../ConceptViewPage/ConceptViewPage.vue'

const getConceptViewMock = vi.fn()

vi.mock('../../services/api/conceptApi', () => ({
  getConceptView: (...args) => getConceptViewMock(...args),
}))

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

describe('ConceptViewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getConceptViewMock.mockResolvedValue({
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
            displayName: 'Markdown',
            conceptType: 'Topic',
            mentionCount: 2,
            connectedCount: 5,
            sampleEvidence: ['Markdown 强调格式与内容分离。'],
            sourceNodeIds: ['n1', 'n2'],
            status: 'unreviewed',
          },
          {
            key: 'Mechanism:version-control',
            displayName: '版本控制',
            conceptType: 'Mechanism',
            mentionCount: 1,
            connectedCount: 3,
            sampleEvidence: ['关联节点：GitHub'],
            sourceNodeIds: ['n3'],
            status: 'unreviewed',
          },
        ],
      },
    })
  })

  it('renders backend concept summary and switches candidate detail', async () => {
    const wrapper = mount(ConceptViewPage, {
      props: baseProps,
    })

    await flushPromises()

    expect(wrapper.text()).toContain('项目内概念总览')
    expect(wrapper.text()).toContain('候选概念：3')
    expect(wrapper.text()).toContain('Markdown')
    expect(wrapper.text()).toContain('fallback graph applied')
    expect(wrapper.text()).toContain('图谱 + Phase 1 快照')

    const candidateButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('版本控制'))

    expect(candidateButton).toBeTruthy()
    await candidateButton.trigger('click')

    expect(wrapper.text()).toContain('Selected Candidate')
    expect(wrapper.text()).toContain('版本控制')
    expect(wrapper.text()).toContain('关联节点：GitHub')
  })
})
