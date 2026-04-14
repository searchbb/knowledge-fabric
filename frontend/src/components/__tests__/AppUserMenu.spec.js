/*
 * AppUserMenu — 组件测试
 *
 * 重点:
 * 1. 点 trigger 打开 panel
 * 2. ESC 关
 * 3. 点外部关
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

async function loadFresh() {
  vi.resetModules()
  const m = await import('../common/AppUserMenu.vue')
  return m.default
}

describe('AppUserMenu', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
  })
  afterEach(() => {
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
  })

  it('初始关闭,trigger 可见', async () => {
    const AppUserMenu = await loadFresh()
    const wrapper = mount(AppUserMenu, { attachTo: document.body })
    expect(wrapper.find('.user-menu-trigger').exists()).toBe(true)
    expect(wrapper.find('.user-menu-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('点 trigger 打开 panel', async () => {
    const AppUserMenu = await loadFresh()
    const wrapper = mount(AppUserMenu, { attachTo: document.body })
    await wrapper.find('.user-menu-trigger').trigger('click')
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(true)
    wrapper.unmount()
  })

  it('打开后再点 trigger 关闭 panel', async () => {
    const AppUserMenu = await loadFresh()
    const wrapper = mount(AppUserMenu, { attachTo: document.body })
    const trig = wrapper.find('.user-menu-trigger')
    await trig.trigger('click')
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(true)
    await trig.trigger('click')
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('ESC 关闭已打开的菜单', async () => {
    const AppUserMenu = await loadFresh()
    const wrapper = mount(AppUserMenu, { attachTo: document.body })
    await wrapper.find('.user-menu-trigger').trigger('click')
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(true)
    const ev = new KeyboardEvent('keydown', { key: 'Escape' })
    document.dispatchEvent(ev)
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('点外部关闭已打开的菜单', async () => {
    const AppUserMenu = await loadFresh()
    const wrapper = mount(AppUserMenu, { attachTo: document.body })
    await wrapper.find('.user-menu-trigger').trigger('click')
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(true)
    // 在 document.body 上触发 mousedown,其 target 不在 rootEl 里
    const outsideTarget = document.createElement('div')
    document.body.appendChild(outsideTarget)
    const ev = new MouseEvent('mousedown', { bubbles: true })
    outsideTarget.dispatchEvent(ev)
    await nextTick()
    expect(wrapper.find('.user-menu-panel').exists()).toBe(false)
    outsideTarget.remove()
    wrapper.unmount()
  })
})
