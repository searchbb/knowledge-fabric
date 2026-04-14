<template>
  <div class="tab-content">
    <!-- Stats -->
    <div class="summary-grid" v-if="stats">
      <article class="card">
        <div class="card-title">总任务</div>
        <div class="metric-value">{{ stats.total }}</div>
      </article>
      <article class="card">
        <div class="card-title">待处理</div>
        <div class="metric-value">{{ (stats.by_status?.open || 0) + (stats.by_status?.reopened || 0) }}</div>
      </article>
      <article class="card">
        <div class="card-title">已完成</div>
        <div class="metric-value">{{ stats.by_status?.resolved || 0 }}</div>
      </article>
    </div>

    <div class="toolbar">
      <select v-model="filterStatus" class="filter-select" @change="loadTasks">
        <option value="">全部状态</option>
        <option value="open">待处理</option>
        <option value="claimed">已认领</option>
        <option value="resolved">已完成</option>
        <option value="reopened">重新打开</option>
      </select>
      <button class="btn-primary" @click="showCreate = true">新建审核任务</button>
      <button
        v-if="selectedIds.length"
        class="btn-small"
        @click="handleBatchResolve"
      >
        批量通过 ({{ selectedIds.length }})
      </button>
    </div>

    <div v-if="loading" class="state-card">正在加载审核队列...</div>

    <div v-else class="tab-layout-2col">
      <!-- Task list -->
      <article class="card queue-card">
        <div class="card-header">
          <div class="card-title">审核任务</div>
          <div class="pill">{{ tasks.length }}</div>
        </div>
        <div v-if="!tasks.length" class="empty-state">暂无审核任务</div>
        <div v-else class="candidate-list">
          <div
            v-for="t in tasks"
            :key="t.task_id"
            class="task-row"
            :class="{ active: t.task_id === selectedTaskId }"
            @click="selectTask(t)"
          >
            <input
              type="checkbox"
              :checked="selectedIds.includes(t.task_id)"
              @click.stop="toggleSelect(t.task_id)"
            />
            <div class="task-info">
              <div class="candidate-topline">
                <span class="candidate-name">{{ t.entity_name || t.entity_id }}</span>
                <span class="priority-badge" :class="t.priority">{{ t.priority }}</span>
              </div>
              <div class="candidate-meta">
                {{ t.action_required }} · {{ t.status }}
                <template v-if="t.resolution"> · {{ t.resolution }}</template>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- Detail + actions -->
      <article class="card detail-card">
        <template v-if="selectedTask">
          <div class="card-header">
            <div>
              <div class="detail-kicker">Review Task</div>
              <h3 class="detail-title">{{ selectedTask.entity_name || selectedTask.entity_id }}</h3>
            </div>
            <div class="detail-badges">
              <span class="chip">{{ selectedTask.status }}</span>
              <span class="chip" :class="selectedTask.priority">{{ selectedTask.priority }}</span>
            </div>
          </div>
          <div class="metric-line">类型: {{ selectedTask.entity_type }}</div>
          <div class="metric-line">操作: {{ selectedTask.action_required }}</div>
          <div v-if="selectedTask.note" class="metric-line">备注: {{ selectedTask.note }}</div>
          <div class="metric-line">创建: {{ selectedTask.created_at }}</div>

          <div class="action-row">
            <button
              v-if="selectedTask.status === 'open'"
              class="btn-small" @click="updateStatus('claimed')"
            >认领</button>
            <button
              v-if="selectedTask.status === 'open' || selectedTask.status === 'claimed'"
              class="btn-primary" @click="updateStatus('resolved')"
            >通过</button>
            <button
              v-if="selectedTask.status === 'resolved'"
              class="btn-small" @click="updateStatus('reopened')"
            >重新打开</button>
          </div>
        </template>

        <!-- Create form -->
        <template v-else-if="showCreate">
          <div class="card-title">新建审核任务</div>
          <div class="form-group">
            <label>实体类型</label>
            <select v-model="createForm.entity_type" class="form-input">
              <option value="concept_entry">概念</option>
              <option value="global_theme">主题</option>
            </select>
          </div>
          <div class="form-group">
            <label>实体 ID</label>
            <input v-model="createForm.entity_id" class="form-input" placeholder="canon_xxx / gtheme_xxx" />
          </div>
          <div class="form-group">
            <label>名称</label>
            <input v-model="createForm.entity_name" class="form-input" />
          </div>
          <div class="form-group">
            <label>操作类型</label>
            <select v-model="createForm.action_required" class="form-input">
              <option value="confirm_link">确认链接</option>
              <option value="review_merge">审核归并</option>
              <option value="verify_alignment">验证对齐</option>
              <option value="approve_theme">确认主题</option>
              <option value="custom">自定义</option>
            </select>
          </div>
          <div class="form-group">
            <label>优先级</label>
            <select v-model="createForm.priority" class="form-input">
              <option value="high">高</option>
              <option value="normal">普通</option>
              <option value="low">低</option>
            </select>
          </div>
          <div class="action-row">
            <button class="btn-primary" @click="handleCreate">创建</button>
            <button class="btn-small" @click="showCreate = false">取消</button>
          </div>
        </template>

        <div v-else class="empty-state">选择任务查看详情，或创建新审核任务</div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import service from '../../../api/index'

const tasks = ref([])
const stats = ref(null)
const loading = ref(false)
const filterStatus = ref('')
const selectedTaskId = ref('')
const selectedTask = ref(null)
const selectedIds = ref([])
const showCreate = ref(false)
const createForm = ref({
  entity_type: 'concept_entry', entity_id: '', entity_name: '',
  action_required: 'confirm_link', priority: 'normal',
})

async function loadTasks() {
  loading.value = true
  try {
    const params = {}
    if (filterStatus.value) params.status = filterStatus.value
    const res = await service({ url: '/api/registry/review/tasks', method: 'get', params })
    tasks.value = res.data?.tasks || []
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  const res = await service({ url: '/api/registry/review/tasks/stats', method: 'get' })
  stats.value = res.data
}

function selectTask(t) {
  selectedTaskId.value = t.task_id
  selectedTask.value = t
  showCreate.value = false
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

async function updateStatus(status) {
  await service({
    url: `/api/registry/review/tasks/${selectedTaskId.value}`,
    method: 'put', data: { status, resolution: status === 'resolved' ? 'approved' : '' },
  })
  await loadTasks()
  await loadStats()
  selectedTask.value = tasks.value.find(t => t.task_id === selectedTaskId.value) || null
}

async function handleBatchResolve() {
  await service({
    url: '/api/registry/review/tasks/batch-resolve',
    method: 'post', data: { task_ids: selectedIds.value, resolution: 'approved' },
  })
  selectedIds.value = []
  await loadTasks()
  await loadStats()
}

async function handleCreate() {
  if (!createForm.value.entity_id) return
  await service({
    url: '/api/registry/review/tasks', method: 'post', data: createForm.value,
  })
  showCreate.value = false
  createForm.value = { entity_type: 'concept_entry', entity_id: '', entity_name: '', action_required: 'confirm_link', priority: 'normal' }
  await loadTasks()
  await loadStats()
}

onMounted(() => { loadTasks(); loadStats() })
</script>

<style scoped>
.tab-content { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.filter-select { border: 1px solid #d4dce8; border-radius: 8px; padding: 8px 12px; font-size: 13px; background: #fff; outline: none; }
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.card, .state-card { border: 1px solid #d4dce8; background: linear-gradient(180deg, #fcfdff 0%, #f5f8ff 100%); border-radius: 18px; padding: 18px; }
.card-title { font-weight: 700; color: #211c18; margin-bottom: 10px; }
.card-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.metric-value { font-size: 28px; font-weight: 700; color: #1b1712; }
.metric-line { color: #5a6573; line-height: 1.6; font-size: 13px; }
.pill, .chip { display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; border: 1px solid #d4dce8; color: #4a6fa5; background: rgba(245, 248, 255, 0.95); font-size: 12px; font-weight: 600; }
.tab-layout-2col { display: grid; grid-template-columns: minmax(300px, 400px) minmax(0, 1fr); gap: 16px; align-items: start; }
.candidate-list { display: flex; flex-direction: column; gap: 8px; }
.task-row { display: flex; align-items: flex-start; gap: 10px; border: 1px solid #d4dce8; background: rgba(255, 255, 255, 0.85); border-radius: 16px; padding: 12px; cursor: pointer; transition: border-color 140ms ease; }
.task-row:hover, .task-row.active { border-color: #4a6fa5; }
.task-row input[type="checkbox"] { margin-top: 4px; }
.task-info { flex: 1; }
.candidate-topline { display: flex; justify-content: space-between; gap: 12px; }
.candidate-name { color: #1e1813; font-weight: 700; }
.candidate-meta { color: #5a6573; font-size: 12px; margin-top: 4px; }
.priority-badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.priority-badge.high { background: #ffebee; color: #c62828; }
.priority-badge.normal { background: #f5f8ff; color: #4a6fa5; }
.priority-badge.low { background: #f5f5f5; color: #757575; }
.detail-kicker { color: #5a6573; font-size: 13px; }
.detail-title { margin: 6px 0 12px; font-size: 24px; color: #1a1713; }
.detail-badges { display: flex; flex-wrap: wrap; gap: 8px; }
.empty-state { color: #7a8090; font-size: 13px; line-height: 1.6; }
.action-row { display: flex; gap: 10px; margin-top: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; font-weight: 600; color: #5a6573; margin-bottom: 4px; }
.form-input { width: 100%; border: 1px solid #d4dce8; border-radius: 8px; padding: 8px 10px; font-size: 13px; outline: none; box-sizing: border-box; }
.btn-primary { background: #4a6fa5; color: #fff; border: none; border-radius: 12px; padding: 10px 18px; font-weight: 600; cursor: pointer; font-size: 14px; white-space: nowrap; }
.btn-small { border: 1px solid #d4dce8; background: #fff; border-radius: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; white-space: nowrap; }
@media (max-width: 960px) { .tab-layout-2col { grid-template-columns: 1fr; } .summary-grid { grid-template-columns: 1fr; } }
</style>
