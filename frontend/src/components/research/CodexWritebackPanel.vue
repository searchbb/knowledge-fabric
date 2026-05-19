<template>
  <section class="writeback-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">Codex 写回</div>
        <p>展示 Codex / Skill 已完成并写回 KFC 的运行日志、咨询记录和外部证据包。</p>
      </div>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在读取写回资产...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ runs.length }}</strong><span>运行日志</span></div>
        <div><strong>{{ consultations.length }}</strong><span>咨询记录</span></div>
        <div><strong>{{ packs.length }}</strong><span>外部证据包</span></div>
        <div><strong>{{ acceptedExternalCount }}</strong><span>C2 已采纳</span></div>
      </div>

      <div class="writeback-columns">
        <div class="column">
          <h3>Research Runs</h3>
          <div v-if="!runs.length" class="empty-state">暂无运行日志</div>
          <article v-for="run in runs" v-else :key="run.run_id" class="mini-card">
            <div class="card-line"><strong>{{ run.title || run.run_id }}</strong><span>{{ run.status }}</span></div>
            <p>{{ run.summary || `${run.stage || ''} ${run.phase || ''}` }}</p>
          </article>
        </div>

        <div class="column">
          <h3>Consultation Logs</h3>
          <div v-if="!consultations.length" class="empty-state">暂无咨询记录</div>
          <article v-for="log in consultations" v-else :key="log.consultation_id" class="mini-card">
            <div class="card-line"><strong>{{ log.kind || log.consultation_id }}</strong><span>{{ log.status }}</span></div>
            <p>{{ log.answer_summary || '未填写摘要' }}</p>
          </article>
        </div>
      </div>

      <div class="external-packs">
        <h3>External Evidence Packs</h3>
        <div v-if="!packs.length" class="empty-state">暂无外部证据包</div>
        <article v-for="pack in packs" v-else :key="pack.pack_id" class="pack-card">
          <div class="pack-head">
            <div>
              <strong>{{ pack.title }}</strong>
              <p>{{ pack.source_type }} · {{ pack.scope || 'C2_external' }} · {{ candidateCount(pack) }} candidates</p>
            </div>
            <span class="status-pill">{{ pack.status }}</span>
          </div>
          <div class="candidate-list">
            <div
              v-for="candidate in pack.evidence_candidates || []"
              :key="candidate.candidate_id || candidate.external_id"
              class="candidate-row"
              :class="candidate.review_status"
            >
              <div>
                <div class="candidate-topline">
                  <span class="status-pill">{{ candidateStatus(candidate.review_status) }}</span>
                  <span v-if="candidate.confidence !== undefined" class="score">confidence {{ candidate.confidence }}</span>
                </div>
                <strong>{{ candidate.claim }}</strong>
                <p>{{ candidate.evidence_text }}</p>
              </div>
              <div class="actions">
                <button
                  type="button"
                  class="btn-secondary"
                  :disabled="reviewingId === candidate.candidate_id"
                  @click="$emit('review', pack.pack_id, candidate.candidate_id || candidate.external_id, 'accepted')"
                >
                  采纳
                </button>
                <button
                  type="button"
                  class="btn-secondary danger"
                  :disabled="reviewingId === candidate.candidate_id"
                  @click="$emit('review', pack.pack_id, candidate.candidate_id || candidate.external_id, 'rejected')"
                >
                  废弃
                </button>
              </div>
            </div>
          </div>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  runs: { type: Array, default: () => [] },
  consultations: { type: Array, default: () => [] },
  packs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  reviewingId: { type: String, default: '' },
  error: { type: String, default: '' },
})

defineEmits(['review'])

const acceptedExternalCount = computed(() => (
  props.packs.reduce((count, pack) => (
    count + (pack.evidence_candidates || []).filter((candidate) => candidate.review_status === 'accepted').length
  ), 0)
))

function candidateCount(pack) {
  return pack.candidate_count ?? (pack.evidence_candidates || []).length
}

function candidateStatus(status) {
  if (status === 'accepted') return '已采纳'
  if (status === 'rejected') return '已废弃'
  return '待评审'
}
</script>

<style scoped>
.writeback-panel {
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
.mini-card p,
.pack-head p,
.candidate-row p {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.summary-grid,
.writeback-columns {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.writeback-columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-grid div,
.mini-card,
.pack-card,
.candidate-row,
.empty-state,
.state-line {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
}

.summary-grid div {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-grid strong {
  font-size: 19px;
}

.summary-grid span,
.card-line span,
.status-pill,
.score {
  color: var(--text-muted);
  font-size: 12px;
}

.column h3,
.external-packs h3 {
  font-size: 13px;
  margin: 0 0 8px;
}

.mini-card,
.pack-card {
  padding: 10px;
  margin-bottom: 8px;
}

.card-line,
.pack-head,
.candidate-topline,
.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.external-packs {
  margin-top: 14px;
}

.candidate-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.candidate-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 10px;
}

.candidate-row.accepted {
  border-color: var(--success-border, #7cc58d);
}

.status-pill,
.score {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  font-weight: 800;
}

.btn-secondary {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  padding: 8px 12px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.btn-secondary.danger,
.inline-error {
  color: var(--danger-text, #b42318);
}

.empty-state,
.state-line {
  padding: 12px;
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .summary-grid,
  .writeback-columns,
  .candidate-row {
    grid-template-columns: 1fr;
  }

  .actions {
    justify-content: flex-start;
  }
}
</style>
