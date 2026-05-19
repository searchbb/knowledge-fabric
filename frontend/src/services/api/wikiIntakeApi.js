import service from '../../api/index'

export function listWikiIntakeCandidates(params = {}) {
  return service({ url: '/api/wiki-intake/candidates', method: 'get', params })
}

export function listWikiTopics(options = {}) {
  return service({
    url: '/api/wiki-intake/topics',
    method: 'get',
    params: {
      ...(options.includeCoverage ? { include_coverage: '1' } : {}),
    },
  })
}

export function getWikiTopicArticles(topicId) {
  return service({ url: `/api/wiki-intake/topics/${topicId}/articles`, method: 'get' })
}

export function getWikiTopicClusterCoverage(topicId) {
  return service({ url: `/api/wiki-intake/topics/${topicId}/cluster-coverage`, method: 'get' })
}

export function setWikiTopicClusterCoverageOverride(topicId, payload) {
  return service({ url: `/api/wiki-intake/topics/${topicId}/cluster-coverage/override`, method: 'post', data: payload })
}

export function linkWikiTopicToCluster(topicId, payload) {
  return service({ url: `/api/wiki-intake/topics/${topicId}/cluster-coverage/link`, method: 'post', data: payload })
}

export function requestWikiTopicClusterProposal(topicId, payload) {
  return service({ url: `/api/wiki-intake/topics/${topicId}/cluster-coverage/proposals`, method: 'post', data: payload })
}

export function getWikiIntakeCandidate(candidateId) {
  return service({ url: `/api/wiki-intake/candidates/${candidateId}`, method: 'get' })
}

export function getWikiIntakeProcessedResult(candidateId) {
  return service({ url: `/api/wiki-intake/candidates/${candidateId}/processed-result`, method: 'get' })
}

export function changeWikiIntakeCandidatePrimaryTopic(candidateId, payload) {
  return service({ url: `/api/wiki-intake/candidates/${candidateId}/topic-associations/primary`, method: 'patch', data: payload })
}

export function unlinkWikiIntakeCandidatePrimaryTopic(candidateId, payload = {}) {
  return service({ url: `/api/wiki-intake/candidates/${candidateId}/topic-associations/unlink-primary`, method: 'post', data: payload })
}

export function scanWikiIntake(payload = {}) {
  return service({ url: '/api/wiki-intake/scan', method: 'post', data: payload })
}

export function processNextWikiIntake(payload = {}) {
  return service({ url: '/api/wiki-intake/process-next', method: 'post', data: payload })
}

export function createWikiIntakeDecision(payload) {
  return service({ url: '/api/wiki-intake/decisions', method: 'post', data: payload })
}

export function getWikiIntakeConfig() {
  return service({ url: '/api/wiki-intake/config', method: 'get' })
}
