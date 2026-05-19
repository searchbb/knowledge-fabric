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

const root = resolve(process.cwd(), 'src')
const workspacePagePath = resolve(root, 'pages', 'research', 'ResearchReviewWorkspacePage.vue')
const p25DocPath = resolve(process.cwd(), '..', 'docs', 'research', 'p25_research_review_workspace_boundary_hardening.md')
const p26DocPath = resolve(process.cwd(), '..', 'docs', 'research', 'p26_research_review_workspace_design_completion.md')

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

describe('research review workspace completion contract', () => {
  beforeEach(() => {
    listResearchProjects.mockReset()
    listGovernanceReviews.mockReset()
    listResearchSnapshots.mockReset()
    listReviewHistory.mockReset()
    listResearchProjects.mockResolvedValue({
      data: {
        projects: [
          { id: 'rp_completion', title: 'Completion Project', status: 'active', goal: 'Close the workspace line.' },
        ],
      },
    })
    listGovernanceReviews.mockResolvedValue({
      data: {
        governance_reviews: [
          { review_id: 'gr_completion', title: 'Completion governance review', status: 'in_review', readiness: 'partial' },
        ],
      },
    })
    listResearchSnapshots.mockResolvedValue({
      data: {
        snapshots: [
          { snapshot_id: 'rs_completion', title: 'Completion snapshot', status: 'indexed' },
        ],
      },
    })
    listReviewHistory.mockResolvedValue({
      data: {
        review_history_entries: Array.from({ length: 7 }, (_, index) => ({
          history_entry_id: `rhe_completion_${index}`,
          event_type: `completion_event_${index}`,
          asset_type: 'governance_review',
          asset_id: `gr_completion_${index}`,
        })),
      },
    })
  })

  it('declares the Review Workspace design line complete and stopped', () => {
    expect(existsSync(p26DocPath)).toBe(true)
    const doc = readSource(p26DocPath)

    expect(doc).toContain('Design Line Status: Complete')
    expect(doc).toContain('P26 closes the P22-P26 Research Review Workspace design line')
    expect(doc).toContain('Stop Rule')
    expect(doc).toContain('After P26 acceptance, stop the P22-P26 Review Workspace design line')
    expect(doc).toContain('Future GovernanceReview product capabilities must begin as a new design line')
    expect(doc).toContain('They must not be implemented as more Review Workspace hardening')
  })

  it('records the existing API, read-only, and architectural completion boundaries', () => {
    const doc = readSource(p26DocPath)
    const requiredPhrases = [
      'Existing API Boundary',
      'listResearchProjects',
      'listGovernanceReviews',
      'listResearchSnapshots',
      'listReviewHistory',
      'Read-Only Boundary',
      'KFC / Knowledge Fabric remains the research asset and provenance repository',
      'Codex, skills, and external workflow tools own orchestration and execution',
      'P22-P26 closes only the Review Workspace surface',
    ]

    for (const phrase of requiredPhrases) {
      expect(doc).toContain(phrase)
    }
  })

  it('makes deferred surfaces explicit instead of treating them as missing requirements', () => {
    const doc = readSource(p26DocPath)
    const deferred = [
      'traceability summary',
      'readiness scoring',
      'workflow',
      'assignment',
      'scheduler',
      'queue',
      'worker',
      'DAG',
      'model runtime',
      'automatic gate decision',
      'persisted read model',
      'orchestration inside KFC',
    ]

    expect(doc).toContain('The other surfaces are intentionally deferred')
    expect(doc).toContain('They are not missing requirements for this completed design line')
    for (const item of deferred) {
      expect(doc).toContain(item)
    }
  })

  it('keeps the completed production surface on the four existing read APIs', () => {
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
    expect(source).toContain('listReviewHistory(project.id, { limit: 5 })')
    expect(source).not.toMatch(/localStorage|sessionStorage|indexedDB|writeback|persistedReviewWorkspace|reviewWorkspaceReadModel/)
    expect(source).not.toMatch(/\b(create|update|delete|submit|approve|reject|assign|evaluate|execute|schedule|run|sync|save|generate)[A-Z][A-Za-z0-9_]*\s*\(/)
  })

  it('keeps the completed surface separate from prototype and frozen attention files', () => {
    const source = readSource(workspacePagePath)
    const resolved = router.resolve('/workspace/research/review')

    expect(resolved.name).toBe('ResearchReviewWorkspace')
    expect(resolved.matched.at(-1)?.components?.default).toBe(ResearchReviewWorkspacePage)
    expect(source).not.toMatch(/ReviewPage\.vue|pages\/ReviewPage|@\/pages\/ReviewPage/)
    expect(source).not.toMatch(/snapshotReviewNoteRollup|gateReviewSnapshotAttentionContext|GateReviewSnapshotAttentionContext/)
  })

  it('renders the completed workspace as bounded passive inspection UI', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('研究审核工作台')
    expect(wrapper.text()).toContain('Completion Project')
    expect(wrapper.text()).toContain('Completion governance review')
    expect(wrapper.text()).toContain('Completion snapshot')
    expect(wrapper.text()).toContain('completion_event_0')
    expect(wrapper.text()).toContain('completion_event_4')
    expect(wrapper.text()).not.toContain('completion_event_5')
    expect(wrapper.text()).not.toContain('completion_event_6')
    expect(listReviewHistory).toHaveBeenCalledWith('rp_completion', { limit: 5 })
  })

  it('keeps completion UI free of mutation and runtime controls', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const actionSurfaceText = [
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
    expect(actionSurfaceText).not.toMatch(/Approve|Reject|Submit|Sign off|Assign|Route|Start|Run|Execute|Schedule|Score|Decide|Generate|Sync|Save|Delete|Edit/i)
    expect(wrapper.emitted()).toEqual({})
  })

  it('keeps P25 and P26 completion contracts aligned', () => {
    const p25Doc = readSource(p25DocPath)
    const p26Doc = readSource(p26DocPath)

    expect(p25Doc).toContain('Research Review Workspace Design Completion / Exit Criteria Baseline')
    expect(p26Doc).toContain('P26 completion contract tests pass')
    expect(p26Doc).toContain('browser read-only scenario passes')
    expect(p26Doc).toContain('GPT acceptance passes')
  })
})
