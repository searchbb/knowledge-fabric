// Guard test: in demo mode, the axios instance must reject every
// mutating HTTP call (POST/PUT/PATCH/DELETE) BEFORE it reaches the
// network. Reads must continue to flow through.
//
// Why this matters: without the guard, demo-mode users can click
// "Create entry" (or any write button we haven't individually gated)
// and the request hits the real backend, corrupting live data with
// demo test records. The interceptor is the single choke point that
// makes demo mode truly read-only.

import { beforeEach, describe, expect, it } from 'vitest'
import service from '../index'
import { setMode } from '../../runtime/appMode'

describe('demo read-only guard (axios request interceptor)', () => {
  beforeEach(() => {
    setMode('live')
  })

  it('in live mode, write requests are not blocked by the interceptor', async () => {
    // We don't have a real backend here; we only need to confirm the
    // request was NOT rejected with isDemoReadonlyBlock. Let it fail
    // naturally (Network Error or adapter error), then assert.
    setMode('live')
    try {
      await service({ url: '/api/whatever', method: 'post', data: {} })
    } catch (err) {
      expect(err.isDemoReadonlyBlock).toBeFalsy()
      return
    }
    // If somehow it resolved, that's also fine — the guard didn't fire.
  })

  for (const method of ['post', 'put', 'patch', 'delete']) {
    it(`in demo mode, ${method.toUpperCase()} requests are rejected before network`, async () => {
      setMode('demo')
      await expect(
        service({ url: '/api/test', method, data: {} })
      ).rejects.toMatchObject({ isDemoReadonlyBlock: true })
    })
  }

  it('in demo mode, GET requests still pass through the interceptor', async () => {
    setMode('demo')
    // GET should NOT carry isDemoReadonlyBlock — if it errors, it's
    // network/adapter, not the guard.
    try {
      await service({ url: '/api/whatever-readonly', method: 'get' })
    } catch (err) {
      expect(err.isDemoReadonlyBlock).toBeFalsy()
    }
  })
})
