import { describe, expect, it } from 'vitest'
import router from '../index'

describe('router', () => {
  it('registers the read-only research review workspace route separately from strategic research', () => {
    const reviewRoute = router.getRoutes().find((route) => route.name === 'ResearchReviewWorkspace')
    const researchRoute = router.getRoutes().find((route) => route.name === 'ResearchProjects')

    expect(reviewRoute?.path).toBe('/workspace/research/review')
    expect(reviewRoute?.meta).toEqual(expect.objectContaining({
      runtimeSurface: 'global',
      productStatus: 'phase2',
    }))
    expect(researchRoute?.path).toBe('/workspace/research')
  })

  it('resolves /workspace/research/review to the dedicated review workspace route', () => {
    const resolved = router.resolve('/workspace/research/review')

    expect(resolved.name).toBe('ResearchReviewWorkspace')
  })

  it('registers wiki topic overview and detail routes', () => {
    expect(router.resolve('/workspace/wiki-topics').name).toBe('WikiTopics')
    expect(router.resolve('/workspace/wiki-topics/ai-tokenization').name).toBe('WikiTopicDetail')
  })
})
