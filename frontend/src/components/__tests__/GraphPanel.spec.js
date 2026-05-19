import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import GraphPanel from '../GraphPanel.vue'
import { lookupConceptByProject } from '../../services/api/registryApi'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { projectId: 'proj_6b877d2807eb' } }),
}))

vi.mock('../../services/api/registryApi', () => ({
  lookupConceptByProject: vi.fn(),
}))

enableAutoUnmount(afterEach)
afterEach(() => {
  vi.useRealTimers()
})

const graphData = {
  nodes: [
    {
      uuid: 'node-fde',
      name: 'FDE 模式',
      labels: ['Entity', 'Method'],
      summary: 'FDE 模式是一种需求梳理方法。',
      attributes: {},
    },
    {
      uuid: 'node-other',
      name: '其他方法',
      labels: ['Entity', 'Method'],
      summary: '其他方法 summary。',
      attributes: {},
    },
  ],
  edges: [],
}

describe('GraphPanel node-select events', () => {
  beforeEach(() => {
    lookupConceptByProject.mockResolvedValue({ data: null })
  })

  it('emits node-select when the focusNodeKey matches an existing node', async () => {
    vi.useFakeTimers()
    const wrapper = mount(GraphPanel, {
      props: {
        graphData,
        initialView: 'graph',
        focusNodeKey: 'Method:FDE+模式',
        readingStructure: {
          group_titles: { Method: '关键方法' },
        },
      },
      attachTo: document.body,
    })

    await vi.runAllTimersAsync()
    await flushPromises()

    const events = wrapper.emitted('node-select') || []
    expect(events.length).toBeGreaterThan(0)
    expect(events.at(-1)[0]).toMatchObject({
      key: 'Method:FDE 模式',
      uuid: 'node-fde',
      name: 'FDE 模式',
      labels: ['Method'],
      readingSectionLabel: '关键方法',
    })
    vi.useRealTimers()
  })

  it('emits node-select when a user clicks a graph node', async () => {
    const wrapper = mount(GraphPanel, {
      props: {
        graphData,
        initialView: 'graph',
        readingStructure: {
          group_titles: { Method: '关键方法' },
        },
      },
      attachTo: document.body,
    })
    await flushPromises()

    await wrapper.find('circle').trigger('click')
    await flushPromises()

    const events = wrapper.emitted('node-select') || []
    expect(events.length).toBe(1)
    expect(events[0][0]).toMatchObject({
      key: 'Method:FDE 模式',
      uuid: 'node-fde',
      name: 'FDE 模式',
      labels: ['Method'],
    })
  })
})
