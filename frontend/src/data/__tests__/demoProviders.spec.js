// Unit tests for the demo provider functions. These are hermetic — they
// don't mount any Vue components; they just invoke the functions and
// inspect the returned shape. This gives us fast feedback that fixtures
// stay internally consistent and that every response matches the shape
// the real backend returns.

import { describe, expect, it } from 'vitest'

import * as demoRegistry from '../providers/demo/registryProvider'
import * as demoTheme from '../providers/demo/themeProvider'
import * as demoResearchProjects from '../providers/demo/researchProjectProvider'
import {
  registryEntries,
  themes,
  crossRelations,
} from '../providers/demo/fixtures/entities'
import { demoResearchProjects as researchProjectFixture } from '../providers/demo/fixtures/researchProjects'

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

describe('demo research project provider', () => {
  it('lists static research projects with backend-like envelope', async () => {
    const res = await demoResearchProjects.listResearchProjects()
    expect(res.success).toBe(true)
    expect(res.data.projects.length).toBe(researchProjectFixture.length)
    expect(res.data.projects[0].title).toContain('华为云 Agent-ready')
  })

  it('gets one research project by id', async () => {
    const res = await demoResearchProjects.getResearchProject('rp_de0a00000001')
    expect(res.data.id).toBe('rp_de0a00000001')
    expect(res.data.status).toBe('draft')
  })

  it('supports demo local evidence pack review in memory', async () => {
    const pack = await demoResearchProjects.getLocalEvidencePack('rp_de0a00000001')
    expect(pack.data.local_evidence_pack.summary.candidate_count).toBeGreaterThanOrEqual(3)

    const accepted = await demoResearchProjects.updateLocalEvidenceCandidate(
      'rp_de0a00000001',
      'ev_de0a00000001',
      { status: 'accepted', note: 'use it' },
    )
    expect(accepted.data.local_evidence_pack.summary.accepted_count).toBe(1)
    expect(accepted.data.evidence_items.some((item) => item.evidence_id === 'ev_de0a00000001')).toBe(true)

    const rejected = await demoResearchProjects.updateLocalEvidenceCandidate(
      'rp_de0a00000001',
      'ev_de0a00000001',
      { status: 'rejected' },
    )
    expect(rejected.data.local_evidence_pack.rejected_evidence_ids).toContain('ev_de0a00000001')
    expect(rejected.data.evidence_items.some((item) => item.evidence_id === 'ev_de0a00000001')).toBe(false)
  })

  it('supports demo Codex writeback asset reads and external candidate review', async () => {
    const runs = await demoResearchProjects.listResearchRuns('rp_de0a00000001')
    expect(runs.data.research_runs[0].stage).toBe('P3')

    const consultations = await demoResearchProjects.listConsultationLogs('rp_de0a00000001')
    expect(consultations.data.consultation_logs[0].kind).toBe('gpt_design_review')

    const packs = await demoResearchProjects.listExternalResearchPacks('rp_de0a00000001')
    expect(packs.data.external_research_packs[0].scope).toBe('C2_external')
    expect(packs.data.external_research_packs[0].evidence_candidates.length).toBe(3)

    const accepted = await demoResearchProjects.updateExternalResearchCandidate(
      'rp_de0a00000001',
      'erp_de0a00000001',
      'ec_de0a00000001',
      { review_status: 'accepted' },
    )
    expect(accepted.data.external_research_pack.accepted_count).toBe(1)
    const externalEvidence = accepted.data.evidence_items.find((item) => item.origin === 'external_research_pack')
    expect(externalEvidence.scope).toBe('C2_external')
  })

  it('supports demo synthesis asset reads and status updates', async () => {
    const rows = await demoResearchProjects.listEvidenceMatrixRows('rp_de0a00000001')
    expect(rows.data.rows[0].claim).toContain('执行控制面')

    const patchedRow = await demoResearchProjects.updateEvidenceMatrixRow(
      'rp_de0a00000001',
      'emr_de0a00000001',
      { status: 'reviewed' },
    )
    expect(patchedRow.data.row.status).toBe('reviewed')

    const cards = await demoResearchProjects.listInsightCards('rp_de0a00000001')
    expect(cards.data.insight_cards[0].title).toBe('执行控制面是长期控制点')

    const patchedCard = await demoResearchProjects.updateInsightCard(
      'rp_de0a00000001',
      'ic_de0a00000001',
      { status: 'accepted' },
    )
    expect(patchedCard.data.insight_card.status).toBe('accepted')

    const drafts = await demoResearchProjects.listArtifactDrafts('rp_de0a00000001')
    expect(drafts.data.artifact_drafts[0].outline.length).toBeGreaterThan(0)

    const patchedDraft = await demoResearchProjects.updateArtifactDraft(
      'rp_de0a00000001',
      'ad_de0a00000001',
      { material_readiness: 'presentation_ready' },
    )
    expect(patchedDraft.data.artifact_draft.material_readiness).toBe('presentation_ready')
  })

  it('supports demo material workshop reads and review records', async () => {
    const packs = await demoResearchProjects.listArtifactPacks('rp_de0a00000001')
    expect(packs.data.artifact_packs[0].title).toContain('战略汇报材料包')

    const updated = await demoResearchProjects.updateArtifactPack(
      'rp_de0a00000001',
      'ap_de0a00000001',
      { status: 'in_review', readiness: 'review_ready' },
    )
    expect(updated.data.artifact_pack.status).toBe('in_review')

    const page = updated.data.artifact_pack.pages[0]
    const reviewed = await demoResearchProjects.addArtifactPackReviewRound(
      'rp_de0a00000001',
      'ap_de0a00000001',
      {
        round_name: 'P5 review round 1',
        reviewer: 'human',
        decisions: [{
          target_type: 'page',
          target_id: page.page_id,
          decision: 'needs_revision',
          severity: 'major',
        }],
      },
    )
    expect(reviewed.data.artifact_pack.review_rounds[0].round_name).toBe('P5 review round 1')
    expect(reviewed.data.artifact_pack.pages[0].review_status).toBe('needs_revision')
  })

  it('supports demo traceability map reads and filters', async () => {
    const map = await demoResearchProjects.getTraceabilityMap('rp_de0a00000001')
    expect(map.data.view_type).toBe('strategic_research_traceability_map')
    expect(map.data.nodes.some((node) => node.asset_type === 'leadership_briefing')).toBe(true)
    expect(map.data.edges.some((edge) => edge.relation_type === 'supports')).toBe(true)

    const filtered = await demoResearchProjects.getTraceabilityMap(
      'rp_de0a00000001',
      { asset_type: 'insight_card', issue_severity: 'warning' },
    )
    expect(filtered.data.nodes.every((node) => node.asset_type === 'insight_card')).toBe(true)
    expect(filtered.data.issues.every((issue) => issue.severity === 'warning')).toBe(true)
  })

  it('supports demo governance review reads and manual status updates', async () => {
    const reviews = await demoResearchProjects.listGovernanceReviews('rp_de0a00000001')
    expect(reviews.data.governance_reviews[0].title).toContain('P9 strategic research')
    expect(reviews.data.governance_reviews[0].finding_count).toBeGreaterThan(0)

    const detail = await demoResearchProjects.getGovernanceReview(
      'rp_de0a00000001',
      'gr_de0a00000001',
    )
    expect(detail.data.governance_review.checklist_items[0].label).toContain('Traceability map')

    const updated = await demoResearchProjects.updateGovernanceReview(
      'rp_de0a00000001',
      'gr_de0a00000001',
      { status: 'signed_off', gate_decision: 'ready_with_risks', readiness: 'ready' },
    )
    expect(updated.data.governance_review.status).toBe('signed_off')
  })

  it('supports demo review history timelines and manual notes', async () => {
    const before = await demoResearchProjects.listReviewHistory('rp_de0a00000001', { asset_type: 'governance_review' })
    expect(before.data.review_history_entries[0].asset_type).toBe('governance_review')

    await demoResearchProjects.updateGovernanceReview(
      'rp_de0a00000001',
      'gr_de0a00000001',
      { gate_decision: 'blocked', readiness: 'not_ready' },
    )
    const assetHistory = await demoResearchProjects.getAssetReviewHistory(
      'rp_de0a00000001',
      'governance_review',
      'gr_de0a00000001',
    )
    expect(assetHistory.data.review_history_entries[0].event_type).toBe('gate_decision_changed')

    const note = await demoResearchProjects.createReviewHistoryNote('rp_de0a00000001', {
      asset_type: 'governance_review',
      asset_id: 'gr_de0a00000001',
      note: 'Accepted remaining risks for readout.',
      actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    })
    expect(note.data.review_history_entry.event_type).toBe('review_note_added')

    const detail = await demoResearchProjects.getReviewHistoryEntry(
      'rp_de0a00000001',
      note.data.review_history_entry.history_entry_id,
    )
    expect(detail.data.review_history_entry.note).toContain('Accepted remaining risks')
  })

  it('supports demo research snapshots and read-only diffs', async () => {
    const listed = await demoResearchProjects.listResearchSnapshots('rp_de0a00000001')
    expect(listed.data.snapshots[0].title).toBe('P11 Gate Baseline')

    const created = await demoResearchProjects.createResearchSnapshot('rp_de0a00000001', {
      title: 'P11 Demo Baseline',
      reason: 'Freeze demo project.',
      gate_type: 'p11_gate',
      governance_review_id: 'gr_de0a00000001',
    })
    expect(created.data.snapshot.snapshot_id).toContain('rs_demo_')

    const nextGate = created.data.snapshot.linked_governance_review.gate_decision === 'blocked'
      ? 'ready_with_risks'
      : 'blocked'
    await demoResearchProjects.updateGovernanceReview(
      'rp_de0a00000001',
      'gr_de0a00000001',
      { gate_decision: nextGate, readiness: 'not_ready' },
    )
    const diff = await demoResearchProjects.diffResearchSnapshot(
      'rp_de0a00000001',
      created.data.snapshot.snapshot_id,
    )
    expect(diff.data.snapshot_diff.summary.has_changes).toBe(true)
    expect(diff.data.snapshot_diff.summary.governance_gate_decision_changed).toBe(true)

    const detail = await demoResearchProjects.getResearchSnapshot(
      'rp_de0a00000001',
      created.data.snapshot.snapshot_id,
    )
    expect(detail.data.snapshot.review_history_watermark.entry_count).toBe(created.data.snapshot.review_history_watermark.entry_count)

    const beforeNotes = await demoResearchProjects.listSnapshotReviewNotes(
      'rp_de0a00000001',
      created.data.snapshot.snapshot_id,
    )
    expect(beforeNotes.data.snapshot_review_notes).toEqual([])
    const note = await demoResearchProjects.createSnapshotReviewNote(
      'rp_de0a00000001',
      created.data.snapshot.snapshot_id,
      {
        target_ref: { section_key: 'governance_gate' },
        note_type: 'observation',
        severity: 'watch',
        note: 'Manual note on demo snapshot diff.',
      },
    )
    expect(note.data.snapshot_review_note.note_id).toContain('srn_demo_')
    const afterNotes = await demoResearchProjects.listSnapshotReviewNotes(
      'rp_de0a00000001',
      created.data.snapshot.snapshot_id,
    )
    expect(afterNotes.data.snapshot_review_notes[0].note).toBe('Manual note on demo snapshot diff.')
    const beforeHistory = await demoResearchProjects.listReviewHistory('rp_de0a00000001')
    const updatedNote = await demoResearchProjects.updateSnapshotReviewNote(
      'rp_de0a00000001',
      created.data.snapshot.snapshot_id,
      note.data.snapshot_review_note.note_id,
      {
        status: 'resolved',
        owner: 'Reviewer',
        resolution_note: 'Manual disposition recorded.',
        actor: 'Reviewer',
      },
    )
    expect(updatedNote.data.snapshot_review_note.status).toBe('resolved')
    expect(updatedNote.data.snapshot_review_note.owner).toBe('Reviewer')
    expect(updatedNote.data.snapshot_review_note.resolved_by).toBe('Reviewer')
    const afterHistory = await demoResearchProjects.listReviewHistory('rp_de0a00000001')
    expect(afterHistory.data.review_history_entries.length).toBe(beforeHistory.data.review_history_entries.length + 1)
    expect(afterHistory.data.review_history_entries[0].event_type).toBe('snapshot_review_note_disposition_updated')
  })

  it('keeps demo mutations readonly', async () => {
    await expect(demoResearchProjects.createResearchProject({ title: 'x' })).rejects.toThrow('Demo 模式为只读')
    await expect(demoResearchProjects.updateResearchProject('rp_de0a00000001', { title: 'x' })).rejects.toThrow('Demo 模式为只读')
    await expect(demoResearchProjects.createGovernanceReview('rp_de0a00000001', { title: 'x' })).rejects.toThrow('Demo 模式为只读')
  })
})
