import service from '../../api/index'

function includeParams(options = {}) {
  return {
    ...(options.includeCounts ? { include_counts: '1' } : {}),
    ...(options.includeArticles ? { include_articles: '1' } : {}),
  }
}

export function listTopicClusters(options = {}) {
  return service({ url: '/api/topic-clusters', method: 'get', params: includeParams(options) })
}

export function createTopicCluster(payload) {
  return service({ url: '/api/topic-clusters', method: 'post', data: payload })
}

export function getTopicCluster(clusterId, options = {}) {
  return service({ url: `/api/topic-clusters/${clusterId}`, method: 'get', params: includeParams(options) })
}

export function getTopicClusterAssetIndex(clusterId) {
  return service({ url: `/api/topic-clusters/${clusterId}/asset-index`, method: 'get' })
}

export function getTopicClusterPromotionBasket(clusterId) {
  return service({ url: `/api/topic-clusters/${clusterId}/promotion-basket`, method: 'get' })
}

export function getTopicClusterPromotionChanges(clusterId, params = {}) {
  return service({ url: `/api/topic-clusters/${clusterId}/promotion-changes`, method: 'get', params })
}

export function getTopicClusterArticleProcessingReview(clusterId, articleId) {
  return service({ url: `/api/topic-clusters/${clusterId}/articles/${articleId}/processing-review`, method: 'get' })
}

export function applyArticleProcessingBatchAction(clusterId, articleId, payload) {
  return service({
    url: `/api/topic-clusters/${clusterId}/articles/${articleId}/processing-review/batch-actions`,
    method: 'post',
    data: payload,
  })
}

export function createTopicClusterMaterialSlice(clusterId, payload) {
  return service({ url: `/api/topic-clusters/${clusterId}/material-slices`, method: 'post', data: payload })
}

export function applyLeadPromotionAction(clusterId, promotionId, payload) {
  return service({
    url: `/api/topic-clusters/${clusterId}/lead-promotions/${promotionId}/actions`,
    method: 'post',
    data: payload,
  })
}

export function createTopicClusterRelationCandidate(clusterId, payload) {
  return service({ url: `/api/topic-clusters/${clusterId}/relation-candidates`, method: 'post', data: payload })
}

export function applyRelationCandidateAction(clusterId, relationCandidateId, payload) {
  return service({
    url: `/api/topic-clusters/${clusterId}/relation-candidates/${relationCandidateId}/actions`,
    method: 'post',
    data: payload,
  })
}

export function getLeadPromotionTrace(clusterId, promotionId) {
  return service({ url: `/api/topic-clusters/${clusterId}/lead-promotions/${promotionId}`, method: 'get' })
}

export function updateTopicCluster(clusterId, payload) {
  return service({ url: `/api/topic-clusters/${clusterId}`, method: 'patch', data: payload })
}

export function getTopicClusterLinks(clusterId) {
  return service({ url: `/api/topic-clusters/${clusterId}/links`, method: 'get' })
}

export function createTopicClusterLink(clusterId, payload) {
  return service({ url: `/api/topic-clusters/${clusterId}/links`, method: 'post', data: payload })
}

export function updateTopicClusterLink(linkId, payload) {
  return service({ url: `/api/topic-cluster-links/${linkId}`, method: 'patch', data: payload })
}

export function deleteTopicClusterLink(linkId) {
  return service({ url: `/api/topic-cluster-links/${linkId}`, method: 'delete' })
}

export function createTopicClusterRefreshRequest(payload) {
  return service({ url: '/api/topic-clusters/refresh-requests', method: 'post', data: payload })
}

export function listTopicClusterRefreshRequests() {
  return service({ url: '/api/topic-clusters/refresh-requests', method: 'get' })
}

export function getTopicClusterRefreshRequest(requestId) {
  return service({ url: `/api/topic-clusters/refresh-requests/${requestId}`, method: 'get' })
}

export function listTopicClusterProposals() {
  return service({ url: '/api/topic-clusters/proposals', method: 'get' })
}

export function getTopicClusterProposal(proposalId) {
  return service({ url: `/api/topic-clusters/proposals/${proposalId}`, method: 'get' })
}

export function applyTopicClusterProposal(proposalId, payload) {
  return service({ url: `/api/topic-clusters/proposals/${proposalId}/apply`, method: 'post', data: payload })
}

export function findTopicClustersByTarget(targetType, targetId) {
  return service({
    url: '/api/topic-clusters/by-target',
    method: 'get',
    params: { target_type: targetType, target_id: targetId },
  })
}
