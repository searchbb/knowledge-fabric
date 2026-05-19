# P26 Research Review Workspace Design Completion

Date: 2026-04-30

## Design Line Status: Complete

P26 closes the P22-P26 Research Review Workspace design line.

The completed Review Workspace is a bounded, read-only, project-first research asset and provenance inspection surface.

It is not a runtime orchestration surface, workflow system, readiness evaluator, assignment tool, model runtime, scheduler, or automatic gate-decision system.

## Completed Scope

The completed design includes:

- a dedicated route: `/workspace/research/review`
- a dedicated sidebar navigation entry: `Review Workspace`
- project-first organization
- read-only GovernanceReview asset visibility per project
- read-only ResearchSnapshot asset visibility per project
- latest 5 review history entries per project
- passive failure isolation for unavailable project sections
- no mutation controls
- no prototype reuse from `ReviewPage.vue`
- no dependency on the frozen P15-P20 attention context

## Existing API Boundary

The completed Review Workspace may use only these existing frontend APIs:

- `listResearchProjects`
- `listGovernanceReviews`
- `listResearchSnapshots`
- `listReviewHistory`

No new data-client method is required for this design line.

P26 adds no:

- backend endpoint
- schema or migration
- persistence model
- persisted Review Workspace read model
- localStorage, sessionStorage, indexedDB, or writeback behavior
- scheduler, queue, worker, task, job, or DAG API
- model runtime API
- mutation API

## Read-Only Boundary

The completed surface must not create, update, delete, approve, reject, assign, schedule, score, execute, mutate, persist, sync, save, submit, generate, or automatically decide anything.

Negative boundary copy is allowed when it clarifies what the workspace is not.

Positive controls, forms, hidden edit surfaces, mutation action links, or role-button controls are not part of the completed design.

## Review History Boundary

Review history remains a bounded passive timeline grouped under project context.

The completed surface calls:

`listReviewHistory(project.id, { limit: 5 })`

History failures remain passive and isolated. Existing project assets remain visible when history is unavailable.

## P21 Surface Split

P21 separated GovernanceReview product work into these surfaces:

- Review Workspace
- Readiness Evaluator
- Workflow / Assignment
- Model-assisted Review

P22-P26 closes only the Review Workspace surface.

The other surfaces are intentionally deferred. They are not missing requirements for this completed design line.

## Explicit Deferrals

The following work is deferred beyond the completed Review Workspace line:

- traceability summary
- readiness scoring
- readiness evaluator
- workflow
- assignment
- human approval routing
- scheduler
- queue
- worker
- DAG
- model runtime
- model-assisted review
- automatic gate decision
- persisted read model
- backend-owned review aggregation
- hidden mutation controls
- orchestration inside KFC

These capabilities must not be added as incidental extensions of the Review Workspace line.

## Architectural Boundary

KFC / Knowledge Fabric remains the research asset and provenance repository.

Codex, skills, and external workflow tools own orchestration and execution.

The Review Workspace may inspect existing research assets. It does not own runtime execution.

## Stop Rule

After P26 acceptance, stop the P22-P26 Review Workspace design line.

Future GovernanceReview product capabilities must begin as a new design line with a separate product-surface name, scope, GPT design gate, local validation plan, and GPT acceptance gate.

Examples of future separate design lines:

- Traceability Surface Planning
- Readiness Evaluator Planning
- Workflow / Assignment Surface Planning
- Model-assisted Review Planning

They must not be implemented as more Review Workspace hardening.

## Exit Criteria

This design line is complete when:

- P26 completion documentation exists
- P26 completion contract tests pass
- P20-P26 guard tests pass
- full frontend tests pass
- frontend build passes
- browser read-only scenario passes
- GPT acceptance passes
- no blocker remains in Ralph state

The existing Vite chunk-size warning is not a P26 blocker if unchanged.
