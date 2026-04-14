/*
 * uiThemeStore — 单元测试
 *
 * 注意:store 在 import 时读初始主题(readInitialId 是模块顶级),
 * 所以测不同初始态要用 vi.resetModules() + 动态 import 每次拿全新模块。
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const STORAGE_KEY = 'gewu-ui-theme'

async function loadFreshStore() {
  vi.resetModules()
  return import('../uiThemeStore.js')
}

describe('uiThemeStore', () => {
  beforeEach(() => {
    // jsdom document 默认不带 data-theme,localStorage 干净
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
  })

  afterEach(() => {
    document.documentElement.removeAttribute('data-theme')
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('THEMES 常量', () => {
    it('有 5 套主题且 id 唯一', async () => {
      const { THEMES } = await loadFreshStore()
      expect(THEMES).toHaveLength(5)
      const ids = THEMES.map(t => t.id)
      expect(new Set(ids).size).toBe(5)
    })

    it('每套主题都有 id/name/nameEn/blurb/swatch 字段', async () => {
      const { THEMES } = await loadFreshStore()
      for (const t of THEMES) {
        expect(t.id).toMatch(/^[a-z-]+$/)
        expect(t.name).toBeTruthy()
        expect(t.nameEn).toBeTruthy()
        expect(t.blurb).toBeTruthy()
        expect(Array.isArray(t.swatch)).toBe(true)
        expect(t.swatch.length).toBeGreaterThanOrEqual(3)
      }
    })

    it('getTheme(id) 返回对应主题,未知 id 回退到首个', async () => {
      const { getTheme, THEMES } = await loadFreshStore()
      expect(getTheme('night-scholar').id).toBe('night-scholar')
      expect(getTheme('not-a-real-theme')).toBe(THEMES[0])
    })
  })

  describe('初始值优先级', () => {
    it('document[data-theme] 优先于 localStorage', async () => {
      document.documentElement.setAttribute('data-theme', 'blue-ledger')
      localStorage.setItem(STORAGE_KEY, 'night-scholar')
      const { uiThemeStore } = await loadFreshStore()
      expect(uiThemeStore.currentId).toBe('blue-ledger')
    })

    it('没有 document attr 时读 localStorage', async () => {
      localStorage.setItem(STORAGE_KEY, 'night-scholar')
      const { uiThemeStore } = await loadFreshStore()
      expect(uiThemeStore.currentId).toBe('night-scholar')
    })

    it('都没有时回退到默认 ivory-study', async () => {
      const { uiThemeStore } = await loadFreshStore()
      expect(uiThemeStore.currentId).toBe('ivory-study')
    })

    it('document attr 是非法 id 时不被信任,降级到 localStorage / 默认', async () => {
      document.documentElement.setAttribute('data-theme', 'bogus-theme')
      localStorage.setItem(STORAGE_KEY, 'night-scholar')
      const { uiThemeStore } = await loadFreshStore()
      expect(uiThemeStore.currentId).toBe('night-scholar')
    })

    it('localStorage 是非法 id 时降级到默认', async () => {
      localStorage.setItem(STORAGE_KEY, 'bogus-theme')
      const { uiThemeStore } = await loadFreshStore()
      expect(uiThemeStore.currentId).toBe('ivory-study')
    })
  })

  describe('setTheme', () => {
    it('合法 id:更新 state + DOM attr + localStorage', async () => {
      const { uiThemeStore, setTheme } = await loadFreshStore()
      setTheme('night-scholar')
      expect(uiThemeStore.currentId).toBe('night-scholar')
      expect(document.documentElement.getAttribute('data-theme')).toBe('night-scholar')
      expect(localStorage.getItem(STORAGE_KEY)).toBe('night-scholar')
    })

    it('非法 id:no-op,state/DOM/storage 都不动', async () => {
      const { uiThemeStore, setTheme } = await loadFreshStore()
      const before = uiThemeStore.currentId
      setTheme('hacker-theme')
      expect(uiThemeStore.currentId).toBe(before)
      expect(document.documentElement.getAttribute('data-theme')).toBeNull()
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
    })

    it('切来切去:state 随最后一次调用', async () => {
      const { uiThemeStore, setTheme } = await loadFreshStore()
      setTheme('night-scholar')
      setTheme('blue-ledger')
      setTheme('sepia-archive')
      expect(uiThemeStore.currentId).toBe('sepia-archive')
    })

    it('localStorage.setItem 抛错(private mode 模拟):不崩,state/DOM 仍更新', async () => {
      const { uiThemeStore, setTheme } = await loadFreshStore()
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('QuotaExceededError')
      })
      expect(() => setTheme('ink-wash')).not.toThrow()
      expect(uiThemeStore.currentId).toBe('ink-wash')
      expect(document.documentElement.getAttribute('data-theme')).toBe('ink-wash')
    })
  })
})
