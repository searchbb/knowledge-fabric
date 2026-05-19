import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listWikiTopics = vi.fn()

vi.mock('../../data/dataClient', () => ({
  listWikiTopics: (...args) => listWikiTopics(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
}))

vi.mock('../../components/common/AppShell.vue', () => ({
  default: { template: '<main><slot /></main>', props: ['crumbs'] },
}))

import WikiTopicsPage from '../WikiTopicsPage.vue'

enableAutoUnmount(afterEach)

const topics = [
  {
    topic_id: 'ai-tokenization',
    title: 'AI 分词与计费成本',
    article_count: 6,
    completed_count: 6,
    needs_review_count: 0,
    last_processed_at: '2026-05-13T11:21:15+08:00',
    top_concepts: ['token economy', '中文税', 'API pricing'],
    cluster_ids: ['tc_wiki_ai-tokenization'],
    cluster_coverage_status: 'linked',
    cluster_coverage: {
      status: 'linked',
      linked_clusters: [{ cluster_id: 'tc_wiki_ai-tokenization', title: 'AI 分词与计费成本' }],
      candidate_clusters: [],
      candidate_count: 0,
    },
    representative_articles: [{ title: 'Token Economy（词元经济）产业链全景报告' }],
  },
  {
    topic_id: 'cloud-data-ai-platform',
    title: 'Cloud Data and AI Platform',
    article_count: 1,
    completed_count: 1,
    needs_review_count: 0,
    last_processed_at: '2026-05-14T10:25:52+08:00',
    top_concepts: ['cloud data', 'AI platform'],
    cluster_ids: [],
    cluster_coverage_status: 'candidate',
    cluster_coverage: {
      status: 'candidate',
      linked_clusters: [],
      candidate_clusters: [{ cluster_id: 'tc_ai_cloud', title: 'AI Cloud Infrastructure & Business' }],
      candidate_count: 1,
    },
    representative_articles: [{ title: '阿里云智能大数据演进' }],
  },
]

describe('WikiTopicsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listWikiTopics.mockResolvedValue({
      data: {
        topics,
        coverage_counts: { linked: 1, candidate: 1, needs_cluster: 0, watch: 0, ignored: 0 },
      },
    })
  })

  it('renders wiki topic overview stats and actions', async () => {
    const wrapper = mount(WikiTopicsPage, {
      global: {
        stubs: {
          RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] },
        },
      },
    })
    await flushPromises()

    expect(listWikiTopics).toHaveBeenCalledWith({ includeCoverage: true })
    expect(wrapper.text()).toContain('主题总览')
    expect(wrapper.text()).toContain('AI 分词与计费成本')
    expect(wrapper.text()).toContain('ai-tokenization')
    expect(wrapper.text()).toContain('Token Economy（词元经济）产业链全景报告')
    expect(wrapper.text()).toContain('文章')
    expect(wrapper.find('a[href="/workspace/wiki-topics/ai-tokenization"]').exists()).toBe(true)
    const topicLink = wrapper.find('a[href="/workspace/wiki-topics/ai-tokenization"]')
    const clusterLink = wrapper.find('a[href="/workspace/topic-clusters/tc_wiki_ai-tokenization"]')
    expect(topicLink.attributes('target')).toBe('_blank')
    expect(topicLink.attributes('rel')).toContain('noopener')
    expect(clusterLink.exists()).toBe(true)
    expect(clusterLink.attributes('target')).toBe('_blank')
    expect(clusterLink.attributes('rel')).toContain('noreferrer')
    expect(wrapper.text()).toContain('有候选主题簇')
    expect(wrapper.text()).toContain('主题簇：有候选')
  })

  it('filters topics by concept or article title', async () => {
    const wrapper = mount(WikiTopicsPage, {
      global: { stubs: { RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
    })
    await flushPromises()

    await wrapper.find('input').setValue('中文税')
    expect(wrapper.text()).toContain('AI 分词与计费成本')

    await wrapper.find('input').setValue('')
    const candidateFilter = wrapper.findAll('button').find((button) => button.text().includes('有候选主题簇'))
    await candidateFilter.trigger('click')
    expect(wrapper.text()).toContain('Cloud Data and AI Platform')
    expect(wrapper.text()).not.toContain('AI 分词与计费成本')

    await wrapper.find('input').setValue('no-match')
    expect(wrapper.text()).toContain('当前筛选下没有主题')
  })

  it('shows an empty state', async () => {
    listWikiTopics.mockResolvedValue({ data: { topics: [], coverage_counts: {} } })
    const wrapper = mount(WikiTopicsPage, {
      global: { stubs: { RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无已预消化主题')
  })
})
