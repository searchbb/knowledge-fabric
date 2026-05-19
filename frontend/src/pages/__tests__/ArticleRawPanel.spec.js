import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ArticleRawPanel from '../ArticleViewPage/ArticleRawPanel.vue'
import { getArticleRaw } from '../../api/vault'

vi.mock('../../api/vault', () => ({
  getArticleRaw: vi.fn(),
}))

enableAutoUnmount(afterEach)

describe('ArticleRawPanel', () => {
  beforeEach(() => {
    getArticleRaw.mockReset()
    Element.prototype.scrollIntoView = vi.fn()
  })

  function mockRaw(content) {
    getArticleRaw.mockResolvedValue({
      success: true,
      filename: 'article.md',
      size: content.length,
      source_backend: 'uploads',
      content,
    })
  }

  it('loads raw markdown and highlights the focused section', async () => {
    mockRaw(`# Article

## FDE 模式
这里介绍 FDE 模式的核心内容。

## Other Section
其他内容。
`)

    const wrapper = mount(ArticleRawPanel, {
      props: {
        projectId: 'proj_6b877d2807eb',
        focusTarget: { name: 'FDE 模式' },
        autoScroll: true,
      },
    })

    await flushPromises()

    expect(getArticleRaw).toHaveBeenCalledWith('proj_6b877d2807eb')
    expect(wrapper.text()).toContain('按节点名称匹配到可能段落')
    const target = wrapper.find('[data-raw-focus="true"]')
    expect(target.exists()).toBe(true)
    expect(target.text()).toContain('FDE 模式')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })

  it('shows a clear fallback when no raw markdown match is found', async () => {
    mockRaw(`# Article

## Existing Section
这里没有目标节点。
`)

    const wrapper = mount(ArticleRawPanel, {
      props: {
        projectId: 'proj_6b877d2807eb',
        focusTarget: { name: '不存在的节点' },
        autoScroll: true,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('未找到精确原文，仅显示全文')
    expect(wrapper.find('[data-raw-focus="true"]').exists()).toBe(false)
  })

  it('treats plus signs in query-derived focus names as spaces', async () => {
    mockRaw(`# Article

## FDE 模式
这里介绍 FDE 模式的核心内容。
`)

    const wrapper = mount(ArticleRawPanel, {
      props: {
        projectId: 'proj_6b877d2807eb',
        focusTarget: { name: 'fde+模式' },
        autoScroll: true,
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-raw-focus="true"]').text()).toContain('FDE 模式')
  })

  it('keeps the graph-side experience usable when the raw API fails', async () => {
    getArticleRaw.mockResolvedValue({
      success: false,
      error_code: 'SOURCE_MD_MISSING',
      error: '源 md 文件不存在',
    })

    const wrapper = mount(ArticleRawPanel, {
      props: {
        projectId: 'proj_missing',
        focusTarget: { name: 'FDE 模式' },
        autoScroll: true,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('原文加载失败')
    expect(wrapper.text()).toContain('SOURCE_MD_MISSING')
    expect(wrapper.text()).toContain('源 md 文件被移动或删除')
  })
})
