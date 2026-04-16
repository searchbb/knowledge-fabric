// Demo theme provider. Themes are derived from the shared entities
// fixture so theme memberships point at real registry entries.

import {
  themes,
  registryEntries,
  crossRelations,
  findTheme,
  findEntry,
} from './fixtures/entities'

const clone = (v) => JSON.parse(JSON.stringify(v))

export async function listGlobalThemes() {
  return { success: true, data: { themes: clone(themes) } }
}

// Used by the ThemeTab inside RegistryPage (previously raw service()).
// Shape is identical to the real endpoint: { data: { themes } }.
export async function listThemesViaRegistryTab() {
  return { success: true, data: { themes: clone(themes) } }
}

export async function getThemeHubView(themeId) {
  const theme = findTheme(themeId)
  if (!theme) {
    throw new Error(`Demo data not available for theme "${themeId}".`)
  }
  // Expand memberships into concept objects for easier rendering.
  const members = theme.concept_memberships.map((m) => {
    const entry = findEntry(m.entry_id)
    return {
      ...m,
      entry: entry ? clone(entry) : null,
    }
  })
  return {
    success: true,
    data: clone({
      theme,
      members,
      stats: {
        concept_count: members.length,
        article_count: new Set(
          members.flatMap((m) => (m.entry?.source_links || []).map((s) => s.project_id)),
        ).size,
      },
    }),
  }
}

export async function getThemePanorama(themeId) {
  const theme = findTheme(themeId)
  if (!theme) {
    throw new Error(`Demo data not available for theme "${themeId}".`)
  }

  // Bucket members by role for the grouped_concepts structure the
  // ThemeDetailPage expects. Augment each with the canonical entry data
  // the page reads (canonical_name, description, etc).
  const grouped = { core: [], bridge: [], peripheral: [] }
  for (const m of theme.concept_memberships) {
    const entry = findEntry(m.entry_id)
    if (!entry) continue
    const row = {
      entry_id: entry.entry_id,
      canonical_name: entry.canonical_name,
      concept_type: entry.concept_type,
      description: entry.description,
      source_links: entry.source_links,
      role: m.role,
      bridge_score: m.role === 'bridge' ? m.score : null,
      xrel_count: crossRelations.filter(
        (r) => r.source_entry_id === entry.entry_id || r.target_entry_id === entry.entry_id,
      ).length,
      description_degraded: false,
    }
    const bucket = grouped[m.role] || grouped.peripheral
    bucket.push(row)
  }

  // Bridge relations: cross-relations that involve a bridge-role member.
  const bridgeIds = new Set(
    theme.concept_memberships.filter((m) => m.role === 'bridge').map((m) => m.entry_id),
  )
  const bridgeRelations = crossRelations
    .filter((r) => bridgeIds.has(r.source_entry_id) || bridgeIds.has(r.target_entry_id))
    .map((r) => {
      const s = findEntry(r.source_entry_id)
      const t = findEntry(r.target_entry_id)
      return {
        ...r,
        source_name: s?.canonical_name || r.source_entry_id,
        target_name: t?.canonical_name || r.target_entry_id,
      }
    })

  return {
    success: true,
    data: clone({
      theme,
      stats: {
        concept_count: theme.concept_memberships.length,
        article_count: new Set(
          theme.concept_memberships
            .map((m) => findEntry(m.entry_id))
            .filter(Boolean)
            .flatMap((e) => (e.source_links || []).map((s) => s.project_id)),
        ).size,
        relation_count: bridgeRelations.length,
      },
      grouped_concepts: grouped,
      bridge_relations: bridgeRelations,
      suggested_memberships: [],
      silent_failures: {
        xrels_with_partial_source: 0,
        xrels_with_no_readable_source: 0,
        descriptions_degraded: 0,
        concepts_missing_source_links: 0,
        bridge_without_xrels: 0,
      },
      discovery_coverage: {
        last_run_at: '2026-04-12T06:20:00Z',
        discovered: bridgeRelations.length,
      },
    }),
  }
}

export async function getOrphans(limit = 200) {
  // An "orphan" is a concept with no theme membership. In the demo
  // fixture, compute dynamically so it stays consistent if entries shift.
  const memberIds = new Set(
    themes.flatMap((t) => t.concept_memberships.map((m) => m.entry_id)),
  )
  const orphans = registryEntries
    .filter((e) => !memberIds.has(e.entry_id))
    .slice(0, limit)
    .map((e) => clone(e))
  return { success: true, data: { orphans } }
}
