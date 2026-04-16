// RelationListPage live/demo roundtrip.
// Mock services/api/registryApi — the live provider wraps those functions.

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listCrossRelationsMock = vi.fn()
const listRegistryConceptsMock = vi.fn()
vi.mock('../../services/api/registryApi', () => ({
  // Reads (the live provider wraps these):
  listCrossRelations: (...a) => listCrossRelationsMock(...a),
  listRegistryConcepts: (...a) => listRegistryConceptsMock(...a),
  // Writes (stay live — stub to prevent accidental real calls):
  discoverCrossRelations: vi.fn(),
  getCrossRelation: vi.fn(),
  getCrossRelationCounts: vi.fn(),
  getRegistryConcept: vi.fn(),
  updateCrossRelation: vi.fn(),
  deleteCrossRelation: vi.fn(),
  createRegistryConcept: vi.fn(),
  updateRegistryConcept: vi.fn(),
  deleteRegistryConcept: vi.fn(),
  linkProjectConcept: vi.fn(),
  unlinkProjectConcept: vi.fn(),
  searchRegistryConcepts: vi.fn(),
  suggestFromProject: vi.fn(),
  getProjectAlignment: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {}, path: '/workspace/relations' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import RelationListPage from '../RelationListPage/RelationListPage.vue'
import { setMode } from '../../runtime/appMode'

enableAutoUnmount(afterEach)

const liveRelations = [
  {
    relation_id: 'rel_live_1',
    source_entry_id: 'ea',
    target_entry_id: 'eb',
    source_name: 'Entry A',
    target_name: 'Entry B',
    relation_type: 'related_to',
    confidence: 0.8,
    source: 'llm',
    review_status: 'pending',
    created_at: '2026-04-13T00:00:00Z',
    directionality: 'directed',
  },
]
const liveEntries = [
  { entry_id: 'ea', canonical_name: 'Entry A', concept_type: 'Technology' },
  { entry_id: 'eb', canonical_name: 'Entry B', concept_type: 'Concept' },
]

describe('RelationListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    listCrossRelationsMock.mockResolvedValue({ data: liveRelations })
    listRegistryConceptsMock.mockResolvedValue({ data: { entries: liveEntries } })
  })

  it('renders live relations on mount', async () => {
    const wrapper = mount(RelationListPage, {
      global: { mocks: { $route: { fullPath: '/workspace/relations' } } },
    })
    await flushPromises()
    expect(listCrossRelationsMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Entry A')
    expect(wrapper.text()).toContain('Entry B')
  })

  it('demo mode renders fixture relations without invoking live api mock', async () => {
    setMode('demo')
    const wrapper = mount(RelationListPage, {
      global: { mocks: { $route: { fullPath: '/workspace/relations' } } },
    })
    await flushPromises()
    expect(listCrossRelationsMock).not.toHaveBeenCalled()
    expect(listRegistryConceptsMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toMatch(/(OpenTelemetry|调用链追踪|端到端时延)/)
  })

  it('roundtrip live → demo → live reloads each way', async () => {
    const wrapper = mount(RelationListPage, {
      global: { mocks: { $route: { fullPath: '/workspace/relations' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Entry A')
    const liveHits = listCrossRelationsMock.mock.calls.length
    expect(liveHits).toBe(1)

    setMode('demo')
    await flushPromises()
    expect(wrapper.text()).not.toContain('Entry A')
    expect(wrapper.text()).toMatch(/(OpenTelemetry|端到端时延)/)
    expect(listCrossRelationsMock.mock.calls.length).toBe(liveHits)

    setMode('live')
    await flushPromises()
    expect(wrapper.text()).toContain('Entry A')
    expect(listCrossRelationsMock.mock.calls.length).toBe(liveHits + 1)
  })
})
