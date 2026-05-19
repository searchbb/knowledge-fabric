<template>
  <div class="asset-list">
    <h4>{{ title }}</h4>
    <div v-if="!items.length" class="empty-note">{{ emptyText }}</div>
    <article
      v-for="item in visibleItems"
      :key="itemKey(item)"
      class="asset-item"
      :data-target-id="item.target_id || item.topic_id || item.link_id"
      :data-target-type="item.target_type || item.source_kind || 'asset'"
    >
      <div class="asset-item-head">
        <strong>{{ item.target_title || item.title || item.topic_id || item.target_id }}</strong>
        <span>{{ badgeLabel(item) }}</span>
      </div>
      <p v-if="item.parent_research_project_title" class="source-line">
        所属研究项目：{{ item.parent_research_project_title }}
      </p>
      <p v-if="item.match_reason">{{ item.match_reason }}</p>
      <p v-else-if="item.digest_summary">{{ item.digest_summary }}</p>
      <p v-if="item.matched_fields?.length" class="source-line">命中字段：{{ item.matched_fields.join(', ') }}</p>
      <p v-if="item.why_candidate?.strong_terms?.length || item.why_candidate?.weak_terms?.length" class="source-line">
        强词：{{ (item.why_candidate.strong_terms || []).join(', ') || '无' }}；
        弱词：{{ (item.why_candidate.weak_terms || []).join(', ') || '无' }}
      </p>
      <p v-if="item.risk_note" class="risk-note">{{ item.risk_note }}</p>
      <small>{{ item.source_kind || item.target_type || 'wiki_topic' }} · {{ item.target_id || item.topic_id || item.link_id }}</small>
      <small v-if="item.source_path_display || item.source_path" class="source-path">
        来源：{{ item.source_path_display || item.source_path }}
      </small>
      <div v-if="hasActions(item)" class="asset-actions">
        <a v-if="item.drilldown_route" class="asset-action" :href="item.drilldown_route" target="_blank" rel="noopener noreferrer">{{ drilldownLabel(item) }}</a>
        <a v-if="item.source_url || item.routes?.source_url" class="asset-action" :href="item.source_url || item.routes.source_url" target="_blank" rel="noopener noreferrer">打开原文</a>
        <a v-if="item.routes?.wiki_intake" class="asset-action" :href="item.routes.wiki_intake" target="_blank" rel="noopener noreferrer">阅读 Intake</a>
        <a v-if="item.routes?.verified_digest" class="asset-action" :href="item.routes.verified_digest" target="_blank" rel="noopener noreferrer">查看消化结果</a>
        <a v-if="item.routes?.source_file" class="asset-action" :href="item.routes.source_file" target="_blank" rel="noopener noreferrer">来源文件</a>
        <button class="asset-action" type="button" @click="toggleDetails(item)">
          {{ isOpen(item) ? '收起候选详情' : '查看候选详情' }}
        </button>
        <button
          v-if="item.promotion_supported"
          class="promote-btn"
          type="button"
          @click="$emit('promote', item)"
        >
          {{ promoteLabel(item) }}
        </button>
      </div>
      <div v-else class="route-note">暂无详情页，仅展示只读候选信息。</div>
      <div v-if="isOpen(item)" class="metadata-panel">
        <dl>
          <div>
            <dt>类型</dt>
            <dd>{{ item.target_type || item.source_kind || 'candidate' }}</dd>
          </div>
          <div>
            <dt>置信度</dt>
            <dd>{{ item.confidence_hint || '未标注' }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ item.confirmation_status || item.status || '候选，非正式关联' }}</dd>
          </div>
          <div v-if="item.matched_terms?.length">
            <dt>命中词</dt>
            <dd>{{ item.matched_terms.join(', ') }}</dd>
          </div>
          <div v-if="item.matched_fields?.length">
            <dt>命中字段</dt>
            <dd>{{ item.matched_fields.join(', ') }}</dd>
          </div>
          <div v-if="item.source_kind">
            <dt>来源类型</dt>
            <dd>{{ item.source_kind }}</dd>
          </div>
          <div v-if="item.source_path_display || item.source_path">
            <dt>来源路径</dt>
            <dd>{{ item.source_path_display || item.source_path }}</dd>
          </div>
          <div v-if="item.risk_note">
            <dt>边界说明</dt>
            <dd>{{ item.risk_note }}</dd>
          </div>
        </dl>
      </div>
    </article>
    <div v-if="hiddenCount > 0" class="hidden-note">
      已默认折叠 {{ hiddenCount }} 条低优先级候选。
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  emptyText: { type: String, default: '暂无条目。' },
  limit: { type: Number, default: 10 },
})
defineEmits(['promote'])

const openIds = ref(new Set())
const visibleItems = computed(() => props.items.slice(0, props.limit))
const hiddenCount = computed(() => Math.max(0, props.items.length - visibleItems.value.length))

function badgeLabel(item) {
  if (item.association_type === 'formal' || item.association_kind === 'direct_link') return '正式关联'
  if (item.association_type === 'candidate' || item.confirmation_status === 'unconfirmed') {
    return `候选 / 未确认${item.confidence_hint ? ` / ${item.confidence_hint}` : ''}`
  }
  return item.association_kind || item.confidence_hint || item.status || 'candidate'
}

function hasActions(item) {
  return Boolean(
    item.drilldown_route
    || item.source_url
    || item.routes?.source_url
    || item.routes?.wiki_intake
    || item.routes?.verified_digest
    || item.routes?.source_file
    || item.promotion_supported,
  )
}

function itemKey(item) {
  const type = item.target_type || item.source_kind || 'asset'
  return `${type}:${item.target_id || item.topic_id || item.link_id || item.target_title}`
}

function isOpen(item) {
  return openIds.value.has(itemKey(item))
}

function toggleDetails(item) {
  const next = new Set(openIds.value)
  const key = itemKey(item)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  openIds.value = next
}

function drilldownLabel(item) {
  if (item.target_type === 'research_project') return '打开项目'
  if (['evidence', 'insight', 'artifact'].includes(item.target_type)) return '打开所属项目'
  return '打开详情'
}

function promoteLabel(item) {
  if (item.target_type === 'kfc_theme') return '建议建立正式 Theme 关联'
  if (item.target_type === 'research_project') return '建议建立正式项目关联'
  return '建议建立正式关联'
}
</script>

<style scoped>
.asset-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.asset-list h4 {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-primary);
}
.asset-item {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 10px;
  background: var(--bg-base);
}
.asset-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.asset-item-head strong {
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
.asset-item-head span {
  flex: 0 0 auto;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 2px 7px;
  color: var(--text-muted);
  font-size: 11px;
}
.asset-item p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
}
.asset-item small,
.empty-note {
  display: block;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.risk-note {
  color: #7c4a03;
}
.source-line,
.source-path {
  color: var(--text-muted);
}
.route-note,
.hidden-note {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}
.asset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.asset-action,
.promote-btn {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 5px 8px;
  background: var(--bg-surface);
  color: var(--accent-primary-hover);
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
.promote-btn {
  color: var(--text-primary);
}
.metadata-panel {
  margin-top: 8px;
  border-top: 1px solid var(--border-default);
  padding-top: 8px;
}
.metadata-panel dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
}
.metadata-panel dt {
  color: var(--text-muted);
  font-size: 11px;
}
.metadata-panel dd {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}
</style>
