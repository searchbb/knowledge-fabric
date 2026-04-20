// NotePasteCard — rich-text paste entry for the AutoPipelinePage.
//
// Covers: paste extraction (HTML / plain text / images), Turndown
// conversion, title auto-prefill rules, submit flow and duplicate
// handling.

import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const serviceMock = vi.fn()
vi.mock('../../api/index', () => ({ default: (...args) => serviceMock(...args) }))

import NotePasteCard from '../AutoPipelinePage/components/NotePasteCard.vue'

enableAutoUnmount(afterEach)

function makeClipboardData({ html = null, text = '', files = [] } = {}) {
  return {
    getData: (type) => {
      if (type === 'text/html') return html || ''
      if (type === 'text/plain') return text
      return ''
    },
    files,
  }
}

function pasteEvent(clipboardData) {
  // jsdom doesn't implement ClipboardEvent, so fake the bits we read.
  const e = new Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'clipboardData', { value: clipboardData })
  return e
}

describe('NotePasteCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('paste handling', () => {
    it('converts HTML paste to Markdown via Turndown', async () => {
      const wrapper = mount(NotePasteCard)
      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(
        pasteEvent(makeClipboardData({
          html: '<h1>Hello</h1><p>A <strong>bold</strong> line.</p>',
        })),
      )
      await flushPromises()
      const preview = wrapper.find('[data-test="note-md-preview"]').element.value
      expect(preview).toContain('# Hello')
      expect(preview).toContain('**bold**')
    })

    it('falls back to plain text when no HTML is present', async () => {
      const wrapper = mount(NotePasteCard)
      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(
        pasteEvent(makeClipboardData({ text: 'just some plain text' })),
      )
      await flushPromises()
      const preview = wrapper.find('[data-test="note-md-preview"]').element.value
      expect(preview).toContain('just some plain text')
    })

    it('embeds pasted images as base64 data URLs in the Markdown', async () => {
      const wrapper = mount(NotePasteCard)
      // 1×1 transparent PNG
      const pngBytes = Uint8Array.from(atob(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
      ), (c) => c.charCodeAt(0))
      const file = new File([pngBytes], 'tiny.png', { type: 'image/png' })

      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(pasteEvent(makeClipboardData({ files: [file] })))
      // FileReader.readAsDataURL in jsdom settles on a macrotask; wait a few ticks.
      for (let i = 0; i < 10; i++) {
        await flushPromises()
        await new Promise((r) => setTimeout(r, 0))
      }

      const preview = wrapper.find('[data-test="note-md-preview"]').element.value
      expect(preview).toMatch(/!\[.*?\]\(data:image\/png;base64,/)
    })
  })

  describe('title auto-prefill', () => {
    it('uses the first H1 as title when present', async () => {
      const wrapper = mount(NotePasteCard)
      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(
        pasteEvent(makeClipboardData({
          html: '<h1>My Title</h1><p>body</p>',
        })),
      )
      await flushPromises()
      const titleInput = wrapper.find('[data-test="note-title"]').element
      expect(titleInput.value).toBe('My Title')
    })

    it('uses the first non-empty line (≤30 chars) when no H1', async () => {
      const wrapper = mount(NotePasteCard)
      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(
        pasteEvent(makeClipboardData({ text: '这是一段随手写的想法，没有标题。\n\n第二段内容。' })),
      )
      await flushPromises()
      const titleInput = wrapper.find('[data-test="note-title"]').element
      expect(titleInput.value).toBe('这是一段随手写的想法，没有标题。')
    })

    it('leaves title blank when no content suggests one', async () => {
      const wrapper = mount(NotePasteCard)
      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(pasteEvent(makeClipboardData({ text: '' })))
      await flushPromises()
      const titleInput = wrapper.find('[data-test="note-title"]').element
      expect(titleInput.value).toBe('')
    })

    it('strips inline markdown formatting from the derived title', async () => {
      // A Twitter-style first line produces bold + link after Turndown:
      // "**@karpathy**: A quick note on [tokenizer](https://x)"
      // The derived title should be the readable text, not the raw MD.
      const wrapper = mount(NotePasteCard)
      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(
        pasteEvent(makeClipboardData({
          html: '<p><b>@karpathy</b>: A note on <a href="https://example.com">tokenizer</a></p>',
        })),
      )
      await flushPromises()
      const titleInput = wrapper.find('[data-test="note-title"]').element
      expect(titleInput.value).not.toMatch(/[*_`~]/)
      expect(titleInput.value).not.toMatch(/\[.*?\]\(/)
      expect(titleInput.value).toContain('@karpathy')
      expect(titleInput.value).toContain('tokenizer')
    })

    it('does not overwrite a user-typed title on subsequent pastes', async () => {
      const wrapper = mount(NotePasteCard)
      const titleInput = wrapper.find('[data-test="note-title"]')
      await titleInput.setValue('User Title')

      const editor = wrapper.find('[data-test="note-editor"]')
      editor.element.dispatchEvent(
        pasteEvent(makeClipboardData({ html: '<h1>Auto Title</h1>' })),
      )
      await flushPromises()
      expect(titleInput.element.value).toBe('User Title')
    })
  })

  describe('submit flow', () => {
    it('disables submit when markdown or title is empty', () => {
      const wrapper = mount(NotePasteCard)
      const btn = wrapper.find('[data-test="note-submit"]').element
      expect(btn.disabled).toBe(true)
    })

    it('POSTs markdown + title to /api/auto/pending-notes on submit', async () => {
      serviceMock.mockResolvedValue({
        data: { added: [{ title: 't', url_fingerprint: 'file:///tmp/x.md' }], duplicates: [] },
      })
      const wrapper = mount(NotePasteCard)
      await wrapper.find('[data-test="note-title"]').setValue('My Note')
      await wrapper.find('[data-test="note-md-preview"]').setValue('body content')
      await wrapper.find('[data-test="note-submit"]').trigger('click')
      await flushPromises()

      expect(serviceMock).toHaveBeenCalledTimes(1)
      const call = serviceMock.mock.calls[0][0]
      expect(call.url).toBe('/api/auto/pending-notes')
      expect(call.method).toBe('post')
      expect(call.data.title).toBe('My Note')
      expect(call.data.markdown).toBe('body content')
    })

    it('shows duplicate warning when backend returns duplicates', async () => {
      serviceMock.mockResolvedValue({
        data: {
          added: [],
          duplicates: [{ existing_bucket: 'processed', existing_url: 'file:///x.md' }],
        },
      })
      const wrapper = mount(NotePasteCard)
      await wrapper.find('[data-test="note-title"]').setValue('t')
      await wrapper.find('[data-test="note-md-preview"]').setValue('body')
      await wrapper.find('[data-test="note-submit"]').trigger('click')
      await flushPromises()

      const result = wrapper.find('[data-test="note-result"]').text()
      expect(result).toMatch(/已存在|重复|duplicate/i)
    })

    it('emits submitted event so the parent can refresh the queue', async () => {
      serviceMock.mockResolvedValue({
        data: { added: [{ title: 't', url_fingerprint: 'file:///x.md' }], duplicates: [] },
      })
      const wrapper = mount(NotePasteCard)
      await wrapper.find('[data-test="note-title"]').setValue('t')
      await wrapper.find('[data-test="note-md-preview"]').setValue('body')
      await wrapper.find('[data-test="note-submit"]').trigger('click')
      await flushPromises()
      expect(wrapper.emitted('submitted')).toBeTruthy()
    })
  })
})
