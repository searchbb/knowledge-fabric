<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <div class="concept-wrap">
      <div v-if="loading" class="state-card">正在加载概念详情...</div>
      <div v-else-if="loadError" class="state-card error-card">{{ loadError }}</div>

      <template v-else-if="entry">
        <!-- Header -->
        <header class="concept-header">
          <div class="section-badge">CANONICAL CONCEPT</div>
          <div class="concept-title-row">
            <h1 class="concept-title">{{ entry.canonical_name }}</h1>
            <span class="concept-type-chip">{{ entry.concept_type }}</span>
          </div>
          <p v-if="entry.description" class="concept-desc">{{ entry.description }}</p>
          <p v-else class="concept-desc-empty">暂无描述</p>

          <div v-if="entry.aliases?.length" class="alias-row">
            <span class="alias-label">别名</span>
            <span v-for="a in entry.aliases" :key="a" class="alias-chip">{{ a }}</span>
          </div>
        </header>

        <!-- Summary counters -->
        <div class="summary-grid">
          <article class="summary-card">
            <div class="card-title">项目链接</div>
            <div class="metric-value">{{ entry.source_links?.length || 0 }}</div>
          </article>
          <article class="summary-card">
            <div class="card-title">跨文关系</div>
            <div class="metric-value">{{ activeRelations.length }}</div>
          </article>
          <article class="summary-card">
            <div class="card-title">待审</div>
            <div class="metric-value">{{ unreviewedCount }}</div>
          </article>
        </div>

        <!-- Section: project links -->
        <section class="section">
          <div class="section-head">
            <h2 class="section-title">项目链接</h2>
            <span class="section-counter">{{ entry.source_links?.length || 0 }}</span>
          </div>
          <div v-if="entry.source_links?.length" class="link-list">
            <div v-for="link in entry.source_links" :key="link.project_id + link.concept_key" class="link-row">
              <div class="link-main">
                <span class="link-project">{{ link.project_name || link.project_id }}</span>
                <span class="link-arrow">→</span>
                <span class="link-concept">{{ entry.concept_type }}:{{ link.concept_key }}</span>
              </div>
              <div class="link-actions">
                <a
                  class="btn-sm"
                  :href="articleHref(link)"
                  target="_blank"
                  rel="noopener"
                  title="在新页面打开文章图谱并聚焦该节点"
                >打开来源文章 ↗</a>
                <button class="btn-sm btn-danger" @click="handleUnlink(link)">解绑</button>
              </div>
            </div>
          </div>
          <div v-else class="empty-note">尚未关联任何项目概念。</div>
        </section>

        <!-- Section: cross-article relations -->
        <section class="section">
          <div class="section-head">
            <h2 class="section-title">跨文关系</h2>
            <span class="section-counter">{{ filteredRelations.length }}</span>
          </div>

          <!-- Filter bar -->
          <div class="xrel-filters">
            <div class="filter-group">
              <button
                v-for="s in statusOpts"
                :key="s.value"
                class="filter-chip"
                :class="{ active: filter.status === s.value }"
                @click="filter.status = s.value"
              >{{ s.label }}</button>
            </div>

            <div class="filter-group">
              <select v-model="filter.type" class="filter-select">
                <option value="all">全部类型</option>
                <option v-for="t in typeOpts" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
              <select v-model="filter.sort" class="filter-select">
                <option value="confidence_desc">置信度最高</option>
                <option value="created_desc">最近发现</option>
              </select>
            </div>
          </div>

          <div v-if="relationsLoading" class="empty-note">加载中...</div>
          <div v-else-if="!filteredRelations.length" class="empty-note">
            {{ allRelations.length ? '当前筛选下无匹配关系' : '暂无跨文关系。可在"跨文关系"列表页手动发现。' }}
          </div>
          <div v-else class="xrel-list">
            <CrossRelationCard
              v-for="rel in filteredRelations"
              :key="rel.relation_id"
              :relation="rel"
              :conceptMap="conceptMap"
              :currentEntryId="entryId"
              @navigate="navigateToConcept"
              @review="handleReview"
              @delete="handleDelete"
            />
          </div>
        </section>

        <!-- Actions -->
        <div class="concept-actions">
          <button class="btn-sm" @click="openInRegistry">在注册表中打开</button>
          <button class="btn-sm btn-danger" @click="handleDeleteEntry">删除条目</button>
        </div>
      </template>

      <div v-else class="state-card">未找到条目 {{ entryId }}</div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import CrossRelationCard from '../../components/CrossRelationCard.vue'
// Reads flip live/demo via dataClient; writes stay on the live API
// (the axios interceptor blocks mutations in demo mode).
import {
  getRegistryConcept,
  listCrossRelations,
  listRegistryConcepts,
} from '../../data/dataClient'
import {
  unlinkProjectConcept,
  updateCrossRelation,
  deleteCrossRelation,
  deleteRegistryConcept,
} from '../../services/api/registryApi'
import { appMode } from '../../runtime/appMode'

const route = useRoute()
const router = useRouter()

const entry = ref(null)
const loading = ref(false)
const loadError = ref('')

const allRelations = ref([])
const relationsLoading = ref(false)
const entryIndex = ref({}) // entry_id -> entry, for peer concept name resolution

const filter = reactive({
  status: 'all',
  type: 'all',
  sort: 'confidence_desc',
})

const statusOpts = [
  { value: 'all', label: '全部' },
  { value: 'accepted', label: '已接受' },
  { value: 'unreviewed', label: '待审' },
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

const entryId = computed(() => route.params.entryId || '')

const crumbs = computed(() => {
  const tail = entry.value?.canonical_name || entryId.value || '概念详情'
  return [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '概念注册表', to: '/workspace/registry' },
    { label: tail },
  ]
})

const activeRelations = computed(() =>
  allRelations.value.filter((r) => r.review_status === 'accepted' || r.review_status === 'unreviewed')
)
const unreviewedCount = computed(() =>
  allRelations.value.filter((r) => r.review_status === 'unreviewed').length
)

const filteredRelations = computed(() => {
  let list = [...allRelations.value]
  if (filter.status !== 'all') list = list.filter((r) => r.review_status === filter.status)
  if (filter.type !== 'all') list = list.filter((r) => r.relation_type === filter.type)
  if (filter.sort === 'confidence_desc') {
    list.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
  } else if (filter.sort === 'created_desc') {
    list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  }
  return list
})

// Build a concept map for CrossRelationCard (entry_id -> {canonical_name, concept_type}).
// Pre-loaded from the global registry so peer concepts resolve to real names instead of
// raw IDs. Current entry + any relation-embedded peer info layered on top as a safety net.
const conceptMap = computed(() => {
  const map = { ...entryIndex.value }
  if (entry.value) map[entry.value.entry_id] = entry.value
  for (const rel of allRelations.value) {
    if (rel.source_entry && !map[rel.source_entry.entry_id]) {
      map[rel.source_entry.entry_id] = rel.source_entry
    }
    if (rel.target_entry && !map[rel.target_entry.entry_id]) {
      map[rel.target_entry.entry_id] = rel.target_entry
    }
  }
  return map
})

async function loadEntryIndex() {
  try {
    const res = await listRegistryConcepts()
    const map = {}
    for (const e of res.data?.entries || []) map[e.entry_id] = e
    entryIndex.value = map
  } catch (_e) { /* non-critical for page render */ }
}

async function loadEntry() {
  if (!entryId.value) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await getRegistryConcept(entryId.value)
    entry.value = res.data || null
  } catch (e) {
    // Clear stale entry so live↔demo switches don't leave the previous
    // concept's data visible alongside the new error.
    entry.value = null
    loadError.value = e.message || '加载条目失败'
  } finally {
    loading.value = false
  }
}

async function loadRelations() {
  if (!entryId.value) return
  relationsLoading.value = true
  try {
    const res = await listCrossRelations({ entry_id: entryId.value })
    // Backend returns data as a flat array under `data`, not `data.relations`.
    allRelations.value = Array.isArray(res.data) ? res.data : (res.data?.relations || [])
  } catch (_e) {
    allRelations.value = []
  } finally {
    relationsLoading.value = false
  }
}

function articleHref(link) {
  return `/process/${link.project_id}?mode=graph&view=reading&focusNode=${encodeURIComponent(link.concept_key)}&from=registry`
}

async function handleUnlink(link) {
  if (!confirm(`确定解绑项目 ${link.project_name || link.project_id} 的 ${link.concept_key}？`)) return
  try {
    await unlinkProjectConcept(entryId.value, {
      project_id: link.project_id,
      concept_key: link.concept_key,
    })
    await loadEntry()
  } catch (e) {
    alert('解绑失败: ' + (e.message || ''))
  }
}

async function handleReview(relationId, reviewStatus) {
  try {
    await updateCrossRelation(relationId, { review_status: reviewStatus })
    await loadRelations()
  } catch (e) {
    alert('审阅失败: ' + (e.message || ''))
  }
}

async function handleDelete(relationId) {
  if (!confirm('确定删除此跨文关系？')) return
  try {
    await deleteCrossRelation(relationId)
    await loadRelations()
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
  }
}

async function handleDeleteEntry() {
  if (!entry.value) return
  if (!confirm(`确定删除条目 "${entry.value.canonical_name}"？相关链接会一并丢失。`)) return
  try {
    await deleteRegistryConcept(entryId.value)
    router.push('/workspace/registry')
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
  }
}

function navigateToConcept(targetEntryId) {
  if (!targetEntryId || targetEntryId === entryId.value) return
  router.push(`/workspace/entry/${targetEntryId}`)
}

function openInRegistry() {
  router.push(`/workspace/registry?tab=concepts&select=${entryId.value}`)
}

onMounted(async () => {
  await Promise.all([loadEntry(), loadRelations(), loadEntryIndex()])
})

watch(entryId, async (next) => {
  if (!next) return
  await Promise.all([loadEntry(), loadRelations()])
})

// Reload entry + relations when live/demo flips.
watch(appMode, async () => {
  await Promise.all([loadEntry(), loadRelations(), loadEntryIndex()])
})
</script>

<style scoped>
.concept-wrap {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

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
.topbar-btn:hover { background: #f0f4ff; border-color: #a9bbd9; }

/* Header */
.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #4a6fa5;
  font-weight: 700;
}
.concept-title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin: 6px 0;
}
.concept-title { margin: 0; font-size: 28px; color: #181818; }
.concept-type-chip {
  font-size: 12px;
  color: #4a6fa5;
  background: #f0f4ff;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid #d4dce8;
}
.concept-desc {
  font-size: 14px;
  line-height: 1.65;
  color: #3f4552;
  margin: 6px 0 10px;
}
.concept-desc-empty {
  font-size: 13px;
  color: #a5a9b3;
  font-style: italic;
  margin: 6px 0 10px;
}

.alias-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.alias-label {
  font-size: 12px;
  font-weight: 700;
  color: #6d6256;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.alias-chip {
  font-size: 12px;
  color: #5a6573;
  background: #f5f8ff;
  border: 1px solid #d4dce8;
  padding: 3px 9px;
  border-radius: 6px;
}

/* Summary */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.summary-card {
  border: 1px solid #d4dce8;
  border-radius: 14px;
  padding: 14px 16px;
  background: #fff;
}
.card-title {
  font-size: 12px;
  font-weight: 700;
  color: #6d6256;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #181818;
}

/* Sections */
.section {
  border: 1px solid #d4dce8;
  border-radius: 16px;
  padding: 20px;
  background: #fff;
}
.section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #181818;
}
.section-counter {
  font-size: 12px;
  color: #9a8d7c;
  background: #f3f4f7;
  padding: 2px 8px;
  border-radius: 10px;
}

.empty-note {
  color: #9a8d7c;
  font-size: 13px;
  padding: 12px 4px;
}
.error-card {
  border-color: #e2b0a8;
  background: #fff8f6;
  color: #c62828;
}
.state-card {
  border: 1px solid #d4dce8;
  border-radius: 14px;
  padding: 14px 18px;
}

/* Links */
.link-list { display: flex; flex-direction: column; gap: 10px; }
.link-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  background: #fafbfc;
}
.link-main { display: flex; align-items: center; gap: 8px; font-size: 13px; min-width: 0; }
.link-project { font-weight: 600; color: #1d1d1d; }
.link-arrow { color: #9a8d7c; }
.link-concept {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #5a6573;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link-actions { display: flex; gap: 6px; flex-shrink: 0; }

.btn-sm {
  display: inline-flex;
  align-items: center;
  padding: 5px 11px;
  border-radius: 8px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #4a6fa5;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
}
.btn-sm:hover { background: #f0f4ff; border-color: #a9bbd9; }
.btn-danger { color: #c62828; border-color: #ef9a9a; }
.btn-danger:hover { background: #ffebee; }

/* Filters */
.xrel-filters {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef1f5;
}
.filter-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.filter-chip {
  padding: 4px 10px;
  border: 1px solid #d4dce8;
  border-radius: 999px;
  background: #fff;
  color: #6d6256;
  font-size: 12px;
  cursor: pointer;
}
.filter-chip.active {
  background: #4a6fa5;
  color: #fff;
  border-color: #4a6fa5;
}
.filter-select {
  padding: 5px 10px;
  border: 1px solid #d4dce8;
  border-radius: 8px;
  background: #fff;
  font-size: 12px;
}

.xrel-list { display: flex; flex-direction: column; gap: 10px; }

.concept-actions {
  display: flex;
  gap: 10px;
  padding-top: 8px;
}
</style>
