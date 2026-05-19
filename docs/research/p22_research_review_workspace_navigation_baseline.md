# P22 Research Review Workspace Navigation Baseline

Date: 2026-04-30

## Status

P22 adds a separate read-only Review Workspace navigation surface.

It is the first product surface after P21's GovernanceReview surface split. It does not extend the frozen P15-P20 attention context and does not promote the existing Phase 2 `ReviewPage.vue` prototype into the strategic research review product model.

## Route

P22 adds:

- `/workspace/research/review`
- `ResearchReviewWorkspace`
- `frontend/src/pages/research/ResearchReviewWorkspacePage.vue`

The existing strategic research route remains:

- `/workspace/research`

## Scope

The P22 page may:

- list existing strategic research projects
- list existing GovernanceReview summaries for each project through existing frontend data-client methods
- show read-only counts and project/review navigation context
- link back to the existing strategic research surface
- state explicit product boundaries

The P22 page must not:

- mutate GovernanceReviews
- mutate review history
- mutate snapshots or snapshot review notes
- modify the frozen P15-P20 attention files
- implement readiness evaluation
- implement workflow or assignment
- implement model-assisted review
- add backend endpoints, schema, persistence, scheduler, worker, queue, DAG, or model runtime calls
- reuse `frontend/src/pages/ReviewPage/ReviewPage.vue` as the production Review Workspace

## Source Of Truth

P22 uses existing KFC research assets through existing frontend data-client methods:

- `listResearchProjects`
- `listGovernanceReviews`

P22 does not introduce a persisted Review Workspace read model.

## Validation

P22 should be validated with:

- route registration tests
- sidebar navigation tests
- page-level read-only rendering tests
- guard checks that the page does not import the frozen attention context or `ReviewPage.vue`
- full frontend tests and build
- browser validation for sidebar, route, reload, and read-only boundary visibility

## Future Boundary

Recommended P23:

`Research Review Workspace Asset Index Baseline`

P23 may enrich the Review Workspace with a read-only asset index grouped by project, using existing APIs where possible. P23 should still avoid readiness evaluation, workflow/assignment, model-assisted review, scheduler/queue behavior, and new persisted read models unless separately designed and accepted.
