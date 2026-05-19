import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listTopicClusters = vi.fn()
const getTopicCluster = vi.fn()
const createTopicCluster = vi.fn()
const listTopicClusterRefreshRequests = vi.fn()
const createTopicClusterRefreshRequest = vi.fn()
const listWikiTopics = vi.fn()
const routerPush = vi.fn()

vi.mock('../../data/dataClient', () => ({
  listTopicClusters: (...args) => listTopicClusters(...args),
  getTopicCluster: (...args) => getTopicCluster(...args),
  createTopicCluster: (...args) => createTopicCluster(...args),
  listTopicClusterRefreshRequests: (...args) => listTopicClusterRefreshRequests(...args),
  createTopicClusterRefreshRequest: (...args) => createTopicClusterRefreshRequest(...args),
  listWikiTopics: (...args) => listWikiTopics(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/topic-clusters', params: {} }),
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
  RouterLink: { template: '<a :href="typeof to === `string` ? to : to.name"><slot /></a>', props: ['to'] },
}))

vi.mock('../../components/common/AppShell.vue', () => ({
  default: { template: '<div class="app-shell-stub"><slot /></div>', props: ['crumbs'] },
}))

import TopicClustersPage from '../TopicClustersPage.vue'

enableAutoUnmount(afterEach)

const routerLinkStub = {
  template: '<a :href="typeof to === `string` ? to : to.name"><slot /></a>',
  props: ['to'],
}

const clusters = [
  {
    cluster_id: 'tc_agent_ready',
    title: 'Agent-ready 企业软件栈',
    description: '聚合企业软件 Agent 化和 Harness。',
    status: 'active',
    strategic_relevance: 'high',
    counts: {
      wiki_topics: 2,
      kfc_themes: 3,
      research_projects: 0,
      candidate_links: 1,
      needs_review_links: 0,
    },
    article_count: 6,
    representative_articles: [{ candidate_id: 'src_token', title: 'Token Economy（词元经济）产业链全景报告' }],
  },
]

describe('TopicClustersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTopicClusters.mockResolvedValue({ data: { items: clusters, total: 1, warnings: [] } })
    getTopicCluster.mockResolvedValue({
      data: {
        cluster: clusters[0],
        links_by_type: {
          wiki_topic: [
            {
              link_id: 'tcl_wiki',
              target_title: 'Agent-ready 企业软件栈',
              target_id: 'agent-ready-enterprise-stack',
            },
          ],
          kfc_theme: [
            {
              link_id: 'tcl_theme',
              target_title: 'AI Agent系统架构与上下文管理',
              target_id: 'gtheme_agent',
            },
          ],
          research_project: [],
        },
        warnings: [],
      },
    })
    createTopicCluster.mockResolvedValue({
      data: { cluster: { cluster_id: 'tc_new', title: 'New Cluster' }, warnings: [] },
    })
    listTopicClusterRefreshRequests.mockResolvedValue({
      data: {
        items: [
          {
            request_id: 'tcr_demo_001',
            status: 'requested',
            created_at: '2026-05-12T10:00:00',
            inputs: { include_wiki_topics: true, include_kfc_themes: true },
            rules: { proposal_only: true, do_not_auto_apply: true },
          },
        ],
        total: 1,
      },
    })
    listWikiTopics.mockResolvedValue({
      data: {
        topics: [],
        coverage_counts: { linked: 32, candidate: 5, needs_cluster: 2, watch: 1, ignored: 0 },
      },
    })
    createTopicClusterRefreshRequest.mockResolvedValue({
      data: {
        request_id: 'tcr_new',
        status: 'requested',
        inputs: { include_wiki_topics: true, include_kfc_themes: true },
        rules: { proposal_only: true, do_not_auto_apply: true },
      },
    })
  })

  it('renders cluster cards with counts and preview links', async () => {
    const wrapper = mount(TopicClustersPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    expect(listTopicClusters).toHaveBeenCalledWith({ includeCounts: true })
    expect(getTopicCluster).toHaveBeenCalledWith('tc_agent_ready')
    expect(wrapper.text()).toContain('主题汇集')
    expect(wrapper.text()).toContain('Agent-ready 企业软件栈')
    expect(wrapper.text()).toContain('Wiki 2')
    expect(wrapper.text()).toContain('文章 6')
    expect(wrapper.text()).toContain('Token Economy（词元经济）产业链全景报告')
    expect(wrapper.text()).toContain('KFC 主题 3')
    expect(wrapper.text()).toContain('AI Agent系统架构与上下文管理')
    expect(wrapper.text()).toContain('最近主题簇建议请求')
    expect(wrapper.text()).toContain('仅生成建议')
    expect(wrapper.text()).toContain('不自动应用')
    expect(wrapper.text()).toContain('Wiki 主题簇覆盖')
    expect(wrapper.text()).toContain('候选待确认')
    expect(wrapper.html()).toContain('/workspace/wiki-topics?coverage=candidate')
    const clusterOpen = wrapper.find('a[href="/workspace/topic-clusters/tc_agent_ready"]')
    const topicOpen = wrapper.find('a[href="/workspace/wiki-topics/agent-ready-enterprise-stack"]')
    expect(clusterOpen.attributes('target')).toBe('_blank')
    expect(clusterOpen.attributes('rel')).toContain('noopener')
    expect(topicOpen.exists()).toBe(false)
    expect(wrapper.text()).not.toContain('打开主题 ')
  })

  it('renders empty state', async () => {
    listTopicClusters.mockResolvedValue({ data: { items: [], total: 0, warnings: [] } })
    const wrapper = mount(TopicClustersPage)
    await flushPromises()

    expect(wrapper.text()).toContain('暂无主题簇')
  })

  it('creates a cluster and navigates to detail', async () => {
    const wrapper = mount(TopicClustersPage)
    await flushPromises()

    await wrapper.find('button').trigger('click')
    await wrapper.find('input').setValue('New Cluster')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createTopicCluster).toHaveBeenCalledWith(expect.objectContaining({ title: 'New Cluster' }))
    expect(routerPush).toHaveBeenCalledWith('/workspace/topic-clusters/tc_new')
  })

  it('creates a refresh request with fixed proposal-only payload', async () => {
    const wrapper = mount(TopicClustersPage)
    await flushPromises()

    const button = wrapper.findAll('button').find((item) => item.text().includes('生成主题簇建议'))
    await button.trigger('click')
    await flushPromises()

    expect(createTopicClusterRefreshRequest).toHaveBeenCalledWith({
      scope: 'all',
      inputs: {
        include_wiki_topics: true,
        include_kfc_themes: true,
        include_kfc_concepts: false,
        include_research_projects: false,
      },
    })
    expect(wrapper.text()).toContain('已创建主题簇建议请求')
    expect(listTopicClusterRefreshRequests).toHaveBeenCalledTimes(2)
  })
})
