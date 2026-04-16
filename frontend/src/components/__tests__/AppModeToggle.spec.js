import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import AppModeToggle from '../common/AppModeToggle.vue'
import DemoBadge from '../common/DemoBadge.vue'
import { appMode, setMode } from '../../runtime/appMode'

describe('AppModeToggle', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setMode('live')
  })

  afterEach(() => {
    window.localStorage.clear()
    setMode('live')
  })

  it('renders both segments and marks the active one', () => {
    const wrapper = mount(AppModeToggle)
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toBe('Live')
    expect(buttons[1].text()).toBe('Demo')
    expect(buttons[0].classes()).toContain('active')
    expect(buttons[1].classes()).not.toContain('active')
  })

  it('clicking Demo flips appMode and updates active state', async () => {
    const wrapper = mount(AppModeToggle)
    await wrapper.findAll('button')[1].trigger('click')
    expect(appMode.value).toBe('demo')

    const buttons = wrapper.findAll('button')
    expect(buttons[0].classes()).not.toContain('active')
    expect(buttons[1].classes()).toContain('active')
  })

  it('clicking Live flips back', async () => {
    setMode('demo')
    const wrapper = mount(AppModeToggle)
    await wrapper.findAll('button')[0].trigger('click')
    expect(appMode.value).toBe('live')
  })

  it('persists choice in localStorage so reloads remember it', async () => {
    const wrapper = mount(AppModeToggle)
    await wrapper.findAll('button')[1].trigger('click')
    expect(window.localStorage.getItem('knowledge-fabric:app-mode')).toBe('demo')
  })
})

describe('DemoBadge', () => {
  beforeEach(() => {
    setMode('live')
  })

  it('does not render in live mode', () => {
    const wrapper = mount(DemoBadge)
    expect(wrapper.find('.demo-badge').exists()).toBe(false)
  })

  it('renders in demo mode', async () => {
    setMode('demo')
    const wrapper = mount(DemoBadge)
    expect(wrapper.find('.demo-badge').exists()).toBe(true)
    expect(wrapper.text()).toContain('Demo mode')
  })
})
