<template>
  <AppShell :crumbs="crumbs">
    <section class="wiki-intake-page">
      <header class="page-head">
        <div>
          <div class="section-badge">WIKI INTAKE</div>
          <h1>素材加工台</h1>
          <p>从唯一外部入口 Clippings 只读扫描 Markdown，自动调用 GPT 预消化后进入 Wiki intake 状态。</p>
        </div>
        <div class="summary">
          <span class="summary-number">{{ stats.total || candidates.length }}</span>
          <span>候选</span>
        </div>
      </header>

      <div class="toolbar">
        <button class="primary-btn" :disabled="scanning" @click="scan">
          {{ scanning ? '扫描中...' : '扫描 Clippings' }}
        </button>
        <button class="primary-btn" :disabled="processing" @click="processNext">
          {{ processing ? '处理中...' : '手动处理下一条' }}
        </button>
        <button class="secondary-btn" :disabled="loading" @click="loadCandidates">刷新</button>
        <span class="path-chip">{{ config?.default_adapter || 'chatgpt_app_attachment' }}</span>
      </div>

      <p class="safety-copy">
        KFC 自动管道只读 Clippings 原文，默认用 GPT 生成预消化和 verified digest，写入 KFC sidecar/wiki hub；不自动创建 研究项目。
      </p>

      <div v-if="message" class="inline-message">{{ message }}</div>
      <div v-if="error" class="state-card error-card">{{ error }}</div>

      <div class="intake-layout">
        <aside class="filters-panel intake-status-pane">
          <button
            v-for="option in filterOptions"
            :key="option.value"
            :class="['filter-btn', { active: statusFilter === option.value }]"
            @click="statusFilter = option.value"
          >
            <span>{{ option.label }}</span>
            <strong>{{ countFor(option.value) }}</strong>
          </button>
        </aside>

        <section ref="candidateListRef" class="candidate-list intake-list-pane">
          <div v-if="loading" class="state-card">加载中...</div>
          <div v-else-if="!filteredCandidates.length" class="state-card">当前筛选下没有素材。</div>
          <template v-else>
            <button
              v-for="candidate in filteredCandidates"
              :key="candidate.candidate_id"
              :ref="(el) => setCandidateRowRef(candidate.candidate_id, el)"
              :class="['candidate-row', { selected: selectedId === candidate.candidate_id }]"
              @click="selectCandidate(candidate.candidate_id)"
            >
              <div class="row-main">
                <div class="row-title">{{ candidate.title }}</div>
                <div class="row-path">{{ candidate.source_relative_path || candidate.source_file_path }}</div>
              </div>
              <div class="row-meta">
                <span :class="['status-pill', `status-${candidate.status}`]">{{ statusLabel(candidate.status) }}</span>
                <span>{{ formatSize(candidate.size_bytes) }}</span>
                <span v-if="candidate.has_digest">digest</span>
                <span v-if="candidate.has_processing_result">处理结果</span>
              </div>
              <p v-if="candidate.excerpt" class="row-excerpt">{{ candidate.excerpt }}</p>
            </button>
          </template>
        </section>

        <aside ref="detailPanelRef" class="detail-panel intake-detail-pane">
          <template v-if="selectedDetail">
            <div class="detail-head">
              <div>
                <div class="detail-eyebrow">{{ selectedDetail.candidate.source_type || 'markdown' }}</div>
                <h2>{{ selectedDetail.candidate.title }}</h2>
              </div>
              <span :class="['status-pill', `status-${selectedDetail.candidate.status}`]">
                {{ statusLabel(selectedDetail.candidate.status) }}
              </span>
            </div>

            <nav class="detail-tabs" aria-label="素材详情视图">
              <button
                v-for="tab in detailTabs"
                :key="tab.value"
                :class="['detail-tab-btn', { active: activeDetailTab === tab.value }]"
                type="button"
                @click="activeDetailTab = tab.value"
              >
                {{ tab.label }}
              </button>
            </nav>

            <div v-if="isCompleted(selectedDetail.candidate) && activeDetailTab !== 'digest'" class="processed-panel">
              <div class="block-title">已进 Wiki</div>
              <dl class="processed-grid">
                <div>
                  <dt>处理时间</dt>
                  <dd>{{ selectedDetail.candidate.auto_processed?.processed_at || '已完成' }}</dd>
                </div>
                <div>
                  <dt>进入主题</dt>
                  <dd>{{ selectedDetail.candidate.auto_processed?.topic_id || '未记录' }}</dd>
                </div>
                <div>
                  <dt>编译运行</dt>
                  <dd>{{ selectedDetail.candidate.auto_processed?.compile_run_id || '未记录' }}</dd>
                </div>
                <div>
                  <dt>状态来源</dt>
                  <dd>{{ selectedDetail.candidate.auto_processed?.backfilled_from ? '旧 intake 状态回填' : 'KFC sidecar' }}</dd>
                </div>
              </dl>
              <div class="artifact-links">
                <a v-if="selectedDetail.candidate.auto_processed?.raw_article_path" :href="pathHref(selectedDetail.candidate.auto_processed.raw_article_path)">原文入库文件</a>
                <a v-if="selectedDetail.candidate.auto_processed?.verified_digest_md_path" :href="pathHref(selectedDetail.candidate.auto_processed.verified_digest_md_path)">验证摘要</a>
                <a v-if="selectedDetail.candidate.auto_processed?.sources_path" :href="pathHref(selectedDetail.candidate.auto_processed.sources_path)">来源清单</a>
              </div>
            </div>

            <div v-if="activeDetailTab !== 'digest'" class="topic-context-panel">
              <div class="block-title">所属主题上下文</div>
              <template v-if="selectedDetail.topic_context">
                <dl class="processed-grid">
                  <div>
                    <dt>Wiki 主题</dt>
                    <dd>{{ selectedDetail.topic_context.title || selectedDetail.topic_context.topic_id }}</dd>
                  </div>
                  <div>
                    <dt>topic_id</dt>
                    <dd>{{ selectedDetail.topic_context.topic_id }}</dd>
                  </div>
                  <div>
                    <dt>当前主题文章数</dt>
                    <dd>{{ selectedDetail.topic_context.article_count || 0 }} 篇</dd>
                  </div>
                  <div>
                    <dt>待复核文章</dt>
                    <dd>{{ selectedDetail.topic_context.needs_review_count || 0 }}</dd>
                  </div>
                </dl>
                <div class="context-clusters">
                  <span>所属主题簇：</span>
                  <router-link
                    v-for="cluster in selectedDetail.topic_context.cluster_links || []"
                    :key="cluster.cluster_id"
                    class="context-link"
                    :to="`/workspace/topic-clusters/${cluster.cluster_id}`"
                  >
                    {{ cluster.title || cluster.cluster_id }}
                  </router-link>
                  <span v-if="!selectedDetail.topic_context.cluster_links?.length" class="muted">暂无</span>
                </div>
                <div v-if="selectedDetail.topic_context.recent_same_topic_articles?.length" class="recent-list">
                  <div class="mini-label">最近同主题文章</div>
                  <ul>
                    <li v-for="article in selectedDetail.topic_context.recent_same_topic_articles.slice(0, 3)" :key="article.candidate_id || article.source_id">
                      {{ article.title }}
                    </li>
                  </ul>
                </div>
                <div class="context-actions">
                  <router-link class="context-link" :to="`/workspace/wiki-topics/${selectedDetail.topic_context.topic_id}`">打开主题</router-link>
                  <router-link
                    v-if="selectedDetail.topic_context.cluster_ids?.length"
                    class="context-link"
                    :to="`/workspace/topic-clusters/${selectedDetail.topic_context.cluster_ids[0]}`"
                  >
                    打开主题簇
                  </router-link>
                </div>
              </template>
              <div v-else class="muted">暂无主题上下文。</div>
              <div v-if="selectedDetail.candidate.auto_processed" class="topic-correction-panel">
                <label>
                  <span>更换主主题</span>
                  <select v-model="topicCorrectionTopicId">
                    <option value="">选择 Wiki Topic</option>
                    <option
                      v-for="topic in topicOptions"
                      :key="topic.topic_id"
                      :value="topic.topic_id"
                    >
                      {{ topic.title || topic.display_name || topic.topic_id }} · {{ topic.topic_id }}
                    </option>
                  </select>
                </label>
                <label>
                  <span>更改原因</span>
                  <input v-model="topicCorrectionReason" type="text" placeholder="例如：Data+AI 主题纠错" />
                </label>
                <div class="correction-actions">
                  <button
                    class="primary-btn"
                    type="button"
                    :disabled="correctingTopic || !topicCorrectionTopicId || topicCorrectionTopicId === selectedTopicId(selectedDetail)"
                    @click="changePrimaryTopic"
                  >
                    {{ correctingTopic ? '更换中...' : '更换主主题' }}
                  </button>
                  <button
                    class="secondary-btn"
                    type="button"
                    :disabled="correctingTopic || !selectedTopicId(selectedDetail)"
                    @click="unlinkPrimaryTopic"
                  >
                    解除主主题关联
                  </button>
                </div>
                <p v-if="topicCorrectionError" class="inline-error">{{ topicCorrectionError }}</p>
              </div>
            </div>

            <div v-if="activeDetailTab !== 'digest'" class="project-action-panel">
              <div class="block-title">加入当前研究项目</div>
              <template v-if="currentResearchProject">
                <p class="muted">
                  当前项目：{{ currentResearchProject.title }}。此操作只写入研究项目 evidence_items，不改原始 Markdown，不重新触发预消化。
                </p>
                <div class="project-action-grid">
                  <label>
                    <span>采用分类</span>
                    <select v-model="projectEvidenceType">
                      <option value="evidence">作为证据</option>
                      <option value="background">作为背景材料</option>
                      <option value="concept_source">作为概念来源</option>
                      <option value="rejected">暂不采用</option>
                    </select>
                  </label>
                  <label>
                    <span>人工备注</span>
                    <textarea v-model="projectEvidenceNote" rows="3" />
                  </label>
                </div>
                <button
                  class="primary-btn"
                  type="button"
                  :disabled="addingToProject || projectEvidenceType === 'rejected'"
                  @click="addArticleToCurrentResearchProject"
                >
                  {{ addingToProject ? '加入中...' : '加入当前研究项目' }}
                </button>
                <button
                  v-if="projectEvidenceType === 'rejected'"
                  class="secondary-btn"
                  type="button"
                  disabled
                >
                  暂不采用不会写入项目
                </button>
                <p v-if="projectActionError" class="inline-error">{{ projectActionError }}</p>
              </template>
              <div v-else class="muted">尚未选择当前研究项目。先到战略研究页创建或选择项目。</div>
            </div>

            <div v-if="!isCompleted(selectedDetail.candidate) && activeDetailTab !== 'digest'" class="decision-panel">
              <textarea v-model="decisionNote" placeholder="决策备注，可留空" />
              <div class="decision-actions">
                <button class="primary-btn" @click="decide('accepted')">接收进 Wiki</button>
                <button class="secondary-btn" @click="decide('needs_human_review')">需复核</button>
                <button class="secondary-btn" @click="decide('deferred')">暂缓</button>
                <button class="secondary-btn" @click="decide('rejected')">拒绝</button>
                <button class="secondary-btn" @click="decide('duplicate')">重复</button>
              </div>
            </div>

            <div v-show="activeDetailTab === 'reader'" class="detail-tab-panel reader-tab-panel">
              <MarkdownArticleViewer
                :markdown="selectedDetail.content || ''"
                :candidate-id="selectedDetail.candidate.candidate_id"
                :source-file-path="selectedDetail.candidate.source_file_path"
              />
            </div>

            <div v-show="activeDetailTab === 'source'" class="detail-tab-panel preview-block">
              <div class="block-title">Markdown 原文</div>
              <pre>{{ selectedDetail.content || '无内容' }}</pre>
            </div>

            <div v-show="activeDetailTab === 'digest'" class="detail-tab-panel predigest-panel">
              <div class="block-title">预消化结果</div>
              <template v-if="hasPredigestResult(selectedDetail)">
                <div class="digest-review-surface">
                  <div v-if="!hasFullProcessedDigest(selectedDetail)" class="state-card">
                    暂无完整预消化摘要，仅有写入清单。
                  </div>

                  <template v-else>
                    <section class="digest-section route-section">
                      <div class="section-head">
                        <span class="section-title">处理结论 / 推荐主题</span>
                        <div class="section-badges">
                          <span v-if="routeTopicLabel(selectedDetail)" class="digest-badge topic-badge">{{ routeTopicLabel(selectedDetail) }}</span>
                          <span v-if="routeConfidence(selectedDetail)" class="digest-badge">{{ routeConfidence(selectedDetail) }}</span>
                        </div>
                      </div>
                      <dl class="digest-route-grid">
                        <div>
                          <dt>推荐主题</dt>
                          <dd>{{ routeTopicId(selectedDetail) || '未记录' }}</dd>
                        </div>
                        <div>
                          <dt>路由方式</dt>
                          <dd>{{ routeModeText(selectedDetail) }}</dd>
                        </div>
                      </dl>
                      <p v-if="routeRationale(selectedDetail)" class="digest-copy">{{ routeRationale(selectedDetail) }}</p>
                    </section>

                    <section class="digest-section">
                      <div class="section-title">文章消化</div>
                      <article v-if="digestSummary(selectedDetail)" class="summary-card">
                        <span>一句话摘要 / 主旨</span>
                        <p>{{ digestSummary(selectedDetail) }}</p>
                      </article>
                      <article v-if="digestMainClaim(selectedDetail)" class="summary-card">
                        <span>主张 / Main claim</span>
                        <p>{{ digestMainClaim(selectedDetail) }}</p>
                      </article>
                      <ul v-if="digestKeyPoints(selectedDetail).length" class="key-point-list">
                        <li v-for="point in digestKeyPoints(selectedDetail)" :key="point">{{ point }}</li>
                      </ul>
                      <div v-if="digestMechanism(selectedDetail) || digestAuthorPosition(selectedDetail)" class="digest-two-column">
                        <article v-if="digestMechanism(selectedDetail)" class="summary-card">
                          <span>机制总结</span>
                          <p>{{ digestMechanism(selectedDetail) }}</p>
                        </article>
                        <article v-if="digestAuthorPosition(selectedDetail)" class="summary-card">
                          <span>作者立场</span>
                          <p>{{ digestAuthorPosition(selectedDetail) }}</p>
                        </article>
                      </div>
                    </section>

                    <section v-if="candidateConcepts(selectedDetail).length" class="digest-section candidate-concept-section">
                      <div class="section-title">候选概念</div>
                      <div class="concept-card-grid">
                        <article
                          v-for="concept in candidateConcepts(selectedDetail)"
                          :key="concept.name"
                          class="concept-card"
                        >
                          <div class="concept-card-head">
                            <h3>{{ concept.name }}</h3>
                            <span class="digest-badge">候选概念</span>
                          </div>
                          <p>{{ concept.summary || '暂无概念解释，仅作为本文候选线索保留。' }}</p>
                          <small>Candidate Concept · 未写入 KFC 正式概念库</small>
                        </article>
                      </div>
                    </section>

                    <section class="digest-section">
                      <div class="section-title">核验与风险</div>
                      <div class="verification-grid">
                        <div v-for="item in verificationStats(selectedDetail)" :key="item.label" class="verification-stat">
                          <span>{{ item.value }}</span>
                          <small>{{ item.label }}</small>
                        </div>
                      </div>
                      <div v-if="reviewClaims(selectedDetail).length" class="claim-list">
                        <article v-for="claim in reviewClaims(selectedDetail)" :key="claim.claim_id || claim.claim_text" class="claim-card">
                          <div class="claim-head">
                            <span class="claim-status">{{ claim.verification_status || claim.status || 'source_only' }}</span>
                            <span v-if="claim.supporting_urls?.length" class="source-count">{{ claim.supporting_urls.length }} 个来源</span>
                          </div>
                          <p>{{ claim.claim_text || claim.fact || claim.claim }}</p>
                          <small v-if="claim.safe_wiki_wording">{{ claim.safe_wiki_wording }}</small>
                          <details v-if="claim.supporting_urls?.length" class="source-details">
                            <summary>查看来源</summary>
                            <ul>
                              <li v-for="url in claim.supporting_urls" :key="sourceUrlText(url)">
                                <a
                                  v-if="sourceUrlHref(url)"
                                  class="source-url-link"
                                  :href="sourceUrlHref(url)"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {{ sourceUrlText(url) }}
                                </a>
                                <span v-else>{{ sourceUrlText(url) }}</span>
                              </li>
                            </ul>
                          </details>
                        </article>
                      </div>
                    </section>

                    <section class="digest-section safe-wiki-section">
                      <div class="section-title">Wiki 安全写法</div>
                      <article v-if="safeWikiSummary(selectedDetail)" class="summary-card safe-summary">
                        <span>建议写入 Wiki 的安全摘要</span>
                        <p>{{ safeWikiSummary(selectedDetail) }}</p>
                      </article>
                      <article v-if="doNotStateAsFact(selectedDetail).length" class="risk-card">
                        <span>不能直接当事实写</span>
                        <ul>
                          <li v-for="item in doNotStateAsFact(selectedDetail)" :key="item">{{ item }}</li>
                        </ul>
                      </article>
                      <article v-if="followUpQuestions(selectedDetail).length" class="summary-card">
                        <span>后续研究建议</span>
                        <ul>
                          <li v-for="item in followUpQuestions(selectedDetail)" :key="item">{{ item }}</li>
                        </ul>
                      </article>
                    </section>

                    <section class="digest-section kfc-followup-section">
                      <div class="section-title">KFC 后续动作建议</div>
                      <div class="kfc-action-grid">
                        <article v-for="action in kfcActionHints(selectedDetail)" :key="action.title" class="kfc-action-card">
                          <span>{{ action.title }}</span>
                          <p>{{ action.body }}</p>
                          <small>只读占位，不会写入概念库或创建关系</small>
                        </article>
                      </div>
                    </section>
                  </template>
                </div>

                <details v-if="auditPayload(selectedDetail)" class="audit-details">
                  <summary>写入结果 / 审计信息 <span>查看原始 JSON</span></summary>
                  <div class="audit-link-row">
                    <a v-if="selectedDetail.candidate.auto_processed?.raw_article_path" :href="pathHref(selectedDetail.candidate.auto_processed.raw_article_path)">raw_article_path</a>
                    <a v-if="selectedDetail.candidate.auto_processed?.verified_digest_md_path" :href="pathHref(selectedDetail.candidate.auto_processed.verified_digest_md_path)">verified_digest_md_path</a>
                    <a v-if="selectedDetail.candidate.auto_processed?.claim_ledger_path" :href="pathHref(selectedDetail.candidate.auto_processed.claim_ledger_path)">claim_ledger_path</a>
                    <a v-if="selectedDetail.candidate.auto_processed?.sources_path" :href="pathHref(selectedDetail.candidate.auto_processed.sources_path)">sources_path</a>
                  </div>
                  <div class="digest-json-block">
                    <div class="mini-label">auto_processed / sidecar payload</div>
                    <pre>{{ prettyJson(auditPayload(selectedDetail)) }}</pre>
                  </div>
                </details>
              </template>
              <div v-else class="state-card">暂无预消化结果。</div>
            </div>

            <div v-show="activeDetailTab === 'metadata'" class="detail-tab-panel metadata-panel">
              <div class="block-title">元数据</div>
              <dl class="meta-grid">
                <div>
                  <dt>candidate_id</dt>
                  <dd>{{ selectedDetail.candidate.candidate_id || '未记录' }}</dd>
                </div>
                <div>
                  <dt>source_id</dt>
                  <dd>{{ selectedDetail.candidate.source_id || selectedDetail.candidate.candidate_id || '未记录' }}</dd>
                </div>
                <div>
                  <dt>source_file_path</dt>
                  <dd>{{ selectedDetail.candidate.source_file_path || '未记录' }}</dd>
                </div>
                <div>
                  <dt>topic_id</dt>
                  <dd>{{ selectedTopicId(selectedDetail) || '未识别' }}</dd>
                </div>
                <div>
                  <dt>status</dt>
                  <dd>{{ statusLabel(selectedDetail.candidate.status) }}</dd>
                </div>
                <div>
                  <dt>content_hash</dt>
                  <dd>{{ selectedDetail.candidate.content_hash || '未记录' }}</dd>
                </div>
                <div>
                  <dt>duplicate_status</dt>
                  <dd>{{ selectedDetail.candidate.duplicate_status || 'none' }}</dd>
                </div>
                <div>
                  <dt>guessed_topics</dt>
                  <dd>{{ topicSummary(selectedDetail.candidate.guessed_topics) }}</dd>
                </div>
              </dl>
            </div>
          </template>
          <div v-else class="state-card">选择一条素材查看处理细节。</div>
        </aside>
      </div>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onBeforeUpdate, onMounted, ref } from 'vue'
import AppShell from '../components/common/AppShell.vue'
import MarkdownArticleViewer from '../components/wiki-intake/MarkdownArticleViewer.vue'
import {
  changeWikiIntakeCandidatePrimaryTopic,
  createWikiIntakeDecision,
  getResearchProject,
  getWikiIntakeCandidate,
  getWikiIntakeConfig,
  getWikiIntakeProcessedResult,
  listWikiTopics,
  listWikiIntakeCandidates,
  processNextWikiIntake,
  scanWikiIntake,
  unlinkWikiIntakeCandidatePrimaryTopic,
  updateResearchProject,
} from '../data/dataClient'
import { readCurrentResearchProject, setCurrentResearchProject, subscribeCurrentResearchProject } from '../utils/currentResearchProjectContext'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '素材加工台' },
]

const filterOptions = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待处理' },
  { value: 'accepted', label: '已接收' },
  { value: 'needs_human_review', label: '需复核' },
  { value: 'completed', label: '已完成' },
  { value: 'deferred', label: '已暂缓' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'duplicate', label: '重复' },
]

const detailTabs = [
  { value: 'digest', label: '预消化结果' },
  { value: 'source', label: 'Markdown 原文' },
  { value: 'reader', label: '阅读视图' },
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

const candidates = ref([])
const stats = ref({})
const config = ref(null)
const selectedId = ref('')
const selectedDetail = ref(null)
const statusFilter = ref('all')
const loading = ref(false)
const scanning = ref(false)
const processing = ref(false)
const error = ref('')
const message = ref('')
const decisionNote = ref('')
const currentResearchProject = ref(null)
const currentResearchProjectDetail = ref(null)
const projectEvidenceType = ref('evidence')
const projectEvidenceNote = ref('用于支撑 Agent-ready 软件栈中 Context Engineering / Harness Engineering 的架构判断。')
const addingToProject = ref(false)
const projectActionError = ref('')
const topicOptions = ref([])
const topicCorrectionTopicId = ref('')
const topicCorrectionReason = ref('')
const topicCorrectionError = ref('')
const correctingTopic = ref(false)
const detailPanelRef = ref(null)
const candidateListRef = ref(null)
const activeDetailTab = ref('reader')
const candidateRowRefs = new Map()
let unsubscribeResearchProject = () => {}

onBeforeUpdate(() => {
  candidateRowRefs.clear()
})

const filteredCandidates = computed(() => {
  if (statusFilter.value === 'all') return candidates.value
  return candidates.value.filter((item) => item.status === statusFilter.value)
})

function statusLabel(status) {
  return statusText[status] || status || '待处理'
}

function countFor(status) {
  if (status === 'all') return candidates.value.length
  return candidates.value.filter((item) => item.status === status).length
}

function formatSize(size) {
  const value = Number(size || 0)
  if (!value) return '0 B'
  if (value < 1024) return `${value} B`
  return `${Math.round(value / 1024)} KB`
}

function topicSummary(topics) {
  if (!Array.isArray(topics) || !topics.length) return '未识别'
  return topics.map((item) => item.topic_id || item).join(', ')
}

function isCompleted(candidate) {
  return candidate?.status === 'completed'
}

function pathHref(path) {
  return `file://${path}`
}

function sourceUrlText(url) {
  if (url === null || url === undefined) return ''
  if (typeof url === 'string') return url
  return url.url || url.href || url.source_url || String(url)
}

function sourceUrlHref(url) {
  const text = sourceUrlText(url).trim()
  if (!text) return ''
  try {
    const parsed = new URL(text)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return parsed.href
  } catch {
    return ''
  }
  return ''
}

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function selectedTopicId(detail) {
  const candidate = detail?.candidate || {}
  if (candidate.auto_processed) return candidate.auto_processed.topic_id || ''
  if (detail?.topic_context?.topic_id) return detail.topic_context.topic_id
  const firstGuess = candidate.guessed_topics?.[0]
  return typeof firstGuess === 'string' ? firstGuess : firstGuess?.topic_id || ''
}

async function loadTopicOptions() {
  try {
    const response = await listWikiTopics()
    const data = response?.data
    topicOptions.value = Array.isArray(data) ? data : (data?.items || data?.topics || [])
  } catch {
    topicOptions.value = []
  }
}

function hasPredigestResult(detail) {
  const candidate = detail?.candidate || {}
  return Boolean(
    detail?.processed_result
      || detail?.decision_digest?.markdown
      || detail?.decision_digest?.payload
      || candidate.latest_processing
      || candidate.auto_processed,
  )
}

function processedResult(detail) {
  return detail?.processed_result || null
}

function verifiedDigest(detail) {
  return processedResult(detail)?.verified_digest?.json || detail?.decision_digest?.payload || {}
}

function sourceDigest(detail) {
  const digest = verifiedDigest(detail)
  return digest.source_digest || digest
}

function semanticResult(detail) {
  return processedResult(detail)?.semantic_result || {}
}

function articleDigest(detail) {
  return semanticResult(detail).article_digest || {}
}

function claimLedger(detail) {
  const claims = processedResult(detail)?.claim_ledger
  return Array.isArray(claims) ? claims : []
}

function hasFullProcessedDigest(detail) {
  const result = processedResult(detail)
  if (!result) return Boolean(detail?.decision_digest?.markdown || detail?.decision_digest?.payload)
  return Boolean(result.verified_digest?.json || result.verified_digest?.md || claimLedger(detail).length || result.sources)
}

function routingDecision(detail) {
  return verifiedDigest(detail).routing_decision || {}
}

function routeTopicId(detail) {
  const semanticTopic = semanticResult(detail).recommended_topic || {}
  const routing = routingDecision(detail)
  return semanticTopic.topic_id
    || routing.resolved_topic_id
    || routing.original_recommended_topic
    || verifiedDigest(detail).recommended_topic
    || verifiedDigest(detail).topic
    || selectedTopicId(detail)
}

function routeTopicLabel(detail) {
  const semanticTopic = semanticResult(detail).recommended_topic || {}
  const routing = routingDecision(detail)
  return semanticTopic.label
    || routing.resolved_topic_label
    || routing.original_recommended_topic_label
    || routing.new_topic_suggestion?.label
    || verifiedDigest(detail).recommended_topic_label
    || detail?.topic_context?.title
    || routeTopicId(detail)
}

function routeConfidence(detail) {
  const routing = routingDecision(detail)
  const label = routing.original_confidence || verifiedDigest(detail).confidence || ''
  const score = routing.original_confidence_score ?? verifiedDigest(detail).confidence_score
  if (label && score !== undefined && score !== null && score !== '') return `${label} ${score}`
  return label || (score !== undefined && score !== null && score !== '' ? `${score}` : '')
}

function routeModeText(detail) {
  const semanticTopic = semanticResult(detail).recommended_topic || {}
  const routing = routingDecision(detail)
  const routeMode = semanticTopic.route_mode || routing.route_mode || detail?.candidate?.auto_processed?.route_mode || ''
  const topic = routeTopicId(detail)
  if (routeMode === 'auto_created_topic') return `系统建议并自动创建了新主题：${topic || '未记录'}`
  if (routeMode === 'recommended_topic') return `匹配已有主题：${topic || '未记录'}`
  return routeMode || '未记录'
}

function routeRationale(detail) {
  const routing = routingDecision(detail)
  const reasons = [
    routing.override_reason,
    routing.new_topic_suggestion?.description,
    ...(Array.isArray(routing.reason_codes) ? routing.reason_codes : []),
    ...(Array.isArray(routing.warnings) ? routing.warnings : []),
  ].filter(Boolean)
  return reasons.slice(0, 3).join('；')
}

function digestSummary(detail) {
  const article = articleDigest(detail)
  const digest = verifiedDigest(detail)
  const source = sourceDigest(detail)
  return article.one_sentence_summary
    || source.one_sentence_summary
    || source.source_summary
    || digest.source_summary
    || digest.summary
    || digest.verified_summary
    || ''
}

function digestMainClaim(detail) {
  const article = articleDigest(detail)
  const source = sourceDigest(detail)
  return article.main_claim || source.main_claim || verifiedDigest(detail).main_claim || ''
}

function asTextList(value, limit = 6) {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (typeof item === 'string') return item
    if (item?.claim && item?.reason) return `${item.claim}：${item.reason}`
    return item?.text || item?.title || item?.summary || item?.claim || item?.reason || ''
  }).filter(Boolean).slice(0, limit)
}

function digestKeyPoints(detail) {
  const article = articleDigest(detail)
  if (Array.isArray(article.key_points) && article.key_points.length) return article.key_points
  const source = sourceDigest(detail)
  return asTextList(source.key_points || verifiedDigest(detail).key_points, 6)
}

function digestConcepts(detail) {
  const source = sourceDigest(detail)
  return asTextList(source.core_concepts || verifiedDigest(detail).core_concepts || verifiedDigest(detail).top_concepts, 12)
}

function candidateConcepts(detail) {
  const semanticConcepts = semanticResult(detail).candidate_concepts
  if (Array.isArray(semanticConcepts) && semanticConcepts.length) {
    return semanticConcepts
      .map((concept) => ({
        name: concept.name || concept.concept || concept.title || '',
        summary: concept.summary || concept.body || concept.description || '',
        candidate_status: concept.candidate_status || 'candidate_only',
        kfc_action_hint: concept.kfc_action_hint || 'review_for_kfc',
      }))
      .filter((concept) => concept.name)
  }
  const source = sourceDigest(detail)
  const rawConcepts = source.core_concepts || verifiedDigest(detail).core_concepts || verifiedDigest(detail).top_concepts || []
  if (!Array.isArray(rawConcepts)) return []
  return rawConcepts.map((concept) => {
    if (typeof concept === 'string') {
      return {
        name: concept,
        summary: '',
        candidate_status: 'candidate_only',
        kfc_action_hint: 'keep_as_article_clue',
      }
    }
    return {
      name: concept?.concept || concept?.name || concept?.title || '',
      summary: concept?.summary || concept?.body || concept?.description || '',
      candidate_status: concept?.candidate_status || 'candidate_only',
      kfc_action_hint: concept?.kfc_action_hint || 'review_for_kfc',
    }
  }).filter((concept) => concept.name).slice(0, 12)
}

function digestMechanism(detail) {
  const article = articleDigest(detail)
  const source = sourceDigest(detail)
  return article.mechanism_summary || source.mechanism_summary || verifiedDigest(detail).mechanism_summary || ''
}

function digestAuthorPosition(detail) {
  const article = articleDigest(detail)
  const source = sourceDigest(detail)
  return article.author_position || source.author_position || verifiedDigest(detail).author_position || ''
}

function claimLedgerSummary(detail) {
  const digest = verifiedDigest(detail)
  const explicit = digest.claim_ledger_summary
  if (explicit && typeof explicit === 'object') return explicit
  const counts = { total_claims: 0, verified: 0, source_only: 0, uncertain: 0, contradicted_or_stale: 0 }
  claimLedger(detail).forEach((claim) => {
    counts.total_claims += 1
    const status = claim.verification_status || claim.status || 'source_only'
    if (status === 'verified') counts.verified += 1
    else if (status === 'uncertain') counts.uncertain += 1
    else if (status === 'contradicted' || status === 'stale' || status === 'contradicted_or_stale') counts.contradicted_or_stale += 1
    else counts.source_only += 1
  })
  return counts
}

function verificationStats(detail) {
  const semanticVerification = semanticResult(detail).verification || {}
  const digest = verifiedDigest(detail)
  const summary = digest.verification_summary || {}
  const ledger = claimLedgerSummary(detail)
  const sources = processedResult(detail)?.sources?.sources || []
  return [
    { label: 'Web 核验', value: summary.web_verification_performed ?? (sources.length ? 'yes' : 'no') },
    { label: '核验深度', value: summary.verification_depth || `${sources.length} sources` },
    { label: 'verified', value: semanticVerification.verified_count ?? summary.verified_facts_count ?? ledger.verified ?? 0 },
    { label: 'source_only', value: semanticVerification.source_only_count ?? ledger.source_only ?? 0 },
    { label: 'uncertain', value: semanticVerification.uncertain_count ?? summary.uncertain_claims_count ?? ledger.uncertain ?? 0 },
    { label: 'stale/contradicted', value: semanticVerification.stale_contradicted_count ?? ledger.contradicted_or_stale ?? 0 },
  ]
}

function reviewClaims(detail) {
  const digest = verifiedDigest(detail)
  const verifiedFacts = Array.isArray(digest.verified_facts) ? digest.verified_facts : []
  const uncertainClaims = Array.isArray(digest.uncertain_claims) ? digest.uncertain_claims : []
  const normalizedFacts = verifiedFacts.map((fact, index) => ({
    claim_id: `verified_${index}`,
    claim_text: fact.fact || fact.claim || fact,
    verification_status: 'verified',
    supporting_urls: fact.supporting_urls || [],
  }))
  const normalizedUncertain = uncertainClaims.map((claim, index) => ({
    claim_id: `uncertain_${index}`,
    claim_text: claim.claim || claim.fact || claim,
    verification_status: 'uncertain',
    safe_wiki_wording: claim.reason || '',
  }))
  return [...normalizedFacts, ...normalizedUncertain, ...claimLedger(detail)].slice(0, 5)
}

function safeWikiSummary(detail) {
  const semanticSafeWiki = semanticResult(detail).safe_wiki || {}
  const digest = verifiedDigest(detail)
  return semanticSafeWiki.summary || digest.safe_wiki?.safe_summary || digest.safe_summary || digest.safe_wiki_wording || digest.verified_summary || ''
}

function doNotStateAsFact(detail) {
  const semanticVerification = semanticResult(detail).verification || {}
  if (Array.isArray(semanticVerification.do_not_state_as_fact) && semanticVerification.do_not_state_as_fact.length) {
    return semanticVerification.do_not_state_as_fact
  }
  const digest = verifiedDigest(detail)
  const safeItems = digest.safe_wiki?.do_not_state_as_fact || digest.do_not_state_as_fact
  const gaps = digest.research_gaps
  const riskyClaims = claimLedger(detail)
    .filter((claim) => ['uncertain', 'contradicted', 'stale', 'contradicted_or_stale'].includes(claim.verification_status || claim.status))
    .map((claim) => `${claim.claim_text || claim.claim}：${claim.verification_notes || claim.reason || '需要进一步核验'}`)
  return [...asTextList(safeItems, 8), ...asTextList(gaps, 8), ...riskyClaims].slice(0, 8)
}

function followUpQuestions(detail) {
  const semanticSafeWiki = semanticResult(detail).safe_wiki || {}
  if (Array.isArray(semanticSafeWiki.follow_up_questions) && semanticSafeWiki.follow_up_questions.length) {
    return semanticSafeWiki.follow_up_questions
  }
  const digest = verifiedDigest(detail)
  return asTextList(digest.safe_wiki?.follow_up_questions || digest.follow_up_questions || digest.recommended_followups || [], 6)
}

function kfcActionHints(detail) {
  const concepts = candidateConcepts(detail).map((concept) => concept.name)
  const conceptText = concepts.length ? concepts.slice(0, 5).join('、') : '暂无可判断候选概念'
  return [
    {
      title: '建议匹配已有 KFC 概念',
      body: concepts.length ? `优先人工检查这些候选概念是否已存在：${conceptText}。` : '缺少候选概念时暂不做匹配判断。',
    },
    {
      title: '建议作为新概念进入 KFC',
      body: concepts.length ? `可把 ${conceptText} 作为待复核概念线索，不在本页自动创建。` : '暂无新概念入库建议。',
    },
    {
      title: '仅保留为本文线索',
      body: '证据不足、作者观点或市场传言类内容先保留在本文审计链路中。',
    },
  ]
}

function auditPayload(detail) {
  const candidate = detail?.candidate || {}
  const payload = {}
  if (candidate.auto_processed) payload.auto_processed = candidate.auto_processed
  if (candidate.latest_processing) payload.latest_processing = candidate.latest_processing
  if (detail?.decision_digest?.payload) payload.decision_digest_v1 = detail.decision_digest.payload
  if (processedResult(detail)) payload.processed_result = processedResult(detail)
  return Object.keys(payload).length ? payload : null
}

function projectEvidenceId(detail) {
  const candidateId = detail?.candidate?.candidate_id || selectedId.value || 'article'
  return `article_${candidateId}`.replace(/[^a-zA-Z0-9_:-]/g, '_')
}

function currentClusterId(detail) {
  const links = detail?.topic_context?.cluster_links || []
  if (links[0]?.cluster_id) return links[0].cluster_id
  const ids = detail?.topic_context?.cluster_ids || []
  return ids[0] || ''
}

async function refreshCurrentResearchProjectDetail() {
  const current = readCurrentResearchProject()
  currentResearchProject.value = current
  currentResearchProjectDetail.value = null
  if (!current?.id) return
  try {
    const response = await getResearchProject(current.id)
    const project = response?.data || null
    currentResearchProjectDetail.value = project || null
    if (project) setCurrentResearchProject(project)
  } catch {
    currentResearchProjectDetail.value = null
  }
}

async function addArticleToCurrentResearchProject() {
  if (!currentResearchProject.value?.id || !selectedDetail.value?.candidate) return
  addingToProject.value = true
  projectActionError.value = ''
  try {
    const project = currentResearchProjectDetail.value
    if (!project?.id) throw new Error('当前研究项目不存在或已被删除')
    const detail = selectedDetail.value
    const candidate = detail.candidate
    const evidenceId = projectEvidenceId(detail)
    const provenance = {
      source_url: candidate.source_url || detail.source_url || '',
      source_file_path: candidate.source_file_path || '',
      candidate_id: candidate.candidate_id || selectedId.value,
      topic_id: selectedTopicId(detail),
      cluster_id: currentClusterId(detail),
      raw_article_path: candidate.auto_processed?.raw_article_path || '',
      verified_digest_md_path: candidate.auto_processed?.verified_digest_md_path || '',
      verified_digest_json_path: candidate.auto_processed?.verified_digest_json_path || '',
    }
    const nextEvidence = [
      ...(project.evidence_items || []).filter((item) => item.evidence_id !== evidenceId),
      {
        evidence_id: evidenceId,
        title: candidate.title,
        evidence_type: projectEvidenceType.value,
        status: 'accepted',
        adoption_note: projectEvidenceNote.value,
        provenance,
        adopted_by: 'human',
        adopted_at: new Date().toISOString(),
      },
    ]
    const response = await updateResearchProject(project.id, { evidence_items: nextEvidence })
    const updated = response?.data
    currentResearchProjectDetail.value = updated
    if (updated) setCurrentResearchProject(updated)
    message.value = `已加入当前研究项目证据篮：${candidate.title}`
  } catch (err) {
    projectActionError.value = err.message || '加入当前研究项目失败'
  } finally {
    addingToProject.value = false
  }
}

function setCandidateRowRef(candidateId, el) {
  if (el) candidateRowRefs.set(candidateId, el)
}

function queryCandidateId() {
  if (typeof window === 'undefined') return ''
  return new URLSearchParams(window.location.search).get('candidate') || ''
}

function syncCandidateQuery(candidateId) {
  if (typeof window === 'undefined' || !candidateId) return
  const url = new URL(window.location.href)
  if (url.searchParams.get('candidate') === candidateId) return
  url.searchParams.set('candidate', candidateId)
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
}

async function scrollSelectedIntoView(candidateId) {
  await nextTick()
  candidateRowRefs.get(candidateId)?.scrollIntoView?.({ block: 'nearest' })
}

async function resetDetailScroll() {
  await nextTick()
  if (detailPanelRef.value) detailPanelRef.value.scrollTop = 0
}

async function loadConfig() {
  try {
    const response = await getWikiIntakeConfig()
    config.value = response.data || null
  } catch {
    config.value = null
  }
}

async function loadCandidates() {
  loading.value = true
  error.value = ''
  let revealSelectedAfterLoad = false
  try {
    const response = await listWikiIntakeCandidates()
    const data = response.data || {}
    candidates.value = data.items || []
    stats.value = data.stats || {}
    const requestedCandidateId = queryCandidateId()
    if (!selectedId.value && candidates.value.length) {
      const initialCandidate = candidates.value.find((item) => item.candidate_id === requestedCandidateId) || candidates.value[0]
      await selectCandidate(initialCandidate.candidate_id, { updateQuery: initialCandidate.candidate_id !== requestedCandidateId })
      revealSelectedAfterLoad = Boolean(requestedCandidateId)
    } else if (selectedId.value) {
      const stillExists = candidates.value.some((item) => item.candidate_id === selectedId.value)
      if (stillExists) await selectCandidate(selectedId.value)
      else selectedDetail.value = null
    }
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
    if (revealSelectedAfterLoad && selectedId.value) {
      await scrollSelectedIntoView(selectedId.value)
    }
  }
}

async function scan() {
  scanning.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await scanWikiIntake()
    const data = response.data || {}
    message.value = `扫描完成：${data.markdown_count || 0} 条 Markdown，重复风险 ${data.duplicate_count || 0} 条。`
    await loadCandidates()
  } catch (e) {
    error.value = e?.response?.data?.error || e?.message || '扫描失败'
  } finally {
    scanning.value = false
  }
}

async function processNext() {
  processing.value = true
  error.value = ''
  message.value = ''
  try {
    const response = await processNextWikiIntake()
    const data = response.data || {}
    const status = data.result?.status || data.runs?.[0]?.result?.status || 'completed'
    message.value = `手动处理完成：${status}`
    await loadCandidates()
  } catch (e) {
    error.value = e?.response?.data?.error || e?.message || '手动处理失败'
  } finally {
    processing.value = false
  }
}

async function selectCandidate(candidateId, options = {}) {
  const { updateQuery = true } = options
  selectedId.value = candidateId
  if (updateQuery) syncCandidateQuery(candidateId)
  try {
    const response = await getWikiIntakeCandidate(candidateId)
    const detail = response.data
    if (detail?.candidate?.auto_processed || detail?.candidate?.status === 'completed') {
      try {
        const processedResponse = await getWikiIntakeProcessedResult(candidateId)
        detail.processed_result = processedResponse?.data || null
      } catch (processedError) {
        detail.processed_result = {
          status: 'unavailable',
          auto_processed: detail?.candidate?.auto_processed || null,
          verified_digest: { json: null, md: '' },
          claim_ledger: [],
          sources: null,
          read_errors: { processed_result: processedError?.message || 'processed_result_unavailable' },
        }
      }
    }
    selectedDetail.value = detail
    activeDetailTab.value = isCompleted(detail?.candidate) || hasPredigestResult(detail) ? 'digest' : 'reader'
    decisionNote.value = ''
    topicCorrectionTopicId.value = selectedTopicId(selectedDetail.value)
    topicCorrectionReason.value = ''
    topicCorrectionError.value = ''
    await resetDetailScroll()
  } catch (e) {
    error.value = e?.message || '详情加载失败'
  }
}

async function changePrimaryTopic() {
  if (!selectedId.value || !topicCorrectionTopicId.value) return
  correctingTopic.value = true
  topicCorrectionError.value = ''
  message.value = ''
  try {
    const response = await changeWikiIntakeCandidatePrimaryTopic(selectedId.value, {
      topic_id: topicCorrectionTopicId.value,
      reason: topicCorrectionReason.value,
      operator: 'human',
    })
    selectedDetail.value = response?.data?.detail || selectedDetail.value
    message.value = `已更换主主题：${topicCorrectionTopicId.value}`
    await loadCandidates()
  } catch (e) {
    topicCorrectionError.value = e?.response?.data?.error || e?.message || '更换主主题失败'
  } finally {
    correctingTopic.value = false
  }
}

async function unlinkPrimaryTopic() {
  if (!selectedId.value) return
  correctingTopic.value = true
  topicCorrectionError.value = ''
  message.value = ''
  try {
    const response = await unlinkWikiIntakeCandidatePrimaryTopic(selectedId.value, {
      reason: topicCorrectionReason.value,
      operator: 'human',
    })
    selectedDetail.value = response?.data?.detail || selectedDetail.value
    topicCorrectionTopicId.value = ''
    message.value = '已解除当前主主题关联，文章进入待复核状态'
    await loadCandidates()
  } catch (e) {
    topicCorrectionError.value = e?.response?.data?.error || e?.message || '解除主题关联失败'
  } finally {
    correctingTopic.value = false
  }
}

async function decide(decision) {
  if (!selectedId.value || isCompleted(selectedDetail.value?.candidate)) return
  error.value = ''
  message.value = ''
  try {
    await createWikiIntakeDecision({
      candidate_id: selectedId.value,
      decision,
      target: 'wiki',
      note: decisionNote.value,
      operator: 'human',
    })
    message.value = `已记录决策：${statusLabel(decision)}`
    await loadCandidates()
  } catch (e) {
    error.value = e?.response?.data?.error || e?.message || '决策失败'
  }
}

onMounted(async () => {
  await refreshCurrentResearchProjectDetail()
  unsubscribeResearchProject = subscribeCurrentResearchProject(() => {
    refreshCurrentResearchProjectDetail()
  })
  await loadConfig()
  await loadTopicOptions()
  await loadCandidates()
})

onBeforeUnmount(() => {
  unsubscribeResearchProject()
})
</script>

<style scoped>
.wiki-intake-page {
  box-sizing: border-box;
  flex: 1;
  min-height: 0;
  height: 100%;
  padding: 20px 24px 24px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--text-primary);
}
.page-head {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}
.section-badge {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--accent-primary);
}
h1 {
  margin: 6px 0;
  font-size: 28px;
}
.page-head p,
.safety-copy {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.summary {
  min-width: 88px;
  padding: 12px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  text-align: center;
}
.summary-number {
  display: block;
  font-size: 28px;
  font-weight: 800;
}
.toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.primary-btn,
.secondary-btn,
.filter-btn,
.candidate-row {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  cursor: pointer;
}
.primary-btn {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
  padding: 8px 12px;
  font-weight: 700;
}
.secondary-btn {
  padding: 8px 12px;
}
.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.project-action-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
  padding: 12px;
  margin: 14px 0;
}
.topic-correction-panel {
  display: grid;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-default);
}
.topic-correction-panel label {
  display: grid;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}
.topic-correction-panel select,
.topic-correction-panel input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  padding: 8px 10px;
}
.correction-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.project-action-grid {
  display: grid;
  gap: 10px;
  margin: 10px 0;
}
.project-action-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}
.project-action-grid select,
.project-action-grid textarea {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font: inherit;
  padding: 8px 10px;
}
.inline-error {
  color: var(--danger-text, #b42318);
  font-size: 12px;
  margin: 8px 0 0;
}
.path-chip,
.inline-message {
  font-size: 12px;
  color: var(--text-secondary);
}
.inline-message {
  flex: 0 0 auto;
  margin: 12px 0;
}
.intake-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 150px minmax(420px, 1fr) minmax(460px, 42vw);
  gap: 16px;
  margin-top: 18px;
  align-items: stretch;
  overflow: hidden;
}
.filters-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  padding-right: 2px;
}
.filter-btn {
  flex: 0 0 auto;
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
}
.filter-btn.active {
  background: var(--bg-selected);
  color: var(--accent-primary-hover);
  font-weight: 800;
}
.candidate-list {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 4px;
  overscroll-behavior: contain;
}
.candidate-row {
  flex: 0 0 auto;
  text-align: left;
  padding: 12px;
}
.candidate-row:hover {
  border-color: var(--accent-primary);
  background: var(--bg-selected);
}
.candidate-row.selected {
  border-color: var(--accent-primary);
  background: linear-gradient(90deg, var(--bg-selected), var(--bg-surface));
  box-shadow: inset 4px 0 0 var(--accent-primary), 0 8px 18px rgba(25, 67, 122, 0.12);
}
.row-title {
  font-weight: 800;
  margin-bottom: 4px;
}
.row-path,
.row-meta,
.row-excerpt,
dd {
  color: var(--text-secondary);
  font-size: 12px;
}
.row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.row-excerpt {
  line-height: 1.5;
  margin: 8px 0 0;
}
.detail-panel {
  min-height: 0;
  align-self: stretch;
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-surface);
}
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.detail-eyebrow {
  font-size: 11px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
}
.detail-head h2 {
  font-size: 20px;
  margin: 4px 0 12px;
}
.detail-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 14px;
  border-bottom: 1px solid var(--border-default);
}
.detail-tab-btn {
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 9px 10px 8px;
  font-size: 13px;
  font-weight: 800;
}
.detail-tab-btn.active {
  color: var(--accent-primary-hover);
  border-bottom-color: var(--accent-primary);
}
.detail-tab-panel {
  min-width: 0;
}
.reader-tab-panel {
  padding: 4px 0 12px;
}
.status-pill {
  align-self: flex-start;
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
.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 0 0 14px;
}
dt {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 800;
}
dd {
  margin: 2px 0 0;
  overflow-wrap: anywhere;
}
.decision-panel {
  border-top: 1px solid var(--border-default);
  border-bottom: 1px solid var(--border-default);
  padding: 12px 0;
  margin-bottom: 12px;
}
.processed-panel {
  border-top: 1px solid var(--border-default);
  border-bottom: 1px solid var(--border-default);
  padding: 12px 0;
  margin-bottom: 12px;
}
.topic-context-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  background: var(--bg-muted);
}
.processed-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 0 0 10px;
}
.artifact-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.artifact-links a {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--accent-primary-hover);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 8px;
  text-decoration: none;
}
.context-clusters,
.context-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
}
.context-link {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--accent-primary-hover);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 8px;
  text-decoration: none;
  background: var(--bg-surface);
}
.recent-list {
  margin-top: 10px;
}
.recent-list ul {
  margin: 4px 0 0 18px;
  padding: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.mini-label,
.muted {
  color: var(--text-muted);
  font-size: 12px;
}
.decision-panel textarea {
  width: 100%;
  min-height: 56px;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 8px;
  resize: vertical;
  color: var(--text-primary);
  background: var(--bg-surface);
}
.decision-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.block-title {
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 8px;
}
.preview-block pre,
.digest-json-block pre {
  overflow-x: auto;
  white-space: pre-wrap;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  background: var(--bg-muted);
}
.predigest-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.digest-review-surface,
.digest-section {
  display: grid;
  gap: 12px;
}
.digest-review-surface {
  min-width: 0;
}
.digest-section {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-surface);
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.section-title {
  font-size: 13px;
  font-weight: 900;
  color: var(--text-primary);
}
.section-badges,
.concept-chip-row,
.audit-link-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.concept-card-grid,
.kfc-action-grid {
  display: grid;
  gap: 10px;
}
.concept-card,
.kfc-action-card {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 10px;
  background: var(--bg-muted);
}
.concept-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}
.concept-card h3 {
  margin: 0;
  font-size: 14px;
  line-height: 1.4;
}
.concept-card p,
.kfc-action-card p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.concept-card small,
.kfc-action-card small {
  display: block;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 11px;
}
.kfc-action-card span {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 900;
}
.digest-badge,
.concept-chip,
.claim-status,
.source-count {
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 800;
  background: var(--bg-muted);
  color: var(--text-secondary);
}
.topic-badge {
  color: var(--accent-primary-hover);
  background: var(--bg-selected);
}
.digest-route-grid,
.verification-grid,
.digest-two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.digest-route-grid {
  margin: 0;
}
.digest-copy,
.summary-card p,
.claim-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.summary-card,
.claim-card,
.risk-card,
.verification-stat {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 10px;
  background: var(--bg-muted);
}
.summary-card span,
.risk-card span {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 900;
}
.key-point-list,
.risk-card ul,
.source-details ul,
.summary-card ul {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.verification-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.verification-stat span {
  display: block;
  font-size: 16px;
  font-weight: 900;
}
.verification-stat small,
.claim-card small {
  color: var(--text-muted);
}
.claim-list {
  display: grid;
  gap: 10px;
}
.claim-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.safe-summary {
  border-color: rgba(26, 127, 55, 0.28);
  background: #f0fff4;
}
.risk-card {
  border-color: rgba(154, 103, 0, 0.28);
  background: #fff8c5;
}
.audit-details {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg-surface-2);
}
.audit-details summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
}
.audit-details summary span {
  margin-left: 8px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}
.audit-link-row {
  margin: 10px 0;
}
.audit-link-row a {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--accent-primary-hover);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 8px;
  text-decoration: none;
  background: var(--bg-surface);
}
.digest-markdown {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: var(--bg-surface);
}
.digest-json-block pre {
  max-height: 360px;
}
.state-card,
.error-card {
  padding: 14px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  color: var(--text-secondary);
}
.error-card {
  color: #cf222e;
  border-color: #ffb4ab;
}
@media (max-width: 1100px) {
  .wiki-intake-page {
    overflow: auto;
  }
  .intake-layout {
    flex: 0 0 auto;
    grid-template-columns: minmax(320px, 0.9fr) minmax(380px, 1.1fr);
    overflow: visible;
  }
  .filters-panel {
    grid-column: 1 / -1;
    flex-direction: row;
    flex-wrap: wrap;
    overflow-x: auto;
    overflow-y: hidden;
  }
  .candidate-list,
  .detail-panel {
    max-height: calc(100vh - 260px);
  }
}
@media (max-width: 760px) {
  .intake-layout {
    grid-template-columns: 1fr;
  }
  .candidate-list,
  .detail-panel {
    max-height: none;
    overflow: visible;
  }
}
</style>
