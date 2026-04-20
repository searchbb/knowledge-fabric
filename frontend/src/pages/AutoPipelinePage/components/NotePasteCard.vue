<template>
  <article class="note-paste-card">
    <header class="npc-head">
      <div class="card-title">从文字/富文本创建笔记</div>
      <p class="section-copy mini-copy">
        从微信/推特/飞书/剪贴板粘贴一段内容，或者自己输入，自动转成 Markdown 入队抽取。
      </p>
    </header>

    <div class="npc-row">
      <input
        class="npc-title"
        data-test="note-title"
        v-model="title"
        :placeholder="titlePlaceholder"
        @input="onTitleTyped"
      />
    </div>

    <div class="npc-split">
      <div
        ref="editorEl"
        class="npc-editor"
        data-test="note-editor"
        contenteditable="true"
        spellcheck="false"
        @paste="onPaste"
      ></div>
      <textarea
        class="npc-preview"
        data-test="note-md-preview"
        v-model="markdown"
        placeholder="转换后的 Markdown 会出现在这里，可以直接改"
      ></textarea>
    </div>

    <div class="npc-footer">
      <button
        class="npc-submit"
        data-test="note-submit"
        :disabled="!canSubmit || submitting"
        @click="submit"
      >
        {{ submitting ? '提交中…' : '加入队列' }}
      </button>
      <span
        v-if="resultText"
        class="npc-result"
        :class="resultKind"
        data-test="note-result"
      >{{ resultText }}</span>
    </div>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import TurndownService from 'turndown'
import { gfm } from 'turndown-plugin-gfm'
import service from '../../../api/index'

const emit = defineEmits(['submitted'])

const turndown = new TurndownService({ headingStyle: 'atx', codeBlockStyle: 'fenced' })
turndown.use(gfm)

const title = ref('')
const markdown = ref('')
const submitting = ref(false)
const resultText = ref('')
const resultKind = ref('')
const editorEl = ref(null)
const titleTouched = ref(false)

const titlePlaceholder = '标题（可留空，会从正文自动取）'

const canSubmit = computed(
  () => title.value.trim().length > 0 && markdown.value.trim().length > 0,
)

function onTitleTyped() {
  titleTouched.value = true
}

function deriveTitle(md) {
  const lines = md.split('\n').map((l) => l.trim()).filter(Boolean)
  if (!lines.length) return ''
  const h1 = lines.find((l) => l.startsWith('# '))
  if (h1) return h1.replace(/^#\s+/, '').trim().slice(0, 60)
  return lines[0].replace(/^[#>*\-]\s*/, '').trim().slice(0, 30)
}

async function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function onPaste(event) {
  const cb = event.clipboardData
  if (!cb) return
  event.preventDefault()

  const html = cb.getData('text/html')
  const text = cb.getData('text/plain')
  const files = Array.from(cb.files || []).filter((f) => f.type.startsWith('image/'))

  let md = ''
  if (html) {
    md = turndown.turndown(html)
  } else if (text) {
    md = text
  }

  if (files.length) {
    const imageBlocks = await Promise.all(
      files.map(async (f) => {
        const dataUrl = await fileToDataUrl(f)
        return `![${f.name || 'image'}](${dataUrl})`
      }),
    )
    md = md ? `${md}\n\n${imageBlocks.join('\n\n')}` : imageBlocks.join('\n\n')
  }

  const appended = markdown.value
    ? `${markdown.value.trimEnd()}\n\n${md}`
    : md
  markdown.value = appended

  if (!titleTouched.value) {
    const derived = deriveTitle(md)
    if (derived) title.value = derived
  }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  resultText.value = ''
  try {
    const res = await service({
      url: '/api/auto/pending-notes',
      method: 'post',
      data: { title: title.value.trim(), markdown: markdown.value.trim() },
    })
    const data = res.data || {}
    if (data.added && data.added.length) {
      resultText.value = `已加入队列：${title.value.trim()}`
      resultKind.value = 'ok'
      title.value = ''
      markdown.value = ''
      titleTouched.value = false
      if (editorEl.value) editorEl.value.innerHTML = ''
      emit('submitted')
    } else if (data.duplicates && data.duplicates.length) {
      resultText.value = `已存在于 ${data.duplicates[0].existing_bucket || '队列'} 中（重复内容已忽略）`
      resultKind.value = 'warn'
    } else {
      resultText.value = '后端未返回新增或重复，请检查'
      resultKind.value = 'warn'
    }
  } catch (e) {
    resultText.value = `提交失败：${e.message || '未知错误'}`
    resultKind.value = 'err'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.note-paste-card { padding: 16px; border: 1px solid var(--border, #d0d7de); border-radius: 8px; margin-top: 16px; background: var(--card-bg, #fff); }
.npc-head { margin-bottom: 12px; }
.npc-row { margin-bottom: 8px; }
.npc-title { width: 100%; padding: 8px; font-size: 14px; border: 1px solid var(--border, #d0d7de); border-radius: 4px; }
.npc-split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; min-height: 180px; }
.npc-editor { padding: 10px; border: 1px dashed var(--border, #d0d7de); border-radius: 4px; overflow: auto; max-height: 420px; }
.npc-editor:empty::before { content: '在这里粘贴或输入…'; color: #999; }
.npc-preview { width: 100%; padding: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; border: 1px solid var(--border, #d0d7de); border-radius: 4px; resize: vertical; max-height: 420px; }
.npc-footer { display: flex; gap: 12px; align-items: center; margin-top: 10px; }
.npc-submit { padding: 8px 16px; border-radius: 4px; border: none; cursor: pointer; background: var(--primary, #0969da); color: #fff; }
.npc-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.npc-result.ok { color: var(--success, #1a7f37); }
.npc-result.warn { color: var(--warn, #9a6700); }
.npc-result.err { color: var(--danger, #cf222e); }
@media (max-width: 720px) { .npc-split { grid-template-columns: 1fr; } }
</style>
