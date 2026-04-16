// Demo concept provider — per-projectId fixture lookup.

import { conceptViewFixturesByProjectId } from './fixtures/conceptView'

const clone = (v) => JSON.parse(JSON.stringify(v))

export async function getConceptView(projectId) {
  const fixture = conceptViewFixturesByProjectId[projectId]
  if (!fixture) {
    throw new Error(
      `Demo data not available for concept view of project "${projectId}".`,
    )
  }
  return clone(fixture)
}
