# Research Playbook

Status: P0 documented. This playbook defines the target strategic research workflow. It does not mean the P1-P4 product capabilities are implemented.

## 1. Purpose

Knowledge Fabric Center (KFC) is the knowledge and strategic research asset repository for research work. It stores traceable research assets and later exposes structured APIs and workspace views.

Codex drives the local workflow. Codex reads this playbook, inspects the repo, calls external skills or models when appropriate, writes files, runs tests, and writes structured results back to KFC when the relevant APIs exist.

KFC must not become a universal Agent scheduler. Model routing, deep research execution, draw.io generation, and one-off workflow orchestration belong in Codex or skills.

## 2. Example Topic

All stages should be validated against this sample topic:

- English: Huawei Cloud Agent-ready enterprise software stack strategy research
- Chinese: 华为云 Agent-ready 企业软件栈战略研究

The sample is a validation scenario, not a hard-coded product domain.

## 3. Research Lifecycle

The target lifecycle is:

```text
Research Topic
-> Problem Definition
-> Issue Tree
-> Local Knowledge Retrieval
-> External Deep Research
-> Cross-check and Gap Review
-> Evidence Matrix
-> Signal
-> Insight
-> Strategic Question
-> Option
-> Plan
-> Artifact
-> Review Decision
```

### A. Define Problem

Input:

- A leader-provided strategic research topic.
- Known audience, decision context, and time horizon when available.

Activity:

- Codex asks GPT Pro or GPT Thinking for problem framing when the stage gate requires it.
- Human reviewer confirms the real decision question.

Output:

- Research Brief.
- Core question.
- Non-goals and known controversy points.

Stored assets planned for P1:

- `ResearchProject.research_brief`
- `ResearchProject.goal`
- `ResearchProject.audience`

### B. Decompose Research Questions

Input:

- Research Brief.

Activity:

- Build an issue tree before retrieval.
- Separate strategic questions from evidence questions.

Output:

- Issue Tree.
- Subtopics.
- Evidence needs.

Stored assets planned for P1:

- `ResearchProject.issue_tree`
- `ResearchProject.subtopics`

### C1. Local Knowledge Retrieval

Input:

- ResearchProject topic, goal, subtopics, and issue tree.

Activity:

- KFC local retrieval is planned to search existing articles, themes, concepts, relations, registry entries, and prior materials.
- Bailian may be called by Codex outside KFC to summarize local evidence candidates.

Output:

- Local Evidence Pack.
- Coverage Map.
- Gap Map.

Stored assets planned for P2:

- `EvidenceItem` with `source_type=local`.
- `CoverageMap`.
- `GapMap`.

### C2. External Deep Research

Input:

- Gap Map from local retrieval.

Activity:

- Codex may call deep research skills outside KFC.
- External results enter KFC only as evidence candidates with source metadata, not as accepted conclusions.

Output:

- External Research Pack.
- External Evidence candidates.
- Conflicts with local knowledge.

Stored assets planned for P3:

- `EvidenceItem` with `source_type=deep_research` or `web`.
- `ConsultationLog`.
- `ResearchRun`.

### D. Cross-check and Gap Review

Input:

- Local Evidence Pack.
- External Research Pack.

Activity:

- GPT Thinking may compare local and external evidence.
- Human reviewer decides which evidence is reliable enough to support insights.

Output:

- Evidence Matrix.
- Contradictions.
- Remaining gaps.

Stored assets planned for P4:

- `EvidenceMatrix`.
- `ReviewDecision`.

### E. Signal Extraction

Input:

- Validated evidence clusters.

Activity:

- Convert repeated evidence patterns into signals.

Output:

- Signals with evidence references.

Stored assets planned for P4:

- `Signal`.

### F. Insight Formation

Input:

- Evidence and signals.

Activity:

- Form strategy-relevant claims.
- Record supporting evidence and counter-evidence.

Output:

- Insight Cards.

Stored assets planned for P4:

- `InsightCard`.

### G. Strategic Questions

Input:

- Accepted insights.

Activity:

- Convert insights into questions that leadership needs to decide.

Output:

- Strategic Questions.

Stored assets planned for P4:

- `StrategicQuestion`.

### H. Options and Recommendations

Input:

- Strategic Questions.

Activity:

- GPT Pro may help form options and recommendations.
- Human reviewer confirms whether the recommendation is appropriate for the audience.

Output:

- Strategic Options.
- Risks.
- Validation plan.

Stored assets planned for P4:

- `StrategicOption`.
- `Plan`.

### I. Artifact Preparation

Input:

- Accepted insights, options, and plans.

Activity:

- Codex may call draw.io or presentation skills outside KFC.
- KFC stores artifact drafts, source insights, screenshots, review comments, and version notes.

Output:

- PPT outline.
- Memo.
- Q&A.
- draw.io page draft.

Stored assets planned for P4:

- `ArtifactDraft`.
- `ReviewDecision`.

## 4. Stage Inputs and Outputs

| Stage | Input | Output | Stored Asset Status |
| --- | --- | --- | --- |
| Problem Definition | Research topic | Research Brief | Planned P1 |
| Issue Tree | Research Brief | Issue Tree, subtopics | Planned P1 |
| Local Retrieval | Topic and issue tree | Local Evidence Pack | Planned P2 |
| External Research | Gap Map | External Research Pack | Planned P3 |
| Cross-check | Local and external evidence | Evidence Matrix | Planned P4 |
| Insight Formation | Evidence and signals | Insight Cards | Planned P4 |
| Options | Strategic questions | Options and plan | Planned P4 |
| Artifact | Accepted insights and options | Draft material | Planned P4 |

## 5. Planned Research Asset Types

These are target asset types. P0 documents intent only.

- `ResearchProject`: human-initiated strategic research task.
- `ResearchBrief`: problem definition, audience, goal, and scope.
- `IssueTree`: decomposition of questions and subtopics.
- `EvidenceItem`: traceable local, web, deep research, or manual evidence candidate.
- `EvidencePack`: grouped evidence for a project and stage.
- `Signal`: pattern derived from evidence.
- `InsightCard`: strategy-relevant claim with support and counter-evidence.
- `StrategicQuestion`: decision question for leadership.
- `StrategicOption`: possible strategic path with benefits, risks, and validation plan.
- `ArtifactDraft`: PPT outline, memo, Q&A, draw.io page, or related draft.
- `ReviewDecision`: accept, reject, revise, or defer decision with rationale.
- `ConsultationLog`: GPT or external skill consultation record.

## 6. Human Review Points

Human review is required before:

- Accepting the real strategic question.
- Marking evidence as material-ready.
- Promoting signals into insights.
- Selecting strategic options.
- Approving final artifact wording.
- Treating external research as more than evidence candidates.

## 7. Sample Walkthrough

Topic:

```text
华为云 Agent-ready 企业软件栈战略研究
```

Problem Definition:

```text
判断华为云在 Agent 时代应该控制企业软件栈的哪一层，以及 90 天内如何验证。
```

Issue Tree:

```text
华为云 Agent-ready 企业软件栈战略研究
├── 为什么现在是战略窗口？
├── 企业软件入口发生什么变化？
├── 不能只做什么？
├── 战略控制点在哪里？
├── AgentArts、CodeArts、DataArts、ModelArts 如何重组？
└── 90 天如何验证？
```

Local Evidence Pack planned for P2:

- Existing themes about Agent architecture, MCP, CLI plus skills, tool search, context compression, safety/action layers, and enterprise harness.

External Research Pack planned for P3:

- Agent governance.
- Agent sprawl.
- OWASP LLM excessive agency.
- Enterprise permissions, audit, identity, and tool execution control.

Artifact planned for P4:

- Five-page strategy outline.
- One draw.io sample page.
- Backup Q&A.

## 8. What KFC Stores vs What Codex Executes

KFC stores:

- ResearchProject state.
- Evidence, signals, insights, options, plans, artifacts, and review decisions.
- Source references and provenance.

Codex executes:

- Stage planning.
- GPT consultation.
- Bailian summarization requests.
- Deep research skill calls.
- draw.io generation.
- File changes, tests, and validation.
- Writeback to KFC when planned APIs exist.

GPT provides:

- Stage design consultation.
- Architecture review.
- Acceptance review.
- Strategic judgment support at key checkpoints.

Bailian provides:

- Low-cost summarization, extraction, evidence cleanup, and simple comparison when Codex calls it.

Deep research skills provide:

- External research packs and source-grounded evidence candidates when Codex calls them.

draw.io skills provide:

- Editable diagram drafts and rendered previews when Codex calls them.

Humans decide:

- Final strategic framing.
- Evidence acceptance.
- Insight acceptance.
- Artifact wording and release readiness.
