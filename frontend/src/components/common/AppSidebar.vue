<template>
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <router-link to="/workspace/overview" class="brand-row">
        <span class="brand-name">格物</span>
      </router-link>
      <div class="brand-sub">知识工作台</div>
    </div>

    <ProjectSwitcher
      :current-project-id="currentProjectId"
      :preserve-section="currentProjectSection || 'article'"
    />

    <nav class="sidebar-nav" aria-label="主导航">
      <div class="nav-group">
        <div class="group-label">按项目</div>
        <router-link
          v-for="item in projectGroup"
          :key="item.key"
          :to="resolveTarget(item)"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <span class="item-icon" aria-hidden="true">{{ item.icon }}</span>
          <span class="item-label">{{ item.label }}</span>
          <span v-if="item.hint" class="item-hint">{{ item.hint }}</span>
        </router-link>
      </div>

      <div class="nav-group">
        <div class="group-label">跨项目</div>
        <router-link
          v-for="item in globalGroup"
          :key="item.key"
          :to="resolveTarget(item)"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <span class="item-icon" aria-hidden="true">{{ item.icon }}</span>
          <span class="item-label">{{ item.label }}</span>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <router-link to="/" class="legacy-link" title="旧版流程（Phase 1 / 仿真 / 报告）">
        旧版 ↗
      </router-link>
      <div class="footer-build">Phase 2 · v0.1</div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ProjectSwitcher from './ProjectSwitcher.vue'

const props = defineProps({
  currentProjectId: { type: String, default: '' },
  currentProjectSection: { type: String, default: '' },
})

const route = useRoute()

// The five project sub-sections (文章图谱/项目概念/主题线索/项目演化/项目审核)
// used to live here as second-level sidebar items. Removed per UX review —
// they duplicate the horizontal section tabs inside WorkspacePage. Left nav
// now carries only the project-list entry point; per-section nav happens via
// the page's own tabs once a project is selected.
const projectGroup = [
  { key: 'overview', label: '项目总览', icon: '📁', target: { name: 'Overview' } },
]

const globalGroup = [
  { key: 'registry', label: '概念注册表', icon: '📒', target: '/workspace/registry' },
  { key: 'themeHub', label: '主题枢纽', icon: '🌐', target: '/workspace/themes' },
  { key: 'relations', label: '跨文关系', icon: '🔗', target: '/workspace/relations' },
  { key: 'evolutionGlobal', label: '演化日志', icon: '📜', target: '/workspace/registry?tab=evolution' },
  { key: 'reviewGlobal', label: '审核队列', icon: '🧾', target: '/workspace/registry?tab=review' },
  { key: 'auto', label: '自动处理', icon: '⚙️', target: '/workspace/auto' },
]

function resolveTarget(item) {
  return item.target
}

function isActive(item) {
  const path = route.path
  const query = route.query || {}

  // 项目总览 stays "active" not only on /workspace/overview but also while the
  // user is inside any specific project workspace — that's what the group
  // label "按项目" refers to, and there's no other sidebar item to highlight.
  if (item.key === 'overview') {
    return path === '/workspace/overview' || /^\/workspace\/[^/]+\/[^/]+$/.test(path)
  }
  if (item.key === 'themeHub') return path === '/workspace/themes' || path.startsWith('/workspace/themes/')
  if (item.key === 'auto') return path === '/workspace/auto'
  if (item.key === 'relations') return path === '/workspace/relations' || path.startsWith('/workspace/relations/')

  if (item.key === 'registry') return (path === '/workspace/registry' && (!query.tab || query.tab === 'concepts')) || path.startsWith('/workspace/entry/')
  if (item.key === 'evolutionGlobal') return path === '/workspace/registry' && query.tab === 'evolution'
  if (item.key === 'reviewGlobal') return path === '/workspace/registry' && query.tab === 'review'

  return false
}
</script>

<style scoped>
.app-sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--bg-surface-2);
  border-right: 1px solid var(--border-default);
  padding: 20px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--text-primary);
}

.sidebar-brand {
  padding: 0 4px;
}
.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: inherit;
}
.brand-mark {
  font-size: 22px;
}
.brand-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}
.brand-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-muted);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
}
.nav-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.group-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-group-label);
  padding: 4px 10px 6px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  text-decoration: none;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  transition: background 120ms ease, color 120ms ease;
}
.nav-item:hover {
  background: var(--bg-muted);
}
.nav-item.active {
  background: var(--bg-selected);
  color: var(--accent-primary-hover);
  font-weight: 700;
  box-shadow: inset 2px 0 0 0 var(--accent-primary);
}
.nav-item.disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}
.nav-item.disabled:hover { background: transparent; }
.item-icon {
  width: 18px;
  text-align: center;
  font-size: 14px;
}
.item-label { flex: 1; }
.item-hint {
  font-size: 10px;
  color: var(--text-muted);
}

.sidebar-footer {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 8px 0;
  border-top: 1px solid var(--border-default);
}
.legacy-link {
  font-size: 11px;
  color: var(--text-muted);
  text-decoration: none;
}
.legacy-link:hover {
  color: var(--accent-primary-hover);
  text-decoration: underline;
}
.footer-build {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

@media (max-width: 960px) {
  .app-sidebar {
    width: 100%;
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
    flex-direction: column;
  }
}
</style>
