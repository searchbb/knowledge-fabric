<template>
  <AppShell :crumbs="crumbs">
    <section class="wiki-topics-page">
      <header class="page-head">
        <div>
          <div class="section-badge">WIKI 主题</div>
          <h1>主题总览</h1>
          <p>查看所有已预消化主题、每个主题下的文章数量、最近增长与关联主题簇。</p>
        </div>
        <div class="summary">
          <span class="summary-number">{{ filteredTopics.length }}</span>
          <span>主题</span>
        </div>
      </header>

      <div class="stats-grid">
        <div><strong>{{ topics.length }}</strong><span>已消化主题</span></div>
        <div><strong>{{ articleTotal }}</strong><span>已处理文章</span></div>
        <div><strong>{{ needsReviewTotal }}</strong><span>待复核文章</span></div>
        <div><strong>{{ coverageCounts.linked || 0 }}</strong><span>已关联主题簇</span></div>
        <div><strong>{{ coverageCounts.candidate || 0 }}</strong><span>有候选主题簇</span></div>
        <div><strong>{{ unresolvedCoverageCount }}</strong><span>未关联主题簇</span></div>
      </div>

      <div class="toolbar">
        <input v-model="searchText" placeholder="搜索主题 / 文章关键词" />
        <select v-model="sortMode">
          <option value="articles">文章数 ↓</option>
          <option value="updated">最近更新 ↓</option>
          <option value="title">主题名称 A-Z</option>
        </select>
        <button class="secondary-btn" :disabled="loading" @click="loadTopics">刷新</button>
      </div>

      <div class="coverage-filters" aria-label="主题簇覆盖 状态筛选">
        <button
          v-for="option in coverageFilterOptions"
          :key="option.value"
          :class="['filter-btn', { active: coverageFilter === option.value }]"
          @click="coverageFilter = option.value"
        >
          {{ option.label }}
          <span>{{ option.value === 'all' ? topics.length : coverageCounts[option.value] || 0 }}</span>
        </button>
      </div>

      <div v-if="error" class="state-card error-card">{{ error }}</div>
      <div v-else-if="loading" class="state-card">加载中...</div>
      <div v-else-if="!topics.length" class="state-card">暂无已预消化主题。</div>
      <div v-else-if="!filteredTopics.length" class="state-card">当前筛选下没有主题。</div>
      <div v-else class="topic-table">
        <article v-for="topic in filteredTopics" :key="topic.topic_id" class="topic-row">
          <div class="topic-main">
            <router-link
              class="topic-title"
              :to="`/workspace/wiki-topics/${topic.topic_id}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ topic.title || topic.topic_id }}
            </router-link>
            <div class="topic-id">{{ topic.topic_id }}</div>
            <div class="concept-list">
              <span v-for="concept in (topic.top_concepts || []).slice(0, 5)" :key="concept">{{ concept }}</span>
            </div>
            <div v-if="topic.representative_articles?.length" class="representative">
              <span>代表文章：</span>
              <span>{{ topic.representative_articles.slice(0, 2).map((item) => item.title).join(' / ') }}</span>
            </div>
          </div>
          <div class="topic-metrics">
            <div><strong>{{ topic.article_count || 0 }}</strong><span>文章</span></div>
            <div><strong>{{ topic.completed_count || 0 }}</strong><span>已完成</span></div>
            <div><strong>{{ topic.needs_review_count || 0 }}</strong><span>待复核</span></div>
            <div><strong>{{ shortDate(topic.last_processed_at) }}</strong><span>最近更新</span></div>
          </div>
          <div class="row-actions">
            <div class="coverage-pill" :class="coverageStatus(topic)">
              主题簇：{{ coverageLabel(coverageStatus(topic)) }}
            </div>
            <div v-if="coverageCandidateCount(topic)" class="muted">候选 {{ coverageCandidateCount(topic) }} 个</div>
            <router-link
              class="action-link"
              :to="`/workspace/wiki-topics/${topic.topic_id}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              打开主题
            </router-link>
            <router-link
              v-if="linkedClusterId(topic)"
              class="action-link"
              :to="`/workspace/topic-clusters/${linkedClusterId(topic)}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              打开主题簇
            </router-link>
            <router-link
              v-else
              class="action-link"
              :to="`/workspace/wiki-topics/${topic.topic_id}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              处理归集
            </router-link>
          </div>
        </article>
      </div>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import { listWikiTopics } from '../data/dataClient'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '主题总览' },
]

const topics = ref([])
const coverageCounts = ref({ linked: 0, candidate: 0, needs_cluster: 0, watch: 0, ignored: 0 })
const loading = ref(false)
const error = ref('')
const searchText = ref('')
const sortMode = ref('articles')
const route = useRoute()
const coverageFilter = ref(route?.query?.coverage || 'all')

const coverageFilterOptions = [
  { value: 'all', label: '全部' },
  { value: 'linked', label: '已关联主题簇' },
  { value: 'candidate', label: '有候选主题簇' },
  { value: 'needs_cluster', label: '待归集' },
  { value: 'watch', label: '观察中' },
  { value: 'ignored', label: '已忽略' },
]

const articleTotal = computed(() => topics.value.reduce((total, topic) => total + Number(topic.article_count || 0), 0))
const needsReviewTotal = computed(() => topics.value.reduce((total, topic) => total + Number(topic.needs_review_count || 0), 0))
const unresolvedCoverageCount = computed(() =>
  ['candidate', 'needs_cluster', 'watch'].reduce((total, status) => total + Number(coverageCounts.value[status] || 0), 0),
)

const filteredTopics = computed(() => {
  const query = searchText.value.trim().toLowerCase()
  let items = topics.value
  if (query) {
    items = items.filter((topic) => {
      const haystack = [
        topic.title,
        topic.display_name,
        topic.topic_id,
        ...(topic.top_concepts || []),
        ...(topic.representative_articles || []).map((article) => article.title),
      ].join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }
  if (coverageFilter.value !== 'all') {
    items = items.filter((topic) => coverageStatus(topic) === coverageFilter.value)
  }
  return [...items].sort((a, b) => {
    if (sortMode.value === 'updated') return String(b.last_processed_at || '').localeCompare(String(a.last_processed_at || ''))
    if (sortMode.value === 'title') return String(a.title || a.topic_id).localeCompare(String(b.title || b.topic_id))
    return Number(b.article_count || 0) - Number(a.article_count || 0)
  })
})

function shortDate(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function coverageStatus(topic) {
  return topic?.cluster_coverage_status || topic?.cluster_coverage?.status || (topic?.cluster_ids?.length ? 'linked' : 'watch')
}

function coverageLabel(status) {
  return {
    linked: '已关联',
    candidate: '有候选',
    needs_cluster: '待归集',
    watch: '观察中',
    ignored: '已忽略',
  }[status] || status
}

function coverageCandidateCount(topic) {
  return Number(topic?.cluster_coverage?.candidate_count || topic?.cluster_coverage?.candidate_clusters?.length || 0)
}

function linkedClusterId(topic) {
  return topic?.cluster_coverage?.linked_clusters?.[0]?.cluster_id || topic?.cluster_ids?.[0] || ''
}

async function loadTopics() {
  loading.value = true
  error.value = ''
  try {
    const response = await listWikiTopics({ includeCoverage: true })
    const data = response.data
    topics.value = Array.isArray(data) ? data : data?.topics || data?.items || []
    coverageCounts.value = data?.coverage_counts || topics.value.reduce((counts, topic) => {
      const status = coverageStatus(topic)
      counts[status] = (counts[status] || 0) + 1
      return counts
    }, { linked: 0, candidate: 0, needs_cluster: 0, watch: 0, ignored: 0 })
  } catch (err) {
    error.value = err?.message || '主题总览加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadTopics)
</script>

<style scoped>
.wiki-topics-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
}
.section-badge {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--accent-primary-hover);
}
h1 {
  margin: 4px 0 8px;
  font-size: 28px;
}
.page-head p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}
.summary,
.stats-grid div,
.topic-row {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
}
.summary {
  min-width: 112px;
  padding: 12px;
}
.summary-number {
  display: block;
  font-size: 26px;
  font-weight: 800;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(110px, 1fr));
  gap: 10px;
}
.stats-grid div {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stats-grid strong {
  font-size: 22px;
}
.stats-grid span,
.topic-id,
.representative,
.topic-metrics span,
.muted {
  color: var(--text-muted);
  font-size: 12px;
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
}
.coverage-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.filter-btn {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  padding: 8px 10px;
  cursor: pointer;
}
.filter-btn.active {
  color: var(--accent-primary-hover);
  background: var(--bg-selected);
  font-weight: 800;
}
.filter-btn span {
  margin-left: 6px;
  color: var(--text-muted);
}
.toolbar input,
.toolbar select {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 8px 10px;
}
.toolbar input {
  min-width: 280px;
}
.secondary-btn,
.action-link {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  color: var(--accent-primary-hover);
  padding: 8px 12px;
  font-weight: 700;
  text-decoration: none;
}
.topic-table {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.topic-row {
  display: grid;
  grid-template-columns: minmax(280px, 1.3fr) minmax(320px, 1fr) auto;
  gap: 16px;
  padding: 14px;
  align-items: center;
}
.topic-title {
  color: var(--text-primary);
  font-weight: 800;
  text-decoration: none;
}
.concept-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.concept-list span {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--text-secondary);
  font-size: 12px;
}
.representative {
  margin-top: 8px;
  line-height: 1.5;
}
.topic-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(70px, 1fr));
  gap: 8px;
}
.topic-metrics div {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.row-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}
.coverage-pill {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 800;
  color: var(--text-secondary);
  background: var(--bg-surface);
}
.coverage-pill.linked {
  color: #136f36;
  background: #effaf3;
}
.coverage-pill.candidate,
.coverage-pill.needs_cluster {
  color: #7c4a03;
  background: #fff7e6;
}
.coverage-pill.ignored {
  color: var(--text-muted);
}
.state-card,
.error-card {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-surface);
  color: var(--text-secondary);
}
.error-card {
  border-color: #f2b8b5;
  background: #fff1f0;
  color: #8c1d18;
}
@media (max-width: 980px) {
  .page-head,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .stats-grid,
  .topic-row {
    grid-template-columns: 1fr;
  }
  .topic-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
