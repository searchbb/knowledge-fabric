/*
 * Token Contract — 确保每套主题定义了完整的 semantic token。
 *
 * 不走 jsdom computed styles(jsdom 对 CSS var 的层叠支持不稳),
 * 直接静态 parse 主题 CSS 文件,按 regex 抽取 token 并比对清单。
 */

import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const THEMES_DIR = path.resolve(__dirname, '../themes')

const THEME_FILES = {
  'ivory-study':   'ivory-study.css',
  'night-scholar': 'night-scholar.css',
  'blue-ledger':   'blue-ledger.css',
  'ink-wash':      'ink-wash.css',
  'sepia-archive': 'sepia-archive.css',
}

// 所有主题都必须定义的 token 清单。顺序无关,但不能漏项 / 不能拼错。
const REQUIRED_TOKENS = [
  // surfaces
  '--bg-app', '--bg-app-gradient', '--bg-canvas',
  '--bg-surface', '--bg-surface-2', '--bg-elevated',
  '--bg-muted', '--bg-selected',
  // text
  '--text-primary', '--text-secondary', '--text-muted', '--text-on-accent',
  // border
  '--border-default', '--border-strong', '--border-muted',
  // accent
  '--accent-primary', '--accent-primary-hover',
  '--accent-soft', '--accent-group-label', '--focus-ring',
  // state
  '--state-warning', '--state-danger',
  // input
  '--input-bg', '--input-border', '--input-border-focus',
  // reading
  '--reading-paper', '--reading-ink', '--reading-quote-bar',
  '--reading-code-bg', '--reading-code-border',
  '--reading-highlight-bg', '--reading-annotate', '--reading-divider',
  // reading code panel — 块级 pre / markdown-source,跟 inline code 分开
  '--reading-code-panel-bg', '--reading-code-panel-ink', '--reading-code-panel-border',
]

/**
 * 从 CSS 文本里抽取 html[data-theme="<id>"] 选择器块里定义的 token 名集合。
 * 只接受和文件对应的 theme id;防止一个文件里塞了别的主题 id 导致误判。
 */
function extractTokensForTheme(cssText, themeId) {
  // 匹配 html[data-theme="<id>"] { ... } 的内容块。'.*?' 非贪婪跨行。
  const blockRe = new RegExp(
    `html\\[data-theme="${themeId}"\\]\\s*\\{([\\s\\S]*?)\\n\\}`,
    'g',
  )
  const tokens = new Set()
  let match
  while ((match = blockRe.exec(cssText)) !== null) {
    const body = match[1]
    // 抽每一条 "--xxx-yyy:" 声明
    const declRe = /(--[a-z0-9-]+)\s*:/g
    let d
    while ((d = declRe.exec(body)) !== null) {
      tokens.add(d[1])
    }
  }
  return tokens
}

describe('Theme CSS contract', () => {
  for (const [themeId, filename] of Object.entries(THEME_FILES)) {
    describe(themeId, () => {
      const filepath = path.join(THEMES_DIR, filename)
      const cssText = fs.readFileSync(filepath, 'utf8')
      const defined = extractTokensForTheme(cssText, themeId)

      it('theme block exists in file', () => {
        expect(defined.size).toBeGreaterThan(0)
      })

      for (const token of REQUIRED_TOKENS) {
        it(`defines ${token}`, () => {
          expect(defined.has(token)).toBe(true)
        })
      }
    })
  }

  it('tokens.css root block defines REQUIRED_TOKENS as fallback', () => {
    const tokensPath = path.resolve(__dirname, '../tokens.css')
    const cssText = fs.readFileSync(tokensPath, 'utf8')
    // :root 块 fallback(主题切换回默认 + 防漏)
    const rootBlockMatch = cssText.match(/:root\s*\{([\s\S]*?)\n\}/)
    expect(rootBlockMatch).toBeTruthy()
    const body = rootBlockMatch[1]
    const defined = new Set()
    const declRe = /(--[a-z0-9-]+)\s*:/g
    let m
    while ((m = declRe.exec(body)) !== null) defined.add(m[1])
    for (const token of REQUIRED_TOKENS) {
      expect(defined.has(token), `tokens.css :root missing ${token}`).toBe(true)
    }
  })
})
