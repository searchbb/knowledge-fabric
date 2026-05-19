# P21 GovernanceReview Product Surface Planning

Date: 2026-04-30

## Status

P21 is a docs/tests-only scope-split baseline.

It does not implement a new product surface. It separates possible future GovernanceReview product work from the frozen P15-P20 attention context.

## Relationship To P20

The P15-P20 GovernanceReview attention context is frozen as a closed, frontend-only, read-only human review aid.

P21 must not extend:

- `frontend/src/components/research/snapshotReviewNoteRollup.js`
- `frontend/src/components/research/gateReviewSnapshotAttentionContext.js`
- `frontend/src/components/research/GateReviewSnapshotAttentionContext.vue`

Future GovernanceReview product surfaces must be designed as separate lines with their own source-of-truth, data, UI, and acceptance boundaries.

## Architecture Principle

KFC remains a research asset and provenance repository.

KFC may store:

- research assets
- review artifacts
- evidence references
- reviewer decisions
- provenance
- human-readable status

Codex, skills, and external tools own orchestration and execution.

KFC must not become:

- universal Agent scheduler
- model runtime
- workflow DAG engine
- background worker system
- hidden gate decision service

## Product Surface Split

### 1. Review Workspace

Purpose:

- Provide a human navigation and reading workspace for reviews.
- Organize reviews, evidence, findings, signoffs, provenance, and source assets.

Allowed future ownership:

- read-only navigation
- review detail layout
- evidence and provenance grouping
- links to existing source assets when explicitly scoped
- visible human review context

Source of truth:

- stored research assets
- GovernanceReview sidecar/state
- review history
- evidence references

No-go:

- hidden mutations
- automatic readiness decisions
- assignment or queue execution
- model calls
- scheduler behavior

Recommended next implementation candidate:

- P22 Research Review Workspace Navigation Baseline.

### 2. Readiness Evaluator

Purpose:

- Define explicit human-readable readiness rules and review criteria.
- May eventually compute explainable readiness signals.

Allowed future ownership:

- documented readiness criteria
- explainable rule evaluation
- surfaced blockers and gaps
- human approval criteria

Source of truth:

- GovernanceReview checklist, findings, signoffs, and accepted evidence.
- Review history for audit context.

No-go:

- hidden readiness scoring
- automatic gate decisions
- unreviewed stage advancement
- mutation of review status without an explicit human action

Prerequisite:

- a separate rule contract and acceptance plan.

### 3. Workflow / Assignment

Purpose:

- Define tasks, owners, status transitions, handoffs, reminders, and queues if KFC ever needs operational review workflow.

Allowed future ownership:

- explicit task records
- owner and due-date metadata
- visible status transitions
- audit trail for human actions

Source of truth:

- a separately scoped workflow model, if approved.

No-go:

- background execution
- scheduler, worker, queue, or DAG runtime
- generic Agent orchestration
- implicit assignment from attention notes
- automatic status changes without a user-visible action and audit trail

Risk:

- This surface has the highest risk of turning KFC into an orchestration runtime. It should not be implemented until a specific workflow need is validated.

### 4. Model-assisted Review

Purpose:

- Let Codex or external skills produce suggested review notes, evidence summaries, gap analysis, or model-assisted critique outside KFC runtime.

Allowed future ownership:

- imported suggestions
- provenance for model-assisted outputs
- confidence and limitation metadata
- human acceptance or rejection records

Source of truth:

- model outputs submitted by Codex/skills as imported artifacts.
- human decisions stored in KFC.

No-go:

- GPT, Bailian, deep-research, or model calls from KFC runtime
- hidden prompt execution
- automatic acceptance of model output
- replacement of human strategic judgment

## P21 No Runtime Changes

P21 adds no:

- backend endpoint
- dataClient method
- schema change
- persistence model
- sidecar write
- frontend route
- product-visible UI behavior
- runtime workflow
- scheduler, worker, queue, or DAG
- assignment engine
- readiness engine
- automatic gate decision
- GPT, Bailian, deep-research, or model runtime call

Existing `ReviewPage.vue` and `frontend/src/components/review/*` remain prototype surfaces. P21 does not treat them as proof of a completed ReviewTask product model.

## Acceptance Criteria

P21 is complete when:

- this planning document exists
- P15-P20 attention context is explicitly preserved as frozen
- the four future product surfaces are named and separated
- each surface has purpose, allowed future ownership, source-of-truth, and no-go boundaries
- KFC's role as research asset/provenance repository is preserved
- Codex/skills/external tools remain responsible for orchestration and execution
- a lightweight contract test protects the planning boundaries
- no production code is changed
- targeted frontend validation passes
- GPT acceptance confirms no blocker

## Recommended P22

Recommended P22:

`Research Review Workspace Navigation Baseline`

P22 should be a separate read-only product surface. It should focus on reviewer navigation and context layout, not readiness, workflow, assignment, or model assistance.

P22 should not:

- modify the frozen P15-P20 attention files
- add a readiness evaluator
- add assignment or workflow execution
- add model runtime calls
- add scheduler, worker, queue, or DAG behavior
