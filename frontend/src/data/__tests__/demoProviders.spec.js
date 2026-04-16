// Unit tests for the demo provider functions. These are hermetic — they
// don't mount any Vue components; they just invoke the functions and
// inspect the returned shape. This gives us fast feedback that fixtures
// stay internally consistent and that every response matches the shape
// the real backend returns.

import { describe, expect, it } from 'vitest'

import * as demoRegistry from '../providers/demo/registryProvider'
import * as demoTheme from '../providers/demo/themeProvider'
import {
  registryEntries,
  themes,
  crossRelations,
} from '../providers/demo/fixtures/entities'

describe('demo registry provider', () => {
  it('listRegistryConcepts returns all entries with correct envelope', async () => {
    const res = await demoRegistry.listRegistryConcepts()
    expect(res.success).toBe(true)
    expect(res.data.entries.length).toBe(registryEntries.length)
    expect(res.data.total).toBe(registryEntries.length)
    // Must be a clone, not the original array.
    expect(res.data.entries).not.toBe(registryEntries)
  })

  it('listRegistryConcepts filters by concept_type', async () => {
    const res = await demoRegistry.listRegistryConcepts('Technology')
    expect(res.data.entries.every((e) => e.concept_type === 'Technology')).toBe(true)
    expect(res.data.entries.length).toBeGreaterThan(0)
  })

  it('getRegistryConcept returns the requested entry', async () => {
    const res = await demoRegistry.getRegistryConcept('reg-otel')
    expect(res.data.canonical_name).toBe('OpenTelemetry')
  })

  it('getRegistryConcept throws a friendly error for unknown entry', async () => {
    await expect(demoRegistry.getRegistryConcept('not-a-real-id')).rejects.toThrow(
      /Demo data not available/,
    )
  })

  it('listCrossRelations augments rows with source/target names', async () => {
    const res = await demoRegistry.listCrossRelations()
    expect(res.data.length).toBe(crossRelations.length)
    const rel = res.data[0]
    expect(rel.source_name).toBeTruthy()
    expect(rel.target_name).toBeTruthy()
  })

  it('listCrossRelations filters by entry_id', async () => {
    const res = await demoRegistry.listCrossRelations({ entry_id: 'reg-latency' })
    // Latency is a bridge concept — several relations should reference it.
    expect(res.data.length).toBeGreaterThan(0)
    for (const r of res.data) {
      expect(
        r.source_entry_id === 'reg-latency' || r.target_entry_id === 'reg-latency',
      ).toBe(true)
    }
  })

  it('getCrossRelation returns relation with hydrated names', async () => {
    const res = await demoRegistry.getCrossRelation('rel-otel-tracing')
    expect(res.data.source_name).toBe('OpenTelemetry')
    expect(res.data.target_name).toBe('调用链追踪')
    expect(res.data.relation_type).toBe('implements')
  })

  it('getCrossRelation throws on unknown relation', async () => {
    await expect(demoRegistry.getCrossRelation('nope')).rejects.toThrow(
      /Demo data not available/,
    )
  })

  it('getCrossRelationCounts returns a count per requested entry', async () => {
    const res = await demoRegistry.getCrossRelationCounts(['reg-otel', 'reg-tracing'])
    expect(typeof res.data['reg-otel']).toBe('number')
    expect(typeof res.data['reg-tracing']).toBe('number')
  })
})

describe('demo theme provider', () => {
  it('listGlobalThemes returns all demo themes', async () => {
    const res = await demoTheme.listGlobalThemes()
    expect(res.data.themes.length).toBe(themes.length)
  })

  it('getThemePanorama returns grouped_concepts bucketed by role', async () => {
    const res = await demoTheme.getThemePanorama('theme-observability')
    const g = res.data.grouped_concepts
    expect(Array.isArray(g.core)).toBe(true)
    expect(Array.isArray(g.bridge)).toBe(true)
    expect(Array.isArray(g.peripheral)).toBe(true)
    // Each entry has the fields the page reads.
    const first = g.core[0]
    expect(first.entry_id).toBeTruthy()
    expect(first.canonical_name).toBeTruthy()
    expect(first.concept_type).toBeTruthy()
  })

  it('getThemePanorama computes bridge_relations from bridge-role members', async () => {
    const res = await demoTheme.getThemePanorama('theme-observability')
    // latency is a bridge member and has at least one relation pointing
    // in/out of it — it should appear in bridge_relations.
    const bridgeIds = new Set(
      res.data.bridge_relations.flatMap((r) => [r.source_entry_id, r.target_entry_id]),
    )
    expect(bridgeIds.has('reg-latency')).toBe(true)
  })

  it('getThemePanorama throws for unknown theme', async () => {
    await expect(demoTheme.getThemePanorama('theme-nope')).rejects.toThrow(
      /Demo data not available/,
    )
  })

  it('getThemeHubView throws for unknown theme', async () => {
    await expect(demoTheme.getThemeHubView('theme-nope')).rejects.toThrow(
      /Demo data not available/,
    )
  })

  it('getOrphans returns concepts not in any theme', async () => {
    const res = await demoTheme.getOrphans()
    const memberIds = new Set(
      themes.flatMap((t) => t.concept_memberships.map((m) => m.entry_id)),
    )
    for (const o of res.data.orphans) {
      expect(memberIds.has(o.entry_id)).toBe(false)
    }
  })
})

describe('demo fixture cross-references are internally consistent', () => {
  const entryIds = new Set(registryEntries.map((e) => e.entry_id))

  it('every theme membership references a valid entry_id', () => {
    for (const theme of themes) {
      for (const m of theme.concept_memberships) {
        expect(entryIds.has(m.entry_id)).toBe(true)
      }
    }
  })

  it('every cross-relation references valid entry_ids on both ends', () => {
    for (const r of crossRelations) {
      expect(entryIds.has(r.source_entry_id)).toBe(true)
      expect(entryIds.has(r.target_entry_id)).toBe(true)
    }
  })
})
