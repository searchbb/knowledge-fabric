// Demo workspace provider.
//
// If the requested projectId has a demo fixture, return it. Otherwise
// throw a friendly error — WorkspacePage surfaces the error via its
// existing error state card, which is the "graceful degradation" the
// brief asks for. No white screen.

import { workspaceFixturesByProjectId } from './fixtures/workspace'

export async function getProjectWorkbench(projectId) {
  const fixture = workspaceFixturesByProjectId[projectId]
  if (!fixture) {
    throw new Error(
      `Demo data not available for project "${projectId}". 返回「按项目」可查看可用的 demo 项目。`,
    )
  }
  // Deep clone so consumers can mutate freely.
  return JSON.parse(JSON.stringify(fixture))
}
