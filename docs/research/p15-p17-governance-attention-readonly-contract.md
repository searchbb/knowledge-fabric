# P15-P17 Governance Attention Read-Only Context Contract

Date: 2026-04-30

## Purpose

The GovernanceReview attention context helps a human reviewer understand active snapshot-review-note evidence while reading a GovernanceReview. It is an explanatory review surface, not a workflow engine, task list, gate decision system, or runtime orchestrator.

## Source Of Truth

- Raw `snapshot_review_notes` are the current-state source of truth for note disposition.
- Immutable review history is the audit source of truth.
- `snapshotReviewNoteRollup` and `gateReviewSnapshotAttentionContext` outputs are derived, disposable frontend projections.
- No persisted rollup, durable traceability asset, or backend-owned read model exists for P15-P17.

## Status Semantics

- Active attention statuses: `open`, `acknowledged`, `deferred`.
- Counted but hidden from active preview: `resolved`.
- Active attention count is `open + acknowledged + deferred`.
- Unknown note statuses are normalized by the P15 rollup helper before P16/P17 context projection.

## Snapshot Inclusion Semantics

- Snapshots linked to the current GovernanceReview are included even when active attention is zero.
- Project-context snapshots are included only when active attention is greater than zero.
- Resolved-only project-context snapshots are excluded from the GovernanceReview attention context.
- Snapshot ordering keeps linked snapshots before project-context snapshots.

## Trace Semantics

`trace_ref` is derived from the source snapshot and source snapshot review note. It is explanatory metadata only.

Required trace flags:

- `readonly = true`
- `affects_gate_readiness = false`

Trace target fallback:

- Missing `target_ref` renders as `Section: Unspecified section`.
- Section-only targets render the section.
- Section plus asset targets render section and asset kind/id.
- Section plus asset plus field targets render all three.

Trace metadata must not invent durable IDs, assignments, workflow state, readiness verdicts, or gate decisions.

## Rendering Contract

The GovernanceReview attention context renders:

- disposition counts
- linked/project snapshot context
- active note preview
- plain-text `Source`
- plain-text `Target`
- plain-text `Trace`

The context must not render:

- buttons
- links
- anchors
- deep links
- selected note state
- route params
- jump-to-edit controls
- assignment controls
- workflow actions
- readiness controls

## Boundary

P15-P17 must not add:

- backend endpoint
- dataClient method
- schema field
- durable traceability object
- persisted rollup
- review-history write on render
- workflow, scheduler, worker, queue, or DAG behavior
- model, GPT, Bailian, or deep-research calls
- automatic readiness or gate decisions
- mutation of snapshots, GovernanceReviews, leadership briefings, evidence, insights, decisions, artifacts, or review history
- repair, rollback, export, generation, reminder, or assignment pathways

## Regression Guard

The P18 guard file `frontend/src/components/research/__tests__/gateReviewAttentionReadOnlyContract.spec.js` protects this contract. It covers:

- linked/project snapshot inclusion
- mixed dispositions
- resolved-only snapshots
- missing note id
- missing severity
- missing target metadata
- target section/asset/field display
- top note limit behavior
- trace flags
- source input immutability
- forbidden helper-output capability fields
- passive component rendering with no buttons or links
- absence of runtime/router/dataClient/workflow imports in the P15-P17 read-only production files

## P19 Golden Fixture

The P19 golden fixture file `frontend/src/components/research/__tests__/fixtures/gateReviewAttentionGoldenCase.js` is a test-only canonical evidence case. It freezes representative helper semantics as stable slices rather than a full output schema.

The golden fixture asserts:

- included snapshot identities
- linked versus project-context relation counts
- active and resolved note totals
- active note ordering
- section-only, section+asset, section+asset+field, and missing-target display labels
- trace source/target/read-only slices
- unknown status normalization into active `open` attention
- input immutability and absence of runtime capability fields

The golden fixture does not define a production API, durable read model, persisted traceability object, UI snapshot, or backend contract. Raw `snapshot_review_notes` and immutable review history remain the source of truth.
