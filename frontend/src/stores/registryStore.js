import { reactive } from 'vue'
import {
  listRegistryConcepts,
  getRegistryConcept,
  createRegistryConcept,
  updateRegistryConcept,
  deleteRegistryConcept,
  linkProjectConcept,
  unlinkProjectConcept,
  searchRegistryConcepts,
  suggestFromProject,
  getProjectAlignment,
  listCrossRelations,
  updateCrossRelation,
  deleteCrossRelation,
  getCrossRelationCounts,
} from '../services/api/registryApi'

export const registryStore = reactive({
  // Entry list
  entries: [],
  total: 0,
  loading: false,
  error: '',

  // Selected entry detail
  selectedEntryId: '',
  selectedEntry: null,
  detailLoading: false,

  // Search
  searchQuery: '',
  searchResults: [],
  searchLoading: false,

  // Suggest
  suggestResult: null,
  suggestLoading: false,

  // Alignment
  alignmentResult: null,
  alignmentLoading: false,

  // Cross-article relations (L3)
  crossRelations: [],
  crossRelationsLoading: false,
  crossRelationCounts: {},  // entry_id -> count

  // Edit/action state
  saving: false,
  actionError: '',
})

// ---------------------------------------------------------------------------
// List & detail
// ---------------------------------------------------------------------------

export async function loadEntries(conceptType) {
  registryStore.loading = true
  registryStore.error = ''
  try {
    const res = await listRegistryConcepts(conceptType)
    registryStore.entries = res.data?.entries || []
    registryStore.total = res.data?.total || 0
  } catch (e) {
    registryStore.error = e.message || '注册表加载失败'
  } finally {
    registryStore.loading = false
  }
}

export async function selectEntry(entryId) {
  if (!entryId) {
    registryStore.selectedEntryId = ''
    registryStore.selectedEntry = null
    return
  }
  registryStore.selectedEntryId = entryId
  registryStore.detailLoading = true
  try {
    const res = await getRegistryConcept(entryId)
    registryStore.selectedEntry = res.data || null
  } catch (e) {
    registryStore.selectedEntry = null
    registryStore.actionError = e.message || '条目加载失败'
  } finally {
    registryStore.detailLoading = false
  }
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export async function addEntry({ canonical_name, concept_type, aliases, description }) {
  registryStore.saving = true
  registryStore.actionError = ''
  try {
    const res = await createRegistryConcept({ canonical_name, concept_type, aliases, description })
    const entry = res.data
    registryStore.entries.unshift(entry)
    registryStore.total += 1
    return entry
  } catch (e) {
    registryStore.actionError = e.message || '创建失败'
    return null
  } finally {
    registryStore.saving = false
  }
}

export async function editEntry(entryId, updates) {
  registryStore.saving = true
  registryStore.actionError = ''
  try {
    const res = await updateRegistryConcept(entryId, updates)
    const updated = res.data
    // Update in list
    const idx = registryStore.entries.findIndex((e) => e.entry_id === entryId)
    if (idx >= 0) registryStore.entries[idx] = updated
    if (registryStore.selectedEntryId === entryId) registryStore.selectedEntry = updated
    return updated
  } catch (e) {
    registryStore.actionError = e.message || '更新失败'
    return null
  } finally {
    registryStore.saving = false
  }
}

export async function removeEntry(entryId) {
  registryStore.saving = true
  registryStore.actionError = ''
  try {
    await deleteRegistryConcept(entryId)
    registryStore.entries = registryStore.entries.filter((e) => e.entry_id !== entryId)
    registryStore.total -= 1
    if (registryStore.selectedEntryId === entryId) {
      registryStore.selectedEntryId = ''
      registryStore.selectedEntry = null
    }
    return true
  } catch (e) {
    registryStore.actionError = e.message || '删除失败'
    return false
  } finally {
    registryStore.saving = false
  }
}

// ---------------------------------------------------------------------------
// Link / unlink
// ---------------------------------------------------------------------------

export async function linkConcept(entryId, { project_id, concept_key, project_name }) {
  registryStore.saving = true
  registryStore.actionError = ''
  try {
    const res = await linkProjectConcept(entryId, { project_id, concept_key, project_name })
    const updated = res.data
    const idx = registryStore.entries.findIndex((e) => e.entry_id === entryId)
    if (idx >= 0) registryStore.entries[idx] = updated
    if (registryStore.selectedEntryId === entryId) registryStore.selectedEntry = updated
    return updated
  } catch (e) {
    registryStore.actionError = e.message || '链接失败'
    return null
  } finally {
    registryStore.saving = false
  }
}

export async function unlinkConcept(entryId, { project_id, concept_key }) {
  registryStore.saving = true
  registryStore.actionError = ''
  try {
    const res = await unlinkProjectConcept(entryId, { project_id, concept_key })
    const updated = res.data
    const idx = registryStore.entries.findIndex((e) => e.entry_id === entryId)
    if (idx >= 0) registryStore.entries[idx] = updated
    if (registryStore.selectedEntryId === entryId) registryStore.selectedEntry = updated
    return updated
  } catch (e) {
    registryStore.actionError = e.message || '解绑失败'
    return null
  } finally {
    registryStore.saving = false
  }
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export async function searchEntries(query) {
  registryStore.searchQuery = query
  if (!query.trim()) {
    registryStore.searchResults = []
    return
  }
  registryStore.searchLoading = true
  try {
    const res = await searchRegistryConcepts(query)
    registryStore.searchResults = res.data?.results || []
  } catch (e) {
    registryStore.searchResults = []
  } finally {
    registryStore.searchLoading = false
  }
}

// ---------------------------------------------------------------------------
// Suggest from project
// ---------------------------------------------------------------------------

export async function loadSuggestions(projectId) {
  registryStore.suggestLoading = true
  registryStore.suggestResult = null
  try {
    const res = await suggestFromProject(projectId)
    registryStore.suggestResult = res.data || null
  } catch (e) {
    registryStore.actionError = e.message || '推荐加载失败'
  } finally {
    registryStore.suggestLoading = false
  }
}

// ---------------------------------------------------------------------------
// Alignment
// ---------------------------------------------------------------------------

export async function loadAlignment(projectId) {
  registryStore.alignmentLoading = true
  registryStore.alignmentResult = null
  try {
    const res = await getProjectAlignment(projectId)
    registryStore.alignmentResult = res.data || null
  } catch (e) {
    registryStore.actionError = e.message || '对齐视图加载失败'
  } finally {
    registryStore.alignmentLoading = false
  }
}

// ---------------------------------------------------------------------------
// Cross-article relations (L3)
// ---------------------------------------------------------------------------

let _crossRelRequestId = 0
export async function loadCrossRelations(entryId, params = {}) {
  const requestId = ++_crossRelRequestId
  registryStore.crossRelationsLoading = true
  try {
    const res = await listCrossRelations({ entry_id: entryId, ...params })
    // Guard: discard stale response if user clicked a different concept while waiting
    if (requestId !== _crossRelRequestId) return
    registryStore.crossRelations = res.data || []
  } catch (e) {
    if (requestId !== _crossRelRequestId) return
    registryStore.crossRelations = []
    registryStore.actionError = e.message || '跨文章关系加载失败'
  } finally {
    if (requestId === _crossRelRequestId) {
      registryStore.crossRelationsLoading = false
    }
  }
}

export async function loadCrossRelationCounts(entryIds) {
  if (!entryIds?.length) return
  try {
    const res = await getCrossRelationCounts(entryIds)
    registryStore.crossRelationCounts = res.data || {}
  } catch {
    // Silently fail — counts are non-critical UI enhancement
  }
}

export async function reviewCrossRelation(relationId, { review_status, review_note }) {
  registryStore.saving = true
  try {
    const res = await updateCrossRelation(relationId, { review_status, review_note })
    // Update in local list
    const idx = registryStore.crossRelations.findIndex(r => r.relation_id === relationId)
    if (idx >= 0) registryStore.crossRelations[idx] = res.data
    return res.data
  } catch (e) {
    registryStore.actionError = e.message || '审阅失败'
    return null
  } finally {
    registryStore.saving = false
  }
}

export async function removeCrossRelation(relationId) {
  registryStore.saving = true
  try {
    await deleteCrossRelation(relationId)
    registryStore.crossRelations = registryStore.crossRelations.filter(r => r.relation_id !== relationId)
    // Decrement counts for involved entries
    return true
  } catch (e) {
    registryStore.actionError = e.message || '删除失败'
    return false
  } finally {
    registryStore.saving = false
  }
}
