import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

enableAutoUnmount(afterEach)

const listResearchProjects = vi.fn()
const createResearchProject = vi.fn()
const getLocalEvidencePack = vi.fn()
const searchLocalEvidencePack = vi.fn()
const updateLocalEvidenceCandidate = vi.fn()
const listResearchRuns = vi.fn()
const listConsultationLogs = vi.fn()
const listExternalResearchPacks = vi.fn()
const updateExternalResearchCandidate = vi.fn()
const listEvidenceMatrixRows = vi.fn()
const listInsightCards = vi.fn()
const listArtifactDrafts = vi.fn()
const updateEvidenceMatrixRow = vi.fn()
const updateInsightCard = vi.fn()
const updateArtifactDraft = vi.fn()
const listArtifactPacks = vi.fn()
const createArtifactPack = vi.fn()
const updateArtifactPack = vi.fn()
const addArtifactPackItem = vi.fn()
const addArtifactPackPage = vi.fn()
const addArtifactPackFileRef = vi.fn()
const addArtifactPackReviewRound = vi.fn()
const listStrategicOptions = vi.fn()
const createStrategicOption = vi.fn()
const updateStrategicOption = vi.fn()
const listValidationPlans = vi.fn()
const createValidationPlan = vi.fn()
const updateValidationPlan = vi.fn()
const listLeadershipDecisionRecords = vi.fn()
const createLeadershipDecisionRecord = vi.fn()
const updateLeadershipDecisionRecord = vi.fn()
const listLeadershipBriefings = vi.fn()
const createLeadershipBriefing = vi.fn()
const getLeadershipBriefing = vi.fn()
const updateLeadershipBriefing = vi.fn()
const getTraceabilityMap = vi.fn()
const listGovernanceReviews = vi.fn()
const createGovernanceReview = vi.fn()
const getGovernanceReview = vi.fn()
const updateGovernanceReview = vi.fn()
const listReviewHistory = vi.fn()
const getAssetReviewHistory = vi.fn()
const createReviewHistoryNote = vi.fn()
const listResearchSnapshots = vi.fn()
const createResearchSnapshot = vi.fn()
const getResearchSnapshot = vi.fn()
const diffResearchSnapshot = vi.fn()
const listSnapshotReviewNotes = vi.fn()
const createSnapshotReviewNote = vi.fn()
const updateSnapshotReviewNote = vi.fn()
const listTopicClustersWithAggregation = vi.fn()
const getTopicClusterAssetIndex = vi.fn()
const updateResearchProject = vi.fn()

vi.mock('../../data/dataClient', () => ({
  listResearchProjects: (...args) => listResearchProjects(...args),
  createResearchProject: (...args) => createResearchProject(...args),
  getLocalEvidencePack: (...args) => getLocalEvidencePack(...args),
  searchLocalEvidencePack: (...args) => searchLocalEvidencePack(...args),
  updateLocalEvidenceCandidate: (...args) => updateLocalEvidenceCandidate(...args),
  listResearchRuns: (...args) => listResearchRuns(...args),
  listConsultationLogs: (...args) => listConsultationLogs(...args),
  listExternalResearchPacks: (...args) => listExternalResearchPacks(...args),
  updateExternalResearchCandidate: (...args) => updateExternalResearchCandidate(...args),
  listEvidenceMatrixRows: (...args) => listEvidenceMatrixRows(...args),
  listInsightCards: (...args) => listInsightCards(...args),
  listArtifactDrafts: (...args) => listArtifactDrafts(...args),
  updateEvidenceMatrixRow: (...args) => updateEvidenceMatrixRow(...args),
  updateInsightCard: (...args) => updateInsightCard(...args),
  updateArtifactDraft: (...args) => updateArtifactDraft(...args),
  listArtifactPacks: (...args) => listArtifactPacks(...args),
  createArtifactPack: (...args) => createArtifactPack(...args),
  updateArtifactPack: (...args) => updateArtifactPack(...args),
  addArtifactPackItem: (...args) => addArtifactPackItem(...args),
  addArtifactPackPage: (...args) => addArtifactPackPage(...args),
  addArtifactPackFileRef: (...args) => addArtifactPackFileRef(...args),
  addArtifactPackReviewRound: (...args) => addArtifactPackReviewRound(...args),
  listStrategicOptions: (...args) => listStrategicOptions(...args),
  createStrategicOption: (...args) => createStrategicOption(...args),
  updateStrategicOption: (...args) => updateStrategicOption(...args),
  listValidationPlans: (...args) => listValidationPlans(...args),
  createValidationPlan: (...args) => createValidationPlan(...args),
  updateValidationPlan: (...args) => updateValidationPlan(...args),
  listLeadershipDecisionRecords: (...args) => listLeadershipDecisionRecords(...args),
  createLeadershipDecisionRecord: (...args) => createLeadershipDecisionRecord(...args),
  updateLeadershipDecisionRecord: (...args) => updateLeadershipDecisionRecord(...args),
  listLeadershipBriefings: (...args) => listLeadershipBriefings(...args),
  createLeadershipBriefing: (...args) => createLeadershipBriefing(...args),
  getLeadershipBriefing: (...args) => getLeadershipBriefing(...args),
  updateLeadershipBriefing: (...args) => updateLeadershipBriefing(...args),
  getTraceabilityMap: (...args) => getTraceabilityMap(...args),
  listGovernanceReviews: (...args) => listGovernanceReviews(...args),
  createGovernanceReview: (...args) => createGovernanceReview(...args),
  getGovernanceReview: (...args) => getGovernanceReview(...args),
  updateGovernanceReview: (...args) => updateGovernanceReview(...args),
  listReviewHistory: (...args) => listReviewHistory(...args),
  getAssetReviewHistory: (...args) => getAssetReviewHistory(...args),
  createReviewHistoryNote: (...args) => createReviewHistoryNote(...args),
  listResearchSnapshots: (...args) => listResearchSnapshots(...args),
  createResearchSnapshot: (...args) => createResearchSnapshot(...args),
  getResearchSnapshot: (...args) => getResearchSnapshot(...args),
  diffResearchSnapshot: (...args) => diffResearchSnapshot(...args),
  listSnapshotReviewNotes: (...args) => listSnapshotReviewNotes(...args),
  createSnapshotReviewNote: (...args) => createSnapshotReviewNote(...args),
  updateSnapshotReviewNote: (...args) => updateSnapshotReviewNote(...args),
  listTopicClustersWithAggregation: (...args) => listTopicClustersWithAggregation(...args),
  getTopicClusterAssetIndex: (...args) => getTopicClusterAssetIndex(...args),
  updateResearchProject: (...args) => updateResearchProject(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/workspace/research', params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>', props: ['to'] },
}))

import ResearchProjectsPage from '../ResearchProjectsPage.vue'

const localEvidencePack = {
  pack_id: 'lep_demo',
  status: 'draft',
  summary: {
    candidate_count: 2,
    accepted_count: 0,
    degraded_count: 1,
    source_project_count: 1,
    concept_count: 1,
    theme_count: 1,
  },
  accepted_evidence_ids: [],
  rejected_evidence_ids: [],
  candidates: [
    {
      evidence_id: 'ev_demo_harness',
      status: 'candidate',
      evidence_type: 'concept',
      title: '企业级 Harness',
      summary: '企业级 Harness 负责权限、审批、测试和回写。',
      why_matched: ['title_match: Harness'],
      score: 0.91,
      source: { registry: 'global_concept_registry' },
      theme_refs: [{ theme_id: 'theme_demo', name: 'Agent-ready 企业软件栈' }],
      source_refs: [
        {
          project_id: 'proj_source',
          project_name: 'Agent-ready 架构笔记',
          source_text: '企业级 Harness 是执行控制面。',
          degraded: false,
        },
      ],
    },
    {
      evidence_id: 'ev_demo_theme',
      status: 'candidate',
      evidence_type: 'theme',
      title: 'Agent-ready 企业软件栈',
      summary: '围绕 Agent-ready 适配层、企业级 Harness 和行业资产复用的主题。',
      why_matched: ['title_match: Agent-ready'],
      score: 0.73,
      source: { registry: 'global_theme_registry' },
      theme_refs: [],
      source_refs: [],
    },
  ],
}

const externalPacks = [
  {
    pack_id: 'erp_demo',
    title: 'Huawei Cloud Agent-ready external evidence pack',
    source_type: 'deep_research',
    scope: 'C2_external',
    status: 'imported',
    candidate_count: 1,
    accepted_count: 0,
    evidence_candidates: [
      {
        candidate_id: 'ec_demo_harness',
        review_status: 'pending',
        claim: '企业级 Agent 的核心控制点在执行治理外壳。',
        evidence_text: '企业 Agent 需要身份、权限、审批、日志、监控和补救机制。',
        source_refs: ['src_001'],
        confidence: 0.86,
      },
    ],
  },
]

const matrixRows = [
  {
    id: 'emr_demo',
    question: '华为云应控制企业软件栈哪一层？',
    claim: '企业 Agent 的长期控制点在执行控制面。',
    status: 'draft',
    confidence: 'high',
    material_readiness: 'usable',
    supporting_evidence_ids: ['ev_demo_harness', 'ei_demo_harness'],
    counter_evidence_ids: [],
  },
]

const insightCards = [
  {
    id: 'ic_demo',
    title: '执行控制面是长期控制点',
    claim: 'Agent 竞争的长期控制点在企业可执行能力资产和行业复用资产。',
    implication: 'AgentArts 应升级为企业 Agent 工程化平台。',
    status: 'draft',
    confidence: 'high',
    supporting_evidence_ids: ['ev_demo_harness', 'ei_demo_harness'],
    counter_evidence_ids: [],
    matrix_row_ids: ['emr_demo'],
  },
]

const artifactDrafts = [
  {
    id: 'ad_demo',
    artifact_type: 'slide_outline',
    title: '华为云 Agent-ready 企业软件栈战略材料大纲',
    purpose: '形成 5 页领导汇报材料输入。',
    status: 'draft',
    material_readiness: 'outline_only',
    source_insight_ids: ['ic_demo'],
    source_evidence_ids: ['ev_demo_harness'],
    outline: [{ section_id: 's1', title: '战略判断', key_message: '长期控制点上移到执行控制面。' }],
  },
]

const artifactPacks = [
  {
    pack_id: 'ap_demo',
    title: '华为云 Agent-ready 企业软件栈战略汇报材料包',
    pack_type: 'leadership_deck',
    purpose: '面向领导汇报 Agent-ready 企业软件栈战略判断。',
    audience: '华为云战略部二层领导',
    status: 'draft',
    readiness: 'outline_ready',
    source_artifact_draft_ids: ['ad_demo'],
    source_insight_ids: ['ic_demo'],
    source_evidence_ids: ['ev_demo_harness', 'ei_demo_harness'],
    items: [],
    pages: [{
      page_id: 'pg_demo',
      sequence: 1,
      page_title: 'Harness 是企业执行控制面',
      page_type: 'framework',
      page_claim: '权限、审批、日志、评测和回写构成企业控制面。',
      source_insight_ids: ['ic_demo'],
      source_evidence_ids: ['ev_demo_harness'],
      source_matrix_row_ids: ['emr_demo'],
      material_status: 'outlined',
      review_status: 'unreviewed',
    }],
    file_refs: [],
    review_rounds: [],
  },
]

const strategicOptions = [
  {
    option_id: 'so_demo',
    title: 'L2 Agent-ready 适配层 + L4 企业级 Harness 作为战略控制点',
    summary: '将企业系统适配层和执行治理 Harness 作为华为云 Agent-ready 软件栈的战略控制点。',
    option_type: 'strategic_path',
    status: 'under_review',
    recommendation_level: 'recommended',
    decision_posture: 'need_validation',
    source_insight_ids: ['ic_demo'],
    source_evidence_matrix_row_ids: ['emr_demo'],
    source_evidence_ids: ['ev_demo_harness'],
    risks: [{ statement: '首客深交付可能难以复用。' }],
    success_metrics: [{ name: 'harness_reuse_ratio' }],
  },
]

const validationPlans = [
  {
    plan_id: 'vp_demo',
    title: '90-day ERP/Test Harness pilot validation',
    summary: '验证企业级 Agent Harness 是否能成为华为云 Agent-ready 软件栈控制点。',
    status: 'under_review',
    plan_type: 'pilot_validation',
    approval_state: 'ready_for_review',
    linked_option_ids: ['so_demo'],
    validation_questions: [{ question: '客户是否愿意接入真实权限和审批？' }],
    validation_methods: [{ method_type: 'customer_pilot', execution_location: 'external' }],
    milestones: [{ name: 'Week 2 first business action' }],
    metrics: [{ name: 'harness_reuse_ratio' }],
  },
]

const decisionRecords = [
  {
    decision_id: 'ldr_demo',
    title: 'Decision on Agent-ready enterprise software stack control point',
    decision_status: 'needs_revision',
    decision_type: 'strategic_direction',
    decision_summary: '建议优先投入 L2 Agent-ready 适配层与 L4 企业级 Harness。',
    linked_option_ids: ['so_demo'],
    linked_validation_plan_ids: ['vp_demo'],
    chosen_option_id: 'so_demo',
    rationale: [{ statement: 'L2 + L4 更贴近企业落地。' }],
    review_rounds: [{
      round_id: 'lrr_demo',
      reviewer: 'VP-level reviewer',
      decision: 'needs_revision',
      blocking: true,
      resolved: false,
    }],
  },
]

const leadershipBriefings = [
  {
    briefing_id: 'lb_demo',
    title: 'Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout',
    briefing_type: 'strategic_readout',
    audience: 'cloud_strategy_leadership',
    status: 'in_review',
    readiness: 'ready',
    section_count: 4,
    source_counts: { insight_cards: 1, strategic_options: 1 },
  },
]

const leadershipBriefingDetail = {
  ...leadershipBriefings[0],
  purpose: 'Prepare leadership discussion on Agent-ready enterprise software stack strategy.',
  executive_summary: {
    headline: 'Enterprise AI competition is moving to Agent-ready software stack control points.',
    key_message: 'Huawei Cloud should focus on L2 Agent-ready adaptation and L4 enterprise Harness.',
    leadership_ask: 'Approve 90-day ERP/Test Harness pilots and control-layer investment priorities.',
    decision_required: true,
  },
  source_asset_refs: [{ asset_type: 'insight_card', asset_id: 'ic_demo', required: true }],
  sections: [
    {
      section_id: 'lbs_demo_1',
      order: 1,
      title: 'Why now',
      section_type: 'context',
      summary: 'Agent operations are becoming a new enterprise software entry point.',
      talking_points: ['The entry point shifts from UI navigation to agent-mediated operations.'],
      source_refs: [{ asset_type: 'insight_card', asset_id: 'ic_demo', required: true }],
      review_state: 'approved',
    },
    {
      section_id: 'lbs_demo_2',
      order: 2,
      title: 'Leadership ask',
      section_type: 'decision_ask',
      summary: 'Align on pilot scope, KPI, and first-customer deep delivery approach.',
      source_refs: [{ asset_type: 'leadership_decision_record', asset_id: 'ldr_demo', required: true }],
      review_state: 'needs_review',
    },
  ],
  decision_asks: [{ ask_id: 'ask_demo', title: 'Approve the first 90-day pilot path', status: 'open' }],
  readiness_checks: {
    has_executive_summary: true,
    has_decision_ask: true,
    all_required_sources_resolved: true,
    has_blocking_review_decisions: false,
  },
  review_rounds: [],
}

const traceabilityMap = {
  project_id: 'rp_de0a00000001',
  generated_at: '2026-04-28T00:00:00Z',
  view_type: 'strategic_research_traceability_map',
  traceability_readiness: 'needs_review',
  summary: {
    node_count: 8,
    edge_count: 7,
    blocking_issue_count: 0,
    warning_issue_count: 1,
    orphan_node_count: 1,
    missing_reference_count: 0,
    briefing_coverage: {
      leadership_briefing_count: 1,
      briefings_with_required_refs: 1,
      briefings_with_blocking_issues: 0,
    },
  },
  lanes: [
    { lane_id: 'evidence', title: 'Evidence', asset_types: ['evidence_item', 'evidence_matrix_row'] },
    { lane_id: 'synthesis', title: 'Synthesis', asset_types: ['insight_card'] },
    { lane_id: 'decision', title: 'Decision', asset_types: ['strategic_option', 'validation_plan', 'leadership_decision_record'] },
    { lane_id: 'materials', title: 'Materials', asset_types: ['artifact_draft', 'artifact_pack'] },
    { lane_id: 'briefing', title: 'Leadership Briefing', asset_types: ['leadership_briefing'] },
  ],
  nodes: [
    { node_id: 'evidence_item:ev_demo_harness', asset_type: 'evidence_item', asset_id: 'ev_demo_harness', title: '企业级 Harness', status: 'accepted', lane_id: 'evidence', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'evidence_matrix_row:emr_demo', asset_type: 'evidence_matrix_row', asset_id: 'emr_demo', title: '华为云应控制企业软件栈哪一层？', status: 'draft', lane_id: 'evidence', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'insight_card:ic_demo', asset_type: 'insight_card', asset_id: 'ic_demo', title: '执行控制面是长期控制点', status: 'draft', lane_id: 'synthesis', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'strategic_option:so_demo', asset_type: 'strategic_option', asset_id: 'so_demo', title: 'L2 Agent-ready 适配层 + L4 企业级 Harness 作为战略控制点', status: 'under_review', lane_id: 'decision', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'validation_plan:vp_demo', asset_type: 'validation_plan', asset_id: 'vp_demo', title: '90-day ERP/Test Harness pilot validation', status: 'under_review', lane_id: 'decision', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'leadership_decision_record:ldr_demo', asset_type: 'leadership_decision_record', asset_id: 'ldr_demo', title: 'Decision on Agent-ready enterprise software stack control point', status: 'needs_revision', lane_id: 'decision', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'artifact_pack:ap_demo', asset_type: 'artifact_pack', asset_id: 'ap_demo', title: '华为云 Agent-ready 企业软件栈战略汇报材料包', status: 'draft', lane_id: 'materials', issue_counts: { blocking: 0, warning: 0, info: 0 } },
    { node_id: 'leadership_briefing:lb_demo', asset_type: 'leadership_briefing', asset_id: 'lb_demo', title: 'Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout', status: 'in_review', readiness: 'ready', lane_id: 'briefing', issue_counts: { blocking: 0, warning: 0, info: 0 } },
  ],
  edges: [
    { edge_id: 'evidence_item:ev_demo_harness->insight_card:ic_demo:supporting_evidence_ids', from_node_id: 'evidence_item:ev_demo_harness', to_node_id: 'insight_card:ic_demo', relation_type: 'supports', source_field: 'supporting_evidence_ids', valid: true },
    { edge_id: 'insight_card:ic_demo->strategic_option:so_demo:source_insight_ids', from_node_id: 'insight_card:ic_demo', to_node_id: 'strategic_option:so_demo', relation_type: 'supports', source_field: 'source_insight_ids', valid: true },
    { edge_id: 'strategic_option:so_demo->validation_plan:vp_demo:linked_option_ids', from_node_id: 'strategic_option:so_demo', to_node_id: 'validation_plan:vp_demo', relation_type: 'plans', source_field: 'linked_option_ids', valid: true },
    { edge_id: 'leadership_decision_record:ldr_demo->leadership_briefing:lb_demo:decision_asks[0].linked_decision_record_ids', from_node_id: 'leadership_decision_record:ldr_demo', to_node_id: 'leadership_briefing:lb_demo', relation_type: 'decides', source_field: 'decision_asks[0].linked_decision_record_ids', valid: true },
  ],
  issues: [{
    issue_id: 'thin_artifact_pack:artifact_pack:ap_demo:source_artifact_draft_ids',
    severity: 'warning',
    issue_type: 'thin_artifact_pack',
    asset_type: 'artifact_pack',
    asset_id: 'ap_demo',
    field: 'source_artifact_draft_ids',
    message: 'Artifact pack has limited material structure.',
  }],
  orphans: [{ node_id: 'evidence_matrix_row:emr_demo', reason: 'No outgoing reference yet.' }],
  filters: { briefing_id: '', asset_type: '', issue_severity: '' },
}

const governanceReviews = [
  {
    review_id: 'gr_demo',
    title: 'P9 strategic research governance review',
    review_type: 'stage_gate',
    status: 'in_review',
    gate_decision: 'not_decided',
    readiness: 'partial',
    checklist_count: 3,
    finding_count: 1,
    signoff_count: 0,
    blocker_count: 0,
    major_open_count: 1,
    failed_required_count: 2,
    ready_for_next_stage: false,
  },
]

const governanceReviewDetail = {
  ...governanceReviews[0],
  traceability_map_version: {
    computed_at: '2026-04-28T00:00:00Z',
    readiness: 'needs_review',
    node_count: 8,
    edge_count: 7,
  },
  checklist_items: [
    {
      item_id: 'chk_traceability_exists',
      category: 'traceability',
      label: 'Traceability map is computable',
      required: true,
      status: 'pass',
      severity: 'major',
      source: 'system_seeded',
    },
    {
      item_id: 'chk_weak_support_reviewed',
      category: 'support',
      label: 'Weak support findings reviewed',
      required: true,
      status: 'fail',
      severity: 'major',
      source: 'system_seeded',
    },
    {
      item_id: 'chk_manual_signoff',
      category: 'signoff',
      label: 'Manual sign-off completed',
      required: true,
      status: 'fail',
      severity: 'major',
      source: 'system_seeded',
    },
  ],
  findings: [{
    finding_id: 'gf_demo',
    finding_type: 'thin_artifact_pack',
    severity: 'major',
    status: 'open',
    asset_ref: { asset_type: 'artifact_pack', asset_id: 'ap_demo' },
    description: 'Artifact pack has limited material structure.',
    source: 'traceability_map',
  }],
  risk_dispositions: [],
  signoffs: [],
  review_summary: {
    overall_readiness: 'partial',
    blocker_count: 0,
    major_open_count: 1,
    accepted_risk_count: 0,
    failed_required_count: 2,
    approved_signoff_count: 0,
    ready_for_next_stage: false,
    summary_note: '',
  },
}

const reviewHistoryEntries = [
  {
    history_entry_id: 'rhe_demo_1',
    asset_type: 'governance_review',
    asset_id: 'gr_demo',
    asset_title: 'P9 strategic research governance review',
    event_type: 'gate_decision_changed',
    event_source: 'kfc_api_patch',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    changed_fields: [
      { path: 'gate_decision', old_value: 'not_decided', new_value: 'ready_with_risks' },
    ],
    summary: 'governance_review updated',
    created_at: '2026-04-28T00:00:00.000000',
  },
  {
    history_entry_id: 'rhe_demo_2',
    asset_type: 'leadership_briefing',
    asset_id: 'lb_demo',
    asset_title: 'Leadership briefing',
    event_type: 'readiness_changed',
    event_source: 'kfc_api_patch',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    changed_fields: [
      { path: 'readiness', old_value: 'needs_review', new_value: 'ready' },
    ],
    summary: 'leadership_briefing updated',
    created_at: '2026-04-28T00:00:00.000000',
  },
]

const researchSnapshots = [
  {
    snapshot_id: 'rs_demo',
    title: 'P11 Gate Baseline',
    reason: 'Freeze current research state.',
    gate_type: 'p11_gate',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    included_asset_kinds: ['project', 'governance_reviews', 'leadership_briefings', 'review_history'],
    asset_counts: { governance_reviews: 1, leadership_briefings: 1, review_history: 2 },
    linked_governance_review: { governance_review_id: 'gr_demo', gate_decision: 'not_decided', readiness: 'partial' },
    linked_leadership_briefing: { briefing_id: 'lb_demo', readiness: 'ready', status: 'in_review' },
    review_history_watermark: { latest_entry_id: 'rhe_demo_2', entry_count: 2 },
    snapshot_fingerprint: 'sha256:snapshot-demo',
    created_at: '2026-04-28T00:00:00.000000',
  },
]

const researchSnapshotDetail = {
  ...researchSnapshots[0],
  asset_kind_summaries: {
    governance_reviews: { count: 1 },
    leadership_briefings: { count: 1 },
    review_history: { count: 2 },
  },
  asset_fingerprints: {
    governance_reviews: [{ asset_id: 'gr_demo', status: 'in_review', readiness: 'partial', gate_decision: 'not_decided' }],
  },
}

const researchSnapshotDiff = {
  snapshot_id: 'rs_demo',
  summary: {
    has_changes: true,
    asset_kinds_changed: 2,
    assets_added: 1,
    assets_removed: 0,
    assets_changed: 1,
    review_history_changed: true,
    governance_gate_decision_changed: true,
    leadership_briefing_readiness_changed: false,
  },
  asset_id_changes: {
    insight_cards: { added: ['ic_new'], removed: [] },
  },
  asset_state_changes: {
    governance_reviews: [{ asset_id: 'gr_demo', changed_fields: { gate_decision: { from: 'not_decided', to: 'blocked' } } }],
  },
  governance_change: { from_gate_decision: 'not_decided', to_gate_decision: 'blocked', changed: true },
  leadership_briefing_change: { from_readiness: 'ready', to_readiness: 'ready', changed: false },
  review_history_change: { from_entry_count: 2, to_entry_count: 4, changed: true },
}

const snapshotReviewNotes = [
  {
    note_id: 'srn_demo',
    snapshot_id: 'rs_demo',
    target_ref: { section_key: 'governance_gate', asset_kind: 'governance_review', asset_id: 'gr_demo', field: 'gate_decision' },
    note_type: 'observation',
    severity: 'watch',
    status: 'open',
    owner: '',
    resolution_note: '',
    resolved_at: '',
    resolved_by: '',
    note: 'Manual reviewer should verify the governance movement.',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    created_at: '2026-04-28T00:00:00.000000',
  },
  {
    note_id: 'srn_ack',
    snapshot_id: 'rs_demo',
    target_ref: { section_key: 'raw_diff', asset_kind: 'snapshot', asset_id: 'rs_demo' },
    note_type: 'observation',
    severity: 'info',
    status: 'acknowledged',
    owner: 'Strategy reviewer',
    resolution_note: '',
    resolved_at: '',
    resolved_by: '',
    note: 'Acknowledged note should still be visible as human attention context.',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    created_at: '2026-04-28T00:02:00.000000',
  },
  {
    note_id: 'srn_deferred',
    snapshot_id: 'rs_demo',
    target_ref: { section_key: 'review_history_activity', asset_kind: 'review_history', asset_id: 'rhe_demo_2' },
    note_type: 'needs_follow_up',
    severity: 'watch',
    status: 'deferred',
    owner: 'Strategy reviewer',
    resolution_note: '',
    resolved_at: '',
    resolved_by: '',
    note: 'Deferred note should be shown in the gate review attention context.',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    created_at: '2026-04-28T00:03:00.000000',
  },
  {
    note_id: 'srn_resolved',
    snapshot_id: 'rs_demo',
    target_ref: { section_key: 'other' },
    note_type: 'observation',
    severity: 'info',
    status: 'resolved',
    owner: 'Strategy reviewer',
    resolution_note: 'Resolved before gate review.',
    resolved_at: '2026-04-28T00:04:00.000000',
    resolved_by: 'Strategy reviewer',
    note: 'Resolved note should be counted but not shown as active attention.',
    actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
    created_at: '2026-04-28T00:04:00.000000',
  },
]

const AppShellStub = {
  template: '<div class="app-shell-stub"><slot /></div>',
  props: ['crumbs'],
}

function mountPage() {
  return mount(ResearchProjectsPage, {
    global: {
      stubs: {
        AppShell: AppShellStub,
        RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] },
      },
    },
  })
}

describe('ResearchProjectsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listResearchProjects.mockResolvedValue({
      data: {
        projects: [
          {
            id: 'rp_de0a00000001',
            title: '华为云 Agent-ready 企业软件栈战略研究',
            background: '研究华为云在 Agent-ready 企业软件栈中的控制点、试点路径和材料输入。',
            audience: '华为云战略部二层领导',
            goal: '形成战略判断、试点路径和汇报材料输入。',
            status: 'draft',
            issue_tree: [],
            evidence_items: [],
            evidence_matrix_rows: [],
            insight_cards: [],
            artifact_drafts: [],
            artifact_packs: [],
            strategic_options: [],
            validation_plans: [],
            leadership_decision_records: [],
            leadership_briefings: [],
            governance_reviews: [],
            created_at: '2026-04-28T00:00:00.000000',
            updated_at: '2026-04-28T00:00:00.000000',
          },
        ],
        total: 1,
      },
    })
    getLocalEvidencePack.mockResolvedValue({
      data: {
        project_id: 'rp_de0a00000001',
        local_evidence_pack: localEvidencePack,
      },
    })
    searchLocalEvidencePack.mockResolvedValue({
      data: {
        project_id: 'rp_de0a00000001',
        local_evidence_pack: localEvidencePack,
      },
    })
    updateLocalEvidenceCandidate.mockResolvedValue({
      data: {
        project_id: 'rp_de0a00000001',
        local_evidence_pack: {
          ...localEvidencePack,
          summary: { ...localEvidencePack.summary, accepted_count: 1 },
          accepted_evidence_ids: ['ev_demo_harness'],
          candidates: localEvidencePack.candidates.map((item) => (
            item.evidence_id === 'ev_demo_harness' ? { ...item, status: 'accepted' } : item
          )),
        },
        evidence_items: [{ evidence_id: 'ev_demo_harness', title: '企业级 Harness' }],
      },
    })
    listResearchRuns.mockResolvedValue({
      data: {
        research_runs: [{
          run_id: 'rr_demo',
          stage: 'P3',
          phase: 'writeback_contract_test',
          title: 'P3 writeback dry run',
          status: 'completed',
          summary: 'Imported one external evidence pack.',
        }],
      },
    })
    listConsultationLogs.mockResolvedValue({
      data: {
        consultation_logs: [{
          consultation_id: 'cl_demo',
          kind: 'gpt_design_review',
          stage: 'P3',
          status: 'complete',
          answer_summary: 'P3 should be a writeback receiver.',
        }],
      },
    })
    listExternalResearchPacks.mockResolvedValue({
      data: {
        external_research_packs: externalPacks,
      },
    })
    listEvidenceMatrixRows.mockResolvedValue({
      data: {
        rows: matrixRows,
      },
    })
    listInsightCards.mockResolvedValue({
      data: {
        insight_cards: insightCards,
      },
    })
    listArtifactDrafts.mockResolvedValue({
      data: {
        artifact_drafts: artifactDrafts,
      },
    })
    updateEvidenceMatrixRow.mockResolvedValue({
      data: {
        row: { ...matrixRows[0], status: 'reviewed' },
      },
    })
    updateInsightCard.mockResolvedValue({
      data: {
        insight_card: { ...insightCards[0], status: 'accepted' },
      },
    })
    updateArtifactDraft.mockResolvedValue({
      data: {
        artifact_draft: { ...artifactDrafts[0], material_readiness: 'presentation_ready' },
      },
    })
    listArtifactPacks.mockResolvedValue({ data: { artifact_packs: artifactPacks } })
    createArtifactPack.mockResolvedValue({
      data: { artifact_pack: { ...artifactPacks[0], pack_id: 'ap_created', pages: [], file_refs: [], review_rounds: [] } },
    })
    updateArtifactPack.mockResolvedValue({
      data: { artifact_pack: { ...artifactPacks[0], status: 'in_review', readiness: 'review_ready' } },
    })
    addArtifactPackItem.mockResolvedValue({
      data: { artifact_pack: { ...artifactPacks[0], items: [{ item_id: 'api_demo', title: '主汇报材料' }] } },
    })
    addArtifactPackPage.mockResolvedValue({
      data: { artifact_pack: { ...artifactPacks[0], pages: [...artifactPacks[0].pages, { page_id: 'pg_added', page_title: '新增页面', page_claim: '新增判断' }] } },
    })
    addArtifactPackFileRef.mockResolvedValue({
      data: { artifact_pack: { ...artifactPacks[0], file_refs: [{ file_ref_id: 'fr_demo', title: '五层架构图 v0.1', file_kind: 'drawio' }] } },
    })
    addArtifactPackReviewRound.mockResolvedValue({
      data: { artifact_pack: { ...artifactPacks[0], review_rounds: [{ review_round_id: 'rv_demo', round_name: 'P5 internal review round 1', decisions: [] }] } },
    })
    listStrategicOptions.mockResolvedValue({ data: { strategic_options: strategicOptions } })
    createStrategicOption.mockResolvedValue({
      data: { strategic_option: { ...strategicOptions[0], option_id: 'so_created', status: 'draft' } },
    })
    updateStrategicOption.mockResolvedValue({
      data: { strategic_option: { ...strategicOptions[0], status: 'accepted_for_planning' } },
    })
    listValidationPlans.mockResolvedValue({ data: { validation_plans: validationPlans } })
    createValidationPlan.mockResolvedValue({
      data: { validation_plan: { ...validationPlans[0], plan_id: 'vp_created', status: 'draft' } },
    })
    updateValidationPlan.mockResolvedValue({
      data: { validation_plan: { ...validationPlans[0], status: 'approved', approval_state: 'approved' } },
    })
    listLeadershipDecisionRecords.mockResolvedValue({ data: { leadership_decision_records: decisionRecords } })
    createLeadershipDecisionRecord.mockResolvedValue({
      data: { leadership_decision_record: { ...decisionRecords[0], decision_id: 'ldr_created' } },
    })
    updateLeadershipDecisionRecord.mockImplementation((projectId, decisionId, payload) => Promise.resolve({
      data: {
        leadership_decision_record: {
          ...decisionRecords[0],
          decision_id: decisionId,
          ...payload,
        },
      },
    }))
    listLeadershipBriefings.mockResolvedValue({ data: { leadership_briefings: leadershipBriefings } })
    getLeadershipBriefing.mockResolvedValue({
      data: { leadership_briefing: leadershipBriefingDetail },
    })
    createLeadershipBriefing.mockResolvedValue({
      data: { leadership_briefing: { ...leadershipBriefingDetail, briefing_id: 'lb_created', status: 'draft', readiness: 'not_ready' } },
    })
    updateLeadershipBriefing.mockImplementation((projectId, briefingId, payload) => Promise.resolve({
      data: {
        leadership_briefing: {
          ...leadershipBriefingDetail,
          briefing_id: briefingId,
          ...payload,
        },
      },
    }))
    getTraceabilityMap.mockResolvedValue({ data: traceabilityMap })
    listGovernanceReviews.mockResolvedValue({ data: { governance_reviews: governanceReviews } })
    getGovernanceReview.mockResolvedValue({
      data: { governance_review: governanceReviewDetail },
    })
    createGovernanceReview.mockResolvedValue({
      data: { governance_review: { ...governanceReviewDetail, review_id: 'gr_created', status: 'draft' } },
    })
    updateGovernanceReview.mockImplementation((projectId, reviewId, payload) => Promise.resolve({
      data: {
        governance_review: {
          ...governanceReviewDetail,
          review_id: reviewId,
          ...payload,
        },
      },
    }))
    listReviewHistory.mockResolvedValue({ data: { review_history_entries: reviewHistoryEntries } })
    getAssetReviewHistory.mockResolvedValue({
      data: { review_history_entries: reviewHistoryEntries.filter((entry) => entry.asset_id === 'gr_demo') },
    })
    createReviewHistoryNote.mockResolvedValue({
      data: {
        review_history_entry: {
          history_entry_id: 'rhe_note',
          asset_type: 'governance_review',
          asset_id: 'gr_demo',
          asset_title: 'P9 strategic research governance review',
          event_type: 'review_note_added',
          note: 'Accepted remaining risks for leadership readout.',
          changed_fields: [],
          actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
          created_at: '2026-04-28T00:00:00.000000',
        },
      },
    })
    listResearchSnapshots.mockResolvedValue({ data: { snapshots: researchSnapshots } })
    getResearchSnapshot.mockResolvedValue({ data: { snapshot: researchSnapshotDetail } })
    createResearchSnapshot.mockResolvedValue({
      data: {
        snapshot: {
          ...researchSnapshotDetail,
          snapshot_id: 'rs_created',
          title: 'P11 Gate Baseline',
          snapshot_fingerprint: 'sha256:created',
        },
      },
    })
    diffResearchSnapshot.mockResolvedValue({ data: { snapshot_diff: researchSnapshotDiff } })
    listSnapshotReviewNotes.mockResolvedValue({ data: { snapshot_review_notes: snapshotReviewNotes } })
    createSnapshotReviewNote.mockResolvedValue({
      data: {
        snapshot_review_note: {
          note_id: 'srn_created',
          snapshot_id: 'rs_demo',
          target_ref: { section_key: 'governance_gate' },
          note_type: 'question',
          severity: 'watch',
          status: 'open',
          owner: '',
          resolution_note: '',
          resolved_at: '',
          resolved_by: '',
          note: 'Please verify the governance gate movement.',
          actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
          created_at: '2026-04-28T00:00:00.000000',
        },
        review_history_entry_id: 'rhe_created',
      },
    })
    updateSnapshotReviewNote.mockResolvedValue({
      data: {
        snapshot_review_note: {
          ...snapshotReviewNotes[0],
          note_id: 'srn_created',
          snapshot_id: 'rs_created',
          status: 'resolved',
          owner: 'Reviewer',
          resolution_note: 'Manual disposition recorded.',
          resolved_at: '2026-04-28T00:01:00.000000',
          resolved_by: 'Reviewer',
          updated_at: '2026-04-28T00:01:00.000000',
        },
        review_history_entry_id: 'rhe_disposition',
        history_recorded: true,
      },
    })
    listTopicClustersWithAggregation.mockResolvedValue({
      data: {
        clusters: [
          {
            cluster_id: 'tc_wiki_agent-harness',
            title: 'Agent Harness 与工具编排',
            counts: { wiki_topics: 1, articles: 25, kfc_themes: 0 },
            article_count: 25,
          },
        ],
      },
    })
    getTopicClusterAssetIndex.mockResolvedValue({
      data: {
        counts: {
          direct_wiki_topic_count: 1,
          indirect_article_count: 25,
          candidate_theme_count: 1,
          candidate_concept_count: 3,
        },
        query_terms: ['agent', 'harness', 'context', 'engineering'],
        indirect_assets: { articles: [] },
      },
    })
    updateResearchProject.mockResolvedValue({
      data: {
        id: 'rp_de0a00000001',
        title: '华为云 Agent-ready 企业软件栈战略研究',
        status: 'draft',
      },
    })
    updateExternalResearchCandidate.mockResolvedValue({
      data: {
        external_research_pack: {
          ...externalPacks[0],
          accepted_count: 1,
          evidence_candidates: externalPacks[0].evidence_candidates.map((candidate) => ({
            ...candidate,
            review_status: 'accepted',
          })),
        },
        evidence_items: [{
          evidence_id: 'ei_demo_harness',
          origin: 'external_research_pack',
          scope: 'C2_external',
          title: '企业级 Agent 的核心控制点在执行治理外壳。',
        }],
      },
    })
    createResearchProject.mockResolvedValue({
      data: {
        id: 'rp_000000000001',
        title: '华为云 Agent-ready 企业软件栈战略研究',
        background: '研究华为云在 Agent-ready 企业软件栈中的控制点、试点路径和材料输入。',
        audience: '华为云战略部二层领导',
        goal: '形成战略判断、试点路径和汇报材料输入。',
        status: 'draft',
        issue_tree: [],
        evidence_items: [],
        evidence_matrix_rows: [],
        insight_cards: [],
        artifact_drafts: [],
        artifact_packs: [],
        strategic_options: [],
        validation_plans: [],
        leadership_decision_records: [],
        leadership_briefings: [],
        governance_reviews: [],
        created_at: '2026-04-28T00:00:00.000000',
        updated_at: '2026-04-28T00:00:00.000000',
      },
    })
  })

  it('renders the project list and selected details', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('战略研究项目')
    expect(wrapper.text()).toContain('华为云 Agent-ready 企业软件栈战略研究')
    expect(wrapper.text()).toContain('华为云战略部二层领导')
    expect(wrapper.text()).toContain('形成战略判断、试点路径和汇报材料输入')
    expect(wrapper.text()).toContain('本地证据包')
    expect(wrapper.text()).toContain('企业级 Harness')
    expect(wrapper.text()).toContain('Codex 写回')
    expect(wrapper.text()).toContain('P3 writeback dry run')
    expect(wrapper.text()).toContain('Huawei Cloud Agent-ready external evidence pack')
    expect(wrapper.text()).toContain('战略合成')
    expect(wrapper.text()).toContain('企业 Agent 的长期控制点在执行控制面')
    expect(wrapper.text()).toContain('战略决策工作台')
    expect(wrapper.text()).toContain('L2 Agent-ready 适配层 + L4 企业级 Harness 作为战略控制点')
    expect(wrapper.text()).toContain('90-day ERP/Test Harness pilot validation')
    expect(wrapper.text()).toContain('Decision on Agent-ready enterprise software stack control point')
    expect(wrapper.text()).toContain('Leadership Briefings')
    expect(wrapper.text()).toContain('Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout')
    expect(wrapper.text()).toContain('Enterprise AI competition is moving to Agent-ready software stack control points')
    expect(wrapper.text()).toContain('Traceability Map')
    expect(wrapper.text()).toContain('strategic_option:so_demo')
    expect(wrapper.text()).toContain('Artifact pack has limited material structure.')
    expect(wrapper.text()).toContain('Governance Review')
    expect(wrapper.text()).toContain('P9 strategic research governance review')
    expect(wrapper.text()).toContain('Weak support findings reviewed')
    expect(wrapper.text()).toContain('材料工坊')
    expect(wrapper.text()).toContain('华为云 Agent-ready 企业软件栈战略汇报材料包')
  })

  it('creates a sample research project', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(createResearchProject).toHaveBeenCalledWith({
      title: '华为云 Agent-ready 企业软件栈战略研究',
      background: '研究华为云在 Agent-ready 企业软件栈中的控制点、试点路径和材料输入。',
      audience: '华为云战略部二层领导',
      goal: '形成战略判断、试点路径和汇报材料输入。',
    })
    expect(wrapper.text()).toContain('rp_000000000001')
  })

  it('searches and accepts local evidence candidates', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const searchButton = wrapper.findAll('button').find((button) => button.text() === '检索本地证据')
    await searchButton.trigger('click')
    await flushPromises()

    expect(searchLocalEvidencePack).toHaveBeenCalledWith('rp_de0a00000001', {
      keywords: [],
      limit: 30,
      include_degraded: true,
    })

    const acceptButton = wrapper.findAll('button').find((button) => button.text() === '采纳')
    await acceptButton.trigger('click')
    await flushPromises()

    expect(updateLocalEvidenceCandidate).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'ev_demo_harness',
      { status: 'accepted', note: '' },
    )
    expect(wrapper.text()).toContain('已采纳')
  })

  it('renders and accepts external writeback evidence candidates', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listResearchRuns).toHaveBeenCalledWith('rp_de0a00000001')
    expect(listConsultationLogs).toHaveBeenCalledWith('rp_de0a00000001')
    expect(listExternalResearchPacks).toHaveBeenCalledWith('rp_de0a00000001')

    const buttons = wrapper.findAll('button').filter((button) => button.text() === '采纳')
    await buttons[buttons.length - 1].trigger('click')
    await flushPromises()

    expect(updateExternalResearchCandidate).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'erp_demo',
      'ec_demo_harness',
      { review_status: 'accepted', review_note: '' },
    )
    expect(wrapper.text()).toContain('C2 已采纳')
  })

  it('renders and reviews synthesis assets', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listEvidenceMatrixRows).toHaveBeenCalledWith('rp_de0a00000001')
    expect(listInsightCards).toHaveBeenCalledWith('rp_de0a00000001')
    expect(listArtifactDrafts).toHaveBeenCalledWith('rp_de0a00000001')
    expect(wrapper.text()).toContain('Evidence Matrix')
    expect(wrapper.text()).toContain('企业 Agent 的长期控制点在执行控制面')

    const reviewedButton = wrapper.findAll('button').find((button) => button.text() === '标记已审')
    await reviewedButton.trigger('click')
    await flushPromises()
    expect(updateEvidenceMatrixRow).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'emr_demo',
      { status: 'reviewed' },
    )
    expect(wrapper.text()).toContain('reviewed')

    const insightsTab = wrapper.findAll('button').find((button) => button.text() === 'Insight Board')
    await insightsTab.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('执行控制面是长期控制点')

    const acceptButtons = wrapper.findAll('button').filter((button) => button.text() === '采纳')
    await acceptButtons[acceptButtons.length - 1].trigger('click')
    await flushPromises()
    expect(updateInsightCard).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'ic_demo',
      { status: 'accepted' },
    )

    const artifactsTab = wrapper.findAll('button').find((button) => button.text() === 'Artifact Studio')
    await artifactsTab.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('华为云 Agent-ready 企业软件栈战略材料大纲')

    const reportButton = wrapper.findAll('button').find((button) => button.text() === '可汇报')
    await reportButton.trigger('click')
    await flushPromises()
    expect(updateArtifactDraft).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'ad_demo',
      { material_readiness: 'presentation_ready' },
    )
  })

  it('renders and updates material workshop packs', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listArtifactPacks).toHaveBeenCalledWith('rp_de0a00000001')
    expect(wrapper.text()).toContain('材料工坊')
    expect(wrapper.text()).toContain('华为云 Agent-ready 企业软件栈战略汇报材料包')

    const createButton = wrapper.findAll('button').find((button) => button.text() === '新建材料包')
    await createButton.trigger('click')
    await flushPromises()
    expect(createArtifactPack).toHaveBeenCalled()

    const reviewButton = wrapper.findAll('button').find((button) => button.text() === '进入评审')
    await reviewButton.trigger('click')
    await flushPromises()
    expect(updateArtifactPack).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.any(String),
      { status: 'in_review', readiness: 'review_ready' },
    )

    const pageButton = wrapper.findAll('button').find((button) => button.text() === '添加页面')
    await pageButton.trigger('click')
    await flushPromises()
    expect(addArtifactPackPage).toHaveBeenCalled()
  })

  it('renders and updates the strategic decision workspace', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listStrategicOptions).toHaveBeenCalledWith('rp_de0a00000001')
    expect(listValidationPlans).toHaveBeenCalledWith('rp_de0a00000001')
    expect(listLeadershipDecisionRecords).toHaveBeenCalledWith('rp_de0a00000001')
    expect(wrapper.text()).toContain('战略决策工作台')
    expect(wrapper.text()).toContain('阻塞未解决')
    expect(wrapper.text()).toContain('external')

    const optionButton = wrapper.findAll('button').find((button) => button.text() === '新建战略选项')
    await optionButton.trigger('click')
    await flushPromises()
    expect(createStrategicOption).toHaveBeenCalled()

    const planButton = wrapper.findAll('button').find((button) => button.text() === '创建试点计划')
    await planButton.trigger('click')
    await flushPromises()
    expect(createValidationPlan).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.objectContaining({ linked_option_ids: [expect.any(String)] }),
    )

    const recordButton = wrapper.findAll('button').find((button) => button.text() === '创建决策记录')
    await recordButton.trigger('click')
    await flushPromises()
    expect(createLeadershipDecisionRecord).toHaveBeenCalled()

    const approveButton = wrapper.findAll('button').find((button) => button.text() === '批准决策')
    await approveButton.trigger('click')
    await flushPromises()
    expect(updateLeadershipDecisionRecord).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.any(String),
      { decision_status: 'approved' },
    )
  })

  it('renders and updates leadership briefing readouts', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listLeadershipBriefings).toHaveBeenCalledWith('rp_de0a00000001')
    expect(getLeadershipBriefing).toHaveBeenCalledWith('rp_de0a00000001', 'lb_demo')
    expect(wrapper.text()).toContain('Leadership Briefings')
    expect(wrapper.text()).toContain('Why now')
    expect(wrapper.text()).toContain('insight_card · ic_demo')

    const createButton = wrapper.findAll('button').find((button) => button.text() === '新建 Readout')
    await createButton.trigger('click')
    await flushPromises()
    expect(createLeadershipBriefing).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.objectContaining({
        title: 'Huawei Cloud Agent-ready Enterprise Software Stack Leadership Readout',
        briefing_type: 'strategic_readout',
      }),
    )

    const readyButton = wrapper.findAll('button').find((button) => button.text() === '标记 Ready')
    await readyButton.trigger('click')
    await flushPromises()
    expect(updateLeadershipBriefing).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.any(String),
      { status: 'in_review', readiness: 'ready' },
    )
  })

  it('renders and filters the traceability map', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(getTraceabilityMap).toHaveBeenCalledWith('rp_de0a00000001', {})
    expect(wrapper.text()).toContain('Traceability Map')
    expect(wrapper.text()).toContain('Evidence')
    expect(wrapper.text()).toContain('Synthesis')
    expect(wrapper.text()).toContain('Decision')
    expect(wrapper.text()).toContain('Materials')
    expect(wrapper.text()).toContain('Leadership Briefing')
    expect(wrapper.text()).toContain('evidence_item:ev_demo_harness')
    expect(wrapper.text()).toContain('supports')
    expect(wrapper.text()).toContain('Artifact pack has limited material structure.')

    const selects = wrapper.findAll('select')
    await selects[1].setValue('insight_card')
    await flushPromises()
    expect(getTraceabilityMap).toHaveBeenCalledWith('rp_de0a00000001', { asset_type: 'insight_card' })

    await selects[2].setValue('warning')
    await flushPromises()
    expect(getTraceabilityMap).toHaveBeenLastCalledWith('rp_de0a00000001', {
      asset_type: 'insight_card',
      issue_severity: 'warning',
    })
  })

  it('renders and updates governance review gate state', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listGovernanceReviews).toHaveBeenCalledWith('rp_de0a00000001')
    expect(getGovernanceReview).toHaveBeenCalledWith('rp_de0a00000001', 'gr_demo')
    expect(wrapper.text()).toContain('Governance Review')
    expect(wrapper.text()).toContain('Traceability map is computable')
    expect(wrapper.text()).toContain('Artifact pack has limited material structure.')
    expect(wrapper.text()).toContain('Snapshot note attention context')
    expect(wrapper.text()).toContain('Read-only context derived from manual snapshot review notes')
    expect(wrapper.text()).toContain('Linked snapshot')
    expect(wrapper.text()).toContain('P11 Gate Baseline')
    expect(wrapper.text()).toContain('Manual reviewer should verify the governance movement.')
    expect(wrapper.text()).toContain('Acknowledged note should still be visible')
    expect(wrapper.text()).toContain('Deferred note should be shown')
    expect(wrapper.text()).toContain('Source')
    expect(wrapper.text()).toContain('P11 Gate Baseline · Linked snapshot · srn_demo')
    expect(wrapper.text()).toContain('Target')
    expect(wrapper.text()).toContain('Section: governance_gate · Asset: governance_review / gr_demo · Field: gate_decision')
    expect(wrapper.text()).toContain('Trace only · active human attention · no gate readiness change')
    expect(wrapper.text()).not.toContain('Resolved note should be counted but not shown as active attention.')

    const createButton = wrapper.findAll('button').find((button) => button.text() === '新建审查')
    await createButton.trigger('click')
    await flushPromises()
    expect(createGovernanceReview).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.objectContaining({
        title: 'P9 strategic research governance review',
        seed_from_traceability_map: true,
      }),
    )

    const acceptButton = wrapper.findAll('button').find((button) => button.text() === '接受风险并签署')
    await acceptButton.trigger('click')
    await flushPromises()
    expect(updateGovernanceReview).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.any(String),
      expect.objectContaining({
        status: 'signed_off',
        gate_decision: 'ready_with_risks',
        readiness: 'ready',
      }),
    )
  })

  it('renders review history and records manual notes for the selected review', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listReviewHistory).toHaveBeenCalledWith('rp_de0a00000001', { limit: 50 })
    expect(getAssetReviewHistory).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'governance_review',
      'gr_demo',
      { limit: 100 },
    )
    expect(wrapper.text()).toContain('Review History')
    expect(wrapper.text()).toContain('gate_decision_changed')
    expect(wrapper.text()).toContain('leadership_briefing')

    const note = wrapper.find('.history-panel textarea')
    await note.setValue('Accepted remaining risks for leadership readout.')
    await wrapper.find('.history-panel .note-form').trigger('submit')
    await flushPromises()

    expect(createReviewHistoryNote).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.objectContaining({
        asset_type: 'governance_review',
        asset_id: 'gr_demo',
        note: 'Accepted remaining risks for leadership readout.',
      }),
    )
    expect(wrapper.text()).toContain('review_note_added')
  })

  it('renders research snapshots and compares a gate baseline to current state', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(listResearchSnapshots).toHaveBeenCalledWith('rp_de0a00000001')
    expect(getResearchSnapshot).toHaveBeenCalledWith('rp_de0a00000001', 'rs_demo')
    expect(wrapper.text()).toContain('Gate Snapshot')
    expect(wrapper.text()).toContain('P11 Gate Baseline')

    await wrapper.find('.snapshot-panel .create-form').trigger('submit')
    await flushPromises()

    expect(createResearchSnapshot).toHaveBeenCalledWith(
      'rp_de0a00000001',
      expect.objectContaining({
        title: 'P11 Gate Baseline',
        gate_type: 'p11_gate',
        governance_review_id: 'gr_demo',
      }),
    )

    const diffButton = wrapper.findAll('.snapshot-panel button').find((button) => button.text() === '对比当前')
    await diffButton.trigger('click')
    await flushPromises()

    expect(diffResearchSnapshot).toHaveBeenCalledWith('rp_de0a00000001', expect.any(String))
    expect(wrapper.text()).toContain('changed')
    expect(wrapper.text()).toContain('ic_new')
    expect(wrapper.text()).toContain('not_decided → blocked')
    expect(wrapper.text()).toContain('人工审阅备注')
    expect(wrapper.text()).toContain('这段快照差异尚未添加人工备注。')

    await wrapper.find('.snapshot-review-panel textarea').setValue('Please verify the governance gate movement.')
    const noteType = wrapper.findAll('.snapshot-review-panel select')[1]
    await noteType.setValue('question')
    await wrapper.find('.snapshot-review-panel .note-form').trigger('submit')
    await flushPromises()

    expect(createSnapshotReviewNote).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'rs_created',
      expect.objectContaining({
        note_type: 'question',
        severity: 'watch',
        note: 'Please verify the governance gate movement.',
        actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
      }),
    )
    expect(wrapper.text()).toContain('Please verify the governance gate movement.')

    await wrapper.find('.snapshot-review-panel .disposition-form select').setValue('resolved')
    await wrapper.find('.snapshot-review-panel .disposition-form input').setValue('Reviewer')
    await wrapper.find('.snapshot-review-panel .disposition-form textarea').setValue('Manual disposition recorded.')
    await wrapper.find('.snapshot-review-panel .disposition-form').trigger('submit')
    await flushPromises()

    expect(updateSnapshotReviewNote).toHaveBeenCalledWith(
      'rp_de0a00000001',
      'rs_created',
      'srn_created',
      expect.objectContaining({
        status: 'resolved',
        owner: 'Reviewer',
        resolution_note: 'Manual disposition recorded.',
        actor: { actor_type: 'manual_user', display_name: 'Reviewer' },
      }),
    )
    expect(wrapper.text()).toContain('Resolved')
    expect(wrapper.text()).toContain('Manual disposition recorded.')
  })

  it('shows create errors and does not expose execution controls', async () => {
    createResearchProject.mockRejectedValue(new Error('Demo 模式为只读'))
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Demo 模式为只读')
    expect(wrapper.text()).not.toContain('Run research')
    expect(wrapper.text()).not.toContain('Ask GPT')
    expect(wrapper.text()).not.toContain('Generate insight')
    expect(wrapper.text()).not.toContain('Generate briefing')
    expect(wrapper.text()).not.toContain('Start pipeline')
    expect(wrapper.text()).not.toContain('深度研究')
    expect(wrapper.text()).not.toContain('生成洞察')
    expect(wrapper.text()).not.toContain('调用 GPT')
    expect(wrapper.text()).not.toContain('开始研究')
    expect(wrapper.text()).not.toContain('一键生成')
    expect(wrapper.text()).not.toContain('生成 PPT')
    expect(wrapper.text()).not.toContain('Auto-fix traceability')
    expect(wrapper.text()).not.toContain('Export draw.io')
    expect(wrapper.text()).not.toContain('Restore snapshot')
    expect(wrapper.text()).not.toContain('Rollback')
  })
})
