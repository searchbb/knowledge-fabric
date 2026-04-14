/*
 * uiThemeStore
 *
 * 注意:这是 *UI 皮肤* store,跟 stores/themeStore.js(领域里的"主题/话题 hub")
 * 完全无关。命名保留 "ui" 前缀避免混淆。
 *
 * 单一职责:维护当前主题 id + 持久化到 localStorage + 把 data-theme 写到 <html>。
 * 组件不关心怎么写 DOM,只调用 setTheme(id)。
 */

import { reactive } from 'vue'

export const THEMES = [
  {
    id: 'ivory-study',
    name: '米色文房',
    nameEn: 'Ivory Study',
    blurb: '延续纸本研究笔记的气质',
    swatch: ['#fff9ef', '#eadfcb', '#bf7d28', '#3b342a'],
  },
  {
    id: 'night-scholar',
    name: '夜读墨屏',
    nameEn: 'Night Scholar',
    blurb: '灯下读札记,长时间阅读护眼',
    swatch: ['#151311', '#26211d', '#d6a15a', '#eee6da'],
  },
  {
    id: 'blue-ledger',
    name: '冷色学术',
    nameEn: 'Blue Ledger',
    blurb: '理性清静,偏结构整理和分析',
    swatch: ['#f5f8fc', '#d6dfec', '#3a6ea5', '#1f2a37'],
  },
  {
    id: 'ink-wash',
    name: '水墨留白',
    nameEn: 'Ink Wash',
    blurb: '极简黑白灰,纯阅读与截图友好',
    swatch: ['#fafaf7', '#e1ded6', '#262420', '#7c7468'],
  },
  {
    id: 'sepia-archive',
    name: '旧档案',
    nameEn: 'Sepia Archive',
    blurb: '复古研究室、卡片目录的感觉',
    swatch: ['#f6eedc', '#d6c39a', '#8a5a44', '#4b3a2a'],
  },
]

const VALID_IDS = THEMES.map((t) => t.id)
const STORAGE_KEY = 'gewu-ui-theme'
const DEFAULT_ID = 'ivory-study'

function readInitialId() {
  // 运行时读:优先信任 <html data-theme>(首屏同步脚本写过),否则 localStorage,最后默认。
  if (typeof document !== 'undefined') {
    const attr = document.documentElement.getAttribute('data-theme')
    if (attr && VALID_IDS.includes(attr)) return attr
  }
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && VALID_IDS.includes(saved)) return saved
  } catch (e) {
    /* ignore */
  }
  return DEFAULT_ID
}

export const uiThemeStore = reactive({
  currentId: readInitialId(),
})

export function setTheme(id) {
  if (!VALID_IDS.includes(id)) return
  uiThemeStore.currentId = id
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', id)
  }
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch (e) {
    /* ignore quota/private-mode errors — 下次开页还是用首屏脚本的默认值 */
  }
}

export function getTheme(id) {
  return THEMES.find((t) => t.id === id) || THEMES[0]
}
