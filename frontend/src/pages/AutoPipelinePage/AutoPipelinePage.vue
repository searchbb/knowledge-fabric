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

    <!-- 1. Stats: always visible (page-level health at a glance) -->
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

    <!-- 2. Add URL form -->
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

    <!-- 3. Rich-text paste entry (2026-04-20): paste from WeChat /
         Twitter / Feishu / clipboard → Turndown → MD →
         /api/auto/pending-notes → same drain path as URL articles. -->
    <NotePasteCard @submitted="loadQueue" />

    <!-- 4. Run pending + live progress. Run-results history will be
         wrapped in CollapsibleCard in a later task. -->
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

      <div v-if="hasInFlightDrain && activeTaskSnapshot" class="live-progress">
        <div class="live-topline">
          <span class="live-dot" aria-hidden="true"></span>
          <span class="live-label">实时进度</span>
          <span class="live-percent">{{ activeTaskSnapshot.progress }}%</span>
        </div>
        <div class="live-bar-track">
          <div class="live-bar-fill" :style="{ width: (activeTaskSnapshot.progress || 0) + '%' }"></div>
        </div>
        <div v-if="inFlightUrl" class="live-url">{{ inFlightUrl }}</div>
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

    <!-- 5. 待处理 bucket (primary actionable queue, stays expanded) -->
    <article class="bucket-card">
      <div class="bucket-header">
        <div class="card-title">待处理 ({{ displayBuckets.pending.length }})</div>
      </div>
      <div v-if="!displayBuckets.pending.length" class="empty-note">队列空。把 URL 贴到上面的输入框加入。</div>
      <div v-else class="bucket-list">
        <div v-for="item in displayBuckets.pending" :key="itemKey(item)" class="bucket-row">
          <div class="bucket-url">{{ item.url || item.md_path || item.url_fingerprint }}</div>
          <div class="bucket-meta">
            <template v-if="item.project_id">项目 {{ item.project_id }}</template>
            <template v-if="item.run_id"> · run {{ shortRunId(item.run_id) }}</template>
            <template v-if="item.attempt != null"> · 尝试 {{ item.attempt }}</template>
            <template v-if="item.duration_ms"> · 耗时 {{ runDurationLabel(item.duration_ms) }}</template>
          </div>
          <div v-if="item.error" class="bucket-error">{{ item.error }}</div>
          <div class="bucket-actions">
            <button
              class="btn-cancel"
              :disabled="cancelingFingerprints.has(item.url_fingerprint)"
              @click="cancelPending(item)"
            >
              {{ cancelingFingerprints.has(item.url_fingerprint) ? '取消中...' : '取消' }}
            </button>
            <span
              v-if="cancelResults[item.url_fingerprint]"
              :class="['retry-note', cancelResults[item.url_fingerprint].kind]"
            >
              {{ cancelResults[item.url_fingerprint].text }}
            </span>
          </div>
        </div>
      </div>
    </article>

    <!-- 6. Discover queue — counts + manual run stay visible; attention
         jobs list + cooldown alert collapse into the body. -->
    <CollapsibleCard
      title="Discover 队列 · 跨文章关系发现"
      subtitle="文章主流程不再等这一步。每篇新文章会在这里落一条待办，后台或手动运行去兑现它。"
      :badge="`共 ${discoverStats.total} 条`"
      storage-key="auto-pipeline:collapse:discover"
      data-test="discover-card"
    >
      <template #summary-extra>
        <span class="dc-inline-counts">
          <span class="dc-inline-chip">待 {{ discoverStats.by_status.pending || 0 }}</span>
          <span class="dc-inline-chip">跑 {{ discoverStats.by_status.running || 0 }}</span>
          <span v-if="(discoverStats.by_status.failed || 0) > 0" class="dc-inline-chip dc-inline-chip--warn">
            失 {{ discoverStats.by_status.failed || 0 }}
          </span>
          <button
            class="btn-tiny"
            :disabled="discoverRunning || (discoverStats.by_status.pending || 0) === 0"
            @click.stop.prevent="runOneDiscover"
          >
            {{ discoverRunning ? '运行中...' : '运行一条' }}
          </button>
        </span>
      </template>

      <div class="discover-counts">
        <div class="dc-metric"><span class="dc-label">待办</span><span class="dc-value">{{ discoverStats.by_status.pending || 0 }}</span></div>
        <div class="dc-metric"><span class="dc-label">运行中</span><span class="dc-value">{{ discoverStats.by_status.running || 0 }}</span></div>
        <div class="dc-metric"><span class="dc-label">完成</span><span class="dc-value">{{ discoverStats.by_status.completed || 0 }}</span></div>
        <div class="dc-metric"><span class="dc-label">部分完成</span><span class="dc-value">{{ discoverStats.by_status.partial || 0 }}</span></div>
        <div class="dc-metric"><span class="dc-label">失败</span><span class="dc-value dc-value--warn">{{ discoverStats.by_status.failed || 0 }}</span></div>
      </div>
      <div class="action-row discover-actions">
        <button class="btn-small" :disabled="discoverRunning" @click="refreshDiscover">刷新</button>
        <span v-if="discoverLastResult" :class="['retry-note', discoverLastResult.kind]">
          {{ discoverLastResult.text }}
        </span>
      </div>

      <!-- Cooldown / budget throttle alert (P4 audit follow-up
           2026-04-17). Only rendered when something was actually
           blocked in the last hour, so a healthy queue doesn't get a
           noisy banner. -->
      <div v-if="discoverSkips.total > 0" class="discover-skip-alert">
        <div class="skip-alert-head">
          <span class="skip-alert-icon" aria-hidden="true">⚠</span>
          <span class="skip-alert-title">
            过去 1 小时有 {{ discoverSkips.total }} 次调度被拦截
          </span>
        </div>
        <div class="skip-alert-breakdown">
          <span v-if="discoverSkips.by_kind.theme_cooldown" class="skip-chip">主题冷却 {{ discoverSkips.by_kind.theme_cooldown }}</span>
          <span v-if="discoverSkips.by_kind.daily_budget" class="skip-chip">日预算 {{ discoverSkips.by_kind.daily_budget }}</span>
          <span v-if="discoverSkips.by_kind.other" class="skip-chip">其他 {{ discoverSkips.by_kind.other }}</span>
        </div>
        <div v-if="discoverSkips.latest" class="skip-alert-latest" :title="discoverSkips.latest.reason">
          最近一次：{{ discoverSkips.latest.reason }}
        </div>
      </div>

      <!-- Job list: only surface jobs that need attention. Completed
           ones live in the counters above so we don't bloat this list
           with the long tail of successful runs. -->
      <div v-if="discoverAttentionJobs.length > 0" class="discover-jobs">
        <div class="discover-jobs-title">需要关注的任务 ({{ discoverAttentionJobs.length }})</div>
        <div
          v-for="job in discoverAttentionJobs"
          :key="job.job_id"
          class="discover-job-row discover-job-row--clickable"
          role="button"
          tabindex="0"
          @click="openJobDrawer(job.job_id)"
          @keyup.enter="openJobDrawer(job.job_id)"
        >
          <span :class="['dj-status', `dj-status--${job.status}`]">{{ discoverStatusLabel(job.status) }}</span>
          <span class="dj-id" :title="job.job_id">{{ shortJobId(job.job_id) }}</span>
          <span v-if="job.last_error" class="dj-error" :title="job.last_error">{{ job.last_error }}</span>
          <span v-else-if="job.new_entry_ids && job.new_entry_ids.length" class="dj-meta">
            {{ job.new_entry_ids.length }} 个新概念
          </span>
          <span class="dj-spacer"></span>
          <!-- Action buttons stop propagation so clicking them doesn't
               also open the drawer. -->
          <button
            v-if="canRetry(job.status)"
            class="btn-tiny"
            :disabled="discoverBusyJobs.has(job.job_id)"
            @click.stop="retryDiscoverJob(job.job_id)"
          >
            {{ discoverBusyJobs.has(job.job_id) ? '处理中...' : '重试' }}
          </button>
          <button
            v-if="canCancel(job.status)"
            class="btn-tiny btn-tiny--danger"
            :disabled="discoverBusyJobs.has(job.job_id)"
            @click.stop="cancelDiscoverJob(job.job_id)"
          >
            取消
          </button>
        </div>
      </div>
    </CollapsibleCard>

    <!-- 7. 失败 bucket -->
    <article class="bucket-card">
      <div class="bucket-header">
        <div class="card-title">失败 ({{ displayBuckets.errored.length }})</div>
        <div v-if="displayBuckets.errored.length > 0" class="bucket-header-actions">
          <button class="btn-bucket btn-bucket-retry" :disabled="!!bulkBusy" @click="retryAllErrored">
            {{ bulkBusy === 'retry' ? '重试中...' : '一键重试失败' }}
          </button>
          <button class="btn-bucket btn-bucket-clear" :disabled="!!bulkBusy" @click="clearAllErrored">
            {{ bulkBusy === 'clear' ? '清空中...' : '清空失败' }}
          </button>
        </div>
      </div>
      <div v-if="bulkResult" :class="['bulk-result', bulkResult.kind]">{{ bulkResult.text }}</div>
      <div v-if="!displayBuckets.errored.length" class="empty-note">还没有失败记录。</div>
      <div v-else class="bucket-list">
        <div v-for="item in displayBuckets.errored" :key="itemKey(item)" class="bucket-row">
          <div class="bucket-url">{{ item.url || item.md_path || item.url_fingerprint }}</div>
          <div class="bucket-meta">
            <template v-if="item.project_id">项目 {{ item.project_id }}</template>
            <template v-if="item.run_id"> · run {{ shortRunId(item.run_id) }}</template>
            <template v-if="item.attempt != null"> · 尝试 {{ item.attempt }}</template>
            <template v-if="item.duration_ms"> · 耗时 {{ runDurationLabel(item.duration_ms) }}</template>
          </div>
          <div v-if="item.error" class="bucket-error">{{ item.error }}</div>
          <div class="bucket-actions">
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

    <!-- 8. 执行中 bucket -->
    <article class="bucket-card">
      <div class="bucket-header">
        <div class="card-title">执行中 ({{ displayBuckets.in_flight.length }})</div>
      </div>
      <div v-if="!displayBuckets.in_flight.length" class="empty-note">当前没有进行中的任务。</div>
      <div v-else class="bucket-list">
        <div v-for="item in displayBuckets.in_flight" :key="itemKey(item)" class="bucket-row">
          <div class="bucket-url">{{ item.url || item.md_path || item.url_fingerprint }}</div>
          <div class="bucket-meta">
            <template v-if="item.project_id">项目 {{ item.project_id }}</template>
            <template v-if="item.run_id"> · run {{ shortRunId(item.run_id) }}</template>
            <template v-if="item.attempt != null"> · 尝试 {{ item.attempt }}</template>
            <template v-if="item.duration_ms"> · 耗时 {{ runDurationLabel(item.duration_ms) }}</template>
          </div>
          <div v-if="item.phase" class="phase-badge-row">
            <span class="phase-badge">{{ item.phase }}</span>
          </div>
          <div v-if="item.error" class="bucket-error">{{ item.error }}</div>
        </div>
      </div>
    </article>

    <!-- 9. 已完成 bucket -->
    <article class="bucket-card">
      <div class="bucket-header">
        <div class="card-title">已完成 ({{ displayBuckets.processed.length }})</div>
      </div>
      <div v-if="!displayBuckets.processed.length" class="empty-note">还没有成功处理过任何 URL。</div>
      <div v-else class="bucket-list">
        <div v-for="item in displayBuckets.processed" :key="itemKey(item)" class="bucket-row">
          <div class="bucket-url">{{ item.url || item.md_path || item.url_fingerprint }}</div>
          <div class="bucket-meta">
            <template v-if="item.project_id">项目 {{ item.project_id }}</template>
            <template v-if="item.run_id"> · run {{ shortRunId(item.run_id) }}</template>
            <template v-if="item.attempt != null"> · 尝试 {{ item.attempt }}</template>
            <template v-if="item.duration_ms"> · 耗时 {{ runDurationLabel(item.duration_ms) }}</template>
          </div>
          <div v-if="item.error" class="bucket-error">{{ item.error }}</div>
        </div>
      </div>
    </article>

    <!-- 10. LLM 抽取模式（配置，沉底） -->
    <CollapsibleCard
      title="抽取模式"
      subtitle="切换 Graphiti 抽取走本地 LM Studio 还是百炼（DashScope）在线 API。切换只影响下一个任务, 有任务在跑的时候会被拒绝。"
      storage-key="auto-pipeline:collapse:llm-mode"
    >
      <template #summary-extra>
        <span class="cc-inline-meta">
          {{ mode.current === 'bailian' ? '在线 百炼' : '本地 qwen3' }}
        </span>
      </template>

      <div v-if="mode.loading" class="mode-loading">加载中...</div>
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
      <div v-if="mode.message" :class="['mode-result', mode.messageKind]">{{ mode.message }}</div>
      <div v-if="!mode.loading" class="mode-meta">
        当前：
        <strong>{{ mode.current === 'bailian' ? '在线 百炼' : '本地 qwen3' }}</strong>
        <template v-if="mode.meta.updated_at"> · 最近更新 {{ mode.meta.updated_at }}</template>
        <template v-if="mode.meta.in_flight_count > 0"> · 有 {{ mode.meta.in_flight_count }} 个任务在跑，暂不能切换</template>
      </div>
    </CollapsibleCard>

    <!-- Job detail drawer (P4 step 9, 2026-04-17). Overlay + slide-in
         panel. Opens when a job row is clicked; closes on backdrop click
         or Esc. Shows the full job record plus a funnel breakdown so
         operators can see "why was this partial?" without SSHing to
         grep discover-jobs.json. -->
    <div
      v-if="jobDrawerOpen"
      class="job-drawer-backdrop"
      @click="closeJobDrawer"
    >
      <aside
        class="job-drawer-panel"
        role="dialog"
        aria-label="Discover job detail"
        @click.stop
      >
        <div class="jd-head">
          <div class="jd-title">
            Discover Job
            <span class="jd-head-id">{{ selectedJobId }}</span>
          </div>
          <button class="jd-close" @click="closeJobDrawer">×</button>
        </div>

        <div v-if="jobDetailLoading" class="jd-body"><em>加载中...</em></div>

        <div v-else-if="!selectedJobDetail" class="jd-body">
          <div class="jd-error">未找到任务或已被清理。</div>
        </div>

        <div v-else class="jd-body">
          <!-- Status + essentials -->
          <section class="jd-section">
            <dl class="jd-grid">
              <dt>状态</dt>
              <dd>
                <span
                  :class="['dj-status', `dj-status--${selectedJobDetail.status}`]"
                >{{ discoverStatusLabel(selectedJobDetail.status) }}</span>
              </dd>
              <dt>主题</dt>
              <dd>{{ selectedJobDetail.theme_id || '—' }}</dd>
              <dt>触发项目</dt>
              <dd>{{ selectedJobDetail.trigger_project_id || '—' }}</dd>
              <dt>触发 run</dt>
              <dd>{{ selectedJobDetail.origin_run_id || '—' }}</dd>
              <dt>尝试次数</dt>
              <dd>{{ selectedJobDetail.attempt_count }} / {{ selectedJobDetail.max_attempts }}</dd>
              <dt>创建</dt>
              <dd>{{ shortDateTime(selectedJobDetail.created_at) }}</dd>
              <dt>开始</dt>
              <dd>{{ shortDateTime(selectedJobDetail.started_at) || '—' }}</dd>
              <dt>结束</dt>
              <dd>{{ shortDateTime(selectedJobDetail.finished_at) || '—' }}</dd>
              <dt>心跳</dt>
              <dd>{{ shortDateTime(selectedJobDetail.heartbeat_at) || '—' }}</dd>
            </dl>
          </section>

          <!-- New entry ids (from the triggering article) -->
          <section v-if="selectedJobDetail.new_entry_ids?.length" class="jd-section">
            <h4 class="jd-section-title">本次新增概念（{{ selectedJobDetail.new_entry_ids.length }}）</h4>
            <div class="jd-entry-list">
              <code v-for="eid in selectedJobDetail.new_entry_ids" :key="eid" class="jd-entry-chip">{{ eid }}</code>
            </div>
          </section>

          <!-- Funnel -->
          <section v-if="selectedJobFunnel" class="jd-section">
            <h4 class="jd-section-title">候选漏斗</h4>
            <dl class="jd-grid jd-grid--funnel">
              <dt>原始 pair</dt>
              <dd>{{ selectedJobFunnel.raw_pairs || 0 }}</dd>
              <dt>增量过滤后</dt>
              <dd>{{ selectedJobFunnel.after_incremental_gate || 0 }}</dd>
              <dt>跨文章后</dt>
              <dd>{{ selectedJobFunnel.after_cross_article || 0 }}</dd>
              <dt>去重后</dt>
              <dd>{{ selectedJobFunnel.after_dedupe_filter || 0 }}</dd>
              <dt>送 LLM</dt>
              <dd>{{ selectedJobFunnel.sent_to_llm || 0 }}</dd>
              <dt>LLM 接受</dt>
              <dd>{{ selectedJobFunnel.llm_accepted || 0 }}</dd>
              <dt>落库去重</dt>
              <dd>{{ selectedJobFunnel.deduped_on_commit || 0 }}</dd>
              <dt>最终写入</dt>
              <dd><strong>{{ selectedJobFunnel.committed || 0 }}</strong></dd>
            </dl>
          </section>

          <!-- Chunk / retry stats -->
          <section v-if="selectedJobStats" class="jd-section">
            <h4 class="jd-section-title">分片与重试</h4>
            <dl class="jd-grid">
              <dt>Chunk 总数</dt>
              <dd>{{ selectedJobStats.llm_chunks_total || 0 }}</dd>
              <dt>Chunk 成功</dt>
              <dd>{{ selectedJobStats.llm_chunks_succeeded || 0 }}</dd>
              <dt>Chunk 失败</dt>
              <dd>{{ selectedJobStats.llm_chunks_failed || 0 }}</dd>
              <dt>Chunk 重试</dt>
              <dd>{{ selectedJobStats.llm_chunks_retried || 0 }}</dd>
            </dl>
          </section>

          <!-- Raw errors -->
          <section v-if="(selectedJobStats?.errors || []).length" class="jd-section">
            <h4 class="jd-section-title">错误（{{ selectedJobStats.errors.length }}）</h4>
            <pre class="jd-errors">{{ (selectedJobStats.errors || []).join('\n') }}</pre>
          </section>

          <section v-if="selectedJobDetail.last_error" class="jd-section">
            <h4 class="jd-section-title">最后一次错误</h4>
            <div class="jd-last-error">{{ selectedJobDetail.last_error }}</div>
          </section>
        </div>
      </aside>
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
import CollapsibleCard from '../../components/common/CollapsibleCard.vue'
import NotePasteCard from './components/NotePasteCard.vue'

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

// Discover V2 queue state (P1.4). Polled alongside the URL queue so the
// counts stay fresh. Separate refs from the URL buckets because the two
// queues are different workloads (URL = article lifecycle, discover =
// enrich) and we don't want a slow /discover-jobs/stats call to block
// /pending-urls or vice versa.
const discoverStats = ref({ total: 0, by_status: {} })
const discoverRunning = ref(false)
const discoverLastResult = ref(null)
const discoverJobs = ref([])
// Throttle alert data (P4 audit follow-up 2026-04-17). `latest` is the
// most-recent skip entry; `by_kind` drives the breakdown chips; `total`
// gates the whole alert's visibility.
const discoverSkips = ref({ total: 0, by_kind: {}, latest: null })
// Set of job_ids currently being retried/cancelled so we can disable
// that specific row's buttons without disabling every other job's row.
const discoverBusyJobs = ref(new Set())

// Job detail drawer (P4 step 9). Keep identity + payload in separate
// refs so the overlay renders immediately with a loading state while
// the fetch is in flight.
const jobDrawerOpen = ref(false)
const selectedJobId = ref('')
const selectedJobDetail = ref(null)
const jobDetailLoading = ref(false)

// Funnel + per-run stats are nested inside the job's ``stats`` field —
// computed helpers so the template stays readable.
const selectedJobFunnel = computed(() => selectedJobDetail.value?.stats?.funnel || null)
const selectedJobStats = computed(() => selectedJobDetail.value?.stats || null)

function shortDateTime(iso) {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(0, 16)
}

// Only surface non-completed jobs in the per-job list. Completed ones are
// already visible in the counter total; listing them would bury the
// retriable partial/failed jobs a user actually needs to see.
const DISCOVER_ATTENTION_STATUSES = new Set([
  'pending',
  'running',
  'partial',
  'failed',
  'cancelled',
])
const discoverAttentionJobs = computed(() =>
  discoverJobs.value.filter((j) => DISCOVER_ATTENTION_STATUSES.has(j.status)),
)

function discoverStatusLabel(status) {
  const map = {
    pending: '待办',
    running: '运行中',
    partial: '部分完成',
    failed: '失败',
    cancelled: '已取消',
    completed: '完成',
  }
  return map[status] || status
}

function canRetry(status) {
  return status === 'partial' || status === 'failed' || status === 'cancelled'
}

function canCancel(status) {
  // Running can't be cancelled mid-LLM — the backend enforces this too.
  return status === 'pending'
}

function shortJobId(id) {
  if (!id) return ''
  // djob_3942d1e9b7 -> djob_3942d1…
  return id.length > 12 ? `${id.slice(0, 12)}…` : id
}

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
const cancelingFingerprints = ref(new Set())
const cancelResults = ref({})
// Bulk operations on the errored bucket: "retry all" / "clear". Only one
// of these runs at a time; `bulkBusy` is either '' | 'retry' | 'clear'.
// `bulkResult` surfaces the API response as a colored one-liner below
// the bucket header.
const bulkBusy = ref('')
const bulkResult = ref(null)
// Poll timer handle so we can tear it down when the run ends or the
// component unmounts.
let pollTimer = null

// Sorted view of the four buckets — always newest-first, so the user
// can scan the top of any list to see the most recent activity. Each
// bucket picks the field that best represents "when did this state
// happen":
//   - pending   → created_at  (when it was queued)
//   - in_flight → claimed_at (when drain picked it up), fallback created_at
//   - processed → finished_at, fallback claimed_at / created_at
//   - errored   → finished_at (error time), fallback claimed_at / created_at
// ISO8601 strings sort lexicographically via localeCompare.
const displayBuckets = computed(() => {
  const byNewest = (pick) => (a, b) => {
    const ka = pick(a) || ''
    const kb = pick(b) || ''
    return kb.localeCompare(ka)
  }
  return {
    pending: buckets.value.pending.slice().sort(byNewest((i) => i.created_at)),
    in_flight: buckets.value.in_flight.slice().sort(byNewest((i) => i.claimed_at || i.created_at)),
    processed: buckets.value.processed.slice().sort(byNewest((i) => i.finished_at || i.claimed_at || i.created_at)),
    errored: buckets.value.errored.slice().sort(byNewest((i) => i.finished_at || i.claimed_at || i.created_at)),
  }
})

// Gap #11 fix: derive drain-active state from the queue itself, not
// from this tab's local `running` boolean. The live-progress panel
// must also show when a second browser tab opens /workspace/auto in
// the middle of a drain, otherwise the user will think "nothing is
// happening" even though the backend is busy.
const hasInFlightDrain = computed(() => buckets.value.in_flight.length > 0)

// Show which URL is currently being processed in the live-progress panel.
const inFlightUrl = computed(() => {
  const item = buckets.value.in_flight[0]
  return item?.url || item?.md_path || null
})

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

async function loadDiscoverStats() {
  // Demo mode: show zeros instead of hitting the real backend. The URL
  // queue has its own fixture via dataClient; discover-jobs doesn't have
  // one yet, and demo mode's invariant is "no live service calls".
  if (appMode.value === 'demo') {
    discoverStats.value = { total: 0, by_status: {} }
    return
  }
  // The response interceptor in api/index.js already unwraps axios to
  // return the backend's {success, data, ...} envelope directly, so what
  // we get here is {success:true, data:{by_status, total}} — i.e. the
  // payload lives at res.data (ONE level), not res.data.data.
  // Silent on error — the panel is informational, and the backend may be
  // a version that doesn't have /api/auto/discover-jobs/stats yet.
  try {
    const res = await service({
      url: '/api/auto/discover-jobs/stats',
      method: 'GET',
    })
    const d = (res && res.data) || {}
    discoverStats.value = {
      total: d.total || 0,
      by_status: d.by_status || {},
    }
  } catch (_e) {
    // keep the last good value; don't flash zeros on a transient error
  }
}

async function loadDiscoverJobs() {
  if (appMode.value === 'demo') {
    discoverJobs.value = []
    return
  }
  try {
    const res = await service({
      url: '/api/auto/discover-jobs?limit=20',
      method: 'GET',
    })
    const d = (res && res.data) || {}
    discoverJobs.value = d.jobs || []
  } catch (_e) {
    // keep last good value
  }
}

async function loadDiscoverSkips() {
  if (appMode.value === 'demo') {
    discoverSkips.value = { total: 0, by_kind: {}, latest: null }
    return
  }
  try {
    const res = await service({
      url: '/api/auto/discover-jobs/recent-skips?within_seconds=3600&limit=5',
      method: 'GET',
    })
    const d = (res && res.data) || {}
    const skips = d.skips || []
    const stats = d.stats || { total: 0, by_kind: {} }
    discoverSkips.value = {
      total: stats.total || 0,
      by_kind: stats.by_kind || {},
      latest: skips[0] || null,
    }
  } catch (_e) {
    // keep last good value; don't flash alerts on network blips
  }
}

async function refreshDiscover() {
  await Promise.all([
    loadDiscoverStats(),
    loadDiscoverJobs(),
    loadDiscoverSkips(),
  ])
}

async function retryDiscoverJob(jobId) {
  const busy = new Set(discoverBusyJobs.value)
  busy.add(jobId)
  discoverBusyJobs.value = busy
  try {
    await service({
      url: `/api/auto/discover-jobs/${jobId}/retry`,
      method: 'POST',
    })
    discoverLastResult.value = {
      kind: 'ok',
      text: `${shortJobId(jobId)} 已重新入队`,
    }
  } catch (e) {
    discoverLastResult.value = {
      kind: 'err',
      text: `重试失败：${(e && e.message) || e}`,
    }
  } finally {
    const next = new Set(discoverBusyJobs.value)
    next.delete(jobId)
    discoverBusyJobs.value = next
    await refreshDiscover()
  }
}

async function openJobDrawer(jobId) {
  selectedJobId.value = jobId
  jobDrawerOpen.value = true
  selectedJobDetail.value = null
  jobDetailLoading.value = true
  try {
    const res = await service({
      url: `/api/auto/discover-jobs/${encodeURIComponent(jobId)}`,
      method: 'GET',
    })
    selectedJobDetail.value = (res && res.data) || null
  } catch (_e) {
    selectedJobDetail.value = null
  } finally {
    jobDetailLoading.value = false
  }
}

function closeJobDrawer() {
  jobDrawerOpen.value = false
  selectedJobId.value = ''
  selectedJobDetail.value = null
}

function handleDrawerEsc(e) {
  if (e.key === 'Escape' && jobDrawerOpen.value) {
    closeJobDrawer()
  }
}

async function cancelDiscoverJob(jobId) {
  const busy = new Set(discoverBusyJobs.value)
  busy.add(jobId)
  discoverBusyJobs.value = busy
  try {
    await service({
      url: `/api/auto/discover-jobs/${jobId}/cancel`,
      method: 'POST',
    })
    discoverLastResult.value = {
      kind: 'ok',
      text: `${shortJobId(jobId)} 已取消`,
    }
  } catch (e) {
    discoverLastResult.value = {
      kind: 'err',
      text: `取消失败：${(e && e.message) || e}`,
    }
  } finally {
    const next = new Set(discoverBusyJobs.value)
    next.delete(jobId)
    discoverBusyJobs.value = next
    await refreshDiscover()
  }
}

async function runOneDiscover() {
  discoverRunning.value = true
  discoverLastResult.value = null
  try {
    const res = await service({
      url: '/api/auto/discover-jobs/run-once',
      method: 'POST',
    })
    const d = (res && res.data) || {}
    if (!d.executed) {
      discoverLastResult.value = { kind: 'info', text: '队列为空' }
    } else {
      const outcome = d.outcome || {}
      const discovered = (outcome.stats || {}).discovered || 0
      discoverLastResult.value = {
        kind: outcome.status === 'failed' ? 'err' : 'ok',
        text: `${outcome.job_id} → ${outcome.status}（新增关系 ${discovered}）`,
      }
    }
  } catch (e) {
    discoverLastResult.value = {
      kind: 'err',
      text: '运行失败：' + ((e && e.message) || e),
    }
  } finally {
    discoverRunning.value = false
    await refreshDiscover()
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
    await refreshDiscover()
  }, 6000)
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  activeTaskSnapshot.value = null
}

onUnmounted(() => {
  stopPoll()
  window.removeEventListener('keyup', handleDrawerEsc)
})

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

async function cancelPending(item) {
  const fp = item?.url_fingerprint
  if (!fp) return
  if (cancelingFingerprints.value.has(fp)) return
  cancelingFingerprints.value = new Set([...cancelingFingerprints.value, fp])
  try {
    await service({
      url: `/api/auto/pending-urls/${fp}`,
      method: 'delete',
    })
    cancelResults.value = {
      ...cancelResults.value,
      [fp]: { kind: 'ok', text: '已取消' },
    }
    await loadQueue()
  } catch (e) {
    const resp = e.response?.data || {}
    const status = e.response?.status
    let text
    let kind = 'err'
    if (status === 409) {
      kind = 'warn'
      text = resp.error || '该任务已开始执行，无法取消'
    } else if (status === 404) {
      text = resp.error || '该任务已不在待处理列表中'
    } else {
      text = resp.error || e.message || '取消失败'
    }
    cancelResults.value = { ...cancelResults.value, [fp]: { kind, text } }
  } finally {
    const next = new Set(cancelingFingerprints.value)
    next.delete(fp)
    cancelingFingerprints.value = next
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
  await refreshDiscover()
  startPoll()
  window.addEventListener('keyup', handleDrawerEsc)
})

// Re-hydrate all pipeline reads when live/demo flips.
watch(appMode, async () => {
  await loadQueue()
  await refreshActiveTask()
  await loadMode()
  await refreshDiscover()
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

.discover-card { margin-bottom: 20px; }
.discover-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px; }
.discover-total { color: #5a6573; font-size: 12px; }
.discover-counts {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin: 6px 0 12px;
}
.dc-metric {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e3e9f2;
}
.dc-label { font-size: 12px; color: #5a6573; }
.dc-value { font-size: 22px; font-weight: 700; color: #1b1712; }
.dc-value--warn { color: #c45a4a; }
.discover-actions { align-items: center; }

/* Throttle alert (P4 audit follow-up 2026-04-17). Subtle amber strip so
   it reads as "we're rate-limiting you on purpose" rather than "broken". */
.discover-skip-alert {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff8eb;
  border: 1px solid #f0d27a;
  color: #7a5620;
  font-size: 12px;
}
.skip-alert-head { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.skip-alert-icon { font-size: 14px; }
.skip-alert-breakdown { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.skip-chip {
  background: #faeac0;
  color: #7a5620;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}
.skip-alert-latest {
  margin-top: 6px;
  color: #5a4420;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.discover-jobs { margin-top: 14px; border-top: 1px solid #e3e9f2; padding-top: 12px; }
.discover-jobs-title { font-size: 12px; color: #5a6573; margin-bottom: 8px; }
.discover-job-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e3e9f2;
  margin-bottom: 6px;
  font-size: 13px;
}
.dj-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  white-space: nowrap;
}
.dj-status--pending { background: #eef2f8; color: #4a6fa5; }
.dj-status--running { background: #e7f3ec; color: #2d7a47; }
.dj-status--partial { background: #fbeed7; color: #a86d12; }
.dj-status--failed { background: #fbe4e0; color: #c45a4a; }
.dj-status--cancelled { background: #eeeeee; color: #777; }
.dj-id { font-family: 'SFMono-Regular', Menlo, monospace; color: #5a6573; font-size: 12px; }
.dj-error {
  color: #c45a4a;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 340px;
}
.dj-meta { color: #5a6573; font-size: 12px; }
.dj-spacer { flex: 1; }
.btn-tiny {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid #4a6fa5;
  background: #fff;
  color: #4a6fa5;
  cursor: pointer;
}
.btn-tiny:hover:not(:disabled) { background: #4a6fa5; color: #fff; }
.btn-tiny:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-tiny--danger { border-color: #c45a4a; color: #c45a4a; }
.btn-tiny--danger:hover:not(:disabled) { background: #c45a4a; color: #fff; }

/* --- Job detail drawer (P4 step 9, 2026-04-17) ------------------------ */
.discover-job-row--clickable { cursor: pointer; }
.discover-job-row--clickable:hover { background: #f5f8ff; }

.job-drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(27, 23, 18, 0.45);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}
.job-drawer-panel {
  width: min(560px, 90vw);
  max-width: 560px;
  height: 100vh;
  background: #fcfdff;
  border-left: 1px solid #d4dce8;
  overflow-y: auto;
  box-shadow: -10px 0 30px rgba(27, 23, 18, 0.15);
}
.jd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid #e3e9f2;
  background: #f5f8ff;
  position: sticky;
  top: 0;
  z-index: 2;
}
.jd-title { font-weight: 700; color: #211c18; font-size: 14px; }
.jd-head-id {
  font-family: 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  color: #5a6573;
  margin-left: 10px;
  font-weight: 400;
}
.jd-close {
  background: none;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: #5a6573;
  cursor: pointer;
  padding: 0 6px;
}
.jd-close:hover { color: #211c18; }
.jd-body { padding: 16px 20px 40px; }
.jd-error { color: #c45a4a; }
.jd-section { margin-bottom: 18px; }
.jd-section-title {
  font-size: 12px;
  color: #5a6573;
  font-weight: 600;
  margin: 0 0 8px;
  letter-spacing: 0.02em;
}
.jd-grid {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 4px 12px;
  margin: 0;
  font-size: 13px;
}
.jd-grid dt { color: #5a6573; }
.jd-grid dd { margin: 0; color: #211c18; font-family: inherit; }
.jd-grid--funnel { grid-template-columns: 110px 1fr; }
.jd-entry-list { display: flex; flex-wrap: wrap; gap: 6px; }
.jd-entry-chip {
  font-family: 'SFMono-Regular', Menlo, monospace;
  font-size: 11px;
  background: #eef2f8;
  color: #4a6fa5;
  padding: 2px 8px;
  border-radius: 10px;
}
.jd-errors {
  font-family: 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  background: #fff8f6;
  border: 1px solid #e2b0a8;
  border-radius: 8px;
  padding: 10px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  color: #8f3a2b;
}
.jd-last-error {
  color: #c45a4a;
  font-size: 13px;
}
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
.live-url {
  margin-top: 8px;
  font-size: 12px;
  color: #6d28d9;
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
  word-break: break-all;
  opacity: 0.9;
}
.live-message {
  margin-top: 6px;
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
.btn-cancel {
  border: 1px solid #888;
  background: #fff;
  color: #555;
  border-radius: 8px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all 120ms ease;
}
.btn-cancel:hover:not(:disabled) { background: #555; border-color: #555; color: #fff; }
.btn-cancel:disabled { opacity: 0.55; cursor: not-allowed; }
.retry-note { font-size: 12px; }
.retry-note.ok { color: #2e7d32; }
.retry-note.warn { color: #e65100; }
.retry-note.err { color: #c62828; }
.phase-badge-row { margin-top: 5px; }
.phase-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
  background: #e0e7ff;
  color: #3730a3;
  border: 1px solid #c7d2fe;
  letter-spacing: 0.03em;
}
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

.cc-inline-meta {
  font-size: 12px;
  color: #6b7280;
  margin-right: 4px;
}
.dc-inline-counts {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
.dc-inline-chip {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #374151;
}
.dc-inline-chip--warn {
  background: #fee2e2;
  color: #991b1b;
}
</style>
