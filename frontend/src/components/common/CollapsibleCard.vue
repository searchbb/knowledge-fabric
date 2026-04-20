<template>
  <details
    class="collapsible-card"
    :open="isOpen"
    @toggle="onToggle"
  >
    <summary class="cc-summary">
      <span class="cc-chevron" aria-hidden="true">›</span>
      <span class="cc-title">{{ title }}</span>
      <span v-if="badge !== null && badge !== undefined && badge !== ''" class="cc-badge">
        {{ badge }}
      </span>
      <span class="cc-spacer"></span>
      <slot name="summary-extra" />
    </summary>
    <p v-if="subtitle" class="cc-subtitle">{{ subtitle }}</p>
    <div class="cc-body">
      <slot />
    </div>
  </details>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  badge: { type: [String, Number], default: null },
  storageKey: { type: String, required: true },
  defaultOpen: { type: Boolean, default: false },
  forceOpen: { type: Boolean, default: false },
})

const touchedKey = computed(() => `${props.storageKey}:touched`)
const stored = ref(null)
const touched = ref(false)

function readInitial() {
  try {
    stored.value = localStorage.getItem(props.storageKey)
    touched.value = localStorage.getItem(touchedKey.value) === '1'
  } catch {
    stored.value = null
    touched.value = false
  }
}

readInitial()

const isOpen = computed(() => {
  if (stored.value === 'open') return true
  if (stored.value === 'closed') return false
  if (props.forceOpen && !touched.value) return true
  return props.defaultOpen
})

function onToggle(event) {
  const open = event.target.open
  stored.value = open ? 'open' : 'closed'
  touched.value = true
  try {
    localStorage.setItem(props.storageKey, stored.value)
    localStorage.setItem(touchedKey.value, '1')
  } catch {
    /* storage unavailable — ignore, in-memory state still works */
  }
}
</script>

<style scoped>
.collapsible-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--card-border, #e5e7eb);
  border-radius: 10px;
  padding: 0;
  margin-bottom: 16px;
}

.cc-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.cc-summary::-webkit-details-marker {
  display: none;
}

.cc-summary:hover {
  background: rgba(0, 0, 0, 0.02);
}

.cc-chevron {
  display: inline-block;
  transition: transform 0.15s ease;
  color: #6b7280;
  font-size: 16px;
  line-height: 1;
}

.collapsible-card[open] .cc-chevron {
  transform: rotate(90deg);
}

.cc-title {
  font-weight: 600;
  font-size: 14px;
  color: #111827;
}

.cc-badge {
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  line-height: 1.5;
}

.cc-spacer {
  flex: 1;
}

.cc-subtitle {
  color: #6b7280;
  font-size: 13px;
  margin: 0 18px 4px 42px;
}

.cc-body {
  padding: 4px 18px 16px 18px;
}
</style>
