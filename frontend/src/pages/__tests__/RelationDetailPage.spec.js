// RelationDetailPage live/demo roundtrip + degradation.
// Mock services/api/registryApi — the live provider wraps these.

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getCrossRelationMock = vi.fn()
const getRegistryConceptMock = vi.fn()
vi.mock('../../services/api/registryApi', () => ({
  // Reads (live-provider wraps):
  getCrossRelation: (...a) => getCrossRelationMock(...a),
  getRegistryConcept: (...a) => getRegistryConceptMock(...a),
  // Writes and other reads (stubbed):
  updateCrossRelation: vi.fn(),
  deleteCrossRelation: vi.fn(),
  listCrossRelations: vi.fn(),
  listRegistryConcepts: vi.fn(),
  discoverCrossRelations: vi.fn(),
  getCrossRelationCounts: vi.fn(),
  createRegistryConcept: vi.fn(),
  updateRegistryConcept: vi.fn(),
  deleteRegistryConcept: vi.fn(),
  linkProjectConcept: vi.fn(),
  unlinkProjectConcept: vi.fn(),
  searchRegistryConcepts: vi.fn(),
  suggestFromProject: vi.fn(),
  getProjectAlignment: vi.fn(),
}))

const routeState = {
  params: { relationId: 'rel_live_1' },
  query: {},
  path: '/workspace/relations/rel_live_1',
}
vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import RelationDetailPage from '../RelationDetailPage/RelationDetailPage.vue'
import { setMode } from '../../runtime/appMode'

enableAutoUnmount(afterEach)

function makeLiveRelation() {
  return {
    data: {
      relation_id: 'rel_live_1',
      source_entry_id: 'ea',
      target_entry_id: 'eb',
      source_name: 'Source Alpha',
      target_name: 'Target Beta',
      source_entry: { canonical_name: 'Source Alpha', concept_type: 'Technology' },
      target_entry: { canonical_name: 'Target Beta', concept_type: 'Concept' },
      relation_type: 'related_to',
      confidence: 0.85,
      source: 'llm',
      review_status: 'pending',
      reason: 'live reason',
      created_at: '2026-04-13T00:00:00Z',
      directionality: 'directed',
      evidence_bridge: null,
      evidence_refs: [],
      discovery_path: 'live',
    },
  }
}

describe('RelationDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    setMode('live')
    routeState.params.relationId = 'rel_live_1'
    getCrossRelationMock.mockResolvedValue(makeLiveRelation())
    getRegistryConceptMock.mockResolvedValue({ data: {} })
  })

  it('loads live relation on mount', async () => {
    const wrapper = mount(RelationDetailPage, {
      global: { mocks: { $route: { fullPath: routeState.path } } },
    })
    await flushPromises()
    expect(getCrossRelationMock).toHaveBeenCalledWith('rel_live_1')
    expect(wrapper.text()).toContain('Source Alpha')
    expect(wrapper.text()).toContain('Target Beta')
  })

  it('demo mode loads a real fixture relation (live mock not called)', async () => {
    routeState.params.relationId = 'rel-otel-tracing'
    setMode('demo')
    const wrapper = mount(RelationDetailPage, {
      global: { mocks: { $route: { fullPath: '/workspace/relations/rel-otel-tracing' } } },
    })
    await flushPromises()
    expect(getCrossRelationMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('OpenTelemetry')
    expect(wrapper.text()).toContain('调用链追踪')
  })

  it('degrades gracefully when relationId has no demo fixture', async () => {
    routeState.params.relationId = 'rel-does-not-exist'
    setMode('demo')
    const wrapper = mount(RelationDetailPage, {
      global: { mocks: { $route: { fullPath: '/workspace/relations/rel-does-not-exist' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toMatch(/Demo data not available/)
  })

  it('roundtrip live(valid) → demo(missing) → live(valid)', async () => {
    const wrapper = mount(RelationDetailPage, {
      global: { mocks: { $route: { fullPath: routeState.path } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Source Alpha')
    expect(getCrossRelationMock).toHaveBeenCalledTimes(1)

    setMode('demo')
    await flushPromises()
    expect(getCrossRelationMock).toHaveBeenCalledTimes(1) // untouched
    expect(wrapper.text()).toMatch(/Demo data not available/)

    setMode('live')
    await flushPromises()
    expect(getCrossRelationMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Source Alpha')
  })
})
