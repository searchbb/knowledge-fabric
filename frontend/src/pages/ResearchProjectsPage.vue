<template>
  <AppShell :crumbs="crumbs">
    <div class="research-page">
      <header class="page-header">
        <div class="section-badge">研究项目</div>
        <h1 class="section-title">战略研究项目</h1>
        <p class="section-copy">创建和管理由人发起的战略研究资产容器。</p>
      </header>

      <div v-if="loading" class="state-card">正在加载战略研究项目...</div>
      <div v-else-if="error" class="state-card error-card">{{ error }}</div>

      <template v-else>
        <section class="create-band">
          <form class="project-form" @submit.prevent="submitCreate">
            <label>
              <span>研究题目</span>
              <input v-model="form.title" type="text" placeholder="华为云 Agent-ready 企业软件栈战略研究" />
            </label>
            <label>
              <span>背景</span>
              <textarea v-model="form.background" rows="3" placeholder="研究背景和已知约束" />
            </label>
            <div class="form-grid">
              <label>
                <span>受众</span>
                <input v-model="form.audience" type="text" placeholder="华为云战略部二层领导" />
              </label>
              <label>
                <span>目标</span>
                <input v-model="form.goal" type="text" placeholder="形成战略判断、试点路径和材料输入" />
              </label>
            </div>
            <div class="form-actions">
              <button type="button" class="btn-secondary" @click="fillSample">填入样例</button>
              <button type="submit" class="btn-primary" :disabled="creating">
                {{ creating ? '创建中...' : '创建研究项目' }}
              </button>
            </div>
            <p v-if="createError" class="inline-error">{{ createError }}</p>
          </form>
        </section>

        <section class="workspace-grid">
          <div class="list-panel">
            <div class="panel-title">项目列表</div>
            <div v-if="!projects.length" class="empty-state">暂无战略研究项目</div>
            <button
              v-for="project in projects"
              v-else
              :key="project.id"
              class="project-row"
              :class="{ active: selectedId === project.id }"
              type="button"
              @click="selectProject(project.id)"
            >
              <span class="row-title">{{ project.title }}</span>
              <span class="row-meta">
                <span class="status-pill">{{ project.status }}</span>
                <span>{{ project.id }}</span>
              </span>
            </button>
          </div>

          <div class="detail-panel">
            <template v-if="selectedProject">
              <div class="detail-head">
                <div>
                  <div class="panel-title">研究定义</div>
                  <h2>{{ selectedProject.title }}</h2>
                </div>
                <span class="status-pill">{{ selectedProject.status }}</span>
              </div>

              <dl class="definition-list">
                <div>
                  <dt>背景</dt>
                  <dd>{{ selectedProject.background || '未填写' }}</dd>
                </div>
                <div>
                  <dt>受众</dt>
                  <dd>{{ selectedProject.audience || '未填写' }}</dd>
                </div>
                <div>
                  <dt>目标</dt>
                  <dd>{{ selectedProject.goal || '未填写' }}</dd>
                </div>
              </dl>

              <div class="asset-strip">
                <div><strong>{{ selectedProject.issue_tree?.length || 0 }}</strong><span>问题拆解</span></div>
                <div><strong>{{ selectedProject.evidence_items?.length || 0 }}</strong><span>证据</span></div>
                <div><strong>{{ selectedProject.insight_cards?.length || 0 }}</strong><span>洞察</span></div>
                <div><strong>{{ selectedProject.artifact_drafts?.length || 0 }}</strong><span>材料草稿</span></div>
              </div>

              <div class="timestamp-row">
                <span>创建：{{ selectedProject.created_at }}</span>
                <span>更新：{{ selectedProject.updated_at }}</span>
              </div>

              <nav class="project-context-tabs" aria-label="研究项目主线">
                <a href="#research-map">研究地图</a>
                <a href="#evidence-basket">证据篮</a>
                <a href="#concept-assets">概念图谱</a>
                <a href="#review-assets">审核</a>
              </nav>

              <section id="research-map" class="project-section-card">
                <div class="panel-title">研究地图</div>
                <p class="section-copy mini-copy">
                  从当前研究题出发，只展示候选 主题簇；只有点击“关联到当前研究项目”才会写入项目关系。
                </p>
                <div v-if="researchMapLoading" class="empty-state">正在加载相关 主题簇...</div>
                <div v-else-if="researchMapError" class="inline-error">{{ researchMapError }}</div>
                <div v-else class="cluster-candidate-grid">
                  <article v-for="candidate in researchMapCandidates" :key="candidate.cluster_id" class="cluster-candidate-card">
                    <div class="card-head-row">
                      <h3>{{ candidate.title }}</h3>
                      <span :class="['status-pill', { linked: linkedClusterIds.has(candidate.cluster_id) }]">
                        {{ linkedClusterIds.has(candidate.cluster_id) ? '当前项目已关联' : '候选' }}
                      </span>
                    </div>
                    <p>{{ candidate.relevance_reason }}</p>
                    <div class="metric-row">
                      <span>Wiki 主题 {{ candidate.wiki_topic_count }}</span>
                      <span>文章 {{ candidate.article_count }}</span>
                      <span>主题 {{ candidate.theme_count }}</span>
                      <span>概念 {{ candidate.concept_count }}</span>
                    </div>
                    <div class="chip-wrap">
                      <span v-for="term in candidate.hit_terms" :key="term" class="chip soft">{{ term }}</span>
                    </div>
                    <div class="action-row">
                      <RouterLink class="action-link" :to="`/workspace/topic-clusters/${candidate.cluster_id}`">打开主题簇</RouterLink>
                      <button
                        class="btn-small"
                        type="button"
                        :disabled="linkedClusterIds.has(candidate.cluster_id)"
                        @click="linkClusterToProject(candidate)"
                      >
                        {{ linkedClusterIds.has(candidate.cluster_id) ? '已关联' : '关联到当前研究项目' }}
                      </button>
                    </div>
                  </article>
                </div>
              </section>

              <section id="evidence-basket" class="project-section-card">
                <div class="panel-title">Wiki 文章证据篮</div>
                <p class="section-copy mini-copy">
                  证据篮只接收人工显式采纳的文章和资产；每条保留主题、主题簇、候选项和来源信息。
                </p>
                <div v-if="!evidenceBasket.length" class="empty-state">暂无已采纳文章证据。可从素材加工台文章详情加入当前项目。</div>
                <article v-for="item in evidenceBasket" :key="item.evidence_id || item.title" class="asset-summary-row">
                  <div>
                    <h3>{{ item.title || item.evidence_id }}</h3>
                    <p>{{ item.adoption_note || item.note || item.claim || '未填写采用理由' }}</p>
                    <div class="meta-line">
                      <span>{{ item.evidence_type || '证据' }}</span>
                      <span v-if="item.provenance?.topic_id">主题 {{ item.provenance.topic_id }}</span>
                      <span v-if="item.provenance?.cluster_id">主题簇 {{ item.provenance.cluster_id }}</span>
                      <span v-if="item.provenance?.candidate_id">候选项 {{ item.provenance.candidate_id }}</span>
                    </div>
                  </div>
                  <div class="article-actions">
                    <a v-if="item.provenance?.source_url" class="action-link" :href="item.provenance.source_url" target="_blank" rel="noreferrer">来源</a>
                    <RouterLink v-if="item.provenance?.candidate_id" class="action-link" :to="`/workspace/wiki-intake?candidate=${item.provenance.candidate_id}`">素材详情</RouterLink>
                    <RouterLink v-if="item.provenance?.topic_id" class="action-link" :to="`/workspace/wiki-topics/${item.provenance.topic_id}`">主题</RouterLink>
                    <RouterLink v-if="item.provenance?.cluster_id" class="action-link" :to="`/workspace/topic-clusters/${item.provenance.cluster_id}`">主题簇</RouterLink>
                  </div>
                </article>
              </section>

              <section id="concept-assets" class="project-section-card">
                <div class="panel-title">KFC 图谱资产与项目概念</div>
                <p class="section-copy mini-copy">
                  主题 / 概念加入项目必须人工确认；这里区分来自 KFC 主题的规范线索和项目内候选概念。
                </p>
                <div class="concept-asset-grid">
                  <article>
                    <h3>来自 KFC 主题的关键概念</h3>
                    <div v-if="!projectConcepts.length" class="empty-state">暂无项目概念。可先用下方样例显式加入。</div>
                    <div class="chip-wrap">
                      <span v-for="concept in projectConcepts" :key="concept.concept_id || concept.name" class="chip soft">
                        {{ concept.name || concept.title || concept.concept_id }}
                      </span>
                    </div>
                    <div class="chip-action-grid">
                      <button
                        v-for="concept in fallbackConcepts"
                        :key="concept"
                        class="btn-small"
                        type="button"
                        :disabled="projectConcepts.some((item) => (item.name || item.concept_id) === concept)"
                        @click="addConceptToProject(concept)"
                      >
                        + {{ concept }}
                      </button>
                    </div>
                  </article>
                  <article>
                    <h3>主题 / 方案 / 洞察线索</h3>
                    <div v-if="!projectThemes.length" class="empty-state">暂无主题关联。</div>
                    <div class="chip-wrap">
                      <span v-for="theme in projectThemes" :key="theme.theme_id || theme.name" class="chip soft">
                        {{ theme.name || theme.title || theme.theme_id }}
                      </span>
                    </div>
                    <button class="btn-small" type="button" @click="addThemeToProject('AI Agent 系统架构与上下文管理')">
                      + AI Agent 系统架构与上下文管理
                    </button>
                  </article>
                </div>
              </section>

              <section id="review-assets" class="project-section-card">
                <div class="panel-title">审核 / 快照</div>
                <div class="asset-strip compact">
                  <div><strong>{{ governanceReviews.length }}</strong><span>治理审核</span></div>
                  <div><strong>{{ researchSnapshots.length }}</strong><span>研究快照</span></div>
                  <div><strong>{{ reviewHistoryEntries.length }}</strong><span>审核记录</span></div>
                  <div><strong>{{ reviewAssetCount }}</strong><span>审阅资产</span></div>
                </div>
                <RouterLink class="action-link" to="/workspace/research/review">进入 审核工作台</RouterLink>
              </section>

              <LocalEvidencePackPanel
                :project-id="selectedProject.id"
                :pack="selectedProject.local_evidence_pack || emptyLocalEvidencePack"
                :loading="evidenceLoading"
                :searching="evidenceSearching"
                :reviewing-id="evidenceReviewingId"
                :error="evidenceError"
                @search="searchEvidencePack"
                @review="reviewEvidenceCandidate"
              />

              <CodexWritebackPanel
                :runs="writebackRuns"
                :consultations="writebackConsultations"
                :packs="writebackPacks"
                :loading="writebackLoading"
                :reviewing-id="writebackReviewingId"
                :error="writebackError"
                @review="reviewExternalEvidenceCandidate"
              />

              <StrategicSynthesisPanel
                :rows="synthesisRows"
                :cards="synthesisCards"
                :drafts="synthesisDrafts"
                :loading="synthesisLoading"
                :updating-id="synthesisUpdatingId"
                :error="synthesisError"
                @patch-row="patchEvidenceMatrixRow"
                @patch-card="patchInsightCard"
                @patch-draft="patchArtifactDraft"
              />

              <StrategicDecisionPanel
                :options="strategicOptions"
                :plans="validationPlans"
                :records="decisionRecords"
                :loading="decisionLoading"
                :updating="decisionUpdating"
                :error="decisionError"
                @create-option="createStrategicOptionSample"
                @update-option="patchStrategicOption"
                @create-plan="createValidationPlanSample"
                @update-plan="patchValidationPlan"
                @create-record="createLeadershipDecisionSample"
                @update-record="patchLeadershipDecisionRecord"
                @resolve-record-review="resolveLeadershipReview"
              />

              <LeadershipBriefingPanel
                :briefings="leadershipBriefings"
                :selected-briefing="selectedLeadershipBriefing"
                :loading="briefingLoading"
                :updating="briefingUpdating"
                :error="briefingError"
                @select-briefing="loadLeadershipBriefingDetail"
                @create-briefing="createLeadershipBriefingSample"
                @update-briefing="patchLeadershipBriefing"
                @add-review="addLeadershipBriefingReview"
                @resolve-review="resolveLeadershipBriefingReview"
              />

              <TraceabilityMapPanel
                :map="traceabilityMap"
                :filters="traceabilityFilters"
                :loading="traceabilityLoading"
                :error="traceabilityError"
                @update-filter="updateTraceabilityFilters"
                @refresh="loadTraceabilityMap(selectedProject.id)"
              />

              <GovernanceReviewPanel
                :reviews="governanceReviews"
                :selected-review="selectedGovernanceReview"
                :snapshot-attention-context="gateReviewSnapshotAttentionContext"
                :loading="governanceLoading"
                :updating="governanceUpdating"
                :error="governanceError"
                @select-review="loadGovernanceReviewDetail"
                @create-review="createGovernanceReviewSample"
                @update-review="patchGovernanceReview"
                @accept-risks="acceptGovernanceRisks"
                @block-review="blockGovernanceReview"
              />

              <ReviewHistoryPanel
                :entries="reviewHistoryEntries"
                :asset-entries="selectedAssetReviewHistory"
                :selected-asset="selectedReviewHistoryAsset"
                :loading="reviewHistoryLoading"
                :updating="reviewHistoryUpdating"
                :error="reviewHistoryError"
                :note-error="reviewHistoryNoteError"
                @refresh="loadReviewHistory(selectedProject.id)"
                @load-asset-history="loadAssetReviewHistory"
                @create-note="createReviewHistoryNoteForSelected"
              />

              <ResearchSnapshotPanel
                :snapshots="researchSnapshots"
                :selected-snapshot="selectedResearchSnapshot"
                :diff="researchSnapshotDiff"
                :review-notes="snapshotReviewNotes"
                :loading="snapshotLoading"
                :creating="snapshotCreating"
                :diffing="snapshotDiffing"
                :notes-loading="snapshotNotesLoading"
                :creating-note="snapshotNoteCreating"
                :updating-note="snapshotNoteUpdating"
                :error="snapshotError"
                :create-error="snapshotCreateError"
                :note-error="snapshotNoteError"
                @refresh="loadResearchSnapshots(selectedProject.id)"
                @create-snapshot="createResearchSnapshotForProject"
                @select-snapshot="loadResearchSnapshotDetail"
                @diff-snapshot="diffResearchSnapshotToCurrent"
                @create-review-note="createSnapshotReviewNoteForSelected"
                @update-review-note="updateSnapshotReviewNoteForSelected"
              />

              <MaterialWorkshopPanel
                :packs="artifactPacks"
                :loading="artifactPackLoading"
                :updating="artifactPackUpdating"
                :error="artifactPackError"
                @create-pack="createMaterialPack"
                @update-pack="updateMaterialPack"
                @add-item="addMaterialPackItem"
                @add-page="addMaterialPackPage"
                @add-file-ref="addMaterialPackFileRef"
                @add-review="addMaterialPackReview"
              />
            </template>
            <div v-else class="empty-state">选择一个研究项目查看定义</div>
          </div>
        </section>
      </template>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import CodexWritebackPanel from '../components/research/CodexWritebackPanel.vue'
import GovernanceReviewPanel from '../components/research/GovernanceReviewPanel.vue'
import LeadershipBriefingPanel from '../components/research/LeadershipBriefingPanel.vue'
import LocalEvidencePackPanel from '../components/research/LocalEvidencePackPanel.vue'
import MaterialWorkshopPanel from '../components/research/MaterialWorkshopPanel.vue'
import ResearchSnapshotPanel from '../components/research/ResearchSnapshotPanel.vue'
import ReviewHistoryPanel from '../components/research/ReviewHistoryPanel.vue'
import StrategicDecisionPanel from '../components/research/StrategicDecisionPanel.vue'
import StrategicSynthesisPanel from '../components/research/StrategicSynthesisPanel.vue'
import TraceabilityMapPanel from '../components/research/TraceabilityMapPanel.vue'
import { buildGateReviewSnapshotAttentionContext } from '../components/research/gateReviewSnapshotAttentionContext'
import {
  addArtifactPackFileRef,
  addArtifactPackItem,
  addArtifactPackPage,
  addArtifactPackReviewRound,
  createLeadershipBriefing,
  createLeadershipDecisionRecord,
  createArtifactPack,
  createGovernanceReview,
  createResearchProject,
  createResearchSnapshot,
  createSnapshotReviewNote,
  createReviewHistoryNote,
  createStrategicOption,
  createValidationPlan,
  diffResearchSnapshot,
  getAssetReviewHistory,
  getLocalEvidencePack,
  getGovernanceReview,
  getLeadershipBriefing,
  getResearchSnapshot,
  getTopicClusterAssetIndex,
  getTraceabilityMap,
  listLeadershipDecisionRecords,
  listLeadershipBriefings,
  listGovernanceReviews,
  listResearchSnapshots,
  listReviewHistory,
  listArtifactDrafts,
  listArtifactPacks,
  listConsultationLogs,
  listEvidenceMatrixRows,
  listExternalResearchPacks,
  listInsightCards,
  listResearchProjects,
  listResearchRuns,
  listStrategicOptions,
  listSnapshotReviewNotes,
  listTopicClustersWithAggregation,
  listValidationPlans,
  searchLocalEvidencePack,
  updateLeadershipDecisionRecord,
  updateLeadershipBriefing,
  updateGovernanceReview,
  updateArtifactDraft,
  updateArtifactPack,
  updateEvidenceMatrixRow,
  updateExternalResearchCandidate,
  updateInsightCard,
  updateLocalEvidenceCandidate,
  updateResearchProject,
  updateSnapshotReviewNote,
  updateStrategicOption,
  updateValidationPlan,
} from '../data/dataClient'
import { setCurrentResearchProject } from '../utils/currentResearchProjectContext'

const crumbs = [
  { label: '研究资产', to: '/workspace/research' },
  { label: '战略研究项目' },
]

const sampleProject = {
  title: '华为云 Agent-ready 企业软件栈战略研究',
  background: '研究华为云在 Agent-ready 企业软件栈中的控制点、试点路径和材料输入。',
  audience: '华为云战略部二层领导',
  goal: '形成战略判断、试点路径和汇报材料输入。',
}

const route = useRoute()
const router = useRouter()

const projects = ref([])
const selectedId = ref('')
const loading = ref(false)
const creating = ref(false)
const error = ref('')
const createError = ref('')
const evidenceLoading = ref(false)
const evidenceSearching = ref(false)
const evidenceReviewingId = ref('')
const evidenceError = ref('')
const writebackLoading = ref(false)
const writebackReviewingId = ref('')
const writebackError = ref('')
const writebackRuns = ref([])
const writebackConsultations = ref([])
const writebackPacks = ref([])
const synthesisLoading = ref(false)
const synthesisUpdatingId = ref('')
const synthesisError = ref('')
const synthesisRows = ref([])
const synthesisCards = ref([])
const synthesisDrafts = ref([])
const artifactPackLoading = ref(false)
const artifactPackUpdating = ref(false)
const artifactPackError = ref('')
const artifactPacks = ref([])
const decisionLoading = ref(false)
const decisionUpdating = ref(false)
const decisionError = ref('')
const strategicOptions = ref([])
const validationPlans = ref([])
const decisionRecords = ref([])
const briefingLoading = ref(false)
const briefingUpdating = ref(false)
const briefingError = ref('')
const leadershipBriefings = ref([])
const selectedLeadershipBriefing = ref(null)
const traceabilityLoading = ref(false)
const traceabilityError = ref('')
const traceabilityMap = ref({ nodes: [], edges: [], issues: [], lanes: [], summary: {} })
const traceabilityFilters = ref({ briefing_id: '', asset_type: '', issue_severity: '' })
const governanceLoading = ref(false)
const governanceUpdating = ref(false)
const governanceError = ref('')
const governanceReviews = ref([])
const selectedGovernanceReview = ref(null)
const reviewHistoryLoading = ref(false)
const reviewHistoryUpdating = ref(false)
const reviewHistoryError = ref('')
const reviewHistoryNoteError = ref('')
const reviewHistoryEntries = ref([])
const selectedAssetReviewHistory = ref([])
const snapshotLoading = ref(false)
const snapshotCreating = ref(false)
const snapshotDiffing = ref(false)
const snapshotError = ref('')
const snapshotCreateError = ref('')
const snapshotNoteError = ref('')
const researchSnapshots = ref([])
const selectedResearchSnapshot = ref(null)
const researchSnapshotDiff = ref(null)
const snapshotReviewNotes = ref([])
const snapshotNotesLoading = ref(false)
const snapshotNoteCreating = ref(false)
const snapshotNoteUpdating = ref(false)
const researchMapLoading = ref(false)
const researchMapError = ref('')
const researchMapCandidates = ref([])
const form = reactive({ ...sampleProject })
const emptyLocalEvidencePack = {
  status: 'not_generated',
  candidates: [],
  accepted_evidence_ids: [],
  rejected_evidence_ids: [],
  summary: {
    candidate_count: 0,
    accepted_count: 0,
    degraded_count: 0,
    source_project_count: 0,
    concept_count: 0,
    theme_count: 0,
  },
}

const selectedProject = computed(() => projects.value.find((item) => item.id === selectedId.value) || null)
const linkedTopicClusters = computed(() => selectedProject.value?.linked_topic_clusters || [])
const linkedClusterIds = computed(() => new Set(linkedTopicClusters.value.map((item) => item.cluster_id)))
const evidenceBasket = computed(() => selectedProject.value?.evidence_items || [])
const projectConcepts = computed(() => selectedProject.value?.linked_concepts || [])
const projectThemes = computed(() => selectedProject.value?.linked_themes || [])
const reviewAssetCount = computed(() => (
  (governanceReviews.value?.length || 0)
  + (researchSnapshots.value?.length || 0)
  + (reviewHistoryEntries.value?.length || 0)
))
const selectedReviewHistoryAsset = computed(() => {
  const review = selectedGovernanceReview.value
  if (!review?.review_id) return null
  return {
    asset_type: 'governance_review',
    asset_id: review.review_id,
    asset_title: review.title,
  }
})
const snapshotNotesBySnapshotId = computed(() => {
  const snapshotId = selectedResearchSnapshot.value?.snapshot_id
  return snapshotId ? { [snapshotId]: snapshotReviewNotes.value } : {}
})
const gateReviewSnapshotAttentionContext = computed(() => buildGateReviewSnapshotAttentionContext({
  governanceReview: selectedGovernanceReview.value,
  snapshots: researchSnapshots.value,
  notesBySnapshotId: snapshotNotesBySnapshotId.value,
}))

const desiredResearchClusterIds = [
  'tc_wiki_agent-harness',
  'tc_wiki_ai-tokenization',
  'tc_wiki_ai-cloud-infrastructure',
  'tc_wiki_ai-infrastructure-market',
  'tc_wiki_ai-commercialization',
]

const fallbackConcepts = [
  'MCP',
  'Agent',
  'Context Engineering',
  'Tool Search',
  'Hooks / Skills / Plugins / MCP 四层架构',
  'Agent-ready 企业软件栈',
]

function normalizeProjects(response) {
  const data = response?.data || {}
  return Array.isArray(data.projects) ? data.projects : []
}

async function loadProjects() {
  loading.value = true
  error.value = ''
  try {
    const response = await listResearchProjects()
    projects.value = normalizeProjects(response)
    const requestedId = String(route.query.project || '')
    if (requestedId && projects.value.some((item) => item.id === requestedId)) {
      selectedId.value = requestedId
    } else if (!selectedId.value && projects.value.length) {
      selectedId.value = projects.value[0].id
    }
  } catch (err) {
    error.value = err.message || '战略研究项目加载失败'
  } finally {
    loading.value = false
  }
}

function buildResearchClusterCandidate(cluster, assetIndex = null) {
  const counts = assetIndex?.counts || cluster.counts || {}
  const queryTerms = assetIndex?.query_terms || []
  const articles = assetIndex?.indirect_assets?.articles || []
  return {
    cluster_id: cluster.cluster_id,
    title: cluster.title || cluster.cluster_id,
    relevance_reason: '命中 Agent-ready、Agent Harness、企业软件栈、云基础设施等研究关键词，适合作为当前战略研究的人工候选主题簇。',
    hit_terms: queryTerms.filter((term) => ['agent', 'harness', 'context', 'engineering', 'cloud', 'infrastructure', 'commercialization', 'token'].includes(String(term).toLowerCase())).slice(0, 6),
    wiki_topic_count: counts.direct_wiki_topic_count ?? cluster.counts?.wiki_topics ?? 0,
    article_count: counts.indirect_article_count ?? cluster.counts?.articles ?? articles.length ?? 0,
    theme_count: (counts.direct_kfc_theme_count || 0) + (counts.candidate_theme_count || 0),
    concept_count: counts.candidate_concept_count || 0,
    asset_index: assetIndex,
  }
}

async function loadResearchMapCandidates() {
  researchMapLoading.value = true
  researchMapError.value = ''
  try {
    const response = await listTopicClustersWithAggregation()
    const clusters = response?.data?.clusters || response?.data?.items || []
    const selected = desiredResearchClusterIds
      .map((clusterId) => clusters.find((item) => item.cluster_id === clusterId))
      .filter(Boolean)
    const withAssets = await Promise.all(selected.map(async (cluster) => {
      try {
        const assetResponse = await getTopicClusterAssetIndex(cluster.cluster_id)
        return buildResearchClusterCandidate(cluster, assetResponse?.data || null)
      } catch {
        return buildResearchClusterCandidate(cluster)
      }
    }))
    researchMapCandidates.value = withAssets
  } catch (err) {
    researchMapError.value = err.message || '研究地图候选加载失败'
  } finally {
    researchMapLoading.value = false
  }
}

function patchSelectedProject(patch) {
  if (!selectedId.value) return
  projects.value = projects.value.map((item) => (
    item.id === selectedId.value ? { ...item, ...patch } : item
  ))
}

async function patchCurrentProject(patch) {
  if (!selectedProject.value?.id) return null
  const response = await updateResearchProject(selectedProject.value.id, patch)
  const updated = response?.data || null
  if (updated?.id) {
    projects.value = projects.value.map((item) => (item.id === updated.id ? updated : item))
    setCurrentResearchProject(updated)
  }
  return updated
}

async function linkClusterToProject(candidate) {
  if (!selectedProject.value?.id || !candidate?.cluster_id || linkedClusterIds.value.has(candidate.cluster_id)) return
  const next = [
    ...linkedTopicClusters.value,
    {
      cluster_id: candidate.cluster_id,
      title: candidate.title,
      article_count: candidate.article_count,
      wiki_topic_count: candidate.wiki_topic_count,
      theme_count: candidate.theme_count,
      concept_count: candidate.concept_count,
      rationale: candidate.relevance_reason,
      linked_by: 'human',
      linked_from: 'research_map',
      linked_at: new Date().toISOString(),
    },
  ]
  await patchCurrentProject({ linked_topic_clusters: next })
}

async function addConceptToProject(name) {
  if (!selectedProject.value?.id || !name) return
  if (projectConcepts.value.some((item) => (item.name || item.concept_id) === name)) return
  await patchCurrentProject({
    linked_concepts: [
      ...projectConcepts.value,
      {
        concept_id: name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, ''),
        name,
        source: {
          registry: 'concept_registry_or_project_concept',
          theme: 'AI Agent 系统架构与上下文管理',
          cluster_ids: Array.from(linkedClusterIds.value),
        },
        status: 'candidate',
        canonical_status: name === 'MCP' || name === 'Agent' ? 'canonical_candidate' : 'project_scoped',
        linked_by: 'human',
      },
    ],
  })
}

async function addThemeToProject(name) {
  if (!selectedProject.value?.id || !name) return
  if (projectThemes.value.some((item) => (item.name || item.theme_id) === name)) return
  await patchCurrentProject({
    linked_themes: [
      ...projectThemes.value,
      {
        theme_id: name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, ''),
        name,
        source: {
          registry: 'global_theme_registry',
          cluster_ids: Array.from(linkedClusterIds.value),
        },
        status: 'candidate',
        linked_by: 'human',
      },
    ],
  })
}

async function loadEvidencePack(projectId) {
  if (!projectId) return
  evidenceLoading.value = true
  evidenceError.value = ''
  try {
    const response = await getLocalEvidencePack(projectId)
    if (selectedId.value === projectId) {
      patchSelectedProject({
        local_evidence_pack: response?.data?.local_evidence_pack || emptyLocalEvidencePack,
      })
    }
  } catch (err) {
    evidenceError.value = err.message || '本地证据包读取失败'
  } finally {
    if (selectedId.value === projectId) {
      evidenceLoading.value = false
    }
  }
}

async function loadWritebackAssets(projectId) {
  if (!projectId) return
  writebackLoading.value = true
  writebackError.value = ''
  try {
    const [runs, consultations, packs] = await Promise.all([
      listResearchRuns(projectId),
      listConsultationLogs(projectId),
      listExternalResearchPacks(projectId),
    ])
    if (selectedId.value === projectId) {
      writebackRuns.value = runs?.data?.research_runs || []
      writebackConsultations.value = consultations?.data?.consultation_logs || []
      writebackPacks.value = packs?.data?.external_research_packs || []
    }
  } catch (err) {
    writebackError.value = err.message || 'Codex 写回资产读取失败'
  } finally {
    if (selectedId.value === projectId) {
      writebackLoading.value = false
    }
  }
}

async function loadSynthesisAssets(projectId) {
  if (!projectId) return
  synthesisLoading.value = true
  synthesisError.value = ''
  try {
    const [rows, cards, drafts] = await Promise.all([
      listEvidenceMatrixRows(projectId),
      listInsightCards(projectId),
      listArtifactDrafts(projectId),
    ])
    if (selectedId.value === projectId) {
      synthesisRows.value = rows?.data?.rows || []
      synthesisCards.value = cards?.data?.insight_cards || []
      synthesisDrafts.value = drafts?.data?.artifact_drafts || []
      patchSelectedProject({
        evidence_matrix_rows: synthesisRows.value,
        insight_cards: synthesisCards.value,
        artifact_drafts: synthesisDrafts.value,
      })
    }
  } catch (err) {
    synthesisError.value = err.message || '战略合成资产读取失败'
  } finally {
    if (selectedId.value === projectId) {
      synthesisLoading.value = false
    }
  }
}

async function loadArtifactPacks(projectId) {
  if (!projectId) return
  artifactPackLoading.value = true
  artifactPackError.value = ''
  try {
    const response = await listArtifactPacks(projectId)
    if (selectedId.value === projectId) {
      artifactPacks.value = response?.data?.artifact_packs || []
      patchSelectedProject({ artifact_packs: artifactPacks.value })
    }
  } catch (err) {
    artifactPackError.value = err.message || '材料包读取失败'
  } finally {
    if (selectedId.value === projectId) {
      artifactPackLoading.value = false
    }
  }
}

async function loadDecisionAssets(projectId) {
  if (!projectId) return
  decisionLoading.value = true
  decisionError.value = ''
  try {
    const [options, plans, records] = await Promise.all([
      listStrategicOptions(projectId),
      listValidationPlans(projectId),
      listLeadershipDecisionRecords(projectId),
    ])
    if (selectedId.value === projectId) {
      strategicOptions.value = options?.data?.strategic_options || []
      validationPlans.value = plans?.data?.validation_plans || []
      decisionRecords.value = records?.data?.leadership_decision_records || []
      patchSelectedProject({
        strategic_options: strategicOptions.value,
        validation_plans: validationPlans.value,
        leadership_decision_records: decisionRecords.value,
      })
    }
  } catch (err) {
    decisionError.value = err.message || '战略决策资产读取失败'
  } finally {
    if (selectedId.value === projectId) {
      decisionLoading.value = false
    }
  }
}

async function loadLeadershipBriefings(projectId) {
  if (!projectId) return
  briefingLoading.value = true
  briefingError.value = ''
  try {
    const response = await listLeadershipBriefings(projectId)
    if (selectedId.value === projectId) {
      leadershipBriefings.value = response?.data?.leadership_briefings || []
      patchSelectedProject({ leadership_briefings: leadershipBriefings.value })
      const firstId = leadershipBriefings.value[0]?.briefing_id
      if (firstId) {
        await loadLeadershipBriefingDetail(firstId)
      } else {
        selectedLeadershipBriefing.value = null
      }
    }
  } catch (err) {
    briefingError.value = err.message || '领导汇报读取失败'
  } finally {
    if (selectedId.value === projectId) {
      briefingLoading.value = false
    }
  }
}

async function loadLeadershipBriefingDetail(briefingId) {
  if (!selectedProject.value?.id || !briefingId) return
  briefingError.value = ''
  try {
    const response = await getLeadershipBriefing(selectedProject.value.id, briefingId)
    selectedLeadershipBriefing.value = response?.data?.leadership_briefing || null
  } catch (err) {
    briefingError.value = err.message || '领导汇报详情读取失败'
  }
}

async function loadTraceabilityMap(projectId, filters = traceabilityFilters.value) {
  if (!projectId) return
  traceabilityLoading.value = true
  traceabilityError.value = ''
  try {
    const params = Object.fromEntries(
      Object.entries(filters || {}).filter(([, value]) => String(value || '').trim()),
    )
    const response = await getTraceabilityMap(projectId, params)
    if (selectedId.value === projectId) {
      traceabilityMap.value = response?.data || { nodes: [], edges: [], issues: [], lanes: [], summary: {} }
    }
  } catch (err) {
    traceabilityError.value = err.message || '追踪图读取失败'
  } finally {
    if (selectedId.value === projectId) {
      traceabilityLoading.value = false
    }
  }
}

async function loadGovernanceReviews(projectId) {
  if (!projectId) return
  governanceLoading.value = true
  governanceError.value = ''
  try {
    const response = await listGovernanceReviews(projectId)
    if (selectedId.value === projectId) {
      governanceReviews.value = response?.data?.governance_reviews || []
      patchSelectedProject({ governance_reviews: governanceReviews.value })
      const firstId = governanceReviews.value[0]?.review_id
      if (firstId) {
        await loadGovernanceReviewDetail(firstId)
      } else {
        selectedGovernanceReview.value = null
      }
    }
  } catch (err) {
    governanceError.value = err.message || '治理审查读取失败'
  } finally {
    if (selectedId.value === projectId) {
      governanceLoading.value = false
    }
  }
}

async function loadGovernanceReviewDetail(reviewId) {
  if (!selectedProject.value?.id || !reviewId) return
  governanceError.value = ''
  try {
    const response = await getGovernanceReview(selectedProject.value.id, reviewId)
    selectedGovernanceReview.value = response?.data?.governance_review || null
    await loadAssetReviewHistory(selectedReviewHistoryAsset.value)
  } catch (err) {
    governanceError.value = err.message || '治理审查详情读取失败'
  }
}

async function loadReviewHistory(projectId) {
  if (!projectId) return
  reviewHistoryLoading.value = true
  reviewHistoryError.value = ''
  try {
    const response = await listReviewHistory(projectId, { limit: 50 })
    if (selectedId.value === projectId) {
      reviewHistoryEntries.value = response?.data?.review_history_entries || []
    }
  } catch (err) {
    reviewHistoryError.value = err.message || '审查历史读取失败'
  } finally {
    if (selectedId.value === projectId) {
      reviewHistoryLoading.value = false
    }
  }
}

async function loadAssetReviewHistory(asset = selectedReviewHistoryAsset.value) {
  if (!selectedProject.value?.id || !asset?.asset_type || !asset?.asset_id) return
  reviewHistoryError.value = ''
  try {
    const response = await getAssetReviewHistory(
      selectedProject.value.id,
      asset.asset_type,
      asset.asset_id,
      { limit: 100 },
    )
    selectedAssetReviewHistory.value = response?.data?.review_history_entries || []
  } catch (err) {
    reviewHistoryError.value = err.message || '资产审查历史读取失败'
  }
}

async function createReviewHistoryNoteForSelected(payload) {
  if (!selectedProject.value?.id || !payload?.asset_type || !payload?.asset_id) return
  reviewHistoryUpdating.value = true
  reviewHistoryNoteError.value = ''
  try {
    const response = await createReviewHistoryNote(selectedProject.value.id, {
      asset_type: payload.asset_type,
      asset_id: payload.asset_id,
      note: payload.note,
      actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    })
    const entry = response?.data?.review_history_entry
    if (entry?.history_entry_id) {
      reviewHistoryEntries.value = [entry, ...reviewHistoryEntries.value.filter((item) => item.history_entry_id !== entry.history_entry_id)]
      selectedAssetReviewHistory.value = [entry, ...selectedAssetReviewHistory.value.filter((item) => item.history_entry_id !== entry.history_entry_id)]
    }
  } catch (err) {
    reviewHistoryNoteError.value = err.message || '人工备注记录失败'
  } finally {
    reviewHistoryUpdating.value = false
  }
}

async function loadResearchSnapshots(projectId) {
  if (!projectId) return
  snapshotLoading.value = true
  snapshotError.value = ''
  try {
    const response = await listResearchSnapshots(projectId)
    if (selectedId.value === projectId) {
      researchSnapshots.value = response?.data?.snapshots || []
      patchSelectedProject({ research_snapshots: researchSnapshots.value })
      const firstId = researchSnapshots.value[0]?.snapshot_id
      if (firstId) {
        await loadResearchSnapshotDetail(firstId)
      } else {
        selectedResearchSnapshot.value = null
        researchSnapshotDiff.value = null
        snapshotReviewNotes.value = []
      }
    }
  } catch (err) {
    snapshotError.value = err.message || '基线快照读取失败'
  } finally {
    if (selectedId.value === projectId) {
      snapshotLoading.value = false
    }
  }
}

async function loadResearchSnapshotDetail(snapshotId) {
  if (!selectedProject.value?.id || !snapshotId) return
  snapshotError.value = ''
  try {
    const response = await getResearchSnapshot(selectedProject.value.id, snapshotId)
    selectedResearchSnapshot.value = response?.data?.snapshot || null
    researchSnapshotDiff.value = null
    await loadSnapshotReviewNotes(snapshotId)
  } catch (err) {
    snapshotError.value = err.message || '基线快照详情读取失败'
  }
}

async function loadSnapshotReviewNotes(snapshotId = selectedResearchSnapshot.value?.snapshot_id) {
  if (!selectedProject.value?.id || !snapshotId) return
  snapshotNotesLoading.value = true
  snapshotNoteError.value = ''
  try {
    const response = await listSnapshotReviewNotes(selectedProject.value.id, snapshotId)
    snapshotReviewNotes.value = response?.data?.snapshot_review_notes || []
  } catch (err) {
    snapshotNoteError.value = err.message || '快照审阅备注读取失败'
  } finally {
    snapshotNotesLoading.value = false
  }
}

async function createResearchSnapshotForProject(payload) {
  if (!selectedProject.value?.id) return
  snapshotCreating.value = true
  snapshotCreateError.value = ''
  try {
    const response = await createResearchSnapshot(selectedProject.value.id, {
      ...payload,
      actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
      governance_review_id: selectedGovernanceReview.value?.review_id || '',
    })
    const snapshot = response?.data?.snapshot
    if (snapshot?.snapshot_id) {
      selectedResearchSnapshot.value = snapshot
      snapshotReviewNotes.value = []
      const indexItem = researchSnapshotIndex(snapshot)
      researchSnapshots.value = [
        indexItem,
        ...researchSnapshots.value.filter((item) => item.snapshot_id !== snapshot.snapshot_id),
      ]
      patchSelectedProject({ research_snapshots: researchSnapshots.value })
      await loadReviewHistory(selectedProject.value.id)
    }
  } catch (err) {
    snapshotCreateError.value = err.message || '基线快照创建失败'
  } finally {
    snapshotCreating.value = false
  }
}

async function createSnapshotReviewNoteForSelected(payload) {
  if (!selectedProject.value?.id || !selectedResearchSnapshot.value?.snapshot_id) return
  snapshotNoteCreating.value = true
  snapshotNoteError.value = ''
  try {
    const response = await createSnapshotReviewNote(
      selectedProject.value.id,
      selectedResearchSnapshot.value.snapshot_id,
      {
        ...payload,
        actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
      },
    )
    const note = response?.data?.snapshot_review_note
    if (note?.note_id) {
      snapshotReviewNotes.value = [
        note,
        ...snapshotReviewNotes.value.filter((item) => item.note_id !== note.note_id),
      ]
      await loadReviewHistory(selectedProject.value.id)
    }
  } catch (err) {
    snapshotNoteError.value = err.message || '快照审阅备注创建失败'
  } finally {
    snapshotNoteCreating.value = false
  }
}

async function updateSnapshotReviewNoteForSelected(payload) {
  if (!selectedProject.value?.id || !selectedResearchSnapshot.value?.snapshot_id || !payload?.note_id) return
  snapshotNoteUpdating.value = true
  snapshotNoteError.value = ''
  try {
    const response = await updateSnapshotReviewNote(
      selectedProject.value.id,
      selectedResearchSnapshot.value.snapshot_id,
      payload.note_id,
      {
        status: payload.status,
        owner: payload.owner,
        resolution_note: payload.resolution_note,
        actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
      },
    )
    const note = response?.data?.snapshot_review_note
    if (note?.note_id) {
      snapshotReviewNotes.value = snapshotReviewNotes.value.map((item) => (
        item.note_id === note.note_id ? note : item
      ))
      await loadReviewHistory(selectedProject.value.id)
    }
  } catch (err) {
    snapshotNoteError.value = err.message || '快照审阅备注处置更新失败'
  } finally {
    snapshotNoteUpdating.value = false
  }
}

async function diffResearchSnapshotToCurrent(snapshotId) {
  if (!selectedProject.value?.id || !snapshotId) return
  snapshotDiffing.value = true
  snapshotError.value = ''
  try {
    const response = await diffResearchSnapshot(selectedProject.value.id, snapshotId)
    researchSnapshotDiff.value = response?.data?.snapshot_diff || null
  } catch (err) {
    snapshotError.value = err.message || '基线快照对比失败'
  } finally {
    snapshotDiffing.value = false
  }
}

function updateTraceabilityFilters(filters) {
  traceabilityFilters.value = filters
  if (selectedProject.value?.id) {
    loadTraceabilityMap(selectedProject.value.id, filters)
  }
}

function fillSample() {
  Object.assign(form, sampleProject)
}

function selectProject(projectId) {
  selectedId.value = projectId
  const project = projects.value.find((item) => item.id === projectId)
  if (project) setCurrentResearchProject(project)
  router.replace({ path: '/workspace/research', query: { project: projectId } })
}

async function searchEvidencePack() {
  if (!selectedProject.value?.id) return
  const projectId = selectedProject.value.id
  evidenceSearching.value = true
  evidenceError.value = ''
  try {
    const response = await searchLocalEvidencePack(projectId, {
      keywords: [],
      limit: 30,
      include_degraded: true,
    })
    patchSelectedProject({
      local_evidence_pack: response?.data?.local_evidence_pack || emptyLocalEvidencePack,
    })
  } catch (err) {
    evidenceError.value = err.message || '本地证据检索失败'
  } finally {
    evidenceSearching.value = false
  }
}

async function reviewEvidenceCandidate(evidenceId, status) {
  if (!selectedProject.value?.id || !evidenceId) return
  const projectId = selectedProject.value.id
  evidenceReviewingId.value = evidenceId
  evidenceError.value = ''
  try {
    const response = await updateLocalEvidenceCandidate(projectId, evidenceId, {
      status,
      note: '',
    })
    patchSelectedProject({
      local_evidence_pack: response?.data?.local_evidence_pack || emptyLocalEvidencePack,
      evidence_items: response?.data?.evidence_items || [],
    })
  } catch (err) {
    evidenceError.value = err.message || '本地证据状态更新失败'
  } finally {
    evidenceReviewingId.value = ''
  }
}

async function reviewExternalEvidenceCandidate(packId, candidateId, reviewStatus) {
  if (!selectedProject.value?.id || !packId || !candidateId) return
  const projectId = selectedProject.value.id
  writebackReviewingId.value = candidateId
  writebackError.value = ''
  try {
    const response = await updateExternalResearchCandidate(projectId, packId, candidateId, {
      review_status: reviewStatus,
      review_note: '',
    })
    const updatedPack = response?.data?.external_research_pack
    if (updatedPack?.pack_id) {
      writebackPacks.value = writebackPacks.value.map((pack) => (
        pack.pack_id === updatedPack.pack_id ? updatedPack : pack
      ))
      patchSelectedProject({
        evidence_items: response?.data?.evidence_items || [],
      })
    }
  } catch (err) {
    writebackError.value = err.message || '外部证据状态更新失败'
  } finally {
    writebackReviewingId.value = ''
  }
}

async function patchEvidenceMatrixRow(rowId, patch) {
  if (!selectedProject.value?.id || !rowId) return
  const projectId = selectedProject.value.id
  synthesisUpdatingId.value = rowId
  synthesisError.value = ''
  try {
    const response = await updateEvidenceMatrixRow(projectId, rowId, patch)
    const row = response?.data?.row
    if (row?.id) {
      synthesisRows.value = synthesisRows.value.map((item) => (item.id === row.id ? row : item))
      patchSelectedProject({ evidence_matrix_rows: synthesisRows.value })
    }
  } catch (err) {
    synthesisError.value = err.message || '证据矩阵状态更新失败'
  } finally {
    synthesisUpdatingId.value = ''
  }
}

async function patchInsightCard(cardId, patch) {
  if (!selectedProject.value?.id || !cardId) return
  const projectId = selectedProject.value.id
  synthesisUpdatingId.value = cardId
  synthesisError.value = ''
  try {
    const response = await updateInsightCard(projectId, cardId, patch)
    const card = response?.data?.insight_card
    if (card?.id) {
      synthesisCards.value = synthesisCards.value.map((item) => (item.id === card.id ? card : item))
      patchSelectedProject({ insight_cards: synthesisCards.value })
    }
  } catch (err) {
    synthesisError.value = err.message || '洞察卡片状态更新失败'
  } finally {
    synthesisUpdatingId.value = ''
  }
}

async function patchArtifactDraft(draftId, patch) {
  if (!selectedProject.value?.id || !draftId) return
  const projectId = selectedProject.value.id
  synthesisUpdatingId.value = draftId
  synthesisError.value = ''
  try {
    const response = await updateArtifactDraft(projectId, draftId, patch)
    const draft = response?.data?.artifact_draft
    if (draft?.id) {
      synthesisDrafts.value = synthesisDrafts.value.map((item) => (item.id === draft.id ? draft : item))
      patchSelectedProject({ artifact_drafts: synthesisDrafts.value })
    }
  } catch (err) {
    synthesisError.value = err.message || '材料草稿状态更新失败'
  } finally {
    synthesisUpdatingId.value = ''
  }
}

function firstEvidenceIds() {
  return (selectedProject.value?.evidence_items || [])
    .filter((item) => item.status === 'accepted' || item.review_status === 'accepted')
    .map((item) => item.evidence_id)
    .slice(0, 2)
}

function replacePack(pack) {
  if (!pack?.pack_id) return
  artifactPacks.value = [
    pack,
    ...artifactPacks.value.filter((item) => item.pack_id !== pack.pack_id),
  ]
  patchSelectedProject({ artifact_packs: artifactPacks.value })
}

function replaceStrategicOption(option) {
  if (!option?.option_id) return
  strategicOptions.value = [
    option,
    ...strategicOptions.value.filter((item) => item.option_id !== option.option_id),
  ]
  patchSelectedProject({ strategic_options: strategicOptions.value })
}

function replaceValidationPlan(plan) {
  if (!plan?.plan_id) return
  validationPlans.value = [
    plan,
    ...validationPlans.value.filter((item) => item.plan_id !== plan.plan_id),
  ]
  patchSelectedProject({ validation_plans: validationPlans.value })
}

function replaceDecisionRecord(record) {
  if (!record?.decision_id) return
  decisionRecords.value = [
    record,
    ...decisionRecords.value.filter((item) => item.decision_id !== record.decision_id),
  ]
  patchSelectedProject({ leadership_decision_records: decisionRecords.value })
}

function briefingIndex(briefing) {
  if (!briefing?.briefing_id) return null
  return {
    briefing_id: briefing.briefing_id,
    title: briefing.title,
    briefing_type: briefing.briefing_type,
    audience: briefing.audience,
    status: briefing.status,
    readiness: briefing.readiness,
    section_count: briefing.sections?.length || 0,
    source_counts: briefing.source_counts || {},
    created_at: briefing.created_at,
    updated_at: briefing.updated_at,
  }
}

function replaceLeadershipBriefing(briefing) {
  if (!briefing?.briefing_id) return
  selectedLeadershipBriefing.value = briefing
  const indexItem = briefingIndex(briefing)
  leadershipBriefings.value = [
    indexItem,
    ...leadershipBriefings.value.filter((item) => item.briefing_id !== briefing.briefing_id),
  ]
  patchSelectedProject({ leadership_briefings: leadershipBriefings.value })
}

function governanceReviewIndex(review) {
  if (!review?.review_id) return null
  const summary = review.review_summary || {}
  return {
    review_id: review.review_id,
    title: review.title,
    review_type: review.review_type,
    status: review.status,
    gate_decision: review.gate_decision,
    readiness: review.readiness,
    checklist_count: review.checklist_items?.length || 0,
    finding_count: review.findings?.length || 0,
    signoff_count: review.signoffs?.length || 0,
    blocker_count: summary.blocker_count || 0,
    major_open_count: summary.major_open_count || 0,
    failed_required_count: summary.failed_required_count || 0,
    ready_for_next_stage: summary.ready_for_next_stage === true,
    created_at: review.created_at,
    updated_at: review.updated_at,
  }
}

function replaceGovernanceReview(review) {
  if (!review?.review_id) return
  selectedGovernanceReview.value = review
  const indexItem = governanceReviewIndex(review)
  governanceReviews.value = [
    indexItem,
    ...governanceReviews.value.filter((item) => item.review_id !== review.review_id),
  ]
  patchSelectedProject({ governance_reviews: governanceReviews.value })
}

function researchSnapshotIndex(snapshot) {
  if (!snapshot?.snapshot_id) return null
  return {
    snapshot_id: snapshot.snapshot_id,
    title: snapshot.title,
    reason: snapshot.reason,
    gate_type: snapshot.gate_type,
    actor: snapshot.actor || {},
    included_asset_kinds: snapshot.included_asset_kinds || [],
    asset_counts: Object.fromEntries(
      Object.entries(snapshot.asset_kind_summaries || {}).map(([kind, summary]) => [kind, summary.count || 0]),
    ),
    linked_governance_review: snapshot.linked_governance_review || {},
    linked_leadership_briefing: snapshot.linked_leadership_briefing || {},
    review_history_watermark: snapshot.review_history_watermark || {},
    snapshot_fingerprint: snapshot.snapshot_fingerprint,
    created_at: snapshot.created_at,
  }
}

async function createStrategicOptionSample() {
  if (!selectedProject.value?.id) return
  const card = synthesisCards.value[0]
  const row = synthesisRows.value[0]
  const draft = synthesisDrafts.value[0]
  const pack = artifactPacks.value[0]
  decisionUpdating.value = true
  decisionError.value = ''
  try {
    const response = await createStrategicOption(selectedProject.value.id, {
      idempotency_key: `strategic-option-${selectedProject.value.id}-${strategicOptions.value.length + 1}`,
      title: 'L2 Agent-ready 适配层 + L4 企业级 Harness 作为战略控制点',
      summary: '将企业系统适配层和执行治理 Harness 作为华为云 Agent-ready 软件栈的战略控制点。',
      recommendation_level: 'recommended',
      decision_posture: 'need_validation',
      source_insight_ids: card?.id ? [card.id] : [],
      source_evidence_matrix_row_ids: row?.id ? [row.id] : [],
      source_evidence_ids: firstEvidenceIds(),
      source_artifact_draft_ids: draft?.id ? [draft.id] : [],
      source_artifact_pack_ids: pack?.pack_id ? [pack.pack_id] : [],
      risks: [{ statement: '首客深交付可能难以平台化复用。', severity: 'high', mitigation: '用 90 天试点验证复用率。' }],
      success_metrics: [{ name: 'harness_reuse_ratio', target: '>= 60%' }],
    })
    replaceStrategicOption(response?.data?.strategic_option)
  } catch (err) {
    decisionError.value = err.message || '战略选项创建失败'
  } finally {
    decisionUpdating.value = false
  }
}

async function patchStrategicOption(optionId, patch) {
  if (!selectedProject.value?.id || !optionId) return
  decisionUpdating.value = true
  decisionError.value = ''
  try {
    const response = await updateStrategicOption(selectedProject.value.id, optionId, patch)
    replaceStrategicOption(response?.data?.strategic_option)
  } catch (err) {
    decisionError.value = err.message || '战略选项更新失败'
  } finally {
    decisionUpdating.value = false
  }
}

async function createValidationPlanSample(optionId) {
  if (!selectedProject.value?.id || !optionId) return
  const pack = artifactPacks.value[0]
  decisionUpdating.value = true
  decisionError.value = ''
  try {
    const response = await createValidationPlan(selectedProject.value.id, {
      idempotency_key: `validation-plan-${selectedProject.value.id}-${validationPlans.value.length + 1}`,
      title: '90-day ERP/Test Harness pilot validation',
      summary: '验证企业级 Agent Harness 是否能成为华为云 Agent-ready 软件栈控制点。',
      linked_option_ids: [optionId],
      source_insight_ids: synthesisCards.value[0]?.id ? [synthesisCards.value[0].id] : [],
      source_evidence_ids: firstEvidenceIds().slice(0, 1),
      source_artifact_pack_ids: pack?.pack_id ? [pack.pack_id] : [],
      validation_questions: [
        { question: '客户是否愿意接入真实权限和审批？', priority: 'high' },
        { question: 'Harness 资产是否能在第二客户复用？', priority: 'high' },
      ],
      validation_methods: [{ method_type: 'customer_pilot', description: 'ERP/Test Harness 试点', execution_location: 'external' }],
      milestones: [{ name: 'Week 2 first business action', status: 'planned' }],
      metrics: [{ name: 'harness_reuse_ratio', target: '>= 60%' }],
      approval_state: 'ready_for_review',
    })
    replaceValidationPlan(response?.data?.validation_plan)
  } catch (err) {
    decisionError.value = err.message || '验证计划创建失败'
  } finally {
    decisionUpdating.value = false
  }
}

async function patchValidationPlan(planId, patch) {
  if (!selectedProject.value?.id || !planId) return
  decisionUpdating.value = true
  decisionError.value = ''
  try {
    const response = await updateValidationPlan(selectedProject.value.id, planId, patch)
    replaceValidationPlan(response?.data?.validation_plan)
  } catch (err) {
    decisionError.value = err.message || '验证计划更新失败'
  } finally {
    decisionUpdating.value = false
  }
}

async function createLeadershipDecisionSample(optionId, planId) {
  if (!selectedProject.value?.id || !optionId) return
  const pack = artifactPacks.value[0]
  decisionUpdating.value = true
  decisionError.value = ''
  try {
    const response = await createLeadershipDecisionRecord(selectedProject.value.id, {
      idempotency_key: `leadership-decision-${selectedProject.value.id}-${decisionRecords.value.length + 1}`,
      title: 'Decision on Agent-ready enterprise software stack control point',
      decision_summary: '建议优先投入 L2 Agent-ready 适配层与 L4 企业级 Harness。',
      linked_option_ids: [optionId],
      linked_validation_plan_ids: planId ? [planId] : [],
      source_insight_ids: synthesisCards.value[0]?.id ? [synthesisCards.value[0].id] : [],
      source_artifact_pack_ids: pack?.pack_id ? [pack.pack_id] : [],
      chosen_option_id: optionId,
      rationale: [{ statement: 'L2 + L4 比模型层更可控、更贴近企业落地。' }],
      review_rounds: [{
        reviewer: 'VP-level reviewer',
        decision: 'needs_revision',
        comments: '补充首客复用与交付毛利指标。',
        blocking: true,
        resolved: false,
      }],
    })
    replaceDecisionRecord(response?.data?.leadership_decision_record)
  } catch (err) {
    decisionError.value = err.message || '领导决策记录创建失败'
  } finally {
    decisionUpdating.value = false
  }
}

async function patchLeadershipDecisionRecord(decisionId, patch) {
  if (!selectedProject.value?.id || !decisionId) return
  decisionUpdating.value = true
  decisionError.value = ''
  try {
    const response = await updateLeadershipDecisionRecord(selectedProject.value.id, decisionId, patch)
    replaceDecisionRecord(response?.data?.leadership_decision_record)
  } catch (err) {
    decisionError.value = err.message || '领导决策记录更新失败'
  } finally {
    decisionUpdating.value = false
  }
}

function resolveLeadershipReview(record) {
  const reviewRounds = (record.review_rounds || []).map((round) => (
    round.blocking === true && ['needs_revision', 'rejected'].includes(round.decision)
      ? { ...round, resolved: true }
      : round
  ))
  patchLeadershipDecisionRecord(record.decision_id, { review_rounds: reviewRounds })
}

function sourceRefsForBriefing() {
  const refs = []
  const card = synthesisCards.value[0]
  const option = strategicOptions.value[0]
  if (card?.id) refs.push({ asset_type: 'insight_card', asset_id: card.id, label: 'Control-layer thesis', required: true })
  if (option?.option_id) refs.push({ asset_type: 'strategic_option', asset_id: option.option_id, label: 'Recommended strategic option', required: true })
  return refs
}

async function createLeadershipBriefingSample() {
  if (!selectedProject.value?.id) return
  const card = synthesisCards.value[0]
  const option = strategicOptions.value[0]
  const plan = validationPlans.value[0]
  const decision = decisionRecords.value[0]
  briefingUpdating.value = true
  briefingError.value = ''
  try {
    const response = await createLeadershipBriefing(selectedProject.value.id, {
      idempotency_key: `leadership-briefing-${selectedProject.value.id}-${leadershipBriefings.value.length + 1}`,
      title: 'Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout',
      briefing_type: 'strategic_readout',
      audience: 'cloud_strategy_leadership',
      purpose: 'Prepare leadership discussion on Agent-ready enterprise software stack strategy.',
      executive_summary: {
        headline: 'Enterprise AI competition is moving to Agent-ready software stack control points.',
        key_message: 'Huawei Cloud should focus on L2 Agent-ready adaptation and L4 enterprise Harness.',
        leadership_ask: 'Approve 90-day ERP/Test Harness pilots and control-layer investment priorities.',
        decision_required: true,
      },
      source_asset_refs: sourceRefsForBriefing(),
      sections: [
        {
          order: 1,
          title: 'Why now',
          section_type: 'context',
          summary: 'Agent operations are becoming a new enterprise software entry point.',
          talking_points: ['The entry point shifts from UI navigation to agent-mediated operations.'],
          source_refs: card?.id ? [{ asset_type: 'insight_card', asset_id: card.id, label: 'Control-layer insight', required: true }] : [],
        },
        {
          order: 2,
          title: 'Control-layer thesis',
          section_type: 'recommendation',
          summary: 'L2 Agent-ready adaptation and L4 enterprise Harness are strategic control points.',
          source_refs: option?.option_id ? [{ asset_type: 'strategic_option', asset_id: option.option_id, label: 'Recommended option', required: true }] : [],
        },
        {
          order: 3,
          title: '90-day validation plan',
          section_type: 'validation_plan',
          summary: 'Use ERP/Test Harness pilots to validate reusable control-layer assets.',
          source_refs: plan?.plan_id ? [{ asset_type: 'validation_plan', asset_id: plan.plan_id, label: '90-day pilot plan', required: true }] : [],
        },
        {
          order: 4,
          title: 'Leadership ask',
          section_type: 'decision_ask',
          summary: 'Align on pilot scope, KPI, and first-customer deep delivery approach.',
          source_refs: decision?.decision_id ? [{ asset_type: 'leadership_decision_record', asset_id: decision.decision_id, label: 'Decision record', required: true }] : [],
        },
      ],
      decision_asks: option?.option_id ? [{
        title: 'Approve the first 90-day pilot path',
        description: 'Use ERP/Test Harness as the first pilot scenario.',
        linked_option_ids: [option.option_id],
        linked_validation_plan_ids: plan?.plan_id ? [plan.plan_id] : [],
        linked_decision_record_ids: decision?.decision_id ? [decision.decision_id] : [],
      }] : [],
    })
    replaceLeadershipBriefing(response?.data?.leadership_briefing)
  } catch (err) {
    briefingError.value = err.message || '领导汇报创建失败'
  } finally {
    briefingUpdating.value = false
  }
}

async function patchLeadershipBriefing(briefingId, patch) {
  if (!selectedProject.value?.id || !briefingId) return
  briefingUpdating.value = true
  briefingError.value = ''
  try {
    const response = await updateLeadershipBriefing(selectedProject.value.id, briefingId, patch)
    replaceLeadershipBriefing(response?.data?.leadership_briefing)
    await loadReviewHistory(selectedProject.value.id)
  } catch (err) {
    briefingError.value = err.message || '领导汇报更新失败'
  } finally {
    briefingUpdating.value = false
  }
}

function addLeadershipBriefingReview(briefingId) {
  if (!selectedLeadershipBriefing.value || !briefingId) return
  const reviewRounds = [
    ...(selectedLeadershipBriefing.value.review_rounds || []),
    {
      reviewer: 'strategy reviewer',
      decision: 'changes_requested',
      comment: 'Clarify AgentArts vs Harness boundary.',
      blocking: true,
      resolved: false,
    },
  ]
  patchLeadershipBriefing(briefingId, { review_rounds: reviewRounds })
}

function resolveLeadershipBriefingReview(briefing) {
  const reviewRounds = (briefing.review_rounds || []).map((round) => (
    round.blocking === true && ['changes_requested', 'rejected'].includes(round.decision)
      ? { ...round, resolved: true }
      : round
  ))
  patchLeadershipBriefing(briefing.briefing_id, { review_rounds: reviewRounds })
}

async function createGovernanceReviewSample() {
  if (!selectedProject.value?.id) return
  governanceUpdating.value = true
  governanceError.value = ''
  try {
    const response = await createGovernanceReview(selectedProject.value.id, {
      idempotency_key: `governance-review-${selectedProject.value.id}-${governanceReviews.value.length + 1}`,
      title: 'P9 strategic research governance review',
      review_type: 'stage_gate',
      seed_from_traceability_map: true,
    })
    replaceGovernanceReview(response?.data?.governance_review)
  } catch (err) {
    governanceError.value = err.message || '治理审查创建失败'
  } finally {
    governanceUpdating.value = false
  }
}

async function patchGovernanceReview(reviewId, patch) {
  if (!selectedProject.value?.id || !reviewId) return
  governanceUpdating.value = true
  governanceError.value = ''
  try {
    const response = await updateGovernanceReview(selectedProject.value.id, reviewId, patch)
    replaceGovernanceReview(response?.data?.governance_review)
    await loadReviewHistory(selectedProject.value.id)
    await loadAssetReviewHistory(selectedReviewHistoryAsset.value)
  } catch (err) {
    governanceError.value = err.message || '治理审查更新失败'
  } finally {
    governanceUpdating.value = false
  }
}

function acceptGovernanceRisks(review) {
  if (!review?.review_id) return
  const checklistItems = (review.checklist_items || []).map((item) => ({
    ...item,
    status: item.required ? 'pass' : (item.status === 'fail' ? 'waived' : item.status),
  }))
  const findings = (review.findings || []).map((finding) => ({
    ...finding,
    status: finding.status === 'open' || finding.status === 'triaged' ? 'accepted_risk' : finding.status,
    disposition: finding.disposition || 'Accepted for next-stage planning.',
  }))
  patchGovernanceReview(review.review_id, {
    status: 'signed_off',
    gate_decision: 'ready_with_risks',
    readiness: 'ready',
    checklist_items: checklistItems,
    findings,
    review_summary: { summary_note: 'Known traceability and support risks accepted for next-stage planning.' },
    signoffs: [
      ...(review.signoffs || []),
      {
        role: 'strategy_owner',
        name: 'P9 reviewer',
        decision: 'approved_with_risks',
        comment: 'Proceed with documented risks.',
      },
    ],
  })
}

function blockGovernanceReview(reviewId) {
  patchGovernanceReview(reviewId, {
    status: 'in_review',
    gate_decision: 'blocked',
    readiness: 'not_ready',
  })
}

async function createMaterialPack() {
  if (!selectedProject.value?.id) return
  const draft = synthesisDrafts.value[0]
  const card = synthesisCards.value[0]
  artifactPackUpdating.value = true
  artifactPackError.value = ''
  try {
    const response = await createArtifactPack(selectedProject.value.id, {
      idempotency_key: `material-pack-${selectedProject.value.id}`,
      title: '华为云 Agent-ready 企业软件栈战略汇报材料包',
      pack_type: 'leadership_deck',
      purpose: '面向领导汇报 Agent-ready 企业软件栈战略判断。',
      audience: selectedProject.value.audience || '',
      source_artifact_draft_ids: draft?.id ? [draft.id] : [],
      source_insight_ids: card?.id ? [card.id] : [],
      source_evidence_ids: firstEvidenceIds(),
      readiness: 'outline_ready',
    })
    replacePack(response?.data?.artifact_pack)
  } catch (err) {
    artifactPackError.value = err.message || '材料包创建失败'
  } finally {
    artifactPackUpdating.value = false
  }
}

async function updateMaterialPack(packId, patch) {
  if (!selectedProject.value?.id || !packId) return
  artifactPackUpdating.value = true
  artifactPackError.value = ''
  try {
    const response = await updateArtifactPack(selectedProject.value.id, packId, patch)
    replacePack(response?.data?.artifact_pack)
  } catch (err) {
    artifactPackError.value = err.message || '材料包更新失败'
  } finally {
    artifactPackUpdating.value = false
  }
}

async function addMaterialPackItem(packId) {
  const draft = synthesisDrafts.value[0]
  if (!selectedProject.value?.id || !packId || !draft?.id) return
  artifactPackUpdating.value = true
  artifactPackError.value = ''
  try {
    const response = await addArtifactPackItem(selectedProject.value.id, packId, {
      artifact_draft_id: draft.id,
      artifact_type: draft.artifact_type || 'slide_outline',
      title: draft.title || '主汇报材料',
      role_in_pack: 'main_deck',
    })
    replacePack(response?.data?.artifact_pack)
  } catch (err) {
    artifactPackError.value = err.message || '材料包条目添加失败'
  } finally {
    artifactPackUpdating.value = false
  }
}

async function addMaterialPackPage(packId) {
  const draft = synthesisDrafts.value[0]
  const card = synthesisCards.value[0]
  const row = synthesisRows.value[0]
  if (!selectedProject.value?.id || !packId) return
  artifactPackUpdating.value = true
  artifactPackError.value = ''
  try {
    const response = await addArtifactPackPage(selectedProject.value.id, packId, {
      page_title: 'Harness 是企业执行控制面',
      page_type: 'framework',
      page_claim: '权限、审批、日志、评测和回写构成企业控制面。',
      source_artifact_draft_id: draft?.id || '',
      source_insight_ids: card?.id ? [card.id] : [],
      source_evidence_ids: firstEvidenceIds(),
      source_matrix_row_ids: row?.id ? [row.id] : [],
      key_messages: ['控制点上移', '资产可复用'],
      material_status: 'outlined',
    })
    replacePack(response?.data?.artifact_pack)
  } catch (err) {
    artifactPackError.value = err.message || '材料包页面添加失败'
  } finally {
    artifactPackUpdating.value = false
  }
}

async function addMaterialPackFileRef(packId) {
  if (!selectedProject.value?.id || !packId) return
  const pack = artifactPacks.value.find((item) => item.pack_id === packId)
  const page = pack?.pages?.[0]
  const draft = synthesisDrafts.value[0]
  if (!page?.page_id) return
  artifactPackUpdating.value = true
  artifactPackError.value = ''
  try {
    const response = await addArtifactPackFileRef(selectedProject.value.id, packId, {
      file_kind: 'drawio',
      title: '五层架构图 v0.1',
      relative_path: 'artifact_files/agent_ready_stack_v0_1.drawio',
      linked_page_ids: [page.page_id],
      linked_artifact_draft_ids: draft?.id ? [draft.id] : [],
    })
    replacePack(response?.data?.artifact_pack)
  } catch (err) {
    artifactPackError.value = err.message || '文件引用登记失败'
  } finally {
    artifactPackUpdating.value = false
  }
}

async function addMaterialPackReview(packId) {
  if (!selectedProject.value?.id || !packId) return
  const pack = artifactPacks.value.find((item) => item.pack_id === packId)
  const page = pack?.pages?.[0]
  if (!page?.page_id) return
  artifactPackUpdating.value = true
  artifactPackError.value = ''
  try {
    const response = await addArtifactPackReviewRound(selectedProject.value.id, packId, {
      round_name: 'P5 internal review round 1',
      reviewer: 'human',
      status: 'completed',
      decisions: [{
        target_type: 'page',
        target_id: page.page_id,
        decision: 'needs_revision',
        severity: 'major',
        comment: '控制点与 L2/L4 层级需要更明确对齐。',
      }],
    })
    replacePack(response?.data?.artifact_pack)
  } catch (err) {
    artifactPackError.value = err.message || '评审记录添加失败'
  } finally {
    artifactPackUpdating.value = false
  }
}

async function submitCreate() {
  createError.value = ''
  if (!form.title.trim()) {
    createError.value = '请填写研究题目'
    return
  }
  creating.value = true
  try {
    const response = await createResearchProject({
      title: form.title.trim(),
      background: form.background,
      audience: form.audience,
      goal: form.goal,
    })
    const project = response?.data
    if (project?.id) {
      projects.value = [project, ...projects.value.filter((item) => item.id !== project.id)]
      selectedId.value = project.id
      setCurrentResearchProject(project)
      router.replace({ path: '/workspace/research', query: { project: project.id } })
    } else {
      await loadProjects()
    }
  } catch (err) {
    createError.value = err.message || '研究项目创建失败'
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  loadProjects()
  loadResearchMapCandidates()
})

watch(selectedId, (projectId) => {
  if (projectId) {
    const project = projects.value.find((item) => item.id === projectId)
    if (project) setCurrentResearchProject(project)
    loadEvidencePack(projectId)
    loadWritebackAssets(projectId)
    loadSynthesisAssets(projectId)
    loadArtifactPacks(projectId)
    loadDecisionAssets(projectId)
    loadLeadershipBriefings(projectId)
    loadTraceabilityMap(projectId)
    loadGovernanceReviews(projectId)
    loadReviewHistory(projectId)
    loadResearchSnapshots(projectId)
  }
})

watch(() => route.query.project, (projectId) => {
  if (projectId && projectId !== selectedId.value && projects.value.some((item) => item.id === projectId)) {
    selectedId.value = String(projectId)
  }
})
</script>

<style scoped>
.research-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}

.page-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-badge {
  color: var(--accent-primary);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.section-title {
  margin: 0;
  font-size: 24px;
  color: var(--text-primary);
}

.section-copy {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}

.state-card,
.create-band,
.list-panel,
.detail-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
}

.state-card {
  padding: 18px;
  color: var(--text-muted);
}

.error-card,
.inline-error {
  color: var(--danger-text, #b42318);
}

.create-band {
  padding: 16px;
}

.project-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.project-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.project-form input,
.project-form textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
  color: var(--text-primary);
  padding: 9px 10px;
  font: inherit;
  font-size: 13px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-primary,
.btn-secondary {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
}

.btn-primary {
  background: var(--accent-primary);
  color: var(--button-primary-text, #fff);
  border-color: var(--accent-primary);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: wait;
}

.btn-secondary {
  background: var(--bg-surface-2);
  color: var(--text-primary);
}

.btn-small,
.action-link {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
  color: var(--accent-primary-hover);
  padding: 7px 10px;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
  cursor: pointer;
}

.btn-small:disabled {
  opacity: 0.55;
  cursor: default;
}

.inline-error {
  margin: 0;
  font-size: 12px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.list-panel,
.detail-panel {
  padding: 14px;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.project-row {
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-primary);
  border-radius: 6px;
  padding: 10px;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.project-row:hover,
.project-row.active {
  background: var(--bg-selected);
  border-color: var(--border-default);
}

.row-title {
  font-size: 14px;
  font-weight: 800;
}

.row-meta {
  display: flex;
  gap: 8px;
  color: var(--text-muted);
  font-size: 11px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 800;
}

.status-pill.linked {
  background: var(--success-bg, #e7f6ec);
  color: var(--success-text, #166534);
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.detail-head h2 {
  margin: 0;
  font-size: 20px;
}

.definition-list {
  display: grid;
  gap: 12px;
  margin: 16px 0;
}

.definition-list div {
  display: grid;
  gap: 4px;
}

.definition-list dt {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
}

.definition-list dd {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.55;
}

.asset-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.asset-strip div {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 10px;
  background: var(--bg-surface-2);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.asset-strip strong {
  font-size: 20px;
}

.asset-strip span {
  color: var(--text-muted);
  font-size: 12px;
}

.timestamp-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  color: var(--text-muted);
  font-size: 12px;
}

.project-context-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 16px 0 0;
}

.project-context-tabs a {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  color: var(--accent-primary-hover);
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}

.project-section-card {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  margin-top: 16px;
  padding: 14px;
}

.mini-copy {
  margin-bottom: 12px;
}

.cluster-candidate-grid,
.concept-asset-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.cluster-candidate-card,
.asset-summary-row,
.concept-asset-grid article {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
  padding: 12px;
}

.card-head-row,
.asset-summary-row,
.action-row,
.article-actions,
.metric-row,
.chip-wrap,
.chip-action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.card-head-row,
.asset-summary-row {
  justify-content: space-between;
}

.card-head-row h3,
.asset-summary-row h3,
.concept-asset-grid h3 {
  margin: 0;
  font-size: 15px;
}

.cluster-candidate-card p,
.asset-summary-row p {
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 8px 0;
}

.metric-row,
.meta-line {
  color: var(--text-muted);
  font-size: 12px;
}

.chip {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--text-secondary);
  font-size: 12px;
}

.chip.soft {
  background: var(--bg-muted);
}

.asset-strip.compact {
  margin-bottom: 12px;
}

.empty-state {
  padding: 16px;
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .form-grid,
  .workspace-grid,
  .asset-strip,
  .cluster-candidate-grid,
  .concept-asset-grid {
    grid-template-columns: 1fr;
  }
}
</style>
