// Demo overview provider — returns a static fixture wrapped in a resolved
// promise so it's behaviourally indistinguishable from the live call.

import { overviewFixture } from './fixtures/overview'

export async function getOverview() {
  // Deep clone so the page can't mutate the fixture by accident.
  return JSON.parse(JSON.stringify(overviewFixture))
}
