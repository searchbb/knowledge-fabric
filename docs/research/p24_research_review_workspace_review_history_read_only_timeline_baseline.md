# P24 Research Review Workspace Review History Read-Only Timeline Baseline

Date: 2026-04-30

## Status

P24 adds a read-only recent review history timeline to the Review Workspace at `/workspace/research/review`.

It remains a factual timeline, not a readiness evaluator, workflow surface, assignment system, traceability summary, model-assisted review runtime, or gate decision system.

## Scope

P24 displays recent review history entries by project.

For each indexed project, P24 may show:

- latest 5 review history entries
- event label
- timestamp
- asset type
- asset title or id
- actor label when present
- summary, note, or comment when present

P24 keeps P23's project-first asset index visible.

## Existing API

P24 uses existing frontend data-client methods only:

- `listResearchProjects`
- `listGovernanceReviews`
- `listResearchSnapshots`
- `listReviewHistory`

P24 calls `listReviewHistory(projectId, { limit: 5 })`.

P24 does not add:

- backend endpoint
- dataClient method
- schema or persistence model
- persisted Review Workspace read model
- mutation API

## UI Contract

The timeline may display neutral factual labels:

- Recent review history
- Showing latest 5 review history entries.
- Review history unavailable for this project. Existing project assets remain visible.
- No review history found for this project.

The timeline must not display controls or language that implies:

- readiness score
- required action
- assignment owner
- workflow execution
- scheduler, worker, queue, or DAG
- model-generated review
- automatic gate decision

## Boundary

P24 does not modify the frozen P15-P20 attention files:

- `frontend/src/components/research/snapshotReviewNoteRollup.js`
- `frontend/src/components/research/gateReviewSnapshotAttentionContext.js`
- `frontend/src/components/research/GateReviewSnapshotAttentionContext.vue`

P24 does not reuse `frontend/src/pages/ReviewPage/ReviewPage.vue` as production truth.

P24 does not add traceability summary. Traceability remains a separately designed future surface.

## Validation

P24 should pass:

- targeted Review Workspace page tests
- route/sidebar tests
- P20-P24 guard tests
- full frontend tests
- frontend build
- browser validation for direct URL, reload, sidebar navigation, asset-index visibility, timeline visibility, no mutation controls, and no prototype copy

## Recommended P25

Recommended P25:

`Research Review Workspace Read-Only Boundary Hardening`

Before adding traceability, P25 should harden P22-P24 boundaries with docs/tests so the Review Workspace does not drift toward readiness scoring, workflow, assignment, model runtime, or traceability-as-coverage semantics.
