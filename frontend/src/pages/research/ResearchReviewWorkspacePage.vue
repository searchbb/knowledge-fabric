<template>
  <AppShell :crumbs="crumbs">
    <div class="review-workspace-page">
      <header class="page-header">
        <div class="section-badge">审核工作台</div>
        <h1 class="section-title">研究审核工作台</h1>
        <p class="section-copy">
          跨战略研究项目查看审核资产的只读导航入口。
        </p>
      </header>

      <section class="boundary-band" aria-label="审核工作台边界">
        <strong>只读导航边界</strong>
        <p>
          这里不是就绪度评估器、流程派单系统、模型辅助审核运行时或关卡决策自动化；只链接已有研究资产，不修改审核状态。
        </p>
      </section>

      <div v-if="loading" class="state-card">正在加载审核工作台...</div>
      <div v-else-if="error" class="state-card error-card">{{ error }}</div>

      <template v-else>
        <section class="summary-grid">
          <article>
            <strong>{{ projectRows.length }}</strong>
            <span>研究项目</span>
          </article>
          <article>
            <strong>{{ totalReviews }}</strong>
            <span>治理审核</span>
          </article>
          <article>
            <strong>{{ projectsWithReviews }}</strong>
            <span>有审核资产的项目</span>
          </article>
          <article>
            <strong>{{ totalSnapshots }}</strong>
            <span>研究快照</span>
          </article>
          <article>
            <strong>{{ projectsWithSnapshots }}</strong>
            <span>有快照的项目</span>
          </article>
        </section>

        <section class="workspace-list" aria-label="审核工作台项目导航">
          <div class="panel-title">审核资产索引</div>
          <p class="index-copy">
            只读索引已有治理审核和研究快照；不打分、不派单，也不做关卡决策。
          </p>
          <div v-if="!projectRows.length" class="empty-state">
            暂无可用战略研究项目。
          </div>
          <article
            v-for="row in projectRows"
            :key="row.project.id"
            class="project-card"
          >
            <div>
              <h2>{{ row.project.title }}</h2>
              <p>{{ row.project.goal || row.project.background || '暂无项目上下文。' }}</p>
              <div class="meta-row">
                <span class="status-pill">{{ row.project.status || 'unknown' }}</span>
                <span>{{ row.project.id }}</span>
                <span>{{ row.reviews.length }} 个治理审核</span>
              </div>
            </div>
            <RouterLink class="btn-secondary" :to="`/workspace/research?project=${row.project.id}`">
              打开战略研究
            </RouterLink>

            <div class="asset-index-strip">
              <div>
                <strong>{{ row.reviews.length }}</strong>
                <span>已索引治理审核</span>
              </div>
              <div>
                <strong>{{ row.snapshots.length }}</strong>
                <span>已索引快照</span>
              </div>
              <div>
                <strong>{{ row.project.evidence_items?.length || 0 }}</strong>
                <span>证据篮</span>
              </div>
              <div>
                <strong>{{ row.project.linked_topic_clusters?.length || 0 }}</strong>
                <span>主题簇覆盖</span>
              </div>
              <div>
                <strong>{{ row.project.linked_concepts?.length || 0 }}</strong>
                <span>概念快照</span>
              </div>
            </div>

            <div v-if="row.reviews.length" class="review-strip">
              <article
                v-for="review in row.reviews"
                :key="review.review_id"
                class="review-chip"
              >
                <strong>{{ review.title }}</strong>
                <span>{{ review.status || 'unknown' }} · {{ review.readiness || 'unknown' }}</span>
                <small>{{ review.review_id }}</small>
              </article>
            </div>
            <p v-else class="empty-line">当前项目尚未索引治理审核资产。</p>

            <div v-if="row.snapshots.length" class="snapshot-strip">
              <article
                v-for="snapshot in row.snapshots"
                :key="snapshot.snapshot_id"
                class="review-chip"
              >
                <strong>{{ snapshot.title || snapshot.snapshot_id }}</strong>
                <span>{{ snapshot.status || 'indexed' }} · {{ snapshot.created_at || '无时间戳' }}</span>
                <small>{{ snapshot.snapshot_id }}</small>
              </article>
            </div>
            <p v-else class="empty-line">当前项目尚未索引研究快照。</p>
            <p v-if="!row.reviews.length && !row.snapshots.length" class="empty-line">
              当前项目暂无已索引审核资产。
            </p>

            <section class="history-timeline" aria-label="近期审核历史">
              <div class="subsection-title">近期审核历史</div>
              <p class="empty-line">显示最近 5 条审核历史。</p>
              <p v-if="row.historyError" class="empty-line">
                当前项目审核历史不可用；已有项目资产仍然可见。
              </p>
              <div v-else-if="row.historyEntries.length" class="timeline-list">
                <article
                  v-for="entry in row.historyEntries"
                  :key="entry.id"
                  class="timeline-entry"
                >
                  <strong>{{ entry.label }}</strong>
                  <span>{{ entry.occurredAt || '无时间戳' }}</span>
                  <span>资产：{{ entry.assetType }} · {{ entry.assetLabel }}</span>
                  <span v-if="entry.actor">操作者：{{ entry.actor }}</span>
                  <p v-if="entry.note">{{ entry.note }}</p>
                </article>
              </div>
              <p v-else class="empty-line">当前项目暂无审核历史。</p>
            </section>
          </article>
        </section>

        <section class="boundary-band compact" aria-label="范围外">
          <strong>当前不处理范围</strong>
          <p>
            就绪度评估、流程派单、模型辅助审核、调度器、队列和关卡决策仍保留为后续独立界面。
          </p>
        </section>
      </template>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppShell from '../../components/common/AppShell.vue'
import {
  listGovernanceReviews,
  listResearchProjects,
  listResearchSnapshots,
  listReviewHistory,
} from '../../data/dataClient'

const crumbs = [
  { label: '研究资产', to: '/workspace/research' },
  { label: '审核工作台' },
]

const loading = ref(false)
const error = ref('')
const projectRows = ref([])

const totalReviews = computed(() => projectRows.value.reduce((sum, row) => sum + row.reviews.length, 0))
const totalSnapshots = computed(() => projectRows.value.reduce((sum, row) => sum + row.snapshots.length, 0))
const projectsWithReviews = computed(() => projectRows.value.filter((row) => row.reviews.length > 0).length)
const projectsWithSnapshots = computed(() => projectRows.value.filter((row) => row.snapshots.length > 0).length)

function normalizeProjects(response) {
  const data = response?.data || {}
  return Array.isArray(data.projects) ? data.projects : []
}

function normalizeReviews(response) {
  const data = response?.data || {}
  return Array.isArray(data.governance_reviews) ? data.governance_reviews : []
}

function normalizeSnapshots(response) {
  const data = response?.data || {}
  return Array.isArray(data.snapshots) ? data.snapshots : []
}

function normalizeReviewHistory(response) {
  const data = response?.data || {}
  return Array.isArray(data.review_history_entries) ? data.review_history_entries.slice(0, 5) : []
}

function actorLabel(actor) {
  if (!actor) return ''
  if (typeof actor === 'string') return actor
  return actor.display_name || actor.name || actor.actor_type || ''
}

function normalizeReviewHistoryEntry(entry = {}) {
  return {
    id: entry.history_entry_id || entry.id || `${entry.created_at || entry.timestamp || ''}-${entry.asset_id || ''}`,
    occurredAt: entry.created_at || entry.timestamp || entry.updated_at || '',
    label: entry.event_type || entry.action || entry.kind || '审核事件',
    assetType: entry.asset_type || entry.asset_ref?.asset_type || '审核资产',
    assetLabel: entry.asset_title || entry.asset_id || entry.asset_ref?.asset_id || '未知资产',
    actor: actorLabel(entry.actor || entry.reviewer),
    note: entry.summary || entry.note || entry.comment || '',
  }
}

async function loadReviewWorkspace() {
  loading.value = true
  error.value = ''
  try {
    const projects = normalizeProjects(await listResearchProjects())
    const rows = await Promise.all(projects.map(async (project) => {
      let reviews = []
      let snapshots = []
      let historyEntries = []
      let historyError = ''
      try {
        const reviewResponse = await listGovernanceReviews(project.id)
        reviews = normalizeReviews(reviewResponse)
      } catch {
        reviews = []
      }
      try {
        const snapshotResponse = await listResearchSnapshots(project.id)
        snapshots = normalizeSnapshots(snapshotResponse)
      } catch {
        snapshots = []
      }
      try {
        const historyResponse = await listReviewHistory(project.id, { limit: 5 })
        historyEntries = normalizeReviewHistory(historyResponse).map(normalizeReviewHistoryEntry)
      } catch (err) {
        historyError = err.message || '审核历史不可用'
      }
      return { project, reviews, snapshots, historyEntries, historyError }
    }))
    projectRows.value = rows
  } catch (err) {
    error.value = err.message || '审核工作台加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadReviewWorkspace)
</script>

<style scoped>
.review-workspace-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-badge {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-group-label);
  font-weight: 700;
}

.section-title {
  margin: 0;
  font-size: 28px;
  color: var(--text-primary);
}

.section-copy,
.boundary-band p,
.index-copy,
.project-card p,
.meta-row,
.review-chip span,
.review-chip small,
.timeline-entry span,
.timeline-entry p,
.empty-line {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.boundary-band,
.state-card,
.summary-grid article,
.workspace-list,
.project-card,
.review-chip {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
}

.boundary-band,
.state-card,
.workspace-list,
.project-card {
  padding: 14px;
}

.boundary-band {
  background: var(--bg-surface-2);
}

.boundary-band.compact {
  padding: 12px 14px;
}

.error-card {
  border-color: var(--danger);
  color: var(--danger);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.summary-grid article {
  padding: 12px;
}

.summary-grid strong {
  display: block;
  font-size: 20px;
}

.summary-grid span {
  color: var(--text-muted);
  font-size: 12px;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.workspace-list,
.project-card,
.asset-index-strip,
.review-strip {
  display: grid;
  gap: 10px;
}

.project-card {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  background: var(--bg-surface-2);
}

.index-copy {
  margin-bottom: 10px;
}

.project-card h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
}

.review-strip {
  grid-column: 1 / -1;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.asset-index-strip {
  grid-column: 1 / -1;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.asset-index-strip div {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  padding: 10px;
}

.asset-index-strip strong {
  display: block;
}

.asset-index-strip span {
  color: var(--text-muted);
  font-size: 12px;
}

.review-chip {
  padding: 10px;
}

.review-chip strong,
.review-chip span,
.review-chip small {
  display: block;
  overflow-wrap: anywhere;
}

.history-timeline {
  grid-column: 1 / -1;
  border-top: 1px solid var(--border-default);
  padding-top: 10px;
}

.subsection-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 4px;
}

.timeline-list {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.timeline-entry {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  padding: 10px;
}

.timeline-entry strong,
.timeline-entry span {
  display: block;
  overflow-wrap: anywhere;
}

.btn-secondary {
  align-self: start;
  text-decoration: none;
}

@media (max-width: 760px) {
  .project-card {
    grid-template-columns: 1fr;
  }
}
</style>
