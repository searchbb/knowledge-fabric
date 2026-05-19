# KFC Research Pipeline Architecture

Status: P0 documented. This document separates the current repo baseline from planned P1-P4 capabilities.

## 1. Architecture Principle

KFC records the state of research. Codex drives the workflow. GPT reviews design and acceptance. External skills provide capabilities. Humans approve strategic judgment.

KFC is a knowledge and strategic research asset repository. It should expose structured APIs and workspace views for research assets, but it must not become a universal Agent scheduler.

Codex is the local orchestrator. It owns workflow execution, local code changes, tests, model or skill calls, material generation, and writeback coordination.

## 2. Current Repo Baseline

Existing facts from the current checkout:

- Backend: Flask application factory in `backend/app/__init__.py`.
- Backend API style: Flask blueprints returning JSON responses.
- Registered backend areas: graph, simulation, report, review, concept, theme, evolution, registry, auto pipeline, discover jobs, LLM mode config, vault, article raw.
- Backend persistence style: JSON sidecars under `backend/data/` for several existing systems, plus project files under existing project storage.
- Backend tests: pytest tests under `backend/tests`.
- Frontend: Vue 3, Vue Router, Vite, Vitest.
- Frontend workspace routes: `/workspace/overview`, `/workspace/registry`, `/workspace/themes`, `/workspace/relations`, `/workspace/auto`, `/workspace/discover`, and project workspace pages.
- Current public framing: Knowledge Fabric Center - A Knowledge Workspace for Research and Insight.
- Current product pipeline: article or document import, semantic graph, reading skeleton, concept registry, theme hub, discover jobs.
- Current docs: minimal docs folder with overview image only before P0.

P0 does not change any backend or frontend product code.

## 3. Target Research Pipeline

Target flow:

```text
User strategic topic
-> Codex orchestration
-> GPT design consultation
-> KFC ResearchProject asset creation
-> Local knowledge retrieval from KFC
-> Codex-called Bailian or deep research skills
-> Evidence writeback
-> GPT Thinking cross-check
-> Insight and option formation
-> Codex-called draw.io or artifact skills
-> KFC artifact and review decision storage
```

For the sample topic:

```text
Huawei Cloud Agent-ready enterprise software stack strategy research
华为云 Agent-ready 企业软件栈战略研究
```

KFC should eventually preserve the trace from evidence to signal to insight to option to artifact.

## 4. Responsibility Boundaries

| Role | Owns | Does Not Own |
| --- | --- | --- |
| KFC | Research assets, provenance, structured APIs, workspace views, review decisions | Universal Agent scheduler, model router, generic workflow DAG engine, direct deep research orchestration |
| Codex | Local orchestration, repo inspection, code edits, tests, GPT and skill calls, writeback coordination | Long-term source of truth for research assets |
| GPT Pro | High-stakes strategic framing, option review, material acceptance advice | Direct repo changes or unverified product claims |
| GPT Thinking | Stage design, structure review, gap analysis, acceptance review | Replacing local tests or human decisions |
| Bailian | Low-cost summarization, cleanup, coarse extraction, simple comparisons when called by Codex | Final strategic judgment |
| Deep research skill | External source discovery and research packs when called by Codex | Directly accepted conclusions |
| draw.io skill | Editable diagram draft generation and visual review support when called by Codex | Product state or evidence truth |
| Human reviewer | Final strategic judgment, evidence acceptance, artifact wording | Routine local execution |

## 5. Data Boundary

| Status | Data Scope |
| --- | --- |
| Existing | Article projects, graph data, registry, themes, discover jobs, relations, notes, workspace views |
| P0 documented | Research lifecycle, architecture boundary, GPT gate process |
| Planned P1 | Minimal ResearchProject sidecar or equivalent store |
| Planned P2 | Local Evidence Pack and coverage/gap maps |
| Planned P3 | Controlled Codex/skill writeback contracts and consultation logs |
| Planned P4 | Evidence Matrix, Insight Board, Artifact Studio, traceability links |
| Out of scope | Generic agent runtime, model scheduler, multi-agent debate engine, workflow DAG platform |

P0 must not lock a complete schema. P1 should validate the smallest durable ResearchProject model against the existing repository style.

## 6. API Boundary

| Stage | API Status |
| --- | --- |
| P0 | No API changes |
| Planned P1 | Candidate ResearchProject create/list/read/update APIs |
| Planned P2 | Candidate local retrieval and local evidence pack APIs |
| Planned P3 | Candidate writeback APIs for Codex-run skills and consultation logs |
| Planned P4 | Candidate APIs for matrix, insight, option, artifact, and review decisions |

KFC APIs should accept structured research assets. They should not directly run GPT, Bailian, deep research, or draw.io.

## 7. Non-Scheduler Rule

KFC must not implement:

- Universal Agent scheduler.
- Generic workflow DAG engine.
- Model router.
- Cron-like executor for research tasks.
- Multi-agent debate runtime.
- Direct GPT/Bailian/deep research/draw.io orchestration.

Allowed KFC behavior:

- Store research asset state.
- Validate payload shape.
- Preserve source references.
- Expose read/write APIs.
- Display reviewable workspace surfaces.
- Record consultation and writeback logs submitted by Codex.

## 8. P1-P4 Roadmap

### Planned P1: Minimal ResearchProject

Intent:

- Add the minimal backend store and API for a human-initiated research task.
- Add a basic frontend entry and detail page if implementation scope permits.

Candidate outputs:

- ResearchProject model.
- Create/list/read/update API.
- Project detail view with research definition and issue tree.

Validation focus:

- Persistence across reload.
- No conflict with existing article Project.
- No scheduler responsibilities.

Not implemented in P0.

### Planned P2: Local Evidence Pack

Intent:

- Connect ResearchProject to existing KFC themes, concepts, articles, and relations.
- Generate local evidence candidates and gaps.

Candidate outputs:

- Local retrieval API.
- EvidenceItem store.
- Local Evidence Pack view.

Validation focus:

- Every evidence item has source reference.
- Empty retrieval returns empty results, not fabricated evidence.
- Evidence is project-linked.

Not implemented in P0.

### Planned P3: Codex/Skill Writeback

Intent:

- Let Codex write external research, GPT consultation, and stage run logs back to KFC through controlled APIs.

Candidate outputs:

- Writeback API.
- ConsultationLog.
- ResearchRun.
- Dry-run capable Codex scripts.

Validation focus:

- Writeback has source, stage, timestamp, and idempotency or clear duplicate behavior.
- KFC still does not call external models directly.

Not implemented in P0.

### Planned P4: Research Workbench Surfaces

Intent:

- Add Evidence Matrix, Insight Board, and Artifact Studio.

Candidate outputs:

- Evidence Matrix.
- Insight Cards.
- Strategic Options.
- Artifact Drafts.
- Review Decisions.

Validation focus:

- Insight and artifact trace back to evidence.
- Codex never overwrites user-edited material without conflict handling.

Not implemented in P0.

## 9. Architecture Decision Records

### ADR-001: KFC Remains A Research Asset Repository

Decision:

- KFC stores structured research assets and provenance.

Reason:

- Long-term value comes from reusable evidence, insight, option, and artifact assets.

Consequence:

- KFC APIs should focus on durable state, not tool orchestration.

### ADR-002: Codex Owns Orchestration

Decision:

- Codex drives GPT calls, skill calls, tests, material generation, and writeback.

Reason:

- Research workflows change quickly and are better handled by local execution and skills.

Consequence:

- KFC should receive structured outputs from Codex rather than directly running external tools.

### ADR-003: GPT Gates Every Stage

Decision:

- Each development stage requires GPT design consultation before implementation and GPT acceptance review after local validation.

Reason:

- The user requires stage-level design advice, test cases, and acceptance before moving forward.

Consequence:

- Stage completion requires both local validation and GPT `Acceptance: PASS`.

### ADR-004: P0 Is Documentation Only

Decision:

- P0 creates architecture and process documents only.

Reason:

- The implementation boundary must be clear before product changes.

Consequence:

- P0 must not change backend, frontend, data, or scripts.
