export async function resolveWorkbenchStateFromSimulation(simulationId, deps) {
  const { getSimulation, loadProjectWorkbenchState } = deps
  const simRes = await getSimulation(simulationId)
  if (!simRes.success || !simRes.data) {
    return {
      success: false,
      error: simRes.error || '未知错误',
      simulation: null,
      workbenchState: null,
    }
  }

  const simData = simRes.data
  let workbenchState = null
  if (simData.project_id) {
    workbenchState = await loadProjectWorkbenchState(simData.project_id)
  }

  return {
    success: true,
    error: '',
    simulation: simData,
    workbenchState,
  }
}

export async function resolveWorkbenchStateFromReport(reportId, deps) {
  const { getReport, getSimulation, loadProjectWorkbenchState } = deps
  const reportRes = await getReport(reportId)
  if (!reportRes.success || !reportRes.data) {
    return {
      success: false,
      error: reportRes.error || '未知错误',
      report: null,
      simulation: null,
      simulationId: null,
      workbenchState: null,
    }
  }

  const reportData = reportRes.data
  const simulationId = reportData.simulation_id || null
  if (!simulationId) {
    return {
      success: true,
      error: '',
      report: reportData,
      simulation: null,
      simulationId: null,
      workbenchState: null,
    }
  }

  const simulationResult = await resolveWorkbenchStateFromSimulation(simulationId, {
    getSimulation,
    loadProjectWorkbenchState,
  })

  return {
    success: simulationResult.success,
    error: simulationResult.error,
    report: reportData,
    simulation: simulationResult.simulation,
    simulationId,
    workbenchState: simulationResult.workbenchState,
  }
}
