import axios from 'axios'
import { appMode, APP_MODES } from '../runtime/appMode'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// HTTP methods that mutate server state. We reject any of these when the
// app is running in demo mode — demo is explicitly read-only, and silently
// letting writes through would (a) corrupt the real backend with demo
// test data and (b) give the user a false "write succeeded" experience
// that disappears on refresh. The rejection looks identical to a normal
// API error, so existing error-handling paths surface it cleanly.
const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete'])

// 请求拦截器
service.interceptors.request.use(
  config => {
    const method = String(config.method || 'get').toLowerCase()
    if (appMode.value === APP_MODES.DEMO && MUTATING_METHODS.has(method)) {
      const path = config.url || 'request'
      const err = new Error(`Demo 模式为只读，已阻止 ${method.toUpperCase()} ${path}`)
      err.isDemoReadonlyBlock = true
      return Promise.reject(err)
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器（容错重试机制）
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message && error.message.includes('timeout')) {
      error.message = '请求超时：后端响应太慢或未启动。可切换到 Demo 模式查看示例数据。'
      error.isNetworkDown = true
    }

    // 处理网络错误
    //
    // Browser's `new Error('Network Error')` leaks through to every page's
    // catch block as a raw English string, which reads as "something broke"
    // rather than "the backend isn't up". Rewrite it once here so every
    // page (Overview, Registry, Themes, Relations, Auto, Workspace…) gets
    // a consistent, actionable Chinese message AND a machine-readable
    // `isNetworkDown` flag pages can use to offer a Demo-mode CTA.
    if (error.message === 'Network Error') {
      error.message = '后端未连接：无法加载数据。可切换到 Demo 模式查看示例数据，或先启动后端服务。'
      error.isNetworkDown = true
    }

    // Console logging policy:
    //   - Demo read-only blocks are intentional, not bugs — silent.
    //   - Network-down is already surfaced in every page's UI via the
    //     friendly message we just rewrote. Logging the raw axios object
    //     ("Response error: AxiosError" / "[object Object]") for every
    //     page on every failed request is pure noise — drop it down to
    //     a single concise warn so the devtools console stays usable
    //     while the backend is offline.
    //   - Anything else (HTTP 4xx/5xx, parse errors) still goes through
    //     console.error with a useful, stringified payload.
    if (error?.isDemoReadonlyBlock) {
      // silent
    } else if (error?.isNetworkDown) {
      console.warn('[api]', error.message)
    } else {
      const detail = error?.response
        ? `${error.response.status} ${error.config?.method?.toUpperCase() || 'REQ'} ${error.config?.url || ''}`
        : error?.message || String(error)
      console.error('[api] response error:', detail)
    }

    return Promise.reject(error)
  }
)

// 带重试的请求函数
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      
      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export function listResearchProjects() {
  return service({ url: '/api/research-projects', method: 'get' })
}

export function createResearchProject(payload) {
  return service({ url: '/api/research-projects', method: 'post', data: payload })
}

export function getResearchProject(projectId) {
  return service({ url: `/api/research-projects/${projectId}`, method: 'get' })
}

export function updateResearchProject(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}`, method: 'patch', data: payload })
}

export function getLocalEvidencePack(projectId) {
  return service({ url: `/api/research-projects/${projectId}/local-evidence-pack`, method: 'get' })
}

export function searchLocalEvidencePack(projectId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/local-evidence-pack/search`,
    method: 'post',
    data: payload,
  })
}

export function updateLocalEvidenceCandidate(projectId, evidenceId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/local-evidence-pack/candidates/${evidenceId}`,
    method: 'patch',
    data: payload,
  })
}

export function listResearchRuns(projectId) {
  return service({ url: `/api/research-projects/${projectId}/research-runs`, method: 'get' })
}

export function listConsultationLogs(projectId) {
  return service({ url: `/api/research-projects/${projectId}/consultation-logs`, method: 'get' })
}

export function listExternalResearchPacks(projectId) {
  return service({ url: `/api/research-projects/${projectId}/external-research-packs`, method: 'get' })
}

export function updateExternalResearchCandidate(projectId, packId, candidateId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/external-research-packs/${packId}/candidates/${candidateId}`,
    method: 'patch',
    data: payload,
  })
}

export function listEvidenceMatrixRows(projectId) {
  return service({ url: `/api/research-projects/${projectId}/evidence-matrix`, method: 'get' })
}

export function createEvidenceMatrixRow(projectId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/evidence-matrix/rows`,
    method: 'post',
    data: payload,
  })
}

export function updateEvidenceMatrixRow(projectId, rowId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/evidence-matrix/rows/${rowId}`,
    method: 'patch',
    data: payload,
  })
}

export function listInsightCards(projectId) {
  return service({ url: `/api/research-projects/${projectId}/insight-cards`, method: 'get' })
}

export function createInsightCard(projectId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/insight-cards`,
    method: 'post',
    data: payload,
  })
}

export function updateInsightCard(projectId, cardId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/insight-cards/${cardId}`,
    method: 'patch',
    data: payload,
  })
}

export function listArtifactDrafts(projectId) {
  return service({ url: `/api/research-projects/${projectId}/artifact-drafts`, method: 'get' })
}

export function createArtifactDraft(projectId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/artifact-drafts`,
    method: 'post',
    data: payload,
  })
}

export function updateArtifactDraft(projectId, draftId, payload) {
  return service({
    url: `/api/research-projects/${projectId}/artifact-drafts/${draftId}`,
    method: 'patch',
    data: payload,
  })
}

export function listArtifactPacks(projectId) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs`, method: 'get' })
}

export function createArtifactPack(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs`, method: 'post', data: payload })
}

export function getArtifactPack(projectId, packId) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs/${packId}`, method: 'get' })
}

export function updateArtifactPack(projectId, packId, payload) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs/${packId}`, method: 'patch', data: payload })
}

export function addArtifactPackItem(projectId, packId, payload) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs/${packId}/items`, method: 'post', data: payload })
}

export function addArtifactPackPage(projectId, packId, payload) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs/${packId}/pages`, method: 'post', data: payload })
}

export function addArtifactPackFileRef(projectId, packId, payload) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs/${packId}/file-refs`, method: 'post', data: payload })
}

export function addArtifactPackReviewRound(projectId, packId, payload) {
  return service({ url: `/api/research-projects/${projectId}/artifact-packs/${packId}/review-rounds`, method: 'post', data: payload })
}

export function listStrategicOptions(projectId) {
  return service({ url: `/api/research-projects/${projectId}/strategic-options`, method: 'get' })
}

export function createStrategicOption(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/strategic-options`, method: 'post', data: payload })
}

export function updateStrategicOption(projectId, optionId, payload) {
  return service({ url: `/api/research-projects/${projectId}/strategic-options/${optionId}`, method: 'patch', data: payload })
}

export function listValidationPlans(projectId) {
  return service({ url: `/api/research-projects/${projectId}/validation-plans`, method: 'get' })
}

export function createValidationPlan(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/validation-plans`, method: 'post', data: payload })
}

export function updateValidationPlan(projectId, planId, payload) {
  return service({ url: `/api/research-projects/${projectId}/validation-plans/${planId}`, method: 'patch', data: payload })
}

export function listLeadershipDecisionRecords(projectId) {
  return service({ url: `/api/research-projects/${projectId}/leadership-decision-records`, method: 'get' })
}

export function createLeadershipDecisionRecord(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/leadership-decision-records`, method: 'post', data: payload })
}

export function updateLeadershipDecisionRecord(projectId, decisionId, payload) {
  return service({ url: `/api/research-projects/${projectId}/leadership-decision-records/${decisionId}`, method: 'patch', data: payload })
}

export function listLeadershipBriefings(projectId) {
  return service({ url: `/api/research-projects/${projectId}/leadership-briefings`, method: 'get' })
}

export function createLeadershipBriefing(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/leadership-briefings`, method: 'post', data: payload })
}

export function getLeadershipBriefing(projectId, briefingId) {
  return service({ url: `/api/research-projects/${projectId}/leadership-briefings/${briefingId}`, method: 'get' })
}

export function updateLeadershipBriefing(projectId, briefingId, payload) {
  return service({ url: `/api/research-projects/${projectId}/leadership-briefings/${briefingId}`, method: 'patch', data: payload })
}

export function getTraceabilityMap(projectId, params = {}) {
  return service({ url: `/api/research-projects/${projectId}/traceability-map`, method: 'get', params })
}

export function listGovernanceReviews(projectId) {
  return service({ url: `/api/research-projects/${projectId}/governance-reviews`, method: 'get' })
}

export function createGovernanceReview(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/governance-reviews`, method: 'post', data: payload })
}

export function getGovernanceReview(projectId, reviewId) {
  return service({ url: `/api/research-projects/${projectId}/governance-reviews/${reviewId}`, method: 'get' })
}

export function updateGovernanceReview(projectId, reviewId, payload) {
  return service({ url: `/api/research-projects/${projectId}/governance-reviews/${reviewId}`, method: 'patch', data: payload })
}

export function listReviewHistory(projectId, params = {}) {
  return service({ url: `/api/research-projects/${projectId}/review-history`, method: 'get', params })
}

export function getAssetReviewHistory(projectId, assetType, assetId, params = {}) {
  return service({
    url: `/api/research-projects/${projectId}/review-history/assets/${assetType}/${assetId}`,
    method: 'get',
    params,
  })
}

export function getReviewHistoryEntry(projectId, historyEntryId) {
  return service({ url: `/api/research-projects/${projectId}/review-history/${historyEntryId}`, method: 'get' })
}

export function createReviewHistoryNote(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/review-history/notes`, method: 'post', data: payload })
}

export function listResearchSnapshots(projectId) {
  return service({ url: `/api/research-projects/${projectId}/snapshots`, method: 'get' })
}

export function createResearchSnapshot(projectId, payload) {
  return service({ url: `/api/research-projects/${projectId}/snapshots`, method: 'post', data: payload })
}

export function getResearchSnapshot(projectId, snapshotId) {
  return service({ url: `/api/research-projects/${projectId}/snapshots/${snapshotId}`, method: 'get' })
}

export function diffResearchSnapshot(projectId, snapshotId) {
  return service({ url: `/api/research-projects/${projectId}/snapshots/${snapshotId}/diff`, method: 'get' })
}

export function listSnapshotReviewNotes(projectId, snapshotId) {
  return service({ url: `/api/research-projects/${projectId}/snapshots/${snapshotId}/review-notes`, method: 'get' })
}

export function createSnapshotReviewNote(projectId, snapshotId, payload) {
  return service({ url: `/api/research-projects/${projectId}/snapshots/${snapshotId}/review-notes`, method: 'post', data: payload })
}

export function getSnapshotReviewNote(projectId, snapshotId, noteId) {
  return service({ url: `/api/research-projects/${projectId}/snapshots/${snapshotId}/review-notes/${noteId}`, method: 'get' })
}

export function updateSnapshotReviewNote(projectId, snapshotId, noteId, payload) {
  return service({ url: `/api/research-projects/${projectId}/snapshots/${snapshotId}/review-notes/${noteId}`, method: 'patch', data: payload })
}

export default service
