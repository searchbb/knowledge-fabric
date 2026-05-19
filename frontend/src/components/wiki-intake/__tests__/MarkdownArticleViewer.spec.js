import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MarkdownArticleViewer from '../MarkdownArticleViewer.vue'

enableAutoUnmount(afterEach)

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async (id, code) => {
      if (code.includes('broken')) throw new Error('invalid mermaid')
      return { svg: `<svg id="${id}" role="img"><text>diagram</text></svg>` }
    }),
  },
}))

async function mountViewer(markdown, candidateId = 'src_test') {
  const wrapper = mount(MarkdownArticleViewer, {
    props: {
      markdown,
      candidateId,
      sourceFilePath: '/Users/mac/Downloads/OB笔记/Clippings/article.md',
    },
  })
  await settleAsyncRender()
  return wrapper
}

async function settleAsyncRender() {
  for (let index = 0; index < 5; index += 1) {
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 0))
  }
}

describe('MarkdownArticleViewer', () => {
  it('renders normal markdown, tables, and code blocks as article HTML', async () => {
    const wrapper = await mountViewer([
      '# Heading',
      '',
      'Paragraph with **strong** text.',
      '',
      '- one',
      '- two',
      '',
      '| A | B |',
      '| - | - |',
      '| 1 | 2 |',
      '',
      '```js',
      'const value = 1',
      '```',
    ].join('\n'))

    expect(wrapper.find('h1').text()).toBe('Heading')
    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.find('pre code').text()).toContain('const value = 1')
  })

  it('rewrites relative image URLs and preserves remote/data/API image URLs', async () => {
    const wrapper = await mountViewer([
      '![Local](assets/test.png)',
      '![Remote](https://example.com/image.png)',
      '![Data](data:image/png;base64,abc)',
      '![Api](/api/wiki-intake/candidates/src_test/assets?path=assets%2Fx.png)',
    ].join('\n\n'), 'src_article')
    const sources = wrapper.findAll('img').map((image) => image.attributes('src'))

    expect(sources[0]).toBe('/api/wiki-intake/candidates/src_article/assets?path=assets%2Ftest.png')
    expect(sources[1]).toBe('https://example.com/image.png')
    expect(sources[2]).toBe('data:image/png;base64,abc')
    expect(sources[3]).toBe('/api/wiki-intake/candidates/src_test/assets?path=assets%2Fx.png')
    expect(wrapper.find('img').attributes('loading')).toBe('lazy')
  })

  it('sanitizes raw HTML and external links', async () => {
    const wrapper = await mountViewer(
      '<script>alert(1)</script><p onclick="alert(2)">Safe</p>\n\n[Link](https://example.com)',
    )

    expect(wrapper.html()).not.toContain('<script')
    expect(wrapper.html()).not.toContain('onclick')
    expect(wrapper.find('p').text()).toBe('Safe')
    expect(wrapper.find('a').attributes('target')).toBe('_blank')
    expect(wrapper.find('a').attributes('rel')).toBe('noopener noreferrer')
  })

  it('renders mermaid diagrams with deterministic block ids', async () => {
    const wrapper = await mountViewer('```mermaid\ngraph TD\nA --> B\n```', 'src_mermaid')

    const target = wrapper.find('#wiki-intake-mermaid-src_mermaid-0')
    expect(target.exists()).toBe(true)
    expect(target.html()).toContain('<svg')
  })

  it('falls back to mermaid source when rendering fails', async () => {
    const wrapper = await mountViewer('```mermaid\nbroken diagram\n```', 'src_bad_mermaid')

    expect(wrapper.find('.mermaid-error').isVisible()).toBe(true)
    expect(wrapper.find('.mermaid-fallback').isVisible()).toBe(true)
    expect(wrapper.find('.mermaid-fallback').text()).toContain('broken diagram')
  })

  it('replaces broken images with a non-blocking placeholder', async () => {
    const wrapper = await mountViewer('![Missing](assets/missing.png)')
    const image = wrapper.find('img')

    image.element.dispatchEvent(new Event('error'))
    await settleAsyncRender()

    expect(wrapper.find('.image-error-placeholder').text()).toContain('Missing')
  })
})
