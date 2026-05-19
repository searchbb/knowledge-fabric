import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getWikiTopicArticles = vi.fn()
const listTopicClusters = vi.fn()
const linkWikiTopicToCluster = vi.fn()
const setWikiTopicClusterCoverageOverride = vi.fn()
const requestWikiTopicClusterProposal = vi.fn()
const routeState = {
  params: { topicId: 'ai-tokenization' },
}

vi.mock('../../data/dataClient', () => ({
  getWikiTopicArticles: (...args) => getWikiTopicArticles(...args),
  listTopicClusters: (...args) => listTopicClusters(...args),
  linkWikiTopicToCluster: (...args) => linkWikiTopicToCluster(...args),
  setWikiTopicClusterCoverageOverride: (...args) => setWikiTopicClusterCoverageOverride(...args),
  requestWikiTopicClusterProposal: (...args) => requestWikiTopicClusterProposal(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] },
}))

vi.mock('../../components/common/AppShell.vue', () => ({
  default: { template: '<main><slot /></main>', props: ['crumbs'] },
}))

import WikiTopicDetailPage from '../WikiTopicDetailPage.vue'

enableAutoUnmount(afterEach)

describe('WikiTopicDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params.topicId = 'ai-tokenization'
    getWikiTopicArticles.mockResolvedValue({
      data: {
        topic: {
          topic_id: 'ai-tokenization',
          title: 'AI 分词与计费成本',
          article_count: 1,
          completed_count: 1,
          needs_review_count: 0,
          top_concepts: ['token economy', 'stablecoin payment'],
          cluster_ids: ['tc_wiki_ai-tokenization'],
          cluster_links: [{ cluster_id: 'tc_wiki_ai-tokenization', title: 'AI 分词与计费成本' }],
          cluster_coverage: {
            topic_id: 'ai-tokenization',
            status: 'linked',
            linked_clusters: [{ cluster_id: 'tc_wiki_ai-tokenization', title: 'AI 分词与计费成本', role: 'primary', status: 'accepted' }],
            candidate_clusters: [],
            candidate_count: 0,
            recommendation: '已正式关联到 Topic Cluster。',
            reason: 'Topic has at least one accepted TopicClusterLink.',
          },
        },
        articles: [
          {
            candidate_id: 'src_token',
            source_id: 'src_token',
            title: 'Token Economy（词元经济）产业链全景报告',
            source_url: 'https://example.com/token',
            source_type: '微信文章',
            status: 'completed',
            processed_at: '2026-05-13T11:21:15+08:00',
            digest_summary: '该材料聚焦 Token Economy 和模型计费。',
            top_concepts: ['token economy', 'AI pricing'],
            markdown_path: '/tmp/token.md',
          },
        ],
      },
    })
    listTopicClusters.mockResolvedValue({
      data: {
        items: [
          { cluster_id: 'tc_wiki_ai-tokenization', title: 'AI 分词与计费成本' },
          { cluster_id: 'tc_ai_cloud', title: 'AI Cloud Infrastructure & Business' },
        ],
      },
    })
    linkWikiTopicToCluster.mockResolvedValue({
      data: {
        coverage: {
          status: 'linked',
          linked_clusters: [{ cluster_id: 'tc_ai_cloud', title: 'AI Cloud Infrastructure & Business' }],
          candidate_clusters: [],
          candidate_count: 0,
        },
      },
    })
    setWikiTopicClusterCoverageOverride.mockResolvedValue({
      data: {
        coverage: {
          status: 'watch',
          linked_clusters: [],
          candidate_clusters: [],
          candidate_count: 0,
          manual_override: { status: 'watch' },
        },
      },
    })
    requestWikiTopicClusterProposal.mockResolvedValue({
      data: {
        request: { request_id: 'tcr_demo_topic', status: 'requested' },
        coverage: {
          status: 'candidate',
          linked_clusters: [],
          candidate_clusters: [{ cluster_id: 'tc_ai_cloud', title: 'AI Cloud Infrastructure & Business' }],
          candidate_count: 1,
        },
      },
    })
  })

  it('loads a topic detail from the route and renders articles', async () => {
    const wrapper = mount(WikiTopicDetailPage, {
      global: { stubs: { 'router-link': { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
    })
    await flushPromises()

    expect(getWikiTopicArticles).toHaveBeenCalledWith('ai-tokenization')
    expect(wrapper.text()).toContain('AI 分词与计费成本')
    expect(wrapper.text()).toContain('Token Economy（词元经济）产业链全景报告')
    expect(wrapper.text()).toContain('该材料聚焦 Token Economy 和模型计费')
    expect(wrapper.text()).toContain('主题簇覆盖')
    expect(wrapper.text()).toContain('已关联')
    const clusterLink = wrapper.find('a[href="/workspace/topic-clusters/tc_wiki_ai-tokenization"]')
    const sourceLink = wrapper.find('a[href="https://example.com/token"]')
    const intakeLink = wrapper.find('a[href="/workspace/wiki-intake?candidate=src_token"]')
    const sourceFileLink = wrapper.find('a[href="file:///tmp/token.md"]')
    expect(clusterLink.exists()).toBe(true)
    expect(clusterLink.attributes('target')).toBe('_blank')
    expect(clusterLink.attributes('rel')).toContain('noopener')
    expect(sourceLink.exists()).toBe(true)
    expect(sourceLink.attributes('target')).toBe('_blank')
    expect(intakeLink.attributes('target')).toBe('_blank')
    expect(sourceFileLink.attributes('target')).toBe('_blank')
  })

  it('filters articles by concept tag', async () => {
    const wrapper = mount(WikiTopicDetailPage, {
      global: { stubs: { 'router-link': { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
    })
    await flushPromises()

    const tag = wrapper.findAll('button').find((button) => button.text() === 'stablecoin payment')
    await tag.trigger('click')

    expect(wrapper.text()).toContain('暂无文章')
  })

  it('supports manual coverage actions from the detail panel', async () => {
    getWikiTopicArticles.mockResolvedValueOnce({
      data: {
        topic: {
          topic_id: 'cloud-data-ai-platform',
          title: 'Cloud Data and AI Platform',
          article_count: 1,
          completed_count: 1,
          needs_review_count: 0,
          top_concepts: ['cloud data', 'AI platform'],
          cluster_ids: [],
          cluster_links: [],
          cluster_coverage: {
            topic_id: 'cloud-data-ai-platform',
            status: 'candidate',
            linked_clusters: [],
            candidate_clusters: [
              {
                cluster_id: 'tc_ai_cloud',
                title: 'AI Cloud Infrastructure & Business',
                reason: 'Matched topic/cluster terms: ai, cloud',
                confidence_label: 'medium',
                matched_terms: ['ai', 'cloud'],
              },
            ],
            candidate_count: 1,
            recommendation: '存在候选 Cluster，等待人工确认。',
          },
        },
        articles: [],
      },
    })
    routeState.params.topicId = 'cloud-data-ai-platform'
    const wrapper = mount(WikiTopicDetailPage, {
      global: { stubs: { 'router-link': { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('AI Cloud Infrastructure & Business')
    const candidateLink = wrapper.findAll('button').find((button) => button.text().includes('关联到此主题簇'))
    await candidateLink.trigger('click')
    await flushPromises()
    expect(linkWikiTopicToCluster).toHaveBeenCalledWith(
      'cloud-data-ai-platform',
      expect.objectContaining({ cluster_id: 'tc_ai_cloud' }),
    )
    expect(wrapper.text()).toContain('已人工关联到 主题簇')

    const proposalButton = wrapper.findAll('button').find((button) => button.text().includes('提出新主题簇建议'))
    await proposalButton.trigger('click')
    await flushPromises()
    expect(requestWikiTopicClusterProposal).toHaveBeenCalledWith(
      'cloud-data-ai-platform',
      expect.objectContaining({ suggested_title: 'Cloud Data and AI Platform' }),
    )

    const watchButton = wrapper.findAll('button').find((button) => button.text().includes('暂时观察'))
    await watchButton.trigger('click')
    await flushPromises()
    expect(setWikiTopicClusterCoverageOverride).toHaveBeenCalledWith(
      'cloud-data-ai-platform',
      expect.objectContaining({ status: 'watch' }),
    )
  })
})
