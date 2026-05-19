<template>
  <AppShell :crumbs="crumbs">
    <section class="wiki-topic-detail">
      <div v-if="loading" class="state-card">加载中...</div>
      <div v-else-if="error" class="state-card error-card">{{ error }}</div>
      <template v-else-if="topic">
        <router-link class="back-link" to="/workspace/wiki-topics">返回主题总览</router-link>
        <header class="detail-head">
          <div>
            <div class="section-badge">WIKI 主题</div>
            <h1>{{ topic.title || topic.topic_id }}</h1>
            <div class="meta-line">
              <span>topic_id: {{ topic.topic_id }}</span>
              <span v-if="topic.last_processed_at">更新 {{ shortDate(topic.last_processed_at) }}</span>
            </div>
          </div>
          <div class="count-grid">
            <div><strong>{{ topic.article_count || articles.length }}</strong><span>文章</span></div>
            <div><strong>{{ topic.completed_count || articles.length }}</strong><span>已完成</span></div>
            <div><strong>{{ topic.needs_review_count || 0 }}</strong><span>待复核</span></div>
            <div><strong>{{ topic.cluster_ids?.length || 0 }}</strong><span>主题簇</span></div>
          </div>
        </header>

        <section class="topic-card">
          <div class="panel-head">
            <h2>主题摘要</h2>
            <div class="cluster-actions">
              <router-link
                v-for="cluster in topic.cluster_links || []"
                :key="cluster.cluster_id"
                class="action-link"
                :to="`/workspace/topic-clusters/${cluster.cluster_id}`"
                target="_blank"
                rel="noopener noreferrer"
              >
                打开主题簇
              </router-link>
            </div>
          </div>
          <p>{{ topicSummary }}</p>
          <div class="concept-list">
            <button
              v-for="concept in topicConcepts"
              :key="concept"
              :class="{ active: activeConcept === concept }"
              @click="activeConcept = activeConcept === concept ? '' : concept"
            >
              {{ concept }}
            </button>
          </div>
        </section>

        <section class="topic-card coverage-panel">
          <div class="panel-head">
            <h2>主题簇覆盖</h2>
            <span class="coverage-pill" :class="coverageStatus">{{ coverageLabel(coverageStatus) }}</span>
          </div>
          <p>{{ coverage?.recommendation || '该主题会保留在 主题簇覆盖 队列中，等待人工确认。' }}</p>
          <div class="coverage-meta">
            <span>当前状态：{{ coverageLabel(coverageStatus) }}</span>
            <span v-if="coverage?.reason">{{ coverage.reason }}</span>
            <span v-if="coverageMessage">{{ coverageMessage }}</span>
          </div>

          <div v-if="coverage?.linked_clusters?.length" class="candidate-list">
            <article v-for="cluster in coverage.linked_clusters" :key="cluster.cluster_id" class="candidate-row linked">
              <div>
                <strong>{{ cluster.title || cluster.cluster_id }}</strong>
                <p>正式关联 · {{ cluster.role || 'primary' }}</p>
              </div>
              <router-link
                class="action-link"
                :to="`/workspace/topic-clusters/${cluster.cluster_id}`"
                target="_blank"
                rel="noopener noreferrer"
              >
                打开主题簇
              </router-link>
            </article>
          </div>

          <div v-else-if="coverage?.candidate_clusters?.length" class="candidate-list">
            <article v-for="cluster in coverage.candidate_clusters" :key="cluster.cluster_id" class="candidate-row">
              <div>
                <strong>{{ cluster.title || cluster.cluster_id }}</strong>
                <p>{{ cluster.reason || '系统候选，等待人工确认。' }}</p>
                <div class="article-meta">
                  <span>{{ cluster.confidence_label || 'medium' }}</span>
                  <span v-if="cluster.matched_terms?.length">命中：{{ cluster.matched_terms.join('、') }}</span>
                </div>
              </div>
              <button class="action-link button-link" :disabled="coverageSaving" @click="confirmLink(cluster.cluster_id)">
                关联到此主题簇
              </button>
            </article>
          </div>
          <div v-else class="empty-note">暂无候选主题簇。可以先观察，或提出新主题簇建议。</div>

          <div class="manual-link-row">
            <label>
              <span>关联到已有主题簇</span>
              <select v-model="selectedClusterId">
                <option value="">选择主题簇</option>
                <option v-for="cluster in allClusters" :key="cluster.cluster_id" :value="cluster.cluster_id">
                  {{ cluster.title || cluster.cluster_id }}
                </option>
              </select>
            </label>
            <button class="action-link button-link" :disabled="coverageSaving || !selectedClusterId" @click="confirmLink(selectedClusterId)">
              确认关联
            </button>
          </div>

          <div class="coverage-actions">
            <button class="action-link button-link" :disabled="coverageSaving" @click="requestProposal">
              提出新主题簇建议
            </button>
            <button class="action-link button-link" :disabled="coverageSaving" @click="setCoverageOverride('watch')">
              暂时观察
            </button>
            <button class="action-link button-link" :disabled="coverageSaving" @click="setCoverageOverride('needs_cluster')">
              标记待归集
            </button>
            <button class="action-link button-link" :disabled="coverageSaving" @click="setCoverageOverride('ignored')">
              标记不需要主题簇
            </button>
          </div>
        </section>

        <section class="topic-card">
          <div class="panel-head">
            <h2>主题下文章</h2>
            <span>{{ filteredArticles.length }} / {{ articles.length }}</span>
          </div>
          <div v-if="!filteredArticles.length" class="empty-note">暂无文章。</div>
          <article v-for="article in filteredArticles" :key="article.candidate_id || article.source_id" class="article-row">
            <div>
              <h3>{{ article.title }}</h3>
              <div class="article-meta">
                <span>{{ article.source_type || 'markdown' }}</span>
                <span>{{ shortDate(article.processed_at) }}</span>
                <span>{{ article.status }}</span>
              </div>
              <p v-if="article.digest_summary">{{ article.digest_summary }}</p>
              <p class="belonging-line">
                主题命中：{{ topic.topic_id }}
                <template v-if="topic.cluster_links?.length">
                  · 主题簇：{{ topic.cluster_links.map((cluster) => cluster.title || cluster.cluster_id).join('、') }}
                </template>
              </p>
              <div class="concept-list small">
                <button v-for="concept in article.top_concepts || []" :key="concept" @click="activeConcept = concept">
                  {{ concept }}
                </button>
              </div>
            </div>
            <div class="article-actions">
              <a v-if="article.source_url" class="action-link" :href="article.source_url" target="_blank" rel="noopener noreferrer">来源</a>
              <router-link
                class="action-link"
                :to="wikiIntakeRoute(article)"
                target="_blank"
                rel="noopener noreferrer"
              >
                回到素材加工台
              </router-link>
              <a v-if="article.markdown_path" class="action-link" :href="pathHref(article.markdown_path)" target="_blank" rel="noopener noreferrer">来源文件</a>
            </div>
          </article>
        </section>

        <section class="topic-card">
          <h2>主题治理建议</h2>
          <p>当前阶段只展示主题沉淀和主题簇关联。拆分、合并或升级研究项目需要后续显式建议 / 草稿流程。</p>
        </section>
      </template>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import {
  getWikiTopicArticles,
  linkWikiTopicToCluster,
  listTopicClusters,
  requestWikiTopicClusterProposal,
  setWikiTopicClusterCoverageOverride,
} from '../data/dataClient'

const route = useRoute()
const topic = ref(null)
const articles = ref([])
const loading = ref(false)
const error = ref('')
const activeConcept = ref('')
const allClusters = ref([])
const selectedClusterId = ref('')
const coverageSaving = ref(false)
const coverageMessage = ref('')

const crumbs = computed(() => [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '主题总览', to: '/workspace/wiki-topics' },
  { label: topic.value?.title || route.params.topicId },
])

const topicConcepts = computed(() => [
  ...new Set([
    ...(topic.value?.top_concepts || []),
    ...articles.value.flatMap((article) => article.top_concepts || []),
  ]),
].slice(0, 16))

const topicSummary = computed(() => {
  const withSummary = articles.value.find((article) => article.digest_summary)
  if (withSummary) return withSummary.digest_summary
  if (topicConcepts.value.length) return `该主题聚合 ${topicConcepts.value.slice(0, 5).join('、')} 等概念下的已预消化文章。`
  return '该主题已形成文章沉淀，后续可在人工确认后进入更正式的研究治理流程。'
})

const filteredArticles = computed(() => {
  if (!activeConcept.value) return articles.value
  return articles.value.filter((article) => (article.top_concepts || []).includes(activeConcept.value))
})

const coverage = computed(() => topic.value?.cluster_coverage || null)
const coverageStatus = computed(() => coverage.value?.status || (topic.value?.cluster_ids?.length ? 'linked' : 'watch'))

function shortDate(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function pathHref(path) {
  return `file://${path}`
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

function wikiIntakeRoute(article) {
  const candidateId = article?.candidate_id || article?.source_id || ''
  return candidateId ? `/workspace/wiki-intake?candidate=${encodeURIComponent(candidateId)}` : '/workspace/wiki-intake'
}

async function loadDetail() {
  loading.value = true
  error.value = ''
  try {
    const response = await getWikiTopicArticles(route.params.topicId)
    const data = response.data || {}
    topic.value = data.topic || null
    articles.value = data.articles || []
    selectedClusterId.value = topic.value?.cluster_coverage?.candidate_clusters?.[0]?.cluster_id || ''
  } catch (err) {
    topic.value = null
    articles.value = []
    error.value = err?.message || '主题详情加载失败'
  } finally {
    loading.value = false
  }
}

async function loadClusters() {
  try {
    const response = await listTopicClusters({ includeCounts: true })
    allClusters.value = response.data?.items || []
  } catch {
    allClusters.value = []
  }
}

function applyCoverageResult(result) {
  const nextCoverage = result?.coverage || result?.data?.coverage
  if (!nextCoverage || !topic.value) return
  topic.value = {
    ...topic.value,
    cluster_coverage: nextCoverage,
    cluster_coverage_status: nextCoverage.status,
    cluster_ids: nextCoverage.linked_clusters?.map((cluster) => cluster.cluster_id) || topic.value.cluster_ids || [],
    cluster_links: nextCoverage.linked_clusters || topic.value.cluster_links || [],
  }
  selectedClusterId.value = nextCoverage.candidate_clusters?.[0]?.cluster_id || ''
}

async function confirmLink(clusterId) {
  if (!clusterId) return
  coverageSaving.value = true
  coverageMessage.value = ''
  try {
    const cluster = allClusters.value.find((item) => item.cluster_id === clusterId)
    const response = await linkWikiTopicToCluster(topic.value.topic_id, {
      cluster_id: clusterId,
      cluster_title: cluster?.title || clusterId,
      rationale: 'Human confirmed from Wiki Topic 主题簇覆盖 panel.',
    })
    applyCoverageResult(response.data)
    coverageMessage.value = '已人工关联到 主题簇'
  } catch (err) {
    coverageMessage.value = err?.message || '关联失败'
  } finally {
    coverageSaving.value = false
  }
}

async function setCoverageOverride(status) {
  coverageSaving.value = true
  coverageMessage.value = ''
  try {
    const response = await setWikiTopicClusterCoverageOverride(topic.value.topic_id, { status, note: 'Updated from 主题簇覆盖 panel.' })
    applyCoverageResult(response.data)
    coverageMessage.value = '覆盖状态已更新'
  } catch (err) {
    coverageMessage.value = err?.message || '状态更新失败'
  } finally {
    coverageSaving.value = false
  }
}

async function requestProposal() {
  coverageSaving.value = true
  coverageMessage.value = ''
  try {
    const response = await requestWikiTopicClusterProposal(topic.value.topic_id, {
      suggested_title: topic.value.title || topic.value.topic_id,
      rationale: 'Human requested a new topic cluster proposal from Wiki Topic detail.',
    })
    applyCoverageResult(response.data)
    coverageMessage.value = `已记录新主题簇建议请求：${response.data?.request?.request_id || ''}`
  } catch (err) {
    coverageMessage.value = err?.message || '建议请求创建失败'
  } finally {
    coverageSaving.value = false
  }
}

onMounted(() => {
  loadDetail()
  loadClusters()
})
watch(() => route.params.topicId, loadDetail)
</script>

<style scoped>
.wiki-topic-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.back-link,
.action-link {
  width: fit-content;
  color: var(--accent-primary-hover);
  text-decoration: none;
  font-weight: 700;
  font-size: 13px;
}
.button-link {
  cursor: pointer;
  font: inherit;
  background: var(--bg-surface);
}
.action-link {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 7px 10px;
}
.detail-head {
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
.meta-line,
.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
}
.belonging-line {
  color: var(--text-muted);
  font-size: 12px;
  margin: 8px 0;
}
.count-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(90px, 1fr));
  gap: 8px;
}
.count-grid div,
.topic-card,
.state-card {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  background: var(--kfc-surface, var(--bg-surface));
}
.count-grid div {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.count-grid strong {
  font-size: 22px;
}
.count-grid span,
.empty-note {
  color: var(--text-muted);
  font-size: 12px;
}
.topic-card {
  padding: 16px;
}
.coverage-panel {
  border-color: var(--kfc-border, var(--border-default));
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
h2,
h3,
.topic-card p {
  margin: 0;
}
.topic-card p {
  margin-top: 8px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.cluster-actions,
.article-actions,
.coverage-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.coverage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
}
.coverage-pill {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 800;
}
.coverage-pill.linked {
  color: #ffffff;
  background: var(--state-linked);
  border-color: var(--state-linked);
}
.coverage-pill.candidate,
.coverage-pill.needs_cluster {
  color: #ffffff;
  background: var(--state-candidate);
  border-color: var(--state-candidate);
}
.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.candidate-row {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 12px 12px 12px 15px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  background: var(--kfc-surface, var(--bg-surface));
}
.candidate-row::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--state-candidate);
}
.candidate-row.linked {
  background: var(--kfc-surface, var(--bg-surface));
}
.candidate-row.linked::before {
  background: var(--state-linked);
}
.manual-link-row {
  display: flex;
  align-items: end;
  gap: 10px;
  margin-top: 12px;
}
.manual-link-row label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}
.manual-link-row select {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--text-primary);
}
.coverage-actions {
  margin-top: 12px;
}
.concept-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}
.concept-list button {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 999px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-secondary);
  padding: 3px 9px;
  cursor: pointer;
}
.concept-list button.active {
  color: var(--accent-primary-hover);
  background: var(--bg-selected);
  font-weight: 700;
}
.concept-list.small {
  margin-top: 8px;
}
.article-row {
  border-top: 1px solid var(--border-default);
  padding: 14px 0;
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto;
  gap: 16px;
}
.article-row:first-of-type {
  border-top: none;
}
.article-row h3 {
  font-size: 16px;
}
.article-actions {
  justify-content: flex-end;
}
.state-card {
  padding: 16px;
  color: var(--text-secondary);
}
.error-card {
  border-color: #f2b8b5;
  background: #fff1f0;
  color: #8c1d18;
}
@media (max-width: 980px) {
  .detail-head,
  .article-row {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
  .count-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
