<template>
  <section v-if="current" class="research-context-bar" aria-label="当前研究项目上下文">
    <div class="context-main">
      <span class="context-kicker">当前研究项目</span>
      <strong>{{ current.title }}</strong>
      <span v-if="current.status" class="status-pill">{{ current.status }}</span>
    </div>
    <nav class="context-nav" aria-label="研究项目快捷入口">
      <RouterLink :to="projectRoute">项目首页</RouterLink>
      <RouterLink :to="`${projectRoute}#research-map`">研究地图</RouterLink>
      <RouterLink :to="`${projectRoute}#evidence-basket`">证据篮</RouterLink>
      <RouterLink :to="`${projectRoute}#concept-assets`">概念图谱</RouterLink>
      <RouterLink to="/workspace/research/review">Review</RouterLink>
    </nav>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { readCurrentResearchProject, subscribeCurrentResearchProject } from '../../utils/currentResearchProjectContext'

const current = ref(null)
let unsubscribe = () => {}

const projectRoute = computed(() => (
  current.value?.id ? `/workspace/research?project=${encodeURIComponent(current.value.id)}` : '/workspace/research'
))

onMounted(() => {
  current.value = readCurrentResearchProject()
  unsubscribe = subscribeCurrentResearchProject((next) => {
    current.value = next
  })
})

onBeforeUnmount(() => {
  unsubscribe()
})
</script>

<style scoped>
.research-context-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 28px;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface);
}
.context-main,
.context-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.context-main strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.context-kicker {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}
.status-pill {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--text-muted);
  font-size: 12px;
}
.context-nav a {
  color: var(--accent-primary-hover);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}
@media (max-width: 960px) {
  .research-context-bar {
    align-items: flex-start;
    flex-direction: column;
    padding: 10px 18px;
  }
  .context-nav {
    flex-wrap: wrap;
  }
}
</style>
