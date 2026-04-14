<template>
  <div class="xrel-card" :class="{ expanded: isExpanded }">
    <!-- Compact view (always visible) -->
    <div class="xrel-header">
      <div class="xrel-direction">
        <span class="xrel-concept-name">{{ sourceName }}</span>
        <span class="xrel-arrow">{{ directionArrow }}</span>
        <span class="xrel-concept-name target" @click="$emit('navigate', otherEntryId)">
          {{ otherName }}
        </span>
        <span class="xrel-article-tag">{{ targetArticle }}</span>
      </div>
      <span class="xrel-type-badge" :class="relation.relation_type">
        {{ typeLabel }}
      </span>
    </div>

    <p class="xrel-reason">{{ relation.reason }}</p>

    <div class="xrel-meta">
      <span class="xrel-confidence">{{ (relation.confidence * 100).toFixed(0) }}%</span>
      <span class="xrel-source">{{ relation.source }}</span>
      <span class="xrel-review" :class="relation.review_status">{{ reviewLabel }}</span>
    </div>

    <div class="xrel-actions">
      <button class="btn-xrel" @click="$emit('navigate', otherEntryId)">
        查看关联概念
      </button>
      <button class="btn-xrel" @click="isExpanded = !isExpanded">
        {{ isExpanded ? '收起详情' : '展开详情' }}
      </button>
    </div>

    <!-- Expanded view -->
    <div v-if="isExpanded" class="xrel-expanded">
      <div v-if="relation.evidence_bridge" class="xrel-evidence">
        <div class="xrel-label">关系说明</div>
        <p>{{ relation.evidence_bridge }}</p>
      </div>

      <div v-if="sourceTextRefs.length" class="xrel-refs">
        <div class="xrel-label">
          节点摘要支撑
          <span class="xrel-degraded-hint" title="这是 phase-1 阶段 LLM 从原文中抽取的节点摘要，指向来源文章的具体节点；不是原文逐字引用，阅读时点击『跳至该文章图谱』进入原文上下文。">?</span>
        </div>
        <div v-for="(ref, i) in sourceTextRefs" :key="`s${i}`" class="xrel-ref-item">
          <div class="xrel-ref-source">
            <span class="xrel-ref-project">{{ ref.project_name || ref.project_id }}</span>
            <span v-if="ref.group_title" class="xrel-ref-section">· {{ ref.group_title }}</span>
            <span class="xrel-ref-concept">· {{ ref.concept_key }}</span>
          </div>
          <p class="xrel-ref-text">{{ ref.source_text }}</p>
          <a v-if="ref.project_id"
             :href="`/process/${ref.project_id}?mode=graph&view=reading&focusNode=${encodeURIComponent(ref.concept_key)}&from=registry`"
             target="_blank"
             class="xrel-ref-jump"
          >跳至该文章图谱 ↗</a>
        </div>
      </div>

      <div v-if="degradedRefs.length" class="xrel-refs xrel-degraded">
        <div class="xrel-label">
          节点摘要支撑（待补齐）
          <span class="xrel-degraded-hint" title="图谱中未找到对应节点，或节点已存在但 summary 为空。需要跑 phase-1 重建或人工补齐节点摘要。">?</span>
        </div>
        <div v-for="(ref, i) in degradedRefs" :key="`d${i}`" class="xrel-ref-item xrel-ref-item-degraded">
          <div class="xrel-ref-source">
            <span class="xrel-ref-project">{{ ref.project_name || ref.project_id || '未知文章' }}</span>
            <span class="xrel-ref-concept" v-if="ref.concept_key">· {{ ref.concept_key }}</span>
          </div>
          <p class="xrel-ref-text xrel-ref-text-degraded">{{ ref.degraded_reason || '未找到原文支撑' }}</p>
        </div>
      </div>

      <div v-if="legacyQuoteOnly" class="xrel-refs xrel-legacy">
        <div class="xrel-label">
          关系复述（旧数据）
          <span class="xrel-degraded-hint" title="这是迁移前的旧引用字段，文本与关系说明重复。请运行 scripts/migrate_xrel_evidence_refs.py --apply 升级到原文锚定。">?</span>
        </div>
        <div v-for="(ref, i) in legacyQuotes" :key="`q${i}`" class="xrel-ref-item">
          <span class="xrel-quote">"{{ ref.quote }}"</span>
        </div>
      </div>

      <div v-if="relation.discovery_path?.length" class="xrel-path">
        <div class="xrel-label">发现路径</div>
        <div class="xrel-breadcrumb">
          <span v-for="(step, i) in relation.discovery_path" :key="i">
            {{ step }}<span v-if="i < relation.discovery_path.length - 1" class="xrel-path-sep"> &rarr; </span>
          </span>
        </div>
      </div>

      <div class="xrel-article-link" v-if="targetProjectId">
        <a :href="`/process/${targetProjectId}?mode=graph&view=reading&focusNode=${encodeURIComponent(targetConceptKey)}&from=registry`"
           target="_blank" class="btn-xrel btn-primary">
          看来源文章 ↗
        </a>
      </div>

      <div class="xrel-review-actions">
        <button v-if="relation.review_status !== 'accepted'" class="btn-xrel btn-accept"
                @click="$emit('review', relation.relation_id, 'accepted')">
          接受
        </button>
        <button v-if="relation.review_status !== 'rejected'" class="btn-xrel btn-reject"
                @click="$emit('review', relation.relation_id, 'rejected')">
          驳回
        </button>
        <button class="btn-xrel btn-danger" @click="$emit('delete', relation.relation_id)">
          删除
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  relation: { type: Object, required: true },
  conceptMap: { type: Object, default: () => ({}) },  // entry_id -> { canonical_name, source_links, ... }
  currentEntryId: { type: String, default: '' },  // the concept currently being viewed
})

defineEmits(['navigate', 'review', 'delete'])

const isExpanded = ref(false)

const TYPE_LABELS = {
  design_inspiration: '设计启示',
  technical_foundation: '技术支撑',
  problem_solution: '问题-方案',
  contrast_reference: '对比参照',
  capability_constraint: '能力约束',
  pattern_reuse: '模式借鉴',
}

const REVIEW_LABELS = {
  unreviewed: '待审阅',
  accepted: '已接受',
  rejected: '已驳回',
  needs_revision: '需修改',
}

const typeLabel = computed(() => TYPE_LABELS[props.relation.relation_type] || props.relation.relation_type)
const reviewLabel = computed(() => REVIEW_LABELS[props.relation.review_status] || props.relation.review_status)

// Determine "the other concept" — the one you'd want to navigate TO
// If I'm viewing the source, the other is the target (and vice versa)
const isViewingSource = computed(() => props.currentEntryId === props.relation.source_entry_id)

const selfEntry = computed(() => {
  const id = isViewingSource.value ? props.relation.source_entry_id : props.relation.target_entry_id
  return props.conceptMap[id] || {}
})
const otherEntry = computed(() => {
  const id = isViewingSource.value ? props.relation.target_entry_id : props.relation.source_entry_id
  return props.conceptMap[id] || {}
})
const otherEntryId = computed(() => isViewingSource.value ? props.relation.target_entry_id : props.relation.source_entry_id)

const selfName = computed(() => selfEntry.value.canonical_name || props.currentEntryId)
const otherName = computed(() => otherEntry.value.canonical_name || otherEntryId.value)

// Direction arrow: if viewing source, show →; if viewing target, show ←; if bidirectional, show ↔
const directionArrow = computed(() => {
  if (props.relation.directionality === 'bidirectional') return '↔'
  return isViewingSource.value ? '→' : '←'
})

const otherArticle = computed(() => {
  const links = otherEntry.value.source_links || []
  return links[0]?.project_name || ''
})

const otherProjectId = computed(() => {
  const links = otherEntry.value.source_links || []
  return links[0]?.project_id || ''
})

const otherConceptKey = computed(() => {
  const links = otherEntry.value.source_links || []
  return links[0]?.concept_key || ''
})

// Keep backward compat names used in template
const sourceName = selfName
const targetName = otherName
const targetArticle = otherArticle
const targetProjectId = otherProjectId
const targetConceptKey = otherConceptKey

// Evidence refs split into three buckets so the UI can label them honestly:
// - sourceTextRefs: real article-summary evidence (post-migration refs)
// - degradedRefs:   refs that resolved to the right concept but lack summary
// - legacyQuotes:   old pre-migration quotes (duplicate of evidence_bridge)
const allRefs = computed(() => props.relation.evidence_refs || [])
const sourceTextRefs = computed(() => allRefs.value.filter(
  r => r && r.source_text && !r.degraded
))
const degradedRefs = computed(() => allRefs.value.filter(
  r => r && r.degraded === true
))
const legacyQuotes = computed(() => allRefs.value.filter(
  r => r && !('source_text' in r) && !('degraded' in r) && r.quote
))
// True when the only evidence we have is legacy quotes — surface this so
// users (and reviewers) know the relation needs migration.
const legacyQuoteOnly = computed(
  () => legacyQuotes.value.length > 0 && sourceTextRefs.value.length === 0
)
</script>

<style scoped>
.xrel-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px 16px;
  background: #fff;
  transition: box-shadow 0.15s;
}
.xrel-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.xrel-card.expanded { border-color: #c7d2fe; background: #fafbff; }

.xrel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 8px; }

.xrel-direction { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.xrel-concept-name { font-weight: 600; color: #1d1d1d; }
.xrel-concept-name.target { color: #4a6fa5; cursor: pointer; }
.xrel-concept-name.target:hover { text-decoration: underline; }
.xrel-arrow { color: #9ca3af; font-size: 14px; }
.xrel-article-tag { font-size: 11px; color: #6b7280; background: #f3f4f6; padding: 1px 6px; border-radius: 4px; }

.xrel-type-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
  white-space: nowrap; flex-shrink: 0;
}
.xrel-type-badge.design_inspiration { background: #fef3c7; color: #92400e; }
.xrel-type-badge.technical_foundation { background: #dbeafe; color: #1e40af; }
.xrel-type-badge.problem_solution { background: #d1fae5; color: #065f46; }
.xrel-type-badge.contrast_reference { background: #ede9fe; color: #5b21b6; }
.xrel-type-badge.capability_constraint { background: #fee2e2; color: #991b1b; }
.xrel-type-badge.pattern_reuse { background: #e0e7ff; color: #3730a3; }

.xrel-reason { font-size: 13px; color: #374151; line-height: 1.5; margin: 0 0 8px; }

.xrel-meta { display: flex; gap: 10px; font-size: 11px; color: #9ca3af; margin-bottom: 8px; }
.xrel-confidence { font-weight: 600; }
.xrel-review.accepted { color: #059669; }
.xrel-review.rejected { color: #dc2626; }
.xrel-review.unreviewed { color: #d97706; }

.xrel-actions { display: flex; gap: 8px; }
.btn-xrel {
  font-size: 12px; padding: 4px 10px; border: 1px solid #e5e7eb; border-radius: 6px;
  background: #fff; color: #374151; cursor: pointer; transition: all 0.15s;
}
.btn-xrel:hover { border-color: #4a6fa5; color: #4a6fa5; }
.btn-xrel.btn-primary { background: #4a6fa5; color: #fff; border-color: #4a6fa5; }
.btn-xrel.btn-primary:hover { background: #3b5998; }
.btn-xrel.btn-accept { color: #059669; border-color: #a7f3d0; }
.btn-xrel.btn-accept:hover { background: #d1fae5; }
.btn-xrel.btn-reject { color: #dc2626; border-color: #fecaca; }
.btn-xrel.btn-reject:hover { background: #fee2e2; }
.btn-xrel.btn-danger { color: #dc2626; border-color: #fecaca; }
.btn-xrel.btn-danger:hover { background: #fee2e2; }

/* Expanded section */
.xrel-expanded { margin-top: 12px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
.xrel-label { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.xrel-evidence, .xrel-refs, .xrel-path { margin-bottom: 12px; }
.xrel-evidence p, .xrel-refs p { font-size: 13px; color: #374151; line-height: 1.6; margin: 0; }
.xrel-quote { font-style: italic; color: #6b7280; font-size: 12px; }
.xrel-ref-item { padding: 8px 10px; border-left: 2px solid #c7d2fe; background: #fafbff; border-radius: 0 6px 6px 0; margin-bottom: 6px; }
.xrel-ref-item:last-child { margin-bottom: 0; }
.xrel-ref-source { font-size: 11px; color: #4a6fa5; margin-bottom: 4px; }
.xrel-ref-project { font-weight: 600; }
.xrel-ref-section { color: #0ea5e9; font-weight: 500; }
.xrel-ref-concept { color: #6b7280; }
.xrel-ref-text { font-size: 13px; color: #1d1d1d; line-height: 1.5; margin: 0 0 4px; }
.xrel-ref-jump { font-size: 11px; color: #4a6fa5; text-decoration: none; }
.xrel-ref-jump:hover { text-decoration: underline; }
.xrel-ref-item-degraded { border-left-color: #fde68a; background: #fffbeb; }
.xrel-ref-text-degraded { color: #92400e; font-size: 12px; font-style: italic; }
.xrel-degraded-hint { display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: #fde68a; color: #92400e; font-size: 10px; text-align: center; line-height: 14px; margin-left: 4px; cursor: help; }
.xrel-legacy .xrel-ref-item { border-left-color: #fecaca; background: #fef2f2; }
.xrel-breadcrumb { font-size: 12px; color: #4a6fa5; }
.xrel-path-sep { color: #9ca3af; }
.xrel-article-link { margin-bottom: 12px; }
.xrel-review-actions { display: flex; gap: 8px; margin-top: 8px; }
</style>
