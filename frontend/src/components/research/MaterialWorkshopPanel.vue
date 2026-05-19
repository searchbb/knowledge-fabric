<template>
  <section class="material-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">材料工坊</div>
        <p>把草稿、洞察和证据组织成可交付材料包，并登记外部文件引用与评审记录。</p>
      </div>
      <button type="button" class="btn-primary" :disabled="loading || updating" @click="$emit('create-pack')">
        新建材料包
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在读取材料包...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ packs.length }}</strong><span>材料包</span></div>
        <div><strong>{{ selectedPack?.pages?.length || 0 }}</strong><span>页面</span></div>
        <div><strong>{{ selectedPack?.file_refs?.length || 0 }}</strong><span>文件引用</span></div>
        <div><strong>{{ selectedPack?.review_rounds?.length || 0 }}</strong><span>评审轮次</span></div>
      </div>

      <div v-if="!packs.length" class="empty-state">暂无材料包</div>
      <template v-else>
        <div class="pack-list">
          <button
            v-for="pack in packs"
            :key="pack.pack_id"
            type="button"
            class="pack-row"
            :class="{ active: selectedPackId === pack.pack_id }"
            @click="selectedPackId = pack.pack_id"
          >
            <strong>{{ pack.title }}</strong>
            <span>{{ pack.pack_type }} · {{ pack.status }} · {{ pack.readiness }}</span>
          </button>
        </div>

        <div v-if="selectedPack" class="pack-detail">
          <div class="asset-topline">
            <span class="status-pill">{{ selectedPack.status }}</span>
            <span class="status-pill">{{ selectedPack.readiness }}</span>
            <span class="status-pill">{{ selectedPack.pack_type }}</span>
          </div>
          <h3>{{ selectedPack.title }}</h3>
          <p>{{ selectedPack.purpose }}</p>

          <div class="actions">
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-pack', selectedPack.pack_id, { status: 'in_review', readiness: 'review_ready' })">
              进入评审
            </button>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('add-item', selectedPack.pack_id)">
              加入草稿
            </button>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('add-page', selectedPack.pack_id)">
              添加页面
            </button>
            <button type="button" class="btn-secondary" :disabled="updating || !(selectedPack.pages || []).length" @click="$emit('add-file-ref', selectedPack.pack_id)">
              登记文件引用
            </button>
            <button type="button" class="btn-secondary" :disabled="updating || !(selectedPack.pages || []).length" @click="$emit('add-review', selectedPack.pack_id)">
              记录评审
            </button>
          </div>

          <div class="tabs" role="tablist" aria-label="材料包视图">
            <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
              {{ tab.label }}
            </button>
          </div>

          <div v-if="activeTab === 'overview'" class="trace-grid">
            <div><span>草稿</span><strong>{{ selectedPack.source_artifact_draft_ids?.length || 0 }}</strong></div>
            <div><span>洞察</span><strong>{{ selectedPack.source_insight_ids?.length || 0 }}</strong></div>
            <div><span>证据</span><strong>{{ selectedPack.source_evidence_ids?.length || 0 }}</strong></div>
            <div><span>条目</span><strong>{{ selectedPack.items?.length || 0 }}</strong></div>
          </div>

          <div v-if="activeTab === 'pages'" class="card-list">
            <div v-if="!selectedPack.pages?.length" class="empty-state">暂无页面</div>
            <article v-for="page in selectedPack.pages || []" v-else :key="page.page_id" class="mini-card">
              <div class="asset-topline">
                <span class="status-pill">Page {{ page.sequence }}</span>
                <span class="status-pill">{{ page.page_type }}</span>
                <span class="status-pill">{{ page.review_status }}</span>
              </div>
              <h4>{{ page.page_title }}</h4>
              <p>{{ page.page_claim }}</p>
              <div class="trace-line">
                <span>洞察 {{ page.source_insight_ids?.length || 0 }}</span>
                <span>证据 {{ page.source_evidence_ids?.length || 0 }}</span>
                <span>矩阵 {{ page.source_matrix_row_ids?.length || 0 }}</span>
              </div>
            </article>
          </div>

          <div v-if="activeTab === 'files'" class="card-list">
            <div v-if="!selectedPack.file_refs?.length" class="empty-state">暂无文件引用</div>
            <article v-for="file in selectedPack.file_refs || []" v-else :key="file.file_ref_id" class="mini-card">
              <h4>{{ file.title }}</h4>
              <p>{{ file.file_kind }} · {{ file.relative_path || file.external_uri }}</p>
            </article>
          </div>

          <div v-if="activeTab === 'reviews'" class="card-list">
            <div v-if="!selectedPack.review_rounds?.length" class="empty-state">暂无评审记录</div>
            <article v-for="round in selectedPack.review_rounds || []" v-else :key="round.review_round_id" class="mini-card">
              <h4>{{ round.round_name }}</h4>
              <p>{{ round.status }} · {{ round.decisions?.length || 0 }} decisions</p>
              <div v-for="decision in round.decisions || []" :key="decision.decision_id" class="decision-line">
                {{ decision.target_type }} · {{ decision.decision }} · {{ decision.severity }}
              </div>
            </article>
          </div>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  packs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  updating: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

defineEmits(['create-pack', 'update-pack', 'add-item', 'add-page', 'add-file-ref', 'add-review'])

const selectedPackId = ref('')
const activeTab = ref('overview')
const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'pages', label: 'Pages' },
  { key: 'files', label: 'Files' },
  { key: 'reviews', label: 'Reviews' },
]

const selectedPack = computed(() => props.packs.find((pack) => pack.pack_id === selectedPackId.value) || props.packs[0] || null)

watch(() => props.packs, (packs) => {
  if (!packs.some((pack) => pack.pack_id === selectedPackId.value)) {
    selectedPackId.value = packs[0]?.pack_id || ''
  }
}, { immediate: true })
</script>

<style scoped>
.material-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.panel-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-bottom: 6px;
}

.panel-head p,
.pack-detail p,
.mini-card p,
.trace-line {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.summary-grid,
.trace-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid div,
.trace-grid div,
.empty-state,
.state-line,
.pack-row,
.pack-detail,
.mini-card {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
}

.summary-grid div,
.trace-grid div {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-grid strong,
.trace-grid strong {
  font-size: 19px;
}

.summary-grid span,
.trace-grid span,
.status-pill,
.trace-line,
.decision-line {
  color: var(--text-muted);
  font-size: 12px;
}

.pack-list,
.card-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.pack-row {
  padding: 10px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
}

.pack-row.active {
  border-color: var(--accent-primary);
}

.pack-detail,
.mini-card {
  padding: 12px;
  margin-top: 12px;
}

.pack-detail h3,
.mini-card h4 {
  margin: 8px 0 6px;
  color: var(--text-primary);
}

.asset-topline,
.actions,
.trace-line {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  font-weight: 800;
}

.actions {
  margin-top: 12px;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  border-bottom: 1px solid var(--border-default);
}

.tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  padding: 8px 2px;
  font-weight: 800;
  cursor: pointer;
}

.tabs button.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
}

.btn-primary,
.btn-secondary {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.btn-primary {
  background: var(--accent-primary);
  color: white;
}

.btn-secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.inline-error {
  color: var(--danger-text, #b42318);
}

.empty-state,
.state-line {
  padding: 12px;
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .panel-head,
  .summary-grid,
  .trace-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
