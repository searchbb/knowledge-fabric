export function buildArticleGraphHref(projectId, conceptKey = '', options = {}) {
  if (!projectId) return '#'

  const params = new URLSearchParams()
  params.set('view', options.view || 'reading')
  if (conceptKey) params.set('focusNode', conceptKey)
  if (options.from) params.set('from', options.from)

  return `/workspace/${encodeURIComponent(projectId)}/article?${params.toString()}`
}

export function buildSourceArticleGraphHref(link, options = {}) {
  return buildArticleGraphHref(link?.project_id, link?.concept_key, options)
}
