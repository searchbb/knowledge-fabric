# KFC / Codex / GPT Gate Process

Status: P0 documented. This process is mandatory for P1-P4 development unless the user explicitly changes it.

## 1. Purpose

This gate process keeps Knowledge Fabric Center development stage-based, reviewable, and locally verifiable.

Every stage follows:

```text
Gate A: GPT Design Consultation
-> Gate B: Codex Local Repo Inspection
-> Gate C: Implementation Plan
-> Gate D: Local Implementation
-> Gate E: Local Validation
-> Gate F: GPT Acceptance Review
-> Gate G: User Report / Next Stage
```

Local tests do not replace GPT acceptance. GPT acceptance does not replace local tests. A stage can finish only when both pass.

## 2. Mandatory Stage Loop

### Gate A: GPT Design Consultation

Before coding a stage, Codex must ask GPT for:

- Minimal stage scope.
- Recommended design.
- Files likely to change.
- API, data, UI, or script shape when relevant.
- Test cases.
- Acceptance criteria.
- Non-goals.
- Scope creep warnings.

The prompt must include:

- Current stage.
- Previous stage completion summary.
- Verified repo facts.
- Current product intent.
- Sample topic: Huawei Cloud Agent-ready enterprise software stack strategy research / 华为云 Agent-ready 企业软件栈战略研究.
- Explicit statement that KFC is not a universal Agent scheduler.

### Gate B: Codex Local Repo Inspection

After GPT design consultation and before implementation, Codex must inspect the local repo.

Required inspection:

- Current branch and working tree.
- Relevant backend services, models, APIs, and tests.
- Relevant frontend routes, pages, stores, APIs, and tests.
- Existing persistence conventions.
- Existing naming, error handling, and response style.
- Any untracked or unrelated user files that must not be touched.
- Compatibility risks with current Knowledge Fabric flows.
- Whether GPT advice conflicts with local evidence.

Codex must form an implementation note:

```text
Stage:
GPT design summary:
Repo inspection summary:
Reuse:
New files:
Modified files:
Compatibility risk:
Data migration need:
Test plan:
Out of scope:
```

### Gate C: Implementation Plan

Codex must convert GPT advice and repo inspection into a small local plan.

The plan must:

- Prefer the smallest locally verifiable change.
- Avoid unrelated refactors.
- Avoid scheduler responsibilities inside KFC.
- Protect user or unrelated worktree changes.
- Include validation commands before implementation starts.

### Gate D: Local Implementation

Codex implements only the current stage scope.

Rules:

- Use existing repo patterns.
- Keep changes narrow.
- Do not rewrite legacy surfaces unless the stage requires it.
- Do not implement future-stage behavior early.
- Do not hide runtime mutation in existing flows.

### Gate E: Local Validation

Codex must collect validation evidence after implementation.

Required evidence:

- Changed files.
- `git status --short`.
- `git diff --name-only`.
- Commands run.
- Test results.
- Data persistence evidence if relevant.
- UI screenshots or visible UI traversal if relevant.
- Codex script integration evidence if relevant.
- Known limitations.
- Confirmation that unrelated untracked files were not touched.

Stage-specific validation:

| Stage | Required Local Validation |
| --- | --- |
| P0 | File existence, keyword, gate completeness, anti-overclaim checks, diff scope |
| P1 | Backend API tests, persistence tests, frontend route/page tests, basic UI flow |
| P2 | Retrieval tests, EvidenceItem source tests, empty-result tests, evidence persistence |
| P3 | Writeback tests, consultation log tests, dry-run script tests, failure behavior |
| P4 | Evidence traceability tests, board/matrix/artifact tests, UI flow validation |

### Gate F: GPT Acceptance Review

After local validation passes, Codex must ask GPT for stage acceptance.

The acceptance prompt must include:

- Stage.
- Prior GPT design consultation summary.
- Implementation summary.
- Changed files.
- Repo inspection summary.
- Test commands and results.
- Sample topic validation.
- Known limitations.
- Scope and non-goal confirmation.

GPT must output:

```text
Acceptance: PASS | FAIL | PASS_WITH_FIXES
Blocking issues:
Non-blocking suggestions:
Scope creep check:
KFC/Codex boundary check:
Missing tests:
Can move to next stage: YES | NO
```

Only `Acceptance: PASS` with `Can move to next stage: YES` is a clean pass.

`PASS_WITH_FIXES` means Codex must evaluate whether the fixes are blocking. If any fix affects the stage done criteria, Codex must fix, revalidate, and request GPT acceptance again.

### Gate G: User Report / Next Stage

Codex reports stage completion to the user only after:

- Local validation passes.
- GPT acceptance returns `PASS`.
- No blocking issues remain.

User report format:

```text
Stage:
Status:
GPT design consultation:
Local implementation:
Local validation:
GPT acceptance:
Sample topic validation:
Changed files:
Next step:
```

## 3. Gate A Prompt Template

```text
Goal
{stage goal}

Current product intent
KFC is a knowledge and strategic research asset repository.
Codex is the local orchestrator.
GPT provides design and acceptance review.
External skills are called by Codex, not scheduled by KFC.

Current stage
{P0/P1/P2/P3/P4}

Previous stage completion
{summary}

Verified repo facts
{repo_summary}

Sample topic
Huawei Cloud Agent-ready enterprise software stack strategy research / 华为云 Agent-ready 企业软件栈战略研究

Question
Please provide detailed design, implementation recommendations, test cases, acceptance criteria, non-goals, and scope creep risks for this stage.

Output format
Use concise Chinese. Provide actionable checklists. End with Consult-End.
```

## 4. Gate F Acceptance Prompt Template

```text
Please act as the Knowledge Fabric stage acceptance reviewer.

Stage:
{P0/P1/P2/P3/P4}

GPT design consultation summary:
{summary}

Implementation summary:
{summary}

Changed files:
{files}

Repo inspection summary:
{summary}

Validation evidence:
- Backend tests: {result}
- Frontend tests: {result}
- Data persistence tests: {result}
- UI flow validation: {result}
- Codex script integration: {result}
- Stage-specific checks: {result}

Sample topic validation:
Huawei Cloud Agent-ready enterprise software stack strategy research / 华为云 Agent-ready 企业软件栈战略研究
{result}

Known limitations:
{limitations}

Please output exactly:
1. Acceptance: PASS | FAIL | PASS_WITH_FIXES
2. Blocking issues:
3. Non-blocking suggestions:
4. Scope creep check:
5. KFC/Codex boundary check:
6. Missing tests:
7. Can move to next stage: YES | NO
End with Consult-End.
```

## 5. PASS Criteria

A stage passes only when all apply:

- GPT design consultation completed.
- Codex local repo inspection completed.
- Implementation stays inside the stage scope.
- Required local validation passes.
- Sample topic validates the stage minimum loop.
- KFC/Codex responsibility boundary remains intact.
- GPT acceptance returns `Acceptance: PASS`.
- GPT acceptance returns `Can move to next stage: YES`.

Direct fail conditions:

- GPT acceptance returns `FAIL`.
- Core local tests fail.
- Data expected to persist does not persist.
- UI is static mock while reported as implemented.
- Evidence, insight, or artifact assets lack source traceability when the stage requires it.
- KFC directly owns universal scheduling, model routing, or multi-agent runtime behavior.
- Codex asks for acceptance without test evidence.
- Stage implementation expands into unrelated future stages.

## 6. P0 Validation Checklist

P0 creates exactly these planned documents:

- `docs/research_playbook.md`
- `docs/kfc_research_pipeline_architecture.md`
- `docs/kfc_codex_gpt_gate_process.md`

File checks:

```bash
test -f docs/research_playbook.md
test -f docs/kfc_research_pipeline_architecture.md
test -f docs/kfc_codex_gpt_gate_process.md
```

Diff scope checks:

```bash
git status --short
git diff --name-only
```

Allowed P0 changed files:

```text
docs/research_playbook.md
docs/kfc_research_pipeline_architecture.md
docs/kfc_codex_gpt_gate_process.md
```

Required keyword checks:

```bash
grep -n "Huawei Cloud Agent-ready" docs/research_playbook.md docs/kfc_research_pipeline_architecture.md docs/kfc_codex_gpt_gate_process.md
grep -n "华为云 Agent-ready" docs/research_playbook.md docs/kfc_research_pipeline_architecture.md docs/kfc_codex_gpt_gate_process.md
grep -n "Bailian" docs/kfc_research_pipeline_architecture.md
grep -n "deep research" docs/kfc_research_pipeline_architecture.md
grep -n "draw.io" docs/kfc_research_pipeline_architecture.md
```

Gate completeness checks:

```bash
grep -n "Gate A" docs/kfc_codex_gpt_gate_process.md
grep -n "Gate B" docs/kfc_codex_gpt_gate_process.md
grep -n "Gate C" docs/kfc_codex_gpt_gate_process.md
grep -n "Gate D" docs/kfc_codex_gpt_gate_process.md
grep -n "Gate E" docs/kfc_codex_gpt_gate_process.md
grep -n "Gate F" docs/kfc_codex_gpt_gate_process.md
grep -n "Gate G" docs/kfc_codex_gpt_gate_process.md
```

Roadmap status checks:

```bash
grep -RniE "Planned P1|Planned P2|Planned P3|Planned P4" docs/*.md
```

Anti-overclaim checks:

```bash
grep -RniE "already supports|自动完成|已支持|内置调度|generic agent scheduler|universal Agent scheduler" docs/*.md
```

If matches appear, they must be in non-goal, out-of-scope, warning, or boundary language.

Optional product regression:

```bash
npm --prefix frontend run build
```

For P0, product test failures are not automatically blocking if the failure is unrelated to documentation-only changes and is recorded clearly.

## 7. P1-P4 Stage Expectations

### Planned P1: Minimal ResearchProject

Required gates:

- GPT design for model, API, persistence, and UI.
- Repo inspection of existing project models, API routes, stores, and page patterns.
- Backend and frontend tests.
- Persistence test across reload.
- Sample topic project can be created and reloaded.

### Planned P2: Local Evidence Pack

Required gates:

- GPT design for retrieval scope and evidence schema.
- Repo inspection of themes, registry, article workspace, and relation services.
- Evidence must include source references.
- Empty retrieval must not fabricate evidence.
- Sample topic local evidence pack can be created.

### Planned P3: Codex/Skill Writeback

Required gates:

- GPT design for writeback contract and consultation logs.
- Repo inspection of API validation and JSON sidecar conventions.
- Dry-run and failure tests for scripts.
- KFC records submissions from Codex but does not call external tools directly.

### Planned P4: Evidence Matrix, Insight Board, Artifact Studio

Required gates:

- GPT design for traceability and conflict handling.
- Repo inspection of workspace UI patterns and store conventions.
- Evidence to signal to insight to artifact traceability tests.
- UI flow validation.
- User edits must not be overwritten silently by Codex writeback.

## 8. Risk Controls

Risk: KFC becomes an Agent platform.

Control:

- All scheduling and external model/tool calls stay in Codex or skills.

Risk: P0 over-designs schemas.

Control:

- P0 names candidate assets but leaves exact P1 schema open for local repo inspection and GPT P1 design.

Risk: Roadmap is written as current product behavior.

Control:

- Future behavior must use `Planned`, `candidate`, `target`, or `not implemented in P0`.

Risk: GPT advice becomes vague.

Control:

- GPT prompts must require files likely to change, tests, non-goals, scope checks, and acceptance criteria.

Risk: GPT acceptance becomes a rubber stamp.

Control:

- Acceptance must include `PASS | FAIL | PASS_WITH_FIXES` and `Can move to next stage: YES | NO`.

Risk: Stage gates slow down small fixes.

Control:

- Full gates apply at stage boundaries. Small internal fixes can be batched into one validation and acceptance review.
