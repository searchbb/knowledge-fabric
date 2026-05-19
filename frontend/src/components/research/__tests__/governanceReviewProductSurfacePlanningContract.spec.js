import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const planningDocPath = resolve(
  process.cwd(),
  '..',
  'docs',
  'research',
  'p21_governance_review_product_surface_planning.md',
)

function readPlanningDoc() {
  return readFileSync(planningDocPath, 'utf8')
}

describe('governance review product surface planning contract', () => {
  it('keeps P21 as docs/tests-only planning separate from the frozen attention context', () => {
    expect(existsSync(planningDocPath)).toBe(true)
    const doc = readPlanningDoc()

    expect(doc).toContain('P21 is a docs/tests-only scope-split baseline')
    expect(doc).toContain('The P15-P20 GovernanceReview attention context is frozen')
    expect(doc).toContain('must not extend')
    expect(doc).toContain('snapshotReviewNoteRollup.js')
    expect(doc).toContain('gateReviewSnapshotAttentionContext.js')
    expect(doc).toContain('GateReviewSnapshotAttentionContext.vue')
  })

  it('names and separates the four candidate future product surfaces', () => {
    const doc = readPlanningDoc()

    expect(doc).toContain('Review Workspace')
    expect(doc).toContain('Readiness Evaluator')
    expect(doc).toContain('Workflow / Assignment')
    expect(doc).toContain('Model-assisted Review')
  })

  it('preserves KFC as a research asset repository while keeping orchestration outside runtime', () => {
    const doc = readPlanningDoc()

    expect(doc).toContain('KFC remains a research asset and provenance repository')
    expect(doc).toContain('KFC may store')
    expect(doc).toContain('Codex, skills, and external tools own orchestration and execution')
    expect(doc).toContain('KFC must not become')
    expect(doc).toContain('universal Agent scheduler')
    expect(doc).toContain('model runtime')
    expect(doc).toContain('workflow DAG engine')
  })

  it('keeps P21 free of runtime, schema, workflow, readiness, and model behavior', () => {
    const doc = readPlanningDoc()
    const requiredNoRuntimeBoundaries = [
      'backend endpoint',
      'dataClient method',
      'schema change',
      'persistence model',
      'sidecar write',
      'frontend route',
      'product-visible UI behavior',
      'runtime workflow',
      'scheduler, worker, queue, or DAG',
      'assignment engine',
      'readiness engine',
      'automatic gate decision',
      'GPT, Bailian, deep-research, or model runtime call',
    ]

    for (const boundary of requiredNoRuntimeBoundaries) {
      expect(doc).toContain(boundary)
    }
  })

  it('keeps P22 pointed at a separate read-only review workspace baseline', () => {
    const doc = readPlanningDoc()

    expect(doc).toContain('Research Review Workspace Navigation Baseline')
    expect(doc).toContain('separate read-only product surface')
    expect(doc).toContain('reviewer navigation and context layout')
    expect(doc).toContain('not readiness, workflow, assignment, or model assistance')
    expect(doc).toContain('should not')
    expect(doc).toContain('modify the frozen P15-P20 attention files')
  })
})
