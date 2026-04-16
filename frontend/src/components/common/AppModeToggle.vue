<template>
  <div
    class="mode-toggle"
    role="group"
    aria-label="运行模式切换"
    :title="title"
  >
    <button
      type="button"
      class="mode-seg"
      :class="{ active: !isDemoActive }"
      :aria-pressed="!isDemoActive"
      @click="select('live')"
    >Live</button>
    <button
      type="button"
      class="mode-seg"
      :class="{ active: isDemoActive }"
      :aria-pressed="isDemoActive"
      @click="select('demo')"
    >Demo</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { appMode, setMode, APP_MODES } from '../../runtime/appMode'

const isDemoActive = computed(() => appMode.value === APP_MODES.DEMO)

const title = computed(() =>
  isDemoActive.value
    ? '当前：Demo 数据。点击 Live 切回真实后端。'
    : '当前：Live 真实后端。点击 Demo 查看示例数据。',
)

function select(target) {
  setMode(target === 'demo' ? APP_MODES.DEMO : APP_MODES.LIVE)
}
</script>

<style scoped>
.mode-toggle {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  border: 1px solid var(--border-default, #d4dce8);
  background: var(--bg-elevated, #fff);
  /* Same vertical rhythm as the neighbouring action buttons. */
  height: 30px;
  align-items: stretch;
  overflow: hidden;
}
.mode-seg {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--text-secondary, #5a6b85);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 0 10px;
  min-width: 44px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 120ms ease, color 120ms ease;
}
.mode-seg:hover:not(.active) {
  background: var(--bg-muted, #f3f6fb);
  color: var(--text-primary, #1f2a44);
}
.mode-seg.active {
  background: var(--accent-primary, #4a6fa5);
  color: #fff;
  box-shadow: 0 1px 2px rgba(20, 40, 80, 0.12);
}
.mode-seg:focus-visible {
  outline: 2px solid var(--accent-primary, #4a6fa5);
  outline-offset: 2px;
}
</style>
