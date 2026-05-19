<template>
  <article :class="['cluster-card', `cluster-${cluster.status || 'candidate'}`]">
    <div class="card-head">
      <div>
        <h3>{{ cluster.title }}</h3>
        <div class="cluster-id">{{ cluster.cluster_id }}</div>
      </div>
      <div class="badges">
        <span :class="['status', `status-${cluster.status || 'candidate'}`]">{{ statusLabel(cluster.status) }}</span>
        <span class="relevance">{{ relevanceLabel(cluster.strategic_relevance) }}</span>
      </div>
    </div>
    <p class="desc">{{ cluster.description || '暂无描述' }}</p>
    <div class="counts">
      <span>Wiki {{ cluster.counts?.wiki_topics || 0 }}</span>
      <span>文章 {{ cluster.article_count || 0 }}</span>
      <span>KFC 主题 {{ cluster.counts?.kfc_themes || 0 }}</span>
      <span>研究项目 {{ cluster.counts?.research_projects || 0 }}</span>
      <span v-if="cluster.counts?.candidate_links">候选 {{ cluster.counts.candidate_links }}</span>
      <span v-if="cluster.counts?.needs_review_links">待复核 {{ cluster.counts.needs_review_links }}</span>
    </div>
    <div v-if="cluster.representative_articles?.length" class="article-preview">
      <div class="preview-label">代表文章</div>
      <div v-for="article in cluster.representative_articles.slice(0, 3)" :key="article.candidate_id || article.source_id || article.title" class="preview-item">
        {{ article.title }}
      </div>
    </div>
    <div class="preview-grid">
      <div>
        <div class="preview-label">Wiki 主题</div>
        <div v-if="!wikiLinks.length" class="preview-empty">暂无</div>
        <div v-for="link in wikiLinks.slice(0, 3)" :key="link.link_id" class="preview-item">
          {{ link.target_title || link.target_id }}
        </div>
      </div>
      <div>
        <div class="preview-label">KFC Theme</div>
        <div v-if="!themeLinks.length" class="preview-empty">暂无</div>
        <div v-for="link in themeLinks.slice(0, 3)" :key="link.link_id" class="preview-item">
          {{ link.target_title || link.target_id }}
        </div>
      </div>
    </div>
    <div class="card-actions">
      <router-link
        class="open-link"
        :to="`/workspace/topic-clusters/${cluster.cluster_id}`"
        target="_blank"
        rel="noopener noreferrer"
      >
        打开主题簇
      </router-link>
    </div>
  </article>
</template>

<script setup>
defineProps({
  cluster: { type: Object, required: true },
  wikiLinks: { type: Array, default: () => [] },
  themeLinks: { type: Array, default: () => [] },
})

function statusLabel(status) {
  const map = {
    active: 'Active',
    candidate: 'Candidate',
    needs_review: 'Needs review',
    retired: 'Retired',
  }
  return map[status] || status || 'Candidate'
}

function relevanceLabel(value) {
  const map = {
    high: '战略相关度高',
    medium: '战略相关度中',
    low: '战略相关度低',
    unknown: '相关度待定',
  }
  return map[value] || value || '相关度待定'
}
</script>

<style scoped>
.cluster-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  background: var(--kfc-surface, var(--bg-surface));
  padding: 16px 16px 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.cluster-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--state-candidate);
}
.cluster-card.cluster-active::before {
  background: var(--state-linked);
}
.cluster-card.cluster-needs_review {
  border-top: 4px solid rgba(192, 86, 33, 0.42);
}
.cluster-card.cluster-retired {
  opacity: 0.72;
}
.cluster-card.cluster-retired::before {
  background: var(--state-ignored);
}
.card-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
h3 {
  margin: 0;
  font-size: 18px;
}
.cluster-id {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}
.badges {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}
.status,
.relevance {
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  border: 1px solid var(--border-default);
  white-space: nowrap;
}
.status-active {
  color: #ffffff;
  background: var(--state-linked);
  border-color: var(--state-linked);
}
.status-candidate,
.status-needs_review {
  color: #ffffff;
  background: var(--state-candidate);
  border-color: var(--state-candidate);
}
.status-needs_review {
  background: var(--state-warning);
  border-color: var(--state-warning);
}
.status-retired {
  color: #ffffff;
  background: var(--state-ignored);
  border-color: var(--state-ignored);
}
.desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.counts,
.preview-grid {
  display: grid;
  gap: 8px;
}
.counts {
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
}
.counts span {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 8px 10px;
  color: var(--text-secondary);
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  font-size: 12px;
}
.preview-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}
.preview-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.preview-item,
.preview-empty {
  font-size: 13px;
  line-height: 1.5;
}
.preview-empty {
  color: var(--text-muted);
}
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.open-link {
  width: fit-content;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 8px 12px;
  text-decoration: none;
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-weight: 700;
  font-size: 13px;
}
.open-link:hover {
  background: var(--kfc-surface-muted, var(--bg-surface-2));
}
</style>
