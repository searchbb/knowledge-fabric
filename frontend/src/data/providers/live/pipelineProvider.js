// Live pipeline provider. AutoPipelinePage needs three reads that don't
// have a dedicated services/api/* module today, so we wrap the raw
// service() calls here. Live behaviour is preserved exactly.

import service from '../../../api/index'

export function listAutoPendingUrls() {
  return service({ url: '/api/auto/pending-urls', method: 'get' })
}

export function listGraphTasks() {
  return service({ url: '/api/graph/tasks', method: 'get' })
}

export function getLlmMode() {
  return service({ url: '/api/config/llm-mode', method: 'get' })
}
