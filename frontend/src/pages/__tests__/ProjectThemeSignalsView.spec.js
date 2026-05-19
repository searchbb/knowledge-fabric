import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listRegistryConceptsMock = vi.fn()
const listGlobalThemesMock = vi.fn()

vi.mock('../../services/api/registryApi', () => ({
  listRegistryConcepts: (...args) => listRegistryConceptsMock(...args),
}))

vi.mock('../../services/api/themeApi', () => ({
  listGlobalThemes: (...args) => listGlobalThemesMock(...args),
}))

import ProjectThemeSignalsView from '../ProjectThemeSignalsView/ProjectThemeSignalsView.vue'

enableAutoUnmount(afterEach)

describe('ProjectThemeSignalsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRegistryConceptsMock.mockResolvedValue({
      data: {
        entries: [
          {
            entry_id: 'canon_fde',
            canonical_name: 'FDE 模式',
            concept_type: 'Method',
            source_links: [
              {
                project_id: 'proj_article',
                project_name: 'FDE source article',
                concept_key: 'Method:fde 模式',
              },
            ],
          },
        ],
      },
    })
    listGlobalThemesMock.mockResolvedValue({
      data: {
        themes: [
          {
            theme_id: 'gtheme_fde',
            name: '个体赋能与组织转型方法论',
            status: 'active',
            concept_memberships: [{ entry_id: 'canon_fde', role: 'member' }],
          },
        ],
      },
    })
  })

  it('carries project context when opening a theme panorama', async () => {
    const wrapper = mount(ProjectThemeSignalsView, {
      props: {
        project: { project_id: 'proj_article', name: 'FDE source article' },
      },
      global: {
        stubs: {
          RouterLink: {
            name: 'RouterLink',
            props: ['to'],
            template: '<a><slot /></a>',
          },
        },
      },
    })
    await flushPromises()

    const themeLink = wrapper
      .findAllComponents({ name: 'RouterLink' })
      .find((link) => link.text().includes('进入主题全景'))

    expect(themeLink.props('to')).toEqual({
      path: '/workspace/themes/gtheme_fde',
      query: {
        from: 'project-theme-signals',
        project_id: 'proj_article',
      },
    })
  })
})
