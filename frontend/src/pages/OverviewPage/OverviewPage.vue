<template>
  <AppShell :crumbs="crumbs">
    <div class="overview-wrap">
    <header class="overview-header">
      <div class="section-badge">PROJECT OVERVIEW</div>
      <h1 class="section-title">项目总览</h1>
      <p class="section-copy">所有项目的概念对齐、主题聚类与审核状态一览。</p>
    </header>

    <div v-if="loading" class="state-card">正在加载项目总览...</div>
    <div v-else-if="error" class="state-card error-card">{{ error }}</div>

    <template v-else>
      <!-- Global stats -->
      <div class="summary-grid">
        <article class="card">
          <div class="card-title">项目数</div>
          <div class="metric-value">{{ data.project_count || 0 }}</div>
        </article>
        <article class="card">
          <div class="card-title">注册表条目</div>
          <div class="metric-value">{{ data.global_stats?.registry_entries || 0 }}</div>
        </article>
        <article class="card">
          <div class="card-title">全局主题</div>
          <div class="metric-value">{{ data.global_stats?.global_themes || 0 }}</div>
        </article>
        <article class="card">
          <div class="card-title">待审核</div>
          <div class="metric-value">{{ data.global_stats?.pending_reviews || 0 }}</div>
        </article>
      </div>

      <!-- Gap #9: filter toolbar. Single-select status filter + free-text
           name filter so the user can quickly narrow 113 rows to e.g.
           "only failed" or "only my Markdown experiments". -->
      <div class="filter-toolbar">
        <label class="filter-label">状态</label>
        <select v-model="statusFilter" class="filter-select">
          <option value="all">全部 ({{ data.projects?.length || 0 }})</option>
          <option
            v-for="opt in statusOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }} ({{ opt.count }})
          </option>
        </select>
        <input
          v-model="nameFilter"
          type="text"
          placeholder="按名称过滤..."
          class="filter-input"
        />
        <span class="filter-summary">显示 {{ filteredProjects.length }} / {{ data.projects?.length || 0 }}</span>
      </div>

      <!-- Project list -->
      <div class="project-table">
        <div class="table-header">
          <span class="col-name">项目</span>
          <span class="col-num">概念</span>
          <span class="col-num">已确认</span>
          <span class="col-num">已链接</span>
          <span class="col-num">对齐率</span>
          <span class="col-num">主题簇</span>
          <span class="col-num">待审核</span>
          <span class="col-action">操作</span>
        </div>

        <div v-if="!data.projects?.length" class="empty-state">暂无项目</div>
        <div v-else-if="!filteredProjects.length" class="empty-state">
          没有匹配当前过滤条件的项目
        </div>

        <div v-for="p in filteredProjects" :key="p.project_id" class="table-row">
          <span class="col-name">
            <div class="project-name">{{ p.project_name }}</div>
            <div class="project-meta">
              <span :class="['status-pill', statusPillClass(p.status)]">{{ p.status }}</span>
              <span class="project-id">{{ p.project_id }}</span>
            </div>
          </span>
          <span class="col-num">{{ p.concept_count }}</span>
          <span class="col-num">{{ p.accepted_concept_count }}</span>
          <span class="col-num">{{ p.linked_concept_count }}</span>
          <span class="col-num">
            <span class="coverage-badge" :class="coverageClass(p.alignment_coverage)">
              {{ Math.round(p.alignment_coverage * 100) }}%
            </span>
          </span>
          <span class="col-num">{{ p.theme_cluster_count }}</span>
          <span class="col-num">{{ p.pending_review_count }}</span>
          <span class="col-action">
            <router-link :to="`/workspace/${p.project_id}/concepts`" class="btn-small">工作台</router-link>
          </span>
        </div>
      </div>

      <div class="nav-row">
        <router-link to="/workspace/registry" class="btn-primary">进入概念注册表</router-link>
        <router-link to="/workspace/themes" class="btn-primary">进入主题枢纽</router-link>
        <router-link to="/workspace/auto" class="btn-primary">自动处理队列</router-link>
      </div>
    </template>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '../../components/common/AppShell.vue'
import { getOverview } from '../../data/dataClient'
import { appMode } from '../../runtime/appMode'

const crumbs = [
  { label: '按项目', to: '/workspace/overview' },
  { label: '项目总览' },
]

const data = ref({})
const loading = ref(false)
const error = ref('')

// Gap #9 filter state
const statusFilter = ref('all')
const nameFilter = ref('')

function coverageClass(val) {
  if (val >= 0.8) return 'high'
  if (val >= 0.4) return 'medium'
  return 'low'
}

function statusPillClass(status) {
  if (!status) return 'status-unknown'
  if (status === 'graph_completed') return 'status-completed'
  if (status === 'failed') return 'status-failed'
  if (status === 'graph_building') return 'status-building'
  if (status === 'cancelled') return 'status-cancelled'
  return 'status-other'
}

// Build the status dropdown options dynamically from the actual
// project list so the user only sees statuses that exist in their data.
// Each option reports its own count so the dropdown doubles as a
// lightweight distribution summary.
const statusOptions = computed(() => {
  const counts = {}
  for (const p of data.value.projects || []) {
    const key = p.status || 'unknown'
    counts[key] = (counts[key] || 0) + 1
  }
  // Stable preferred ordering so "failed" always lands near the top even
  // when counts shift between loads.
  const preferred = [
    'failed',
    'graph_building',
    'cancelled',
    'graph_completed',
    'unknown',
  ]
  const ordered = []
  for (const key of preferred) {
    if (counts[key]) {
      ordered.push({ value: key, label: key, count: counts[key] })
      delete counts[key]
    }
  }
  for (const key of Object.keys(counts).sort()) {
    ordered.push({ value: key, label: key, count: counts[key] })
  }
  return ordered
})

const filteredProjects = computed(() => {
  const all = data.value.projects || []
  const nameQ = nameFilter.value.trim().toLowerCase()
  return all.filter((p) => {
    if (statusFilter.value !== 'all' && (p.status || 'unknown') !== statusFilter.value) {
      return false
    }
    if (nameQ) {
      const hay = `${p.project_name || ''} ${p.project_id || ''}`.toLowerCase()
      if (!hay.includes(nameQ)) return false
    }
    return true
  })
})

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    const res = await getOverview()
    data.value = res.data || {}
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)

// Refetch when the user flips Live/Demo in the topbar so the page
// reflects the new data source immediately — no full browser reload.
watch(appMode, () => {
  loadOverview()
})
</script>

<style scoped>
.overview-wrap { max-width: 1200px; margin: 0 auto; }
.overview-header { margin-bottom: 24px; }
.section-badge { font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent-primary); font-weight: 700; }
.section-title { margin: 8px 0 0; font-size: 28px; color: var(--text-primary); }
.section-copy { color: var(--text-secondary); line-height: 1.6; }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.card, .state-card { border: 1px solid var(--border-default); background: var(--bg-surface); border-radius: 18px; padding: 18px; }
.error-card { border-color: var(--state-danger); background: var(--bg-muted); }
.card-title { font-weight: 700; color: var(--text-primary); margin-bottom: 10px; }
.metric-value { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.project-table { border: 1px solid var(--border-default); border-radius: 18px; overflow: hidden; background: var(--bg-elevated); }
.table-header { display: grid; grid-template-columns: 2fr repeat(6, 1fr) 100px; padding: 12px 16px; background: var(--bg-surface-2); font-size: 12px; font-weight: 700; color: var(--accent-primary); border-bottom: 1px solid var(--border-default); }
.table-row { display: grid; grid-template-columns: 2fr repeat(6, 1fr) 100px; padding: 14px 16px; border-bottom: 1px solid var(--border-muted); align-items: center; }
.table-row:last-child { border-bottom: none; }
.col-name { min-width: 0; }
.col-num { text-align: center; font-size: 14px; color: var(--text-primary); }
.col-action { text-align: center; }
.project-name { font-weight: 700; color: var(--text-primary); font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.project-meta { color: var(--text-muted); font-size: 11px; margin-top: 2px; }
.coverage-badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
/* 覆盖率徽章是语义状态色,跨主题保持识别度,不走 token */
.coverage-badge.high { background: #e8f5e9; color: #2e7d32; }
.coverage-badge.medium { background: #fff3e0; color: #e65100; }
.coverage-badge.low { background: #ffebee; color: #c62828; }
.empty-state { padding: 24px; text-align: center; color: var(--text-muted); }

/* Gap #9: filter toolbar */
.filter-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 12px;
}
.filter-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-primary);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.filter-select,
.filter-input {
  border: 1px solid var(--input-border);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--input-bg);
  outline: none;
  font-family: inherit;
}
.filter-select:focus,
.filter-input:focus { border-color: var(--input-border-focus); }
.filter-input { flex: 1; min-width: 200px; }
.filter-summary {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: auto;
}

/* Status pill in the meta row of each project — 状态色跨主题保持识别度 */
.status-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  margin-right: 6px;
}
.status-pill.status-completed { background: #e8f5e9; color: #2e7d32; }
.status-pill.status-failed { background: #ffebee; color: #c62828; }
.status-pill.status-building { background: #e3f2fd; color: #1565c0; }
.status-pill.status-cancelled { background: #f3e8ff; color: #6b21a8; }
.status-pill.status-other,
.status-pill.status-unknown { background: #eeeeee; color: #616161; }
.project-id { color: var(--text-muted); font-size: 11px; }

.nav-row { margin-top: 24px; display: flex; gap: 12px; }
.btn-primary { background: var(--accent-primary); color: var(--text-on-accent); border: none; border-radius: 12px; padding: 10px 18px; font-weight: 600; cursor: pointer; font-size: 14px; text-decoration: none; }
.btn-primary:hover { background: var(--accent-primary-hover); }
.btn-small { border: 1px solid var(--border-default); background: var(--bg-elevated); border-radius: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; text-decoration: none; color: var(--accent-primary); }
.btn-small:hover { background: var(--bg-muted); }
@media (max-width: 960px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } .table-header, .table-row { grid-template-columns: 2fr repeat(3, 1fr) 80px; } .col-num:nth-child(n+5) { display: none; } }
</style>
