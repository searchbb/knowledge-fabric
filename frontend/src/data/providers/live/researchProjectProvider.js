import service, {
  addArtifactPackFileRef as addArtifactPackFileRefRequest,
  addArtifactPackItem as addArtifactPackItemRequest,
  addArtifactPackPage as addArtifactPackPageRequest,
  addArtifactPackReviewRound as addArtifactPackReviewRoundRequest,
  createLeadershipBriefing as createLeadershipBriefingRequest,
  createLeadershipDecisionRecord as createLeadershipDecisionRecordRequest,
  createArtifactPack as createArtifactPackRequest,
  createArtifactDraft as createArtifactDraftRequest,
  createEvidenceMatrixRow as createEvidenceMatrixRowRequest,
  createInsightCard as createInsightCardRequest,
  createResearchProject as createResearchProjectRequest,
  createStrategicOption as createStrategicOptionRequest,
  createValidationPlan as createValidationPlanRequest,
  getLocalEvidencePack as getLocalEvidencePackRequest,
  getLeadershipBriefing as getLeadershipBriefingRequest,
  getGovernanceReview as getGovernanceReviewRequest,
  getAssetReviewHistory as getAssetReviewHistoryRequest,
  getReviewHistoryEntry as getReviewHistoryEntryRequest,
  getTraceabilityMap as getTraceabilityMapRequest,
  getResearchProject as getResearchProjectRequest,
  listArtifactPacks as listArtifactPacksRequest,
  listArtifactDrafts as listArtifactDraftsRequest,
  listConsultationLogs as listConsultationLogsRequest,
  listEvidenceMatrixRows as listEvidenceMatrixRowsRequest,
  listExternalResearchPacks as listExternalResearchPacksRequest,
  listInsightCards as listInsightCardsRequest,
  listLeadershipBriefings as listLeadershipBriefingsRequest,
  listGovernanceReviews as listGovernanceReviewsRequest,
  listReviewHistory as listReviewHistoryRequest,
  listLeadershipDecisionRecords as listLeadershipDecisionRecordsRequest,
  listResearchProjects as listResearchProjectsRequest,
  listResearchRuns as listResearchRunsRequest,
  listStrategicOptions as listStrategicOptionsRequest,
  listValidationPlans as listValidationPlansRequest,
  searchLocalEvidencePack as searchLocalEvidencePackRequest,
  updateLeadershipDecisionRecord as updateLeadershipDecisionRecordRequest,
  updateLeadershipBriefing as updateLeadershipBriefingRequest,
  updateGovernanceReview as updateGovernanceReviewRequest,
  updateArtifactDraft as updateArtifactDraftRequest,
  updateArtifactPack as updateArtifactPackRequest,
  updateEvidenceMatrixRow as updateEvidenceMatrixRowRequest,
  updateExternalResearchCandidate as updateExternalResearchCandidateRequest,
  updateInsightCard as updateInsightCardRequest,
  updateLocalEvidenceCandidate as updateLocalEvidenceCandidateRequest,
  updateResearchProject as updateResearchProjectRequest,
  updateStrategicOption as updateStrategicOptionRequest,
  updateValidationPlan as updateValidationPlanRequest,
  createGovernanceReview as createGovernanceReviewRequest,
  createReviewHistoryNote as createReviewHistoryNoteRequest,
  createResearchSnapshot as createResearchSnapshotRequest,
  createSnapshotReviewNote as createSnapshotReviewNoteRequest,
  diffResearchSnapshot as diffResearchSnapshotRequest,
  getResearchSnapshot as getResearchSnapshotRequest,
  getSnapshotReviewNote as getSnapshotReviewNoteRequest,
  listResearchSnapshots as listResearchSnapshotsRequest,
  listSnapshotReviewNotes as listSnapshotReviewNotesRequest,
  updateSnapshotReviewNote as updateSnapshotReviewNoteRequest,
} from '../../../api/index'

export function listResearchProjects() {
  return listResearchProjectsRequest()
}

export function createResearchProject(payload) {
  return createResearchProjectRequest(payload)
}

export function getResearchProject(projectId) {
  return getResearchProjectRequest(projectId)
}

export function updateResearchProject(projectId, payload) {
  return updateResearchProjectRequest(projectId, payload)
}

export function getLocalEvidencePack(projectId) {
  return getLocalEvidencePackRequest(projectId)
}

export function searchLocalEvidencePack(projectId, payload) {
  return searchLocalEvidencePackRequest(projectId, payload)
}

export function updateLocalEvidenceCandidate(projectId, evidenceId, payload) {
  return updateLocalEvidenceCandidateRequest(projectId, evidenceId, payload)
}

export function listResearchRuns(projectId) {
  return listResearchRunsRequest(projectId)
}

export function listConsultationLogs(projectId) {
  return listConsultationLogsRequest(projectId)
}

export function listExternalResearchPacks(projectId) {
  return listExternalResearchPacksRequest(projectId)
}

export function updateExternalResearchCandidate(projectId, packId, candidateId, payload) {
  return updateExternalResearchCandidateRequest(projectId, packId, candidateId, payload)
}

export function listEvidenceMatrixRows(projectId) {
  return listEvidenceMatrixRowsRequest(projectId)
}

export function createEvidenceMatrixRow(projectId, payload) {
  return createEvidenceMatrixRowRequest(projectId, payload)
}

export function updateEvidenceMatrixRow(projectId, rowId, payload) {
  return updateEvidenceMatrixRowRequest(projectId, rowId, payload)
}

export function listInsightCards(projectId) {
  return listInsightCardsRequest(projectId)
}

export function createInsightCard(projectId, payload) {
  return createInsightCardRequest(projectId, payload)
}

export function updateInsightCard(projectId, cardId, payload) {
  return updateInsightCardRequest(projectId, cardId, payload)
}

export function listArtifactDrafts(projectId) {
  return listArtifactDraftsRequest(projectId)
}

export function createArtifactDraft(projectId, payload) {
  return createArtifactDraftRequest(projectId, payload)
}

export function updateArtifactDraft(projectId, draftId, payload) {
  return updateArtifactDraftRequest(projectId, draftId, payload)
}

export function listArtifactPacks(projectId) {
  return listArtifactPacksRequest(projectId)
}

export function createArtifactPack(projectId, payload) {
  return createArtifactPackRequest(projectId, payload)
}

export function updateArtifactPack(projectId, packId, payload) {
  return updateArtifactPackRequest(projectId, packId, payload)
}

export function addArtifactPackItem(projectId, packId, payload) {
  return addArtifactPackItemRequest(projectId, packId, payload)
}

export function addArtifactPackPage(projectId, packId, payload) {
  return addArtifactPackPageRequest(projectId, packId, payload)
}

export function addArtifactPackFileRef(projectId, packId, payload) {
  return addArtifactPackFileRefRequest(projectId, packId, payload)
}

export function addArtifactPackReviewRound(projectId, packId, payload) {
  return addArtifactPackReviewRoundRequest(projectId, packId, payload)
}

export function listStrategicOptions(projectId) {
  return listStrategicOptionsRequest(projectId)
}

export function createStrategicOption(projectId, payload) {
  return createStrategicOptionRequest(projectId, payload)
}

export function updateStrategicOption(projectId, optionId, payload) {
  return updateStrategicOptionRequest(projectId, optionId, payload)
}

export function listValidationPlans(projectId) {
  return listValidationPlansRequest(projectId)
}

export function createValidationPlan(projectId, payload) {
  return createValidationPlanRequest(projectId, payload)
}

export function updateValidationPlan(projectId, planId, payload) {
  return updateValidationPlanRequest(projectId, planId, payload)
}

export function listLeadershipDecisionRecords(projectId) {
  return listLeadershipDecisionRecordsRequest(projectId)
}

export function createLeadershipDecisionRecord(projectId, payload) {
  return createLeadershipDecisionRecordRequest(projectId, payload)
}

export function updateLeadershipDecisionRecord(projectId, decisionId, payload) {
  return updateLeadershipDecisionRecordRequest(projectId, decisionId, payload)
}

export function listLeadershipBriefings(projectId) {
  return listLeadershipBriefingsRequest(projectId)
}

export function createLeadershipBriefing(projectId, payload) {
  return createLeadershipBriefingRequest(projectId, payload)
}

export function getLeadershipBriefing(projectId, briefingId) {
  return getLeadershipBriefingRequest(projectId, briefingId)
}

export function updateLeadershipBriefing(projectId, briefingId, payload) {
  return updateLeadershipBriefingRequest(projectId, briefingId, payload)
}

export function getTraceabilityMap(projectId, params = {}) {
  return getTraceabilityMapRequest(projectId, params)
}

export function listGovernanceReviews(projectId) {
  return listGovernanceReviewsRequest(projectId)
}

export function createGovernanceReview(projectId, payload) {
  return createGovernanceReviewRequest(projectId, payload)
}

export function getGovernanceReview(projectId, reviewId) {
  return getGovernanceReviewRequest(projectId, reviewId)
}

export function updateGovernanceReview(projectId, reviewId, payload) {
  return updateGovernanceReviewRequest(projectId, reviewId, payload)
}

export function listReviewHistory(projectId, params = {}) {
  return listReviewHistoryRequest(projectId, params)
}

export function getAssetReviewHistory(projectId, assetType, assetId, params = {}) {
  return getAssetReviewHistoryRequest(projectId, assetType, assetId, params)
}

export function getReviewHistoryEntry(projectId, historyEntryId) {
  return getReviewHistoryEntryRequest(projectId, historyEntryId)
}

export function createReviewHistoryNote(projectId, payload) {
  return createReviewHistoryNoteRequest(projectId, payload)
}

export function listResearchSnapshots(projectId) {
  return listResearchSnapshotsRequest(projectId)
}

export function createResearchSnapshot(projectId, payload) {
  return createResearchSnapshotRequest(projectId, payload)
}

export function getResearchSnapshot(projectId, snapshotId) {
  return getResearchSnapshotRequest(projectId, snapshotId)
}

export function diffResearchSnapshot(projectId, snapshotId) {
  return diffResearchSnapshotRequest(projectId, snapshotId)
}

export function listSnapshotReviewNotes(projectId, snapshotId) {
  return listSnapshotReviewNotesRequest(projectId, snapshotId)
}

export function createSnapshotReviewNote(projectId, snapshotId, payload) {
  return createSnapshotReviewNoteRequest(projectId, snapshotId, payload)
}

export function getSnapshotReviewNote(projectId, snapshotId, noteId) {
  return getSnapshotReviewNoteRequest(projectId, snapshotId, noteId)
}

export function updateSnapshotReviewNote(projectId, snapshotId, noteId, payload) {
  return updateSnapshotReviewNoteRequest(projectId, snapshotId, noteId, payload)
}

// Keep a direct service reference in this module so tests can assert this
// provider remains a thin live API boundary if named exports are refactored.
export const researchProjectService = service
