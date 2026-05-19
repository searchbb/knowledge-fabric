import {
  findTopicClustersByTarget as apiFindTopicClustersByTarget,
  createTopicCluster as apiCreateTopicCluster,
  createTopicClusterLink as apiCreateTopicClusterLink,
  createTopicClusterMaterialSlice as apiCreateTopicClusterMaterialSlice,
  createTopicClusterRelationCandidate as apiCreateTopicClusterRelationCandidate,
  createTopicClusterRefreshRequest as apiCreateTopicClusterRefreshRequest,
  deleteTopicClusterLink as apiDeleteTopicClusterLink,
  applyArticleProcessingBatchAction as apiApplyArticleProcessingBatchAction,
  applyLeadPromotionAction as apiApplyLeadPromotionAction,
  applyRelationCandidateAction as apiApplyRelationCandidateAction,
  applyTopicClusterProposal as apiApplyTopicClusterProposal,
  getLeadPromotionTrace as apiGetLeadPromotionTrace,
  getTopicClusterArticleProcessingReview as apiGetTopicClusterArticleProcessingReview,
  getTopicClusterProposal as apiGetTopicClusterProposal,
  getTopicClusterRefreshRequest as apiGetTopicClusterRefreshRequest,
  getTopicCluster as apiGetTopicCluster,
  getTopicClusterAssetIndex as apiGetTopicClusterAssetIndex,
  getTopicClusterLinks as apiGetTopicClusterLinks,
  getTopicClusterPromotionBasket as apiGetTopicClusterPromotionBasket,
  getTopicClusterPromotionChanges as apiGetTopicClusterPromotionChanges,
  listTopicClusterProposals as apiListTopicClusterProposals,
  listTopicClusterRefreshRequests as apiListTopicClusterRefreshRequests,
  listTopicClusters as apiListTopicClusters,
  updateTopicCluster as apiUpdateTopicCluster,
  updateTopicClusterLink as apiUpdateTopicClusterLink,
} from '../../../services/api/topicClustersApi'

export function listTopicClusters(options) {
  return apiListTopicClusters(options)
}

export function createTopicCluster(payload) {
  return apiCreateTopicCluster(payload)
}

export function getTopicCluster(clusterId, options) {
  return apiGetTopicCluster(clusterId, options)
}

export function getTopicClusterAssetIndex(clusterId) {
  return apiGetTopicClusterAssetIndex(clusterId)
}

export function getTopicClusterPromotionBasket(clusterId) {
  return apiGetTopicClusterPromotionBasket(clusterId)
}

export function getTopicClusterPromotionChanges(clusterId, params) {
  return apiGetTopicClusterPromotionChanges(clusterId, params)
}

export function getTopicClusterArticleProcessingReview(clusterId, articleId) {
  return apiGetTopicClusterArticleProcessingReview(clusterId, articleId)
}

export function applyArticleProcessingBatchAction(clusterId, articleId, payload) {
  return apiApplyArticleProcessingBatchAction(clusterId, articleId, payload)
}

export function createTopicClusterMaterialSlice(clusterId, payload) {
  return apiCreateTopicClusterMaterialSlice(clusterId, payload)
}

export function applyLeadPromotionAction(clusterId, promotionId, payload) {
  return apiApplyLeadPromotionAction(clusterId, promotionId, payload)
}

export function createTopicClusterRelationCandidate(clusterId, payload) {
  return apiCreateTopicClusterRelationCandidate(clusterId, payload)
}

export function applyRelationCandidateAction(clusterId, relationCandidateId, payload) {
  return apiApplyRelationCandidateAction(clusterId, relationCandidateId, payload)
}

export function getLeadPromotionTrace(clusterId, promotionId) {
  return apiGetLeadPromotionTrace(clusterId, promotionId)
}

export function updateTopicCluster(clusterId, payload) {
  return apiUpdateTopicCluster(clusterId, payload)
}

export function getTopicClusterLinks(clusterId) {
  return apiGetTopicClusterLinks(clusterId)
}

export function createTopicClusterLink(clusterId, payload) {
  return apiCreateTopicClusterLink(clusterId, payload)
}

export function updateTopicClusterLink(linkId, payload) {
  return apiUpdateTopicClusterLink(linkId, payload)
}

export function deleteTopicClusterLink(linkId) {
  return apiDeleteTopicClusterLink(linkId)
}

export function createTopicClusterRefreshRequest(payload) {
  return apiCreateTopicClusterRefreshRequest(payload)
}

export function listTopicClusterRefreshRequests() {
  return apiListTopicClusterRefreshRequests()
}

export function getTopicClusterRefreshRequest(requestId) {
  return apiGetTopicClusterRefreshRequest(requestId)
}

export function listTopicClusterProposals() {
  return apiListTopicClusterProposals()
}

export function getTopicClusterProposal(proposalId) {
  return apiGetTopicClusterProposal(proposalId)
}

export function applyTopicClusterProposal(proposalId, payload) {
  return apiApplyTopicClusterProposal(proposalId, payload)
}

export function findTopicClustersByTarget(targetType, targetId) {
  return apiFindTopicClustersByTarget(targetType, targetId)
}
