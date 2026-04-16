// Demo evolution provider — per-projectId fixture lookup.

import { evolutionViewFixturesByProjectId } from './fixtures/evolutionView'

const clone = (v) => JSON.parse(JSON.stringify(v))

export async function getEvolutionView(projectId) {
  const fixture = evolutionViewFixturesByProjectId[projectId]
  if (!fixture) {
    throw new Error(
      `Demo data not available for evolution view of project "${projectId}".`,
    )
  }
  return clone(fixture)
}
