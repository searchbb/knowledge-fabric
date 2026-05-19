import { enableAutoUnmount, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

enableAutoUnmount(afterEach)

let currentPath = '/workspace/research/review'
let currentQuery = {}

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: currentPath, query: currentQuery, params: {} }),
}))

vi.mock('../ProjectSwitcher.vue', () => ({
  default: { template: '<div />', props: ['currentProjectId', 'preserveSection'] },
}))

import AppSidebar from '../AppSidebar.vue'

describe('AppSidebar', () => {
  function mountSidebar() {
    return mount(AppSidebar, {
      global: {
        stubs: {
          'router-link': { template: '<a :href="typeof to === `string` ? to : to.name"><slot /></a>', props: ['to'] },
        },
      },
    })
  }

  afterEach(() => {
    currentPath = '/workspace/research/review'
    currentQuery = {}
  })

  it('shows separate strategic research and review workspace entries', () => {
    const wrapper = mountSidebar()
    const links = wrapper.findAll('a')

    expect(wrapper.text()).toContain('战略研究')
    expect(wrapper.text()).toContain('审核工作台')
    expect(links.some((link) => link.attributes('href') === '/workspace/research')).toBe(true)
    expect(links.some((link) => link.attributes('href') === '/workspace/research/review')).toBe(true)
  })

  it('marks Review Workspace active without marking Strategic Research active', () => {
    currentPath = '/workspace/research/review'
    const wrapper = mountSidebar()

    const reviewLink = wrapper.find('a[href="/workspace/research/review"]')
    const researchLink = wrapper.find('a[href="/workspace/research"]')

    expect(reviewLink.classes()).toContain('active')
    expect(researchLink.classes()).not.toContain('active')
  })

  it('shows the high-frequency workflow entries and folds low-frequency tools by default', () => {
    currentPath = '/workspace/topic-clusters'
    const wrapper = mountSidebar()
    const links = wrapper.findAll('a')

    expect(wrapper.text()).toContain('素材处理')
    expect(wrapper.text()).toContain('知识组织')
    expect(wrapper.text()).toContain('战略研究')
    expect(wrapper.text()).toContain('主题汇集')
    expect(wrapper.text()).toContain('自动处理')
    expect(wrapper.text()).toContain('素材加工台')
    expect(wrapper.text()).toContain('队列与日志')
    expect(wrapper.text()).toContain('更多工具')
    expect(wrapper.text()).not.toContain('Discover 队列')
    expect(wrapper.text()).not.toContain('审核队列')
    expect(wrapper.text()).not.toContain('演化日志')
    expect(wrapper.text()).not.toContain('主题总览')
    expect(wrapper.text()).not.toContain('主题枢纽')
    expect(wrapper.text()).not.toContain('跨文关系')
    expect(wrapper.text().indexOf('自动处理')).toBeLessThan(wrapper.text().indexOf('主题汇集'))
    expect(wrapper.text().indexOf('主题汇集')).toBeLessThan(wrapper.text().indexOf('审核工作台'))
    expect(links.some((link) => link.attributes('href') === '/workspace/topic-clusters')).toBe(true)
    expect(links.some((link) => link.attributes('href') === '/workspace/wiki-intake')).toBe(true)
  })

  it('expands low-frequency queue entries on click', async () => {
    currentPath = '/workspace/auto'
    const wrapper = mountSidebar()

    expect(wrapper.text()).not.toContain('Discover 队列')
    await wrapper.find('button[aria-expanded="false"].nav-disclosure').trigger('click')

    expect(wrapper.text()).toContain('Discover 队列')
    expect(wrapper.text()).toContain('审核队列')
    expect(wrapper.text()).toContain('演化日志')
    expect(wrapper.find('a[href="/workspace/discover"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/workspace/registry?tab=review"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/workspace/registry?tab=evolution"]').exists()).toBe(true)
  })

  it('opens the queue group when a child route is active', () => {
    currentPath = '/workspace/discover'
    const wrapper = mountSidebar()

    const discoverLink = wrapper.find('a[href="/workspace/discover"]')
    expect(wrapper.text()).toContain('Discover 队列')
    expect(wrapper.find('button.nav-disclosure').attributes('aria-expanded')).toBe('true')
    expect(discoverLink.classes()).toContain('active')
  })

  it('folds more tools by default and expands legacy entries on click', async () => {
    currentPath = '/workspace/topic-clusters'
    const wrapper = mountSidebar()

    expect(wrapper.text()).not.toContain('项目总览')
    expect(wrapper.text()).not.toContain('概念注册表')
    await wrapper.find('button.group-trigger').trigger('click')

    expect(wrapper.text()).toContain('项目总览')
    expect(wrapper.text()).toContain('概念注册表')
    expect(wrapper.text()).toContain('主题总览')
    expect(wrapper.text()).toContain('主题枢纽')
    expect(wrapper.text()).toContain('跨文关系')
    expect(wrapper.find('a[href="/workspace/wiki-topics"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/workspace/themes"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/workspace/relations"]').exists()).toBe(true)
  })

  it('opens more tools when a folded child route is active', () => {
    currentPath = '/workspace/wiki-topics/ai-tokenization'
    const wrapper = mountSidebar()

    expect(wrapper.text()).toContain('主题总览')
    expect(wrapper.find('button.group-trigger').attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('a[href="/workspace/wiki-topics"]').classes()).toContain('active')
  })

  it('marks Topic Cluster active on detail pages', () => {
    currentPath = '/workspace/topic-clusters/tc_agent_ready'
    const wrapper = mountSidebar()

    expect(wrapper.find('a[href="/workspace/topic-clusters"]').classes()).toContain('active')
  })

  it('marks Wiki Intake active', () => {
    currentPath = '/workspace/wiki-intake'
    const wrapper = mountSidebar()

    expect(wrapper.find('a[href="/workspace/wiki-intake"]').classes()).toContain('active')
  })

  it('marks Wiki Topic Overview active on detail pages', () => {
    currentPath = '/workspace/wiki-topics/ai-tokenization'
    const wrapper = mountSidebar()

    expect(wrapper.find('a[href="/workspace/wiki-topics"]').classes()).toContain('active')
  })

  it('opens more tools for registry tabs and marks the tab item active', () => {
    currentPath = '/workspace/registry'
    currentQuery = { tab: 'review' }
    const wrapper = mountSidebar()

    expect(wrapper.text()).toContain('审核队列')
    expect(wrapper.find('a[href="/workspace/registry?tab=review"]').classes()).toContain('active')
  })
})
