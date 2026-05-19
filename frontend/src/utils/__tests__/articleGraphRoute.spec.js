import { describe, expect, it } from 'vitest'

import { buildArticleGraphHref, buildSourceArticleGraphHref } from '../articleGraphRoute'

describe('articleGraphRoute', () => {
  it('builds workspace article graph links that preserve focus node context', () => {
    expect(buildArticleGraphHref('proj_agent', 'Problem:agent-harness', { from: 'registry' })).toBe(
      '/workspace/proj_agent/article?view=reading&focusNode=Problem%3Aagent-harness&from=registry',
    )
  })

  it('builds source-link article graph hrefs without falling back to legacy process pages', () => {
    const href = buildSourceArticleGraphHref(
      { project_id: 'proj_1', concept_key: 'Topic:API经济' },
      { from: 'registry' },
    )

    expect(href).toBe('/workspace/proj_1/article?view=reading&focusNode=Topic%3AAPI%E7%BB%8F%E6%B5%8E&from=registry')
    expect(href).not.toContain('/process/')
  })
})
