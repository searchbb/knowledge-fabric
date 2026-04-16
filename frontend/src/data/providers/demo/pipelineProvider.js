// Demo pipeline provider — global fixtures (not per-projectId).

import {
  pendingUrlsFixture,
  graphTasksFixture,
  llmModeFixture,
} from './fixtures/pipeline'

const clone = (v) => JSON.parse(JSON.stringify(v))

export async function listAutoPendingUrls() {
  return clone(pendingUrlsFixture)
}

export async function listGraphTasks() {
  return clone(graphTasksFixture)
}

export async function getLlmMode() {
  return clone(llmModeFixture)
}
