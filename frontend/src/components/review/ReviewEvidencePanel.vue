<template>
  <section class="evidence-panel">
    <section v-if="loading && !task" class="empty-state">
      <div class="panel-kicker">Evidence</div>
      <h3 class="panel-title">正在组装证据区</h3>
      <p class="panel-copy">先拉取原文片段、局部子图和跨文章候选，再把它们映射到当前校验任务。</p>
    </section>

    <section v-else-if="error && !task" class="empty-state">
      <div class="panel-kicker">Evidence</div>
      <h3 class="panel-title">证据区加载失败</h3>
      <p class="panel-copy">{{ error }}</p>
    </section>

    <div v-else-if="task" class="panel-body">
      <header class="panel-header">
        <div class="panel-kicker">Evidence</div>
        <h3 class="panel-title">{{ task.title }}</h3>
        <p class="panel-copy">{{ task.summary }}</p>
      </header>

      <div class="meta-row">
        <span class="meta-pill">{{ task.kindLabel }}</span>
        <span class="meta-pill">{{ task.documentLabel }}</span>
        <span class="meta-pill">{{ task.statusLabel }}</span>
      </div>

      <div class="evidence-grid">
        <article v-for="item in task.evidence" :key="`${task.id}-${item.label}`" class="evidence-card">
          <div class="card-label">{{ item.label }}</div>
          <div class="card-value">{{ item.value }}</div>
        </article>
      </div>

      <article class="narrative-card">
        <div class="card-label">原文片段</div>
        <div v-if="task.sourceSnippets?.length" class="snippet-list">
          <div v-for="snippet in task.sourceSnippets" :key="snippet.id" class="snippet-item">
            <div class="snippet-heading">{{ snippet.heading }}</div>
            <p class="snippet-text">{{ snippet.text }}</p>
            <div v-if="snippet.matchedTerms?.length" class="snippet-tags">
              <span v-for="term in snippet.matchedTerms" :key="term" class="meta-pill">{{ term }}</span>
            </div>
          </div>
        </div>
        <p v-else class="card-copy">当前没有命中原文片段，后续可以补更细的 chunk 级证据召回。</p>
      </article>

      <article class="narrative-card">
        <div class="card-label">局部子图</div>
        <ReviewSubgraphPreview :subgraph="task.subgraph" />
      </article>

      <article class="narrative-card">
        <div class="card-label">跨文章候选</div>
        <div v-if="task.crossArticleCandidates?.length" class="candidate-list">
          <div v-for="candidate in task.crossArticleCandidates" :key="candidate.projectId" class="candidate-item">
            <div class="candidate-topline">
              <span class="candidate-name">{{ candidate.name }}</span>
              <span class="meta-pill">{{ candidate.status }}</span>
            </div>
            <div class="card-copy">{{ candidate.reason }}</div>
            <div class="candidate-summary">{{ candidate.summary }}</div>
          </div>
        </div>
        <p v-else class="card-copy">当前还没有跨文章候选，后续会从 canonical/theme 注册层补进来。</p>
      </article>

      <article class="narrative-card">
        <div class="card-label">系统判断理由</div>
        <p class="card-copy">{{ task.rationale }}</p>
      </article>

      <article class="narrative-card">
        <div class="card-label">建议如何处理</div>
        <ul class="suggestion-list">
          <li v-for="suggestion in task.suggestions" :key="suggestion">{{ suggestion }}</li>
        </ul>
      </article>
    </div>

    <section v-else class="empty-state">
      <div class="panel-kicker">Evidence</div>
      <h3 class="panel-title">没有可展示的任务</h3>
      <p class="panel-copy">当前过滤条件下没有任务。你可以切回“全部任务”或等待真实 ReviewTask 接入。</p>
    </section>
  </section>
</template>

<script setup>
import ReviewSubgraphPreview from './ReviewSubgraphPreview.vue'

defineProps({
  task: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})
</script>

<style scoped>
.evidence-panel {
  border: 1px solid #eadfcb;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 22px;
  padding: 20px;
  min-width: 0;
}

.panel-body,
.empty-state {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.panel-kicker,
.card-label {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #8f6c38;
  font-weight: 700;
}

.panel-title {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  color: #181818;
}

.panel-copy,
.card-copy,
.card-value,
.suggestion-list,
.snippet-text,
.candidate-summary {
  color: #62584d;
  line-height: 1.7;
}

.meta-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.meta-pill {
  border-radius: 999px;
  border: 1px solid #eadfcb;
  padding: 6px 10px;
  background: #fffcf7;
  color: #6b5434;
  font-size: 12px;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.evidence-card,
.narrative-card {
  border: 1px solid #ece2d0;
  border-radius: 18px;
  background: linear-gradient(180deg, #fffdf9 0%, #fff8ee 100%);
  padding: 16px;
}

.snippet-list,
.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.snippet-item,
.candidate-item {
  border: 1px solid #efe3d2;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snippet-heading,
.candidate-name {
  font-size: 15px;
  font-weight: 700;
  color: #211c18;
}

.snippet-tags,
.candidate-topline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.suggestion-list {
  margin: 0;
  padding-left: 18px;
}

@media (max-width: 900px) {
  .evidence-grid {
    grid-template-columns: 1fr;
  }
}
</style>
