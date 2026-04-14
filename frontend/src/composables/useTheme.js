/*
 * useTheme composable
 *
 * 组件里用:
 *   const { currentId, currentTheme, themes, setTheme } = useTheme()
 */

import { computed } from 'vue'
import { uiThemeStore, setTheme, getTheme, THEMES } from '../stores/uiThemeStore'

export function useTheme() {
  const currentId = computed(() => uiThemeStore.currentId)
  const currentTheme = computed(() => getTheme(uiThemeStore.currentId))
  return {
    currentId,
    currentTheme,
    themes: THEMES,
    setTheme,
  }
}
