# P15-P20 Governance Attention Freeze

Date: 2026-04-30

## Status

The P15-P20 GovernanceReview attention context is complete as a bounded read-only review aid.

It helps a human reviewer see active `snapshot_review_notes` while reading a GovernanceReview. It is a frontend-derived explanation surface, not a workflow engine, task list, readiness evaluator, gate decision system, model runtime, navigation surface, or persisted traceability model.

## Production Surface

The attention context is defined by three production frontend files:

- `frontend/src/components/research/snapshotReviewNoteRollup.js`
- `frontend/src/components/research/gateReviewSnapshotAttentionContext.js`
- `frontend/src/components/research/GateReviewSnapshotAttentionContext.vue`

Host pages and panels may render the component, but they do not redefine the attention contract.

## Source Of Truth

- Raw `snapshot_review_notes` are the current-state source of truth for note disposition.
- Immutable review history is the audit source of truth.
- Rollups, attention previews, and trace labels are disposable frontend projections.
- No backend-owned read model, persisted rollup, durable traceability asset, schema migration, or sidecar write is part of P15-P20.

## Closed Capabilities

P15-P20 may derive and render:

- disposition counts
- active attention counts
- linked versus project-context snapshot context
- active note previews
- read-only Source / Target / Trace labels
- trace flags that state the context is read-only and does not change gate readiness

P15-P20 must not add:

- backend endpoint
- dataClient method
- schema field or migration
- persisted rollup
- durable traceability asset
- review-history write on render
- snapshot or GovernanceReview mutation on render
- route, link, href, jump-to-edit, or navigation control
- button, click handler, emitted event, assignment, reminder, workflow, scheduler, worker, queue, or DAG behavior
- automatic readiness calculation
- gate decision automation
- GPT, Bailian, deep-research, or model runtime call

## Regression Guards

- P18 read-only contract:
  - `frontend/src/components/research/__tests__/gateReviewAttentionReadOnlyContract.spec.js`
- P19 golden fixture:
  - `frontend/src/components/research/__tests__/fixtures/gateReviewAttentionGoldenCase.js`
  - `frontend/src/components/research/__tests__/gateReviewAttentionGoldenCase.spec.js`
- P20 freeze contract:
  - `frontend/src/components/research/__tests__/gateReviewAttentionFreezeContract.spec.js`

The P20 freeze guard protects:

- the known production attention surface
- absence of runtime/router/persistence/model imports in production attention files
- absence of action/navigation/workflow capability fields in helper output
- passive component rendering with no buttons, links, click handlers, or emitted events
- input immutability and read-only disclaimers

## Exit Criteria

The attention line is considered complete when:

- P18 read-only contract tests pass.
- P19 golden fixture tests pass.
- P20 freeze contract tests pass.
- Targeted P15-P20 frontend tests pass.
- Full frontend tests pass.
- Frontend build passes, allowing only the existing Vite large chunk warning.
- GPT acceptance confirms no remaining blocker.

After P20, changes in this line should be limited to bug fixes, fixture maintenance, documentation clarification, or test compatibility updates.

## Future Work Boundary

Any future workflow, navigation, persistence, readiness, assignment, or model-assisted review capability must be designed as a separate product surface.

Examples of separate surfaces:

- Research Review Workspace for reviewer navigation and editing.
- Governance Readiness Evaluator for explicit readiness rules and human approval criteria.
- Review Workflow / Assignment Surface for tasks, reminders, owners, due dates, and queues.
- Model-assisted Governance Review for suggested notes, confidence, provenance, and human acceptance workflows.

These future surfaces must not be hidden inside the P15-P20 read-only attention context.
