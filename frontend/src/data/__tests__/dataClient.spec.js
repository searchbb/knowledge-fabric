// Tests for the dataClient public surface.
//
// Goal: prove that the same method call reaches the live provider when
// appMode is 'live' and the demo provider when it's 'demo'. That's the
// whole contract of this layer — the pages rely on it.

import { beforeEach, describe, expect, it, vi } from 'vitest'

const liveGetOverview = vi.fn()
const demoGetOverview = vi.fn()
const liveGetProjectWorkbench = vi.fn()
const demoGetProjectWorkbench = vi.fn()

vi.mock('../providers/live/overviewProvider', () => ({
  getOverview: (...args) => liveGetOverview(...args),
}))
vi.mock('../providers/demo/overviewProvider', () => ({
  getOverview: (...args) => demoGetOverview(...args),
}))
vi.mock('../providers/live/workspaceProvider', () => ({
  getProjectWorkbench: (...args) => liveGetProjectWorkbench(...args),
}))
vi.mock('../providers/demo/workspaceProvider', () => ({
  getProjectWorkbench: (...args) => demoGetProjectWorkbench(...args),
}))

// Stage-3 providers: concept / evolution / review / pipeline.
const liveGetConceptView = vi.fn()
const demoGetConceptView = vi.fn()
const liveGetEvolutionView = vi.fn()
const demoGetEvolutionView = vi.fn()
const liveGetReviewView = vi.fn()
const demoGetReviewView = vi.fn()
const liveListPendingUrls = vi.fn()
const demoListPendingUrls = vi.fn()
const liveListGraphTasks = vi.fn()
const demoListGraphTasks = vi.fn()
const liveGetLlmMode = vi.fn()
const demoGetLlmMode = vi.fn()

vi.mock('../providers/live/conceptProvider', () => ({
  getConceptView: (...a) => liveGetConceptView(...a),
}))
vi.mock('../providers/demo/conceptProvider', () => ({
  getConceptView: (...a) => demoGetConceptView(...a),
}))
vi.mock('../providers/live/evolutionProvider', () => ({
  getEvolutionView: (...a) => liveGetEvolutionView(...a),
}))
vi.mock('../providers/demo/evolutionProvider', () => ({
  getEvolutionView: (...a) => demoGetEvolutionView(...a),
}))
vi.mock('../providers/live/reviewProvider', () => ({
  getReviewView: (...a) => liveGetReviewView(...a),
}))
vi.mock('../providers/demo/reviewProvider', () => ({
  getReviewView: (...a) => demoGetReviewView(...a),
}))
vi.mock('../providers/live/pipelineProvider', () => ({
  listAutoPendingUrls: (...a) => liveListPendingUrls(...a),
  listGraphTasks: (...a) => liveListGraphTasks(...a),
  getLlmMode: (...a) => liveGetLlmMode(...a),
}))
vi.mock('../providers/demo/pipelineProvider', () => ({
  listAutoPendingUrls: (...a) => demoListPendingUrls(...a),
  listGraphTasks: (...a) => demoListGraphTasks(...a),
  getLlmMode: (...a) => demoGetLlmMode(...a),
}))

import * as dataClient from '../dataClient'
import { setMode } from '../../runtime/appMode'

describe('dataClient', () => {
  beforeEach(() => {
    liveGetOverview.mockReset().mockResolvedValue({ data: { from: 'live' } })
    demoGetOverview.mockReset().mockResolvedValue({ data: { from: 'demo' } })
    liveGetProjectWorkbench.mockReset().mockResolvedValue({ project: { source: 'live' } })
    demoGetProjectWorkbench.mockReset().mockResolvedValue({ project: { source: 'demo' } })
    window.localStorage.clear()
    setMode('live')
  })

  it('routes getOverview to the live provider in live mode', async () => {
    setMode('live')
    const res = await dataClient.getOverview()
    expect(liveGetOverview).toHaveBeenCalledTimes(1)
    expect(demoGetOverview).not.toHaveBeenCalled()
    expect(res.data.from).toBe('live')
  })

  it('routes getOverview to the demo provider in demo mode', async () => {
    setMode('demo')
    const res = await dataClient.getOverview()
    expect(demoGetOverview).toHaveBeenCalledTimes(1)
    expect(liveGetOverview).not.toHaveBeenCalled()
    expect(res.data.from).toBe('demo')
  })

  it('routes getProjectWorkbench based on current mode', async () => {
    setMode('live')
    await dataClient.getProjectWorkbench('p1')
    expect(liveGetProjectWorkbench).toHaveBeenCalledWith('p1')

    setMode('demo')
    await dataClient.getProjectWorkbench('p2')
    expect(demoGetProjectWorkbench).toHaveBeenCalledWith('p2')
  })

  describe('stage-3 dispatch', () => {
    beforeEach(() => {
      liveGetConceptView.mockReset().mockResolvedValue({ src: 'live-concept' })
      demoGetConceptView.mockReset().mockResolvedValue({ src: 'demo-concept' })
      liveGetEvolutionView.mockReset().mockResolvedValue({ src: 'live-evolution' })
      demoGetEvolutionView.mockReset().mockResolvedValue({ src: 'demo-evolution' })
      liveGetReviewView.mockReset().mockResolvedValue({ src: 'live-review' })
      demoGetReviewView.mockReset().mockResolvedValue({ src: 'demo-review' })
      liveListPendingUrls.mockReset().mockResolvedValue({ src: 'live-pending' })
      demoListPendingUrls.mockReset().mockResolvedValue({ src: 'demo-pending' })
      liveListGraphTasks.mockReset().mockResolvedValue({ src: 'live-tasks' })
      demoListGraphTasks.mockReset().mockResolvedValue({ src: 'demo-tasks' })
      liveGetLlmMode.mockReset().mockResolvedValue({ src: 'live-mode' })
      demoGetLlmMode.mockReset().mockResolvedValue({ src: 'demo-mode' })
    })

    it('getConceptView dispatches by mode', async () => {
      setMode('live')
      expect((await dataClient.getConceptView('p1')).src).toBe('live-concept')
      expect(liveGetConceptView).toHaveBeenCalledWith('p1')
      setMode('demo')
      expect((await dataClient.getConceptView('p2')).src).toBe('demo-concept')
      expect(demoGetConceptView).toHaveBeenCalledWith('p2')
    })

    it('getEvolutionView dispatches by mode', async () => {
      setMode('demo')
      expect((await dataClient.getEvolutionView('x')).src).toBe('demo-evolution')
      setMode('live')
      expect((await dataClient.getEvolutionView('y')).src).toBe('live-evolution')
    })

    it('getReviewView dispatches by mode', async () => {
      setMode('demo')
      expect((await dataClient.getReviewView('x')).src).toBe('demo-review')
      setMode('live')
      expect((await dataClient.getReviewView('y')).src).toBe('live-review')
    })

    it('pipeline methods dispatch by mode', async () => {
      setMode('demo')
      expect((await dataClient.listAutoPendingUrls()).src).toBe('demo-pending')
      expect((await dataClient.listGraphTasks()).src).toBe('demo-tasks')
      expect((await dataClient.getLlmMode()).src).toBe('demo-mode')
      setMode('live')
      expect((await dataClient.listAutoPendingUrls()).src).toBe('live-pending')
      expect((await dataClient.listGraphTasks()).src).toBe('live-tasks')
      expect((await dataClient.getLlmMode()).src).toBe('live-mode')
    })
  })
})
