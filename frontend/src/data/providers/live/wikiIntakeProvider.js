import {
  createWikiIntakeDecision as apiCreateWikiIntakeDecision,
  changeWikiIntakeCandidatePrimaryTopic as apiChangeWikiIntakeCandidatePrimaryTopic,
  getWikiIntakeCandidate as apiGetWikiIntakeCandidate,
  getWikiIntakeProcessedResult as apiGetWikiIntakeProcessedResult,
  getWikiTopicClusterCoverage as apiGetWikiTopicClusterCoverage,
  getWikiIntakeConfig as apiGetWikiIntakeConfig,
  getWikiTopicArticles as apiGetWikiTopicArticles,
  linkWikiTopicToCluster as apiLinkWikiTopicToCluster,
  listWikiTopics as apiListWikiTopics,
  listWikiIntakeCandidates as apiListWikiIntakeCandidates,
  processNextWikiIntake as apiProcessNextWikiIntake,
  requestWikiTopicClusterProposal as apiRequestWikiTopicClusterProposal,
  scanWikiIntake as apiScanWikiIntake,
  setWikiTopicClusterCoverageOverride as apiSetWikiTopicClusterCoverageOverride,
  unlinkWikiIntakeCandidatePrimaryTopic as apiUnlinkWikiIntakeCandidatePrimaryTopic,
} from '../../../services/api/wikiIntakeApi'

export function listWikiIntakeCandidates(params) {
  return apiListWikiIntakeCandidates(params)
}

export function listWikiTopics(options) {
  return apiListWikiTopics(options)
}

export function getWikiTopicArticles(topicId) {
  return apiGetWikiTopicArticles(topicId)
}

export function getWikiTopicClusterCoverage(topicId) {
  return apiGetWikiTopicClusterCoverage(topicId)
}

export function setWikiTopicClusterCoverageOverride(topicId, payload) {
  return apiSetWikiTopicClusterCoverageOverride(topicId, payload)
}

export function linkWikiTopicToCluster(topicId, payload) {
  return apiLinkWikiTopicToCluster(topicId, payload)
}

export function requestWikiTopicClusterProposal(topicId, payload) {
  return apiRequestWikiTopicClusterProposal(topicId, payload)
}

export function getWikiIntakeCandidate(candidateId) {
  return apiGetWikiIntakeCandidate(candidateId)
}

export function getWikiIntakeProcessedResult(candidateId) {
  return apiGetWikiIntakeProcessedResult(candidateId)
}

export function changeWikiIntakeCandidatePrimaryTopic(candidateId, payload) {
  return apiChangeWikiIntakeCandidatePrimaryTopic(candidateId, payload)
}

export function unlinkWikiIntakeCandidatePrimaryTopic(candidateId, payload) {
  return apiUnlinkWikiIntakeCandidatePrimaryTopic(candidateId, payload)
}

export function scanWikiIntake(payload) {
  return apiScanWikiIntake(payload)
}

export function processNextWikiIntake(payload) {
  return apiProcessNextWikiIntake(payload)
}

export function createWikiIntakeDecision(payload) {
  return apiCreateWikiIntakeDecision(payload)
}

export function getWikiIntakeConfig() {
  return apiGetWikiIntakeConfig()
}
