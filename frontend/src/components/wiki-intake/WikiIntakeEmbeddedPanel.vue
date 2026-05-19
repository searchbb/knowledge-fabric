<template>
  <section class="embedded-intake-panel" aria-label="Wiki Intake embedded detail">
    <div class="embedded-intake-toolbar">
      <div>
        <span class="embedded-eyebrow">WIKI INTAKE</span>
        <strong>素材加工台详情</strong>
      </div>
      <RouterLink
        v-if="candidateId"
        class="embedded-link"
        :to="fullIntakeRoute"
        target="_blank"
        rel="noopener noreferrer"
      >
        完整页面
      </RouterLink>
    </div>

    <div v-if="loading" class="embedded-state">Intake 详情加载中...</div>
    <div v-else-if="error" class="embedded-state error">{{ error }}</div>
    <div v-else-if="!detail" class="embedded-state">这篇文章没有可用的 Intake 记录。</div>
    <template v-else>
      <div class="embedded-detail-head">
        <div>
          <span class="embedded-eyebrow">{{ detail.candidate.source_type || 'markdown' }}</span>
          <h4>{{ detail.candidate.title }}</h4>
        </div>
        <span :class="['status-pill', `status-${detail.candidate.status}`]">
          {{ statusLabel(detail.candidate.status) }}
        </span>
      </div>

      <nav class="embedded-tabs" aria-label="素材详情视图">
        <button
          v-for="tab in detailTabs"
          :key="tab.value"
          :class="{ active: activeTab === tab.value }"
          type="button"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div v-if="isCompleted(detail.candidate)" class="embedded-block processed">
        <div class="block-title">已进 Wiki</div>
        <dl class="detail-grid">
          <div>
            <dt>处理时间</dt>
            <dd>{{ detail.candidate.auto_processed?.processed_at || '已完成' }}</dd>
          </div>
          <div>
            <dt>进入主题</dt>
            <dd>{{ detail.candidate.auto_processed?.topic_id || selectedTopicId(detail) || '未记录' }}</dd>
          </div>
          <div>
            <dt>编译运行</dt>
            <dd>{{ detail.candidate.auto_processed?.compile_run_id || '未记录' }}</dd>
          </div>
          <div>
            <dt>状态来源</dt>
            <dd>{{ detail.candidate.auto_processed?.backfilled_from ? '旧 intake 状态回填' : 'KFC sidecar' }}</dd>
          </div>
        </dl>
        <div class="artifact-links">
          <a v-if="detail.candidate.auto_processed?.raw_article_path" :href="pathHref(detail.candidate.auto_processed.raw_article_path)">原文入库文件</a>
          <a v-if="detail.candidate.auto_processed?.verified_digest_md_path" :href="pathHref(detail.candidate.auto_processed.verified_digest_md_path)">验证摘要</a>
          <a v-if="detail.candidate.auto_processed?.sources_path" :href="pathHref(detail.candidate.auto_processed.sources_path)">来源清单</a>
        </div>
      </div>

      <div class="embedded-block topic-context">
        <div class="block-title">所属主题上下文</div>
        <template v-if="detail.topic_context">
          <dl class="detail-grid">
            <div>
              <dt>Wiki 主题</dt>
              <dd>{{ detail.topic_context.title || detail.topic_context.topic_id }}</dd>
            </div>
            <div>
              <dt>topic_id</dt>
              <dd>{{ detail.topic_context.topic_id }}</dd>
            </div>
            <div>
              <dt>当前主题文章数</dt>
              <dd>{{ detail.topic_context.article_count || 0 }} 篇</dd>
            </div>
            <div>
              <dt>待复核文章</dt>
              <dd>{{ detail.topic_context.needs_review_count || 0 }}</dd>
            </div>
          </dl>
          <div class="context-links">
            <span>所属主题簇：</span>
            <RouterLink
              v-for="cluster in detail.topic_context.cluster_links || []"
              :key="cluster.cluster_id"
              class="embedded-link"
              :to="`/workspace/topic-clusters/${cluster.cluster_id}`"
            >
              {{ cluster.title || cluster.cluster_id }}
            </RouterLink>
            <span v-if="!detail.topic_context.cluster_links?.length" class="muted">暂无</span>
          </div>
        </template>
        <div v-else class="muted">暂无主题上下文。</div>
      </div>

      <div v-show="activeTab === 'reader'" class="tab-panel reader-panel">
        <MarkdownArticleViewer
          :markdown="detail.content || ''"
          :candidate-id="detail.candidate.candidate_id"
          :source-file-path="detail.candidate.source_file_path"
        />
      </div>

      <div v-show="activeTab === 'source'" class="tab-panel source-panel">
        <div class="block-title">Markdown 原文</div>
        <pre>{{ detail.content || '无内容' }}</pre>
      </div>

      <div v-show="activeTab === 'digest'" class="tab-panel digest-panel">
        <div class="block-title">预消化结果</div>
        <template v-if="hasPredigestResult(detail)">
          <div v-if="detail.decision_digest?.markdown" class="digest-markdown">
            <MarkdownArticleViewer
              :markdown="detail.decision_digest.markdown"
              :candidate-id="detail.candidate.candidate_id"
              :source-file-path="detail.decision_digest.markdown_path || detail.candidate.source_file_path"
            />
          </div>
          <div v-if="detail.decision_digest?.payload" class="json-block">
            <div class="mini-label">decision_digest_v1</div>
            <pre>{{ prettyJson(detail.decision_digest.payload) }}</pre>
          </div>
          <div v-if="detail.candidate.latest_processing" class="json-block">
            <div class="mini-label">latest_processing</div>
            <pre>{{ prettyJson(detail.candidate.latest_processing) }}</pre>
          </div>
          <div v-if="detail.candidate.auto_processed" class="json-block">
            <div class="mini-label">auto_processed</div>
            <pre>{{ prettyJson(detail.candidate.auto_processed) }}</pre>
          </div>
        </template>
        <div v-else class="embedded-state">暂无预消化结果。</div>
      </div>

      <div v-show="activeTab === 'metadata'" class="tab-panel metadata-panel">
        <div class="block-title">元数据</div>
        <dl class="detail-grid metadata-grid">
          <div>
            <dt>candidate_id</dt>
            <dd>{{ detail.candidate.candidate_id || '未记录' }}</dd>
          </div>
          <div>
            <dt>source_id</dt>
            <dd>{{ detail.candidate.source_id || detail.candidate.candidate_id || '未记录' }}</dd>
          </div>
          <div>
            <dt>source_file_path</dt>
            <dd>{{ detail.candidate.source_file_path || '未记录' }}</dd>
          </div>
          <div>
            <dt>topic_id</dt>
            <dd>{{ selectedTopicId(detail) || '未识别' }}</dd>
          </div>
          <div>
            <dt>status</dt>
            <dd>{{ statusLabel(detail.candidate.status) }}</dd>
          </div>
          <div>
            <dt>content_hash</dt>
            <dd>{{ detail.candidate.content_hash || '未记录' }}</dd>
          </div>
          <div>
            <dt>duplicate_status</dt>
            <dd>{{ detail.candidate.duplicate_status || 'none' }}</dd>
          </div>
          <div>
            <dt>guessed_topics</dt>
            <dd>{{ topicSummary(detail.candidate.guessed_topics) }}</dd>
          </div>
        </dl>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import MarkdownArticleViewer from './MarkdownArticleViewer.vue'
import { getWikiIntakeCandidate } from '../../data/dataClient'

const props = defineProps({
  candidateId: {
    type: String,
    default: '',
  },
})

const detailTabs = [
  { value: 'reader', label: '阅读视图' },
  { value: 'source', label: 'Markdown 原文' },
  { value: 'digest', label: '预消化结果' },
  { value: 'metadata', label: '元数据' },
]

const statusText = {
  pending: '待处理',
  accepted: '已接收',
  needs_human_review: '需复核',
  completed: '已完成',
  deferred: '已暂缓',
  rejected: '已拒绝',
  duplicate: '重复',
}

const activeTab = ref('reader')
const detail = ref(null)
const loading = ref(false)
const error = ref('')

const fullIntakeRoute = computed(() => (
  props.candidateId ? `/workspace/wiki-intake?candidate=${encodeURIComponent(props.candidateId)}` : '/workspace/wiki-intake'
))

function statusLabel(status) {
  return statusText[status] || status || '待处理'
}

function isCompleted(candidate) {
  return candidate?.status === 'completed'
}

function pathHref(path) {
  return `file://${path}`
}

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function topicSummary(topics) {
  if (!Array.isArray(topics) || !topics.length) return '未识别'
  return topics.map((item) => item.topic_id || item).join(', ')
}

function selectedTopicId(item) {
  const candidate = item?.candidate || {}
  if (candidate.auto_processed?.topic_id) return candidate.auto_processed.topic_id
  if (item?.topic_context?.topic_id) return item.topic_context.topic_id
  const firstGuess = candidate.guessed_topics?.[0]
  return typeof firstGuess === 'string' ? firstGuess : firstGuess?.topic_id || ''
}

function hasPredigestResult(item) {
  const candidate = item?.candidate || {}
  return Boolean(
    item?.decision_digest?.markdown
      || item?.decision_digest?.payload
      || candidate.latest_processing
      || candidate.auto_processed,
  )
}

async function loadCandidate(candidateId) {
  detail.value = null
  error.value = ''
  activeTab.value = 'reader'
  if (!candidateId) return
  loading.value = true
  try {
    const response = await getWikiIntakeCandidate(candidateId)
    detail.value = response?.data || null
  } catch (err) {
    error.value = err?.response?.data?.error || err?.message || 'Intake 详情加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.candidateId, loadCandidate, { immediate: true })
</script>

<style scoped>
.embedded-intake-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.embedded-intake-toolbar,
.embedded-detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.embedded-intake-toolbar strong {
  display: block;
  margin-top: 2px;
}
.embedded-eyebrow {
  font-size: 11px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
}
.embedded-link,
.artifact-links a {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--accent-primary-hover);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 8px;
  text-decoration: none;
  background: var(--bg-surface);
}
.embedded-detail-head h4 {
  margin: 4px 0 0;
  font-size: 15px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.embedded-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  border-bottom: 1px solid var(--border-default);
}
.embedded-tabs button {
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 8px 6px 7px;
  font-size: 12px;
  font-weight: 800;
}
.embedded-tabs button.active {
  color: var(--accent-primary-hover);
  border-bottom-color: var(--accent-primary);
}
.embedded-state {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  color: var(--text-secondary);
  padding: 12px;
}
.embedded-state.error {
  color: #cf222e;
  border-color: #ffb4ab;
}
.status-pill {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 800;
  background: var(--bg-muted);
  color: var(--text-secondary);
}
.status-accepted,
.status-completed { color: #1a7f37; background: #dafbe1; }
.status-rejected { color: #cf222e; background: #ffebe9; }
.status-deferred,
.status-needs_human_review,
.status-duplicate { color: #9a6700; background: #fff8c5; }
.embedded-block {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-muted);
}
.processed {
  background: var(--bg-surface);
}
.block-title {
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 8px;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}
dt {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 800;
}
dd {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.artifact-links,
.context-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}
.context-links {
  color: var(--text-secondary);
  font-size: 12px;
}
.muted,
.mini-label {
  color: var(--text-muted);
  font-size: 12px;
}
.tab-panel {
  min-width: 0;
}
.reader-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  max-height: min(820px, calc(100vh - 300px));
  min-height: clamp(320px, calc(100vh - 360px), 620px);
  overflow: auto;
  overscroll-behavior: contain;
  padding: 18px;
}
.source-panel pre,
.json-block pre {
  overflow: auto;
  white-space: pre-wrap;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  background: var(--bg-muted);
}
.source-panel pre {
  max-height: min(820px, calc(100vh - 300px));
  min-height: clamp(320px, calc(100vh - 360px), 620px);
}
.digest-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.digest-markdown {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  max-height: min(760px, calc(100vh - 340px));
  overflow: auto;
  padding: 18px;
  background: var(--bg-surface);
}
.json-block pre {
  max-height: 360px;
}
@media (max-width: 720px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
  .reader-panel,
  .source-panel pre,
  .digest-markdown {
    max-height: none;
    min-height: 0;
  }
}
</style>
