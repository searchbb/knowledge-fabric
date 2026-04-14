<template>
  <button
    type="button"
    class="copy-link-btn"
    :class="{ copied: state === 'copied', failed: state === 'failed' }"
    :title="title"
    @click="handleCopy"
  >
    <span class="icon" aria-hidden="true">
      <template v-if="state === 'copied'">✓</template>
      <template v-else-if="state === 'failed'">!</template>
      <template v-else>🔗</template>
    </span>
    <span class="label">
      <template v-if="state === 'copied'">已复制</template>
      <template v-else-if="state === 'failed'">复制失败</template>
      <template v-else>{{ label }}</template>
    </span>
  </button>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  url: {
    type: String,
    default: '',
  },
  label: {
    type: String,
    default: '复制链接',
  },
  title: {
    type: String,
    default: '复制该页面的可分享链接',
  },
})

const state = ref('idle')

async function handleCopy() {
  const target = props.url || window.location.href
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(target)
    } else {
      // Fallback: select a temporary textarea. Deliberately narrow — runs only when
      // the clipboard API is unavailable (older browsers / insecure contexts).
      const ta = document.createElement('textarea')
      ta.value = target
      ta.style.position = 'fixed'
      ta.style.top = '-1000px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    state.value = 'copied'
  } catch (err) {
    state.value = 'failed'
    console.error('[CopyLinkButton] copy failed:', err)
  }
  setTimeout(() => { state.value = 'idle' }, 1800)
}
</script>

<style scoped>
.copy-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #4a6fa5;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.copy-link-btn:hover {
  background: #f0f4ff;
  border-color: #a9bbd9;
}
.copy-link-btn.copied {
  background: #e8f5e9;
  border-color: #a5d6a7;
  color: #2e7d32;
}
.copy-link-btn.failed {
  background: #ffebee;
  border-color: #ef9a9a;
  color: #c62828;
}
.icon {
  font-size: 14px;
  line-height: 1;
}
.label {
  font-size: 12px;
  white-space: nowrap;
}
</style>
