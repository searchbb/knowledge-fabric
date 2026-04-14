<template>
  <header class="app-topbar">
    <nav class="breadcrumbs" aria-label="面包屑">
      <template v-for="(item, idx) in crumbs" :key="idx">
        <span v-if="idx > 0" class="sep" aria-hidden="true">/</span>
        <router-link v-if="item.to && idx !== crumbs.length - 1" :to="item.to" class="crumb">
          {{ item.label }}
        </router-link>
        <span v-else class="crumb current">{{ item.label }}</span>
      </template>
    </nav>

    <div class="topbar-actions">
      <slot name="actions">
        <CopyLinkButton v-if="showCopy" />
        <a
          v-if="showNewTab"
          class="new-tab-btn"
          :href="currentPath"
          target="_blank"
          rel="noopener"
          title="在新页面打开"
        >
          <span class="icon" aria-hidden="true">↗</span>
          <span class="label">新页</span>
        </a>
      </slot>
      <AppUserMenu />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import CopyLinkButton from './CopyLinkButton.vue'
import AppUserMenu from './AppUserMenu.vue'

const props = defineProps({
  crumbs: {
    type: Array,
    required: true,
  },
  showCopy: { type: Boolean, default: true },
  showNewTab: { type: Boolean, default: true },
})

const route = useRoute()

const currentPath = computed(() => route.fullPath)
</script>

<style scoped>
.app-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-muted);
  min-height: 56px;
}

.breadcrumbs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-secondary);
  min-width: 0;
}
.crumb {
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
}
.crumb:hover { color: var(--accent-primary-hover); text-decoration: underline; }
.crumb.current {
  color: var(--text-primary);
  font-weight: 700;
}
.sep { color: var(--text-muted); }

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.new-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-elevated);
  color: var(--accent-primary);
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.new-tab-btn:hover {
  background: var(--bg-muted);
  border-color: var(--border-strong);
}
.new-tab-btn .icon { font-size: 13px; }
</style>
