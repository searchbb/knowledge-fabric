<template>
  <article ref="articleRef" class="markdown-article-viewer" v-html="safeHtml" />
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const props = defineProps({
  markdown: { type: String, default: '' },
  candidateId: { type: String, required: true },
  sourceFilePath: { type: String, default: '' },
})

const articleRef = ref(null)
const renderNonce = ref(0)

const sanitizeConfig = {
  ALLOWED_TAGS: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr', 'span', 'div',
    'strong', 'em', 'b', 'i', 'del', 's', 'mark', 'sub', 'sup', 'kbd',
    'a', 'img',
    'ul', 'ol', 'li',
    'blockquote',
    'code', 'pre',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'details', 'summary',
    'figure', 'figcaption',
  ],
  ALLOWED_ATTR: [
    'href', 'src', 'alt', 'title', 'class', 'target', 'rel',
    'loading', 'decoding', 'id', 'hidden', 'aria-label',
    'data-image-fallback', 'data-mermaid-index',
  ],
  ADD_ATTR: [
    'target', 'rel', 'loading', 'decoding', 'hidden', 'aria-label',
    'data-image-fallback', 'data-mermaid-index',
  ],
  ALLOW_DATA_ATTR: true,
  FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button'],
  FORBID_ATTR: ['style'],
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function safeIdPart(value) {
  return String(value || 'candidate').replace(/[^A-Za-z0-9_-]/g, '_') || 'candidate'
}

function rewriteImageSrc(src, candidateId) {
  const value = String(src || '').trim()
  if (!value) return value
  if (/^https?:\/\//i.test(value)) return value
  if (/^data:image\//i.test(value)) return value
  if (value.startsWith('/api/')) return value
  return `/api/wiki-intake/candidates/${encodeURIComponent(candidateId)}/assets?path=${encodeURIComponent(value)}`
}

function finalizeRenderedHtml(cleanHtml, candidateId) {
  if (typeof document === 'undefined') return cleanHtml
  const template = document.createElement('template')
  template.innerHTML = cleanHtml
  template.content.querySelectorAll('img').forEach((image) => {
    const currentSrc = image.getAttribute('src') || ''
    image.setAttribute('src', rewriteImageSrc(currentSrc, candidateId))
    image.setAttribute('loading', 'lazy')
    image.setAttribute('decoding', 'async')
    image.setAttribute('data-image-fallback', 'true')
  })
  template.content.querySelectorAll('a[href]').forEach((anchor) => {
    const href = anchor.getAttribute('href') || ''
    if (/^https?:\/\//i.test(href)) {
      anchor.setAttribute('target', '_blank')
      anchor.setAttribute('rel', 'noopener noreferrer')
    }
  })
  return template.innerHTML
}

const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: false,
})

const defaultFenceRenderer = md.renderer.rules.fence?.bind(md.renderer)

md.renderer.rules.image = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  token.attrSet('src', rewriteImageSrc(token.attrGet('src'), env.candidateId))
  token.attrSet('alt', token.content || token.attrGet('alt') || '')
  token.attrSet('loading', 'lazy')
  token.attrSet('decoding', 'async')
  token.attrSet('data-image-fallback', 'true')
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const href = token.attrGet('href') || ''
  if (/^https?:\/\//i.test(href)) {
    token.attrSet('target', '_blank')
    token.attrSet('rel', 'noopener noreferrer')
  }
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const language = String(token.info || '').trim().split(/\s+/)[0].toLowerCase()
  if (language !== 'mermaid') {
    if (defaultFenceRenderer) return defaultFenceRenderer(tokens, idx, options, env, self)
    return `<pre><code>${escapeHtml(token.content)}</code></pre>`
  }

  const blockIndex = env.mermaidBlocks.length
  const id = `wiki-intake-mermaid-${safeIdPart(env.candidateId)}-${blockIndex}`
  env.mermaidBlocks.push({ id, code: token.content, index: blockIndex })
  return [
    `<div class="mermaid-block" data-mermaid-index="${blockIndex}">`,
    `<div id="${id}" class="mermaid-render-target" aria-label="Mermaid diagram"></div>`,
    `<pre class="mermaid-fallback" hidden><code>${escapeHtml(token.content)}</code></pre>`,
    '<p class="mermaid-error" hidden>Mermaid render failed. Showing source.</p>',
    '</div>',
  ].join('')
}

const renderedArticle = computed(() => {
  const env = { candidateId: props.candidateId, sourceFilePath: props.sourceFilePath, mermaidBlocks: [] }
  const rawHtml = md.render(props.markdown || '', env)
  const cleanHtml = DOMPurify.sanitize(rawHtml, sanitizeConfig)
  return {
    html: finalizeRenderedHtml(cleanHtml, props.candidateId),
    mermaidBlocks: env.mermaidBlocks,
  }
})

const safeHtml = computed(() => renderedArticle.value.html)

let mermaidPromise = null

async function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then((module) => module.default || module)
  }
  return mermaidPromise
}

function showMermaidFallback(container, error) {
  if (!container) return
  const target = container.querySelector('.mermaid-render-target')
  const fallback = container.querySelector('.mermaid-fallback')
  const message = container.querySelector('.mermaid-error')
  if (target) target.innerHTML = ''
  if (fallback) fallback.hidden = false
  if (message) {
    message.hidden = false
    const detail = error?.message ? ` ${error.message}` : ''
    message.textContent = `Mermaid render failed. Showing source.${detail}`
  }
}

function findMermaidTarget(blockId) {
  return articleRef.value?.querySelector(`[id="${blockId}"]`) || null
}

async function renderMermaidBlocks(nonce) {
  const blocks = renderedArticle.value.mermaidBlocks
  if (!blocks.length) return

  let mermaid
  try {
    mermaid = await loadMermaid()
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'default',
    })
  } catch (error) {
    for (const block of blocks) {
      showMermaidFallback(findMermaidTarget(block.id)?.closest('.mermaid-block'), error)
    }
    return
  }

  for (const block of blocks) {
    if (nonce !== renderNonce.value) return
    const target = findMermaidTarget(block.id)
    const container = target?.closest('.mermaid-block')
    if (!target || !container) continue
    try {
      const result = await mermaid.render(`${block.id}-svg-${nonce}`, block.code)
      if (nonce !== renderNonce.value) return
      target.innerHTML = typeof result === 'string' ? result : result.svg
      result?.bindFunctions?.(target)
    } catch (error) {
      showMermaidFallback(container, error)
    }
  }
}

function installImageFallbacks() {
  const root = articleRef.value
  if (!root) return
  root.querySelectorAll('img[data-image-fallback="true"]').forEach((image) => {
    image.addEventListener('error', handleImageError, { once: true })
  })
}

function handleImageError(event) {
  const image = event.currentTarget
  if (!image?.parentNode) return
  const placeholder = document.createElement('div')
  placeholder.className = 'image-error-placeholder'
  const alt = image.getAttribute('alt')
  placeholder.textContent = alt ? `图片加载失败：${alt}` : '图片加载失败'
  image.replaceWith(placeholder)
}

watch(
  () => [safeHtml.value, props.candidateId],
  async () => {
    renderNonce.value += 1
    const nonce = renderNonce.value
    await nextTick()
    installImageFallbacks()
    await renderMermaidBlocks(nonce)
  },
  { immediate: true },
)
</script>

<style scoped>
.markdown-article-viewer {
  max-width: 860px;
  margin: 0 auto;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.markdown-article-viewer :deep(*) {
  box-sizing: border-box;
}

.markdown-article-viewer :deep(h1),
.markdown-article-viewer :deep(h2),
.markdown-article-viewer :deep(h3),
.markdown-article-viewer :deep(h4),
.markdown-article-viewer :deep(h5),
.markdown-article-viewer :deep(h6) {
  line-height: 1.3;
  margin: 1.55em 0 0.65em;
  color: var(--text-primary);
}

.markdown-article-viewer :deep(h1) {
  font-size: 28px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-default);
}

.markdown-article-viewer :deep(h2) {
  font-size: 23px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-subtle, var(--border-default));
}

.markdown-article-viewer :deep(h3) {
  font-size: 19px;
}

.markdown-article-viewer :deep(p),
.markdown-article-viewer :deep(ul),
.markdown-article-viewer :deep(ol),
.markdown-article-viewer :deep(blockquote),
.markdown-article-viewer :deep(pre),
.markdown-article-viewer :deep(table),
.markdown-article-viewer :deep(details),
.markdown-article-viewer :deep(figure) {
  margin: 0 0 1em;
}

.markdown-article-viewer :deep(ul),
.markdown-article-viewer :deep(ol) {
  padding-left: 1.4em;
}

.markdown-article-viewer :deep(li + li) {
  margin-top: 0.25em;
}

.markdown-article-viewer :deep(a) {
  color: var(--accent-primary-hover);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

.markdown-article-viewer :deep(blockquote) {
  border-left: 4px solid var(--accent-primary);
  padding: 8px 14px;
  color: var(--text-secondary);
  background: var(--bg-muted);
  border-radius: 0 6px 6px 0;
}

.markdown-article-viewer :deep(table) {
  display: block;
  width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
  white-space: nowrap;
}

.markdown-article-viewer :deep(th),
.markdown-article-viewer :deep(td) {
  border: 1px solid var(--border-default);
  padding: 8px 10px;
  text-align: left;
}

.markdown-article-viewer :deep(th) {
  background: var(--bg-muted);
  font-weight: 800;
}

.markdown-article-viewer :deep(code) {
  border-radius: 4px;
  padding: 2px 5px;
  background: var(--bg-muted);
  font-size: 0.9em;
}

.markdown-article-viewer :deep(pre) {
  overflow-x: auto;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: #0f172a;
  color: #e5e7eb;
}

.markdown-article-viewer :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-article-viewer :deep(img) {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 18px auto;
  border-radius: 8px;
}

.markdown-article-viewer :deep(.image-error-placeholder) {
  max-width: 100%;
  margin: 18px auto;
  border: 1px dashed var(--border-default);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  color: var(--text-secondary);
  background: var(--bg-muted);
}

.markdown-article-viewer :deep(.mermaid-block) {
  max-width: 100%;
  margin: 20px auto;
  overflow-x: auto;
  text-align: center;
}

.markdown-article-viewer :deep(.mermaid-render-target) {
  display: inline-block;
  min-width: min(100%, 320px);
}

.markdown-article-viewer :deep(.mermaid-render-target svg) {
  max-width: 100%;
  height: auto;
}

.markdown-article-viewer :deep(.mermaid-fallback) {
  text-align: left;
}

.markdown-article-viewer :deep(.mermaid-error) {
  margin-top: 8px;
  color: #9a6700;
  font-size: 12px;
  text-align: left;
}

@media (max-width: 760px) {
  .markdown-article-viewer {
    font-size: 14px;
  }

  .markdown-article-viewer :deep(h1) {
    font-size: 24px;
  }
}
</style>
