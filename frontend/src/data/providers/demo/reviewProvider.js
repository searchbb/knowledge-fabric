// Demo review provider — per-projectId fixture lookup.

import { reviewViewFixturesByProjectId } from './fixtures/reviewView'

const clone = (v) => JSON.parse(JSON.stringify(v))

export async function getReviewView(projectId) {
  const fixture = reviewViewFixturesByProjectId[projectId]
  if (!fixture) {
    throw new Error(
      `Demo data not available for review view of project "${projectId}".`,
    )
  }
  return clone(fixture)
}
