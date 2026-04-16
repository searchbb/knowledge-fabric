<template>
  <AppShell
    :crumbs="crumbs"
    :project-id="projectId"
    :project-section="activeView"
  >
    <template #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <div class="workspace-wrap">
      <header class="workspace-header">
        <div class="section-badge">PROJECT WORKSPACE</div>
        <h1 class="workspace-title">{{ pageTitle }}</h1>
        <p class="workspace-subtitle">{{ pageSubtitle }}</p>
      </header>

      <!-- Section tabs -->
      <nav class="section-tabs" aria-label="项目子视图">
        <button
          v-for="item in navItems"
          :key="item.key"
          class="section-tab"
          :class="{ active: item.key === activeView }"
          @click="handleSelectView(item.key)"
        >
          {{ navLabels[item.key] || item.label }}
        </button>
      </nav>

      <section v-if="error" class="state-card error-card">
        <div class="state-title">加载失败</div>
        <div class="state-body">{{ error }}</div>
      </section>

      <section v-else-if="loading" class="state-card">
        <div class="state-title">正在加载工作台状态</div>
        <div class="state-body">复用现有项目、图谱和阅读骨架状态，避免新旧路径数据分叉。</div>
      </section>

      <section v-else class="content-slot" :class="{ 'content-slot--graph': activeView === 'article' }">
        <component
          :is="activePageComponent"
          :project="projectData"
          :graph-data="graphData"
          :phase1-task-result="phase1TaskResult"
          :refreshing="loading"
          :embedded="true"
          @refresh="loadWorkspace"
        />
      </section>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import ArticleViewPage from '../ArticleViewPage/ArticleViewPage.vue'
import ConceptViewPage from '../ConceptViewPage/ConceptViewPage.vue'
import ProjectThemeSignalsView from '../ProjectThemeSignalsView/ProjectThemeSignalsView.vue'
import EvolutionViewPage from '../EvolutionViewPage/EvolutionViewPage.vue'
import ReviewPage from '../ReviewPage/ReviewPage.vue'
import {
  DEFAULT_WORKSPACE_VIEW,
  WORKSPACE_NAV_ITEMS,
  normalizeWorkspaceView,
  workspaceStore,
} from '../../stores/workspaceStore'
import { getProjectWorkbench } from '../../data/dataClient'
import { appMode } from '../../runtime/appMode'

const route = useRoute()
const router = useRouter()

const pageComponentMap = {
  article: ArticleViewPage,
  concepts: ConceptViewPage,
  themes: ProjectThemeSignalsView,
  evolution: EvolutionViewPage,
  review: ReviewPage,
}

// Renamed labels to match the new "按项目" IA (Apr 2026 nav redesign).
const navLabels = {
  article: '文章图谱',
  concepts: '项目概念',
  themes: '主题线索',
  evolution: '项目演化',
  review: '项目审核',
}

const pageMeta = {
  article: {
    title: '文章图谱',
    subtitle: '单篇文章的抽取结果与阅读骨架。作为项目级验收入口。',
  },
  concepts: {
    title: '项目概念',
    subtitle: '本项目的 canonical 概念与 local concept 对齐治理。',
  },
  themes: {
    title: '主题线索',
    subtitle: '本项目的主题簇与到全局主题的映射视图。',
  },
  evolution: {
    title: '项目演化',
    subtitle: '本项目随时间补充既有主题和概念的演化轨迹。',
  },
  review: {
    title: '项目审核',
    subtitle: '本项目的待归一、待确认关系与主题归属的 ReviewTask 队列。',
  },
}

const navItems = WORKSPACE_NAV_ITEMS
const loading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const phase1TaskResult = ref(null)

const projectId = computed(() => route.params.projectId || '')
const activeView = computed(() => normalizeWorkspaceView(route.params.section))
const activePageComponent = computed(() => pageComponentMap[activeView.value] || ArticleViewPage)
const pageTitle = computed(() => pageMeta[activeView.value]?.title || pageMeta[DEFAULT_WORKSPACE_VIEW].title)
const pageSubtitle = computed(() => pageMeta[activeView.value]?.subtitle || pageMeta[DEFAULT_WORKSPACE_VIEW].subtitle)

const crumbs = computed(() => {
  const name = projectData.value?.name || projectId.value || '项目'
  return [
    { label: '按项目', to: '/workspace/overview' },
    { label: name, to: `/workspace/${projectId.value}/${activeView.value}` },
    { label: navLabels[activeView.value] || pageTitle.value },
  ]
})

function ensureCanonicalWorkspaceRoute() {
  const pid = route.params.projectId
  if (!pid) return
  const nextView = normalizeWorkspaceView(route.params.section)
  if (route.params.section === nextView) return
  router.replace({
    name: 'Workspace',
    params: { projectId: pid, section: nextView },
  })
}

async function loadWorkspace() {
  const pid = route.params.projectId
  if (!pid) {
    error.value = '缺少 projectId'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const state = await getProjectWorkbench(pid)
    projectData.value = state.project
    graphData.value = state.graphData
    phase1TaskResult.value = state.phase1TaskResult
    workspaceStore.currentProjectId = pid
    workspaceStore.currentView = activeView.value
    workspaceStore.project = state.project
    workspaceStore.graphData = state.graphData
    workspaceStore.phase1TaskResult = state.phase1TaskResult
    workspaceStore.error = ''
  } catch (loadError) {
    // Clear stale project/graph state on error — otherwise, switching
    // live↔demo for a project that exists in one mode but not the other
    // leaves the old project's breadcrumb + metadata visible alongside
    // the error card.
    projectData.value = null
    graphData.value = null
    phase1TaskResult.value = null
    workspaceStore.project = null
    workspaceStore.graphData = null
    workspaceStore.phase1TaskResult = null
    error.value = loadError.message || '工作台加载失败'
    workspaceStore.error = error.value
  } finally {
    loading.value = false
  }
}

function handleSelectView(viewKey) {
  const nextView = normalizeWorkspaceView(viewKey)
  workspaceStore.currentView = nextView
  router.push({
    name: 'Workspace',
    params: { projectId: route.params.projectId, section: nextView },
  })
}

watch(activeView, (nextView) => {
  workspaceStore.currentView = nextView
})

watch(
  () => route.params.section,
  () => { ensureCanonicalWorkspaceRoute() },
  { immediate: true },
)

watch(
  () => route.params.projectId,
  () => {
    ensureCanonicalWorkspaceRoute()
    loadWorkspace()
  },
  { immediate: true },
)

// Reload when live/demo flips so the workspace swaps data source without
// a browser refresh.
watch(appMode, () => {
  loadWorkspace()
})
</script>

<style scoped>
/* Flex column so the active section (.content-slot) can flex: 1 when it
   needs to fill the viewport (article graph). Max-width still centers via
   width + margin auto; `width: 100%` required once parent is flex. */
.workspace-wrap {
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.workspace-header { margin-bottom: 16px; }
.section-badge {
  font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--accent-group-label); font-weight: 700; margin-bottom: 6px;
}
.workspace-title { margin: 0; font-size: 28px; color: var(--text-primary); }
.workspace-subtitle { margin: 6px 0 0; color: var(--text-secondary); font-size: 14px; line-height: 1.6; }

.section-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border-default);
  margin: 18px 0 20px;
}
.section-tab {
  padding: 10px 18px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease;
}
.section-tab:hover { color: var(--accent-primary-hover); }
.section-tab.active {
  color: var(--accent-primary-hover);
  border-bottom-color: var(--accent-primary);
  font-weight: 700;
}

.topbar-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 8px;
  border: 1px solid var(--border-default); background: var(--bg-elevated);
  color: var(--accent-primary); font-size: 12px; font-weight: 500;
  text-decoration: none; cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover { background: var(--bg-muted); border-color: var(--border-strong); }

.state-card,
.content-slot {
  border: 1px solid var(--border-default);
  border-radius: 20px;
  background: var(--bg-elevated);
  padding: 22px;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.05);
}
/* Article view embeds a full graph panel — strip the box so the graph
   takes full width + height. flex:1 + min-height:0 lets the graph wrapper
   fill remaining vertical space without absolute-positioning hacks. */
.content-slot--graph {
  border: none;
  background: transparent;
  padding: 0;
  box-shadow: none;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.error-card {
  border-color: var(--state-danger);
  background: var(--bg-muted);
}
.state-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.state-body {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}
</style>
