<template>
  <div v-if="normalizedResult" class="phase1-summary-strip">
    <div class="summary-main">
      <div class="summary-title-group">
        <span class="summary-kicker">PHASE-1</span>
        <span class="summary-title">知识工作台抽取状态</span>
      </div>
      <div class="summary-pill-row">
        <span class="summary-pill">Provider · {{ providerLabel }}</span>
        <span class="summary-pill" :class="toneClass(buildStatusMeta.tone)">构建 · {{ buildStatusMeta.label }}</span>
        <span class="summary-pill" :class="toneClass(readingStatusMeta.tone)">阅读骨架 · {{ readingStatusMeta.label }}</span>
      </div>
    </div>

    <div class="summary-metrics">
      <div class="summary-metric">
        <span class="metric-label">文本块</span>
        <span class="metric-value">{{ chunkProgressLabel }}</span>
      </div>
      <div class="summary-metric">
        <span class="metric-label">成功率</span>
        <span class="metric-value">{{ successRatioLabel }}</span>
      </div>
      <div class="summary-metric">
        <span class="metric-label">告警</span>
        <span class="metric-value">{{ warningCountLabel }}</span>
      </div>
    </div>

    <div v-if="summaryNote" class="summary-note">
      {{ summaryNote }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  taskResult: {
    type: Object,
    default: null,
  },
})

const normalizedResult = computed(() => {
  const result = props.taskResult
  return result && typeof result === 'object' ? result : null
})

const buildOutcome = computed(() => normalizedResult.value?.build_outcome || null)
const readingStatus = computed(() => normalizedResult.value?.reading_structure_status || null)
const diagnostics = computed(() => normalizedResult.value?.diagnostics || null)

const providerLabel = computed(() => {
  const provider = normalizedResult.value?.provider || diagnostics.value?.provider
  return provider ? String(provider).toUpperCase() : 'UNKNOWN'
})

const buildStatusMeta = computed(() => {
  switch (buildOutcome.value?.status) {
    case 'completed':
      return { label: '已完成', tone: 'success' }
    case 'completed_with_warnings':
      return { label: '完成但有告警', tone: 'warning' }
    case 'completed_with_fallback':
      return { label: 'Fallback 完成', tone: 'warning' }
    case 'failed':
      return { label: '失败', tone: 'error' }
    default:
      return { label: '未知', tone: 'muted' }
  }
})

const readingStatusMeta = computed(() => {
  switch (readingStatus.value?.status) {
    case 'generated':
      return { label: '已生成', tone: 'success' }
    case 'fallback':
      return { label: 'Fallback', tone: 'warning' }
    case 'failed':
      return { label: '失败', tone: 'error' }
    case 'skipped':
      return { label: '跳过', tone: 'muted' }
    default:
      return { label: '未知', tone: 'muted' }
  }
})

const chunkProgressLabel = computed(() => {
  const total = diagnostics.value?.chunk_count || 0
  const processed = diagnostics.value?.processed_chunk_count || 0
  return total ? `${processed}/${total}` : '—'
})

const successRatioLabel = computed(() => {
  const ratio = buildOutcome.value?.success_ratio
  if (typeof ratio !== 'number') return '—'
  return `${Math.round(ratio * 100)}%`
})

const warningCountLabel = computed(() => {
  const warnings = buildOutcome.value?.warnings
  return Array.isArray(warnings) ? `${warnings.length}` : '0'
})

const summaryNote = computed(() => {
  if (diagnostics.value?.fallback_graph_applied) {
    const mode = diagnostics.value?.fallback_graph_mode || 'heuristic_outline'
    return `当前图谱来自 fallback graph (${mode})，下游分析应按“阶段性可用结果”理解。`
  }
  if (buildOutcome.value?.status === 'completed_with_warnings') {
    return 'Phase-1 已完成，但存在构建告警；后续页面结果应结合告警一起阅读。'
  }
  if (readingStatus.value?.status === 'failed' || readingStatus.value?.status === 'skipped') {
    return '阅读骨架不是完全成功状态，当前更多依赖图谱本体而不是阅读整理结果。'
  }
  return ''
})

const toneClass = (tone) => `tone-${tone || 'muted'}`
</script>

<style scoped>
.phase1-summary-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 24px;
  border-bottom: 1px solid #ececec;
  background:
    linear-gradient(135deg, rgba(255, 87, 34, 0.06), rgba(255, 138, 80, 0.02)),
    #fff;
}

.summary-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.summary-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.summary-kicker {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #ff5722;
}

.summary-title {
  font-size: 13px;
  font-weight: 700;
  color: #111;
}

.summary-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e8e8e8;
  background: #f6f6f6;
  color: #333;
  font-size: 11px;
  padding: 4px 9px;
}

.summary-metrics {
  display: flex;
  gap: 18px;
  flex-shrink: 0;
}

.summary-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 58px;
}

.metric-label {
  font-size: 10px;
  color: #999;
}

.metric-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  color: #111;
}

.summary-note {
  max-width: 420px;
  font-size: 11px;
  color: #555;
  line-height: 1.45;
}

.tone-success {
  background: #e8f5e9;
  border-color: #cbe8cd;
  color: #23632b;
}

.tone-warning {
  background: #fff3e0;
  border-color: #ffd7a6;
  color: #8f4b00;
}

.tone-error {
  background: #fdecec;
  border-color: #f4c7c7;
  color: #a12626;
}

.tone-muted {
  background: #f3f3f3;
  border-color: #e8e8e8;
  color: #666;
}

@media (max-width: 1100px) {
  .phase1-summary-strip {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-metrics {
    gap: 12px;
  }

  .summary-note {
    max-width: none;
  }
}

@media (max-width: 720px) {
  .phase1-summary-strip {
    padding: 12px 16px;
  }

  .summary-metrics {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
