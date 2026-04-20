// CollapsibleCard — reusable <details>-based wrapper used by
// AutoPipelinePage to shorten the vertical footprint of low-attention
// blocks. Behaviour under test:
//   - respects defaultOpen on first render when no localStorage entry
//   - reads + writes localStorage on toggle (key = `storageKey`)
//   - forceOpen overrides defaultOpen only until the user has manually
//     toggled once (tracked via `${storageKey}:touched`)
//   - renders title + badge + subtitle + #summary-extra slot + default
//     slot

import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import CollapsibleCard from '../common/CollapsibleCard.vue'

enableAutoUnmount(afterEach)

beforeEach(() => {
  localStorage.clear()
})

// jsdom doesn't implement the native <details> click→toggle default
// action, so a plain summary click doesn't flip details.open or fire a
// toggle event. This helper simulates what a real browser does when a
// user clicks a summary: flip open, then dispatch the toggle event that
// the component's `@toggle` handler actually listens for.
async function userToggle(wrapper) {
  const details = wrapper.find('details').element
  details.open = !details.open
  details.dispatchEvent(new Event('toggle'))
  await wrapper.vm.$nextTick()
}

describe('CollapsibleCard', () => {
  it('renders closed by default when defaultOpen is false', () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:a', title: 'Hello' },
      slots: { default: '<p class="body">Body text</p>' },
    })
    expect(wrapper.find('details').element.open).toBe(false)
    expect(wrapper.find('.cc-title').text()).toBe('Hello')
  })

  it('renders open when defaultOpen=true and no stored value', () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:b', title: 'X', defaultOpen: true },
    })
    expect(wrapper.find('details').element.open).toBe(true)
  })

  it('restores state from localStorage over defaultOpen', () => {
    localStorage.setItem('test:c', 'open')
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:c', title: 'X', defaultOpen: false },
    })
    expect(wrapper.find('details').element.open).toBe(true)
  })

  it('writes localStorage on toggle', async () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:d', title: 'X' },
    })
    await userToggle(wrapper)
    expect(localStorage.getItem('test:d')).toBe('open')
    expect(localStorage.getItem('test:d:touched')).toBe('1')
  })

  it('does not mark touched when forceOpen causes a programmatic open', async () => {
    // Mount with forceOpen=false initially, then flip to true via prop
    // update. This simulates errored.length going 0 → 1 via a backend
    // poll — the programmatic toggle that follows must NOT count as a
    // user gesture, otherwise the forceOpen gate is defeated forever.
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:prog', title: 'X', forceOpen: false },
    })
    expect(wrapper.find('details').element.open).toBe(false)
    expect(localStorage.getItem('test:prog:touched')).toBe(null)

    // Programmatic open via forceOpen flip. Vue updates the :open
    // binding, which (in a real browser) would fire a toggle event.
    // Simulate that here so the component's suppression path runs.
    await wrapper.setProps({ forceOpen: true })
    expect(wrapper.find('details').element.open).toBe(true)
    wrapper.find('details').element.dispatchEvent(new Event('toggle'))
    await wrapper.vm.$nextTick()

    // Programmatic open must NOT mark user as having touched.
    expect(localStorage.getItem('test:prog:touched')).toBe(null)
    expect(localStorage.getItem('test:prog')).toBe(null)

    // A real user gesture afterwards IS still recorded as a touch.
    await userToggle(wrapper)
    expect(localStorage.getItem('test:prog:touched')).toBe('1')
  })

  it('forceOpen overrides defaultOpen before user touches it', () => {
    const wrapper = mount(CollapsibleCard, {
      props: {
        storageKey: 'test:e',
        title: 'X',
        defaultOpen: false,
        forceOpen: true,
      },
    })
    expect(wrapper.find('details').element.open).toBe(true)
  })

  it('forceOpen is ignored once user has touched', async () => {
    localStorage.setItem('test:f', 'closed')
    localStorage.setItem('test:f:touched', '1')
    const wrapper = mount(CollapsibleCard, {
      props: {
        storageKey: 'test:f',
        title: 'X',
        forceOpen: true,
      },
    })
    expect(wrapper.find('details').element.open).toBe(false)
  })

  it('renders the badge slot content', () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:g', title: 'X', badge: 42 },
    })
    expect(wrapper.find('.cc-badge').text()).toBe('42')
  })

  it('renders the summary-extra slot alongside the title', () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:h', title: 'X' },
      slots: { 'summary-extra': '<span class="extra">Always visible</span>' },
    })
    expect(wrapper.find('.extra').exists()).toBe(true)
  })

  it('renders numeric 0 as a badge (does not hide zero counts)', () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:zero', title: 'X', badge: 0 },
    })
    expect(wrapper.find('.cc-badge').exists()).toBe(true)
    expect(wrapper.find('.cc-badge').text()).toBe('0')
  })

  it('renders the subtitle when provided', () => {
    const wrapper = mount(CollapsibleCard, {
      props: { storageKey: 'test:sub', title: 'X', subtitle: 'Hello subtitle' },
    })
    expect(wrapper.find('.cc-subtitle').text()).toBe('Hello subtitle')
  })

  it('round-trips toggle state through localStorage across mounts', async () => {
    // First mount: user clicks open, then tear down.
    const first = mount(CollapsibleCard, {
      props: { storageKey: 'test:roundtrip', title: 'X' },
    })
    await userToggle(first)
    first.unmount()

    // Second mount with the same key: should come up open.
    const second = mount(CollapsibleCard, {
      props: { storageKey: 'test:roundtrip', title: 'X' },
    })
    expect(second.find('details').element.open).toBe(true)
  })
})
