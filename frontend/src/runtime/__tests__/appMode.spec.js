// Tests for the appMode runtime module.
//
// Each test reloads the module fresh via `vi.resetModules()` so the
// initial-mode resolution logic runs under the test's localStorage/env
// setup rather than whatever happened in a previous test.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const STORAGE_KEY = 'knowledge-fabric:app-mode'

async function loadFreshModule() {
  vi.resetModules()
  return await import('../appMode.js')
}

describe('appMode', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.unstubAllEnvs()
  })

  afterEach(() => {
    window.localStorage.clear()
    vi.unstubAllEnvs()
  })

  it('defaults to live when nothing is configured', async () => {
    const { appMode, isLive, isDemo } = await loadFreshModule()
    expect(appMode.value).toBe('live')
    expect(isLive.value).toBe(true)
    expect(isDemo.value).toBe(false)
  })

  it('honours VITE_APP_MODE=demo as initial default', async () => {
    vi.stubEnv('VITE_APP_MODE', 'demo')
    const { appMode } = await loadFreshModule()
    expect(appMode.value).toBe('demo')
  })

  it('prefers localStorage over env when both are set', async () => {
    vi.stubEnv('VITE_APP_MODE', 'demo')
    window.localStorage.setItem(STORAGE_KEY, 'live')
    const { appMode } = await loadFreshModule()
    expect(appMode.value).toBe('live')
  })

  it('persists setMode to localStorage', async () => {
    const { setMode } = await loadFreshModule()
    setMode('demo')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('demo')
    setMode('live')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('live')
  })

  it('toggleMode flips between live and demo', async () => {
    const { appMode, toggleMode } = await loadFreshModule()
    expect(appMode.value).toBe('live')
    toggleMode()
    expect(appMode.value).toBe('demo')
    toggleMode()
    expect(appMode.value).toBe('live')
  })

  it('ignores unknown mode values', async () => {
    const { appMode, setMode } = await loadFreshModule()
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    setMode('banana')
    expect(appMode.value).toBe('live')
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})
