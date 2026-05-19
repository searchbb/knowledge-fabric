# P25 Research Review Workspace Boundary Hardening

Date: 2026-04-30

## Status

P25 hardens the P22-P24 Review Workspace boundary with documentation and contract tests.

P25 adds no new product behavior. It exists to make the current Research Review Workspace enforceably read-only before P26 declares the design line complete.

## Contract

The Review Workspace at `/workspace/research/review` is a bounded inspection surface.

It may show:

- strategic research projects
- existing GovernanceReview assets per project
- existing ResearchSnapshot assets per project
- latest 5 review history entries per project
- passive unavailable or empty states for missing project sections
- navigation back to existing strategic research assets

It must remain:

- read-only
- project-first
- existing-API-only
- passively failure-isolated by project section
- separate from the legacy `ReviewPage.vue` prototype
- separate from the frozen P15-P20 attention context
- separate from traceability, readiness, workflow, assignment, model runtime, scheduler, queue, worker, DAG, and automatic gate decision surfaces

## Existing APIs Only

The production Review Workspace may use only these frontend data-client methods:

- `listResearchProjects`
- `listGovernanceReviews`
- `listResearchSnapshots`
- `listReviewHistory`

P25 does not add:

- backend endpoint
- dataClient method
- schema or migration
- persistence model
- persisted Review Workspace read model
- task, job, scheduler, worker, queue, or DAG API
- model runtime API
- mutation API

## Read-Only UI Boundary

The Review Workspace may include negative boundary copy that says what it is not.

It must not include positive controls or capability language for:

- approve or reject
- submit or sign off
- assign or route work
- start, run, execute, schedule, or repair workflow
- evaluate readiness or compute readiness score
- execute model-assisted review
- decide gate outcome automatically
- edit review history
- create, update, or delete review assets

The page must not render forms, inputs, textareas, selects, contenteditable regions, mutation buttons, or role-button controls in the Review Workspace content.

## Review History Boundary

Review history remains a passive factual timeline.

The page must call:

`listReviewHistory(project.id, { limit: 5 })`

History entries remain grouped under project context. If one project's history request fails, existing project assets and other project sections remain visible.

P25 does not introduce a persisted timeline or read-model API.

## Prototype Isolation

The production Review Workspace must not import, reuse, redirect to, or render copy from:

`frontend/src/pages/ReviewPage/ReviewPage.vue`

That page remains a legacy/prototype surface and is not production truth for Research Review Workspace.

## Frozen Attention Boundary

P25 does not reopen or depend on the frozen P15-P20 attention production files:

- `frontend/src/components/research/snapshotReviewNoteRollup.js`
- `frontend/src/components/research/gateReviewSnapshotAttentionContext.js`
- `frontend/src/components/research/GateReviewSnapshotAttentionContext.vue`

The P15-P20 attention context remains a closed, read-only frontend-derived review aid.

## Route and Sidebar Boundary

The route remains:

`/workspace/research/review`

The route component remains:

`ResearchReviewWorkspacePage`

The sidebar entry remains:

`Review Workspace`

The Review Workspace route must not redirect to the registry review tab, the legacy `ReviewPage.vue` prototype, or any readiness/workflow/model surface.

## Validation

P25 should pass:

- P25 boundary contract tests
- existing Review Workspace page tests
- AppSidebar route-entry tests
- router tests
- P20-P25 guard tests
- full frontend tests
- frontend build
- browser validation for direct URL, reload, sidebar navigation, asset-index visibility, timeline visibility, no mutation controls, no prototype copy, and no console errors

## Recommended P26

Recommended P26:

`Research Review Workspace Design Completion / Exit Criteria Baseline`

P26 should be docs/tests-only by default. It should declare the current Review Workspace product design boundary complete and explicitly defer traceability, readiness evaluator, workflow or assignment, model-assisted review runtime, scheduler, queue, worker, DAG, automatic gate decision, persisted read model, and hidden mutations.
