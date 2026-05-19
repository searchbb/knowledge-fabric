import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ConceptDetailPage from '../ConceptDetailPage/ConceptDetailPage.vue'
import { setMode } from '../../runtime/appMode'

enableAutoUnmount(afterEach)

const getRegistryConceptMock = vi.fn()
const getRegistryConceptGraphMock = vi.fn()
const listCrossRelationsMock = vi.fn()
const listRegistryConceptsMock = vi.fn()
const createRegistryConceptGraphificationRequestMock = vi.fn()
const createRegistryConceptGraphSnapshotMock = vi.fn()
const routerPushMock = vi.fn()
const routeState = {
  params: {},
  query: {},
  path: '/workspace/entry/canon_agent',
  fullPath: '/workspace/entry/canon_agent',
}

vi.mock('../../data/dataClient', () => ({
  getRegistryConcept: (...args) => getRegistryConceptMock(...args),
  getRegistryConceptGraph: (...args) => getRegistryConceptGraphMock(...args),
  listCrossRelations: (...args) => listCrossRelationsMock(...args),
  listRegistryConcepts: (...args) => listRegistryConceptsMock(...args),
}))

vi.mock('../../services/api/registryApi', () => ({
  createRegistryConceptGraphificationRequest: (...args) => createRegistryConceptGraphificationRequestMock(...args),
  createRegistryConceptGraphSnapshot: (...args) => createRegistryConceptGraphSnapshotMock(...args),
  unlinkProjectConcept: vi.fn(),
  updateCrossRelation: vi.fn(),
  deleteCrossRelation: vi.fn(),
  deleteRegistryConcept: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: routerPushMock }),
  RouterLink: {
    name: 'RouterLinkStub',
    template: '<a><slot /></a>',
    props: ['to'],
  },
}))

describe('ConceptDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
    setMode('live')
    getRegistryConceptMock.mockResolvedValue({
      data: {
        entry_id: 'canon_agent',
        canonical_name: 'Agent Harness',
        concept_type: 'Problem',
        aliases: [],
        description: 'Agent workflow control problem.',
        graph_status: 'snapshot_available',
        material_graph_id: 'kmg_agent',
        graph_node_count: 5,
        graph_edge_count: 4,
        cross_article_link_count: 1,
        source_links: [
          {
            project_id: 'proj_agent',
            project_name: 'Agent source project',
            concept_key: 'Problem:agent-harness',
          },
        ],
        source_evidence_refs: [
          {
            entry_id: 'canon_agent',
            project_id: 'proj_agent',
            project_name: 'Agent source project',
            concept_key: 'Problem:agent-harness',
            source_node_uuid: 'node_agent_harness',
            source_text: 'Agent Harness keeps runtime work tied to evidence.',
            source_excerpt: 'Agent Runtime lets tools collaborate around source evidence.',
            source_context: 'Before the runtime, handoffs were implicit. Agent Runtime lets tools collaborate around source evidence. Reviewers can jump back to the source article.',
            group_label: 'Problem',
            group_title: '核心问题',
            degraded: false,
          },
        ],
      },
    })
    getRegistryConceptGraphMock.mockResolvedValue({
      data: {
        concept_id: 'canon_agent',
        graph_status: 'snapshot_available',
        material_graph_id: 'kmg_agent',
        node_count: 5,
        edge_count: 4,
        cross_article_link_count: 1,
        graph: {
          graph_id: 'kmg_agent',
          nodes: [
            { id: 'concept:canon_agent', type: 'concept', label: 'Agent Harness' },
            { id: 'material_slice:ms_agent', type: 'material_slice', label: 'Agent runtime source slice', data: { text: 'Agent Runtime lets tools collaborate around source evidence.' } },
            { id: 'source_article:src_agent', type: 'source_article', label: 'Agent Runtime source article' },
            { id: 'concept:canon_runtime', type: 'related_concept', label: 'Agent Runtime' },
            { id: 'topic_cluster:tc_agent', type: 'topic_cluster', label: 'Agent Harness 与工具编排' },
          ],
          edges: [
            { id: 'edge:concept:slice', type: 'derived_from', label: '概念来自原文片段', source: 'concept:canon_agent', target: 'material_slice:ms_agent' },
            { id: 'edge:slice:article', type: 'sliced_from', label: '片段来自来源文章', source: 'material_slice:ms_agent', target: 'source_article:src_agent' },
          ],
          cross_article_links: [
            { target_concept_id: 'canon_runtime', label: 'Agent Runtime' },
          ],
        },
      },
    })
    createRegistryConceptGraphSnapshotMock.mockResolvedValue({
      data: {
        graph_status: 'snapshot_available',
        material_graph_id: 'kmg_agent',
        node_count: 5,
        edge_count: 4,
        cross_article_link_count: 1,
        graph: {
          nodes: [{ id: 'concept:canon_agent', type: 'concept', label: 'Agent Harness' }],
          edges: [],
          cross_article_links: [],
        },
      },
    })
    createRegistryConceptGraphificationRequestMock.mockResolvedValue({
      data: { request_id: 'kgreq_agent' },
    })
    listCrossRelationsMock.mockResolvedValue({ data: [] })
    listRegistryConceptsMock.mockResolvedValue({ data: { entries: [] } })
  })

  it('opens source articles in the workspace article graph with node focus preserved', async () => {
    const wrapper = mount(ConceptDetailPage, {
      props: {
        entryId: 'canon_agent',
        embedded: true,
        relatedConcepts: [
          { entry_id: 'canon_context', canonical_name: 'Context Window', concept_type: 'Constraint' },
        ],
      },
    })
    await flushPromises()

    const sourceLink = wrapper
      .findAll('a')
      .find((link) => link.text() === '查看原文')

    expect(sourceLink).toBeTruthy()
    expect(sourceLink.attributes('href')).toBe(
      '/workspace/proj_agent/article?view=reading&focusNode=Problem%3Aagent-harness&from=registry',
    )
    expect(sourceLink.attributes('href')).not.toContain('/process/')
  })

  it('renders embedded concept details as a relationship-first compact pane', async () => {
    listRegistryConceptsMock.mockResolvedValue({
      data: {
        entries: [
          { entry_id: 'canon_agent', canonical_name: 'Agent Harness', concept_type: 'Problem' },
          { entry_id: 'canon_runtime', canonical_name: 'Agent Runtime', concept_type: 'Architecture' },
        ],
      },
    })
    listCrossRelationsMock.mockResolvedValue({
      data: [
        {
          relation_id: 'xrel_agent_runtime',
          source_entry_id: 'canon_agent',
          target_entry_id: 'canon_runtime',
          relation_type: 'technical_foundation',
          review_status: 'unreviewed',
          confidence: 0.8,
          reason: '共同支撑工具编排上下文。',
        },
      ],
    })
    const wrapper = mount(ConceptDetailPage, {
      props: {
        entryId: 'canon_agent',
        embedded: true,
        relatedConcepts: [
          { entry_id: 'canon_context', canonical_name: 'Context Window', concept_type: 'Constraint' },
        ],
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="concept-compact-pane"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('Problem')
    expect(wrapper.text()).toContain('Agent source project')
    expect(wrapper.text()).toContain('相关概念')
    expect(wrapper.text()).toContain('Agent Runtime')
    expect(wrapper.text()).toContain('正式关系')
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('支撑')
    expect(wrapper.text()).toContain('→')
    expect(wrapper.text()).toContain('共同支撑工具编排上下文。')
    expect(wrapper.text()).toContain('Context Window')
    expect(wrapper.text()).toContain('同主题邻近')
    expect(wrapper.text()).toContain('暂无正式关系说明。')
    expect(wrapper.text()).toContain('来源证据')
    expect(wrapper.text()).toContain('定义摘要')
    expect(wrapper.text()).toContain('元信息 / 治理 / 研究项目')
    expect(wrapper.text()).not.toContain('CONCEPT WORKBENCH')
    expect(wrapper.text()).not.toContain('CANONICAL CONCEPT')
    expect(wrapper.text()).not.toContain('概念工作台')
    expect(wrapper.text().indexOf('相关概念')).toBeLessThan(wrapper.text().indexOf('元信息 / 治理 / 研究项目'))

    await wrapper.findAll('button').find((button) => button.text().includes('Agent Runtime')).trigger('click')
    await flushPromises()
    expect(wrapper.emitted('navigate')?.[0]).toEqual(['canon_runtime'])
  })

  it('keeps the full Concept Workbench on the full concept page', async () => {
    const wrapper = mount(ConceptDetailPage, {
      props: {
        entryId: 'canon_agent',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('CONCEPT WORKBENCH')
    expect(wrapper.text()).toContain('CANONICAL CONCEPT')
    expect(wrapper.text()).toContain('概念工作台')
    expect(wrapper.text()).toContain('当前研究项目')
    expect(wrapper.text()).toContain('概览')
    expect(wrapper.text()).toContain('来源证据')
    expect(wrapper.text()).toContain('图谱邻域')
    expect(wrapper.text()).toContain('研究项目')
    expect(wrapper.text()).toContain('治理')
    expect(wrapper.text()).toContain('已进入当前研究项目')

    await wrapper.findAll('button').find((button) => button.text() === '图谱邻域').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('KFC 来源图谱')
    expect(wrapper.text()).toContain('概念邻域')
    expect(wrapper.text()).toContain('Agent runtime source slice')
    expect(wrapper.text()).toContain('Agent Runtime')
    expect(wrapper.text()).toContain('KFC 只保存概念、来源片段、确定性关系快照和外部图谱化请求')

    const requestButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('请求外部图谱化建议'))
    expect(requestButton).toBeTruthy()
    await requestButton.trigger('click')
    await flushPromises()

    expect(createRegistryConceptGraphificationRequestMock).toHaveBeenCalledWith('canon_agent', expect.objectContaining({
      requested_by: 'human',
    }))
    expect(wrapper.text()).toContain('已写入外部图谱化请求')
  })

  it('uses source_links as provenance when top-level source article fields are missing', async () => {
    routeState.query = { project_id: 'proj_agent', from: 'theme-panorama' }
    const wrapper = mount(ConceptDetailPage, {
      props: {
        entryId: 'canon_agent',
      },
    })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '来源证据').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('当前来源')
    expect(wrapper.text()).toContain('Agent source project')
    expect(wrapper.text()).toContain('Problem:agent-harness')
    expect(wrapper.text()).toContain('Agent Runtime lets tools collaborate around source evidence.')
    expect(wrapper.text()).toContain('Reviewers can jump back to the source article.')
    const locateLink = wrapper
      .findAll('a')
      .find((link) => link.text().includes('定位到阅读图谱'))
    expect(locateLink).toBeTruthy()
    expect(locateLink.attributes('href')).toBe(
      '/workspace/proj_agent/article?view=reading&focusNode=Problem%3Aagent-harness&from=registry',
    )
    expect(wrapper.text()).not.toContain('来源 unknown')
  })
})
