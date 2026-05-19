<template>
  <AppShell :crumbs="crumbs">
    <section class="proposal-detail">
      <router-link to="/workspace/topic-clusters/proposals" class="back-link">返回建议包</router-link>
      <div v-if="error" class="state-card error-card">{{ error }}</div>
      <div v-else-if="loading" class="state-card">加载中...</div>
      <template v-else-if="proposal">
        <header class="detail-head">
          <div>
            <div class="section-badge">建议审核</div>
            <h1>{{ proposal.proposal_id }}</h1>
            <p>只有勾选的支持动作会被应用。合并、拆分、更新在本阶段仅供审阅。</p>
          </div>
        </header>
        <div v-if="proposal.warnings?.length" class="warning-bar">
          <div v-for="warning in proposal.warnings" :key="warning.code || warning.message">
            {{ warning.code || 'warning' }}：{{ warning.message || warning }}
          </div>
        </div>
        <div class="action-groups">
          <section v-for="group in groupedActions" :key="group.key" class="action-group">
            <h2>{{ group.title }}</h2>
            <div v-if="!group.items.length" class="empty-note">暂无</div>
            <article v-for="action in group.items" :key="action.action_id" class="action-card">
              <label class="action-check">
                <input
                  type="checkbox"
                  :disabled="!isSupported(action)"
                  :checked="selected.has(action.action_id)"
                  @change="toggleAction(action.action_id, $event.target.checked)"
                />
                <span>{{ action.action_id }}</span>
              </label>
              <div class="meta-line">
                <span>{{ action.action_type }}</span>
                <span v-if="action.confidence != null">置信度 {{ Math.round(action.confidence * 100) }}%</span>
                <span v-if="!isSupported(action)" class="review-only">仅审核</span>
              </div>
              <p v-if="action.rationale">{{ action.rationale }}</p>
              <pre>{{ payloadSummary(action.payload) }}</pre>
            </article>
          </section>
        </div>
        <section class="apply-panel">
          <p>只有选中的支持动作会被应用。未选动作会记录为 rejected，不会自动应用。</p>
          <button class="primary-btn" :disabled="!selected.size || applying" @click="applySelected">
            {{ applying ? '应用中...' : '应用所选' }}
          </button>
          <span v-if="applyError" class="inline-error">{{ applyError }}</span>
          <div v-if="applyResult" class="result-box">
            <strong>已应用</strong>
            <div>新建主题簇: {{ applyResult.created_cluster_ids?.join(', ') || 'none' }}</div>
            <div>新建关联: {{ applyResult.created_link_ids?.join(', ') || 'none' }}</div>
            <div>跳过主题簇: {{ applyResult.skipped_existing_cluster_ids?.join(', ') || 'none' }}</div>
            <div>跳过关联: {{ applyResult.skipped_existing_link_ids?.join(', ') || 'none' }}</div>
          </div>
        </section>
      </template>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import { applyTopicClusterProposal, getTopicClusterProposal } from '../data/dataClient'

const supportedTypes = new Set(['create_cluster', 'add_link'])
const route = useRoute()
const proposal = ref(null)
const applications = ref([])
const selected = ref(new Set())
const loading = ref(false)
const applying = ref(false)
const error = ref('')
const applyError = ref('')
const applyResult = ref(null)

const crumbs = computed(() => [
  { label: '主题汇集', to: '/workspace/topic-clusters' },
  { label: '建议包', to: '/workspace/topic-clusters/proposals' },
  { label: proposal.value?.proposal_id || 'Proposal' },
])

const groupedActions = computed(() => {
  const groups = [
    { key: 'create_cluster', title: '新主题簇建议', items: [] },
    { key: 'update_cluster', title: '更新建议', items: [] },
    { key: 'add_link', title: '新增关联建议', items: [] },
    { key: 'merge_cluster', title: '可能合并', items: [] },
    { key: 'split_cluster', title: '可能拆分', items: [] },
  ]
  const byKey = Object.fromEntries(groups.map((group) => [group.key, group]))
  for (const action of proposal.value?.actions || []) {
    const group = byKey[action.action_type] || byKey.update_cluster
    group.items.push(action)
  }
  return groups
})

function isSupported(action) {
  return supportedTypes.has(action.action_type)
}

function toggleAction(actionId, checked) {
  const next = new Set(selected.value)
  if (checked) next.add(actionId)
  else next.delete(actionId)
  selected.value = next
}

function payloadSummary(payload) {
  return JSON.stringify(payload || {}, null, 2)
}

async function loadProposal() {
  loading.value = true
  error.value = ''
  selected.value = new Set()
  try {
    const response = await getTopicClusterProposal(route.params.proposalId)
    proposal.value = response.data?.proposal || null
    applications.value = response.data?.applications || []
  } catch (err) {
    error.value = err?.message || '建议加载失败'
  } finally {
    loading.value = false
  }
}

async function applySelected() {
  applying.value = true
  applyError.value = ''
  applyResult.value = null
  const accepted = Array.from(selected.value)
  const rejected = (proposal.value?.actions || [])
    .map((action) => action.action_id)
    .filter((actionId) => !selected.value.has(actionId))
  try {
    const response = await applyTopicClusterProposal(proposal.value.proposal_id, {
      accepted_actions: accepted,
      rejected_actions: rejected,
    })
    applyResult.value = response.data
    await loadProposal()
  } catch (err) {
    applyError.value = err?.message || 'Apply failed'
  } finally {
    applying.value = false
  }
}

onMounted(loadProposal)
</script>

<style scoped>
.proposal-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
}
.back-link {
  width: fit-content;
  color: var(--accent-primary-hover);
  text-decoration: none;
  font-weight: 700;
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
.detail-head p,
.apply-panel p {
  margin: 0;
  color: var(--text-secondary);
}
.action-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
}
.action-group,
.apply-panel,
.state-card,
.warning-bar {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-surface);
}
.action-group h2 {
  margin: 0 0 10px;
  font-size: 16px;
}
.action-card {
  border-top: 1px solid var(--border-default);
  padding: 12px 0;
}
.action-check {
  display: flex;
  gap: 8px;
  font-weight: 700;
}
.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
}
.review-only {
  color: #7c4a03;
}
pre {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-muted);
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
}
.primary-btn {
  border: 1px solid var(--accent-primary);
  border-radius: 8px;
  background: var(--accent-primary);
  color: white;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
  width: fit-content;
}
.primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.inline-error,
.error-card {
  color: #8c1d18;
}
.warning-bar {
  color: #7c4a03;
  background: #fff7e6;
  border-color: #f3d58b;
}
.result-box {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  color: var(--text-secondary);
}
.empty-note {
  color: var(--text-muted);
  font-size: 13px;
}
</style>
