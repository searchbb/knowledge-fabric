<template>
  <div class="tab-content">
    <div class="toolbar">
      <select v-model="filterEntityType" class="filter-select" @change="loadFeed">
        <option value="">全部类型</option>
        <option value="concept_entry">概念</option>
        <option value="global_theme">主题</option>
        <option value="review_queue">审核</option>
      </select>
      <select v-model="filterEventType" class="filter-select" @change="loadFeed">
        <option value="">全部事件</option>
        <optgroup label="人工">
          <option value="created">创建</option>
          <option value="updated">更新</option>
          <option value="linked">链接</option>
          <option value="deleted">删除</option>
          <option value="concept_attached">概念挂载</option>
          <option value="concept_detached">概念移除</option>
          <option value="review_task_created">审核任务创建</option>
          <option value="review_task_resolved">审核任务完成</option>
        </optgroup>
        <!-- Gap #1 fix: auto-pipeline event types are now in the dropdown
             so the user can filter the feed to only what ran overnight.
             Kept in a separate optgroup so the visual split between
             manual work and unattended pipeline is obvious. -->
        <optgroup label="自动管线">
          <option value="concept_auto_accepted">自动接受概念</option>
          <option value="canonical_auto_created">自动创建 canonical</option>
          <option value="canonical_auto_linked">自动链接 canonical</option>
          <option value="cross_type_match_flagged">跨类型提示</option>
          <option value="theme_auto_created">自动创建主题</option>
          <option value="theme_auto_reused">自动复用主题</option>
          <option value="auto_run_summary">自动运行汇总</option>
        </optgroup>
      </select>
      <!-- Gap #2 fix: actor_type secondary filter. This is orthogonal to
           the event_type filter — e.g. the user may want "all linked
           events by auto" or "all created events by human". -->
      <select v-model="filterActorType" class="filter-select" @change="loadFeed">
        <option value="">全部来源</option>
        <option value="auto">自动管线</option>
        <option value="human">人工操作</option>
      </select>
    </div>

    <div v-if="loading" class="state-card">正在加载演化日志...</div>

    <div v-else class="feed-list">
      <div v-if="!events.length" class="empty-state">暂无演化事件</div>
      <div
        v-for="evt in filteredEvents"
        :key="evt.event_id"
        :class="['feed-item', { 'feed-item-clickable': isClickable(evt) }]"
        :data-entity-type="evt.entity_type"
        @click="handleEventClick(evt)"
      >
        <div class="feed-topline">
          <!-- Gap #2 fix: actor badge in front of the event badge so the
               user sees "auto vs human" before reading the action. -->
          <span :class="['actor-badge', actorBadgeClass(evt.actor_type)]">
            {{ actorLabel(evt.actor_type) }}
          </span>
          <span class="feed-badge" :class="evt.event_type">{{ eventLabel(evt.event_type) }}</span>
          <span class="feed-entity">{{ evt.entity_name || evt.entity_id }}</span>
          <span v-if="isClickable(evt)" class="feed-jump-hint" aria-hidden="true">→</span>
          <span class="feed-time">{{ formatTime(evt.timestamp) }}</span>
        </div>
        <div class="feed-meta">
          {{ evt.entity_type }} · {{ evt.entity_id }}
          <template v-if="evt.project_id"> · 项目: {{ evt.project_id }}</template>
          <template v-if="evt.run_id"> · run: {{ shortRunId(evt.run_id) }}</template>
        </div>
      </div>

      <div v-if="total > events.length" class="load-more">
        <button class="btn-small" @click="loadMore">加载更多 ({{ total - events.length }} 条)</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import service from '../../../api/index'
// NOTE: we no longer directly call loadEntries / selectEntry here — the
// handler just pushes ?select=<id> to the URL and RegistryPage reacts.
// Keeping the imports removed avoids accidental coupling.

const router = useRouter()

const events = ref([])
const total = ref(0)
const loading = ref(false)
const offset = ref(0)
const filterEntityType = ref('')
const filterEventType = ref('')
// Gap #2 fix: client-side actor filter. Backend feed API does not yet
// accept an ``actor_type`` query param, so we filter in-memory after
// loading. This is cheap for the default 50-row page and keeps the
// backend patch minimal.
const filterActorType = ref('')

const eventLabels = {
  created: '创建', updated: '更新', deleted: '删除',
  linked: '链接', unlinked: '解绑', merged: '合并',
  cluster_linked: '簇链接',
  concept_attached: '概念挂载', concept_detached: '概念移除',
  review_task_created: '审核创建', review_task_resolved: '审核完成',
  review_task_claimed: '审核认领', review_task_batch_resolved: '批量完成',
  // auto pipeline labels (Gap #1)
  concept_auto_accepted: '自动接受概念',
  canonical_auto_created: '自动创建 canonical',
  canonical_auto_linked: '自动链接 canonical',
  cross_type_match_flagged: '跨类型提示',
  theme_auto_created: '自动创建主题',
  theme_auto_reused: '自动复用主题',
  auto_run_summary: '自动运行汇总',
}

function eventLabel(type) { return eventLabels[type] || type }
function formatTime(ts) { return ts ? ts.replace('T', ' ').slice(0, 19) : '' }

// Gap #2 fix: short run_id for compact display in the feed meta line.
function shortRunId(rid) {
  if (!rid) return ''
  return rid.length > 14 ? rid.slice(0, 14) + '…' : rid
}

function actorLabel(actor) {
  if (actor === 'auto') return '自动'
  if (actor === 'human') return '人工'
  return '未知'
}

function actorBadgeClass(actor) {
  if (actor === 'auto') return 'actor-auto'
  if (actor === 'human') return 'actor-human'
  return 'actor-unknown'
}

// Gap #2 client-side actor filter. Applied after the backend-served feed
// is loaded so the count in the "load more" button still reflects the
// full unfiltered total — we intentionally do not hide "there are N more
// events matching the other actor" from the user.
const filteredEvents = computed(() => {
  if (!filterActorType.value) return events.value
  return events.value.filter((e) => {
    const actor = e.actor_type || 'human'
    return actor === filterActorType.value
  })
})

// Gap #3 fix: concept_entry events are clickable and jump the user to
// the canonical detail inside the concepts tab. Other entity types stay
// passive on this round (per GPT recommendation "起步只做 concept_entry").
// The handler switches the router query back to tab=concepts AND calls
// the registry store's selectEntry() so the middle column populates.
function isClickable(evt) {
  return evt.entity_type === 'concept_entry' && !!evt.entity_id
}

async function handleEventClick(evt) {
  if (!isClickable(evt)) return
  // Push the URL with tab=concepts + select=<entity_id>. RegistryPage
  // has watchers on route.query.tab AND route.query.select that will
  // flip the active tab, ensure entries are loaded, and call selectEntry
  // for the target canonical. Keeping all navigation-driven state in
  // the URL is cleaner than calling store functions across components
  // and makes the behaviour deep-linkable.
  await router.replace({
    path: '/workspace/registry',
    query: { tab: 'concepts', select: evt.entity_id },
  })
}

async function loadFeed() {
  loading.value = true
  offset.value = 0
  try {
    const params = { limit: 50, offset: 0 }
    if (filterEntityType.value) params.entity_type = filterEntityType.value
    if (filterEventType.value) params.event_type = filterEventType.value
    const res = await service({ url: '/api/registry/evolution/feed', method: 'get', params })
    events.value = res.data?.events || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  offset.value += 50
  const params = { limit: 50, offset: offset.value }
  if (filterEntityType.value) params.entity_type = filterEntityType.value
  if (filterEventType.value) params.event_type = filterEventType.value
  const res = await service({ url: '/api/registry/evolution/feed', method: 'get', params })
  events.value.push(...(res.data?.events || []))
}

onMounted(loadFeed)
</script>

<style scoped>
.tab-content { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.filter-select { border: 1px solid #d4dce8; border-radius: 8px; padding: 8px 12px; font-size: 13px; background: #fff; outline: none; }
.filter-select:focus { border-color: #4a6fa5; }
.state-card { border: 1px solid #d4dce8; background: linear-gradient(180deg, #fcfdff 0%, #f5f8ff 100%); border-radius: 18px; padding: 18px; color: #5a6573; }
.feed-list { display: flex; flex-direction: column; gap: 10px; }
.feed-item { border: 1px solid #d4dce8; background: rgba(255, 255, 255, 0.85); border-radius: 16px; padding: 14px; }

/* Gap #3 fix: clickable feed items get a subtle hover state + a jump
   hint arrow so the user knows which rows are navigable. */
.feed-item-clickable {
  cursor: pointer;
  transition: border-color 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}
.feed-item-clickable:hover {
  border-color: #4a6fa5;
  transform: translateY(-1px);
  box-shadow: 0 8px 22px rgba(74, 111, 165, 0.10);
}
.feed-jump-hint {
  color: #4a6fa5;
  font-weight: 700;
  margin-left: auto;
  margin-right: 8px;
  font-size: 14px;
  opacity: 0;
  transition: opacity 140ms ease;
}
.feed-item-clickable:hover .feed-jump-hint { opacity: 1; }
.feed-topline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* Gap #2 fix: actor badge variants. Distinct shape (square-ish with
   stronger border) so they don't visually collide with the event-type
   pill next to them. */
.actor-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid #d4dce8;
  background: #eef1f5;
  color: #5a6573;
}
.actor-badge.actor-auto {
  background: #ede9fe;
  color: #5b21b6;
  border-color: #c4b5fd;
}
.actor-badge.actor-human {
  background: #e0f2fe;
  color: #075985;
  border-color: #7dd3fc;
}

.feed-badge { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; border: 1px solid #d4dce8; background: #f5f8ff; color: #4a6fa5; }
.feed-badge.created { background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }
.feed-badge.updated { background: #fff3e0; color: #e65100; border-color: #ffcc80; }
.feed-badge.linked { background: #e3f2fd; color: #1565c0; border-color: #90caf9; }
.feed-badge.deleted { background: #ffebee; color: #c62828; border-color: #ef9a9a; }
.feed-entity { font-weight: 700; color: #1d1d1d; }
.feed-time { color: #8a8a8a; font-size: 12px; margin-left: auto; }
.feed-meta { color: #5a6573; font-size: 12px; margin-top: 6px; }
.empty-state { color: #7a8090; font-size: 13px; padding: 20px 0; }
.load-more { text-align: center; padding: 12px; }
.btn-small { border: 1px solid #d4dce8; background: #fff; border-radius: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; }
.btn-small:hover { background: #f5f8ff; }
</style>
