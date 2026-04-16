import { reactive } from 'vue'
// Read goes through dataClient so live/demo mode swaps automatically.
import { getEvolutionView } from '../data/dataClient'
import { createEmptyEvolutionViewModel } from '../types/evolution'

export const evolutionStore = reactive({
  meta: createEmptyEvolutionViewModel().meta,
  projectOverview: createEmptyEvolutionViewModel().projectOverview,
  knowledgeAssetSnapshot: createEmptyEvolutionViewModel().knowledgeAssetSnapshot,
  traceabilityAndSignalQuality: createEmptyEvolutionViewModel().traceabilityAndSignalQuality,
  nextCapabilitiesGap: createEmptyEvolutionViewModel().nextCapabilitiesGap,
  diagnostics: createEmptyEvolutionViewModel().diagnostics,
  loading: false,
  error: '',
})

let seedSequence = 0

function resetEvolutionStore() {
  const emptyView = createEmptyEvolutionViewModel()
  evolutionStore.meta = emptyView.meta
  evolutionStore.projectOverview = emptyView.projectOverview
  evolutionStore.knowledgeAssetSnapshot = emptyView.knowledgeAssetSnapshot
  evolutionStore.traceabilityAndSignalQuality = emptyView.traceabilityAndSignalQuality
  evolutionStore.nextCapabilitiesGap = emptyView.nextCapabilitiesGap
  evolutionStore.diagnostics = emptyView.diagnostics
}

export async function loadEvolutionView(payload = {}) {
  const currentSequence = ++seedSequence
  evolutionStore.loading = true
  evolutionStore.error = ''

  try {
    const projectId = payload.projectId || payload.project?.project_id
    if (!projectId) {
      resetEvolutionStore()
      return
    }

    const response = await getEvolutionView(projectId)
    if (currentSequence !== seedSequence) return

    const view = response?.data || {}
    evolutionStore.meta = view.meta || createEmptyEvolutionViewModel().meta
    evolutionStore.projectOverview = view.projectOverview || createEmptyEvolutionViewModel().projectOverview
    evolutionStore.knowledgeAssetSnapshot = view.knowledgeAssetSnapshot || createEmptyEvolutionViewModel().knowledgeAssetSnapshot
    evolutionStore.traceabilityAndSignalQuality = view.traceabilityAndSignalQuality || createEmptyEvolutionViewModel().traceabilityAndSignalQuality
    evolutionStore.nextCapabilitiesGap = view.nextCapabilitiesGap || createEmptyEvolutionViewModel().nextCapabilitiesGap
    evolutionStore.diagnostics = view.diagnostics || createEmptyEvolutionViewModel().diagnostics
  } catch (error) {
    resetEvolutionStore()
    evolutionStore.error = error.message || '演化视图加载失败'
  } finally {
    if (currentSequence === seedSequence) {
      evolutionStore.loading = false
    }
  }
}
