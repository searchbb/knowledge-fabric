/*
 * WCAG AA 对比度断言
 *
 * 每套主题下关键 text/bg 配对需要 ≥ 4.5(正文级别)。
 * 参考 WCAG 2.1 §1.4.3 Contrast (Minimum):
 *   - Normal text: ≥ 4.5
 *   - Large text: ≥ 3.0(我们暂不区分,统一打 4.5)
 *
 * 解析策略:读主题 CSS 文件,regex 抽 token = hex 映射,
 * 然后对关键 pair 计算对比度。
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

/**
 * 从主题 CSS 里抽 token → hex 的 map。
 * 只接受 3 位 / 6 位 hex(忽略 rgba/gradient/var 引用 — 对比度对这些无意义)。
 */
function parseThemeTokens(filepath, themeId) {
  const cssText = fs.readFileSync(filepath, 'utf8')
  const blockRe = new RegExp(
    `html\\[data-theme="${themeId}"\\]\\s*\\{([\\s\\S]*?)\\n\\}`,
  )
  const m = cssText.match(blockRe)
  if (!m) return {}
  const body = m[1]
  const out = {}
  const declRe = /(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;/g
  let d
  while ((d = declRe.exec(body)) !== null) {
    out[d[1]] = normalizeHex(d[2])
  }
  return out
}

function normalizeHex(hex) {
  let h = hex.replace('#', '')
  if (h.length === 3) h = h.split('').map(c => c + c).join('')
  if (h.length === 8) h = h.slice(0, 6) // 丢 alpha
  return '#' + h.toLowerCase()
}

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

/** WCAG 相对亮度 */
function relativeLuminance({ r, g, b }) {
  const channel = (v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

/** WCAG 对比度 ratio */
export function contrastRatio(hexA, hexB) {
  const lumA = relativeLuminance(hexToRgb(hexA))
  const lumB = relativeLuminance(hexToRgb(hexB))
  const lighter = Math.max(lumA, lumB)
  const darker = Math.min(lumA, lumB)
  return (lighter + 0.05) / (darker + 0.05)
}

// 关键 pair 断言:
//   正文字 vs 主背景 / 次级字 vs surface / reading 正文 vs 纸面 / reading 代码块
// GPT V2 验收指出 reading-code-panel 之前是硬编码,现在也纳入对比度测试。
const CRITICAL_PAIRS = [
  { text: '--text-primary',   bg: '--bg-canvas',    min: 4.5, label: 'primary on canvas' },
  { text: '--text-primary',   bg: '--bg-surface',   min: 4.5, label: 'primary on surface' },
  { text: '--text-primary',   bg: '--bg-elevated',  min: 4.5, label: 'primary on elevated' },
  { text: '--text-secondary', bg: '--bg-canvas',    min: 4.5, label: 'secondary on canvas' },
  { text: '--reading-ink',    bg: '--reading-paper', min: 4.5, label: 'reading ink on paper' },
  { text: '--reading-code-panel-ink', bg: '--reading-code-panel-bg', min: 4.5, label: 'code panel ink on bg' },
]

describe('Contrast ratio (WCAG AA)', () => {
  it('contrastRatio util: white on black = 21', () => {
    expect(Math.round(contrastRatio('#ffffff', '#000000'))).toBe(21)
  })
  it('contrastRatio util: 相同色 = 1', () => {
    expect(contrastRatio('#888888', '#888888')).toBeCloseTo(1.0, 2)
  })

  for (const [themeId, filename] of Object.entries(THEME_FILES)) {
    describe(themeId, () => {
      const filepath = path.join(THEMES_DIR, filename)
      const tokens = parseThemeTokens(filepath, themeId)

      for (const pair of CRITICAL_PAIRS) {
        it(`${pair.label} ≥ ${pair.min}`, () => {
          const fg = tokens[pair.text]
          const bg = tokens[pair.bg]
          expect(fg, `token ${pair.text} not found / not hex`).toBeTruthy()
          expect(bg, `token ${pair.bg} not found / not hex`).toBeTruthy()
          const ratio = contrastRatio(fg, bg)
          expect(
            ratio,
            `${pair.label} = ${ratio.toFixed(2)} (fg ${fg} / bg ${bg})`,
          ).toBeGreaterThanOrEqual(pair.min)
        })
      }
    })
  }
})
