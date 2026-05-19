import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import GateReviewSnapshotAttentionContext from '../GateReviewSnapshotAttentionContext.vue'
import { buildGateReviewSnapshotAttentionContext } from '../gateReviewSnapshotAttentionContext'
import {
  goldenGovernanceReview,
  goldenNotesBySnapshotId,
  goldenOptions,
  goldenSnapshots,
} from './fixtures/gateReviewAttentionGoldenCase'

const ATTENTION_PRODUCTION_FILES = [
  'components/research/snapshotReviewNoteRollup.js',
  'components/research/gateReviewSnapshotAttentionContext.js',
  'components/research/GateReviewSnapshotAttentionContext.vue',
]

function sourcePath(file) {
  return resolve(process.cwd(), 'src', file)
}

function readSource(file) {
  return readFileSync(sourcePath(file), 'utf8')
}

function collectKeys(value, keys = new Set()) {
  if (Array.isArray(value)) {
    value.forEach((item) => collectKeys(item, keys))
    return keys
  }
  if (value && typeof value === 'object') {
    Object.keys(value).forEach((key) => {
      keys.add(key)
      collectKeys(value[key], keys)
    })
  }
  return keys
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value))
}

function buildGoldenContext() {
  return buildGateReviewSnapshotAttentionContext({
    governanceReview: goldenGovernanceReview,
    snapshots: goldenSnapshots,
    notesBySnapshotId: goldenNotesBySnapshotId,
    topNoteLimit: goldenOptions.topNoteLimit,
  })
}

describe('gate review attention freeze contract', () => {
  it('keeps the P15-P19 production attention surface explicit and narrow', () => {
    expect(ATTENTION_PRODUCTION_FILES).toEqual([
      'components/research/snapshotReviewNoteRollup.js',
      'components/research/gateReviewSnapshotAttentionContext.js',
      'components/research/GateReviewSnapshotAttentionContext.vue',
    ])

    for (const file of ATTENTION_PRODUCTION_FILES) {
      expect(existsSync(sourcePath(file))).toBe(true)
    }
  })

  it('keeps production attention files free of runtime, router, persistence, and model surfaces', () => {
    const forbiddenPatterns = [
      /dataClient/,
      /vue-router|useRouter|useRoute|RouterLink/,
      /\bfetch\s*\(/,
      /\baxios\b/,
      /\blocalStorage\b/,
      /\bsessionStorage\b/,
      /\bindexedDB\b/,
      /\bWebSocket\b/,
      /\bEventSource\b/,
      /\bdefineEmits\b|\$emit\b|\bemit\s*\(/,
      /Bailian|OpenAI|deepResearch|deep_research|deep-research|modelClient|\bllm\b|\bgpt\b/i,
      /createReviewHistory|updateGovernanceReview|updateSnapshotReviewNote|createSnapshotReviewNote/,
    ]

    for (const file of ATTENTION_PRODUCTION_FILES) {
      const source = readSource(file)
      for (const pattern of forbiddenPatterns) {
        expect(source).not.toMatch(pattern)
      }
    }
  })

  it('keeps derived helper output free of action, navigation, and workflow capability fields', () => {
    const context = buildGoldenContext()
    const keys = collectKeys(context)
    const forbiddenKeys = [
      'actions',
      'action',
      'buttons',
      'links',
      'href',
      'route',
      'to',
      'router',
      'emit',
      'command',
      'mutation',
      'assignment',
      'assignee',
      'task',
      'workflow',
      'readiness',
      'gate_decision',
      'decision_action',
      'model_call',
      'llm_call',
      'scheduler',
      'worker',
      'queue',
      'dag',
      'persisted_rollup',
      'review_history_append',
      'sidecar_write',
    ]

    for (const key of forbiddenKeys) {
      expect(keys.has(key)).toBe(false)
    }
  })

  it('keeps the attention component passive and non-interactive', () => {
    const source = readSource('components/research/GateReviewSnapshotAttentionContext.vue')
    const forbiddenPatterns = [
      /<button(\s|>)/,
      /<a(\s|>)/,
      /RouterLink/,
      /@click/,
      /defineEmits/,
      /\$emit\b|\bemit\s*\(/,
    ]

    for (const pattern of forbiddenPatterns) {
      expect(source).not.toMatch(pattern)
    }

    const wrapper = mount(GateReviewSnapshotAttentionContext, {
      props: { context: buildGoldenContext() },
    })
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.findAll('a')).toHaveLength(0)
    expect(wrapper.findAll('[href]')).toHaveLength(0)
    expect(wrapper.findAll('[role="button"]')).toHaveLength(0)
    expect(wrapper.emitted()).toEqual({})
  })

  it('keeps raw snapshot review notes as source data and does not mutate inputs', () => {
    const source = {
      governanceReview: goldenGovernanceReview,
      snapshots: goldenSnapshots,
      notesBySnapshotId: goldenNotesBySnapshotId,
    }
    const before = deepClone(source)
    const context = buildGoldenContext()

    expect(source).toEqual(before)
    expect(context.disclaimers).toEqual({
      read_only: true,
      does_not_change_gate_readiness: true,
      does_not_mutate_governance_review: true,
      does_not_mutate_snapshot: true,
    })
  })
})
