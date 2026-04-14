export function createEmptyThemeViewModel() {
  return {
    meta: {
      projectId: '',
      projectName: '',
      graphId: null,
      phase1Status: 'unknown',
      viewVersion: 'theme-candidates-v1',
      generatedFrom: [],
      generatedAt: '',
    },
    overview: {
      summaryText: '',
      candidateCount: 0,
      nodeCount: 0,
      edgeCount: 0,
      readingGroupCount: 0,
      uncoveredNodesCount: 0,
    },
    backbone: {
      title: '',
      summary: '',
      problem: { title: '', summary: '' },
      solution: { title: '', summary: '' },
      architecture: { title: '', summary: '' },
      articleSections: [],
    },
    themeCandidates: [],
    diagnostics: {
      warnings: [],
      emptyReason: '',
      dataCompleteness: 'empty',
      unassignedReadingGroups: [],
      unassignedLabels: [],
      uncoveredNodesCount: 0,
    },
    limitations: [],
  }
}

export function createEmptyThemeCandidate() {
  return {
    candidateKey: '',
    title: '',
    kind: 'reading_group',
    summary: '',
    supportSignals: [],
    evidence: {
      nodeCount: 0,
      edgeCount: 0,
      readingGroupRefs: [],
      topLabels: [],
      sampleNodes: [],
    },
    sourceRefs: [],
  }
}

export function normalizeThemeCandidate(candidate = {}) {
  const empty = createEmptyThemeCandidate()
  return {
    ...empty,
    ...candidate,
    supportSignals: Array.isArray(candidate.supportSignals) ? candidate.supportSignals : [],
    sourceRefs: Array.isArray(candidate.sourceRefs) ? candidate.sourceRefs : [],
    evidence: {
      ...empty.evidence,
      ...(candidate.evidence || {}),
      readingGroupRefs: Array.isArray(candidate.evidence?.readingGroupRefs) ? candidate.evidence.readingGroupRefs : [],
      topLabels: Array.isArray(candidate.evidence?.topLabels) ? candidate.evidence.topLabels : [],
      sampleNodes: Array.isArray(candidate.evidence?.sampleNodes) ? candidate.evidence.sampleNodes : [],
    },
  }
}
