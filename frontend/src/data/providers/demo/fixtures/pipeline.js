// Demo pipeline fixture.
//
// AutoPipelinePage hits 3 separate global endpoints — fixture mirrors
// each so the page can render without a backend.
//
//   GET /api/auto/pending-urls   → { pending, in_flight, processed, errored }
//   GET /api/graph/tasks         → array of task records
//   GET /api/config/llm-mode     → llm config snapshot

export const pendingUrlsFixture = {
  success: true,
  data: {
    pending: [
      {
        url: 'https://demo.example.com/articles/observability-guide.html',
        project_id: 'demo-observability-platform',
        run_id: 'demo-run-101',
        phase: 'queued',
        attempt: 0,
        duration_ms: 0,
        url_fingerprint: 'fp-demo-1',
        error: '',
      },
      {
        url: 'https://demo.example.com/articles/agentic-patterns.md',
        project_id: 'demo-agentic-workflows',
        run_id: 'demo-run-102',
        phase: 'queued',
        attempt: 0,
        duration_ms: 0,
        url_fingerprint: 'fp-demo-2',
        error: '',
      },
    ],
    in_flight: [
      {
        url: 'https://demo.example.com/articles/rag-bench.md',
        project_id: 'demo-retrieval-benchmarks',
        run_id: 'demo-run-103',
        phase: 'extracting',
        attempt: 1,
        duration_ms: 4200,
        url_fingerprint: 'fp-demo-3',
        error: '',
      },
    ],
    processed: [
      {
        url: 'https://demo.example.com/articles/otel-deep-dive.md',
        project_id: 'demo-observability-platform',
        run_id: 'demo-run-099',
        phase: 'completed',
        attempt: 1,
        duration_ms: 18450,
        url_fingerprint: 'fp-demo-prev-1',
        error: '',
      },
    ],
    errored: [
      {
        url: 'https://demo.example.com/articles/missing.html',
        project_id: 'demo-observability-platform',
        run_id: 'demo-run-098',
        phase: 'failed',
        attempt: 2,
        duration_ms: 2100,
        url_fingerprint: 'fp-demo-prev-2',
        error: 'demo: 404 Not Found from upstream (示例错误)',
      },
    ],
  },
}

export const graphTasksFixture = {
  success: true,
  data: [
    {
      task_id: 'demo-task-running-1',
      task_type: 'graph_build',
      status: 'running',
      progress: 0.62,
      message: '正在抽取实体与关系...（示例任务，不会真实执行）',
      project_id: 'demo-retrieval-benchmarks',
    },
    {
      task_id: 'demo-task-completed-1',
      task_type: 'graph_build',
      status: 'completed',
      progress: 1,
      message: '示例：构建完成，0 警告',
      project_id: 'demo-observability-platform',
    },
  ],
}

export const llmModeFixture = {
  success: true,
  data: {
    mode: 'local',
    local_model: 'demo-local-llm',
    local_semaphore: 4,
    deepseek_model: 'deepseek-chat',
    deepseek_semaphore: 8,
    deepseek_configured: false,
    updated_at: '2026-04-12T07:00:00Z',
    in_flight_count: 1,
  },
}
