export function createEmptyConceptViewModel() {
  return {
    meta: {
      projectId: '',
      projectName: '',
      graphId: null,
      phase1Status: 'unknown',
      sourceScope: 'project_graph',
      generatedAt: '',
    },
    summary: {
      nodeCount: 0,
      edgeCount: 0,
      typedNodeCount: 0,
      candidateConceptCount: 0,
      relationCount: 0,
      warningsCount: 0,
    },
    candidateConcepts: [],
    diagnostics: {
      warnings: [],
      emptyReason: '',
      dataCompleteness: 'empty',
      typeCounts: [],
    },
  }
}

export function createEmptyConceptCandidate() {
  return {
    key: '',
    displayName: '',
    conceptType: 'Node',
    mentionCount: 0,
    connectedCount: 0,
    sampleEvidence: [],
    sourceNodeIds: [],
    status: 'unreviewed',
  }
}

export function normalizeConceptCandidate(candidate = {}) {
  const empty = createEmptyConceptCandidate()
  return {
    ...empty,
    ...candidate,
    sampleEvidence: Array.isArray(candidate.sampleEvidence) ? candidate.sampleEvidence : [],
    sourceNodeIds: Array.isArray(candidate.sourceNodeIds) ? candidate.sourceNodeIds : [],
  }
}
