import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

enableAutoUnmount(afterEach)

const routerPush = vi.fn()
const getOverview = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('../../../data/dataClient', () => ({
  getOverview: (...args) => getOverview(...args),
}))

vi.mock('../../../runtime/appMode', () => ({
  appMode: ref('live'),
}))

import ProjectSwitcher from '../ProjectSwitcher.vue'

describe('ProjectSwitcher', () => {
  beforeEach(() => {
    routerPush.mockReset()
    getOverview.mockReset()
    getOverview.mockResolvedValue({
      data: {
        projects: [
          { project_id: 'proj_article_1', project_name: 'Agent Harness 工作流笔记', status: 'completed' },
        ],
      },
    })
  })

  function mountSwitcher(props = {}) {
    return mount(ProjectSwitcher, {
      props,
      global: {
        stubs: {
          'router-link': { template: '<a :href="to"><slot /></a>', props: ['to'] },
        },
      },
    })
  }

  it('uses article-facing labels for the sidebar switcher copy', async () => {
    const wrapper = mountSwitcher()

    expect(wrapper.text()).toContain('当前文章')
    expect(wrapper.text()).toContain('未选择文章')
    expect(wrapper.text()).not.toContain('当前项目')
    expect(wrapper.text()).not.toContain('未选择项目')

    await wrapper.find('button.switcher-trigger').trigger('click')
    await flushPromises()

    expect(wrapper.find('input.panel-search').attributes('placeholder')).toBe('搜索文章名或 ID...')

    await wrapper.find('input.panel-search').setValue('no-match')

    expect(wrapper.text()).toContain('没有匹配文章')
    expect(wrapper.text()).not.toContain('没有匹配项目')
  })

  it('keeps selection routing on the existing project_id workspace model', async () => {
    const wrapper = mountSwitcher({ preserveSection: 'themes' })

    await wrapper.find('button.switcher-trigger').trigger('click')
    await flushPromises()
    await wrapper.find('button.panel-item').trigger('click')

    expect(routerPush).toHaveBeenCalledWith({
      name: 'Workspace',
      params: { projectId: 'proj_article_1', section: 'themes' },
    })
  })
})
