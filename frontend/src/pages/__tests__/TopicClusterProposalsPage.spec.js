import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listTopicClusterProposals = vi.fn()

vi.mock('../../data/dataClient', () => ({
  listTopicClusterProposals: (...args) => listTopicClusterProposals(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/topic-clusters/proposals', params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a :href="typeof to === `string` ? to : to.name"><slot /></a>', props: ['to'] },
}))

vi.mock('../../components/common/AppShell.vue', () => ({
  default: { template: '<div class="app-shell-stub"><slot /></div>', props: ['crumbs'] },
}))

import TopicClusterProposalsPage from '../TopicClusterProposalsPage.vue'

enableAutoUnmount(afterEach)

describe('TopicClusterProposalsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listTopicClusterProposals.mockResolvedValue({
      data: {
        items: [
          {
            proposal_id: 'tcp_demo_agent_ready',
            status: 'ready_for_review',
            created_at: '2026-05-12T10:05:00',
            action_count: 3,
            supported_action_count: 2,
            unsupported_action_count: 1,
            warning_count: 1,
          },
        ],
      },
    })
  })

  it('renders proposal summaries and boundary copy', async () => {
    const wrapper = mount(TopicClusterProposalsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('主题簇建议')
    expect(wrapper.text()).toContain('不生成建议')
    expect(wrapper.text()).toContain('tcp_demo_agent_ready')
    expect(wrapper.text()).toContain('支持 2')
    expect(wrapper.text()).toContain('仅审核 1')
  })

  it('renders empty state', async () => {
    listTopicClusterProposals.mockResolvedValue({ data: { items: [] } })
    const wrapper = mount(TopicClusterProposalsPage)
    await flushPromises()

    expect(wrapper.text()).toContain('暂无建议包')
  })
})
