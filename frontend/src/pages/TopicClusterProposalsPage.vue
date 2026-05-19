<template>
  <AppShell :crumbs="crumbs">
    <section class="proposal-page">
      <header class="page-head">
        <div>
          <div class="section-badge">建议包</div>
          <h1>主题簇建议</h1>
          <p>KFC 只审阅外部 runner 写入的建议包，不生成建议，也不启动后台任务。</p>
        </div>
      </header>
      <div v-if="error" class="state-card error-card">{{ error }}</div>
      <div v-else-if="loading" class="state-card">加载中...</div>
      <div v-else-if="!proposals.length" class="state-card">
        暂无建议包。外部 runner 可将 tcp_*.json 写入 backend/data/topic_cluster_proposals/。
      </div>
      <div v-else class="proposal-list">
        <article v-for="proposal in proposals" :key="proposal.proposal_id" class="proposal-card">
          <div>
            <h2>{{ proposal.proposal_id }}</h2>
            <div class="meta-line">
              <span>{{ proposal.status }}</span>
              <span>{{ proposal.created_at }}</span>
              <span>动作 {{ proposal.action_count }}</span>
              <span>支持 {{ proposal.supported_action_count }}</span>
              <span>仅审核 {{ proposal.unsupported_action_count }}</span>
              <span>警告 {{ proposal.warning_count }}</span>
            </div>
          </div>
          <router-link :to="`/workspace/topic-clusters/proposals/${proposal.proposal_id}`" class="open-link">
            查看详情
          </router-link>
        </article>
      </div>
    </section>
  </AppShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AppShell from '../components/common/AppShell.vue'
import { listTopicClusterProposals } from '../data/dataClient'

const crumbs = [
  { label: '主题汇集', to: '/workspace/topic-clusters' },
  { label: '建议包' },
]
const proposals = ref([])
const loading = ref(false)
const error = ref('')

async function loadProposals() {
  loading.value = true
  error.value = ''
  try {
    const response = await listTopicClusterProposals()
    proposals.value = response.data?.items || []
  } catch (err) {
      error.value = err?.message || '建议包加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadProposals)
</script>

<style scoped>
.proposal-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
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
}
.proposal-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.proposal-card,
.state-card {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-surface);
}
.proposal-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
h2 {
  margin: 0;
  font-size: 18px;
}
.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}
.open-link {
  color: var(--accent-primary-hover);
  text-decoration: none;
  font-weight: 700;
}
.error-card {
  color: #8c1d18;
  background: #fff1f0;
  border-color: #f2b8b5;
}
</style>
