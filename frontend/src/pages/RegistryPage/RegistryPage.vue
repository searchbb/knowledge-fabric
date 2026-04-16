<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <button class="topbar-btn" @click="handleExport" title="下载全部注册表 JSON">
        <span class="icon">⬇</span><span class="label">导出</span>
      </button>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <main class="registry-main">
      <!-- Tab bar (horizontal, replacing sidebar tabs) -->
      <nav class="registry-tabs" aria-label="注册表子视图">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="registry-tab"
          :class="{ active: activeTab === tab.key }"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <section class="phase2-page">
        <div class="section-badge">{{ activeTabMeta.badge }}</div>
        <h2 class="section-title">{{ activeTabMeta.title }}</h2>
        <p class="section-copy">{{ activeTabMeta.subtitle }}</p>

        <!-- Theme / Evolution / Review tabs -->
        <ThemeTab v-if="activeTab === 'themes'" />
        <EvolutionTab v-else-if="activeTab === 'evolution'" />
        <ReviewTab v-else-if="activeTab === 'review'" />

        <!-- Concepts tab (default, existing content below) -->
        <template v-else>

        <!-- Error: show FIRST when the backend failed. The stats row and
             toolbar below display "0" / active buttons, so rendering them
             above the error card reads as "empty registry" instead of
             "we never reached the backend". Surface the diagnosis before
             the shell so the user isn't misled. -->
        <div v-if="registryStore.error" class="state-card error-card">
          <div class="card-title">加载失败</div>
          <div class="metric-line">{{ registryStore.error }}</div>
        </div>

        <!-- Loading -->
        <div v-else-if="registryStore.loading" class="state-card">
          <div class="card-title">正在加载注册表</div>
        </div>

        <!-- Stats row (only when not erroring/loading) -->
        <div v-else class="summary-grid">
          <article class="card">
            <div class="card-title">注册表条目</div>
            <div class="metric-value">{{ registryStore.total }}</div>
          </article>
          <article class="card">
            <div class="card-title">项目链接数</div>
            <div class="metric-value">{{ totalLinks }}</div>
          </article>
          <article class="card">
            <div class="card-title">覆盖类型</div>
            <div class="metric-value">{{ uniqueTypes }}</div>
          </article>
        </div>

        <!-- Toolbar + main layout — same gating as stats row, but
             using v-if (not v-else) since they are siblings of the
             error/loading/stats triplet above, not part of its v-if chain. -->
        <template v-if="!registryStore.error && !registryStore.loading">
        <!-- Search bar + create button -->
        <div class="toolbar">
          <input
            class="search-input"
            type="text"
            placeholder="搜索概念名 / 别名..."
            v-model="searchQuery"
            @input="handleSearch"
          />
          <button class="btn-small" @click="openSuggestPanel">项目推荐</button>
          <button class="btn-primary" @click="showCreateForm = true">新建条目</button>
        </div>

        <!-- Main layout -->
        <div class="registry-layout">
          <!-- Left: entry list -->
          <article class="card queue-card">
            <div class="card-header">
              <div class="card-title">
                {{ searchQuery ? '搜索结果' : '全部条目' }}
              </div>
              <div class="pill">{{ displayEntries.length }}</div>
            </div>

            <div v-if="!displayEntries.length" class="empty-state">
              {{ searchQuery ? '没有匹配的条目' : '注册表为空，使用"新建条目"或"项目推荐"来添加' }}
            </div>

            <div v-else class="candidate-list">
              <button
                v-for="entry in displayEntries"
                :key="entry.entry_id"
                type="button"
                class="candidate-button"
                :class="{ active: entry.entry_id === registryStore.selectedEntryId }"
                @click="handleSelectEntry(entry.entry_id)"
              >
                <div class="candidate-topline">
                  <span class="candidate-name">{{ entry.canonical_name }}</span>
                  <span class="candidate-status">{{ entry.source_links?.length || 0 }} 链接</span>
                  <span v-if="registryStore.crossRelationCounts[entry.entry_id]" class="xrel-badge">
                    x-rel {{ registryStore.crossRelationCounts[entry.entry_id] }}
                  </span>
                </div>
                <div class="candidate-meta">
                  {{ entry.concept_type }}
                  <template v-if="entry.aliases?.length"> · {{ entry.aliases.length }} 别名</template>
                </div>
              </button>
            </div>
          </article>

          <!-- Middle: detail panel -->
          <article class="card detail-card">
            <template v-if="selectedEntry">
              <div class="card-header">
                <div>
                  <div class="detail-kicker">Canonical Entry</div>
                  <h3 class="detail-title">{{ selectedEntry.canonical_name }}</h3>
                </div>
                <div class="detail-badges">
                  <span class="chip">{{ selectedEntry.concept_type }}</span>
                  <router-link
                    :to="`/workspace/entry/${selectedEntry.entry_id}`"
                    class="open-detail-btn"
                    title="在独立页查看完整详情（可分享链接）"
                  >独立页打开 →</router-link>
                </div>
              </div>

              <div v-if="selectedEntry.description" class="detail-sections">
                <section class="detail-section">
                  <div class="subsection-title">描述</div>
                  <p class="section-copy mini-copy">{{ selectedEntry.description }}</p>
                </section>
              </div>

              <div class="detail-sections">
                <section class="detail-section">
                  <div class="subsection-title">别名</div>
                  <div class="chip-wrap" v-if="selectedEntry.aliases?.length">
                    <span v-for="alias in selectedEntry.aliases" :key="alias" class="chip soft">{{ alias }}</span>
                  </div>
                  <div v-else class="empty-note">暂无别名</div>
                </section>

                <section class="detail-section">
                  <div class="subsection-title">项目链接 ({{ selectedEntry.source_links?.length || 0 }})</div>
                  <div v-if="selectedEntry.source_links?.length" class="link-list">
                    <div v-for="link in selectedEntry.source_links" :key="link.project_id + link.concept_key" class="link-item">
                      <a
                        class="link-project link-clickable"
                        :href="`/process/${link.project_id}?mode=graph&view=reading&focusNode=${encodeURIComponent(link.concept_key)}&from=registry`"
                        target="_blank"
                        :title="`新窗口打开阅读视图，定位到 ${link.concept_key}`"
                      >{{ link.project_name || link.project_id }} ↗</a>
                      <div class="link-concept">{{ link.concept_key }}</div>
                      <button class="btn-small btn-danger" @click="handleUnlink(link)">解绑</button>
                    </div>
                  </div>
                  <div v-else class="empty-note">尚未关联任何项目概念</div>
                </section>

                <!-- Block 3: Cross-article relations (L3) -->
                <section class="detail-section">
                  <div class="subsection-title">
                    跨文章关联
                    <span v-if="registryStore.crossRelations.length" class="pill small">{{ filteredCrossRelations.length }}</span>
                  </div>
                  <div v-if="registryStore.crossRelationsLoading" class="empty-note">加载中...</div>
                  <div v-else-if="filteredCrossRelations.length" class="xrel-list">
                    <CrossRelationCard
                      v-for="rel in filteredCrossRelations"
                      :key="rel.relation_id"
                      :relation="rel"
                      :conceptMap="conceptMap"
                      :currentEntryId="registryStore.selectedEntryId"
                      @navigate="handleNavigateConcept"
                      @review="handleReviewRelation"
                      @delete="handleDeleteRelation"
                    />
                  </div>
                  <div v-else class="empty-note">暂无跨文章关联</div>
                </section>
              </div>

              <div class="action-row">
                <button class="btn-small" @click="startEdit">编辑</button>
                <button class="btn-small btn-danger" @click="handleDelete">删除</button>
              </div>
            </template>

            <div v-else class="empty-state">
              选择左侧条目查看详情，或使用搜索查找特定概念
            </div>
          </article>

          <!-- Right: action panel -->
          <article class="card action-card">
            <!-- Create form -->
            <template v-if="showCreateForm">
              <div class="card-title">新建条目</div>
              <div class="form-group">
                <label>名称</label>
                <input v-model="formData.canonical_name" class="form-input" placeholder="Canonical 概念名" />
              </div>
              <div class="form-group">
                <label>类型</label>
                <input v-model="formData.concept_type" class="form-input" placeholder="Concept" />
              </div>
              <div class="form-group">
                <label>别名 (逗号分隔)</label>
                <input v-model="formData.aliasesRaw" class="form-input" placeholder="AI, 人工智能" />
              </div>
              <div class="form-group">
                <label>描述</label>
                <textarea v-model="formData.description" class="form-input" rows="3" placeholder="可选描述" />
              </div>
              <div class="action-row">
                <button class="btn-primary" @click="handleCreate" :disabled="registryStore.saving">
                  {{ registryStore.saving ? '保存中...' : '创建' }}
                </button>
                <button class="btn-small" @click="resetForm">取消</button>
              </div>
            </template>

            <!-- Edit form -->
            <template v-else-if="editMode && selectedEntry">
              <div class="card-title">编辑条目</div>
              <div class="form-group">
                <label>名称</label>
                <input v-model="editData.canonical_name" class="form-input" />
              </div>
              <div class="form-group">
                <label>类型</label>
                <input v-model="editData.concept_type" class="form-input" />
              </div>
              <div class="form-group">
                <label>别名 (逗号分隔)</label>
                <input v-model="editData.aliasesRaw" class="form-input" />
              </div>
              <div class="form-group">
                <label>描述</label>
                <textarea v-model="editData.description" class="form-input" rows="3" />
              </div>
              <div class="action-row">
                <button class="btn-primary" @click="handleEdit" :disabled="registryStore.saving">
                  {{ registryStore.saving ? '保存中...' : '保存' }}
                </button>
                <button class="btn-small" @click="editMode = false">取消</button>
              </div>
            </template>

            <!-- Suggest panel -->
            <template v-else-if="currentPanel === 'suggest'">
              <div class="card-header">
                <div class="card-title">从项目推荐</div>
                <button class="btn-small" @click="closeSuggestPanel">关闭</button>
              </div>
              <p class="section-copy mini-copy">选择一个项目，将其已确认概念推荐到全局注册表。</p>
              <div class="form-group">
                <label>项目 ID</label>
                <input v-model="suggestProjectId" class="form-input" placeholder="proj_xxxx" />
              </div>
              <button
                class="btn-primary"
                @click="handleSuggest"
                :disabled="registryStore.suggestLoading || !suggestProjectId"
              >
                {{ registryStore.suggestLoading ? '分析中...' : '生成推荐' }}
              </button>

              <template v-if="registryStore.suggestResult">
                <div class="suggest-summary">
                  <div class="metric-line">项目：{{ registryStore.suggestResult.project_name }}</div>
                  <div class="metric-line">已确认概念：{{ registryStore.suggestResult.total_accepted }}</div>
                  <div class="metric-line">新候选：{{ registryStore.suggestResult.new_candidates?.length || 0 }}</div>
                  <div class="metric-line">已匹配：{{ registryStore.suggestResult.existing_matches?.length || 0 }}</div>
                  <div class="metric-line">跨类型提示：{{ registryStore.suggestResult.cross_type_matches?.length || 0 }}</div>
                  <div class="metric-line">已链接：{{ registryStore.suggestResult.already_linked?.length || 0 }}</div>
                </div>

                <div v-if="registryStore.suggestResult.new_candidates?.length" class="suggest-section">
                  <div class="subsection-title">可注册 ({{ registryStore.suggestResult.new_candidates.length }})</div>
                  <div v-for="c in registryStore.suggestResult.new_candidates" :key="c.concept_key" class="suggest-item">
                    <span class="candidate-name">{{ c.display_name }}</span>
                    <span class="candidate-meta">{{ c.concept_type }}</span>
                    <button class="btn-small" @click="quickCreate(c)">注册</button>
                  </div>
                </div>

                <div v-if="registryStore.suggestResult.existing_matches?.length" class="suggest-section">
                  <div class="subsection-title">可链接 ({{ registryStore.suggestResult.existing_matches.length }})</div>
                  <div v-for="c in registryStore.suggestResult.existing_matches" :key="c.concept_key" class="suggest-item">
                    <span class="candidate-name">{{ c.display_name }}</span>
                    <span class="candidate-meta">→ {{ c.matched_canonical_name }}</span>
                    <button class="btn-small" @click="quickLink(c)">链接</button>
                  </div>
                </div>

                <div v-if="registryStore.suggestResult.cross_type_matches?.length" class="suggest-section">
                  <div class="subsection-title">跨类型提示 ({{ registryStore.suggestResult.cross_type_matches.length }})</div>
                  <div v-for="c in registryStore.suggestResult.cross_type_matches" :key="c.concept_key" class="suggest-item">
                    <span class="candidate-name">{{ c.display_name }}</span>
                    <span class="candidate-meta">{{ c.concept_type }} → {{ c.matched_canonical_name }} [{{ c.matched_concept_type }}]</span>
                    <button class="btn-small" @click="quickLinkCrossType(c)">链接为别名</button>
                  </div>
                </div>
              </template>
            </template>

            <!-- Default: cross-relation filters + action info -->
            <template v-else>
              <!-- Cross-relation filter panel (when concept has relations) -->
              <template v-if="selectedEntry && registryStore.crossRelations.length">
                <div class="card-title">跨文章关联筛选</div>

                <!-- Summary bar -->
                <div class="xfilter-summary">
                  {{ filteredCrossRelations.length }} 条关系
                  <span v-if="xrelFilterState.reviewStatus !== 'all'" class="xfilter-active"> · 已筛选</span>
                </div>

                <!-- Status tabs -->
                <div class="xfilter-tabs">
                  <button v-for="s in xrelStatusOptions" :key="s.value"
                    class="xfilter-tab" :class="{ active: xrelFilterState.reviewStatus === s.value }"
                    @click="xrelFilterState.reviewStatus = s.value">
                    {{ s.label }}
                  </button>
                </div>

                <!-- Relation type chips -->
                <div class="xfilter-section">
                  <div class="xfilter-label">关系类型</div>
                  <div class="xfilter-chips">
                    <button v-for="t in xrelTypeOptions" :key="t.value"
                      class="xfilter-chip" :class="{ active: xrelFilterState.types.includes(t.value) }"
                      @click="toggleXrelType(t.value)">
                      {{ t.label }}
                    </button>
                  </div>
                </div>

                <!-- Confidence + Sort row -->
                <div class="xfilter-row">
                  <div class="xfilter-half">
                    <div class="xfilter-label">置信度</div>
                    <select v-model="xrelFilterState.minConfidence" class="form-input xfilter-select">
                      <option :value="0">全部</option>
                      <option :value="0.6">&ge;60%</option>
                      <option :value="0.8">&ge;80%</option>
                    </select>
                  </div>
                  <div class="xfilter-half">
                    <div class="xfilter-label">排序</div>
                    <select v-model="xrelFilterState.sort" class="form-input xfilter-select">
                      <option value="confidence_desc">置信度最高</option>
                      <option value="created_desc">最近发现</option>
                    </select>
                  </div>
                </div>

                <!-- Actions -->
                <div class="xfilter-actions">
                  <button class="btn-small" @click="resetXrelFilter">清空筛选</button>
                </div>

                <hr class="xfilter-divider" />
              </template>

              <div class="card-title">操作面板</div>
              <p class="section-copy mini-copy">
                选择左侧条目后可编辑、删除或管理项目链接。使用"项目推荐"批量导入概念。
              </p>
              <div v-if="registryStore.actionError" class="error-text">{{ registryStore.actionError }}</div>
            </template>
          </article>
        </div>
        </template><!-- /non-error, non-loading -->
        </template><!-- /concepts tab (default) -->
      </section>
    </main>
  </AppShell>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import ThemeTab from './tabs/ThemeTab.vue'
import EvolutionTab from './tabs/EvolutionTab.vue'
import ReviewTab from './tabs/ReviewTab.vue'
import CrossRelationCard from '../../components/CrossRelationCard.vue'
import {
  registryStore,
  loadEntries,
  selectEntry,
  addEntry,
  editEntry,
  removeEntry,
  unlinkConcept,
  searchEntries,
  loadSuggestions,
  linkConcept,
  loadCrossRelations,
  loadCrossRelationCounts,
  reviewCrossRelation,
  removeCrossRelation,
} from '../../stores/registryStore'
import { appMode } from '../../runtime/appMode'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'concepts', label: '概念' },
  { key: 'evolution', label: '演化日志' },
  { key: 'review', label: '审核队列' },
]

const tabMeta = {
  concepts: { badge: 'CONCEPT REGISTRY', title: '跨项目概念注册表', subtitle: '全局 canonical 概念的唯一真相源。各项目的已确认概念可以链接到这里，实现跨项目知识积累与对齐。' },
  evolution: { badge: 'EVOLUTION LOG', title: '演化日志', subtitle: '所有概念/主题的创建、更新、链接、审核等变更记录。' },
  review: { badge: 'REVIEW QUEUE', title: '审核队列', subtitle: '人工校验任务管理：认领、通过、重开、批量处理。' },
}

const activeTab = ref(route.query.tab || 'concepts')
const activeTabMeta = computed(() => tabMeta[activeTab.value] || tabMeta.concepts)

const selectedEntryName = computed(() => registryStore.selectedEntry?.canonical_name || '')

const crumbs = computed(() => {
  if (activeTab.value === 'evolution') {
    return [
      { label: '跨项目', to: '/workspace/registry' },
      { label: '演化日志' },
    ]
  }
  if (activeTab.value === 'review') {
    return [
      { label: '跨项目', to: '/workspace/registry' },
      { label: '审核队列' },
    ]
  }
  const base = [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '概念注册表', to: '/workspace/registry' },
  ]
  if (selectedEntryName.value) {
    return [...base, { label: selectedEntryName.value }]
  }
  return [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '概念注册表' },
  ]
})

function switchTab(key) {
  // "全局主题" 直接跳到新的 Hub-and-Spoke 主题页面
  if (key === 'themes') {
    router.push('/workspace/themes')
    return
  }
  activeTab.value = key
  router.replace({ query: { ...route.query, tab: key } })
}

// Gap #3 fix: react to URL changes made by OTHER components (e.g. the
// EvolutionTab clicking a concept_entry row which does router.replace to
// switch to tab=concepts + add ?select=canon_xxx). Without this watcher
// RegistryPage keeps its initial activeTab forever because Vue Router
// reuses the component instance on query-only changes.
watch(
  () => route.query.tab,
  (next) => {
    if (next && next !== activeTab.value) {
      activeTab.value = next
    }
  },
)

// Gap #3 fix: when a deep link carries ?select=canon_xxx, wait until the
// entries list is loaded, then select the target canonical so the middle
// detail panel populates. Runs on mount AND on any subsequent URL change.
watch(
  () => route.query.select,
  async (next) => {
    if (!next || typeof next !== 'string') return
    // Force the concept tab visible so the detail card actually renders.
    if (activeTab.value !== 'concepts') activeTab.value = 'concepts'
    // Wait for the store to have entries; if still empty, trigger a load.
    if (!registryStore.entries?.length) {
      try { await loadEntries() } catch (_err) { /* non-fatal */ }
    }
    selectEntry(next)
    loadCrossRelations(next)
    // Auto-scroll only the left entry list (not the whole page)
    nextTick(() => {
      setTimeout(() => {
        const activeBtn = document.querySelector('.candidate-button.active')
        if (!activeBtn) return
        const listContainer = activeBtn.closest('.candidate-list') || activeBtn.closest('.queue-card')
        if (listContainer) {
          const btnTop = activeBtn.offsetTop - listContainer.offsetTop
          listContainer.scrollTop = btnTop - listContainer.clientHeight / 2 + activeBtn.clientHeight / 2
        }
      }, 300)
    })
  },
  { immediate: true },
)

const currentPanel = ref('list')
const showCreateForm = ref(false)
const editMode = ref(false)
const searchQuery = ref('')
const suggestProjectId = ref('')

const formData = ref({
  canonical_name: '',
  concept_type: 'Concept',
  aliasesRaw: '',
  description: '',
})

const editData = ref({
  canonical_name: '',
  concept_type: '',
  aliasesRaw: '',
  description: '',
})

const lastProjectId = computed(() => route.query.from || '')

const selectedEntry = computed(() => registryStore.selectedEntry)

const totalLinks = computed(() =>
  registryStore.entries.reduce((sum, e) => sum + (e.source_links?.length || 0), 0)
)

const uniqueTypes = computed(() =>
  new Set(registryStore.entries.map((e) => e.concept_type)).size
)

const displayEntries = computed(() => {
  if (searchQuery.value && registryStore.searchResults.length) {
    return registryStore.searchResults
  }
  return registryStore.entries
})

// -- Cross-relation filter state (local, no API calls) --
const xrelFilterState = ref({
  reviewStatus: 'all',
  types: ['design_inspiration', 'technical_foundation', 'problem_solution', 'contrast_reference', 'capability_constraint', 'pattern_reuse'],
  minConfidence: 0,
  sort: 'confidence_desc',
})

const xrelStatusOptions = [
  { value: 'all', label: '全部' },
  { value: 'accepted', label: '已接受' },
  { value: 'unreviewed', label: '待审阅' },
  { value: 'rejected', label: '已驳回' },
]

const xrelTypeOptions = [
  { value: 'design_inspiration', label: '设计启示' },
  { value: 'technical_foundation', label: '技术支撑' },
  { value: 'problem_solution', label: '问题-方案' },
  { value: 'contrast_reference', label: '对比参照' },
  { value: 'capability_constraint', label: '能力约束' },
  { value: 'pattern_reuse', label: '模式借鉴' },
]

const filteredCrossRelations = computed(() => {
  let list = [...registryStore.crossRelations]
  const f = xrelFilterState.value
  // Status filter
  if (f.reviewStatus !== 'all') {
    list = list.filter(r => r.review_status === f.reviewStatus)
  }
  // Type filter
  if (f.types.length < 6) {
    list = list.filter(r => f.types.includes(r.relation_type))
  }
  // Confidence filter
  if (f.minConfidence > 0) {
    list = list.filter(r => (r.confidence || 0) >= f.minConfidence)
  }
  // Sort
  if (f.sort === 'confidence_desc') {
    list.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
  } else if (f.sort === 'created_desc') {
    list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  }
  return list
})

function toggleXrelType(typeValue) {
  const types = xrelFilterState.value.types
  const idx = types.indexOf(typeValue)
  if (idx >= 0) {
    if (types.length > 1) types.splice(idx, 1)  // don't allow empty
  } else {
    types.push(typeValue)
  }
}

function resetXrelFilter() {
  xrelFilterState.value = {
    reviewStatus: 'all',
    types: ['design_inspiration', 'technical_foundation', 'problem_solution', 'contrast_reference', 'capability_constraint', 'pattern_reuse'],
    minConfidence: 0,
    sort: 'confidence_desc',
  }
}

let searchTimer = null
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (searchQuery.value.trim()) {
      searchEntries(searchQuery.value)
    } else {
      registryStore.searchResults = []
    }
  }, 300)
}

function handleSelectEntry(entryId) {
  selectEntry(entryId)
  loadCrossRelations(entryId)
  editMode.value = false
  showCreateForm.value = false
}

// -- Cross-relation handlers (L3) --
const conceptMap = computed(() => {
  const map = {}
  for (const e of registryStore.entries) {
    map[e.entry_id] = e
  }
  return map
})

function handleNavigateConcept(targetEntryId) {
  handleSelectEntry(targetEntryId)
}

async function handleReviewRelation(relationId, reviewStatus) {
  await reviewCrossRelation(relationId, { review_status: reviewStatus })
}

async function handleDeleteRelation(relationId) {
  if (!confirm('确定删除此跨文章关系？')) return
  const ok = await removeCrossRelation(relationId)
  if (ok) {
    // Refresh counts for current entry
    const entryIds = registryStore.entries.map(e => e.entry_id)
    loadCrossRelationCounts(entryIds)
  }
}

function resetForm() {
  showCreateForm.value = false
  formData.value = { canonical_name: '', concept_type: 'Concept', aliasesRaw: '', description: '' }
}

async function handleCreate() {
  const aliases = formData.value.aliasesRaw
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
  const entry = await addEntry({
    canonical_name: formData.value.canonical_name,
    concept_type: formData.value.concept_type || 'Concept',
    aliases,
    description: formData.value.description,
  })
  if (entry) {
    resetForm()
    selectEntry(entry.entry_id)
  }
}

function startEdit() {
  if (!selectedEntry.value) return
  editData.value = {
    canonical_name: selectedEntry.value.canonical_name,
    concept_type: selectedEntry.value.concept_type,
    aliasesRaw: (selectedEntry.value.aliases || []).join(', '),
    description: selectedEntry.value.description || '',
  }
  editMode.value = true
}

async function handleEdit() {
  const aliases = editData.value.aliasesRaw
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
  await editEntry(registryStore.selectedEntryId, {
    canonical_name: editData.value.canonical_name,
    concept_type: editData.value.concept_type,
    aliases,
    description: editData.value.description,
  })
  editMode.value = false
}

async function handleDelete() {
  if (!registryStore.selectedEntryId) return
  await removeEntry(registryStore.selectedEntryId)
}

async function handleUnlink(link) {
  await unlinkConcept(registryStore.selectedEntryId, {
    project_id: link.project_id,
    concept_key: link.concept_key,
  })
}

function openSuggestPanel() {
  currentPanel.value = 'suggest'
  showCreateForm.value = false
  editMode.value = false
  if (!suggestProjectId.value && lastProjectId.value) {
    suggestProjectId.value = lastProjectId.value
  }
}

function closeSuggestPanel() {
  currentPanel.value = 'list'
}

async function handleSuggest() {
  if (!suggestProjectId.value) return
  await loadSuggestions(suggestProjectId.value)
}

async function quickCreate(candidate) {
  const entry = await addEntry({
    canonical_name: candidate.display_name,
    concept_type: candidate.concept_type,
    aliases: [],
    description: '',
  })
  if (entry && suggestProjectId.value) {
    await linkConcept(entry.entry_id, {
      project_id: suggestProjectId.value,
      concept_key: candidate.concept_key,
      project_name: registryStore.suggestResult?.project_name || '',
    })
    // Refresh suggestions
    await loadSuggestions(suggestProjectId.value)
  }
}

async function quickLink(match) {
  await linkConcept(match.matched_entry_id, {
    project_id: suggestProjectId.value,
    concept_key: match.concept_key,
    project_name: registryStore.suggestResult?.project_name || '',
  })
  await loadSuggestions(suggestProjectId.value)
}

async function quickLinkCrossType(match) {
  // Cross-type linking: explicit user action to promote the cross-type hint to
  // a real registry link. Uses the same linkConcept backend call, so the
  // canonical entry on the registry side gains a new source_link.
  await linkConcept(match.matched_entry_id, {
    project_id: suggestProjectId.value,
    concept_key: match.concept_key,
    project_name: registryStore.suggestResult?.project_name || '',
  })
  await loadSuggestions(suggestProjectId.value)
}

async function handleExport() {
  try {
    const res = await fetch(
      (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001') + '/api/registry/export'
    )
    const json = await res.json()
    const blob = new Blob([JSON.stringify(json.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gewu-registry-export-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    registryStore.actionError = '导出失败: ' + (e.message || '')
  }
}

async function hydrateRegistry() {
  await loadEntries()
  const entryIds = registryStore.entries.map(e => e.entry_id)
  if (entryIds.length) loadCrossRelationCounts(entryIds)
  // Re-hydrate the currently-selected entry if one is set, so the
  // middle detail panel flips to the new data source too.
  if (registryStore.selectedEntryId) {
    await selectEntry(registryStore.selectedEntryId)
    await loadCrossRelations(registryStore.selectedEntryId)
  }
}

onMounted(hydrateRegistry)

// Reload registry on mode flip so the list + counts switch together.
watch(appMode, () => { hydrateRegistry() })
</script>

<style scoped>
/* Legacy sidebar styles removed (now provided by AppShell). Topbar buttons & tabs first. */
.topbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: #fff;
  color: var(--accent-primary);
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover { background: var(--bg-muted); border-color: var(--border-strong); }
.topbar-btn .icon { font-size: 13px; }

.registry-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border-muted);
  margin-bottom: 20px;
}
.registry-tab {
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
.registry-tab:hover { color: var(--accent-primary); }
.registry-tab.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
  font-weight: 700;
}

/* -- Main area (now inside AppShell) -- */
.registry-main {
  max-width: 1400px;
  margin: 0 auto;
}

.phase2-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent-primary);
  font-weight: 700;
}

.section-title {
  margin: 0;
  font-size: 28px;
  color: var(--text-primary);
}

.section-copy,
.metric-line {
  color: var(--text-secondary);
  line-height: 1.6;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.card,
.state-card {
  border: 1px solid var(--border-default);
  background: linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-surface-2) 100%);
  border-radius: 18px;
  padding: 18px;
}

.error-card {
  border-color: #e2b0a8;
  background: #fff8f6;
}

.card-title {
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  flex: 1;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  transition: border-color 200ms;
}

.search-input:focus {
  border-color: var(--accent-primary);
}

.btn-primary {
  background: var(--accent-primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 10px 18px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
  transition: background 200ms;
  white-space: nowrap;
}

.btn-primary:hover {
  background: var(--accent-primary-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-small {
  border: 1px solid var(--border-default);
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-small:hover {
  background: var(--bg-surface-2);
}

.btn-danger {
  color: #c44;
  border-color: #e8b0b0;
}

.btn-danger:hover {
  background: #fff5f5;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.registry-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(260px, 320px);
  gap: 16px;
  align-items: start;
}

.pill,
.chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  color: var(--accent-primary);
  background: rgba(245, 248, 255, 0.95);
  font-size: 12px;
  font-weight: 600;
}

.chip.soft {
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-secondary);
}

.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 65vh;
  overflow-y: auto;
}

.candidate-button {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-default);
  background: rgba(255, 255, 255, 0.85);
  border-radius: 16px;
  padding: 14px;
  cursor: pointer;
  transition: border-color 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}

.candidate-button:hover,
.candidate-button.active {
  border-color: var(--accent-primary);
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(74, 111, 165, 0.08);
}

.candidate-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.candidate-name {
  color: var(--text-primary);
  font-weight: 700;
}

.candidate-status,
.candidate-meta {
  color: var(--text-secondary);
  font-size: 13px;
}

.xrel-badge {
  font-size: 10px;
  font-weight: 600;
  color: #6366f1;
  background: #eef2ff;
  padding: 1px 5px;
  border-radius: 4px;
  margin-left: 4px;
}

.xrel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pill.small {
  font-size: 11px;
  padding: 1px 6px;
  margin-left: 6px;
}

/* -- Cross-relation filter panel -- */
.xfilter-summary {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}
.xfilter-active { color: var(--accent-primary); font-weight: 600; }

.xfilter-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.xfilter-tab {
  flex: 1;
  padding: 5px 0;
  font-size: 11px;
  border: none;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}
.xfilter-tab:not(:last-child) { border-right: 1px solid #e5e7eb; }
.xfilter-tab.active { background: var(--accent-primary); color: #fff; font-weight: 600; }
.xfilter-tab:hover:not(.active) { background: #f3f4f6; }

.xfilter-section { margin-bottom: 12px; }
.xfilter-label {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.xfilter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.xfilter-chip {
  font-size: 10px;
  padding: 3px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}
.xfilter-chip.active { background: #eef2ff; border-color: #6366f1; color: #4338ca; font-weight: 600; }
.xfilter-chip:hover:not(.active) { border-color: #9ca3af; }

.xfilter-row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.xfilter-half { flex: 1; }
.xfilter-select {
  font-size: 12px;
  padding: 4px 8px;
}

.xfilter-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.xfilter-divider {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 12px 0;
}

.detail-kicker,
.subsection-title {
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-title {
  margin: 6px 0 0;
  font-size: 24px;
  color: #1a1713;
}

.detail-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.open-detail-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--accent-primary);
  background: var(--accent-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}
.open-detail-btn:hover { background: #3c5d8a; border-color: #3c5d8a; }

.detail-sections {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 18px;
}

.mini-copy {
  font-size: 13px;
  margin: 0;
}

.empty-state,
.empty-note {
  color: #7a8090;
  font-size: 13px;
  line-height: 1.6;
}

.link-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  border: 1px solid #e4e8f0;
  border-radius: 12px;
  padding: 10px 12px;
  background: #fff;
}

.link-project {
  font-weight: 600;
  color: #1d1d1d;
  font-size: 13px;
}
.link-clickable {
  text-decoration: none;
  color: var(--accent-primary);
  cursor: pointer;
  transition: color 100ms;
}
.link-clickable:hover {
  color: #2c5282;
  text-decoration: underline;
}

.link-concept {
  color: var(--text-secondary);
  font-size: 12px;
  flex: 1;
}

.action-row {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.form-input {
  width: 100%;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--accent-primary);
}

.suggest-summary {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: #fff;
}

.suggest-section {
  margin-top: 16px;
}

.suggest-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-muted);
}

.suggest-item:last-child {
  border-bottom: none;
}

.error-text {
  color: #c44;
  font-size: 13px;
  margin-top: 10px;
}

@media (max-width: 1240px) {
  .registry-layout {
    grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  }
  .action-card {
    grid-column: span 2;
  }
}

@media (max-width: 960px) {
  .registry-shell {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
  }
  .registry-layout {
    grid-template-columns: 1fr;
  }
  .action-card {
    grid-column: auto;
  }
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
