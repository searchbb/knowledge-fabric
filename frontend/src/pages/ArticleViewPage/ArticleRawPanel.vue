<template>
  <div class="article-raw-wrap">
    <!-- 元信息 + 外链图片风险提示 banner -->
    <header v-if="data" class="raw-meta">
      <div class="meta-line">
        <span class="meta-chip">📄 {{ data.filename }}</span>
        <span class="meta-chip">{{ formatSize(data.size) }}</span>
        <span class="meta-chip" :class="`backend-${data.source_backend}`">
          真源:{{ data.source_backend === 'vault' ? 'Obsidian vault' : 'backend/uploads' }}
        </span>
        <span v-if="data.vault_relative_dir" class="meta-chip">📁 {{ data.vault_relative_dir }}</span>
        <button class="reload-btn" @click="load" :disabled="loading" title="重新拉取原文">
          {{ loading ? '加载中...' : '⟳ 刷新' }}
        </button>
      </div>
      <div v-if="data.image_policy?.may_fail" class="image-warning">
        ⚠ {{ data.image_policy.message }}
      </div>
    </header>

    <!-- 加载中 -->
    <div v-if="loading && !data" class="raw-state">
      <div class="state-title">加载中…</div>
    </div>

    <!-- 错误(明确展示错误码,方便用户反馈/自查) -->
    <div v-else-if="error" class="raw-state error-state">
      <div class="state-title">原文加载失败</div>
      <div class="state-code" v-if="errorCode">{{ errorCode }}</div>
      <div class="state-body">{{ error }}</div>
      <div class="state-hint" v-if="errorHint">{{ errorHint }}</div>
      <button class="retry-btn" @click="load">重试</button>
    </div>

    <!-- 原文渲染 + 视图切换(渲染 / 源码) -->
    <div v-else-if="data" class="raw-body">
      <div class="view-switch">
        <button
          class="switch-btn"
          :class="{ active: viewMode === 'rendered' }"
          @click="viewMode = 'rendered'"
        >渲染</button>
        <button
          class="switch-btn"
          :class="{ active: viewMode === 'source' }"
          @click="viewMode = 'source'"
        >源码</button>
      </div>

      <article
        v-if="viewMode === 'rendered'"
        class="markdown-prose"
        v-html="safeHtml"
      />
      <pre v-else class="markdown-source">{{ data.content }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

import { getArticleRaw } from '../../api/vault'

const props = defineProps({
  projectId: { type: String, required: true },
})

const data = ref(null)
const loading = ref(false)
const error = ref('')
const errorCode = ref('')
const viewMode = ref('rendered')

// 单实例 markdown-it:禁用原生 HTML(html:false),只允许 md 本身语法,降低 XSS 面。
// DOMPurify 再做一次白名单清洗,双保险。
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
})

// DOMPurify 配置:允许常见 md 元素,禁用 script/iframe/object,强制链接用 rel="noopener"
const sanitizeConfig = {
  ALLOWED_TAGS: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr', 'span', 'div',
    'strong', 'em', 'b', 'i', 'del', 's', 'mark', 'sub', 'sup',
    'a', 'img',
    'ul', 'ol', 'li',
    'blockquote',
    'code', 'pre',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
  ],
  ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel'],
  ALLOWED_URI_REGEXP: /^(?:https?|mailto):/i,
  ADD_ATTR: ['target', 'rel'],
}

const safeHtml = computed(() => {
  if (!data.value?.content) return ''
  const rawHtml = md.render(data.value.content)
  const clean = DOMPurify.sanitize(rawHtml, sanitizeConfig)
  // 给所有外链 a 加 target="_blank" rel="noopener noreferrer"(sanitize 后二次加工)
  return clean.replace(
    /<a\s+([^>]*?)href="(https?:[^"]+)"([^>]*)>/gi,
    (m, pre, href, post) =>
      `<a ${pre}href="${href}" target="_blank" rel="noopener noreferrer"${post}>`
  )
})

const errorHint = computed(() => {
  switch (errorCode.value) {
    case 'PROJECT_NOT_FOUND':
      return '项目可能已被删除,请回到项目列表确认。'
    case 'NO_SOURCE_FILE':
      return '项目元数据里没有记录 md 文件,可能是老项目格式或上传未完成。'
    case 'SOURCE_MD_MISSING':
      return '源 md 文件被移动或删除。若存于 vault 请检查 Obsidian 是否改过名/路径。'
    case 'SOURCE_MD_UNREADABLE':
      return '文件存在但读取失败,可能是权限或 iCloud 同步未就绪,稍后重试。'
    default:
      return ''
  }
})

async function load() {
  if (!props.projectId) return
  loading.value = true
  error.value = ''
  errorCode.value = ''
  try {
    const res = await getArticleRaw(props.projectId)
    if (res?.success) {
      data.value = res
    } else {
      error.value = res?.error || '未知错误'
      errorCode.value = res?.error_code || ''
    }
  } catch (e) {
    error.value = e?.message || '网络异常'
  } finally {
    loading.value = false
  }
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// 懒加载:仅首次挂载(tab 切过来) + projectId 变更时拉取
onMounted(load)
watch(() => props.projectId, load)
</script>

<style scoped>
.article-raw-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.raw-meta {
  padding: 10px 16px;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: var(--bg-elevated);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.meta-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.meta-chip {
  padding: 3px 10px;
  font-size: 12px;
  background: var(--bg-muted);
  color: var(--text-secondary);
  border-radius: 999px;
  border: 1px solid var(--border-default);
}
/* meta-chip.backend-* 属于语义状态标签,跨主题保持识别度 */
.meta-chip.backend-vault { background: #e8f3ea; color: #2e6b2e; border-color: #c5dfc5; }
.meta-chip.backend-uploads { background: #f1f4fa; color: #3d5b8a; border-color: #c8d3ea; }

.reload-btn {
  margin-left: auto;
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 6px;
  border: 1px solid var(--border-default);
  background: var(--bg-elevated);
  color: var(--accent-primary);
  cursor: pointer;
}
.reload-btn:disabled { opacity: 0.6; cursor: wait; }

/* 图像警告属于语义警告态,跨主题保持识别度 */
.image-warning {
  padding: 8px 12px;
  font-size: 12px;
  color: #8a5a00;
  background: #fffbe6;
  border-left: 3px solid #f0b500;
  border-radius: 4px;
}

.view-switch {
  display: flex;
  gap: 6px;
  padding-bottom: 8px;
}
.switch-btn {
  padding: 5px 14px;
  font-size: 13px;
  border: 1px solid var(--border-default);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
}
.switch-btn.active {
  background: var(--accent-primary);
  color: var(--text-on-accent);
  border-color: var(--accent-primary);
}

.raw-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--reading-paper);
  border: 1px solid var(--reading-divider);
  border-radius: 12px;
  padding: 20px 28px 28px;
  overflow: hidden;
}

.markdown-prose {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  font-size: 15px;
  line-height: 1.75;
  color: var(--reading-ink);
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
}
.markdown-prose :deep(h1) { font-size: 24px; margin-top: 8px; border-bottom: 2px solid var(--reading-divider); padding-bottom: 6px; color: var(--reading-ink); }
.markdown-prose :deep(h2) { font-size: 20px; margin-top: 24px; color: var(--reading-ink); }
.markdown-prose :deep(h3) { font-size: 17px; margin-top: 20px; color: var(--reading-ink); }
.markdown-prose :deep(p) { margin: 10px 0; }
.markdown-prose :deep(img) { max-width: 100%; height: auto; display: block; margin: 12px auto; border-radius: 6px; }
.markdown-prose :deep(a) { color: var(--reading-annotate); text-decoration: underline; }
.markdown-prose :deep(blockquote) {
  border-left: 3px solid var(--reading-quote-bar);
  padding: 2px 14px;
  color: var(--text-secondary);
  margin: 14px 0;
  background: var(--reading-highlight-bg);
}
.markdown-prose :deep(code) {
  background: var(--reading-code-bg);
  border: 1px solid var(--reading-code-border);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.92em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
/* Code block(fenced / pre)— 吃 reading-code-panel token。
   各主题下都是"深底浅字"的终端感,但每个主题的具体 hex 不同,
   这样阅读层契约完整不被硬编码撕开。 */
.markdown-prose :deep(pre) {
  background: var(--reading-code-panel-bg);
  color: var(--reading-code-panel-ink);
  border: 1px solid var(--reading-code-panel-border);
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
}
.markdown-prose :deep(pre code) { background: transparent; border: none; color: inherit; padding: 0; }
.markdown-prose :deep(table) { border-collapse: collapse; margin: 14px 0; }
.markdown-prose :deep(th),
.markdown-prose :deep(td) { border: 1px solid var(--reading-divider); padding: 6px 10px; }
.markdown-prose :deep(th) { background: var(--bg-surface-2); color: var(--text-primary); }

.markdown-source {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--reading-code-panel-bg);
  color: var(--reading-code-panel-ink);
  border: 1px solid var(--reading-code-panel-border);
  padding: 16px 20px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.raw-state {
  padding: 40px 20px;
  text-align: center;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px dashed var(--border-default);
  border-radius: 12px;
}
.raw-state.error-state {
  border-color: #e2b0a8;
  background: #fff8f6;
  color: #8c2a20;
}
.state-title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.state-code {
  display: inline-block;
  padding: 2px 10px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: rgba(198, 40, 40, 0.1);
  color: #8c2a20;
  border-radius: 4px;
  margin-bottom: 8px;
}
.state-body { font-size: 14px; line-height: 1.6; }
.state-hint { font-size: 12px; color: var(--text-muted); margin-top: 8px; }
.retry-btn {
  margin-top: 12px;
  padding: 6px 16px;
  background: var(--accent-primary);
  color: var(--text-on-accent);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.retry-btn:hover { background: var(--accent-primary-hover); }
</style>
