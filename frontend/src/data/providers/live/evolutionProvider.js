// Live evolution provider — wraps services/api/evolutionApi reads.

import { getEvolutionView as apiGetEvolutionView } from '../../../services/api/evolutionApi'

export function getEvolutionView(projectId) {
  return apiGetEvolutionView(projectId)
}
