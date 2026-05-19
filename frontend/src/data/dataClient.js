// Public data-client surface.
//
// Pages (and stores) must import from here, NOT from ../api/... or
// ../services/api/... directly. That's the boundary that makes live/demo
// mode swapping possible without page-level conditionals.
//
// New data needs? Add a method here + a live provider + a demo provider.
// Keep the surface narrow and task-oriented — don't leak HTTP verbs or
// endpoint paths.

import { appMode, APP_MODES } from '../runtime/appMode'

import * as liveOverview from './providers/live/overviewProvider'
import * as liveWorkspace from './providers/live/workspaceProvider'
import * as liveRegistry from './providers/live/registryProvider'
import * as liveTheme from './providers/live/themeProvider'
import * as liveConcept from './providers/live/conceptProvider'
import * as liveEvolution from './providers/live/evolutionProvider'
import * as liveReview from './providers/live/reviewProvider'
import * as livePipeline from './providers/live/pipelineProvider'
import * as liveTopicCluster from './providers/live/topicClusterProvider'
import * as liveWikiIntake from './providers/live/wikiIntakeProvider'
import * as liveResearchProject from './providers/live/researchProjectProvider'

import * as demoOverview from './providers/demo/overviewProvider'
import * as demoWorkspace from './providers/demo/workspaceProvider'
import * as demoRegistry from './providers/demo/registryProvider'
import * as demoTheme from './providers/demo/themeProvider'
import * as demoConcept from './providers/demo/conceptProvider'
import * as demoEvolution from './providers/demo/evolutionProvider'
import * as demoReview from './providers/demo/reviewProvider'
import * as demoPipeline from './providers/demo/pipelineProvider'
import * as demoTopicCluster from './providers/demo/topicClusterProvider'
import * as demoWikiIntake from './providers/demo/wikiIntakeProvider'
import * as demoResearchProject from './providers/demo/researchProjectProvider'

function pick(liveImpl, demoImpl) {
  return appMode.value === APP_MODES.DEMO ? demoImpl : liveImpl
}

// ----- Overview --------------------------------------------------------
export function getOverview() {
  return pick(liveOverview, demoOverview).getOverview()
}

// ----- Workspace -------------------------------------------------------
export function getProjectWorkbench(projectId) {
  return pick(liveWorkspace, demoWorkspace).getProjectWorkbench(projectId)
}

// ----- Registry (and cross-relations shared with Relation pages) -------
export function listRegistryConcepts(conceptType) {
  return pick(liveRegistry, demoRegistry).listRegistryConcepts(conceptType)
}

export function getRegistryConcept(entryId) {
  return pick(liveRegistry, demoRegistry).getRegistryConcept(entryId)
}

export function getRegistryConceptGraph(entryId) {
  return pick(liveRegistry, demoRegistry).getRegistryConceptGraph(entryId)
}

export function listCrossRelations(params) {
  return pick(liveRegistry, demoRegistry).listCrossRelations(params)
}

export function getCrossRelation(relationId) {
  return pick(liveRegistry, demoRegistry).getCrossRelation(relationId)
}

export function getCrossRelationCounts(entryIds) {
  return pick(liveRegistry, demoRegistry).getCrossRelationCounts(entryIds)
}

// ----- Theme -----------------------------------------------------------
export function listGlobalThemes() {
  return pick(liveTheme, demoTheme).listGlobalThemes()
}

export function listThemesViaRegistryTab() {
  return pick(liveTheme, demoTheme).listThemesViaRegistryTab()
}

export function getThemeHubView(themeId) {
  return pick(liveTheme, demoTheme).getThemeHubView(themeId)
}

export function getThemePanorama(themeId) {
  return pick(liveTheme, demoTheme).getThemePanorama(themeId)
}

export function getOrphans(limit) {
  return pick(liveTheme, demoTheme).getOrphans(limit)
}

// ----- Topic Clusters (strategic aggregation layer) -------------------
export function listTopicClusters(options) {
  return pick(liveTopicCluster, demoTopicCluster).listTopicClusters(options)
}

export function listTopicClustersWithAggregation() {
  return pick(liveTopicCluster, demoTopicCluster).listTopicClusters({ includeCounts: true })
}

export function createTopicCluster(payload) {
  return pick(liveTopicCluster, demoTopicCluster).createTopicCluster(payload)
}

export function getTopicCluster(clusterId, options) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicCluster(clusterId, options)
}

export function getTopicClusterWithArticles(clusterId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicCluster(clusterId, { includeCounts: true, includeArticles: true })
}

export function getTopicClusterAssetIndex(clusterId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterAssetIndex(clusterId)
}

export function getTopicClusterPromotionBasket(clusterId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterPromotionBasket(clusterId)
}

export function getTopicClusterPromotionChanges(clusterId, params) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterPromotionChanges(clusterId, params)
}

export function getTopicClusterArticleProcessingReview(clusterId, articleId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterArticleProcessingReview(clusterId, articleId)
}

export function applyArticleProcessingBatchAction(clusterId, articleId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).applyArticleProcessingBatchAction(clusterId, articleId, payload)
}

export function createTopicClusterMaterialSlice(clusterId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).createTopicClusterMaterialSlice(clusterId, payload)
}

export function applyLeadPromotionAction(clusterId, promotionId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).applyLeadPromotionAction(clusterId, promotionId, payload)
}

export function createTopicClusterRelationCandidate(clusterId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).createTopicClusterRelationCandidate(clusterId, payload)
}

export function applyRelationCandidateAction(clusterId, relationCandidateId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).applyRelationCandidateAction(clusterId, relationCandidateId, payload)
}

export function getLeadPromotionTrace(clusterId, promotionId) {
  return pick(liveTopicCluster, demoTopicCluster).getLeadPromotionTrace(clusterId, promotionId)
}

export function updateTopicCluster(clusterId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).updateTopicCluster(clusterId, payload)
}

export function getTopicClusterLinks(clusterId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterLinks(clusterId)
}

export function createTopicClusterLink(clusterId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).createTopicClusterLink(clusterId, payload)
}

export function updateTopicClusterLink(linkId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).updateTopicClusterLink(linkId, payload)
}

export function deleteTopicClusterLink(linkId) {
  return pick(liveTopicCluster, demoTopicCluster).deleteTopicClusterLink(linkId)
}

export function createTopicClusterRefreshRequest(payload) {
  return pick(liveTopicCluster, demoTopicCluster).createTopicClusterRefreshRequest(payload)
}

export function listTopicClusterRefreshRequests() {
  return pick(liveTopicCluster, demoTopicCluster).listTopicClusterRefreshRequests()
}

export function getTopicClusterRefreshRequest(requestId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterRefreshRequest(requestId)
}

export function listTopicClusterProposals() {
  return pick(liveTopicCluster, demoTopicCluster).listTopicClusterProposals()
}

export function getTopicClusterProposal(proposalId) {
  return pick(liveTopicCluster, demoTopicCluster).getTopicClusterProposal(proposalId)
}

export function applyTopicClusterProposal(proposalId, payload) {
  return pick(liveTopicCluster, demoTopicCluster).applyTopicClusterProposal(proposalId, payload)
}

export function findTopicClustersByTarget(targetType, targetId) {
  return pick(liveTopicCluster, demoTopicCluster).findTopicClustersByTarget(targetType, targetId)
}

// ----- Wiki Intake (Clippings -> llm-wiki staging) --------------------
export function listWikiIntakeCandidates(params) {
  return pick(liveWikiIntake, demoWikiIntake).listWikiIntakeCandidates(params)
}

export function listWikiTopics(options) {
  return pick(liveWikiIntake, demoWikiIntake).listWikiTopics(options)
}

export function getWikiTopicArticles(topicId) {
  return pick(liveWikiIntake, demoWikiIntake).getWikiTopicArticles(topicId)
}

export function getWikiTopicClusterCoverage(topicId) {
  return pick(liveWikiIntake, demoWikiIntake).getWikiTopicClusterCoverage(topicId)
}

export function setWikiTopicClusterCoverageOverride(topicId, payload) {
  return pick(liveWikiIntake, demoWikiIntake).setWikiTopicClusterCoverageOverride(topicId, payload)
}

export function linkWikiTopicToCluster(topicId, payload) {
  return pick(liveWikiIntake, demoWikiIntake).linkWikiTopicToCluster(topicId, payload)
}

export function requestWikiTopicClusterProposal(topicId, payload) {
  return pick(liveWikiIntake, demoWikiIntake).requestWikiTopicClusterProposal(topicId, payload)
}

export function getWikiIntakeCandidate(candidateId) {
  return pick(liveWikiIntake, demoWikiIntake).getWikiIntakeCandidate(candidateId)
}

export function getWikiIntakeProcessedResult(candidateId) {
  return pick(liveWikiIntake, demoWikiIntake).getWikiIntakeProcessedResult(candidateId)
}

export function changeWikiIntakeCandidatePrimaryTopic(candidateId, payload) {
  return pick(liveWikiIntake, demoWikiIntake).changeWikiIntakeCandidatePrimaryTopic(candidateId, payload)
}

export function unlinkWikiIntakeCandidatePrimaryTopic(candidateId, payload) {
  return pick(liveWikiIntake, demoWikiIntake).unlinkWikiIntakeCandidatePrimaryTopic(candidateId, payload)
}

export function scanWikiIntake(payload) {
  return pick(liveWikiIntake, demoWikiIntake).scanWikiIntake(payload)
}

export function processNextWikiIntake(payload) {
  return pick(liveWikiIntake, demoWikiIntake).processNextWikiIntake(payload)
}

export function createWikiIntakeDecision(payload) {
  return pick(liveWikiIntake, demoWikiIntake).createWikiIntakeDecision(payload)
}

export function getWikiIntakeConfig() {
  return pick(liveWikiIntake, demoWikiIntake).getWikiIntakeConfig()
}

// ----- Concept (per-project candidate concepts view) ------------------
export function getConceptView(projectId) {
  return pick(liveConcept, demoConcept).getConceptView(projectId)
}

// ----- Evolution (per-project snapshot view) --------------------------
export function getEvolutionView(projectId) {
  return pick(liveEvolution, demoEvolution).getEvolutionView(projectId)
}

// ----- Review (per-project review queue) ------------------------------
export function getReviewView(projectId) {
  return pick(liveReview, demoReview).getReviewView(projectId)
}

// ----- AutoPipeline (global) ------------------------------------------
export function listAutoPendingUrls() {
  return pick(livePipeline, demoPipeline).listAutoPendingUrls()
}

export function listGraphTasks() {
  return pick(livePipeline, demoPipeline).listGraphTasks()
}

export function getLlmMode() {
  return pick(livePipeline, demoPipeline).getLlmMode()
}

// ----- Research Projects (strategic research assets) ------------------
export function listResearchProjects() {
  return pick(liveResearchProject, demoResearchProject).listResearchProjects()
}

export function createResearchProject(payload) {
  return pick(liveResearchProject, demoResearchProject).createResearchProject(payload)
}

export function getResearchProject(projectId) {
  return pick(liveResearchProject, demoResearchProject).getResearchProject(projectId)
}

export function updateResearchProject(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateResearchProject(projectId, payload)
}

export function getLocalEvidencePack(projectId) {
  return pick(liveResearchProject, demoResearchProject).getLocalEvidencePack(projectId)
}

export function searchLocalEvidencePack(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).searchLocalEvidencePack(projectId, payload)
}

export function updateLocalEvidenceCandidate(projectId, evidenceId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateLocalEvidenceCandidate(
    projectId,
    evidenceId,
    payload,
  )
}

export function listResearchRuns(projectId) {
  return pick(liveResearchProject, demoResearchProject).listResearchRuns(projectId)
}

export function listConsultationLogs(projectId) {
  return pick(liveResearchProject, demoResearchProject).listConsultationLogs(projectId)
}

export function listExternalResearchPacks(projectId) {
  return pick(liveResearchProject, demoResearchProject).listExternalResearchPacks(projectId)
}

export function updateExternalResearchCandidate(projectId, packId, candidateId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateExternalResearchCandidate(
    projectId,
    packId,
    candidateId,
    payload,
  )
}

export function listEvidenceMatrixRows(projectId) {
  return pick(liveResearchProject, demoResearchProject).listEvidenceMatrixRows(projectId)
}

export function createEvidenceMatrixRow(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createEvidenceMatrixRow(projectId, payload)
}

export function updateEvidenceMatrixRow(projectId, rowId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateEvidenceMatrixRow(projectId, rowId, payload)
}

export function listInsightCards(projectId) {
  return pick(liveResearchProject, demoResearchProject).listInsightCards(projectId)
}

export function createInsightCard(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createInsightCard(projectId, payload)
}

export function updateInsightCard(projectId, cardId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateInsightCard(projectId, cardId, payload)
}

export function listArtifactDrafts(projectId) {
  return pick(liveResearchProject, demoResearchProject).listArtifactDrafts(projectId)
}

export function createArtifactDraft(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createArtifactDraft(projectId, payload)
}

export function updateArtifactDraft(projectId, draftId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateArtifactDraft(projectId, draftId, payload)
}

export function listArtifactPacks(projectId) {
  return pick(liveResearchProject, demoResearchProject).listArtifactPacks(projectId)
}

export function createArtifactPack(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createArtifactPack(projectId, payload)
}

export function updateArtifactPack(projectId, packId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateArtifactPack(projectId, packId, payload)
}

export function addArtifactPackItem(projectId, packId, payload) {
  return pick(liveResearchProject, demoResearchProject).addArtifactPackItem(projectId, packId, payload)
}

export function addArtifactPackPage(projectId, packId, payload) {
  return pick(liveResearchProject, demoResearchProject).addArtifactPackPage(projectId, packId, payload)
}

export function addArtifactPackFileRef(projectId, packId, payload) {
  return pick(liveResearchProject, demoResearchProject).addArtifactPackFileRef(projectId, packId, payload)
}

export function addArtifactPackReviewRound(projectId, packId, payload) {
  return pick(liveResearchProject, demoResearchProject).addArtifactPackReviewRound(projectId, packId, payload)
}

export function listStrategicOptions(projectId) {
  return pick(liveResearchProject, demoResearchProject).listStrategicOptions(projectId)
}

export function createStrategicOption(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createStrategicOption(projectId, payload)
}

export function updateStrategicOption(projectId, optionId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateStrategicOption(projectId, optionId, payload)
}

export function listValidationPlans(projectId) {
  return pick(liveResearchProject, demoResearchProject).listValidationPlans(projectId)
}

export function createValidationPlan(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createValidationPlan(projectId, payload)
}

export function updateValidationPlan(projectId, planId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateValidationPlan(projectId, planId, payload)
}

export function listLeadershipDecisionRecords(projectId) {
  return pick(liveResearchProject, demoResearchProject).listLeadershipDecisionRecords(projectId)
}

export function createLeadershipDecisionRecord(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createLeadershipDecisionRecord(projectId, payload)
}

export function updateLeadershipDecisionRecord(projectId, decisionId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateLeadershipDecisionRecord(projectId, decisionId, payload)
}

export function listLeadershipBriefings(projectId) {
  return pick(liveResearchProject, demoResearchProject).listLeadershipBriefings(projectId)
}

export function createLeadershipBriefing(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createLeadershipBriefing(projectId, payload)
}

export function getLeadershipBriefing(projectId, briefingId) {
  return pick(liveResearchProject, demoResearchProject).getLeadershipBriefing(projectId, briefingId)
}

export function updateLeadershipBriefing(projectId, briefingId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateLeadershipBriefing(projectId, briefingId, payload)
}

export function getTraceabilityMap(projectId, params = {}) {
  return pick(liveResearchProject, demoResearchProject).getTraceabilityMap(projectId, params)
}

export function listGovernanceReviews(projectId) {
  return pick(liveResearchProject, demoResearchProject).listGovernanceReviews(projectId)
}

export function createGovernanceReview(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createGovernanceReview(projectId, payload)
}

export function getGovernanceReview(projectId, reviewId) {
  return pick(liveResearchProject, demoResearchProject).getGovernanceReview(projectId, reviewId)
}

export function updateGovernanceReview(projectId, reviewId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateGovernanceReview(projectId, reviewId, payload)
}

export function listReviewHistory(projectId, params = {}) {
  return pick(liveResearchProject, demoResearchProject).listReviewHistory(projectId, params)
}

export function getAssetReviewHistory(projectId, assetType, assetId, params = {}) {
  return pick(liveResearchProject, demoResearchProject).getAssetReviewHistory(projectId, assetType, assetId, params)
}

export function getReviewHistoryEntry(projectId, historyEntryId) {
  return pick(liveResearchProject, demoResearchProject).getReviewHistoryEntry(projectId, historyEntryId)
}

export function createReviewHistoryNote(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createReviewHistoryNote(projectId, payload)
}

export function listResearchSnapshots(projectId) {
  return pick(liveResearchProject, demoResearchProject).listResearchSnapshots(projectId)
}

export function createResearchSnapshot(projectId, payload) {
  return pick(liveResearchProject, demoResearchProject).createResearchSnapshot(projectId, payload)
}

export function getResearchSnapshot(projectId, snapshotId) {
  return pick(liveResearchProject, demoResearchProject).getResearchSnapshot(projectId, snapshotId)
}

export function diffResearchSnapshot(projectId, snapshotId) {
  return pick(liveResearchProject, demoResearchProject).diffResearchSnapshot(projectId, snapshotId)
}

export function listSnapshotReviewNotes(projectId, snapshotId) {
  return pick(liveResearchProject, demoResearchProject).listSnapshotReviewNotes(projectId, snapshotId)
}

export function createSnapshotReviewNote(projectId, snapshotId, payload) {
  return pick(liveResearchProject, demoResearchProject).createSnapshotReviewNote(projectId, snapshotId, payload)
}

export function getSnapshotReviewNote(projectId, snapshotId, noteId) {
  return pick(liveResearchProject, demoResearchProject).getSnapshotReviewNote(projectId, snapshotId, noteId)
}

export function updateSnapshotReviewNote(projectId, snapshotId, noteId, payload) {
  return pick(liveResearchProject, demoResearchProject).updateSnapshotReviewNote(projectId, snapshotId, noteId, payload)
}
