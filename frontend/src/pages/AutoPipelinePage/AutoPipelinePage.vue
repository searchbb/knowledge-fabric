<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

  <div class="auto-shell">
    <header class="page-header">
      <div class="section-badge">AUTO PIPELINE</div>
      <h1 class="section-title">自动处理队列</h1>
      <p class="section-copy">
        把 URL 加入队列后，后端会依次抓取、构建图谱、接受概念、落库 canonical、命名主题，每一步都带审计痕迹。
        本页是该管线的手动入口——等 OpenClaw 接入后，列表会自动填充。
      </p>
    </header>

    <div v-if="error" class="state-card error-card">{{ error }}</div>

    <!-- LLM 抽取模式开关 (2026-04-15: 本地 qwen3 太慢 → 支持切百炼在线 DashScope qwen3.5-plus) -->
    <article class="mode-card">
      <div class="mode-header">
        <div>
          <div class="card-title">抽取模式</div>
          <p class="section-copy mini-copy">
            切换 Graphiti 抽取走本地 LM Studio 还是百炼（DashScope）在线 API。切换只影响下一个任务,
            有任务在跑的时候会被拒绝。
          </p>
        </div>
        <div v-if="mode.loading" class="mode-loading">加载中...</div>
      </div>

      <div class="mode-switch-row" v-if="!mode.loading">
        <button
          :class="['mode-btn', mode.current === 'local' ? 'mode-btn-active' : '']"
          :disabled="mode.switching || mode.current === 'local'"
          @click="switchMode('local')"
        >
          <span class="mode-btn-title">本地 · qwen3</span>
          <span class="mode-btn-sub">{{ mode.meta.local_model || 'qwen/qwen3-30b-a3b-2507' }}</span>
          <span class="mode-btn-sub">并发 {{ mode.meta.local_semaphore ?? '?' }}</span>
        </button>
        <button
          :class="['mode-btn', mode.current === 'bailian' ? 'mode-btn-active' : '']"
          :disabled="mode.switching || mode.current === 'bailian' || !mode.meta.bailian_configured"
          @click="switchMode('bailian')"
        >
          <span class="mode-btn-title">在线 · 百炼</span>
          <span class="mode-btn-sub">{{ mode.meta.bailian_model || 'qwen3.5-plus' }}</span>
          <span class="mode-btn-sub">并发 {{ mode.meta.bailian_semaphore ?? '?' }}</span>
          <span v-if="!mode.meta.bailian_configured" class="mode-btn-warn">
            .env 未配置 BAILIAN_API_KEY
          </span>
        </button>
      </div>

      <div v-if="mode.message" :class="['mode-result', mode.messageKind]">
        {{ mode.message }}
      </div>
      <div v-if="!mode.loading" class="mode-meta">
        当前：
        <strong>{{ mode.current === 'bailian' ? '在线 百炼' : '本地 qwen3' }}</strong>
        <template v-if="mode.meta.updated_at"> · 最近更新 {{ mode.meta.updated_at }}</template>
        <template v-if="mode.meta.in_flight_count > 0"> · 有 {{ mode.meta.in_flight_count }} 个任务在跑，暂不能切换</template>
      </div>
    </article>

    <!-- Stats row -->
    <div class="summary-grid">
      <article class="card">
        <div class="card-title">待处理</div>
        <div class="metric-value">{{ buckets.pending.length }}</div>
      </article>
      <article class="card">
        <div class="card-title">执行中</div>
        <div class="metric-value">{{ buckets.in_flight.length }}</div>
      </article>
      <article class="card">
        <div class="card-title">已完成</div>
        <div class="metric-value">{{ buckets.processed.length }}</div>
      </article>
      <article class="card">
        <div class="card-title">失败</div>
        <div class="metric-value">{{ buckets.errored.length }}</div>
      </article>
    </div>

    <!-- Add URL form -->
    <article class="action-card">
      <div class="card-title">加入新 URL</div>
      <p class="section-copy mini-copy">
        支持微信公众号 / Medium / Notion / 普通 HTML 链接。重复链接（按指纹判断）会自动去重。
      </p>
      <div class="add-row">
        <input
          v-model="newUrl"
          type="text"
          class="form-input"
          placeholder="https://mp.weixin.qq.com/s/..."
          @keyup.enter="addUrl"
        />
        <button class="btn-primary" :disabled="adding || !newUrl.trim()" @click="addUrl">
          {{ adding ? '加入中...' : '加入队列' }}
        </button>
      </div>
      <div v-if="addResult" :class="['add-result', addResult.kind]">{{ addResult.text }}</div>
    </article>

    <!-- Run button -->
    <article class="action-card">
      <div class="card-title">运行待处理</div>
      <p class="section-copy mini-copy">
        同步触发一次 drain。每个 URL 有独立的 20 分钟总超时 + 4 分钟无进度保护，卡住的 URL 会被自动 cancel 并标为失败，不阻塞后续。
      </p>
      <div class="action-row">
        <button
          class="btn-primary"
          :disabled="running || buckets.pending.length === 0"
          @click="runPending"
        >
          {{ running ? '执行中...' : `运行 ${buckets.pending.length} 条待处理` }}
        </button>
        <button class="btn-small" :disabled="loading" @click="loadQueue">刷新队列</button>
      </div>

      <!-- Gap #11 fix: live progress panel. Renders whenever there's an
           in-flight URL in the queue (i.e. a drain is active) AND we
           have a concrete build task to report on — this matters so a
           second browser tab opening /workspace/auto still sees the
           running drain, not just the tab that clicked the button. -->
      <div
        v-if="hasInFlightDrain && activeTaskSnapshot"
        class="live-progress"
      >
        <div class="live-topline">
          <span class="live-dot" aria-hidden="true"></span>
          <span class="live-label">实时进度</span>
          <span class="live-percent">{{ activeTaskSnapshot.progress }}%</span>
        </div>
        <div class="live-bar-track">
          <div
            class="live-bar-fill"
            :style="{ width: (activeTaskSnapshot.progress || 0) + '%' }"
          ></div>
        </div>
        <div class="live-message">{{ activeTaskSnapshot.message || '准备中...' }}</div>
        <div class="live-meta">
          任务 {{ shortTaskId(activeTaskSnapshot.task_id) }}
          <template v-if="activeTaskSnapshot.task_type"> · {{ activeTaskSnapshot.task_type }}</template>
        </div>
      </div>
      <div v-else-if="hasInFlightDrain" class="live-progress live-progress--waiting">
        <span class="live-dot" aria-hidden="true"></span>
        正在初始化...（稍等几秒就会显示实时进度）
      </div>
      <div v-if="runResult" class="run-result">
        <div class="metric-line">总运行：{{ runResult.total_runs }}</div>
        <div
          v-for="run in runResult.runs"
          :key="run.run_id"
          :class="['run-row', runSeverityClass(run.status)]"
        >
          <div class="run-topline">
            <span class="run-status">{{ runStatusLabel(run.status) }}</span>
            <span class="run-url">{{ run.url }}</span>
          </div>
          <div class="run-meta">
            {{ runDurationLabel(run.duration_ms) }}
            <template v-if="run.project_id"> · 项目 {{ run.project_id }}</template>
            <template v-if="run.phase"> · 阶段 {{ run.phase }}</template>
          </div>
          <div v-if="run.error" class="run-error">{{ run.error }}</div>
        </div>
      </div>
    </article>

    <!-- Buckets -->
    <div class="buckets">
      <article v-for="bucket in bucketPanels" :key="bucket.key" class="bucket-card">
        <div class="bucket-header">
          <div class="card-title">
            {{ bucket.title }} ({{ displayBuckets[bucket.key].length }})
          </div>
          <div
            v-if="bucket.key === 'errored' && displayBuckets.errored.length > 0"
            class="bucket-header-actions"
          >
            <button
              class="btn-bucket btn-bucket-retry"
              :disabled="bulkBusy"
              @click="retryAllErrored"
            >
              {{ bulkBusy === 'retry' ? '重试中...' : '一键重试失败' }}
            </button>
            <button
              class="btn-bucket btn-bucket-clear"
              :disabled="bulkBusy"
              @click="clearAllErrored"
            >
              {{ bulkBusy === 'clear' ? '清空中...' : '清空失败' }}
            </button>
          </div>
        </div>
        <div
          v-if="bucket.key === 'errored' && bulkResult"
          :class="['bulk-result', bulkResult.kind]"
        >
          {{ bulkResult.text }}
        </div>
        <div v-if="!displayBuckets[bucket.key].length" class="empty-note">{{ bucket.emptyText }}</div>
        <div v-else class="bucket-list">
          <div v-for="item in displayBuckets[bucket.key]" :key="itemKey(item)" class="bucket-row">
            <div class="bucket-url">{{ item.url || item.md_path || item.url_fingerprint }}</div>
            <div class="bucket-meta">
              <template v-if="item.project_id">项目 {{ item.project_id }}</template>
              <template v-if="item.run_id"> · run {{ shortRunId(item.run_id) }}</template>
              <template v-if="item.phase"> · 阶段 {{ item.phase }}</template>
              <template v-if="item.attempt != null"> · 尝试 {{ item.attempt }}</template>
              <template v-if="item.duration_ms"> · 耗时 {{ runDurationLabel(item.duration_ms) }}</template>
            </div>
            <div v-if="item.error" class="bucket-error">{{ item.error }}</div>
            <div v-if="bucket.key === 'errored'" class="bucket-actions">
              <button
                class="btn-retry"
                :disabled="retryingFingerprints.has(item.url_fingerprint)"
                @click="retryErrored(item)"
              >
                {{ retryingFingerprints.has(item.url_fingerprint) ? '重试中...' : '重试' }}
              </button>
              <span
                v-if="retryResults[item.url_fingerprint]"
                :class="['retry-note', retryResults[item.url_fingerprint].kind]"
              >
                {{ retryResults[item.url_fingerprint].text }}
              </span>
            </div>
          </div>
        </div>
      </article>
    </div>

  </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
// Read paths (pending-urls / graph-tasks / llm-mode) flip live↔demo via
// dataClient. Write paths (add URL / process / retry / switch mode)
// continue to use the raw axios `service` — the interceptor in
// api/index.js blocks them in demo mode with a friendly error so demo
// mode never pollutes the real backend.
import service from '../../api/index'
import {
  listAutoPendingUrls,
  listGraphTasks,
  getLlmMode,
} from '../../data/dataClient'
import { appMode } from '../../runtime/appMode'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '自动处理' },
]

const buckets = ref({ pending: [], in_flight: [], processed: [], errored: [] })
const loading = ref(false)
const adding = ref(false)
const running = ref(false)
const error = ref('')
const newUrl = ref('')
const addResult = ref(null)
const runResult = ref(null)

// LLM 抽取模式状态 (2026-04-11)
const mode = ref({
  loading: true,
  switching: false,
  current: 'local',
  meta: {},
  message: '',
  messageKind: '',
})
// Gap #11 fix: latest backend task snapshot for the in-flight URL so we
// can show real-time build progress while the drain is running.
const activeTaskSnapshot = ref(null)
// Retry UI state: which fingerprints are mid-request (for the per-row
// button spinner) and the most recent note text per fingerprint (success
// or error feedback that disappears after the next refresh).
const retryingFingerprints = ref(new Set())
const retryResults = ref({})
// Bulk operations on the errored bucket: "retry all" / "clear". Only one
// of these runs at a time; `bulkBusy` is either '' | 'retry' | 'clear'.
// `bulkResult` surfaces the API response as a colored one-liner below
// the bucket header.
const bulkBusy = ref('')
const bulkResult = ref(null)
// Poll timer handle so we can tear it down when the run ends or the
// component unmounts.
let pollTimer = null

const bucketPanels = [
  { key: 'pending', title: '待处理', emptyText: '队列空。把 URL 贴到上面的输入框加入。' },
  { key: 'in_flight', title: '执行中', emptyText: '当前没有进行中的任务。' },
  { key: 'processed', title: '已完成', emptyText: '还没有成功处理过任何 URL。' },
  { key: 'errored', title: '失败', emptyText: '还没有失败记录。' },
]

// Sorted view of the four buckets. Only `processed` is reordered: newest
// `finished_at` first so the latest success sits at the top. Other
// buckets keep the backend's natural order (pending = FIFO, in_flight =
// claim order, errored = failure chronology — which is useful when
// reading the error messages in context). `.slice()` preserves the
// original array reactivity without mutating it.
const displayBuckets = computed(() => ({
  pending: buckets.value.pending,
  in_flight: buckets.value.in_flight,
  processed: buckets.value.processed.slice().sort((a, b) => {
    const keyA = a.finished_at || a.claimed_at || a.created_at || ''
    const keyB = b.finished_at || b.claimed_at || b.created_at || ''
    return keyB.localeCompare(keyA)
  }),
  errored: buckets.value.errored,
}))

// Gap #11 fix: derive drain-active state from the queue itself, not
// from this tab's local `running` boolean. The live-progress panel
// must also show when a second browser tab opens /workspace/auto in
// the middle of a drain, otherwise the user will think "nothing is
// happening" even though the backend is busy.
const hasInFlightDrain = computed(() => buckets.value.in_flight.length > 0)

function itemKey(item) {
  return item.run_id || item.url_fingerprint || item.url || item.md_path || JSON.stringify(item)
}

function shortRunId(rid) {
  return rid?.length > 14 ? rid.slice(0, 14) + '…' : rid
}

function shortTaskId(tid) {
  return tid?.length > 8 ? tid.slice(0, 8) + '…' : tid
}

function runStatusLabel(status) {
  if (status === 'processed') return '成功'
  if (status === 'errored') return '失败'
  if (status === 'skipped_duplicate') return '重复跳过'
  return status || '?'
}

function runSeverityClass(status) {
  if (status === 'processed') return 'run-ok'
  if (status === 'errored') return 'run-err'
  return 'run-other'
}

function runDurationLabel(ms) {
  if (!ms) return '0s'
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const min = Math.floor(s / 60)
  const rem = s % 60
  return `${min}m${rem}s`
}

async function loadQueue() {
  loading.value = true
  error.value = ''
  try {
    const res = await listAutoPendingUrls()
    const d = res.data || {}
    buckets.value = {
      pending: d.pending || [],
      in_flight: d.in_flight || [],
      processed: d.processed || [],
      errored: d.errored || [],
    }
  } catch (e) {
    // Clear stale buckets on error so demo↔live switches don't leave
    // the previous mode's data visible.
    buckets.value = { pending: [], in_flight: [], processed: [], errored: [] }
    error.value = e.message || '加载队列失败'
  } finally {
    loading.value = false
  }
}

// Gap #11 fix: fetch the freshest build task snapshot so we can show
// progress % / current chunk / message while the drain is running.
// Silent on error — this is progress UI, not a critical path.
async function refreshActiveTask() {
  try {
    const res = await listGraphTasks()
    const tasks = res.data || []
    const active = tasks.find(
      (t) =>
        t.status === 'processing' &&
        typeof t.task_type === 'string' &&
        (t.task_type.startsWith('构建图谱') ||
          t.task_type.startsWith('graph_build')),
    )
    activeTaskSnapshot.value = active || null
  } catch (_err) {
    // swallow — progress polling must never raise into the UI
  }
}

// Gap #11 fix v3: unconditional 6s heartbeat poll while the page is
// mounted. v2 tried to gate the poll on `running || hasInFlightDrain`
// via a `watch({immediate:true})`, but that left a fatal
// chicken-and-egg hole: the initial queue load is async and runs
// *after* the watch fires with shouldPoll=false, so a tab that opened
// AFTER a drain started never saw in_flight and never began polling.
// The only robust cross-tab answer is "always tick while mounted" —
// the cost is two small GETs every 6 seconds, which is negligible.
//
// loadQueue handles the bucket counts (updates the summary cards and
// the in_flight list); refreshActiveTask picks the freshest build
// task snapshot for the live-progress panel. When no drain is active
// both are cheap no-ops — the UI just redraws the same numbers.
function startPoll() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await loadQueue()
    await refreshActiveTask()
    // Also refresh the LLM mode card so the semaphore/model/updated_at
    // labels don't go stale when the backend is restarted or .env is
    // tuned mid-session. Silent on error — the card is informational.
    await loadMode()
  }, 6000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  activeTaskSnapshot.value = null
}

onUnmounted(stopPoll)

async function addUrl() {
  const url = newUrl.value.trim()
  if (!url) return
  adding.value = true
  addResult.value = null
  try {
    const res = await service({
      url: '/api/auto/pending-urls',
      method: 'post',
      data: { urls: [url] },
    })
    const data = res.data || {}
    if (data.added?.length) {
      addResult.value = { kind: 'ok', text: `已加入队列：${url}` }
      newUrl.value = ''
    } else if (data.duplicates?.length) {
      const dup = data.duplicates[0]
      addResult.value = {
        kind: 'warn',
        text: `已存在于 ${dup.existing_bucket || '队列'} 中（按指纹去重，不重复添加）`,
      }
    } else {
      addResult.value = { kind: 'warn', text: '后端没有返回新增或重复，检查格式' }
    }
    await loadQueue()
  } catch (e) {
    addResult.value = { kind: 'err', text: e.message || '加入失败' }
  } finally {
    adding.value = false
  }
}

async function runPending() {
  if (!buckets.value.pending.length) return
  running.value = true
  runResult.value = null
  // Kick off an immediate poll so the user sees the state change fast
  // (pending → in_flight) without waiting 6 seconds for the first tick.
  await loadQueue()
  await refreshActiveTask()
  try {
    // Override axios's default 5-minute timeout: a single URL's watchdog
    // budget is 20 minutes, and N URLs in sequence can easily exceed the
    // default. We bound at 1 hour which still catches genuinely hung
    // requests but lets a normal overnight drain complete.
    const res = await service({
      url: '/api/auto/process-pending',
      method: 'post',
      data: {},
      timeout: 3600000,
    })
    runResult.value = res.data || null
    await loadQueue()
  } catch (e) {
    error.value = e.message || '运行失败'
  } finally {
    running.value = false
    // One last refresh so the final state is visible even if a
    // mid-drain poll was in flight when the POST returned.
    await loadQueue()
  }
}

async function retryErrored(item) {
  const fp = item?.url_fingerprint
  if (!fp) return
  if (retryingFingerprints.value.has(fp)) return
  // Vue 3's reactivity tracks Set mutations only if we reassign; use a new
  // Set so the per-button disabled binding updates.
  retryingFingerprints.value = new Set([...retryingFingerprints.value, fp])
  try {
    await service({
      url: '/api/auto/retry-errored',
      method: 'post',
      data: { url_fingerprint: fp },
    })
    retryResults.value = {
      ...retryResults.value,
      [fp]: { kind: 'ok', text: '已放回待处理，点击"运行"重新抓取' },
    }
    await loadQueue()
  } catch (e) {
    const resp = e.response?.data || {}
    const status = e.response?.status
    let text
    let kind = 'err'
    if (status === 409) {
      kind = 'warn'
      text = resp.error || '该 URL 已在待处理或执行中'
    } else if (status === 404) {
      text = resp.error || '该记录已不在失败列表中（可能已被重试）'
    } else {
      text = resp.error || e.message || '重试失败'
    }
    retryResults.value = { ...retryResults.value, [fp]: { kind, text } }
  } finally {
    const next = new Set(retryingFingerprints.value)
    next.delete(fp)
    retryingFingerprints.value = next
  }
}

async function retryAllErrored() {
  if (bulkBusy.value) return
  bulkBusy.value = 'retry'
  bulkResult.value = null
  try {
    const res = await service({
      url: '/api/auto/retry-all-errored',
      method: 'post',
      data: {},
    })
    const d = res.data || {}
    const retried = (d.retried || []).length
    const skipped = (d.skipped_already_queued || []).length
    const deduped = d.deduped || 0
    const parts = [`已重试 ${retried} 条`]
    if (skipped) parts.push(`${skipped} 条已在队列中（跳过）`)
    if (deduped) parts.push(`合并 ${deduped} 条重复记录`)
    bulkResult.value = {
      kind: retried > 0 ? 'ok' : 'warn',
      text: parts.join('，'),
    }
    await loadQueue()
  } catch (e) {
    const resp = e.response?.data || {}
    bulkResult.value = {
      kind: 'err',
      text: resp.error || e.message || '一键重试失败',
    }
  } finally {
    bulkBusy.value = ''
  }
}

async function clearAllErrored() {
  if (bulkBusy.value) return
  const count = buckets.value.errored.length
  if (!count) return
  // Destructive action — confirm with the native dialog. The text is
  // deliberately specific about count so a stray double-click can't wipe
  // more than expected.
  if (!window.confirm(`确认清空失败列表中的 ${count} 条记录？此操作不可撤销。`)) return
  bulkBusy.value = 'clear'
  bulkResult.value = null
  try {
    const res = await service({
      url: '/api/auto/clear-errored',
      method: 'post',
      data: {},
    })
    const cleared = res.data?.cleared ?? 0
    bulkResult.value = {
      kind: 'ok',
      text: `已清空 ${cleared} 条失败记录`,
    }
    await loadQueue()
  } catch (e) {
    const resp = e.response?.data || {}
    bulkResult.value = {
      kind: 'err',
      text: resp.error || e.message || '清空失败',
    }
  } finally {
    bulkBusy.value = ''
  }
}

async function loadMode() {
  // Only show the "加载中..." text on the first mount; subsequent
  // polls should refresh silently so the card doesn't flicker every 6s.
  const firstLoad = mode.value.meta && Object.keys(mode.value.meta).length === 0
  if (firstLoad) mode.value.loading = true
  try {
    const res = await getLlmMode()
    const d = res.data || {}
    mode.value.current = d.mode || 'local'
    mode.value.meta = d
    mode.value.loading = false
  } catch (e) {
    mode.value.loading = false
    // Don't clobber a recent switch-success toast with a background poll
    // error. Only surface if we have no prior state.
    if (firstLoad) {
      mode.value.message = `读取当前模式失败：${e.message || e}`
      mode.value.messageKind = 'err'
    }
  }
}

async function switchMode(target) {
  if (mode.value.switching) return
  if (mode.value.current === target) return
  mode.value.switching = true
  mode.value.message = ''
  mode.value.messageKind = ''
  try {
    const res = await service({
      url: '/api/config/llm-mode',
      method: 'put',
      data: { mode: target },
    })
    const d = res.data || {}
    mode.value.current = d.mode || target
    mode.value.meta = d
    mode.value.message =
      target === 'bailian'
        ? `已切换到在线 百炼（${d.bailian_model || 'qwen3.5-plus'}，并发 ${d.bailian_semaphore ?? '?'}）。下一个任务生效。`
        : `已切换到本地 ${d.local_model || 'qwen3'}（并发 ${d.local_semaphore ?? '?'}）。下一个任务生效。`
    mode.value.messageKind = 'ok'
  } catch (e) {
    const resp = e.response?.data || {}
    const code = resp.error_code || ''
    if (code === 'IN_FLIGHT') {
      mode.value.message = resp.error || '有任务正在执行，暂时不能切换'
      mode.value.messageKind = 'warn'
    } else if (code === 'BAILIAN_NOT_CONFIGURED') {
      mode.value.message = resp.error || 'BAILIAN_API_KEY 未在 .env 配置'
      mode.value.messageKind = 'err'
    } else {
      mode.value.message = resp.error || e.message || '切换模式失败'
      mode.value.messageKind = 'err'
    }
    // 失败后也刷一下当前状态，确保 UI 和后端一致
    await loadMode()
  } finally {
    mode.value.switching = false
  }
}

// Gap #11 fix v3: do one immediate fetch on mount (so the first paint
// isn't empty cards) and then start the unconditional 6s poll. If the
// tab is opened while a drain is already running elsewhere, the very
// first tick picks up in_flight + activeTaskSnapshot and the
// live-progress panel renders within ~6 seconds.
onMounted(async () => {
  await loadQueue()
  await refreshActiveTask()
  await loadMode()
  startPoll()
})

// Re-hydrate all three pipeline reads when live/demo flips.
watch(appMode, async () => {
  await loadQueue()
  await refreshActiveTask()
  await loadMode()
})
</script>

<style scoped>
.auto-shell { max-width: 1200px; margin: 0 auto; }
.topbar-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 8px;
  border: 1px solid #d4dce8; background: #fff;
  color: #4a6fa5; font-size: 12px; font-weight: 500;
  text-decoration: none; cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover { background: #f0f4ff; border-color: #a9bbd9; }
.page-header { margin-bottom: 24px; }
.section-badge { font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: #4a6fa5; font-weight: 700; }
.section-title { margin: 8px 0 0; font-size: 28px; color: #181818; }
.section-copy { color: #5a6573; line-height: 1.6; }
.mini-copy { font-size: 13px; margin: 6px 0 12px; }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.card, .action-card, .bucket-card, .state-card {
  border: 1px solid #d4dce8;
  background: linear-gradient(180deg, #fcfdff 0%, #f5f8ff 100%);
  border-radius: 18px;
  padding: 18px;
}
.error-card { border-color: #e2b0a8; background: #fff8f6; }
.card-title { font-weight: 700; color: #211c18; margin-bottom: 10px; }
.metric-value { font-size: 28px; font-weight: 700; color: #1b1712; }

.action-card { margin-bottom: 16px; }
.add-row { display: flex; gap: 10px; margin-top: 10px; }
.action-row { display: flex; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
.form-input {
  flex: 1;
  border: 1px solid #d4dce8;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}
.form-input:focus { border-color: #4a6fa5; }
.btn-primary {
  background: #4a6fa5;
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 10px 18px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-small {
  border: 1px solid #d4dce8;
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  text-decoration: none;
  color: #4a6fa5;
}

.add-result { margin-top: 10px; font-size: 13px; padding: 8px 12px; border-radius: 8px; }
.add-result.ok { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.add-result.warn { background: #fff3e0; color: #e65100; border: 1px solid #ffcc80; }
.add-result.err { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }

/* Gap #11 fix: live progress panel shown during a drain. */
.live-progress {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid #c4b5fd;
  background: linear-gradient(180deg, #f5f3ff 0%, #ede9fe 100%);
  border-radius: 12px;
  color: #4c1d95;
}
.live-progress--waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.live-topline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #7c3aed;
  animation: livePulse 1.2s ease-in-out infinite;
}
@keyframes livePulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}
.live-label {
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.live-percent {
  margin-left: auto;
  font-weight: 700;
  font-size: 16px;
}
.live-bar-track {
  height: 6px;
  border-radius: 999px;
  background: rgba(124, 58, 237, 0.15);
  overflow: hidden;
}
.live-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #7c3aed 0%, #a855f7 100%);
  transition: width 400ms ease;
}
.live-message {
  margin-top: 8px;
  font-size: 13px;
  color: #5b21b6;
}
.live-meta {
  margin-top: 4px;
  font-size: 11px;
  color: #6d28d9;
  opacity: 0.85;
}

.run-result { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.metric-line { color: #5a6573; font-size: 13px; }
.run-row { border: 1px solid #d4dce8; border-radius: 12px; padding: 12px 14px; background: #fff; }
.run-row.run-ok { border-left: 4px solid #2e7d32; }
.run-row.run-err { border-left: 4px solid #c62828; background: #fff8f6; }
.run-row.run-other { border-left: 4px solid #4a6fa5; }
.run-topline { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.run-status { font-weight: 700; color: #1d1d1d; font-size: 13px; }
.run-url { color: #4a6fa5; font-size: 13px; word-break: break-all; }
.run-meta { color: #5a6573; font-size: 12px; margin-top: 4px; }
.run-error { color: #c62828; font-size: 12px; margin-top: 4px; }

.buckets { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-top: 16px; }
.bucket-list { display: flex; flex-direction: column; gap: 10px; }
.bucket-row { border: 1px solid #eef1f5; border-radius: 10px; padding: 10px 12px; background: #fff; }
.bucket-url { font-weight: 600; color: #1d1d1d; font-size: 13px; word-break: break-all; }
.bucket-meta { color: #5a6573; font-size: 11px; margin-top: 3px; }
.bucket-error { color: #c62828; font-size: 12px; margin-top: 4px; }
.bucket-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.bucket-header .card-title { margin-bottom: 0; }
.bucket-header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.btn-bucket {
  border-radius: 8px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all 120ms ease;
  border: 1px solid;
  background: #fff;
}
.btn-bucket:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-bucket-retry { border-color: #4a6fa5; color: #4a6fa5; }
.btn-bucket-retry:hover:not(:disabled) { background: #4a6fa5; color: #fff; }
.btn-bucket-clear { border-color: #888; color: #666; }
.btn-bucket-clear:hover:not(:disabled) { background: #555; border-color: #555; color: #fff; }
.bulk-result {
  margin-bottom: 10px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
}
.bulk-result.ok { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.bulk-result.warn { background: #fff3e0; color: #e65100; border: 1px solid #ffcc80; }
.bulk-result.err { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.bucket-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.btn-retry {
  border: 1px solid #c62828;
  background: #fff;
  color: #c62828;
  border-radius: 8px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all 120ms ease;
}
.btn-retry:hover:not(:disabled) {
  background: #c62828;
  color: #fff;
}
.btn-retry:disabled { opacity: 0.55; cursor: not-allowed; }
.retry-note { font-size: 12px; }
.retry-note.ok { color: #2e7d32; }
.retry-note.warn { color: #e65100; }
.retry-note.err { color: #c62828; }
.empty-note { color: #7a8090; font-size: 13px; padding: 8px 0; }

.nav-row { margin-top: 24px; display: flex; gap: 12px; }

/* LLM 抽取模式切换卡片 */
.mode-card {
  border: 1px solid #d4dce8;
  background: linear-gradient(180deg, #fffbf0 0%, #fff3d6 100%);
  border-radius: 18px;
  padding: 18px;
  margin-bottom: 16px;
}
.mode-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.mode-loading { font-size: 12px; color: #997200; }
.mode-switch-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 2px solid #e6d39b;
  background: #fffef7;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: all 120ms ease;
}
.mode-btn:hover:not(:disabled) {
  border-color: #d97706;
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(217, 119, 6, 0.12);
}
.mode-btn:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}
.mode-btn-active {
  border-color: #d97706;
  background: linear-gradient(180deg, #fef3c7 0%, #fde68a 100%);
  box-shadow: 0 2px 6px rgba(217, 119, 6, 0.18);
}
.mode-btn-title {
  font-weight: 700;
  color: #1f1d1b;
  font-size: 15px;
}
.mode-btn-sub {
  font-size: 12px;
  color: #77682a;
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
}
.mode-btn-warn {
  font-size: 11px;
  color: #c62828;
  margin-top: 2px;
}
.mode-result {
  margin-top: 12px;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 8px;
}
.mode-result.ok { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.mode-result.warn { background: #fff3e0; color: #e65100; border: 1px solid #ffcc80; }
.mode-result.err { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
.mode-meta { margin-top: 10px; font-size: 12px; color: #77682a; }

@media (max-width: 900px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
