<template>
  <div class="project-switcher" :class="{ open: isOpen }">
    <button
      type="button"
      class="switcher-trigger"
      :disabled="disabled"
      @click="toggle"
      :aria-expanded="isOpen"
    >
      <div class="trigger-label">
        <div class="kicker">{{ disabled ? '加载中...' : '当前项目' }}</div>
        <div class="current-name">
          <span v-if="currentProject" class="name-text">{{ currentProject.project_name || currentProject.project_id }}</span>
          <span v-else class="name-placeholder">未选择项目</span>
        </div>
      </div>
      <span class="caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="isOpen" class="switcher-panel" @click.stop>
      <div class="panel-header">
        <input
          ref="searchInput"
          v-model="search"
          type="text"
          class="panel-search"
          placeholder="搜索项目名或 ID..."
        />
      </div>
      <div class="panel-list">
        <div v-if="loading" class="panel-empty">正在加载...</div>
        <div v-else-if="error" class="panel-error">{{ error }}</div>
        <div v-else-if="!filtered.length" class="panel-empty">没有匹配项目</div>
        <button
          v-for="p in filtered"
          :key="p.project_id"
          type="button"
          class="panel-item"
          :class="{ active: p.project_id === currentProjectId }"
          @click="selectProject(p)"
        >
          <div class="item-main">
            <span class="item-name">{{ p.project_name || p.project_id }}</span>
            <span v-if="p.status" class="item-status">{{ p.status }}</span>
          </div>
          <div class="item-sub">{{ p.project_id }}</div>
        </button>
      </div>
      <div class="panel-footer">
        <router-link to="/workspace/overview" class="panel-footer-link" @click="close">
          查看项目总览 →
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import service from '../../api/index'

const props = defineProps({
  currentProjectId: { type: String, default: '' },
  // When navigating to a new project, try to preserve this section if present.
  preserveSection: { type: String, default: 'article' },
})

const router = useRouter()

const isOpen = ref(false)
const loading = ref(false)
const error = ref('')
const projects = ref([])
const search = ref('')
const searchInput = ref(null)

const currentProject = computed(() => {
  if (!props.currentProjectId) return null
  return projects.value.find((p) => p.project_id === props.currentProjectId) || null
})

const disabled = computed(() => loading.value && !projects.value.length)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return projects.value
  return projects.value.filter((p) => {
    const hay = `${p.project_name || ''} ${p.project_id || ''}`.toLowerCase()
    return hay.includes(q)
  })
})

async function loadProjects() {
  loading.value = true
  error.value = ''
  try {
    const res = await service({ url: '/api/registry/overview', method: 'get' })
    projects.value = res.data?.projects || []
  } catch (e) {
    error.value = e.message || '加载项目列表失败'
  } finally {
    loading.value = false
  }
}

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    if (!projects.value.length) loadProjects()
    nextTick(() => searchInput.value?.focus())
  }
}

function close() {
  isOpen.value = false
  search.value = ''
}

function selectProject(p) {
  close()
  router.push({
    name: 'Workspace',
    params: { projectId: p.project_id, section: props.preserveSection },
  })
}

function handleClickOutside(e) {
  if (!isOpen.value) return
  const el = e.target.closest?.('.project-switcher')
  if (!el) close()
}

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
  // Pre-warm cache so the current name can render on first click.
  if (props.currentProjectId) loadProjects()
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleClickOutside)
})

watch(() => props.currentProjectId, (next) => {
  if (next && !projects.value.length && !loading.value) loadProjects()
})
</script>

<style scoped>
.project-switcher {
  position: relative;
  width: 100%;
}

.switcher-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid #eadfcb;
  border-radius: 14px;
  cursor: pointer;
  text-align: left;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
.switcher-trigger:hover {
  border-color: #d8b079;
  box-shadow: 0 4px 12px rgba(159, 117, 51, 0.08);
}
.switcher-trigger:disabled {
  cursor: wait;
  opacity: 0.7;
}
.project-switcher.open .switcher-trigger {
  border-color: #bf7d28;
  box-shadow: 0 6px 16px rgba(191, 125, 40, 0.12);
}

.trigger-label {
  flex: 1;
  min-width: 0;
}
.kicker {
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #9a6b2e;
  font-weight: 700;
  margin-bottom: 2px;
}
.current-name {
  font-size: 14px;
  font-weight: 700;
  color: #1d1d1d;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.name-placeholder {
  color: #9a8d7c;
  font-weight: 500;
}
.caret {
  color: #9a6b2e;
  font-size: 12px;
}

.switcher-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 40;
  background: #fff;
  border: 1px solid #d4dce8;
  border-radius: 14px;
  box-shadow: 0 12px 32px rgba(44, 31, 13, 0.14);
  max-height: 360px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 10px;
  border-bottom: 1px solid #eef1f5;
}
.panel-search {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d4dce8;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}
.panel-search:focus { border-color: #4a6fa5; }

.panel-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.panel-empty,
.panel-error {
  padding: 16px;
  font-size: 13px;
  text-align: center;
  color: #7a8090;
}
.panel-error { color: #c62828; }

.panel-item {
  display: block;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  text-align: left;
  cursor: pointer;
  border-bottom: 1px solid #f3f4f7;
}
.panel-item:last-child { border-bottom: none; }
.panel-item:hover { background: #f5f8ff; }
.panel-item.active { background: #e8efff; }

.item-main {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.item-name {
  font-weight: 600;
  font-size: 13px;
  color: #1d1d1d;
}
.item-status {
  font-size: 11px;
  color: #7a8090;
  padding: 2px 6px;
  border-radius: 999px;
  background: #f0f4ff;
}
.item-sub {
  font-size: 11px;
  color: #9ba3b0;
  margin-top: 2px;
  font-family: 'JetBrains Mono', monospace;
}

.panel-footer {
  padding: 10px 14px;
  border-top: 1px solid #eef1f5;
  background: #fafbfc;
}
.panel-footer-link {
  font-size: 12px;
  color: #4a6fa5;
  text-decoration: none;
}
.panel-footer-link:hover { text-decoration: underline; }
</style>
