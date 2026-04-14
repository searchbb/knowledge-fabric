/*
 * ThemeSwitcher — 组件测试
 *
 * 重点:
 * 1. 卡片数量 = THEMES 长度(不 hardcode),扩到 5/7 张都能自动
 * 2. 当前主题的卡片有 active 态
 * 3. 点非当前卡片触发 setTheme
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// 每个 it 独立拿新模块实例,避免全局 store 串扰
async function loadWithFreshStore() {
  vi.resetModules()
  const storeModule = await import('../../stores/uiThemeStore.js')
  const componentModule = await import('../settings/ThemeSwitcher.vue')
  return { storeModule, ThemeSwitcher: componentModule.default }
}

describe('ThemeSwitcher', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
  })
  afterEach(() => {
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
  })

  it('渲染一张卡片 per THEMES item(数量随 THEMES 变化)', async () => {
    const { storeModule, ThemeSwitcher } = await loadWithFreshStore()
    const wrapper = mount(ThemeSwitcher)
    const cards = wrapper.findAll('.theme-card')
    expect(cards.length).toBe(storeModule.THEMES.length)
  })

  it('每张卡片展示 name/nameEn/blurb', async () => {
    const { storeModule, ThemeSwitcher } = await loadWithFreshStore()
    const wrapper = mount(ThemeSwitcher)
    const cards = wrapper.findAll('.theme-card')
    for (let i = 0; i < cards.length; i++) {
      const t = storeModule.THEMES[i]
      const text = cards[i].text()
      expect(text).toContain(t.name)
      expect(text).toContain(t.nameEn)
      expect(text).toContain(t.blurb)
    }
  })

  it('默认主题 ivory-study 的卡片有 active 类', async () => {
    const { ThemeSwitcher } = await loadWithFreshStore()
    const wrapper = mount(ThemeSwitcher)
    const active = wrapper.findAll('.theme-card.active')
    expect(active.length).toBe(1)
    expect(active[0].text()).toContain('米色文房')
  })

  it('点击非当前卡片后 setTheme 生效,DOM attr 更新', async () => {
    const { ThemeSwitcher } = await loadWithFreshStore()
    const wrapper = mount(ThemeSwitcher)
    const cards = wrapper.findAll('.theme-card')
    // 找到"夜读墨屏"卡片
    const nightIdx = cards.findIndex(c => c.text().includes('夜读墨屏'))
    expect(nightIdx).toBeGreaterThanOrEqual(0)
    await cards[nightIdx].trigger('click')
    await nextTick()
    expect(document.documentElement.getAttribute('data-theme')).toBe('night-scholar')
    // 重新渲染后 active 应切换到夜读
    const active = wrapper.findAll('.theme-card.active')
    expect(active.length).toBe(1)
    expect(active[0].text()).toContain('夜读墨屏')
  })

  it('有 aria-checked 和 role="radio" 便于辅助技术识别', async () => {
    const { ThemeSwitcher } = await loadWithFreshStore()
    const wrapper = mount(ThemeSwitcher)
    const cards = wrapper.findAll('[role="radio"]')
    expect(cards.length).toBeGreaterThan(0)
    const checked = cards.filter(c => c.attributes('aria-checked') === 'true')
    expect(checked.length).toBe(1)
  })
})
