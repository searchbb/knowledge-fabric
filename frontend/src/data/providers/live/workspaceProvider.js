// Live workspace provider. Delegates to the existing project workbench
// loader so the live code path is literally unchanged — it's just reached
// through the provider boundary now.

import { loadProjectWorkbenchState } from '../../../utils/projectWorkbenchState'

export async function getProjectWorkbench(projectId) {
  return loadProjectWorkbenchState(projectId)
}
