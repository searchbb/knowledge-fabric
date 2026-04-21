// Knowledge Fabric Center app runtime mode.
//
// Two modes exist today:
//   - 'live' : the real backend (Flask + Neo4j + actual pipeline).
//   - 'demo' : local fixtures only. Useful for walking a stranger through
//              the product without depending on the backend being up, and
//              for quickly checking the UX from a fresh-eyes perspective.
//
// The mode is a reactive ref so pages can `watch(appMode, ...)` and
// re-fetch whatever they show when it flips.
//
// Default resolution order:
//   1. localStorage (user's last explicit choice)
//   2. import.meta.env.VITE_APP_MODE (useful for pinning a deployment to
//      'demo' on a public demo site)
//   3. 'live'

import { computed, ref } from 'vue'

export const APP_MODES = Object.freeze({
  LIVE: 'live',
  DEMO: 'demo',
})

const STORAGE_KEY = 'knowledge-fabric:app-mode'

function readInitialMode() {
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage?.getItem(STORAGE_KEY)
      if (stored === APP_MODES.LIVE || stored === APP_MODES.DEMO) {
        return stored
      }
    } catch (err) {
      // localStorage may be disabled (e.g. private browsing). Ignore.
    }
  }
  const envDefault = import.meta.env?.VITE_APP_MODE
  if (envDefault === APP_MODES.DEMO) return APP_MODES.DEMO
  return APP_MODES.LIVE
}

export const appMode = ref(readInitialMode())

export const isDemo = computed(() => appMode.value === APP_MODES.DEMO)
export const isLive = computed(() => appMode.value === APP_MODES.LIVE)

export function setMode(nextMode) {
  if (nextMode !== APP_MODES.LIVE && nextMode !== APP_MODES.DEMO) {
    console.warn('[appMode] ignoring unknown mode:', nextMode)
    return
  }
  if (appMode.value === nextMode) return
  appMode.value = nextMode
  try {
    window.localStorage?.setItem(STORAGE_KEY, nextMode)
  } catch (err) {
    // ignore persistence failure; in-memory state still flips
  }
}

export function toggleMode() {
  setMode(isDemo.value ? APP_MODES.LIVE : APP_MODES.DEMO)
}
