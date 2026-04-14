import { reactive } from 'vue'
import {
  getThemeView,
  putThemeDecision,
  deleteThemeDecision,
  listThemeClusters,
  createThemeCluster,
  updateThemeCluster,
  attachConceptsToCluster,
  detachConceptsFromCluster,
  attachEvidenceToCluster,
} from '../services/api/themeApi'
import {
  createEmptyThemeCandidate,
  createEmptyThemeViewModel,
  normalizeThemeCandidate,
} from '../types/theme'

export const themeStore = reactive({
  items: [],
  selectedId: '',
  selectedTheme: createEmptyThemeCandidate(),
  meta: createEmptyThemeViewModel().meta,
  overview: createEmptyThemeViewModel().overview,
  backbone: createEmptyThemeViewModel().backbone,
  diagnostics: createEmptyThemeViewModel().diagnostics,
  limitations: createEmptyThemeViewModel().limitations,
  loading: false,
  error: '',
  projectId: '',
  savingById: {},
  errorById: {},
  clusters: [],
  clusterLoading: false,
})

let seedSequence = 0

function resetThemeStore() {
  const emptyView = createEmptyThemeViewModel()
  themeStore.items = []
  themeStore.selectedId = ''
  themeStore.selectedTheme = createEmptyThemeCandidate()
  themeStore.meta = emptyView.meta
  themeStore.overview = emptyView.overview
  themeStore.backbone = emptyView.backbone
  themeStore.diagnostics = emptyView.diagnostics
  themeStore.limitations = emptyView.limitations
}

export async function loadThemeView(payload = {}) {
  const currentSequence = ++seedSequence
  themeStore.loading = true
  themeStore.error = ''

  try {
    const projectId = payload.projectId || payload.project?.project_id
    if (!projectId) {
      resetThemeStore()
      return
    }

    const response = await getThemeView(projectId)
    if (currentSequence !== seedSequence) return

    const view = response?.data || {}
    const items = (view.themeCandidates || []).map((item) => normalizeThemeCandidate(item))

    themeStore.projectId = projectId
    themeStore.items = items
    themeStore.selectedId = items[0]?.candidateKey || ''
    themeStore.selectedTheme = items[0] || createEmptyThemeCandidate()
    themeStore.savingById = {}
    themeStore.errorById = {}
    themeStore.meta = view.meta || createEmptyThemeViewModel().meta
    themeStore.overview = view.overview || createEmptyThemeViewModel().overview
    themeStore.backbone = view.backbone || createEmptyThemeViewModel().backbone
    themeStore.diagnostics = view.diagnostics || createEmptyThemeViewModel().diagnostics
    themeStore.limitations = Array.isArray(view.limitations) ? view.limitations : []
  } catch (error) {
    resetThemeStore()
    themeStore.error = error.message || '主题视图加载失败'
  } finally {
    if (currentSequence === seedSequence) {
      themeStore.loading = false
    }
  }
}

export function selectTheme(themeKey) {
  const nextTheme = themeStore.items.find((item) => item.candidateKey === themeKey)
  if (!nextTheme) return

  themeStore.selectedId = nextTheme.candidateKey
  themeStore.selectedTheme = nextTheme
}

export async function applyThemeDecision(candidateKey, { status, note }) {
  if (!themeStore.projectId) return

  const item = themeStore.items.find((c) => c.candidateKey === candidateKey)
  if (item) {
    item.status = status
    if (note !== undefined) item.note = note
    if (themeStore.selectedId === candidateKey) {
      themeStore.selectedTheme = { ...item }
    }
  }

  themeStore.savingById[candidateKey] = true
  delete themeStore.errorById[candidateKey]
  try {
    await putThemeDecision(themeStore.projectId, candidateKey, { status, note: note || '' })
  } catch (err) {
    themeStore.errorById[candidateKey] = err.message || '保存失败'
  } finally {
    themeStore.savingById[candidateKey] = false
  }
}

export async function clearThemeDecision(candidateKey) {
  if (!themeStore.projectId) return

  themeStore.savingById[candidateKey] = true
  delete themeStore.errorById[candidateKey]
  try {
    await deleteThemeDecision(themeStore.projectId, candidateKey)
    const item = themeStore.items.find((c) => c.candidateKey === candidateKey)
    if (item) {
      item.status = 'unreviewed'
      item.note = ''
      if (themeStore.selectedId === candidateKey) {
        themeStore.selectedTheme = { ...item }
      }
    }
  } catch (err) {
    themeStore.errorById[candidateKey] = err.message || '清除失败'
  } finally {
    themeStore.savingById[candidateKey] = false
  }
}

// Stage G: Theme Cluster helpers

export async function loadClusters() {
  if (!themeStore.projectId) return
  themeStore.clusterLoading = true
  try {
    const resp = await listThemeClusters(themeStore.projectId)
    themeStore.clusters = resp?.data || []
  } catch {
    themeStore.clusters = []
  } finally {
    themeStore.clusterLoading = false
  }
}

export async function addCluster({ name, summary, source_theme_keys }) {
  if (!themeStore.projectId) return null
  const resp = await createThemeCluster(themeStore.projectId, { name, summary, source_theme_keys })
  if (resp?.data) {
    themeStore.clusters.push(resp.data)
  }
  return resp?.data || null
}

export async function editCluster(clusterId, updates) {
  if (!themeStore.projectId) return
  const resp = await updateThemeCluster(themeStore.projectId, clusterId, updates)
  if (resp?.data) {
    const idx = themeStore.clusters.findIndex((c) => c.id === clusterId)
    if (idx >= 0) themeStore.clusters.splice(idx, 1, resp.data)
  }
}

export async function attachConcepts(clusterId, concept_ids) {
  if (!themeStore.projectId) return
  const resp = await attachConceptsToCluster(themeStore.projectId, clusterId, concept_ids)
  if (resp?.data) {
    const idx = themeStore.clusters.findIndex((c) => c.id === clusterId)
    if (idx >= 0) themeStore.clusters.splice(idx, 1, resp.data)
  }
}

export async function detachConcepts(clusterId, concept_ids) {
  if (!themeStore.projectId) return
  const resp = await detachConceptsFromCluster(themeStore.projectId, clusterId, concept_ids)
  if (resp?.data) {
    const idx = themeStore.clusters.findIndex((c) => c.id === clusterId)
    if (idx >= 0) themeStore.clusters.splice(idx, 1, resp.data)
  }
}

export async function attachEvidence(clusterId, evidence_refs) {
  if (!themeStore.projectId) return
  const resp = await attachEvidenceToCluster(themeStore.projectId, clusterId, evidence_refs)
  if (resp?.data) {
    const idx = themeStore.clusters.findIndex((c) => c.id === clusterId)
    if (idx >= 0) themeStore.clusters.splice(idx, 1, resp.data)
  }
}
