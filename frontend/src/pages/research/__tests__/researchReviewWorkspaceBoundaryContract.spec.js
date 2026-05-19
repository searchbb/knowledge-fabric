import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
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

import router from '../../../router'
import ResearchReviewWorkspacePage from '../ResearchReviewWorkspacePage.vue'

const workspacePagePath = resolve(process.cwd(), 'src', 'pages', 'research', 'ResearchReviewWorkspacePage.vue')
const sidebarPath = resolve(process.cwd(), 'src', 'components', 'common', 'AppSidebar.vue')
const routerPath = resolve(process.cwd(), 'src', 'router', 'index.js')
const p25DocPath = resolve(
  process.cwd(),
  '..',
  'docs',
  'research',
  'p25_research_review_workspace_boundary_hardening.md',
)

function readSource(path) {
  return readFileSync(path, 'utf8')
}

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

describe('research review workspace boundary contract', () => {
  beforeEach(() => {
    listResearchProjects.mockReset()
    listGovernanceReviews.mockReset()
    listResearchSnapshots.mockReset()
    listReviewHistory.mockReset()
    listResearchProjects.mockResolvedValue({
      data: {
        projects: [
          { id: 'rp_boundary_a', title: 'Boundary A', status: 'active', goal: 'Keep read-only review assets visible.' },
          { id: 'rp_boundary_b', title: 'Boundary B', status: 'active', goal: 'Keep failure isolated.' },
        ],
      },
    })
    listGovernanceReviews.mockResolvedValue({
      data: {
        governance_reviews: [
          { review_id: 'gr_boundary', title: 'Boundary governance review', status: 'in_review', readiness: 'partial' },
        ],
      },
    })
    listResearchSnapshots.mockResolvedValue({
      data: {
        snapshots: [
          { snapshot_id: 'rs_boundary', title: 'Boundary snapshot', status: 'indexed' },
        ],
      },
    })
    listReviewHistory.mockResolvedValue({
      data: {
        review_history_entries: [
          {
            history_entry_id: 'rhe_boundary',
            event_type: 'governance_review_updated',
            asset_type: 'governance_review',
            asset_id: 'gr_boundary',
            asset_title: 'Boundary governance review',
          },
        ],
      },
    })
  })

  it('documents the P25 read-only boundary without adding product behavior', () => {
    expect(existsSync(p25DocPath)).toBe(true)
    const doc = readSource(p25DocPath)

    expect(doc).toContain('P25 adds no new product behavior')
    expect(doc).toContain('read-only')
    expect(doc).toContain('existing-API-only')
    expect(doc).toContain('passively failure-isolated')
    expect(doc).toContain('separate from the legacy `ReviewPage.vue` prototype')
    expect(doc).toContain('separate from the frozen P15-P20 attention context')
    expect(doc).toContain('P26 should be docs/tests-only by default')
  })

  it('keeps the production page existing-API-only', () => {
    const source = readSource(workspacePagePath)
    const dataClientImport = source.match(/import\s*\{([^}]*)\}\s*from\s*['"]\.\.\/\.\.\/data\/dataClient['"]/)
    const importedNames = dataClientImport?.[1]
      .split(',')
      .map((name) => name.trim())
      .filter(Boolean)
      .sort()

    expect(importedNames).toEqual([
      'listGovernanceReviews',
      'listResearchProjects',
      'listResearchSnapshots',
      'listReviewHistory',
    ])
    expect(source).not.toMatch(/\b(create|update|delete|submit|approve|reject|assign|evaluate|execute|schedule|run)[A-Z][A-Za-z0-9_]*\s*\(/)
    expect(source).not.toMatch(/createReview|updateReview|deleteReview|submitReview|approveReview|rejectReview|assignReview/)
    expect(source).not.toMatch(/readModel|persistedReviewWorkspace|reviewWorkspaceReadModel|taskApi|jobApi|modelRuntime/)
  })

  it('keeps review history bounded to latest five entries per project', async () => {
    listReviewHistory
      .mockResolvedValueOnce({
        data: {
          review_history_entries: Array.from({ length: 6 }, (_, index) => ({
            history_entry_id: `rhe_a_${index}`,
            event_type: `boundary_event_${index}`,
            asset_type: 'governance_review',
            asset_id: `gr_a_${index}`,
          })),
        },
      })
      .mockRejectedValueOnce(new Error('history unavailable'))

    const wrapper = mountPage()
    await flushPromises()

    expect(listReviewHistory).toHaveBeenNthCalledWith(1, 'rp_boundary_a', { limit: 5 })
    expect(listReviewHistory).toHaveBeenNthCalledWith(2, 'rp_boundary_b', { limit: 5 })
    expect(wrapper.text()).toContain('Boundary governance review')
    expect(wrapper.text()).toContain('Boundary snapshot')
    expect(wrapper.text()).toContain('boundary_event_0')
    expect(wrapper.text()).toContain('boundary_event_4')
    expect(wrapper.text()).not.toContain('boundary_event_5')
    expect(wrapper.text()).toContain('当前项目审核历史不可用；已有项目资产仍然可见。')
  })

  it('renders passive read-only content without mutation controls or hidden edit surfaces', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const controlText = [
      ...wrapper.findAll('button'),
      ...wrapper.findAll('[role="button"]'),
      ...wrapper.findAll('a'),
    ].map((node) => node.text()).join(' ')

    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('[role="button"]')).toHaveLength(0)
    expect(wrapper.findAll('form')).toHaveLength(0)
    expect(wrapper.findAll('input')).toHaveLength(0)
    expect(wrapper.findAll('textarea')).toHaveLength(0)
    expect(wrapper.findAll('select')).toHaveLength(0)
    expect(wrapper.findAll('[contenteditable="true"]')).toHaveLength(0)
    expect(controlText).not.toMatch(/Approve|Reject|Submit|Sign off|Assign|Route|Start|Run|Execute|Schedule|Repair|Evaluate readiness|Decide gate|Edit history/i)
    expect(wrapper.emitted()).toEqual({})
  })

  it('isolates the production route from prototype review and frozen attention surfaces', () => {
    const pageSource = readSource(workspacePagePath)
    const routerSource = readSource(routerPath)

    expect(pageSource).not.toMatch(/ReviewPage\.vue|pages\/ReviewPage|@\/pages\/ReviewPage/)
    expect(pageSource).not.toMatch(/snapshotReviewNoteRollup|gateReviewSnapshotAttentionContext|GateReviewSnapshotAttentionContext/)
    expect(routerSource).toContain("path: '/workspace/research/review'")
    expect(routerSource).toContain('ResearchReviewWorkspacePage')
    expect(routerSource).not.toMatch(/path:\s*['"]\/workspace\/research\/review['"][\s\S]*ReviewPage/)
  })

  it('keeps route and sidebar continuity for the separate Review Workspace surface', () => {
    const sidebarSource = readSource(sidebarPath)
    const researchGroupSource = sidebarSource.slice(
      sidebarSource.indexOf('const researchGroup = ['),
      sidebarSource.indexOf('function resolveTarget'),
    )
    const resolved = router.resolve('/workspace/research/review')

    expect(resolved.name).toBe('ResearchReviewWorkspace')
    expect(resolved.matched.at(-1)?.components?.default).toBe(ResearchReviewWorkspacePage)
    expect(researchGroupSource).toContain("label: '审核工作台'")
    expect(researchGroupSource).toContain("target: '/workspace/research/review'")
    expect(researchGroupSource).not.toContain('registry?tab=review')
  })
})
