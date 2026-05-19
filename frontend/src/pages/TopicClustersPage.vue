<template>
  <AppShell :crumbs="crumbs">
    <section class="topic-page">
      <header class="page-head">
        <div>
          <div class="section-badge">主题簇</div>
          <h1>主题汇集</h1>
          <p>把 Wiki 预消化主题、KFC 主题和后续研究项目聚合到更高层的战略研究主题下。</p>
        </div>
        <div class="summary">
          <span class="summary-number">{{ filteredClusters.length }}</span>
          <span>主题簇</span>
        </div>
      </header>

      <div class="toolbar">
        <button class="primary-btn" @click="showCreate = !showCreate">
          {{ showCreate ? '取消创建' : '创建主题簇' }}
        </button>
        <router-link class="secondary-link" to="/workspace/topic-clusters/proposals">查看建议包</router-link>
        <button class="secondary-btn" :disabled="creatingRefreshRequest" @click="requestRefresh">
          {{ creatingRefreshRequest ? '创建请求中...' : '生成主题簇建议' }}
        </button>
      </div>
      <p class="safety-copy">KFC 仅记录主题簇建议请求，不会自动调用模型、Codex 或外部任务；后续建议必须人工审阅后才能应用。</p>

      <section class="coverage-panel">
        <div>
          <h2>Wiki 主题簇覆盖</h2>
          <p>所有 Wiki 主题都进入可见治理状态；候选、待归集、观察中都需要人工确认后才会正式关联。</p>
        </div>
        <div class="coverage-stats">
          <router-link class="coverage-stat" to="/workspace/wiki-topics?coverage=linked">
            <strong>{{ topicCoverageCounts.linked || 0 }}</strong><span>已归集主题</span>
          </router-link>
          <router-link class="coverage-stat" to="/workspace/wiki-topics?coverage=candidate">
            <strong>{{ topicCoverageCounts.candidate || 0 }}</strong><span>候选待确认</span>
          </router-link>
          <router-link class="coverage-stat" to="/workspace/wiki-topics?coverage=needs_cluster">
            <strong>{{ topicCoverageCounts.needs_cluster || 0 }}</strong><span>待归集</span>
          </router-link>
          <router-link class="coverage-stat" to="/workspace/wiki-topics?coverage=watch">
            <strong>{{ topicCoverageCounts.watch || 0 }}</strong><span>观察中</span>
          </router-link>
          <router-link class="coverage-stat" to="/workspace/wiki-topics?coverage=ignored">
            <strong>{{ topicCoverageCounts.ignored || 0 }}</strong><span>已忽略</span>
          </router-link>
        </div>
      </section>

      <form v-if="showCreate" class="edit-panel" @submit.prevent="submitCreate">
        <div class="form-grid">
          <label>
            <span>标题</span>
            <input v-model="createForm.title" placeholder="例如：Agent-ready 企业软件栈" />
          </label>
          <label>
              <span>状态</span>
            <select v-model="createForm.status">
              <option value="candidate">candidate</option>
              <option value="active">active</option>
              <option value="needs_review">needs_review</option>
              <option value="retired">retired</option>
            </select>
          </label>
          <label>
            <span>战略相关度</span>
            <select v-model="createForm.strategic_relevance">
              <option value="unknown">unknown</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </label>
        </div>
        <label class="full-field">
          <span>描述</span>
          <textarea v-model="createForm.description" rows="3" placeholder="这个主题簇聚合哪些 Wiki 主题与 KFC 主题" />
        </label>
        <div class="form-actions">
          <button class="primary-btn" type="submit" :disabled="savingCreate">保存并打开</button>
          <span v-if="createError" class="inline-error">{{ createError }}</span>
        </div>
      </form>

      <div v-if="warnings.length" class="warning-bar">
        有 {{ warnings.length }} 个 sidecar 读取警告，页面已跳过异常文件继续加载。
      </div>
      <div v-if="error" class="state-card error-card">
        <div class="error-title">加载失败</div>
        <div>{{ error }}</div>
      </div>

      <template v-else>
        <div class="filters" aria-label="主题簇 状态筛选">
          <button
            v-for="option in filterOptions"
            :key="option.value"
            :class="['filter-btn', { active: statusFilter === option.value }]"
            @click="statusFilter = option.value"
          >
            {{ option.label }}
          </button>
        </div>

        <div v-if="loading" class="state-card">加载中...</div>
        <div v-else-if="!clusters.length" class="state-card">
          暂无主题簇。可以手工创建第一个战略主题聚合节点。
        </div>
        <div v-else-if="!filteredClusters.length" class="state-card">
          当前筛选下没有主题簇。
        </div>
        <div v-else class="cluster-grid">
          <TopicClusterCard
            v-for="cluster in filteredClusters"
            :key="cluster.cluster_id"
            :cluster="cluster"
            :wiki-links="previewLinks(cluster.cluster_id, 'wiki_topic')"
            :theme-links="previewLinks(cluster.cluster_id, 'kfc_theme')"
          />
        </div>

        <section class="requests-panel">
          <div class="panel-head">
            <h2>最近主题簇建议请求</h2>
            <button class="secondary-btn" @click="loadRefreshRequests">查看最近建议</button>
          </div>
          <div v-if="refreshRequestMessage" class="inline-success">{{ refreshRequestMessage }}</div>
          <div v-if="refreshRequestError" class="inline-error">{{ refreshRequestError }}</div>
          <div v-if="!refreshRequests.length" class="empty-note">暂无请求记录</div>
          <div v-else class="request-list">
            <article v-for="request in refreshRequests.slice(0, 5)" :key="request.request_id" class="request-row">
              <div>
                <div class="request-id">{{ request.request_id }}</div>
                <div class="request-meta">
                  <span>{{ request.status }}</span>
                  <span>{{ request.created_at }}</span>
                  <span>输入：{{ inputSummary(request.inputs) }}</span>
                </div>
              </div>
              <div class="rule-badges">
                <span v-if="request.rules?.proposal_only">仅生成建议</span>
                <span v-if="request.rules?.do_not_auto_apply">不自动应用</span>
              </div>
            </article>
          </div>
        </section>
      </template>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import TopicClusterCard from '../components/topic-clusters/TopicClusterCard.vue'
import {
  createTopicCluster,
  createTopicClusterRefreshRequest,
  getTopicCluster,
  listWikiTopics,
  listTopicClusterRefreshRequests,
  listTopicClusters,
} from '../data/dataClient'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '主题汇集' },
]

const filterOptions = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '活跃' },
  { value: 'candidate', label: '候选' },
  { value: 'needs_review', label: '待复核' },
]

const clusters = ref([])
const detailsById = ref({})
const warnings = ref([])
const loading = ref(false)
const error = ref('')
const statusFilter = ref('all')
const router = useRouter()
const showCreate = ref(false)
const savingCreate = ref(false)
const createError = ref('')
const creatingRefreshRequest = ref(false)
const refreshRequestError = ref('')
const refreshRequestMessage = ref('')
const refreshRequests = ref([])
const topicCoverageCounts = ref({ linked: 0, candidate: 0, needs_cluster: 0, watch: 0, ignored: 0 })
const createForm = ref({
  title: '',
  description: '',
  status: 'candidate',
  strategic_relevance: 'unknown',
})

const filteredClusters = computed(() => {
  if (statusFilter.value === 'all') return clusters.value
  return clusters.value.filter((cluster) => cluster.status === statusFilter.value)
})

function previewLinks(clusterId, targetType) {
  const detail = detailsById.value[clusterId]
  return (detail?.links_by_type?.[targetType] || []).filter((link) => !link.deleted && link.status !== 'rejected')
}

function inputSummary(inputs = {}) {
  const labels = []
  if (inputs.include_wiki_topics) labels.push('Wiki')
  if (inputs.include_kfc_themes) labels.push('KFC 主题')
  if (inputs.include_kfc_concepts) labels.push('KFC 概念')
  if (inputs.include_research_projects) labels.push('研究项目')
  return labels.join(', ') || '未选择'
}

async function loadClusters() {
  loading.value = true
  error.value = ''
  warnings.value = []
  try {
    const response = await listTopicClusters({ includeCounts: true })
    const data = response.data || {}
    clusters.value = data.items || []
    warnings.value = data.warnings || []
    const detailEntries = await Promise.all(
      clusters.value.map(async (cluster) => {
        try {
          const detailResponse = await getTopicCluster(cluster.cluster_id)
          return [cluster.cluster_id, detailResponse.data || {}]
        } catch {
          return [cluster.cluster_id, { links_by_type: {} }]
        }
      }),
    )
    detailsById.value = Object.fromEntries(detailEntries)
  } catch (err) {
    error.value = err?.message || '主题簇加载失败'
  } finally {
    loading.value = false
  }
}

async function loadTopicCoverage() {
  try {
    const response = await listWikiTopics({ includeCoverage: true })
    const data = response.data || {}
    topicCoverageCounts.value = data.coverage_counts || { linked: 0, candidate: 0, needs_cluster: 0, watch: 0, ignored: 0 }
  } catch {
    topicCoverageCounts.value = { linked: 0, candidate: 0, needs_cluster: 0, watch: 0, ignored: 0 }
  }
}

async function loadRefreshRequests() {
  refreshRequestError.value = ''
  try {
    const response = await listTopicClusterRefreshRequests()
    refreshRequests.value = response.data?.items || []
  } catch (err) {
    refreshRequestError.value = err?.message || '请求记录加载失败'
  }
}

async function submitCreate() {
  createError.value = ''
  if (!createForm.value.title.trim()) {
    createError.value = '标题不能为空'
    return
  }
  savingCreate.value = true
  try {
    const response = await createTopicCluster({
      title: createForm.value.title.trim(),
      description: createForm.value.description,
      status: createForm.value.status,
      strategic_relevance: createForm.value.strategic_relevance,
    })
    const clusterId = response.data?.cluster?.cluster_id
    if (clusterId) router.push(`/workspace/topic-clusters/${clusterId}`)
  } catch (err) {
    createError.value = err?.message || '创建失败'
  } finally {
    savingCreate.value = false
  }
}

async function requestRefresh() {
  creatingRefreshRequest.value = true
  refreshRequestError.value = ''
  refreshRequestMessage.value = ''
  try {
    await createTopicClusterRefreshRequest({
      scope: 'all',
      inputs: {
        include_wiki_topics: true,
        include_kfc_themes: true,
        include_kfc_concepts: false,
        include_research_projects: false,
      },
    })
    refreshRequestMessage.value = '已创建主题簇建议请求'
    await loadRefreshRequests()
  } catch (err) {
    refreshRequestError.value = err?.message || '创建主题簇建议请求失败'
  } finally {
    creatingRefreshRequest.value = false
  }
}

onMounted(() => {
  loadClusters()
  loadTopicCoverage()
  loadRefreshRequests()
})
</script>

<style scoped>
.topic-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.page-head {
  display: flex;
  align-items: flex-start;
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
  max-width: 760px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.summary {
  min-width: 120px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.summary-number {
  font-size: 26px;
  font-weight: 800;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.primary-btn,
.secondary-btn {
  border-radius: 8px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
}
.secondary-link {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--text-secondary);
  padding: 8px 12px;
  font-weight: 700;
  text-decoration: none;
}
.primary-btn {
  border: 1px solid var(--kfc-primary, var(--accent-primary));
  background: var(--kfc-primary, var(--accent-primary));
  color: white;
}
.secondary-btn {
  border: 1px solid var(--kfc-border, var(--border-default));
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--text-secondary);
}
.primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.safety-copy {
  margin: -8px 0 0;
  color: var(--text-muted);
  font-size: 13px;
}
.coverage-panel {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  background: var(--kfc-surface, var(--bg-surface));
  padding: 16px;
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(420px, 1.6fr);
  gap: 16px;
  align-items: center;
}
.coverage-panel h2,
.coverage-panel p {
  margin: 0;
}
.coverage-panel p {
  margin-top: 6px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.coverage-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(90px, 1fr));
  gap: 8px;
}
.coverage-stat {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 10px 10px 10px 13px;
  text-decoration: none;
  color: var(--text-secondary);
  background: var(--kfc-surface, var(--bg-surface));
}
.coverage-stat::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--state-readonly);
}
.coverage-stat:nth-child(1)::before {
  background: var(--state-linked);
}
.coverage-stat:nth-child(2)::before,
.coverage-stat:nth-child(3)::before {
  background: var(--state-candidate);
}
.coverage-stat:nth-child(5) {
  opacity: 0.78;
}
.coverage-stat:nth-child(5)::before {
  background: var(--state-ignored);
}
.coverage-stat strong {
  display: block;
  font-size: 20px;
  color: var(--text-primary);
}
.coverage-stat span {
  font-size: 12px;
}
.edit-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 160px 160px;
  gap: 12px;
}
.edit-panel label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.edit-panel input,
.edit-panel select,
.edit-panel textarea {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font: inherit;
}
.full-field {
  width: 100%;
}
.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.inline-error {
  color: #8c1d18;
  font-size: 13px;
}
.inline-success {
  color: #136f36;
  font-size: 13px;
}
.requests-panel {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 16px;
  background: var(--kfc-surface, var(--bg-surface));
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.panel-head h2 {
  margin: 0;
  font-size: 16px;
}
.empty-note {
  color: var(--text-muted);
  font-size: 13px;
}
.request-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.request-row {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.request-id {
  font-weight: 700;
}
.request-meta,
.rule-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
}
.rule-badges span {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--accent-primary-hover);
}
.filter-btn {
  border: 1px solid var(--kfc-border, var(--border-default));
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
}
.filter-btn.active {
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  background: var(--kfc-surface, var(--bg-surface));
  box-shadow: inset 0 -3px 0 var(--kfc-primary, var(--accent-primary));
  font-weight: 700;
}
.cluster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 14px;
}
.state-card,
.warning-bar {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-surface);
  color: var(--text-secondary);
}
.warning-bar {
  border-color: rgba(192, 86, 33, 0.32);
  background: rgba(192, 86, 33, 0.08);
  color: var(--state-warning);
}
.error-card {
  border-color: #f2b8b5;
  background: #fff1f0;
  color: #8c1d18;
}
.error-title {
  font-weight: 800;
  margin-bottom: 4px;
}
@media (max-width: 720px) {
  .page-head {
    flex-direction: column;
  }
  .summary {
    width: 100%;
  }
  .coverage-panel,
  .coverage-stats {
    grid-template-columns: 1fr;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
