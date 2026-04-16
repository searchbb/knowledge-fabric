<template>
  <section class="action-panel">
    <div class="panel-kicker">Action</div>
    <h3 class="panel-title">人工判断区</h3>
    <p class="panel-copy">当前动作只在原型页内生效，不写数据库；目标是让你判断交互方向，而不是现在就做完审核系统。</p>

    <article class="status-card">
      <div class="status-label">当前任务状态</div>
      <div class="status-value">{{ task?.statusLabel || '未选择任务' }}</div>
      <div class="status-note">{{ task?.lastDecisionLabel || '尚未执行动作' }}</div>
    </article>

    <p v-if="readonly" class="readonly-notice">
      Demo 模式只读：审核动作已禁用，不会写到任何后端。
    </p>

    <div class="action-group">
      <button
        v-for="decision in decisions"
        :key="decision.key"
        class="decision-button"
        :class="decision.tone"
        :disabled="!task || readonly"
        :title="readonly ? 'Demo 模式只读' : ''"
        @click="$emit('apply-decision', decision.key)"
      >
        {{ decision.label }}
      </button>
    </div>

    <article class="signal-card">
      <div class="status-label">人工说明输入</div>
      <textarea
        class="manual-note"
        :value="task?.manualNote || ''"
        :disabled="!task || readonly"
        :placeholder="readonly ? 'Demo 模式只读，无法编辑说明。' : '例如：把 Markdown 视为工具层 canonical，格式与内容分离更像它的机制，不要直接合并。'"
        @input="$emit('update-manual-note', $event.target.value)"
      />
      <div class="signal-line">你的说明会被记录为当前任务的人工指导语，用来约束后续 AI 处理方向。</div>
    </article>

    <article class="signal-card">
      <div class="status-label">AI 处理预览</div>
      <div class="signal-line">{{ task?.assistantPreview || '选择任务后，这里会显示 AI 如何结合你的说明处理当前任务。' }}</div>
    </article>

    <article class="signal-card">
      <div class="status-label">Phase 1 信号</div>
      <div class="signal-line">Provider：{{ phase1TaskResult?.provider || 'unknown' }}</div>
      <div class="signal-line">构建状态：{{ phase1TaskResult?.build_outcome?.status || 'unknown' }}</div>
      <div class="signal-line">阅读骨架：{{ phase1TaskResult?.reading_structure_status?.status || 'unknown' }}</div>
      <div class="signal-line">Warning：{{ warningCount }}</div>
    </article>

    <article class="signal-card">
      <div class="status-label">为什么先做原型</div>
      <div class="signal-line">先确认 review 的心智模型是否成立，再接真实 ReviewTask API。</div>
      <div class="signal-line">保留“通过 / 存疑 / 忽略”三个最小动作，避免过早绑定复杂审核流。</div>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: {
    type: Object,
    default: null,
  },
  decisions: {
    type: Array,
    default: () => [],
  },
  phase1TaskResult: {
    type: Object,
    default: null,
  },
  readonly: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['apply-decision', 'update-manual-note'])

const warningCount = computed(() => props.phase1TaskResult?.build_outcome?.warnings?.length || 0)
</script>

<style scoped>
.action-panel {
  border: 1px solid #eadfcb;
  background: linear-gradient(180deg, #fffdfa 0%, #fff7eb 100%);
  border-radius: 22px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.panel-kicker,
.status-label {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #8f6c38;
  font-weight: 700;
}

.panel-title {
  margin: 0;
  font-size: 22px;
  color: #181818;
}

.panel-copy,
.status-note,
.signal-line {
  color: #62584d;
  line-height: 1.6;
  font-size: 13px;
}

.status-card,
.signal-card {
  border: 1px solid #eadfcb;
  background: rgba(255, 255, 255, 0.84);
  border-radius: 18px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-value {
  font-size: 20px;
  font-weight: 700;
  color: #1e1d19;
}

.action-group {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.readonly-notice {
  margin: 0;
  padding: 8px 12px;
  border: 1px solid #d8b483;
  background: #fff5e0;
  color: #875612;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
}

.decision-button {
  border: 1px solid #e2d1b7;
  border-radius: 16px;
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  background: #fffdf9;
  color: #3f362c;
}

.decision-button.primary {
  background: #1f6d48;
  color: #fff;
  border-color: #1f6d48;
}

.decision-button.secondary {
  background: #fff2da;
  color: #875612;
  border-color: #dfbf8d;
}

.decision-button.ghost {
  background: #faf7f2;
  color: #6f6255;
}

.decision-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.manual-note {
  min-height: 112px;
  resize: vertical;
  border: 1px solid #e0ceb1;
  border-radius: 14px;
  padding: 12px 14px;
  background: #fffefb;
  color: #2f281f;
  font: inherit;
  line-height: 1.6;
}
</style>
