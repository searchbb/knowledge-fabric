# P23 Research Review Workspace Asset Index Baseline

Date: 2026-04-30

## Status

P23 adds a read-only project-first asset index to the Review Workspace at `/workspace/research/review`.

It remains an index, not an evaluator, workflow surface, assignment system, model-assisted review runtime, or gate decision system.

## Scope

P23 indexes existing reviewable assets by project:

- GovernanceReviews
- research snapshots

P23 intentionally defers:

- review history timeline
- traceability summary
- readiness scoring
- workflow or assignment state
- model-assisted review suggestions

## Existing APIs

P23 uses existing frontend data-client methods only:

- `listResearchProjects`
- `listGovernanceReviews`
- `listResearchSnapshots`

P23 does not add:

- backend endpoint
- dataClient method
- schema or persistence model
- persisted Review Workspace read model
- mutation API

## UI Contract

The Review Workspace may display:

- project-first groups
- GovernanceReview counts
- snapshot counts
- representative GovernanceReview titles/status labels
- representative snapshot titles/status labels/timestamps
- neutral empty states
- navigation back to the existing strategic research surface

The Review Workspace must not display controls or language that implies:

- readiness score
- pass/fail gate status
- required action
- assignment owner
- workflow execution
- scheduler, worker, queue, or DAG
- model-generated review
- automatic gate decision

## Boundary

P23 does not modify the frozen P15-P20 attention files:

- `frontend/src/components/research/snapshotReviewNoteRollup.js`
- `frontend/src/components/research/gateReviewSnapshotAttentionContext.js`
- `frontend/src/components/research/GateReviewSnapshotAttentionContext.vue`

P23 does not reuse `frontend/src/pages/ReviewPage/ReviewPage.vue` as production truth.

## Validation

P23 should pass:

- targeted Review Workspace page tests
- sidebar and route tests
- P20-P23 guard tests
- full frontend tests
- frontend build
- browser validation for direct URL, reload, sidebar navigation, asset-index visibility, no mutation controls, and no prototype copy

## Recommended P24

Recommended P24:

`Research Review Workspace Review History Read-Only Timeline Baseline`

P24 may add a read-only review history timeline with existing `listReviewHistory`, but should still avoid readiness scoring, workflow/assignment, model runtime, scheduler/queue behavior, gate decisions, and mutation controls.
