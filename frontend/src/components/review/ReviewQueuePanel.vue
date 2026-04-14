<template>
  <section class="queue-panel">
    <header class="panel-header">
      <div>
        <div class="panel-kicker">Review Queue</div>
        <h3 class="panel-title">待校验任务</h3>
      </div>
      <span class="prototype-pill">原型模式</span>
    </header>

    <p class="panel-copy">
      用现有 Phase 1 warning、诊断和图谱快照模拟首批 ReviewTask，先验证“任务切换 -> 看证据 -> 做判断”的主链路。
    </p>

    <div class="filter-row">
      <button
        v-for="filter in filters"
        :key="filter.key"
        class="filter-chip"
        :class="{ active: filter.key === activeFilter }"
        @click="$emit('change-filter', filter.key)"
      >
        <span>{{ filter.label }}</span>
        <span class="chip-count">{{ filter.count }}</span>
      </button>
    </div>

    <div class="task-list">
      <button
        v-for="task in tasks"
        :key="task.id"
        class="task-card"
        :class="{ active: task.id === activeTaskId }"
        @click="$emit('select-task', task.id)"
      >
        <div class="task-topline">
          <span class="task-pill severity" :class="task.severity">{{ task.severityLabel }}</span>
          <span class="task-pill status" :class="task.status">{{ task.statusLabel }}</span>
        </div>
        <div class="task-title">{{ task.title }}</div>
        <div class="task-summary">{{ task.summary }}</div>
        <div class="task-meta">
          <span>{{ task.kindLabel }}</span>
          <span>{{ task.confidenceLabel }}</span>
        </div>
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  tasks: {
    type: Array,
    default: () => [],
  },
  filters: {
    type: Array,
    default: () => [],
  },
  activeTaskId: {
    type: String,
    default: '',
  },
  activeFilter: {
    type: String,
    default: 'all',
  },
})

defineEmits(['change-filter', 'select-task'])
</script>

<style scoped>
.queue-panel {
  border: 1px solid #eadfcb;
  background: linear-gradient(180deg, #fffdf9 0%, #fff9ef 100%);
  border-radius: 22px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.panel-header,
.task-topline,
.task-meta,
.filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.panel-kicker {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #8f6c38;
  font-weight: 700;
}

.panel-title {
  margin: 6px 0 0;
  font-size: 22px;
  color: #181818;
}

.panel-copy,
.task-summary,
.task-meta {
  color: #62584d;
  line-height: 1.6;
  font-size: 13px;
}

.prototype-pill,
.task-pill,
.filter-chip {
  border-radius: 999px;
  border: 1px solid #e6d3b7;
  background: rgba(255, 255, 255, 0.88);
  color: #6b5434;
  font-size: 12px;
  padding: 5px 10px;
}

.filter-row {
  justify-content: flex-start;
}

.filter-chip {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.filter-chip.active {
  border-color: #bf7d28;
  background: #fff3df;
  color: #7b4e16;
}

.chip-count {
  font-weight: 700;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  width: 100%;
  text-align: left;
  border: 1px solid #eadfcb;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}

.task-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(85, 60, 23, 0.08);
}

.task-card.active {
  border-color: #bf7d28;
  box-shadow: 0 12px 24px rgba(191, 125, 40, 0.12);
}

.task-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f1c18;
}

.task-pill.severity.high {
  color: #8c3a2b;
  border-color: #e3b8af;
  background: #fff5f3;
}

.task-pill.severity.medium {
  color: #8a6526;
  border-color: #ead4a6;
  background: #fff9ee;
}

.task-pill.severity.low {
  color: #4f6b59;
  border-color: #cfe1d5;
  background: #f6fcf7;
}

.task-pill.status.approved {
  color: #2f6848;
  border-color: #c4ddcb;
  background: #f3fbf5;
}

.task-pill.status.questioned {
  color: #8a6526;
  border-color: #ead4a6;
  background: #fff9ee;
}

.task-pill.status.ignored {
  color: #71685e;
  border-color: #e5ddd2;
  background: #faf8f4;
}
</style>
