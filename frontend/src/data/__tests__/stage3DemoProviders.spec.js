// Stage-3 demo provider unit tests. Hermetic — no Vue, no mounts.

import { describe, expect, it } from 'vitest'

import * as demoConcept from '../providers/demo/conceptProvider'
import * as demoEvolution from '../providers/demo/evolutionProvider'
import * as demoReview from '../providers/demo/reviewProvider'
import * as demoPipeline from '../providers/demo/pipelineProvider'

import {
  PROJECT_OBSERVABILITY,
  PROJECT_AGENTIC,
  PROJECT_RETRIEVAL,
} from '../providers/demo/fixtures/entities'

describe('demo concept provider', () => {
  it.each([
    [PROJECT_OBSERVABILITY, '可观测性平台调研'],
    [PROJECT_AGENTIC, 'Agentic Workflows 设计笔记'],
    [PROJECT_RETRIEVAL, '检索增强生成基准对比'],
  ])('returns fixture for %s', async (pid, expectedName) => {
    const res = await demoConcept.getConceptView(pid)
    expect(res.success).toBe(true)
    expect(res.data.meta.projectName).toBe(expectedName)
    expect(Array.isArray(res.data.candidateConcepts)).toBe(true)
    expect(res.data.candidateConcepts.length).toBeGreaterThan(0)
  })

  it('throws friendly error for unknown projectId', async () => {
    await expect(demoConcept.getConceptView('not-a-real-id')).rejects.toThrow(
      /Demo data not available/,
    )
  })
})

describe('demo evolution provider', () => {
  it('returns snapshot with all required sections', async () => {
    const res = await demoEvolution.getEvolutionView(PROJECT_OBSERVABILITY)
    expect(res.data.meta.projectId).toBe(PROJECT_OBSERVABILITY)
    expect(res.data.projectOverview).toBeTruthy()
    expect(res.data.knowledgeAssetSnapshot).toBeTruthy()
    expect(res.data.traceabilityAndSignalQuality).toBeTruthy()
    expect(res.data.nextCapabilitiesGap).toBeTruthy()
    expect(res.data.diagnostics).toBeTruthy()
  })

  it('degrades with error for unknown project', async () => {
    await expect(demoEvolution.getEvolutionView('no-such-id')).rejects.toThrow(
      /Demo data not available/,
    )
  })
})

describe('demo review provider', () => {
  it('returns summary + items for a supported project', async () => {
    const res = await demoReview.getReviewView(PROJECT_AGENTIC)
    expect(Array.isArray(res.data.items)).toBe(true)
    expect(res.data.items.length).toBeGreaterThan(0)
    expect(res.data.summary).toBeTruthy()
    // Item shape check — decorateReviewTask downstream needs these.
    const first = res.data.items[0]
    expect(first.id).toBeTruthy()
    expect(first.title).toBeTruthy()
    expect(['warning', 'concept', 'relation', 'theme']).toContain(first.kind)
    expect(['low', 'medium', 'high']).toContain(first.severity)
  })

  it('degrades for unknown project', async () => {
    await expect(demoReview.getReviewView('no-such-id')).rejects.toThrow(
      /Demo data not available/,
    )
  })
})

describe('demo pipeline provider', () => {
  it('listAutoPendingUrls returns all 4 buckets', async () => {
    const res = await demoPipeline.listAutoPendingUrls()
    expect(Array.isArray(res.data.pending)).toBe(true)
    expect(Array.isArray(res.data.in_flight)).toBe(true)
    expect(Array.isArray(res.data.processed)).toBe(true)
    expect(Array.isArray(res.data.errored)).toBe(true)
    // Sanity: at least one URL in each category so demo page isn't empty.
    expect(res.data.pending.length + res.data.in_flight.length + res.data.processed.length + res.data.errored.length).toBeGreaterThan(0)
  })

  it('listGraphTasks returns task records with required fields', async () => {
    const res = await demoPipeline.listGraphTasks()
    expect(Array.isArray(res.data)).toBe(true)
    for (const t of res.data) {
      expect(t.task_id).toBeTruthy()
      expect(['running', 'processing', 'completed', 'failed']).toContain(t.status)
    }
  })

  it('getLlmMode returns config snapshot', async () => {
    const res = await demoPipeline.getLlmMode()
    expect(['local', 'bailian']).toContain(res.data.mode)
    expect(res.data.local_model).toBeTruthy()
  })
})
