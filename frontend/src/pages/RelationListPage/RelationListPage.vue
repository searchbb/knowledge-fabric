<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <!-- "发现新关系" 全局按钮已移除 (2026-04-16, GPT consult f09fb61ce5e8a061):
           跨文关系发现现在内嵌在自动 pipeline 的 discover phase；想对单个主题
           重跑发现，请去主题详情页用那里的 "发现新关系" 按钮。原全局按钮的
           本意是 "对所有主题全量重发现"，成本高且语义模糊（且之前还带个空
           theme_id 的 400 bug），直接拿掉。 -->
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <div class="relation-wrap">
      <header class="page-header">
        <div class="section-badge">CROSS-ARTICLE RELATIONS</div>
        <h1 class="page-title">跨文关系</h1>
        <p class="page-subtitle">LLM 从全局概念池发现的跨文章关联。可筛选、审阅、追溯证据。</p>
      </header>

      <!-- Filter bar — hidden when the load failed, otherwise the chip
           counts read as "all categories empty" rather than "we never
           reached the backend". Keep the bar visible for normal empty
           and loaded states. -->
      <div v-if="!loadError" class="filter-bar">
        <div class="filter-group">
          <button
            v-for="s in statusOpts"
            :key="s.value"
            class="filter-chip"
            :class="{ active: filter.status === s.value }"
            @click="filter.status = s.value"
          >{{ s.label }} <span class="chip-count">{{ statusCounts[s.value] || 0 }}</span></button>
        </div>

        <div class="filter-group">
          <select v-model="filter.type" class="filter-select">
            <option value="all">全部类型</option>
            <option v-for="t in typeOpts" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
          <select v-model="filter.minConfidence" class="filter-select">
            <option :value="0">置信度不限</option>
            <option :value="0.6">≥ 60%</option>
            <option :value="0.8">≥ 80%</option>
            <option :value="0.9">≥ 90%</option>
          </select>
          <select v-model="filter.sort" class="filter-select">
            <option value="confidence_desc">置信度最高</option>
            <option value="created_desc">最近发现</option>
          </select>
        </div>
      </div>

      <!-- List -->
      <div v-if="loading" class="state-card">加载中...</div>
      <div v-else-if="loadError" class="state-card error-card">
        <div class="error-title">加载失败</div>
        <div>{{ loadError }}</div>
      </div>
      <div v-else-if="!filteredRelations.length" class="state-card">
        <template v-if="!allRelations.length">暂无跨文关系。新文章入库时会自动发现关系；如需对单个主题重跑，请到主题详情页。</template>
        <template v-else>当前筛选下无匹配关系。</template>
      </div>
      <div v-else class="relation-list">
        <router-link
          v-for="rel in filteredRelations"
          :key="rel.relation_id"
          :to="`/workspace/relations/${rel.relation_id}`"
          class="relation-row"
        >
          <div class="row-main">
            <div class="row-concepts">
              <span class="concept-name">{{ getName(rel, 'source') }}</span>
              <span class="arrow">{{ rel.directionality === 'bidirectional' ? '↔' : '→' }}</span>
              <span class="concept-name">{{ getName(rel, 'target') }}</span>
            </div>
            <span class="type-badge" :class="rel.relation_type">{{ typeLabel(rel.relation_type) }}</span>
          </div>
          <p class="row-reason">{{ rel.reason }}</p>
          <div class="row-meta">
            <span class="conf">{{ Math.round((rel.confidence || 0) * 100) }}%</span>
            <span class="source-tag">{{ rel.source }}</span>
            <span class="review-tag" :class="rel.review_status">{{ reviewLabel(rel.review_status) }}</span>
            <span class="date">{{ formatDate(rel.created_at) }}</span>
          </div>
        </router-link>
      </div>

      <div v-if="filteredRelations.length" class="list-footer">
        {{ filteredRelations.length }} / {{ allRelations.length }} 条
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
// Reads flip live/demo via dataClient.
import { listCrossRelations, listRegistryConcepts } from '../../data/dataClient'
import { appMode } from '../../runtime/appMode'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '跨文关系' },
]

const allRelations = ref([])
const conceptMap = ref({}) // entry_id -> { canonical_name, concept_type }
const loading = ref(false)
const loadError = ref('')

const filter = reactive({
  status: 'all',
  type: 'all',
  minConfidence: 0,
  sort: 'confidence_desc',
})

const statusOpts = [
  { value: 'all', label: '全部' },
  { value: 'unreviewed', label: '待审' },
  { value: 'accepted', label: '已接受' },
  { value: 'rejected', label: '已驳回' },
]

const typeOpts = [
  { value: 'design_inspiration', label: '设计启示' },
  { value: 'technical_foundation', label: '技术支撑' },
  { value: 'problem_solution', label: '问题-方案' },
  { value: 'contrast_reference', label: '对比参照' },
  { value: 'capability_constraint', label: '能力约束' },
  { value: 'pattern_reuse', label: '模式借鉴' },
]

const typeLabelMap = Object.fromEntries(typeOpts.map((t) => [t.value, t.label]))

function typeLabel(key) { return typeLabelMap[key] || key }
function reviewLabel(status) {
  if (status === 'accepted') return '已接受'
  if (status === 'rejected') return '已驳回'
  return '待审'
}
function formatDate(iso) {
  if (!iso) return ''
  return iso.slice(0, 10)
}

function getName(rel, side) {
  const obj = rel[`${side}_entry`]
  if (obj?.canonical_name) return obj.canonical_name
  // Second: consult the concept map preloaded from the registry
  const entryId = rel[`${side}_entry_id`]
  if (entryId && conceptMap.value[entryId]?.canonical_name) {
    return conceptMap.value[entryId].canonical_name
  }
  // Fallback: embedded source_name / target_name or raw ID
  return rel[`${side}_name`] || entryId || '(未知概念)'
}

const statusCounts = computed(() => {
  const counts = { all: allRelations.value.length, unreviewed: 0, accepted: 0, rejected: 0 }
  for (const r of allRelations.value) {
    const s = r.review_status || 'unreviewed'
    if (counts[s] !== undefined) counts[s] += 1
  }
  return counts
})

const filteredRelations = computed(() => {
  let list = [...allRelations.value]
  if (filter.status !== 'all') list = list.filter((r) => (r.review_status || 'unreviewed') === filter.status)
  if (filter.type !== 'all') list = list.filter((r) => r.relation_type === filter.type)
  if (filter.minConfidence > 0) list = list.filter((r) => (r.confidence || 0) >= filter.minConfidence)
  if (filter.sort === 'confidence_desc') {
    list.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
  } else if (filter.sort === 'created_desc') {
    list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  }
  return list
})

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [relRes, conceptRes] = await Promise.all([
      listCrossRelations({}),
      listRegistryConcepts(),
    ])
    // Backend returns cross-relations as flat array under `data`.
    allRelations.value = Array.isArray(relRes.data) ? relRes.data : (relRes.data?.relations || [])
    // Build concept_id -> concept map for name lookup
    const map = {}
    const entries = conceptRes.data?.entries || []
    for (const e of entries) {
      map[e.entry_id] = e
    }
    conceptMap.value = map
  } catch (e) {
    loadError.value = e.message || '加载跨文关系失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
// Reload when live/demo flips.
watch(appMode, loadAll)
</script>

<style scoped>
.relation-wrap { max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }

.topbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #4a6fa5;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover:not(:disabled) { background: #f0f4ff; border-color: #a9bbd9; }
.topbar-btn:disabled { opacity: 0.6; cursor: wait; }

.page-header { }
.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #4a6fa5;
  font-weight: 700;
}
.page-title { margin: 6px 0 4px; font-size: 26px; color: #181818; }
.page-subtitle { color: #5a6573; font-size: 14px; margin: 0; }

.filter-bar {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 14px;
  padding: 12px;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  background: #fff;
}
.filter-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.filter-chip {
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #6d6256;
  font-size: 12px;
  cursor: pointer;
}
.filter-chip.active { background: #4a6fa5; color: #fff; border-color: #4a6fa5; }
.chip-count {
  margin-left: 4px;
  font-size: 10px;
  opacity: 0.75;
}
.filter-select {
  padding: 5px 10px;
  border: 1px solid #d4dce8;
  border-radius: 8px;
  background: #fff;
  font-size: 12px;
  color: #3f4552;
}

.state-card {
  border: 1px solid #d4dce8;
  border-radius: 12px;
  padding: 18px 20px;
  background: #fff;
  color: #6d6256;
  font-size: 13px;
}
.error-card { border-color: #e2b0a8; background: #fff8f6; color: #c62828; }
.error-title { font-weight: 700; margin-bottom: 4px; }

.relation-list { display: flex; flex-direction: column; gap: 10px; }
.relation-row {
  display: block;
  padding: 14px 16px;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  background: #fff;
  text-decoration: none;
  color: inherit;
  transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
}
.relation-row:hover {
  border-color: #a9bbd9;
  box-shadow: 0 6px 14px rgba(74, 111, 165, 0.08);
  transform: translateX(2px);
}

.row-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.row-concepts {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}
.concept-name {
  font-weight: 700;
  color: #181818;
  font-size: 14px;
}
.arrow {
  color: #9a8d7c;
  font-size: 12px;
}
.type-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  background: #f0f4ff;
  color: #4a6fa5;
  border: 1px solid #d4dce8;
  font-weight: 500;
  white-space: nowrap;
}

.row-reason {
  margin: 0 0 8px;
  font-size: 13px;
  color: #5a6573;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.row-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #9a8d7c;
}
.conf { color: #4a6fa5; font-weight: 600; }
.review-tag.accepted { color: #2e7d32; }
.review-tag.rejected { color: #c62828; }
.source-tag {
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.list-footer {
  text-align: center;
  font-size: 12px;
  color: #9a8d7c;
  padding: 8px 0;
}
</style>
