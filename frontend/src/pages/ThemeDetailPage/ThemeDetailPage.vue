<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

  <div class="theme-detail-shell">
    <!-- Left: theme overview -->
    <aside class="td-sidebar">
      <template v-if="panorama">
        <h2 class="td-theme-name">{{ panorama.theme.name }}</h2>
        <p v-if="panorama.theme.description" class="td-theme-desc">{{ panorama.theme.description }}</p>

        <div class="td-stats">
          <div class="td-stat"><span class="td-stat-num">{{ panorama.stats.concept_count }}</span> 概念</div>
          <div class="td-stat"><span class="td-stat-num">{{ panorama.stats.article_count }}</span> 文章</div>
          <div class="td-stat"><span class="td-stat-num">{{ panorama.stats.relation_count }}</span> 跨文章关系</div>
        </div>

        <div v-if="panorama.theme.keywords?.length" class="td-keywords">
          <span v-for="kw in panorama.theme.keywords" :key="kw" class="td-kw-chip">{{ kw }}</span>
        </div>

        <button class="td-discover-btn" :disabled="discovering" @click="handleDiscover">
          {{ discovering ? '发现中...' : '发现主题内关系' }}
        </button>
        <div v-if="discoverResult" class="td-discover-result">
          {{ discoverResult }}
        </div>

        <!-- Discover V2 theme-scoped status panel (P4 step 8, 2026-04-17).
             Collapses silently when nothing has ever run against this
             theme, so the sidebar stays clean for brand-new themes. -->
        <section
          v-if="themeDiscover.stats.total > 0 || themeDiscover.history.length > 0"
          class="td-discover-panel"
        >
          <div class="td-discover-panel-title">Discover 队列（本主题）</div>

          <!-- Per-status counts -->
          <div class="td-discover-status-row">
            <span
              v-for="(count, status) in themeDiscover.stats.by_status"
              :key="status"
              :class="['td-ds-badge', `td-ds-badge--${status}`]"
            >{{ discoverStatusLabel(status) }} {{ count }}</span>
          </div>

          <!-- Most-recent history entries -->
          <div v-if="themeDiscover.history.length > 0" class="td-discover-history">
            <div class="td-discover-history-title">近 {{ Math.min(themeDiscover.history.length, 5) }} 次发现</div>
            <div
              v-for="entry in themeDiscover.history.slice(0, 5)"
              :key="(entry.job_id || '') + entry.run_at"
              class="td-discover-history-row"
            >
              <span class="td-ds-when">{{ shortDateTime(entry.run_at) }}</span>
              <span class="td-ds-gained">+{{ entry.discovered }} 关系</span>
              <span v-if="entry.errors_count" class="td-ds-errors">· {{ entry.errors_count }} 错</span>
              <span class="td-ds-job" :title="entry.job_id">{{ shortJobId(entry.job_id) }}</span>
            </div>
          </div>
        </section>

        <!-- Concept group nav -->
        <nav class="td-group-nav">
          <div class="td-group-nav-title">概念分组</div>
          <button class="td-nav-item" :class="{ active: scrollTarget === 'bridge' }" @click="scrollTo('bridge')">
            桥接概念 ({{ panorama.grouped_concepts.bridge.length }})
          </button>
          <button class="td-nav-item" :class="{ active: scrollTarget === 'core' }" @click="scrollTo('core')">
            核心概念 ({{ panorama.grouped_concepts.core.length }})
          </button>
          <button class="td-nav-item" :class="{ active: scrollTarget === 'peripheral' }" @click="scrollTo('peripheral')">
            边缘概念 ({{ panorama.grouped_concepts.peripheral.length }})
          </button>
        </nav>

        <div class="td-articles">
          <div class="td-group-nav-title">涉及文章</div>
          <div v-for="a in panorama.articles" :key="a" class="td-article-item">{{ a }}</div>
        </div>
      </template>
      <div v-else-if="loading" class="td-loading">加载中...</div>
      <div v-else-if="error" class="td-error">{{ error }}</div>
    </aside>

    <!-- Middle: main content area -->
    <main class="td-main">
      <div class="td-tabs">
        <button v-for="t in tabs" :key="t.key" class="td-tab" :class="{ active: activeTab === t.key }" @click="activeTab = t.key">
          {{ t.label }}
        </button>
      </div>

      <template v-if="panorama">
        <!-- Coverage & risk strip — GPT-suggested "not missing knowledge"
             early warning. Aggregates silent failures and suggestion count
             so the user knows the theme is complete (or explicitly isn't). -->
        <div v-if="hasCoverageSignal" class="td-coverage-bar">
          <div class="td-coverage-title">覆盖与风险</div>
          <div class="td-coverage-items">
            <button v-if="suggestionCount" class="td-coverage-item warn" @click="activeTab = 'suggestions'">
              <span class="td-coverage-num">{{ suggestionCount }}</span>
              <span>同文章但未纳入主题</span>
            </button>
            <div v-if="silent.xrels_with_partial_source" class="td-coverage-item warn">
              <span class="td-coverage-num">{{ silent.xrels_with_partial_source }}</span>
              <span>桥接关系一端原文缺失</span>
            </div>
            <div v-if="silent.xrels_with_no_readable_source" class="td-coverage-item danger">
              <span class="td-coverage-num">{{ silent.xrels_with_no_readable_source }}</span>
              <span>桥接关系两端原文均缺失</span>
            </div>
            <div v-if="silent.descriptions_degraded" class="td-coverage-item warn">
              <span class="td-coverage-num">{{ silent.descriptions_degraded }}</span>
              <span>概念描述 degraded</span>
            </div>
            <div v-if="silent.concepts_missing_source_links" class="td-coverage-item danger">
              <span class="td-coverage-num">{{ silent.concepts_missing_source_links }}</span>
              <span>概念无来源链接</span>
            </div>
            <div v-if="silent.bridge_without_xrels" class="td-coverage-item warn">
              <span class="td-coverage-num">{{ silent.bridge_without_xrels }}</span>
              <span>桥接分类但无有效跨文关系</span>
            </div>
            <div v-if="coverage && coverage.last_run_at" class="td-coverage-item info">
              <span class="td-coverage-num">{{ coverage.discovered }}</span>
              <span>发现新桥接（最近运行 {{ formatDate(coverage.last_run_at) }}）</span>
            </div>
            <div v-else class="td-coverage-item info">
              <span>桥接发现</span><span>尚未运行（点击"发现主题内关系"）</span>
            </div>
          </div>
        </div>

        <!-- Tab 1: Concept Groups -->
        <div v-if="activeTab === 'groups'" class="td-content">
          <section v-if="panorama.grouped_concepts.bridge.length" id="group-bridge" class="td-group-section">
            <h3 class="td-group-title">桥接概念 <span class="td-count">{{ panorama.grouped_concepts.bridge.length }}</span></h3>
            <p class="td-group-hint">连接不同文章的关键概念，拥有跨文章关系</p>

            <!-- Confirmed members first -->
            <div v-if="bridgeMembers.length" class="td-bridge-subgroup">
              <div class="td-bridge-subtitle">已确认 <span class="td-count">{{ bridgeMembers.length }}</span></div>
              <div class="td-concept-grid">
                <div v-for="c in bridgeMembers" :key="c.entry_id" class="td-concept-card bridge">
                  <div class="td-cc-header">
                    <span class="td-cc-name">
                      {{ c.canonical_name }}
                      <span v-if="isDegradedDescription(c)" class="td-cc-degraded" title="描述疑似模板生成，未经 LLM 语义加工">!</span>
                    </span>
                    <span class="td-cc-type">{{ c.concept_type }}</span>
                  </div>
                  <p v-if="c.description" class="td-cc-desc">{{ c.description.slice(0, 100) }}{{ c.description.length > 100 ? '...' : '' }}</p>
                  <div class="td-cc-meta">
                    <span class="td-cc-role td-cc-role-member">已确认</span>
                    <span>{{ c.source_links?.length || 0 }} 文章</span>
                    <span class="td-cc-xrel">x-rel {{ c.xrel_count }}</span>
                    <span>桥接分 {{ c.bridge_score.toFixed(1) }}</span>
                  </div>
                  <router-link :to="`/workspace/entry/${c.entry_id}`" class="td-cc-link">查看详情 &rarr;</router-link>
                </div>
              </div>
            </div>

            <!-- Candidates after -->
            <div v-if="bridgeCandidates.length" class="td-bridge-subgroup">
              <div class="td-bridge-subtitle">候选（待审阅） <span class="td-count">{{ bridgeCandidates.length }}</span></div>
              <div class="td-concept-grid">
                <div v-for="c in bridgeCandidates" :key="c.entry_id" class="td-concept-card bridge td-concept-card-candidate">
                  <div class="td-cc-header">
                    <span class="td-cc-name">
                      {{ c.canonical_name }}
                      <span v-if="isDegradedDescription(c)" class="td-cc-degraded" title="描述疑似模板生成，未经 LLM 语义加工">!</span>
                    </span>
                    <span class="td-cc-type">{{ c.concept_type }}</span>
                  </div>
                  <p v-if="c.description" class="td-cc-desc">{{ c.description.slice(0, 100) }}{{ c.description.length > 100 ? '...' : '' }}</p>
                  <div class="td-cc-meta">
                    <span class="td-cc-role td-cc-role-candidate">候选</span>
                    <span>{{ c.source_links?.length || 0 }} 文章</span>
                    <span class="td-cc-xrel">x-rel {{ c.xrel_count }}</span>
                    <span>桥接分 {{ c.bridge_score.toFixed(1) }}</span>
                  </div>
                  <router-link :to="`/workspace/entry/${c.entry_id}`" class="td-cc-link">查看详情 &rarr;</router-link>
                </div>
              </div>
            </div>
          </section>

          <section v-if="panorama.grouped_concepts.core.length" id="group-core" class="td-group-section">
            <h3 class="td-group-title">核心概念 <span class="td-count">{{ panorama.grouped_concepts.core.length }}</span></h3>
            <p class="td-group-hint">主题的核心成员概念</p>
            <div class="td-concept-grid">
              <div v-for="c in panorama.grouped_concepts.core" :key="c.entry_id" class="td-concept-card">
                <div class="td-cc-header">
                  <span class="td-cc-name">{{ c.canonical_name }}</span>
                  <span class="td-cc-type">{{ c.concept_type }}</span>
                </div>
                <p v-if="c.description" class="td-cc-desc">{{ c.description.slice(0, 100) }}{{ c.description.length > 100 ? '...' : '' }}</p>
                <div class="td-cc-meta">
                  <span>{{ c.source_links?.length || 0 }} 文章</span>
                </div>
                <router-link :to="`/workspace/entry/${c.entry_id}`" class="td-cc-link">查看详情 &rarr;</router-link>
              </div>
            </div>
          </section>

          <section v-if="panorama.grouped_concepts.peripheral.length" id="group-peripheral" class="td-group-section">
            <h3 class="td-group-title">边缘概念 <span class="td-count">{{ panorama.grouped_concepts.peripheral.length }}</span></h3>
            <div class="td-concept-grid compact">
              <div v-for="c in panorama.grouped_concepts.peripheral" :key="c.entry_id" class="td-concept-card small">
                <span class="td-cc-name">{{ c.canonical_name }}</span>
                <span class="td-cc-type">{{ c.concept_type }}</span>
                <router-link :to="`/workspace/entry/${c.entry_id}`" class="td-cc-link">查看 &rarr;</router-link>
              </div>
            </div>
          </section>
        </div>

        <!-- Tab 3: Suggestions (orphans sharing articles with this theme) -->
        <div v-if="activeTab === 'suggestions'" class="td-content">
          <div v-if="!(panorama.suggested_memberships || []).length" class="td-empty">
            <p>没有"同文章但未纳入"的概念 — 本主题在已覆盖文章里不漏知识。</p>
          </div>
          <div v-else>
            <p class="td-group-hint">
              这些 canonical 概念与本主题已包含的文章同源但尚未纳入主题。
              点击"纳入候选"把它作为 candidate 加入，便于后续审阅。
            </p>
            <div v-if="highSuggestions.length" class="td-suggest-section">
              <div class="td-bridge-subtitle">优先建议 <span class="td-count">{{ highSuggestions.length }}</span></div>
              <div class="td-suggest-list">
                <div v-for="s in highSuggestions" :key="s.entry_id" class="td-suggest-item">
                  <div class="td-suggest-main">
                    <div>
                      <span class="td-suggest-name">{{ s.canonical_name }}</span>
                      <span class="td-cc-type">{{ s.concept_type }}</span>
                    </div>
                    <p v-if="s.description" class="td-suggest-desc">{{ s.description }}</p>
                    <div class="td-suggest-reason">{{ s.reason }}</div>
                  </div>
                  <div class="td-suggest-actions">
                    <button class="btn-xrel btn-primary" @click="handleAttachSuggestion(s.entry_id)">
                      纳入候选
                    </button>
                    <router-link :to="`/workspace/entry/${s.entry_id}`" class="btn-xrel">
                      查看详情
                    </router-link>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="lowSuggestions.length" class="td-suggest-section">
              <div class="td-bridge-subtitle td-bridge-subtitle-muted">
                可能无关（数字/时间型 Evidence/Example） <span class="td-count">{{ lowSuggestions.length }}</span>
                <button class="td-suggest-toggle" @click="showLowSuggestions = !showLowSuggestions">
                  {{ showLowSuggestions ? '收起' : '展开' }}
                </button>
              </div>
              <div v-if="showLowSuggestions" class="td-suggest-list">
                <div v-for="s in lowSuggestions" :key="s.entry_id" class="td-suggest-item td-suggest-item-low">
                  <div class="td-suggest-main">
                    <div>
                      <span class="td-suggest-name">{{ s.canonical_name }}</span>
                      <span class="td-cc-type">{{ s.concept_type }}</span>
                    </div>
                    <p v-if="s.description" class="td-suggest-desc">{{ s.description }}</p>
                    <div class="td-suggest-reason">{{ s.reason }}</div>
                  </div>
                  <div class="td-suggest-actions">
                    <button class="btn-xrel" @click="handleAttachSuggestion(s.entry_id)">
                      纳入候选
                    </button>
                    <router-link :to="`/workspace/entry/${s.entry_id}`" class="btn-xrel">
                      查看详情
                    </router-link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 2: Bridge List -->
        <div v-if="activeTab === 'bridges'" class="td-content">
          <div v-if="!panorama.bridge_relations.length" class="td-empty">
            <p>暂无桥接关系</p>
            <button class="td-discover-btn" @click="handleDiscover" :disabled="discovering">立即发现</button>
          </div>
          <div v-else class="td-bridge-list">
            <CrossRelationCard
              v-for="rel in panorama.bridge_relations"
              :key="rel.relation_id"
              :relation="rel"
              :conceptMap="conceptMap"
              :currentEntryId="''"
              @navigate="navigateToConcept"
              @review="handleReview"
              @delete="handleDelete"
            />
          </div>
        </div>
      </template>
      <div v-else-if="loading" class="td-loading-main">加载中...</div>
    </main>
  </div>
  </AppShell>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import CrossRelationCard from '../../components/CrossRelationCard.vue'
// Read flips live/demo via dataClient; writes stay on the live API.
import { getThemePanorama } from '../../data/dataClient'
import { discoverCrossRelations, updateCrossRelation, deleteCrossRelation } from '../../services/api/registryApi'
import { appMode } from '../../runtime/appMode'
// Raw axios for the live-only Discover V2 endpoint. The api/index.js
// response interceptor already unwraps to the backend envelope — so what
// we get back is {success, data, ...}. Payload lives at ONE level down.
import service from '../../api/index'

const route = useRoute()
const props = defineProps({ themeId: String })

const panorama = ref(null)
const loading = ref(false)
const error = ref('')
const activeTab = ref('groups')
const scrollTarget = ref('')
const discovering = ref(false)
const discoverResult = ref('')

// Discover V2 — theme-scoped status aggregate (P4 step 8). Fetched
// alongside the panorama so the sidebar can surface history + jobs +
// funnel trend without user action. Demo mode skips the fetch.
const themeDiscover = ref({ coverage: {}, history: [], jobs: [], stats: { total: 0, by_status: {} } })

const tabs = [
  { key: 'groups', label: '概念分组' },
  { key: 'bridges', label: '桥接清单' },
  { key: 'suggestions', label: '建议纳入' },
]

const crumbs = computed(() => [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '主题枢纽', to: '/workspace/themes' },
  { label: panorama.value?.theme?.name || (props.themeId || route.params.themeId || '主题全景') },
])

const conceptMap = computed(() => {
  if (!panorama.value) return {}
  const map = {}
  const groups = panorama.value.grouped_concepts
  for (const group of [groups.core, groups.bridge, groups.peripheral]) {
    for (const c of group) {
      map[c.entry_id] = c
    }
  }
  return map
})

// Bridge concepts split by role so confirmed ones surface above candidates
// (see GPT feedback P3: candidate-role concepts shouldn't lead the panel).
// Sort rule: role=member first (desc by bridge_score), then candidate
// (desc by bridge_score). Within each subgroup the original score ordering
// from the API is preserved.
const bridgeMembers = computed(() => {
  if (!panorama.value) return []
  return panorama.value.grouped_concepts.bridge.filter(c => c.role === 'member')
})
const bridgeCandidates = computed(() => {
  if (!panorama.value) return []
  return panorama.value.grouped_concepts.bridge.filter(c => c.role !== 'member')
})

// A description is considered "degraded" when it matches one of the legacy
// auto-generated templates (e.g. "关联节点：xxx") or when the backend flags
// it explicitly via description_degraded. Surfacing this warns the user
// that the text is not a proper LLM-authored summary.
function isDegradedDescription(concept) {
  if (!concept) return false
  if (concept.description_degraded === true) return true
  const desc = (concept.description || '').trim()
  if (!desc) return false
  return desc.startsWith('关联节点：') || desc.startsWith('关联节点:')
}

// ---------------------------------------------------------------------------
// Coverage & risk strip — drives the "not missing knowledge" header band.
// ---------------------------------------------------------------------------
const silent = computed(() => panorama.value?.silent_failures || {})
const coverage = computed(() => panorama.value?.discovery_coverage || null)
const suggestionCount = computed(
  () => (panorama.value?.suggested_memberships || []).length,
)
// High / low relevance split so pure quantitative Evidence (e.g.
// "9000 多次提交") does not drown out substantive suggestions.
const highSuggestions = computed(
  () => (panorama.value?.suggested_memberships || []).filter(s => s.relevance !== 'low'),
)
const lowSuggestions = computed(
  () => (panorama.value?.suggested_memberships || []).filter(s => s.relevance === 'low'),
)
const showLowSuggestions = ref(false)
const hasCoverageSignal = computed(() => {
  if (!panorama.value) return false
  const s = silent.value
  if (suggestionCount.value > 0) return true
  if (s.xrels_with_partial_source > 0) return true
  if (s.xrels_with_no_readable_source > 0) return true
  if (s.descriptions_degraded > 0) return true
  if (s.concepts_missing_source_links > 0) return true
  if (s.bridge_without_xrels > 0) return true
  // Always show coverage status — users should see "未运行" too.
  return true
})
function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false }).slice(0, 16)
  } catch (_) {
    return iso.slice(0, 16)
  }
}

async function handleAttachSuggestion(entryId) {
  const tid = props.themeId || route.params.themeId
  try {
    await fetch(`/api/registry/themes/${tid}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concept_entry_ids: [entryId],
        role: 'candidate',
        score: 0.7,
      }),
    })
    await loadPanorama()
  } catch (e) {
    alert('纳入失败: ' + (e.message || e))
  }
}

async function loadPanorama() {
  const tid = props.themeId || route.params.themeId
  if (!tid) return
  loading.value = true
  error.value = ''
  try {
    const res = await getThemePanorama(tid)
    panorama.value = res.data
  } catch (e) {
    // Also clear the stale panorama — otherwise when a subsequent load
    // fails (e.g. switching live→demo for a theme that doesn't exist in
    // demo fixtures), the previous theme's content stays on screen and
    // the error card is hidden behind v-if="panorama" branches.
    panorama.value = null
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
  // Fire-and-forget the theme-scoped discover aggregate. Independent of
  // the panorama fetch so a slow/missing discover endpoint never holds
  // up the rest of the page.
  loadThemeDiscover(tid)
}

async function loadThemeDiscover(themeId) {
  // Demo mode: clear to empty so stale live data doesn't leak into the
  // demo view. Real backend has no demo fixture for discover-jobs yet.
  if (appMode.value === 'demo') {
    themeDiscover.value = { coverage: {}, history: [], jobs: [], stats: { total: 0, by_status: {} } }
    return
  }
  try {
    const res = await service({
      url: `/api/auto/discover-jobs/by-theme/${encodeURIComponent(themeId)}`,
      method: 'GET',
    })
    const d = (res && res.data) || {}
    themeDiscover.value = {
      coverage: d.coverage || {},
      history: d.history || [],
      jobs: d.jobs || [],
      stats: d.stats || { total: 0, by_status: {} },
    }
  } catch (_e) {
    // Informational panel — don't surface the error, just keep last good.
  }
}

function discoverStatusLabel(status) {
  const map = {
    pending: '待办',
    running: '运行中',
    completed: '完成',
    partial: '部分完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

function shortJobId(id) {
  if (!id) return ''
  return id.length > 14 ? `${id.slice(0, 14)}…` : id
}

function shortDateTime(iso) {
  if (!iso) return ''
  // Incoming: "2026-04-17T13:42:11" — strip seconds for denser display.
  return iso.replace('T', ' ').slice(0, 16)
}

function scrollTo(group) {
  scrollTarget.value = group
  const el = document.getElementById(`group-${group}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function navigateToConcept(entryId) {
  window.open(`/workspace/entry/${entryId}`, '_blank')
}

async function handleDiscover() {
  const tid = props.themeId || route.params.themeId
  discovering.value = true
  discoverResult.value = ''
  try {
    const res = await discoverCrossRelations({ theme_id: tid, max_pairs: 30, min_confidence: 0.6 })
    const d = res.data
    discoverResult.value = `新增 ${d.discovered} 条，跳过 ${d.skipped} 条重复`
    await loadPanorama()
  } catch (e) {
    discoverResult.value = `发现失败: ${e.message || '未知错误'}`
  } finally {
    discovering.value = false
  }
}

async function handleReview(relationId, reviewStatus) {
  await updateCrossRelation(relationId, { review_status: reviewStatus })
  await loadPanorama()
}

async function handleDelete(relationId) {
  if (!confirm('确定删除此跨文章关系？')) return
  await deleteCrossRelation(relationId)
  await loadPanorama()
}

onMounted(loadPanorama)
watch(() => route.params.themeId, loadPanorama)
// Reload panorama when live/demo flips so the theme page swaps source.
watch(appMode, loadPanorama)
</script>

<style scoped>
.theme-detail-shell {
  display: flex;
  min-height: 100vh;
  background: #f8f9fc;
}

/* Sidebar */
.td-sidebar {
  width: 300px;
  min-width: 300px;
  background: linear-gradient(180deg, #f5f8ff 0%, #fff 100%);
  border-right: 1px solid #d4dce8;
  padding: 24px 20px;
  overflow-y: auto;
}
.td-back { font-size: 13px; color: #4a6fa5; text-decoration: none; display: block; margin-bottom: 16px; }
.td-back:hover { text-decoration: underline; }
.td-theme-name { font-size: 22px; font-weight: 700; color: #1e1813; margin: 0 0 8px; }
.td-theme-desc { font-size: 13px; color: #5a6573; line-height: 1.5; margin: 0 0 16px; }

.td-stats { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.td-stat { font-size: 12px; color: #6b7280; }
.td-stat-num { font-size: 18px; font-weight: 700; color: #1e1813; display: block; }

.td-keywords { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.td-kw-chip { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: #eef2ff; color: #4338ca; }

.td-discover-btn {
  width: 100%;
  padding: 10px;
  background: #4a6fa5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 8px;
}
.td-discover-btn:hover:not(:disabled) { background: #3b5998; }
.td-discover-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.td-discover-result { font-size: 12px; color: #059669; margin-bottom: 16px; }

/* Discover V2 status panel (P4 step 8). Lives in the sidebar below the
   one-shot discover button. Keep typography quiet — it's an audit strip,
   not a hero element. */
.td-discover-panel {
  margin: 12px 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fbfaf5;
  border: 1px solid #e8e2d5;
}
.td-discover-panel-title {
  font-size: 12px;
  color: #5a6573;
  font-weight: 600;
  margin-bottom: 6px;
}
.td-discover-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.td-ds-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #eef2f8;
  color: #4a6fa5;
}
.td-ds-badge--running { background: #e7f3ec; color: #2d7a47; }
.td-ds-badge--partial { background: #fbeed7; color: #a86d12; }
.td-ds-badge--failed { background: #fbe4e0; color: #c45a4a; }
.td-ds-badge--cancelled { background: #eeeeee; color: #777; }

.td-discover-history-title {
  font-size: 11px;
  color: #7a7a7a;
  margin-bottom: 4px;
}
.td-discover-history-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 11px;
  color: #5a6573;
  padding: 4px 0;
  border-top: 1px dashed #eee5d0;
}
.td-discover-history-row:first-of-type { border-top: none; }
.td-ds-when { color: #555; }
.td-ds-gained { color: #2d7a47; font-weight: 500; }
.td-ds-errors { color: #c45a4a; }
.td-ds-job { font-family: 'SFMono-Regular', Menlo, monospace; color: #888; font-size: 10px; }

.td-group-nav { margin-top: 20px; }
.td-group-nav-title { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
.td-nav-item {
  display: block; width: 100%; text-align: left; padding: 8px 12px; border: none; background: none;
  font-size: 13px; color: #374151; cursor: pointer; border-radius: 6px; margin-bottom: 2px;
}
.td-nav-item:hover { background: #f3f4f6; }
.td-nav-item.active { background: #eef2ff; color: #4338ca; font-weight: 600; }

.td-articles { margin-top: 20px; }
.td-article-item { font-size: 12px; color: #5a6573; padding: 4px 0; }

.td-loading, .td-error { font-size: 13px; color: #6b7280; padding: 20px 0; }
.td-error { color: #dc2626; }

/* Main content */
.td-main { flex: 1; padding: 24px 32px; overflow-y: auto; }
.td-tabs { display: flex; gap: 0; border-bottom: 2px solid #e5e7eb; margin-bottom: 24px; }
.td-tab {
  padding: 10px 20px; border: none; background: none; font-size: 14px; color: #6b7280;
  cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px;
}
.td-tab.active { color: #4a6fa5; border-bottom-color: #4a6fa5; font-weight: 600; }
.td-tab:hover:not(.active) { color: #374151; }

.td-content { }
.td-loading-main { text-align: center; padding: 60px; color: #6b7280; }
.td-empty { text-align: center; padding: 60px; color: #6b7280; }

/* Concept groups */
.td-group-section { margin-bottom: 32px; }
.td-group-title { font-size: 18px; font-weight: 700; color: #1e1813; margin: 0 0 4px; }
.td-count { font-size: 14px; font-weight: 400; color: #9ca3af; }
.td-group-hint { font-size: 12px; color: #6b7280; margin: 0 0 16px; }

.td-concept-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.td-concept-grid.compact { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }

.td-concept-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px;
  transition: box-shadow 0.15s;
}
.td-concept-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.td-concept-card.bridge { border-left: 3px solid #6366f1; }
.td-concept-card-candidate { border-left-color: #a5b4fc; background: #fafbff; }
.td-concept-card.small { padding: 10px 14px; display: flex; align-items: center; gap: 8px; }

.td-bridge-subgroup { margin-bottom: 18px; }
.td-bridge-subgroup:last-child { margin-bottom: 0; }
.td-bridge-subtitle {
  font-size: 12px; font-weight: 600; color: #4338ca; text-transform: uppercase;
  letter-spacing: 0.5px; margin: 0 0 10px;
}
.td-cc-role {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
  text-transform: uppercase; letter-spacing: 0.3px;
}
.td-cc-role-member { background: #dcfce7; color: #166534; }
.td-cc-role-candidate { background: #fef3c7; color: #92400e; }
.td-cc-degraded {
  display: inline-block; margin-left: 4px; width: 16px; height: 16px;
  border-radius: 50%; background: #fde68a; color: #92400e; font-size: 11px;
  font-weight: 700; text-align: center; line-height: 16px; cursor: help;
}

.td-cc-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.td-cc-name { font-weight: 600; font-size: 14px; color: #1d1d1d; }
.td-cc-type { font-size: 11px; color: #6b7280; background: #f3f4f6; padding: 1px 6px; border-radius: 4px; white-space: nowrap; }
.td-cc-desc { font-size: 12px; color: #374151; line-height: 1.5; margin: 0 0 8px; }
.td-cc-meta { display: flex; gap: 10px; font-size: 11px; color: #9ca3af; margin-bottom: 6px; }
.td-cc-xrel { color: #6366f1; font-weight: 600; }
.td-cc-link { font-size: 12px; color: #4a6fa5; text-decoration: none; }
.td-cc-link:hover { text-decoration: underline; }

/* Bridge list */
.td-bridge-list { display: flex; flex-direction: column; gap: 12px; }

/* Coverage & risk strip (GPT-suggested "not missing knowledge" summary) */
.td-coverage-bar { background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 12px 14px; margin-bottom: 20px; }
.td-coverage-title { font-size: 12px; font-weight: 700; color: #92400e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
.td-coverage-items { display: flex; flex-wrap: wrap; gap: 8px; }
.td-coverage-item { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; padding: 4px 10px; border-radius: 6px; background: #fff; border: 1px solid #fcd34d; color: #78350f; text-decoration: none; cursor: default; }
.td-coverage-item.warn { background: #fffbeb; }
.td-coverage-item.danger { background: #fef2f2; border-color: #fecaca; color: #991b1b; }
.td-coverage-item.info { background: #f0f9ff; border-color: #bae6fd; color: #075985; }
.td-coverage-item button, .td-coverage-item { cursor: pointer; }
.td-coverage-item:not(button):not(a) { cursor: default; }
.td-coverage-num { font-weight: 700; font-size: 13px; }

/* Suggestions tab */
.td-suggest-list { display: flex; flex-direction: column; gap: 10px; }
.td-suggest-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 12px 14px; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; }
.td-suggest-main { flex: 1; min-width: 0; }
.td-suggest-name { font-weight: 600; font-size: 14px; color: #1d1d1d; margin-right: 8px; }
.td-suggest-desc { font-size: 12px; color: #374151; line-height: 1.5; margin: 4px 0; }
.td-suggest-reason { font-size: 11px; color: #92400e; background: #fffbeb; padding: 2px 8px; border-radius: 4px; display: inline-block; }
.td-suggest-actions { display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
.td-suggest-section { margin-bottom: 20px; }
.td-suggest-section:last-child { margin-bottom: 0; }
.td-suggest-item-low { background: #fafafa; opacity: 0.85; }
.td-suggest-item-low .td-suggest-reason { background: #f3f4f6; color: #6b7280; }
.td-bridge-subtitle-muted { color: #6b7280; display: flex; align-items: center; gap: 10px; }
.td-suggest-toggle { margin-left: auto; font-size: 11px; padding: 2px 10px; border: 1px solid #e5e7eb; background: #fff; border-radius: 4px; cursor: pointer; color: #374151; }
.td-suggest-toggle:hover { background: #f3f4f6; }
</style>
