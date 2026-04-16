// Demo registry provider — returns data derived from the shared
// entities fixture. Shape matches the real registryApi responses:
//
//   listRegistryConcepts → { success, data: { entries: [], total } }
//   getRegistryConcept   → { success, data: <entry> }
//   listCrossRelations   → { success, data: [<relation>...] }
//   getCrossRelation     → { success, data: <relation> }
//   getCrossRelationCounts → { success, data: { [entry_id]: n, ... } }

import {
  registryEntries,
  crossRelations,
  crossRelationsForEntry,
  findEntry,
  findRelation,
} from './fixtures/entities'

const clone = (v) => JSON.parse(JSON.stringify(v))

export async function listRegistryConcepts(conceptType) {
  let entries = registryEntries
  if (conceptType) {
    entries = entries.filter((e) => e.concept_type === conceptType)
  }
  return {
    success: true,
    data: { entries: clone(entries), total: entries.length },
  }
}

export async function getRegistryConcept(entryId) {
  const entry = findEntry(entryId)
  if (!entry) {
    throw new Error(`Demo data not available for concept "${entryId}".`)
  }
  return { success: true, data: clone(entry) }
}

export async function listCrossRelations(params = {}) {
  const entryId = params.entry_id
  const rows = entryId ? crossRelationsForEntry(entryId) : crossRelations
  // Augment with the source/target canonical names so the list-page
  // doesn't have to cross-reference. The real API does the same.
  const augmented = rows.map((r) => {
    const s = findEntry(r.source_entry_id)
    const t = findEntry(r.target_entry_id)
    return {
      ...r,
      source_name: s?.canonical_name || r.source_entry_id,
      target_name: t?.canonical_name || r.target_entry_id,
      source_entry: s ? { canonical_name: s.canonical_name, concept_type: s.concept_type } : null,
      target_entry: t ? { canonical_name: t.canonical_name, concept_type: t.concept_type } : null,
    }
  })
  return { success: true, data: clone(augmented) }
}

export async function getCrossRelation(relationId) {
  const rel = findRelation(relationId)
  if (!rel) {
    throw new Error(`Demo data not available for relation "${relationId}".`)
  }
  const s = findEntry(rel.source_entry_id)
  const t = findEntry(rel.target_entry_id)
  return {
    success: true,
    data: clone({
      ...rel,
      source_name: s?.canonical_name || rel.source_entry_id,
      target_name: t?.canonical_name || rel.target_entry_id,
      source_entry: s ? { canonical_name: s.canonical_name, concept_type: s.concept_type } : null,
      target_entry: t ? { canonical_name: t.canonical_name, concept_type: t.concept_type } : null,
      evidence_bridge: null,
      evidence_refs: [],
      discovery_path: 'demo-fixture',
    }),
  }
}

export async function getCrossRelationCounts(entryIds) {
  const counts = {}
  for (const id of entryIds || []) {
    counts[id] = crossRelationsForEntry(id).length
  }
  return { success: true, data: counts }
}
