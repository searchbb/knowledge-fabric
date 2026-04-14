<template>
  <div class="theme-switcher" role="radiogroup" aria-label="外观主题">
    <button
      v-for="t in themes"
      :key="t.id"
      type="button"
      class="theme-card"
      :class="{ active: currentId === t.id }"
      role="radio"
      :aria-checked="currentId === t.id"
      @click="onSelect(t.id)"
    >
      <div class="swatches" aria-hidden="true">
        <span
          v-for="(c, i) in t.swatch"
          :key="i"
          class="swatch"
          :style="{ background: c }"
        ></span>
      </div>
      <div class="meta">
        <div class="name">
          {{ t.name }}
          <span v-if="currentId === t.id" class="check" aria-hidden="true">✓</span>
        </div>
        <div class="name-en">{{ t.nameEn }}</div>
        <div class="blurb">{{ t.blurb }}</div>
      </div>
    </button>
  </div>
</template>

<script setup>
import { useTheme } from '../../composables/useTheme'

const { currentId, themes, setTheme } = useTheme()

function onSelect(id) {
  setTheme(id)
}
</script>

<style scoped>
.theme-switcher {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}

.theme-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-default);
  background: var(--bg-elevated);
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: background 120ms ease, border-color 120ms ease, transform 80ms ease;
}
.theme-card:hover {
  background: var(--bg-muted);
  border-color: var(--border-strong);
}
.theme-card:active {
  transform: translateY(1px);
}
.theme-card.active {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px var(--accent-soft);
  background: var(--bg-selected);
}
.theme-card:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}

.swatches {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border-radius: 8px;
  background: var(--bg-surface-2);
  border: 1px solid var(--border-muted);
  flex-shrink: 0;
}
.swatch {
  width: 14px;
  height: 28px;
  border-radius: 4px;
  display: inline-block;
}

.meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}
.check {
  color: var(--accent-primary);
  font-size: 12px;
  font-weight: 900;
}
.name-en {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.blurb {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
