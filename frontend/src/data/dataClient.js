// Public data-client surface.
//
// Pages (and stores) must import from here, NOT from ../api/... or
// ../services/api/... directly. That's the boundary that makes live/demo
// mode swapping possible without page-level conditionals.
//
// New data needs? Add a method here + a live provider + a demo provider.
// Keep the surface narrow and task-oriented — don't leak HTTP verbs or
// endpoint paths.

import { appMode, APP_MODES } from '../runtime/appMode'

import * as liveOverview from './providers/live/overviewProvider'
import * as liveWorkspace from './providers/live/workspaceProvider'
import * as liveRegistry from './providers/live/registryProvider'
import * as liveTheme from './providers/live/themeProvider'
import * as liveConcept from './providers/live/conceptProvider'
import * as liveEvolution from './providers/live/evolutionProvider'
import * as liveReview from './providers/live/reviewProvider'
import * as livePipeline from './providers/live/pipelineProvider'

import * as demoOverview from './providers/demo/overviewProvider'
import * as demoWorkspace from './providers/demo/workspaceProvider'
import * as demoRegistry from './providers/demo/registryProvider'
import * as demoTheme from './providers/demo/themeProvider'
import * as demoConcept from './providers/demo/conceptProvider'
import * as demoEvolution from './providers/demo/evolutionProvider'
import * as demoReview from './providers/demo/reviewProvider'
import * as demoPipeline from './providers/demo/pipelineProvider'

function pick(liveImpl, demoImpl) {
  return appMode.value === APP_MODES.DEMO ? demoImpl : liveImpl
}

// ----- Overview --------------------------------------------------------
export function getOverview() {
  return pick(liveOverview, demoOverview).getOverview()
}

// ----- Workspace -------------------------------------------------------
export function getProjectWorkbench(projectId) {
  return pick(liveWorkspace, demoWorkspace).getProjectWorkbench(projectId)
}

// ----- Registry (and cross-relations shared with Relation pages) -------
export function listRegistryConcepts(conceptType) {
  return pick(liveRegistry, demoRegistry).listRegistryConcepts(conceptType)
}

export function getRegistryConcept(entryId) {
  return pick(liveRegistry, demoRegistry).getRegistryConcept(entryId)
}

export function listCrossRelations(params) {
  return pick(liveRegistry, demoRegistry).listCrossRelations(params)
}

export function getCrossRelation(relationId) {
  return pick(liveRegistry, demoRegistry).getCrossRelation(relationId)
}

export function getCrossRelationCounts(entryIds) {
  return pick(liveRegistry, demoRegistry).getCrossRelationCounts(entryIds)
}

// ----- Theme -----------------------------------------------------------
export function listGlobalThemes() {
  return pick(liveTheme, demoTheme).listGlobalThemes()
}

export function listThemesViaRegistryTab() {
  return pick(liveTheme, demoTheme).listThemesViaRegistryTab()
}

export function getThemeHubView(themeId) {
  return pick(liveTheme, demoTheme).getThemeHubView(themeId)
}

export function getThemePanorama(themeId) {
  return pick(liveTheme, demoTheme).getThemePanorama(themeId)
}

export function getOrphans(limit) {
  return pick(liveTheme, demoTheme).getOrphans(limit)
}

// ----- Concept (per-project candidate concepts view) ------------------
export function getConceptView(projectId) {
  return pick(liveConcept, demoConcept).getConceptView(projectId)
}

// ----- Evolution (per-project snapshot view) --------------------------
export function getEvolutionView(projectId) {
  return pick(liveEvolution, demoEvolution).getEvolutionView(projectId)
}

// ----- Review (per-project review queue) ------------------------------
export function getReviewView(projectId) {
  return pick(liveReview, demoReview).getReviewView(projectId)
}

// ----- AutoPipeline (global) ------------------------------------------
export function listAutoPendingUrls() {
  return pick(livePipeline, demoPipeline).listAutoPendingUrls()
}

export function listGraphTasks() {
  return pick(livePipeline, demoPipeline).listGraphTasks()
}

export function getLlmMode() {
  return pick(livePipeline, demoPipeline).getLlmMode()
}
