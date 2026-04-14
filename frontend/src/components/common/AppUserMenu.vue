<template>
  <div class="user-menu" ref="rootEl">
    <button
      type="button"
      class="user-menu-trigger"
      :class="{ open }"
      @click="toggle"
      aria-haspopup="menu"
      :aria-expanded="open"
      :title="currentTheme.name + ' · 点击切换外观'"
    >
      <span class="avatar" aria-hidden="true">格</span>
    </button>

    <div v-if="open" class="user-menu-panel" role="menu">
      <div class="section-label">外观</div>
      <ThemeSwitcher />
      <div class="panel-footer">
        当前:{{ currentTheme.name }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import ThemeSwitcher from '../settings/ThemeSwitcher.vue'
import { useTheme } from '../../composables/useTheme'

const { currentTheme } = useTheme()
const open = ref(false)
const rootEl = ref(null)

function toggle() {
  open.value = !open.value
}

function handleDocClick(e) {
  if (!open.value) return
  if (rootEl.value && !rootEl.value.contains(e.target)) {
    open.value = false
  }
}

function handleEsc(e) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleDocClick)
  document.addEventListener('keydown', handleEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleDocClick)
  document.removeEventListener('keydown', handleEsc)
})
</script>

<style scoped>
.user-menu {
  position: relative;
  display: inline-block;
}

.user-menu-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid var(--border-default);
  background: var(--bg-elevated);
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
}
.user-menu-trigger:hover {
  background: var(--bg-muted);
  border-color: var(--border-strong);
}
.user-menu-trigger.open,
.user-menu-trigger:focus-visible {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px var(--accent-soft);
  outline: none;
}

.avatar {
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-weight: 800;
  font-size: 14px;
  color: var(--accent-primary);
  letter-spacing: 0;
  line-height: 1;
  /* 中文字符视觉重心偏下,手动微调一下 */
  transform: translateY(-0.5px);
}

.user-menu-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 260px;
  padding: 8px 4px;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: var(--bg-elevated);
  box-shadow: 0 12px 28px -12px rgba(0, 0, 0, 0.22), 0 4px 10px -4px rgba(0, 0, 0, 0.08);
  z-index: 40;
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-group-label);
  padding: 6px 12px 4px;
}

.panel-footer {
  padding: 8px 12px 4px;
  margin-top: 4px;
  border-top: 1px solid var(--border-muted);
  font-size: 11px;
  color: var(--text-muted);
}
</style>
