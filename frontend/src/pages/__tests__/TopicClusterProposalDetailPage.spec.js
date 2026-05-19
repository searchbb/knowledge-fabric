import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getTopicClusterProposal = vi.fn()
const applyTopicClusterProposal = vi.fn()
const routeState = {
  query: {},
  path: '/workspace/topic-clusters/proposals/tcp_demo',
  params: { proposalId: 'tcp_demo' },
}

vi.mock('../../data/dataClient', () => ({
  getTopicClusterProposal: (...args) => getTopicClusterProposal(...args),
  applyTopicClusterProposal: (...args) => applyTopicClusterProposal(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a :href="typeof to === `string` ? to : to.name"><slot /></a>', props: ['to'] },
}))

vi.mock('../../components/common/AppShell.vue', () => ({
  default: { template: '<div class="app-shell-stub"><slot /></div>', props: ['crumbs'] },
}))

import TopicClusterProposalDetailPage from '../TopicClusterProposalDetailPage.vue'

enableAutoUnmount(afterEach)

describe('TopicClusterProposalDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getTopicClusterProposal.mockResolvedValue({
      data: {
        proposal: {
          proposal_id: 'tcp_demo',
          warnings: [{ code: 'manual_review', message: 'Review merge manually' }],
          actions: [
            {
              action_id: 'create_cluster:tc_new',
              action_type: 'create_cluster',
              confidence: 0.86,
              rationale: 'Create a new cluster.',
              payload: { cluster_id: 'tc_new', title: 'New Cluster' },
            },
            {
              action_id: 'add_link:tcl_new',
              action_type: 'add_link',
              confidence: 0.78,
              rationale: 'Add a supporting link.',
              payload: { link_id: 'tcl_new', cluster_id: 'tc_new', target_type: 'wiki_topic', target_id: 'agent-harness' },
            },
            {
              action_id: 'merge_cluster:tc_old->tc_new',
              action_type: 'merge_cluster',
              confidence: 0.4,
              rationale: 'Review only.',
              payload: { from_cluster_id: 'tc_old', to_cluster_id: 'tc_new' },
            },
          ],
        },
        applications: [],
      },
    })
    applyTopicClusterProposal.mockResolvedValue({
      data: {
        created_cluster_ids: ['tc_new'],
        created_link_ids: [],
        skipped_existing_cluster_ids: [],
        skipped_existing_link_ids: [],
      },
    })
  })

  it('groups actions and leaves all checkboxes unchecked by default', async () => {
    const wrapper = mount(TopicClusterProposalDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('新主题簇建议')
    expect(wrapper.text()).toContain('新增关联建议')
    expect(wrapper.text()).toContain('可能合并')
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes).toHaveLength(3)
    expect(checkboxes.at(0).element.checked).toBe(false)
    expect(checkboxes.at(1).element.checked).toBe(false)
    expect(checkboxes.at(2).element.disabled).toBe(true)
    expect(wrapper.find('button.primary-btn').element.disabled).toBe(true)
  })

  it('applies only selected supported actions', async () => {
    const wrapper = mount(TopicClusterProposalDetailPage)
    await flushPromises()

    await wrapper.findAll('input[type="checkbox"]').at(0).setValue(true)
    await wrapper.find('button.primary-btn').trigger('click')
    await flushPromises()

    expect(applyTopicClusterProposal).toHaveBeenCalledWith('tcp_demo', {
      accepted_actions: ['create_cluster:tc_new'],
      rejected_actions: ['add_link:tcl_new', 'merge_cluster:tc_old->tc_new'],
    })
    expect(wrapper.text()).toContain('新建主题簇: tc_new')
  })
})
