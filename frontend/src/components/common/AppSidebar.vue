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
      <div
        v-for="section in navSections"
        :key="section.key"
        class="nav-group"
        :class="{ 'nav-group-collapsible': section.collapsible }"
      >
        <button
          v-if="section.collapsible"
          type="button"
          class="group-label group-trigger"
          :class="{ active: isGroupActive(section), open: isGroupOpen(section) }"
          :aria-expanded="isGroupOpen(section)"
          @click="toggleGroup(section)"
        >
          <span class="group-disclosure" aria-hidden="true">{{ isGroupOpen(section) ? '▾' : '▸' }}</span>
          <span>{{ section.label }}</span>
        </button>
        <div v-else class="group-label">{{ section.label }}</div>

        <div v-if="!section.collapsible || isGroupOpen(section)" class="nav-entries">
          <template v-for="entry in section.entries" :key="entry.key">
            <router-link
              v-if="entry.type !== 'group'"
              :to="resolveTarget(entry)"
              class="nav-item"
              :class="{ active: isActive(entry) }"
            >
              <span class="item-icon" aria-hidden="true">{{ entry.icon }}</span>
              <span class="item-label">{{ entry.label }}</span>
              <span v-if="entry.hint" class="item-hint">{{ entry.hint }}</span>
            </router-link>

            <div
              v-else
              class="nav-collapsible"
              :class="{ active: isGroupActive(entry), open: isGroupOpen(entry) }"
            >
              <button
                type="button"
                class="nav-item nav-disclosure"
                :class="{ active: isGroupActive(entry) }"
                :aria-expanded="isGroupOpen(entry)"
                @click="toggleGroup(entry)"
              >
                <span class="item-icon group-disclosure" aria-hidden="true">{{ isGroupOpen(entry) ? '▾' : '▸' }}</span>
                <span class="item-label">{{ entry.label }}</span>
              </button>
              <div v-if="isGroupOpen(entry)" class="nav-subitems">
                <router-link
                  v-for="child in entry.children"
                  :key="child.key"
                  :to="resolveTarget(child)"
                  class="nav-item nav-subitem"
                  :class="{ active: isActive(child) }"
                >
                  <span class="item-label">{{ child.label }}</span>
                </router-link>
              </div>
            </div>
          </template>
        </div>
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
import { reactive } from 'vue'
import { useRoute } from 'vue-router'
import ProjectSwitcher from './ProjectSwitcher.vue'

const props = defineProps({
  currentProjectId: { type: String, default: '' },
  currentProjectSection: { type: String, default: '' },
})

const route = useRoute()
const openGroups = reactive({})

// The five project sub-sections (文章图谱/项目概念/主题线索/项目演化/项目审核)
// used to live here as second-level sidebar items. Removed per UX review —
// they duplicate the horizontal section tabs inside WorkspacePage. Left nav
// now carries only the project-list entry point; per-section nav happens via
// the page's own tabs once a project is selected.
const processingGroup = [
  { key: 'auto', label: '自动处理', icon: '📥', target: '/workspace/auto' },
  { key: 'wikiIntake', label: '素材加工台', icon: '🧰', target: '/workspace/wiki-intake' },
  {
    key: 'queuesAndLogs',
    type: 'group',
    label: '队列与日志',
    children: [
      { key: 'discoverQueue', label: 'Discover 队列', target: '/workspace/discover' },
      { key: 'reviewGlobal', label: '审核队列', target: '/workspace/registry?tab=review' },
      { key: 'evolutionGlobal', label: '演化日志', target: '/workspace/registry?tab=evolution' },
    ],
  },
]

const knowledgeGroup = [
  { key: 'topicClusters', label: '主题汇集', icon: '◎', target: '/workspace/topic-clusters' },
]

const researchGroup = [
  { key: 'researchProjects', label: '战略研究', icon: '研', target: '/workspace/research' },
  { key: 'researchReviewWorkspace', label: '审核工作台', icon: '审', target: '/workspace/research/review' },
]

const moreToolsGroup = [
  { key: 'overview', label: '项目总览', icon: '项', target: { name: 'Overview' } },
  { key: 'registry', label: '概念注册表', icon: '概', target: '/workspace/registry' },
  { key: 'wikiTopics', label: '主题总览', icon: '目', target: '/workspace/wiki-topics' },
  { key: 'themeHub', label: '主题枢纽', icon: '枢', target: '/workspace/themes' },
  { key: 'relations', label: '跨文关系', icon: '关', target: '/workspace/relations' },
]

const navSections = [
  { key: 'processing', label: '素材处理', entries: processingGroup },
  { key: 'knowledge', label: '知识组织', entries: knowledgeGroup },
  { key: 'research', label: '战略研究', entries: researchGroup },
  { key: 'moreTools', label: '更多工具', collapsible: true, entries: moreToolsGroup },
]

function resolveTarget(item) {
  return item.target
}

function isGroupActive(group) {
  const entries = group.entries || group.children || []
  return entries.some((entry) => entry.type === 'group' ? isGroupActive(entry) : isActive(entry))
}

function isGroupOpen(group) {
  if (isGroupActive(group)) return true
  return Boolean(openGroups[group.key])
}

function toggleGroup(group) {
  openGroups[group.key] = !isGroupOpen(group)
}

function isActive(item) {
  const path = route.path
  const query = route.query || {}

  // Keep concrete project workspaces associated with 项目总览 without stealing
  // active state from global detail pages such as topic clusters or wiki topics.
  if (item.key === 'overview') {
    return path === '/workspace/overview' || /^\/workspace\/proj_[^/]+\/[^/]+$/.test(path)
  }
  if (item.key === 'themeHub') return path === '/workspace/themes' || path.startsWith('/workspace/themes/')
  if (item.key === 'auto') return path === '/workspace/auto'
  if (item.key === 'discoverQueue') return path === '/workspace/discover'
  if (item.key === 'researchProjects') return path === '/workspace/research'
  if (item.key === 'researchReviewWorkspace') return path === '/workspace/research/review'
  if (item.key === 'relations') return path === '/workspace/relations' || path.startsWith('/workspace/relations/')
  if (item.key === 'topicClusters') return path === '/workspace/topic-clusters' || path.startsWith('/workspace/topic-clusters/')
  if (item.key === 'wikiIntake') return path === '/workspace/wiki-intake'
  if (item.key === 'wikiTopics') return path === '/workspace/wiki-topics' || path.startsWith('/workspace/wiki-topics/')

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
.nav-entries,
.nav-subitems {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-group-label);
  padding: 4px 10px 6px;
}
.group-trigger {
  width: 100%;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}
.group-trigger:hover,
.group-trigger.active {
  color: var(--accent-primary-hover);
}
.group-disclosure {
  width: 14px;
  text-align: center;
  font-size: 12px;
  letter-spacing: 0;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 0;
  background: transparent;
  text-decoration: none;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  text-align: left;
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
.nav-disclosure {
  width: 100%;
  cursor: pointer;
}
.nav-collapsible.active > .nav-disclosure {
  background: var(--bg-selected);
  color: var(--accent-primary-hover);
  font-weight: 700;
}
.nav-subitems {
  margin-left: 28px;
  padding-left: 8px;
  border-left: 1px solid var(--border-default);
}
.nav-subitem {
  padding: 7px 10px;
  color: var(--text-secondary);
}
.nav-subitem.active {
  color: var(--accent-primary-hover);
}
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
