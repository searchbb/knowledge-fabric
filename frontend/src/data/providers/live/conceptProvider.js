// Live concept provider — wraps services/api/conceptApi reads.

import { getConceptView as apiGetConceptView } from '../../../services/api/conceptApi'

export function getConceptView(projectId) {
  return apiGetConceptView(projectId)
}
