<template>
  <section class="decision-panel">
    <div class="panel-head">
      <div>
        <div class="panel-title">战略决策工作台</div>
        <p>把洞察转换成战略选项、验证计划和领导决策记录。KFC 只沉淀决策资产，验证执行仍在 Codex、Skill 或人工团队外部完成。</p>
      </div>
      <button type="button" class="btn-primary" :disabled="loading || updating" @click="$emit('create-option')">
        新建战略选项
      </button>
    </div>

    <p v-if="error" class="inline-error">{{ error }}</p>
    <div v-if="loading" class="state-line">正在读取战略决策资产...</div>

    <template v-else>
      <div class="summary-grid">
        <div><strong>{{ options.length }}</strong><span>战略选项</span></div>
        <div><strong>{{ plans.length }}</strong><span>验证计划</span></div>
        <div><strong>{{ records.length }}</strong><span>决策记录</span></div>
        <div><strong>{{ openBlockingReviews }}</strong><span>阻塞评审</span></div>
      </div>

      <div class="decision-columns">
        <section class="asset-column">
          <div class="column-head">
            <h3>Strategic Options</h3>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('create-option')">创建样例</button>
          </div>
          <article v-for="option in options" :key="option.option_id" class="mini-card">
            <div class="asset-topline">
              <span class="status-pill">{{ option.status }}</span>
              <span class="status-pill">{{ option.recommendation_level }}</span>
              <span class="status-pill">{{ option.decision_posture }}</span>
            </div>
            <h4>{{ option.title }}</h4>
            <p>{{ option.summary }}</p>
            <div class="trace-line">
              <span>洞察 {{ option.source_insight_ids?.length || 0 }}</span>
              <span>矩阵 {{ option.source_evidence_matrix_row_ids?.length || 0 }}</span>
              <span>风险 {{ option.risks?.length || 0 }}</span>
            </div>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-option', option.option_id, { status: 'accepted_for_planning', review_state: 'reviewed' })">
              进入规划
            </button>
          </article>
          <div v-if="!options.length" class="empty-state">暂无战略选项</div>
        </section>

        <section class="asset-column">
          <div class="column-head">
            <h3>Validation Plans</h3>
            <button type="button" class="btn-secondary" :disabled="updating || !options.length" @click="$emit('create-plan', options[0]?.option_id)">
              创建试点计划
            </button>
          </div>
          <article v-for="plan in plans" :key="plan.plan_id" class="mini-card">
            <div class="asset-topline">
              <span class="status-pill">{{ plan.status }}</span>
              <span class="status-pill">{{ plan.approval_state }}</span>
              <span class="status-pill">{{ executionLabel(plan) }}</span>
            </div>
            <h4>{{ plan.title }}</h4>
            <p>{{ plan.summary }}</p>
            <div class="trace-line">
              <span>选项 {{ plan.linked_option_ids?.length || 0 }}</span>
              <span>问题 {{ plan.validation_questions?.length || 0 }}</span>
              <span>指标 {{ plan.metrics?.length || 0 }}</span>
            </div>
            <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-plan', plan.plan_id, { status: 'approved', approval_state: 'approved' })">
              批准计划
            </button>
          </article>
          <div v-if="!plans.length" class="empty-state">暂无验证计划</div>
        </section>

        <section class="asset-column">
          <div class="column-head">
            <h3>Leadership Decisions</h3>
            <button type="button" class="btn-secondary" :disabled="updating || !options.length" @click="$emit('create-record', options[0]?.option_id, plans[0]?.plan_id)">
              创建决策记录
            </button>
          </div>
          <article v-for="record in records" :key="record.decision_id" class="mini-card">
            <div class="asset-topline">
              <span class="status-pill">{{ record.decision_status }}</span>
              <span class="status-pill">{{ record.decision_type }}</span>
              <span v-if="hasOpenBlockingReview(record)" class="status-pill danger">阻塞未解决</span>
            </div>
            <h4>{{ record.title }}</h4>
            <p>{{ record.decision_summary }}</p>
            <div class="trace-line">
              <span>选项 {{ record.linked_option_ids?.length || 0 }}</span>
              <span>计划 {{ record.linked_validation_plan_ids?.length || 0 }}</span>
              <span>理由 {{ record.rationale?.length || 0 }}</span>
            </div>
            <div class="actions">
              <button type="button" class="btn-secondary" :disabled="updating || !hasOpenBlockingReview(record)" @click="$emit('resolve-record-review', record)">
                解决阻塞
              </button>
              <button type="button" class="btn-secondary" :disabled="updating" @click="$emit('update-record', record.decision_id, { decision_status: 'approved' })">
                批准决策
              </button>
            </div>
          </article>
          <div v-if="!records.length" class="empty-state">暂无领导决策记录</div>
        </section>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  options: { type: Array, default: () => [] },
  plans: { type: Array, default: () => [] },
  records: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  updating: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

defineEmits([
  'create-option',
  'update-option',
  'create-plan',
  'update-plan',
  'create-record',
  'update-record',
  'resolve-record-review',
])

function hasOpenBlockingReview(record) {
  return (record.review_rounds || []).some(
    (round) => round.blocking === true && ['needs_revision', 'rejected'].includes(round.decision) && !round.resolved,
  )
}

function executionLabel(plan) {
  const first = (plan.validation_methods || [])[0]
  return first?.execution_location || 'external'
}

const openBlockingReviews = computed(() => props.records.filter((record) => hasOpenBlockingReview(record)).length)
</script>

<style scoped>
.decision-panel {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 14px;
  margin-top: 16px;
}

.panel-head,
.column-head,
.asset-topline,
.actions,
.trace-line {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-head,
.column-head {
  justify-content: space-between;
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
.trace-line {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.5;
}

.summary-grid,
.decision-columns {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.decision-columns {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-grid div,
.asset-column,
.mini-card,
.empty-state,
.state-line {
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-surface-2);
}

.summary-grid div,
.asset-column,
.mini-card,
.empty-state,
.state-line {
  padding: 12px;
}

.summary-grid div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-grid strong {
  font-size: 19px;
}

.summary-grid span,
.status-pill,
.trace-line {
  color: var(--text-muted);
  font-size: 12px;
}

.asset-column h3,
.mini-card h4 {
  margin: 0 0 8px;
  color: var(--text-primary);
}

.asset-column {
  display: grid;
  align-content: start;
  gap: 10px;
}

.status-pill {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--bg-muted);
  font-weight: 800;
}

.status-pill.danger {
  color: var(--danger-text, #b42318);
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
  color: var(--text-muted);
}

@media (max-width: 1100px) {
  .decision-columns,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .panel-head {
    flex-direction: column;
  }
}
</style>
