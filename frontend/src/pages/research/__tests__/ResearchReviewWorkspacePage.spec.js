import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

enableAutoUnmount(afterEach)

const listResearchProjects = vi.fn()
const listGovernanceReviews = vi.fn()
const listResearchSnapshots = vi.fn()
const listReviewHistory = vi.fn()

vi.mock('../../../data/dataClient', () => ({
  listResearchProjects: (...args) => listResearchProjects(...args),
  listGovernanceReviews: (...args) => listGovernanceReviews(...args),
  listResearchSnapshots: (...args) => listResearchSnapshots(...args),
  listReviewHistory: (...args) => listReviewHistory(...args),
}))

import ResearchReviewWorkspacePage from '../ResearchReviewWorkspacePage.vue'

function mountPage() {
  return mount(ResearchReviewWorkspacePage, {
    global: {
      stubs: {
        AppShell: { template: '<main><slot /></main>', props: ['crumbs'] },
        RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] },
      },
    },
  })
}

describe('ResearchReviewWorkspacePage', () => {
  beforeEach(() => {
    listResearchProjects.mockReset()
    listGovernanceReviews.mockReset()
    listResearchSnapshots.mockReset()
    listReviewHistory.mockReset()
    listResearchProjects.mockResolvedValue({
      data: {
        projects: [
          {
            id: 'rp_review_nav',
            title: 'Huawei Cloud Agent-ready strategy',
            status: 'active',
            goal: 'Prepare reviewable strategic assets.',
          },
        ],
      },
    })
    listGovernanceReviews.mockResolvedValue({
      data: {
        governance_reviews: [
          {
            review_id: 'gr_review_nav',
            title: 'P22 navigation review',
            status: 'in_review',
            readiness: 'partial',
          },
        ],
      },
    })
    listResearchSnapshots.mockResolvedValue({
      data: {
        snapshots: [
          {
            snapshot_id: 'rs_review_nav',
            title: 'P23 review snapshot',
            status: 'indexed',
            created_at: '2026-04-30T00:00:00.000000',
          },
        ],
      },
    })
    listReviewHistory.mockResolvedValue({
      data: {
        review_history_entries: [
          {
            history_entry_id: 'rhe_review_nav',
            event_type: 'governance_review_updated',
            asset_type: 'governance_review',
            asset_id: 'gr_review_nav',
            asset_title: 'P22 navigation review',
            actor: { display_name: 'Reviewer' },
            summary: 'governance review updated',
            created_at: '2026-04-30T00:10:00.000000',
          },
        ],
      },
    })
  })

  it('renders a read-only review workspace using existing research project and governance review APIs', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listResearchProjects).toHaveBeenCalledTimes(1)
    expect(listGovernanceReviews).toHaveBeenCalledWith('rp_review_nav')
    expect(listResearchSnapshots).toHaveBeenCalledWith('rp_review_nav')
    expect(listReviewHistory).toHaveBeenCalledWith('rp_review_nav', { limit: 5 })
    expect(wrapper.text()).toContain('研究审核工作台')
    expect(wrapper.text()).toContain('只读导航边界')
    expect(wrapper.text()).toContain('审核资产索引')
    expect(wrapper.text()).toContain('Huawei Cloud Agent-ready strategy')
    expect(wrapper.text()).toContain('P22 navigation review')
    expect(wrapper.text()).toContain('P23 review snapshot')
    expect(wrapper.text()).toContain('近期审核历史')
    expect(wrapper.text()).toContain('显示最近 5 条审核历史。')
    expect(wrapper.text()).toContain('governance_review_updated')
    expect(wrapper.text()).toContain('资产：governance_review · P22 navigation review')
    expect(wrapper.text()).toContain('操作者：Reviewer')
    expect(wrapper.text()).toContain('1研究项目')
    expect(wrapper.text()).toContain('1治理审核')
    expect(wrapper.text()).toContain('1研究快照')
    expect(wrapper.text()).toContain('1已索引快照')
    expect(wrapper.find('a[href="/workspace/research?project=rp_review_nav"]').exists()).toBe(true)
  })

  it('renders an empty state without mutating review state', async () => {
    listResearchProjects.mockResolvedValueOnce({ data: { projects: [] } })

    const wrapper = mountPage()
    await flushPromises()

    expect(listGovernanceReviews).not.toHaveBeenCalled()
    expect(listResearchSnapshots).not.toHaveBeenCalled()
    expect(listReviewHistory).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('暂无可用战略研究项目。')
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('[role="button"]')).toHaveLength(0)
  })

  it('keeps projects in the asset index when snapshot loading fails passively', async () => {
    listResearchSnapshots.mockRejectedValueOnce(new Error('snapshot service unavailable'))

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('P22 navigation review')
    expect(wrapper.text()).toContain('0已索引快照')
    expect(wrapper.text()).toContain('当前项目尚未索引研究快照。')
  })

  it('limits review history to five entries and handles history failure passively', async () => {
    listResearchProjects.mockResolvedValueOnce({
      data: {
        projects: [
          { id: 'rp_history_a', title: 'History A', status: 'active' },
          { id: 'rp_history_b', title: 'History B', status: 'active' },
        ],
      },
    })
    listGovernanceReviews.mockResolvedValue({ data: { governance_reviews: [] } })
    listResearchSnapshots.mockResolvedValue({ data: { snapshots: [] } })
    listReviewHistory
      .mockResolvedValueOnce({
        data: {
          review_history_entries: Array.from({ length: 6 }, (_, index) => ({
            history_entry_id: `rhe_${index}`,
            event_type: `review_event_${index}`,
            asset_type: 'governance_review',
            asset_id: `gr_${index}`,
            created_at: `2026-04-30T00:0${index}:00.000000`,
          })),
        },
      })
      .mockRejectedValueOnce(new Error('history unavailable'))

    const wrapper = mountPage()
    await flushPromises()

    expect(listReviewHistory).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('review_event_0')
    expect(wrapper.text()).toContain('review_event_4')
    expect(wrapper.text()).not.toContain('review_event_5')
    expect(wrapper.text()).toContain('当前项目审核历史不可用；已有项目资产仍然可见。')
  })

  it('does not render readiness, workflow, assignment, model, or gate decision controls', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.findAll('button')).toHaveLength(0)
    const linkText = wrapper.findAll('a').map((link) => link.text()).join(' ')
    expect(linkText).not.toMatch(/\bAssign\b|Approve|Reject|Decide gate|Run model|Evaluate readiness|\bSchedule\b/i)
    expect(wrapper.emitted()).toEqual({})
  })
})
