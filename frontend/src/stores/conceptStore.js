import { reactive } from 'vue'
import {
  getConceptView,
  putConceptDecision,
  deleteConceptDecision,
  postConceptMergeSuggest,
  postConceptNormalize,
} from '../services/api/conceptApi'
import {
  createEmptyConceptCandidate,
  createEmptyConceptViewModel,
  normalizeConceptCandidate,
} from '../types/concept'

export const conceptStore = reactive({
  items: [],
  selectedId: '',
  selectedConcept: createEmptyConceptCandidate(),
  meta: createEmptyConceptViewModel().meta,
  summary: createEmptyConceptViewModel().summary,
  diagnostics: createEmptyConceptViewModel().diagnostics,
  loading: false,
  error: '',
  projectId: '',
  savingById: {},
  errorById: {},
  mergeSuggestions: null,
  normalizedNames: null,
  mergeLoading: false,
})

let seedSequence = 0

function resetConceptStore() {
  const emptyView = createEmptyConceptViewModel()
  conceptStore.items = []
  conceptStore.selectedId = ''
  conceptStore.selectedConcept = createEmptyConceptCandidate()
  conceptStore.meta = emptyView.meta
  conceptStore.summary = emptyView.summary
  conceptStore.diagnostics = emptyView.diagnostics
}

export async function loadConceptView(payload = {}) {
  const currentSequence = ++seedSequence
  conceptStore.loading = true
  conceptStore.error = ''

  try {
    const projectId = payload.projectId || payload.project?.project_id
    if (!projectId) {
      resetConceptStore()
      return
    }

    const response = await getConceptView(projectId)
    if (currentSequence !== seedSequence) return

    const view = response?.data || {}
    const items = (view.candidateConcepts || []).map((item) => normalizeConceptCandidate(item))

    conceptStore.projectId = projectId
    conceptStore.items = items
    conceptStore.selectedId = items[0]?.key || ''
    conceptStore.selectedConcept = items[0] || createEmptyConceptCandidate()
    conceptStore.savingById = {}
    conceptStore.errorById = {}
    conceptStore.meta = view.meta || createEmptyConceptViewModel().meta
    conceptStore.summary = view.summary || createEmptyConceptViewModel().summary
    conceptStore.diagnostics = view.diagnostics || createEmptyConceptViewModel().diagnostics
  } catch (error) {
    resetConceptStore()
    conceptStore.error = error.message || '概念视图加载失败'
  } finally {
    if (currentSequence === seedSequence) {
      conceptStore.loading = false
    }
  }
}

export function selectConcept(conceptKey) {
  const nextConcept = conceptStore.items.find((item) => item.key === conceptKey)
  if (!nextConcept) return

  conceptStore.selectedId = nextConcept.key
  conceptStore.selectedConcept = nextConcept
}

export async function applyConceptDecision(conceptKey, { status, note, canonical_name }) {
  if (!conceptStore.projectId) return

  const item = conceptStore.items.find((c) => c.key === conceptKey)
  if (item) {
    item.status = status
    if (note !== undefined) item.note = note
    if (canonical_name !== undefined) item.canonicalName = canonical_name
    if (conceptStore.selectedId === conceptKey) {
      conceptStore.selectedConcept = { ...item }
    }
  }

  conceptStore.savingById[conceptKey] = true
  delete conceptStore.errorById[conceptKey]
  try {
    await putConceptDecision(conceptStore.projectId, conceptKey, {
      status,
      note: note || '',
      canonical_name: canonical_name || '',
    })
  } catch (err) {
    conceptStore.errorById[conceptKey] = err.message || '保存失败'
  } finally {
    conceptStore.savingById[conceptKey] = false
  }
}

export async function clearConceptDecision(conceptKey) {
  if (!conceptStore.projectId) return

  conceptStore.savingById[conceptKey] = true
  delete conceptStore.errorById[conceptKey]
  try {
    await deleteConceptDecision(conceptStore.projectId, conceptKey)
    const item = conceptStore.items.find((c) => c.key === conceptKey)
    if (item) {
      item.status = 'unreviewed'
      item.note = ''
      item.canonicalName = ''
      if (conceptStore.selectedId === conceptKey) {
        conceptStore.selectedConcept = { ...item }
      }
    }
  } catch (err) {
    conceptStore.errorById[conceptKey] = err.message || '清除失败'
  } finally {
    conceptStore.savingById[conceptKey] = false
  }
}

export async function loadMergeSuggestions() {
  if (!conceptStore.projectId) return
  conceptStore.mergeLoading = true
  try {
    const response = await postConceptMergeSuggest(conceptStore.projectId)
    conceptStore.mergeSuggestions = response?.data || null
  } catch (err) {
    conceptStore.mergeSuggestions = null
  } finally {
    conceptStore.mergeLoading = false
  }
}

export async function loadNormalizedNames() {
  if (!conceptStore.projectId) return
  try {
    const response = await postConceptNormalize(conceptStore.projectId)
    conceptStore.normalizedNames = response?.data || null
  } catch {
    conceptStore.normalizedNames = null
  }
}

export async function mergeConceptInto(sourceKey, targetKey) {
  if (!conceptStore.projectId) return

  // Mark source as merged → target
  await applyConceptDecision(sourceKey, {
    status: 'merged',
    note: `归并到 ${targetKey}`,
    canonical_name: '',
  })
  // Persist merge_to on the source
  await putConceptDecision(conceptStore.projectId, sourceKey, {
    status: 'merged',
    note: `归并到 ${targetKey}`,
    canonical_name: '',
    merge_to: targetKey,
  })

  // Mark target as canonical if not already
  const target = conceptStore.items.find((c) => c.key === targetKey)
  if (target && target.status !== 'canonical') {
    await applyConceptDecision(targetKey, {
      status: 'canonical',
      note: target.note || '',
      canonical_name: target.canonicalName || target.displayName || '',
    })
  }
}
