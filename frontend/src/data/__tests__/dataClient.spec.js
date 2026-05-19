// Tests for the dataClient public surface.
//
// Goal: prove that the same method call reaches the live provider when
// appMode is 'live' and the demo provider when it's 'demo'. That's the
// whole contract of this layer — the pages rely on it.

import { beforeEach, describe, expect, it, vi } from 'vitest'

const liveGetOverview = vi.fn()
const demoGetOverview = vi.fn()
const liveGetProjectWorkbench = vi.fn()
const demoGetProjectWorkbench = vi.fn()
const liveListResearchProjects = vi.fn()
const demoListResearchProjects = vi.fn()
const liveCreateResearchProject = vi.fn()
const demoCreateResearchProject = vi.fn()
const liveGetLocalEvidencePack = vi.fn()
const demoGetLocalEvidencePack = vi.fn()
const liveSearchLocalEvidencePack = vi.fn()
const demoSearchLocalEvidencePack = vi.fn()
const liveUpdateLocalEvidenceCandidate = vi.fn()
const demoUpdateLocalEvidenceCandidate = vi.fn()
const liveListResearchRuns = vi.fn()
const demoListResearchRuns = vi.fn()
const liveListConsultationLogs = vi.fn()
const demoListConsultationLogs = vi.fn()
const liveListExternalResearchPacks = vi.fn()
const demoListExternalResearchPacks = vi.fn()
const liveUpdateExternalResearchCandidate = vi.fn()
const demoUpdateExternalResearchCandidate = vi.fn()
const liveListEvidenceMatrixRows = vi.fn()
const demoListEvidenceMatrixRows = vi.fn()
const liveCreateEvidenceMatrixRow = vi.fn()
const demoCreateEvidenceMatrixRow = vi.fn()
const liveUpdateEvidenceMatrixRow = vi.fn()
const demoUpdateEvidenceMatrixRow = vi.fn()
const liveListInsightCards = vi.fn()
const demoListInsightCards = vi.fn()
const liveCreateInsightCard = vi.fn()
const demoCreateInsightCard = vi.fn()
const liveUpdateInsightCard = vi.fn()
const demoUpdateInsightCard = vi.fn()
const liveListArtifactDrafts = vi.fn()
const demoListArtifactDrafts = vi.fn()
const liveCreateArtifactDraft = vi.fn()
const demoCreateArtifactDraft = vi.fn()
const liveUpdateArtifactDraft = vi.fn()
const demoUpdateArtifactDraft = vi.fn()
const liveGetTraceabilityMap = vi.fn()
const demoGetTraceabilityMap = vi.fn()
const liveListGovernanceReviews = vi.fn()
const demoListGovernanceReviews = vi.fn()
const liveCreateGovernanceReview = vi.fn()
const demoCreateGovernanceReview = vi.fn()
const liveGetGovernanceReview = vi.fn()
const demoGetGovernanceReview = vi.fn()
const liveUpdateGovernanceReview = vi.fn()
const demoUpdateGovernanceReview = vi.fn()
const liveListReviewHistory = vi.fn()
const demoListReviewHistory = vi.fn()
const liveGetAssetReviewHistory = vi.fn()
const demoGetAssetReviewHistory = vi.fn()
const liveGetReviewHistoryEntry = vi.fn()
const demoGetReviewHistoryEntry = vi.fn()
const liveCreateReviewHistoryNote = vi.fn()
const demoCreateReviewHistoryNote = vi.fn()
const liveListResearchSnapshots = vi.fn()
const demoListResearchSnapshots = vi.fn()
const liveCreateResearchSnapshot = vi.fn()
const demoCreateResearchSnapshot = vi.fn()
const liveGetResearchSnapshot = vi.fn()
const demoGetResearchSnapshot = vi.fn()
const liveDiffResearchSnapshot = vi.fn()
const demoDiffResearchSnapshot = vi.fn()
const liveListSnapshotReviewNotes = vi.fn()
const demoListSnapshotReviewNotes = vi.fn()
const liveCreateSnapshotReviewNote = vi.fn()
const demoCreateSnapshotReviewNote = vi.fn()
const liveGetSnapshotReviewNote = vi.fn()
const demoGetSnapshotReviewNote = vi.fn()
const liveUpdateSnapshotReviewNote = vi.fn()
const demoUpdateSnapshotReviewNote = vi.fn()

vi.mock('../providers/live/overviewProvider', () => ({
  getOverview: (...args) => liveGetOverview(...args),
}))
vi.mock('../providers/demo/overviewProvider', () => ({
  getOverview: (...args) => demoGetOverview(...args),
}))
vi.mock('../providers/live/workspaceProvider', () => ({
  getProjectWorkbench: (...args) => liveGetProjectWorkbench(...args),
}))
vi.mock('../providers/demo/workspaceProvider', () => ({
  getProjectWorkbench: (...args) => demoGetProjectWorkbench(...args),
}))
vi.mock('../providers/live/researchProjectProvider', () => ({
  listResearchProjects: (...args) => liveListResearchProjects(...args),
  createResearchProject: (...args) => liveCreateResearchProject(...args),
  getResearchProject: vi.fn(),
  updateResearchProject: vi.fn(),
  getLocalEvidencePack: (...args) => liveGetLocalEvidencePack(...args),
  searchLocalEvidencePack: (...args) => liveSearchLocalEvidencePack(...args),
  updateLocalEvidenceCandidate: (...args) => liveUpdateLocalEvidenceCandidate(...args),
  listResearchRuns: (...args) => liveListResearchRuns(...args),
  listConsultationLogs: (...args) => liveListConsultationLogs(...args),
  listExternalResearchPacks: (...args) => liveListExternalResearchPacks(...args),
  updateExternalResearchCandidate: (...args) => liveUpdateExternalResearchCandidate(...args),
  listEvidenceMatrixRows: (...args) => liveListEvidenceMatrixRows(...args),
  createEvidenceMatrixRow: (...args) => liveCreateEvidenceMatrixRow(...args),
  updateEvidenceMatrixRow: (...args) => liveUpdateEvidenceMatrixRow(...args),
  listInsightCards: (...args) => liveListInsightCards(...args),
  createInsightCard: (...args) => liveCreateInsightCard(...args),
  updateInsightCard: (...args) => liveUpdateInsightCard(...args),
  listArtifactDrafts: (...args) => liveListArtifactDrafts(...args),
  createArtifactDraft: (...args) => liveCreateArtifactDraft(...args),
  updateArtifactDraft: (...args) => liveUpdateArtifactDraft(...args),
  getTraceabilityMap: (...args) => liveGetTraceabilityMap(...args),
  listGovernanceReviews: (...args) => liveListGovernanceReviews(...args),
  createGovernanceReview: (...args) => liveCreateGovernanceReview(...args),
  getGovernanceReview: (...args) => liveGetGovernanceReview(...args),
  updateGovernanceReview: (...args) => liveUpdateGovernanceReview(...args),
  listReviewHistory: (...args) => liveListReviewHistory(...args),
  getAssetReviewHistory: (...args) => liveGetAssetReviewHistory(...args),
  getReviewHistoryEntry: (...args) => liveGetReviewHistoryEntry(...args),
  createReviewHistoryNote: (...args) => liveCreateReviewHistoryNote(...args),
  listResearchSnapshots: (...args) => liveListResearchSnapshots(...args),
  createResearchSnapshot: (...args) => liveCreateResearchSnapshot(...args),
  getResearchSnapshot: (...args) => liveGetResearchSnapshot(...args),
  diffResearchSnapshot: (...args) => liveDiffResearchSnapshot(...args),
  listSnapshotReviewNotes: (...args) => liveListSnapshotReviewNotes(...args),
  createSnapshotReviewNote: (...args) => liveCreateSnapshotReviewNote(...args),
  getSnapshotReviewNote: (...args) => liveGetSnapshotReviewNote(...args),
  updateSnapshotReviewNote: (...args) => liveUpdateSnapshotReviewNote(...args),
}))
vi.mock('../providers/demo/researchProjectProvider', () => ({
  listResearchProjects: (...args) => demoListResearchProjects(...args),
  createResearchProject: (...args) => demoCreateResearchProject(...args),
  getResearchProject: vi.fn(),
  updateResearchProject: vi.fn(),
  getLocalEvidencePack: (...args) => demoGetLocalEvidencePack(...args),
  searchLocalEvidencePack: (...args) => demoSearchLocalEvidencePack(...args),
  updateLocalEvidenceCandidate: (...args) => demoUpdateLocalEvidenceCandidate(...args),
  listResearchRuns: (...args) => demoListResearchRuns(...args),
  listConsultationLogs: (...args) => demoListConsultationLogs(...args),
  listExternalResearchPacks: (...args) => demoListExternalResearchPacks(...args),
  updateExternalResearchCandidate: (...args) => demoUpdateExternalResearchCandidate(...args),
  listEvidenceMatrixRows: (...args) => demoListEvidenceMatrixRows(...args),
  createEvidenceMatrixRow: (...args) => demoCreateEvidenceMatrixRow(...args),
  updateEvidenceMatrixRow: (...args) => demoUpdateEvidenceMatrixRow(...args),
  listInsightCards: (...args) => demoListInsightCards(...args),
  createInsightCard: (...args) => demoCreateInsightCard(...args),
  updateInsightCard: (...args) => demoUpdateInsightCard(...args),
  listArtifactDrafts: (...args) => demoListArtifactDrafts(...args),
  createArtifactDraft: (...args) => demoCreateArtifactDraft(...args),
  updateArtifactDraft: (...args) => demoUpdateArtifactDraft(...args),
  getTraceabilityMap: (...args) => demoGetTraceabilityMap(...args),
  listGovernanceReviews: (...args) => demoListGovernanceReviews(...args),
  createGovernanceReview: (...args) => demoCreateGovernanceReview(...args),
  getGovernanceReview: (...args) => demoGetGovernanceReview(...args),
  updateGovernanceReview: (...args) => demoUpdateGovernanceReview(...args),
  listReviewHistory: (...args) => demoListReviewHistory(...args),
  getAssetReviewHistory: (...args) => demoGetAssetReviewHistory(...args),
  getReviewHistoryEntry: (...args) => demoGetReviewHistoryEntry(...args),
  createReviewHistoryNote: (...args) => demoCreateReviewHistoryNote(...args),
  listResearchSnapshots: (...args) => demoListResearchSnapshots(...args),
  createResearchSnapshot: (...args) => demoCreateResearchSnapshot(...args),
  getResearchSnapshot: (...args) => demoGetResearchSnapshot(...args),
  diffResearchSnapshot: (...args) => demoDiffResearchSnapshot(...args),
  listSnapshotReviewNotes: (...args) => demoListSnapshotReviewNotes(...args),
  createSnapshotReviewNote: (...args) => demoCreateSnapshotReviewNote(...args),
  getSnapshotReviewNote: (...args) => demoGetSnapshotReviewNote(...args),
  updateSnapshotReviewNote: (...args) => demoUpdateSnapshotReviewNote(...args),
}))

// Stage-3 providers: concept / evolution / review / pipeline.
const liveGetConceptView = vi.fn()
const demoGetConceptView = vi.fn()
const liveGetEvolutionView = vi.fn()
const demoGetEvolutionView = vi.fn()
const liveGetReviewView = vi.fn()
const demoGetReviewView = vi.fn()
const liveListPendingUrls = vi.fn()
const demoListPendingUrls = vi.fn()
const liveListGraphTasks = vi.fn()
const demoListGraphTasks = vi.fn()
const liveGetLlmMode = vi.fn()
const demoGetLlmMode = vi.fn()

vi.mock('../providers/live/conceptProvider', () => ({
  getConceptView: (...a) => liveGetConceptView(...a),
}))
vi.mock('../providers/demo/conceptProvider', () => ({
  getConceptView: (...a) => demoGetConceptView(...a),
}))
vi.mock('../providers/live/evolutionProvider', () => ({
  getEvolutionView: (...a) => liveGetEvolutionView(...a),
}))
vi.mock('../providers/demo/evolutionProvider', () => ({
  getEvolutionView: (...a) => demoGetEvolutionView(...a),
}))
vi.mock('../providers/live/reviewProvider', () => ({
  getReviewView: (...a) => liveGetReviewView(...a),
}))
vi.mock('../providers/demo/reviewProvider', () => ({
  getReviewView: (...a) => demoGetReviewView(...a),
}))
vi.mock('../providers/live/pipelineProvider', () => ({
  listAutoPendingUrls: (...a) => liveListPendingUrls(...a),
  listGraphTasks: (...a) => liveListGraphTasks(...a),
  getLlmMode: (...a) => liveGetLlmMode(...a),
}))
vi.mock('../providers/demo/pipelineProvider', () => ({
  listAutoPendingUrls: (...a) => demoListPendingUrls(...a),
  listGraphTasks: (...a) => demoListGraphTasks(...a),
  getLlmMode: (...a) => demoGetLlmMode(...a),
}))

import * as dataClient from '../dataClient'
import { setMode } from '../../runtime/appMode'

describe('dataClient', () => {
  beforeEach(() => {
    liveGetOverview.mockReset().mockResolvedValue({ data: { from: 'live' } })
    demoGetOverview.mockReset().mockResolvedValue({ data: { from: 'demo' } })
    liveGetProjectWorkbench.mockReset().mockResolvedValue({ project: { source: 'live' } })
    demoGetProjectWorkbench.mockReset().mockResolvedValue({ project: { source: 'demo' } })
    liveListResearchProjects.mockReset().mockResolvedValue({ data: { source: 'live-research' } })
    demoListResearchProjects.mockReset().mockResolvedValue({ data: { source: 'demo-research' } })
    liveCreateResearchProject.mockReset().mockResolvedValue({ data: { id: 'rp_live' } })
    demoCreateResearchProject.mockReset().mockRejectedValue(new Error('readonly'))
    liveGetLocalEvidencePack.mockReset().mockResolvedValue({ data: { src: 'live-pack' } })
    demoGetLocalEvidencePack.mockReset().mockResolvedValue({ data: { src: 'demo-pack' } })
    liveSearchLocalEvidencePack.mockReset().mockResolvedValue({ data: { src: 'live-search' } })
    demoSearchLocalEvidencePack.mockReset().mockResolvedValue({ data: { src: 'demo-search' } })
    liveUpdateLocalEvidenceCandidate.mockReset().mockResolvedValue({ data: { src: 'live-review' } })
    demoUpdateLocalEvidenceCandidate.mockReset().mockResolvedValue({ data: { src: 'demo-review' } })
    liveListResearchRuns.mockReset().mockResolvedValue({ data: { src: 'live-runs' } })
    demoListResearchRuns.mockReset().mockResolvedValue({ data: { src: 'demo-runs' } })
    liveListConsultationLogs.mockReset().mockResolvedValue({ data: { src: 'live-consults' } })
    demoListConsultationLogs.mockReset().mockResolvedValue({ data: { src: 'demo-consults' } })
    liveListExternalResearchPacks.mockReset().mockResolvedValue({ data: { src: 'live-packs' } })
    demoListExternalResearchPacks.mockReset().mockResolvedValue({ data: { src: 'demo-packs' } })
    liveUpdateExternalResearchCandidate.mockReset().mockResolvedValue({ data: { src: 'live-external-review' } })
    demoUpdateExternalResearchCandidate.mockReset().mockResolvedValue({ data: { src: 'demo-external-review' } })
    liveListEvidenceMatrixRows.mockReset().mockResolvedValue({ data: { src: 'live-matrix' } })
    demoListEvidenceMatrixRows.mockReset().mockResolvedValue({ data: { src: 'demo-matrix' } })
    liveCreateEvidenceMatrixRow.mockReset().mockResolvedValue({ data: { src: 'live-matrix-create' } })
    demoCreateEvidenceMatrixRow.mockReset().mockRejectedValue(new Error('readonly'))
    liveUpdateEvidenceMatrixRow.mockReset().mockResolvedValue({ data: { src: 'live-matrix-update' } })
    demoUpdateEvidenceMatrixRow.mockReset().mockResolvedValue({ data: { src: 'demo-matrix-update' } })
    liveListInsightCards.mockReset().mockResolvedValue({ data: { src: 'live-insights' } })
    demoListInsightCards.mockReset().mockResolvedValue({ data: { src: 'demo-insights' } })
    liveCreateInsightCard.mockReset().mockResolvedValue({ data: { src: 'live-insight-create' } })
    demoCreateInsightCard.mockReset().mockRejectedValue(new Error('readonly'))
    liveUpdateInsightCard.mockReset().mockResolvedValue({ data: { src: 'live-insight-update' } })
    demoUpdateInsightCard.mockReset().mockResolvedValue({ data: { src: 'demo-insight-update' } })
    liveListArtifactDrafts.mockReset().mockResolvedValue({ data: { src: 'live-artifacts' } })
    demoListArtifactDrafts.mockReset().mockResolvedValue({ data: { src: 'demo-artifacts' } })
    liveCreateArtifactDraft.mockReset().mockResolvedValue({ data: { src: 'live-artifact-create' } })
    demoCreateArtifactDraft.mockReset().mockRejectedValue(new Error('readonly'))
    liveUpdateArtifactDraft.mockReset().mockResolvedValue({ data: { src: 'live-artifact-update' } })
    demoUpdateArtifactDraft.mockReset().mockResolvedValue({ data: { src: 'demo-artifact-update' } })
    liveGetTraceabilityMap.mockReset().mockResolvedValue({ data: { src: 'live-traceability' } })
    demoGetTraceabilityMap.mockReset().mockResolvedValue({ data: { src: 'demo-traceability' } })
    liveListGovernanceReviews.mockReset().mockResolvedValue({ data: { src: 'live-governance-list' } })
    demoListGovernanceReviews.mockReset().mockResolvedValue({ data: { src: 'demo-governance-list' } })
    liveCreateGovernanceReview.mockReset().mockResolvedValue({ data: { src: 'live-governance-create' } })
    demoCreateGovernanceReview.mockReset().mockRejectedValue(new Error('readonly'))
    liveGetGovernanceReview.mockReset().mockResolvedValue({ data: { src: 'live-governance-detail' } })
    demoGetGovernanceReview.mockReset().mockResolvedValue({ data: { src: 'demo-governance-detail' } })
    liveUpdateGovernanceReview.mockReset().mockResolvedValue({ data: { src: 'live-governance-update' } })
    demoUpdateGovernanceReview.mockReset().mockResolvedValue({ data: { src: 'demo-governance-update' } })
    liveListReviewHistory.mockReset().mockResolvedValue({ data: { src: 'live-review-history' } })
    demoListReviewHistory.mockReset().mockResolvedValue({ data: { src: 'demo-review-history' } })
    liveGetAssetReviewHistory.mockReset().mockResolvedValue({ data: { src: 'live-asset-review-history' } })
    demoGetAssetReviewHistory.mockReset().mockResolvedValue({ data: { src: 'demo-asset-review-history' } })
    liveGetReviewHistoryEntry.mockReset().mockResolvedValue({ data: { src: 'live-review-history-entry' } })
    demoGetReviewHistoryEntry.mockReset().mockResolvedValue({ data: { src: 'demo-review-history-entry' } })
    liveCreateReviewHistoryNote.mockReset().mockResolvedValue({ data: { src: 'live-review-history-note' } })
    demoCreateReviewHistoryNote.mockReset().mockResolvedValue({ data: { src: 'demo-review-history-note' } })
    liveListResearchSnapshots.mockReset().mockResolvedValue({ data: { src: 'live-snapshots' } })
    demoListResearchSnapshots.mockReset().mockResolvedValue({ data: { src: 'demo-snapshots' } })
    liveCreateResearchSnapshot.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-create' } })
    demoCreateResearchSnapshot.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-create' } })
    liveGetResearchSnapshot.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-detail' } })
    demoGetResearchSnapshot.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-detail' } })
    liveDiffResearchSnapshot.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-diff' } })
    demoDiffResearchSnapshot.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-diff' } })
    liveListSnapshotReviewNotes.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-notes' } })
    demoListSnapshotReviewNotes.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-notes' } })
    liveCreateSnapshotReviewNote.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-note-create' } })
    demoCreateSnapshotReviewNote.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-note-create' } })
    liveGetSnapshotReviewNote.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-note-detail' } })
    demoGetSnapshotReviewNote.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-note-detail' } })
    liveUpdateSnapshotReviewNote.mockReset().mockResolvedValue({ data: { src: 'live-snapshot-note-update' } })
    demoUpdateSnapshotReviewNote.mockReset().mockResolvedValue({ data: { src: 'demo-snapshot-note-update' } })
    window.localStorage.clear()
    setMode('live')
  })

  it('routes getOverview to the live provider in live mode', async () => {
    setMode('live')
    const res = await dataClient.getOverview()
    expect(liveGetOverview).toHaveBeenCalledTimes(1)
    expect(demoGetOverview).not.toHaveBeenCalled()
    expect(res.data.from).toBe('live')
  })

  it('routes getOverview to the demo provider in demo mode', async () => {
    setMode('demo')
    const res = await dataClient.getOverview()
    expect(demoGetOverview).toHaveBeenCalledTimes(1)
    expect(liveGetOverview).not.toHaveBeenCalled()
    expect(res.data.from).toBe('demo')
  })

  it('routes getProjectWorkbench based on current mode', async () => {
    setMode('live')
    await dataClient.getProjectWorkbench('p1')
    expect(liveGetProjectWorkbench).toHaveBeenCalledWith('p1')

    setMode('demo')
    await dataClient.getProjectWorkbench('p2')
    expect(demoGetProjectWorkbench).toHaveBeenCalledWith('p2')
  })

  it('routes research project methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.listResearchProjects()).data.source).toBe('live-research')
    await dataClient.createResearchProject({ title: 'Strategy' })
    expect(liveCreateResearchProject).toHaveBeenCalledWith({ title: 'Strategy' })

    setMode('demo')
    expect((await dataClient.listResearchProjects()).data.source).toBe('demo-research')
    await expect(dataClient.createResearchProject({ title: 'Strategy' })).rejects.toThrow('readonly')
  })

  it('routes local evidence pack methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.getLocalEvidencePack('rp_1')).data.src).toBe('live-pack')
    expect((await dataClient.searchLocalEvidencePack('rp_1', { limit: 5 })).data.src).toBe('live-search')
    expect((
      await dataClient.updateLocalEvidenceCandidate('rp_1', 'ev_1', { status: 'accepted' })
    ).data.src).toBe('live-review')
    expect(liveSearchLocalEvidencePack).toHaveBeenCalledWith('rp_1', { limit: 5 })
    expect(liveUpdateLocalEvidenceCandidate).toHaveBeenCalledWith('rp_1', 'ev_1', { status: 'accepted' })

    setMode('demo')
    expect((await dataClient.getLocalEvidencePack('rp_1')).data.src).toBe('demo-pack')
    expect((await dataClient.searchLocalEvidencePack('rp_1', { limit: 5 })).data.src).toBe('demo-search')
    expect((
      await dataClient.updateLocalEvidenceCandidate('rp_1', 'ev_1', { status: 'accepted' })
    ).data.src).toBe('demo-review')
  })

  it('routes Codex writeback methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.listResearchRuns('rp_1')).data.src).toBe('live-runs')
    expect((await dataClient.listConsultationLogs('rp_1')).data.src).toBe('live-consults')
    expect((await dataClient.listExternalResearchPacks('rp_1')).data.src).toBe('live-packs')
    expect((
      await dataClient.updateExternalResearchCandidate('rp_1', 'erp_1', 'ec_1', { review_status: 'accepted' })
    ).data.src).toBe('live-external-review')
    expect(liveUpdateExternalResearchCandidate).toHaveBeenCalledWith(
      'rp_1',
      'erp_1',
      'ec_1',
      { review_status: 'accepted' },
    )

    setMode('demo')
    expect((await dataClient.listResearchRuns('rp_1')).data.src).toBe('demo-runs')
    expect((await dataClient.listConsultationLogs('rp_1')).data.src).toBe('demo-consults')
    expect((await dataClient.listExternalResearchPacks('rp_1')).data.src).toBe('demo-packs')
    expect((
      await dataClient.updateExternalResearchCandidate('rp_1', 'erp_1', 'ec_1', { review_status: 'accepted' })
    ).data.src).toBe('demo-external-review')
  })

  it('routes strategic synthesis methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.listEvidenceMatrixRows('rp_1')).data.src).toBe('live-matrix')
    expect((await dataClient.createEvidenceMatrixRow('rp_1', { claim: 'c' })).data.src).toBe('live-matrix-create')
    expect((
      await dataClient.updateEvidenceMatrixRow('rp_1', 'emr_1', { status: 'reviewed' })
    ).data.src).toBe('live-matrix-update')
    expect((await dataClient.listInsightCards('rp_1')).data.src).toBe('live-insights')
    expect((await dataClient.createInsightCard('rp_1', { title: 'i' })).data.src).toBe('live-insight-create')
    expect((await dataClient.updateInsightCard('rp_1', 'ic_1', { status: 'accepted' })).data.src).toBe('live-insight-update')
    expect((await dataClient.listArtifactDrafts('rp_1')).data.src).toBe('live-artifacts')
    expect((await dataClient.createArtifactDraft('rp_1', { title: 'a' })).data.src).toBe('live-artifact-create')
    expect((
      await dataClient.updateArtifactDraft('rp_1', 'ad_1', { material_readiness: 'presentation_ready' })
    ).data.src).toBe('live-artifact-update')

    setMode('demo')
    expect((await dataClient.listEvidenceMatrixRows('rp_1')).data.src).toBe('demo-matrix')
    await expect(dataClient.createEvidenceMatrixRow('rp_1', { claim: 'c' })).rejects.toThrow('readonly')
    expect((
      await dataClient.updateEvidenceMatrixRow('rp_1', 'emr_1', { status: 'reviewed' })
    ).data.src).toBe('demo-matrix-update')
    expect((await dataClient.listInsightCards('rp_1')).data.src).toBe('demo-insights')
    await expect(dataClient.createInsightCard('rp_1', { title: 'i' })).rejects.toThrow('readonly')
    expect((await dataClient.updateInsightCard('rp_1', 'ic_1', { status: 'accepted' })).data.src).toBe('demo-insight-update')
    expect((await dataClient.listArtifactDrafts('rp_1')).data.src).toBe('demo-artifacts')
    await expect(dataClient.createArtifactDraft('rp_1', { title: 'a' })).rejects.toThrow('readonly')
    expect((
      await dataClient.updateArtifactDraft('rp_1', 'ad_1', { material_readiness: 'presentation_ready' })
    ).data.src).toBe('demo-artifact-update')
  })

  it('routes traceability map reads based on current mode', async () => {
    setMode('live')
    expect((await dataClient.getTraceabilityMap('rp_1', { asset_type: 'insight_card' })).data.src).toBe('live-traceability')
    expect(liveGetTraceabilityMap).toHaveBeenCalledWith('rp_1', { asset_type: 'insight_card' })

    setMode('demo')
    expect((await dataClient.getTraceabilityMap('rp_1', { issue_severity: 'warning' })).data.src).toBe('demo-traceability')
    expect(demoGetTraceabilityMap).toHaveBeenCalledWith('rp_1', { issue_severity: 'warning' })
  })

  it('routes governance review methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.listGovernanceReviews('rp_1')).data.src).toBe('live-governance-list')
    expect((await dataClient.createGovernanceReview('rp_1', { title: 'P9' })).data.src).toBe('live-governance-create')
    expect((await dataClient.getGovernanceReview('rp_1', 'gr_1')).data.src).toBe('live-governance-detail')
    expect((await dataClient.updateGovernanceReview('rp_1', 'gr_1', { status: 'in_review' })).data.src).toBe('live-governance-update')

    setMode('demo')
    expect((await dataClient.listGovernanceReviews('rp_1')).data.src).toBe('demo-governance-list')
    await expect(dataClient.createGovernanceReview('rp_1', { title: 'P9' })).rejects.toThrow('readonly')
    expect((await dataClient.getGovernanceReview('rp_1', 'gr_1')).data.src).toBe('demo-governance-detail')
    expect((await dataClient.updateGovernanceReview('rp_1', 'gr_1', { status: 'in_review' })).data.src).toBe('demo-governance-update')
  })

  it('routes review history methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.listReviewHistory('rp_1', { limit: 10 })).data.src).toBe('live-review-history')
    expect((await dataClient.getAssetReviewHistory('rp_1', 'governance_review', 'gr_1')).data.src).toBe('live-asset-review-history')
    expect((await dataClient.getReviewHistoryEntry('rp_1', 'rhe_1')).data.src).toBe('live-review-history-entry')
    expect((await dataClient.createReviewHistoryNote('rp_1', { asset_type: 'governance_review' })).data.src).toBe('live-review-history-note')

    setMode('demo')
    expect((await dataClient.listReviewHistory('rp_1', { event_type: 'status_changed' })).data.src).toBe('demo-review-history')
    expect((await dataClient.getAssetReviewHistory('rp_1', 'leadership_briefing', 'lb_1')).data.src).toBe('demo-asset-review-history')
    expect((await dataClient.getReviewHistoryEntry('rp_1', 'rhe_1')).data.src).toBe('demo-review-history-entry')
    expect((await dataClient.createReviewHistoryNote('rp_1', { asset_type: 'governance_review' })).data.src).toBe('demo-review-history-note')
  })

  it('routes research snapshot methods based on current mode', async () => {
    setMode('live')
    expect((await dataClient.listResearchSnapshots('rp_1')).data.src).toBe('live-snapshots')
    expect((await dataClient.createResearchSnapshot('rp_1', { title: 'P11' })).data.src).toBe('live-snapshot-create')
    expect((await dataClient.getResearchSnapshot('rp_1', 'rs_1')).data.src).toBe('live-snapshot-detail')
    expect((await dataClient.diffResearchSnapshot('rp_1', 'rs_1')).data.src).toBe('live-snapshot-diff')
    expect((await dataClient.listSnapshotReviewNotes('rp_1', 'rs_1')).data.src).toBe('live-snapshot-notes')
    expect((await dataClient.createSnapshotReviewNote('rp_1', 'rs_1', { note: 'n' })).data.src).toBe('live-snapshot-note-create')
    expect((await dataClient.getSnapshotReviewNote('rp_1', 'rs_1', 'srn_1')).data.src).toBe('live-snapshot-note-detail')
    expect((await dataClient.updateSnapshotReviewNote('rp_1', 'rs_1', 'srn_1', { status: 'acknowledged' })).data.src).toBe('live-snapshot-note-update')
    expect(liveUpdateSnapshotReviewNote).toHaveBeenCalledWith('rp_1', 'rs_1', 'srn_1', { status: 'acknowledged' })

    setMode('demo')
    expect((await dataClient.listResearchSnapshots('rp_1')).data.src).toBe('demo-snapshots')
    expect((await dataClient.createResearchSnapshot('rp_1', { title: 'P11' })).data.src).toBe('demo-snapshot-create')
    expect((await dataClient.getResearchSnapshot('rp_1', 'rs_1')).data.src).toBe('demo-snapshot-detail')
    expect((await dataClient.diffResearchSnapshot('rp_1', 'rs_1')).data.src).toBe('demo-snapshot-diff')
    expect((await dataClient.listSnapshotReviewNotes('rp_1', 'rs_1')).data.src).toBe('demo-snapshot-notes')
    expect((await dataClient.createSnapshotReviewNote('rp_1', 'rs_1', { note: 'n' })).data.src).toBe('demo-snapshot-note-create')
    expect((await dataClient.getSnapshotReviewNote('rp_1', 'rs_1', 'srn_1')).data.src).toBe('demo-snapshot-note-detail')
    expect((await dataClient.updateSnapshotReviewNote('rp_1', 'rs_1', 'srn_1', { status: 'resolved' })).data.src).toBe('demo-snapshot-note-update')
    expect(demoUpdateSnapshotReviewNote).toHaveBeenCalledWith('rp_1', 'rs_1', 'srn_1', { status: 'resolved' })
  })

  describe('stage-3 dispatch', () => {
    beforeEach(() => {
      liveGetConceptView.mockReset().mockResolvedValue({ src: 'live-concept' })
      demoGetConceptView.mockReset().mockResolvedValue({ src: 'demo-concept' })
      liveGetEvolutionView.mockReset().mockResolvedValue({ src: 'live-evolution' })
      demoGetEvolutionView.mockReset().mockResolvedValue({ src: 'demo-evolution' })
      liveGetReviewView.mockReset().mockResolvedValue({ src: 'live-review' })
      demoGetReviewView.mockReset().mockResolvedValue({ src: 'demo-review' })
      liveListPendingUrls.mockReset().mockResolvedValue({ src: 'live-pending' })
      demoListPendingUrls.mockReset().mockResolvedValue({ src: 'demo-pending' })
      liveListGraphTasks.mockReset().mockResolvedValue({ src: 'live-tasks' })
      demoListGraphTasks.mockReset().mockResolvedValue({ src: 'demo-tasks' })
      liveGetLlmMode.mockReset().mockResolvedValue({ src: 'live-mode' })
      demoGetLlmMode.mockReset().mockResolvedValue({ src: 'demo-mode' })
    })

    it('getConceptView dispatches by mode', async () => {
      setMode('live')
      expect((await dataClient.getConceptView('p1')).src).toBe('live-concept')
      expect(liveGetConceptView).toHaveBeenCalledWith('p1')
      setMode('demo')
      expect((await dataClient.getConceptView('p2')).src).toBe('demo-concept')
      expect(demoGetConceptView).toHaveBeenCalledWith('p2')
    })

    it('getEvolutionView dispatches by mode', async () => {
      setMode('demo')
      expect((await dataClient.getEvolutionView('x')).src).toBe('demo-evolution')
      setMode('live')
      expect((await dataClient.getEvolutionView('y')).src).toBe('live-evolution')
    })

    it('getReviewView dispatches by mode', async () => {
      setMode('demo')
      expect((await dataClient.getReviewView('x')).src).toBe('demo-review')
      setMode('live')
      expect((await dataClient.getReviewView('y')).src).toBe('live-review')
    })

    it('pipeline methods dispatch by mode', async () => {
      setMode('demo')
      expect((await dataClient.listAutoPendingUrls()).src).toBe('demo-pending')
      expect((await dataClient.listGraphTasks()).src).toBe('demo-tasks')
      expect((await dataClient.getLlmMode()).src).toBe('demo-mode')
      setMode('live')
      expect((await dataClient.listAutoPendingUrls()).src).toBe('live-pending')
      expect((await dataClient.listGraphTasks()).src).toBe('live-tasks')
      expect((await dataClient.getLlmMode()).src).toBe('live-mode')
    })
  })
})
