// Live overview provider. Thin wrapper around the existing axios service
// so the switch from direct-service calls to provider-based calls is
// behaviour-preserving in live mode.

import service from '../../../api/index'

export async function getOverview() {
  // The response interceptor already unwraps to response.data, so this
  // resolves to { success, data, ... } just like callers expect.
  return service({ url: '/api/registry/overview', method: 'get' })
}
