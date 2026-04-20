<template>
  <AppShell :crumbs="crumbs" copy-label="Discover 队列">
    <div class="dq-shell">
      <header class="page-header">
        <div class="section-badge">DISCOVER QUEUE</div>
        <h1 class="section-title">Discover 队列</h1>
        <p class="section-copy">
          跨文章概念关系发现任务的全局视图。主流程只负责把新文章的 discover 任务排进这里；
          后台工人 / 手动运行会消化它们。点击任一行可以看任务详情（漏斗、错误、重试计数等）。
        </p>
      </header>

      <!-- Stats row -->
      <article class="card">
        <div class="card-title">队列概览 · 共 {{ stats.total }} 条</div>
        <div class="dq-counts">
          <div
            v-for="status in STATUS_ORDER"
            :key="status"
            :class="['dq-count', `dq-count--${status}`]"
          >
            <span class="dq-count-label">{{ statusLabel(status) }}</span>
            <span class="dq-count-value">{{ stats.by_status[status] || 0 }}</span>
          </div>
        </div>
        <div class="action-row">
          <button class="btn-small" :disabled="loading" @click="refresh">刷新</button>
          <button
            class="btn-small"
            :disabled="runningOne || (stats.by_status.pending || 0) === 0"
            @click="runOneNow"
          >
            {{ runningOne ? '运行中...' : '手动运行一条' }}
          </button>
          <button class="btn-small" :disabled="recoveringStale" @click="recoverStale">
            {{ recoveringStale ? '恢复中...' : '恢复卡住的任务' }}
          </button>
          <span v-if="lastActionResult" :class="['retry-note', lastActionResult.kind]">
            {{ lastActionResult.text }}
          </span>
        </div>
      </article>

      <!-- Filters -->
      <article class="card dq-filter-card">
        <div class="card-title">筛选</div>
        <div class="dq-filter-row">
          <label class="dq-filter-item">
            <span>状态</span>
            <select v-model="filterStatus">
              <option value="">全部</option>
              <option v-for="s in STATUS_ORDER" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
          </label>
          <label class="dq-filter-item dq-filter-item--grow">
            <span>主题 ID 包含</span>
            <input v-model="filterTheme" placeholder="gtheme_..." />
          </label>
          <label class="dq-filter-item dq-filter-item--grow">
            <span>Job ID 包含</span>
            <input v-model="filterJob" placeholder="djob_..." />
          </label>
        </div>
      </article>

      <!-- Job table -->
      <article class="card dq-table-card">
        <div class="dq-table-head">
          <div class="card-title">任务列表 ({{ filteredJobs.length }}/{{ jobs.length }})</div>
        </div>
        <div v-if="filteredJobs.length === 0" class="dq-empty">
          没有匹配的任务。
        </div>
        <table v-else class="dq-table">
          <thead>
            <tr>
              <th>状态</th>
              <th>Job ID</th>
              <th>主题</th>
              <th>触发项目</th>
              <th>新概念</th>
              <th>创建</th>
              <th>结束</th>
              <th>产出</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in filteredJobs"
              :key="job.job_id"
              class="dq-row"
              @click="openDrawer(job.job_id)"
            >
              <td>
                <span :class="['dq-badge', `dq-badge--${job.status}`]">{{ statusLabel(job.status) }}</span>
              </td>
              <td class="dq-mono">{{ shortId(job.job_id) }}</td>
              <td class="dq-mono">{{ shortId(job.theme_id) }}</td>
              <td class="dq-mono">{{ shortId(job.trigger_project_id) }}</td>
              <td>{{ (job.new_entry_ids || []).length }}</td>
              <td>{{ shortDateTime(job.created_at) }}</td>
              <td>{{ shortDateTime(job.finished_at) || '—' }}</td>
              <td>
                <span v-if="job.stats?.discovered !== undefined">{{ job.stats.discovered }}</span>
                <span v-else>—</span>
              </td>
              <td class="dq-actions">
                <button
                  v-if="canRetry(job.status)"
                  class="btn-tiny"
                  :disabled="busyJobs.has(job.job_id)"
                  @click.stop="retryJob(job.job_id)"
                >重试</button>
                <button
                  v-if="canCancel(job.status)"
                  class="btn-tiny btn-tiny--danger"
                  :disabled="busyJobs.has(job.job_id)"
                  @click.stop="cancelJob(job.job_id)"
                >取消</button>
              </td>
            </tr>
          </tbody>
        </table>
      </article>

      <!-- Reuse the same drawer markup pattern as AutoPipelinePage. -->
      <div v-if="drawerOpen" class="job-drawer-backdrop" @click="closeDrawer">
        <aside class="job-drawer-panel" role="dialog" @click.stop>
          <div class="jd-head">
            <div class="jd-title">
              Discover Job
              <span class="jd-head-id">{{ drawerJobId }}</span>
            </div>
            <button class="jd-close" @click="closeDrawer">×</button>
          </div>
          <div v-if="drawerLoading" class="jd-body"><em>加载中...</em></div>
          <div v-else-if="!drawerJob" class="jd-body"><div class="jd-error">未找到任务或已被清理。</div></div>
          <div v-else class="jd-body">
            <section class="jd-section">
              <dl class="jd-grid">
                <dt>状态</dt>
                <dd><span :class="['dq-badge', `dq-badge--${drawerJob.status}`]">{{ statusLabel(drawerJob.status) }}</span></dd>
                <dt>主题</dt><dd>{{ drawerJob.theme_id || '—' }}</dd>
                <dt>触发项目</dt><dd>{{ drawerJob.trigger_project_id || '—' }}</dd>
                <dt>触发 run</dt><dd>{{ drawerJob.origin_run_id || '—' }}</dd>
                <dt>尝试</dt><dd>{{ drawerJob.attempt_count }} / {{ drawerJob.max_attempts }}</dd>
                <dt>创建</dt><dd>{{ shortDateTime(drawerJob.created_at) }}</dd>
                <dt>开始</dt><dd>{{ shortDateTime(drawerJob.started_at) || '—' }}</dd>
                <dt>结束</dt><dd>{{ shortDateTime(drawerJob.finished_at) || '—' }}</dd>
              </dl>
            </section>
            <section v-if="drawerJob.new_entry_ids?.length" class="jd-section">
              <h4 class="jd-section-title">新概念（{{ drawerJob.new_entry_ids.length }}）</h4>
              <div class="jd-entry-list">
                <code v-for="eid in drawerJob.new_entry_ids" :key="eid" class="jd-entry-chip">{{ eid }}</code>
              </div>
            </section>
            <section v-if="drawerFunnel" class="jd-section">
              <h4 class="jd-section-title">候选漏斗</h4>
              <dl class="jd-grid jd-grid--funnel">
                <dt>原始 pair</dt><dd>{{ drawerFunnel.raw_pairs || 0 }}</dd>
                <dt>增量过滤后</dt><dd>{{ drawerFunnel.after_incremental_gate || 0 }}</dd>
                <dt>跨文章后</dt><dd>{{ drawerFunnel.after_cross_article || 0 }}</dd>
                <dt>去重后</dt><dd>{{ drawerFunnel.after_dedupe_filter || 0 }}</dd>
                <dt>送 LLM</dt><dd>{{ drawerFunnel.sent_to_llm || 0 }}</dd>
                <dt>LLM 接受</dt><dd>{{ drawerFunnel.llm_accepted || 0 }}</dd>
                <dt>落库去重</dt><dd>{{ drawerFunnel.deduped_on_commit || 0 }}</dd>
                <dt>最终写入</dt><dd><strong>{{ drawerFunnel.committed || 0 }}</strong></dd>
              </dl>
            </section>
            <section v-if="(drawerJob.stats?.errors || []).length" class="jd-section">
              <h4 class="jd-section-title">错误（{{ drawerJob.stats.errors.length }}）</h4>
              <pre class="jd-errors">{{ (drawerJob.stats.errors || []).join('\n') }}</pre>
            </section>
          </div>
        </aside>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AppShell from '../../components/common/AppShell.vue'
// The api/index.js response interceptor strips one layer → payload at res.data.
import service from '../../api/index'
import { appMode } from '../../runtime/appMode'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: 'Discover 队列' },
]

const STATUS_ORDER = ['pending', 'running', 'partial', 'completed', 'failed', 'cancelled']

const stats = ref({ total: 0, by_status: {} })
const jobs = ref([])
const loading = ref(false)
const runningOne = ref(false)
const recoveringStale = ref(false)
const lastActionResult = ref(null)
const busyJobs = ref(new Set())

const filterStatus = ref('')
const filterTheme = ref('')
const filterJob = ref('')

const drawerOpen = ref(false)
const drawerJobId = ref('')
const drawerJob = ref(null)
const drawerLoading = ref(false)
const drawerFunnel = computed(() => drawerJob.value?.stats?.funnel || null)

const filteredJobs = computed(() => {
  return jobs.value.filter((j) => {
    if (filterStatus.value && j.status !== filterStatus.value) return false
    if (filterTheme.value && !(j.theme_id || '').includes(filterTheme.value)) return false
    if (filterJob.value && !(j.job_id || '').includes(filterJob.value)) return false
    return true
  })
})

function statusLabel(s) {
  return ({
    pending: '待办',
    running: '运行中',
    completed: '完成',
    partial: '部分完成',
    failed: '失败',
    cancelled: '已取消',
  })[s] || s
}

function shortId(id) {
  if (!id) return '—'
  return id.length > 16 ? `${id.slice(0, 16)}…` : id
}

function shortDateTime(iso) {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(0, 16)
}

function canRetry(status) {
  return status === 'partial' || status === 'failed' || status === 'cancelled'
}
function canCancel(status) {
  return status === 'pending'
}

async function refresh() {
  if (appMode.value === 'demo') {
    stats.value = { total: 0, by_status: {} }
    jobs.value = []
    return
  }
  loading.value = true
  try {
    const [statsRes, listRes] = await Promise.all([
      service({ url: '/api/auto/discover-jobs/stats', method: 'GET' }),
      service({ url: '/api/auto/discover-jobs?limit=500', method: 'GET' }),
    ])
    const s = (statsRes && statsRes.data) || {}
    stats.value = { total: s.total || 0, by_status: s.by_status || {} }
    const l = (listRes && listRes.data) || {}
    jobs.value = l.jobs || []
  } catch (_e) {
    // informational — keep last good
  } finally {
    loading.value = false
  }
}

async function runOneNow() {
  runningOne.value = true
  lastActionResult.value = null
  try {
    const res = await service({
      url: '/api/auto/discover-jobs/run-once',
      method: 'POST',
    })
    const d = (res && res.data) || {}
    if (!d.executed) {
      lastActionResult.value = { kind: 'info', text: '队列为空' }
    } else {
      const o = d.outcome || {}
      const disc = (o.stats || {}).discovered || 0
      lastActionResult.value = {
        kind: o.status === 'failed' ? 'err' : 'ok',
        text: `${o.job_id} → ${statusLabel(o.status)}（新增 ${disc}）`,
      }
    }
  } catch (e) {
    lastActionResult.value = { kind: 'err', text: '运行失败：' + ((e && e.message) || e) }
  } finally {
    runningOne.value = false
    await refresh()
  }
}

async function recoverStale() {
  recoveringStale.value = true
  lastActionResult.value = null
  try {
    const res = await service({
      url: '/api/auto/discover-jobs/recover-stale',
      method: 'POST',
    })
    const d = (res && res.data) || {}
    lastActionResult.value = {
      kind: 'ok',
      text: `重入队 ${(d.requeued || []).length} / 放弃 ${(d.gave_up || []).length}`,
    }
  } catch (e) {
    lastActionResult.value = { kind: 'err', text: '恢复失败：' + ((e && e.message) || e) }
  } finally {
    recoveringStale.value = false
    await refresh()
  }
}

async function retryJob(jobId) {
  const busy = new Set(busyJobs.value); busy.add(jobId); busyJobs.value = busy
  try {
    await service({ url: `/api/auto/discover-jobs/${jobId}/retry`, method: 'POST' })
    lastActionResult.value = { kind: 'ok', text: `${shortId(jobId)} 已重新入队` }
  } catch (e) {
    lastActionResult.value = { kind: 'err', text: '重试失败：' + ((e && e.message) || e) }
  } finally {
    const next = new Set(busyJobs.value); next.delete(jobId); busyJobs.value = next
    await refresh()
  }
}

async function cancelJob(jobId) {
  const busy = new Set(busyJobs.value); busy.add(jobId); busyJobs.value = busy
  try {
    await service({ url: `/api/auto/discover-jobs/${jobId}/cancel`, method: 'POST' })
    lastActionResult.value = { kind: 'ok', text: `${shortId(jobId)} 已取消` }
  } catch (e) {
    lastActionResult.value = { kind: 'err', text: '取消失败：' + ((e && e.message) || e) }
  } finally {
    const next = new Set(busyJobs.value); next.delete(jobId); busyJobs.value = next
    await refresh()
  }
}

async function openDrawer(jobId) {
  drawerJobId.value = jobId
  drawerOpen.value = true
  drawerJob.value = null
  drawerLoading.value = true
  try {
    const res = await service({
      url: `/api/auto/discover-jobs/${encodeURIComponent(jobId)}`,
      method: 'GET',
    })
    drawerJob.value = (res && res.data) || null
  } catch (_e) {
    drawerJob.value = null
  } finally {
    drawerLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  drawerJob.value = null
  drawerJobId.value = ''
}

function onKey(e) {
  if (e.key === 'Escape' && drawerOpen.value) closeDrawer()
}

let poll = null
onMounted(async () => {
  await refresh()
  poll = setInterval(refresh, 6000)
  window.addEventListener('keyup', onKey)
})
onUnmounted(() => {
  if (poll) clearInterval(poll)
  window.removeEventListener('keyup', onKey)
})
</script>

<style scoped>
.dq-shell { max-width: 1200px; margin: 0 auto; padding: 24px; }
.page-header { margin-bottom: 18px; }
.section-badge { font-size: 12px; letter-spacing: 0.18em; color: #4a6fa5; font-weight: 700; }
.section-title { margin: 6px 0 0; font-size: 28px; color: #181818; }
.section-copy { color: #5a6573; line-height: 1.6; max-width: 760px; }
.card {
  border: 1px solid #d4dce8;
  background: linear-gradient(180deg, #fcfdff 0%, #f5f8ff 100%);
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 16px;
}
.card-title { font-weight: 700; color: #211c18; margin-bottom: 10px; }
.action-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.dq-counts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.dq-count {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e3e9f2;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dq-count-label { font-size: 12px; color: #5a6573; }
.dq-count-value { font-size: 22px; font-weight: 700; color: #1b1712; }
.dq-count--failed .dq-count-value { color: #c45a4a; }
.dq-count--partial .dq-count-value { color: #a86d12; }

.dq-filter-card { padding-bottom: 14px; }
.dq-filter-row { display: flex; gap: 12px; flex-wrap: wrap; }
.dq-filter-item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #5a6573; min-width: 150px; }
.dq-filter-item--grow { flex: 1; }
.dq-filter-item input, .dq-filter-item select {
  border: 1px solid #d4dce8; border-radius: 8px; padding: 6px 10px; font-size: 13px;
}

.dq-table-card { padding: 0; }
.dq-table-head { padding: 16px 18px 8px; }
.dq-empty { padding: 30px; color: #7a7a7a; text-align: center; }
.dq-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dq-table th, .dq-table td {
  text-align: left; padding: 8px 12px; border-bottom: 1px solid #f0f2f5;
}
.dq-table th { background: #f5f8ff; color: #4a6fa5; font-weight: 600; }
.dq-row { cursor: pointer; }
.dq-row:hover { background: #f5f8ff; }
.dq-mono { font-family: 'SFMono-Regular', Menlo, monospace; color: #5a6573; font-size: 12px; }
.dq-actions { display: flex; gap: 6px; }

.dq-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #eef2f8;
  color: #4a6fa5;
  font-weight: 600;
}
.dq-badge--running { background: #e7f3ec; color: #2d7a47; }
.dq-badge--partial { background: #fbeed7; color: #a86d12; }
.dq-badge--failed { background: #fbe4e0; color: #c45a4a; }
.dq-badge--cancelled { background: #eeeeee; color: #777; }
.dq-badge--completed { background: #e8f1ff; color: #336ea8; }

.btn-small {
  font-size: 13px; padding: 6px 14px; border-radius: 10px;
  border: 1px solid #4a6fa5; background: #fff; color: #4a6fa5; cursor: pointer;
}
.btn-small:hover:not(:disabled) { background: #4a6fa5; color: #fff; }
.btn-small:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-tiny {
  font-size: 12px; padding: 4px 10px; border-radius: 8px;
  border: 1px solid #4a6fa5; background: #fff; color: #4a6fa5; cursor: pointer;
}
.btn-tiny:hover:not(:disabled) { background: #4a6fa5; color: #fff; }
.btn-tiny:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-tiny--danger { border-color: #c45a4a; color: #c45a4a; }
.btn-tiny--danger:hover:not(:disabled) { background: #c45a4a; color: #fff; }

.retry-note { font-size: 12px; }
.retry-note.ok { color: #059669; }
.retry-note.err { color: #c45a4a; }
.retry-note.info { color: #5a6573; }

/* Drawer — same skin as AutoPipelinePage's so they feel familial. */
.job-drawer-backdrop {
  position: fixed; inset: 0; background: rgba(27, 23, 18, 0.45);
  z-index: 1000; display: flex; justify-content: flex-end;
}
.job-drawer-panel {
  width: min(560px, 90vw); height: 100vh; background: #fcfdff;
  border-left: 1px solid #d4dce8; overflow-y: auto;
  box-shadow: -10px 0 30px rgba(27, 23, 18, 0.15);
}
.jd-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; border-bottom: 1px solid #e3e9f2;
  background: #f5f8ff; position: sticky; top: 0; z-index: 2;
}
.jd-title { font-weight: 700; color: #211c18; font-size: 14px; }
.jd-head-id { font-family: 'SFMono-Regular', Menlo, monospace; font-size: 12px; color: #5a6573; margin-left: 10px; font-weight: 400; }
.jd-close { background: none; border: none; font-size: 24px; line-height: 1; color: #5a6573; cursor: pointer; padding: 0 6px; }
.jd-close:hover { color: #211c18; }
.jd-body { padding: 16px 20px 40px; }
.jd-error { color: #c45a4a; }
.jd-section { margin-bottom: 18px; }
.jd-section-title { font-size: 12px; color: #5a6573; font-weight: 600; margin: 0 0 8px; }
.jd-grid { display: grid; grid-template-columns: 90px 1fr; gap: 4px 12px; margin: 0; font-size: 13px; }
.jd-grid dt { color: #5a6573; }
.jd-grid dd { margin: 0; color: #211c18; }
.jd-grid--funnel { grid-template-columns: 110px 1fr; }
.jd-entry-list { display: flex; flex-wrap: wrap; gap: 6px; }
.jd-entry-chip { font-family: 'SFMono-Regular', Menlo, monospace; font-size: 11px; background: #eef2f8; color: #4a6fa5; padding: 2px 8px; border-radius: 10px; }
.jd-errors {
  font-family: 'SFMono-Regular', Menlo, monospace; font-size: 12px;
  background: #fff8f6; border: 1px solid #e2b0a8; border-radius: 8px;
  padding: 10px; max-height: 240px; overflow: auto;
  white-space: pre-wrap; color: #8f3a2b;
}
</style>
