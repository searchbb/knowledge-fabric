<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <div class="relation-detail-wrap">
      <div v-if="loading" class="state-card">加载中...</div>
      <div v-else-if="loadError" class="state-card error-card">{{ loadError }}</div>

      <template v-else-if="relation">
        <!-- Header -->
        <header class="rd-header">
          <div class="section-badge">CROSS-ARTICLE RELATION</div>
          <div class="rd-title-row">
            <h1 class="rd-title">{{ typeLabel }}</h1>
            <span class="rd-type-badge" :class="relation.relation_type">{{ relation.relation_type }}</span>
          </div>

          <div class="rd-meta-row">
            <span class="meta-pill"><strong>置信度</strong> {{ Math.round((relation.confidence || 0) * 100) }}%</span>
            <span class="meta-pill"><strong>来源</strong> {{ relation.source }}</span>
            <span class="meta-pill review-pill" :class="relation.review_status || 'unreviewed'">
              <strong>状态</strong> {{ reviewLabel }}
            </span>
            <span v-if="relation.created_at" class="meta-pill"><strong>发现时间</strong> {{ formatDate(relation.created_at) }}</span>
          </div>
        </header>

        <!-- Concepts -->
        <section class="rd-concepts">
          <article class="rd-concept-card">
            <div class="card-kicker">源概念</div>
            <div class="card-name">{{ sourceName }}</div>
            <div v-if="sourceType" class="card-type">{{ sourceType }}</div>
            <div class="card-actions">
              <router-link v-if="relation.source_entry_id" :to="`/workspace/entry/${relation.source_entry_id}`" class="btn-sm">查看概念详情 →</router-link>
            </div>
          </article>

          <div class="rd-arrow">
            {{ relation.directionality === 'bidirectional' ? '↔' : '→' }}
          </div>

          <article class="rd-concept-card">
            <div class="card-kicker">目标概念</div>
            <div class="card-name">{{ targetName }}</div>
            <div v-if="targetType" class="card-type">{{ targetType }}</div>
            <div class="card-actions">
              <router-link v-if="relation.target_entry_id" :to="`/workspace/entry/${relation.target_entry_id}`" class="btn-sm">查看概念详情 →</router-link>
            </div>
          </article>
        </section>

        <!-- Rationale / evidence -->
        <section class="rd-section">
          <h2 class="rd-section-title">关系说明</h2>
          <p class="rd-reason">{{ relation.reason || '(未记录 rationale)' }}</p>
        </section>

        <section v-if="relation.evidence_bridge" class="rd-section">
          <h2 class="rd-section-title">证据桥梁</h2>
          <p class="rd-evidence-bridge">{{ relation.evidence_bridge }}</p>
        </section>

        <section v-if="relation.evidence_refs?.length" class="rd-section">
          <h2 class="rd-section-title">原文引用 ({{ relation.evidence_refs.length }})</h2>
          <div class="evidence-list">
            <blockquote
              v-for="(ref, i) in relation.evidence_refs"
              :key="i"
              class="evidence-quote"
            >
              <p class="quote-text">"{{ ref.quote }}"</p>
              <footer v-if="ref.source_project || ref.source_concept" class="quote-source">
                <span v-if="ref.source_project">{{ ref.source_project }}</span>
                <span v-if="ref.source_concept"> · {{ ref.source_concept }}</span>
              </footer>
            </blockquote>
          </div>
        </section>

        <section v-if="relation.discovery_path?.length" class="rd-section">
          <h2 class="rd-section-title">发现路径</h2>
          <div class="path-breadcrumb">
            <span v-for="(step, i) in relation.discovery_path" :key="i" class="path-step">
              {{ step }}<span v-if="i < relation.discovery_path.length - 1" class="path-sep"> → </span>
            </span>
          </div>
        </section>

        <!-- Actions -->
        <section class="rd-actions">
          <button
            v-if="relation.review_status !== 'accepted'"
            class="btn-primary"
            :disabled="saving"
            @click="handleReview('accepted')"
          >{{ saving ? '处理中...' : '接受' }}</button>
          <button
            v-if="relation.review_status !== 'rejected'"
            class="btn-sm btn-danger"
            :disabled="saving"
            @click="handleReview('rejected')"
          >驳回</button>
          <button
            v-if="relation.review_status !== 'unreviewed'"
            class="btn-sm"
            :disabled="saving"
            @click="handleReview('unreviewed')"
          >标为待审</button>
          <button class="btn-sm btn-danger" :disabled="saving" @click="handleDelete">删除</button>
          <router-link to="/workspace/relations" class="btn-sm">返回列表</router-link>
        </section>
      </template>

      <div v-else class="state-card">未找到关系 {{ relationId }}</div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import {
  getCrossRelation,
  updateCrossRelation,
  deleteCrossRelation,
  getRegistryConcept,
} from '../../services/api/registryApi'

const route = useRoute()
const router = useRouter()

const relation = ref(null)
const sourceEntry = ref(null)
const targetEntry = ref(null)
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)

const relationId = computed(() => route.params.relationId || '')

const typeLabelMap = {
  design_inspiration: '设计启示',
  technical_foundation: '技术支撑',
  problem_solution: '问题-方案',
  contrast_reference: '对比参照',
  capability_constraint: '能力约束',
  pattern_reuse: '模式借鉴',
}

const typeLabel = computed(() => typeLabelMap[relation.value?.relation_type] || relation.value?.relation_type || '未知类型')

const reviewLabel = computed(() => {
  const s = relation.value?.review_status
  if (s === 'accepted') return '已接受'
  if (s === 'rejected') return '已驳回'
  return '待审'
})

const sourceName = computed(() =>
  sourceEntry.value?.canonical_name
  || relation.value?.source_entry?.canonical_name
  || relation.value?.source_name
  || relation.value?.source_entry_id
  || '(未知)'
)
const sourceType = computed(() =>
  sourceEntry.value?.concept_type
  || relation.value?.source_entry?.concept_type
  || ''
)
const targetName = computed(() =>
  targetEntry.value?.canonical_name
  || relation.value?.target_entry?.canonical_name
  || relation.value?.target_name
  || relation.value?.target_entry_id
  || '(未知)'
)
const targetType = computed(() =>
  targetEntry.value?.concept_type
  || relation.value?.target_entry?.concept_type
  || ''
)

const crumbs = computed(() => {
  const tail = relation.value
    ? `${sourceName.value} ${relation.value?.directionality === 'bidirectional' ? '↔' : '→'} ${targetName.value}`
    : relationId.value || '关系详情'
  return [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '跨文关系', to: '/workspace/relations' },
    { label: tail },
  ]
})

function formatDate(iso) { return iso ? iso.slice(0, 19).replace('T', ' ') : '' }

async function loadRelation() {
  if (!relationId.value) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await getCrossRelation(relationId.value)
    relation.value = res.data || null
    // Hydrate source/target concept names: API returns only IDs, fetch the
    // canonical entries in parallel so we can render their real names.
    const sid = relation.value?.source_entry_id
    const tid = relation.value?.target_entry_id
    const [sRes, tRes] = await Promise.all([
      sid ? getRegistryConcept(sid).catch(() => null) : null,
      tid ? getRegistryConcept(tid).catch(() => null) : null,
    ])
    sourceEntry.value = sRes?.data || null
    targetEntry.value = tRes?.data || null
  } catch (e) {
    loadError.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function handleReview(reviewStatus) {
  saving.value = true
  try {
    await updateCrossRelation(relationId.value, { review_status: reviewStatus })
    await loadRelation()
  } catch (e) {
    alert('审阅失败: ' + (e.message || ''))
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!confirm('确定删除此跨文关系？')) return
  saving.value = true
  try {
    await deleteCrossRelation(relationId.value)
    router.push('/workspace/relations')
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
    saving.value = false
  }
}

onMounted(loadRelation)
watch(relationId, loadRelation)
</script>

<style scoped>
.relation-detail-wrap {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.topbar-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 8px;
  border: 1px solid #d4dce8; background: #fff;
  color: #4a6fa5; font-size: 12px; font-weight: 500;
  text-decoration: none; cursor: pointer;
}
.topbar-btn:hover { background: #f0f4ff; border-color: #a9bbd9; }

.state-card {
  border: 1px solid #d4dce8;
  border-radius: 12px;
  padding: 18px 20px;
  background: #fff;
  color: #6d6256;
  font-size: 13px;
}
.error-card { border-color: #e2b0a8; background: #fff8f6; color: #c62828; }

.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #4a6fa5;
  font-weight: 700;
}
.rd-title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin: 6px 0 10px;
}
.rd-title { margin: 0; font-size: 26px; color: #181818; }
.rd-type-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f0f4ff;
  color: #4a6fa5;
  border: 1px solid #d4dce8;
  font-weight: 500;
}
.rd-meta-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.meta-pill {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 8px;
  background: #f3f4f7;
  color: #3f4552;
}
.meta-pill strong {
  font-weight: 700;
  color: #6d6256;
  margin-right: 4px;
}
.review-pill.accepted { background: #e8f5e9; color: #2e7d32; }
.review-pill.rejected { background: #ffebee; color: #c62828; }

.rd-concepts {
  display: grid;
  grid-template-columns: 1fr 60px 1fr;
  gap: 14px;
  align-items: stretch;
}
.rd-concept-card {
  border: 1px solid #d4dce8;
  border-radius: 14px;
  padding: 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.card-kicker {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #9a8d7c;
  font-weight: 700;
}
.card-name {
  font-size: 18px;
  font-weight: 700;
  color: #181818;
}
.card-type {
  font-size: 12px;
  color: #4a6fa5;
  background: #f0f4ff;
  padding: 2px 8px;
  border-radius: 999px;
  align-self: flex-start;
}
.card-actions { margin-top: auto; }

.rd-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #9a6b2e;
}

.rd-section {
  border: 1px solid #d4dce8;
  border-radius: 14px;
  padding: 18px;
  background: #fff;
}
.rd-section-title {
  margin: 0 0 10px;
  font-size: 14px;
  color: #6d6256;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.rd-reason {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  color: #3f4552;
}
.rd-evidence-bridge {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: #3f4552;
  font-style: italic;
}

.evidence-list { display: flex; flex-direction: column; gap: 12px; }
.evidence-quote {
  margin: 0;
  padding: 12px 16px;
  border-left: 3px solid #bf7d28;
  background: #fff9ef;
  border-radius: 4px;
}
.quote-text {
  margin: 0 0 4px;
  font-size: 14px;
  line-height: 1.6;
  color: #3f4552;
}
.quote-source {
  font-size: 11px;
  color: #9a8d7c;
}

.path-breadcrumb {
  font-size: 13px;
  color: #5a6573;
  line-height: 1.7;
}
.path-sep { color: #9a8d7c; margin: 0 4px; }

.rd-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 4px;
}

.btn-primary {
  padding: 8px 18px;
  border-radius: 10px;
  border: 1px solid #2e7d32;
  background: #2e7d32;
  color: #fff;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.6; cursor: wait; }
.btn-primary:hover:not(:disabled) { background: #246728; }

.btn-sm {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #4a6fa5;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
}
.btn-sm:hover:not(:disabled) { background: #f0f4ff; border-color: #a9bbd9; }
.btn-sm:disabled { opacity: 0.6; cursor: wait; }
.btn-danger {
  color: #c62828;
  border-color: #ef9a9a;
}
.btn-danger:hover:not(:disabled) {
  background: #ffebee;
}
</style>
