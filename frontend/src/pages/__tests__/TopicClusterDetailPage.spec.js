import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getTopicCluster = vi.fn()
const getTopicClusterAssetIndex = vi.fn()
const getTopicClusterPromotionBasket = vi.fn()
const getTopicClusterPromotionChanges = vi.fn()
const getTopicClusterArticleProcessingReview = vi.fn()
const applyArticleProcessingBatchAction = vi.fn()
const createTopicClusterMaterialSlice = vi.fn()
const applyLeadPromotionAction = vi.fn()
const applyRelationCandidateAction = vi.fn()
const getLeadPromotionTrace = vi.fn()
const getThemePanorama = vi.fn()
const updateTopicCluster = vi.fn()
const createTopicClusterLink = vi.fn()
const updateTopicClusterLink = vi.fn()
const deleteTopicClusterLink = vi.fn()
const getResearchProject = vi.fn()
const updateResearchProject = vi.fn()
const getWikiIntakeCandidate = vi.fn()
const getRegistryConcept = vi.fn()
const getRegistryConceptGraph = vi.fn()
const listCrossRelations = vi.fn()
const listRegistryConcepts = vi.fn()
const routeState = {
  query: {},
  path: '/workspace/topic-clusters/tc_agent_ready',
  params: { clusterId: 'tc_agent_ready' },
}

vi.mock('../../data/dataClient', () => ({
  getTopicCluster: (...args) => getTopicCluster(...args),
  getTopicClusterAssetIndex: (...args) => getTopicClusterAssetIndex(...args),
  getTopicClusterPromotionBasket: (...args) => getTopicClusterPromotionBasket(...args),
  getTopicClusterPromotionChanges: (...args) => getTopicClusterPromotionChanges(...args),
  getTopicClusterArticleProcessingReview: (...args) => getTopicClusterArticleProcessingReview(...args),
  applyArticleProcessingBatchAction: (...args) => applyArticleProcessingBatchAction(...args),
  createTopicClusterMaterialSlice: (...args) => createTopicClusterMaterialSlice(...args),
  applyLeadPromotionAction: (...args) => applyLeadPromotionAction(...args),
  applyRelationCandidateAction: (...args) => applyRelationCandidateAction(...args),
  getLeadPromotionTrace: (...args) => getLeadPromotionTrace(...args),
  getThemePanorama: (...args) => getThemePanorama(...args),
  updateTopicCluster: (...args) => updateTopicCluster(...args),
  createTopicClusterLink: (...args) => createTopicClusterLink(...args),
  updateTopicClusterLink: (...args) => updateTopicClusterLink(...args),
  deleteTopicClusterLink: (...args) => deleteTopicClusterLink(...args),
  getResearchProject: (...args) => getResearchProject(...args),
  updateResearchProject: (...args) => updateResearchProject(...args),
  getWikiIntakeCandidate: (...args) => getWikiIntakeCandidate(...args),
  getRegistryConcept: (...args) => getRegistryConcept(...args),
  getRegistryConceptGraph: (...args) => getRegistryConceptGraph(...args),
  listCrossRelations: (...args) => listCrossRelations(...args),
  listRegistryConcepts: (...args) => listRegistryConcepts(...args),
}))

vi.mock('../../services/api/registryApi', () => ({
  unlinkProjectConcept: vi.fn(),
  updateCrossRelation: vi.fn(),
  deleteCrossRelation: vi.fn(),
  deleteRegistryConcept: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: {
    props: ['to'],
    computed: {
      href() {
        if (typeof this.to === 'string') return this.to
        const query = new URLSearchParams(this.to?.query || {}).toString()
        return `${this.to?.path || this.to?.name || ''}${query ? `?${query}` : ''}`
      },
    },
    template: '<a :href="href"><slot /></a>',
  },
  'router-link': {
    props: ['to'],
    computed: {
      href() {
        if (typeof this.to === 'string') return this.to
        const query = new URLSearchParams(this.to?.query || {}).toString()
        return `${this.to?.path || this.to?.name || ''}${query ? `?${query}` : ''}`
      },
    },
    template: '<a :href="href"><slot /></a>',
  },
}))

vi.mock('../../components/common/AppShell.vue', () => ({
  default: { template: '<div class="app-shell-stub"><main class="app-content"><slot /></main></div>', props: ['crumbs'] },
}))

import TopicClusterDetailPage from '../TopicClusterDetailPage.vue'

enableAutoUnmount(afterEach)

const routerLinkStub = {
  props: ['to'],
  computed: {
    href() {
      if (typeof this.to === 'string') return this.to
      const query = new URLSearchParams(this.to?.query || {}).toString()
      return `${this.to?.path || this.to?.name || ''}${query ? `?${query}` : ''}`
    },
  },
  template: '<a :href="href"><slot /></a>',
}

function relationshipCardIds(wrapper, targetType) {
  return wrapper.findAll('.candidate-review-card')
    .filter((card) => card.attributes('data-target-type') === targetType)
    .map((card) => card.attributes('data-target-id'))
}

describe('TopicClusterDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    })
    window.localStorage.clear()
    routeState.params.clusterId = 'tc_agent_ready'
    getTopicCluster.mockResolvedValue({
      data: {
        cluster: {
          cluster_id: 'tc_agent_ready',
          title: 'Agent-ready 企业软件栈',
          description: '聚合企业软件 Agent 化和 Harness。',
          status: 'active',
          strategic_relevance: 'high',
          counts: { wiki_topics: 1, kfc_themes: 1, research_projects: 1 },
          article_count: 2,
          linked_topic_articles: [
            {
              topic_id: 'agent-ready-enterprise-stack',
              title: 'Agent-ready 企业软件栈',
              article_count: 2,
              articles: [
                {
                  candidate_id: 'src_agent',
                  title: 'Agent Harness 工作流笔记',
                  processed_at: '2026-05-13T11:21:15+08:00',
                  source_url: 'https://example.com/agent-harness',
                  verified_digest_md_path: '/tmp/agent-digest.md',
                  markdown_path: '/tmp/agent.md',
                  top_concepts: [
                    "{'concept': 'Agent Harness', 'summary': '从 Wiki 粗加工提取的 Agent Harness 概念线索。'}",
                    { concept: 'MCP', summary: 'Model Context Protocol。' },
                  ],
                  belongs_to_cluster_reason: [
                    'formal wiki_topic link: agent-ready-enterprise-stack',
                    'top concepts overlap: Agent Harness, MCP',
                  ],
                },
                {
                  candidate_id: 'src_agent_followup',
                  title: 'Agent Harness 复盘记录',
                  processed_at: '2026-05-13T12:21:15+08:00',
                  source_url: 'https://example.com/agent-harness-followup',
                  top_concepts: ['Agent Harness', 'Tooling'],
                  belongs_to_cluster_reason: [
                    'formal wiki_topic link: agent-ready-enterprise-stack',
                    'top concepts overlap: Agent Harness, Tooling',
                  ],
                },
              ],
            },
          ],
        },
        links_by_type: {
          wiki_topic: [
            {
              link_id: 'tcl_wiki',
              target_id: 'agent-ready-enterprise-stack',
              target_title: 'Agent-ready 企业软件栈',
              role: 'primary',
              status: 'accepted',
              rationale: '主 Wiki 预消化入口。',
            },
          ],
          kfc_theme: [
            {
              link_id: 'tcl_theme',
              target_id: 'gtheme_agent',
              target_title: 'AI Agent系统架构与上下文管理',
              role: 'primary',
              status: 'accepted',
            },
          ],
          research_project: [
            {
              link_id: 'tcl_rp',
              target_id: 'rp_000000000000',
              target_title: 'Agent-ready 战略研究',
              role: 'supporting',
              status: 'needs_review',
            },
          ],
        },
        warnings: [],
      },
    })
    getTopicClusterAssetIndex.mockResolvedValue({
      data: {
        cluster_id: 'tc_agent_ready',
        cluster_title: 'Agent-ready 企业软件栈',
        generated_at: '2026-05-13T12:00:00+08:00',
        direct_links: {
          wiki_topics: [
            {
              target_type: 'wiki_topic',
              target_id: 'agent-ready-enterprise-stack',
              target_title: 'Agent-ready 企业软件栈',
              association_kind: 'direct_link',
            },
          ],
          kfc_themes: [
            {
              target_type: 'kfc_theme',
              target_id: 'gtheme_agent',
              target_title: 'AI Agent系统架构与上下文管理',
              relation_state: 'linked',
              association_type: 'formal',
            },
          ],
          research_projects: [
            {
              target_type: 'research_project',
              target_id: 'rp_000000000000',
              target_title: 'Agent-ready 战略研究',
              relation_state: 'linked',
              association_type: 'formal',
            },
          ],
        },
        formal_assets: {
          kfc_themes: [
            {
              target_type: 'kfc_theme',
              target_id: 'gtheme_agent',
              target_title: 'AI Agent系统架构与上下文管理',
              association_type: 'formal',
              relation_state: 'linked',
              confirmation_status: 'confirmed',
              summary: '探讨 AI Agent 系统分层架构、上下文压缩管道和工具调用模式。',
              match_reason: '覆盖 Agent Harness、MCP、工具编排、上下文管理等主题。',
              source_kind: 'topic_cluster_link',
              source_path_display: 'backend/uploads/projects/global_themes.json',
              link_id: 'tcl_theme',
              link_record: {
                link_id: 'tcl_theme',
                link_status: 'accepted',
                created_at: '2026-05-13T10:00:00+08:00',
                source_path: 'backend/uploads/projects/global_themes.json',
              },
              member_concepts: [{ entry_id: 'canon_mcp', title: 'MCP' }],
              linked_articles: [],
              linked_projects: [],
              supported_actions: ['view_detail', 'open_theme_hub', 'view_link_record', 'unlink_theme'],
              promotion_supported: false,
            },
          ],
          concepts: [
            {
              target_type: 'concept',
              target_id: 'canon_deposited_harness',
              concept_id: 'canon_deposited_harness',
              target_title: 'Agent Harness 沉淀概念',
              association_type: 'formal',
              relation_state: 'linked',
              confirmation_status: 'unreviewed',
              quality_state: 'machine_generated',
              review_state: 'unreviewed',
              summary: '从 KFC 加工篮自动沉淀的可用 Concept 资产。',
              match_reason: 'Concept carries a formal KFC TopicCluster link.',
              source_kind: 'concept_registry',
              source_path_display: 'backend/uploads/projects/concept_registry.json',
              source_article_id: 'src_agent',
              source_quote: 'Agent Harness 把原文片段整理成可复用 KFC 概念。',
              source_context: '来自 Wiki 文章上下文，并保留 material slice 与 lead 追溯。',
              source_material_slice_id: 'mslice_deposited_harness',
              source_lead_id: 'lead_deposited_harness',
              supported_actions: ['view_detail', 'open_concept_registry', 'unlink_concept', 'deprecate_concept'],
              promotion_supported: false,
            },
          ],
          research_projects: [
            {
              target_type: 'research_project',
              target_id: 'rp_000000000000',
              target_title: 'Agent-ready 战略研究',
              association_type: 'formal',
              relation_state: 'linked',
              confirmation_status: 'confirmed',
              summary: '研究 Agent-ready 企业软件栈。',
              source_kind: 'topic_cluster_link',
              source_path_display: 'backend/data/research_projects/rp_000000000000.json',
              link_id: 'tcl_rp',
              link_record: { link_id: 'tcl_rp', link_status: 'needs_review', source_path: 'backend/data/research_projects/rp_000000000000.json' },
              project_asset_summary: { topic_cluster_count: 1, evidence_count: 2, concept_count: 3, review_snapshot_count: 1 },
              supported_actions: ['view_detail', 'open_project', 'unlink_project'],
              promotion_supported: false,
            },
          ],
        },
        derived_assets: {
          concepts: [
            {
              target_type: 'concept',
              target_id: 'canon_mcp',
              target_title: 'MCP',
              relation_state: 'derived_from_linked_theme',
              association_type: 'derived',
              source_kind: 'linked_theme',
              match_reason: '来自已关联 Theme：AI Agent系统架构与上下文管理',
              summary: 'Model Context Protocol。',
              concept_type: 'Technology',
              linked_themes: [{ theme_id: 'gtheme_agent', title: 'AI Agent系统架构与上下文管理' }],
              supported_actions: ['view_detail', 'open_concept_registry', 'add_to_current_project_concept_basket'],
              promotion_supported: false,
            },
          ],
        },
        ignored_assets: { kfc_themes: [], concepts: [], research_projects: [] },
        indirect_assets: {
          articles: [
            {
              target_type: 'article',
              target_id: 'src_agent',
              target_title: 'Agent Harness 工作流笔记',
              association_kind: 'indirect_aggregation',
              digest_summary: '企业 Agent Harness 需要执行治理。',
              source_url: 'https://example.com/agent-harness',
              top_concepts: [
                "{'concept': 'Agent Harness', 'summary': '从 Wiki 粗加工提取的 Agent Harness 概念线索。'}",
                { concept: 'MCP', summary: 'Model Context Protocol。' },
              ],
              routes: {
                source_url: 'https://example.com/agent-harness',
                wiki_intake: '/workspace/wiki-intake?candidate=src_agent',
                verified_digest: 'file:///tmp/agent-digest.md',
                source_file: 'file:///tmp/agent.md',
              },
            },
          ],
          wiki_topics: [],
          representative_articles: [],
        },
        candidate_assets: {
          kfc_themes: [
            {
              target_type: 'kfc_theme',
              target_id: 'gtheme_agent_candidate',
              target_title: 'Agent Harness 执行治理',
              association_type: 'candidate',
              confirmation_status: 'unconfirmed',
              match_reason: '本地字段命中：agent, harness',
              matched_terms: ['agent', 'harness'],
              matched_fields: ['title', 'description'],
              summary: '企业 Agent 的权限审批、回滚和审计控制点。',
              definition: '企业 Agent 的权限审批、回滚和审计控制点。',
              canonical: true,
              canonical_status: 'active',
              member_concepts: [{ entry_id: 'canon_agent_harness', title: 'Agent Harness' }],
              linked_articles: [],
              linked_themes: [],
              linked_projects: [],
              provenance: { source_file: 'backend/uploads/projects/global_themes.json', mutation: false },
              diagnostics: { missing_definition: false, missing_article_provenance: true, promotion_supported: true },
              why_candidate: { strong_terms: ['harness'], weak_terms: ['agent'], matched_fields: ['title'] },
              confidence_hint: 'high',
              source_kind: 'global_themes',
              source_path_display: 'backend/uploads/projects/global_themes.json',
              risk_note: '只读候选 Theme；不是正式 TopicClusterLink。',
              promotion_supported: true,
              promotion_action: 'create_topic_cluster_link',
            },
            {
              target_type: 'kfc_theme',
              target_id: 'gtheme_agent_candidate_2',
              target_title: 'Agent Harness 执行治理',
              association_type: 'candidate',
              confirmation_status: 'unconfirmed',
              match_reason: '同名候选但 target_id 不同。',
              matched_terms: ['agent', 'harness'],
              matched_fields: ['title'],
              summary: '第二个同名 Theme 候选，用于校验按钮绑定当前卡片。',
              confidence_hint: 'high',
              source_kind: 'global_themes',
              source_path_display: 'backend/uploads/projects/global_themes.json',
              risk_note: '只读候选 Theme；不是正式 TopicClusterLink。',
              diagnostics: { missing_definition: false, missing_article_provenance: true, promotion_supported: true },
              promotion_supported: true,
              promotion_action: 'create_topic_cluster_link',
            },
          ],
          concepts: [
            {
              target_type: 'concept',
              target_id: 'canon_agent_harness',
              target_title: 'Agent Harness',
              association_type: 'candidate',
              match_reason: '本地字段命中：agent, harness',
              matched_terms: ['agent', 'harness'],
              matched_fields: ['title'],
              confidence_hint: 'high',
              source_kind: 'concept_registry',
              source_path_display: 'backend/uploads/projects/concept_registry.json',
              summary: '',
              aliases: ['执行治理外壳'],
              concept_type: 'Solution',
              canonical: true,
              canonical_status: 'canonical',
              linked_articles: [],
              linked_themes: [{ theme_id: 'gtheme_agent_candidate', title: 'Agent Harness 执行治理' }],
              linked_projects: [],
              provenance: { source_file: 'backend/uploads/projects/concept_registry.json', mutation: false },
              diagnostics: {
                missing_definition: true,
                missing_article_provenance: true,
                concept_cluster_link_unsupported: true,
                promotion_supported: false,
              },
              risk_note: '只读候选 Concept；P27 不扩展写入 link target_type。',
              promotion_supported: false,
            },
          ],
          research_projects: [
            {
              target_type: 'research_project',
              target_id: 'rp_agent',
              target_title: '华为云 Agent-ready 企业软件栈战略研究',
              association_type: 'candidate',
              confirmation_status: 'unconfirmed',
              match_reason: '本地字段命中：agent, harness',
              confidence_hint: 'medium',
              source_kind: 'research_project',
              source_path_display: 'backend/data/research_projects/rp_agent.json',
              summary: '研究企业 Agent-ready 软件栈。',
              project_status: 'active',
              linked_articles: [],
              linked_themes: [],
              linked_projects: [],
              project_asset_summary: {
                topic_cluster_count: 2,
                evidence_count: 30,
                concept_count: 105,
                review_snapshot_count: 1,
              },
              provenance: { source_file: 'backend/data/research_projects/rp_agent.json', mutation: false },
              diagnostics: { missing_definition: false, missing_article_provenance: true, promotion_supported: true },
              risk_note: '只读候选 ResearchProject；P27 不写入项目引用。',
              promotion_supported: true,
              promotion_action: 'create_topic_cluster_link',
            },
            {
              target_type: 'research_project',
              target_id: 'rp_agent_duplicate_title',
              target_title: '华为云 Agent-ready 企业软件栈战略研究',
              association_type: 'candidate',
              confirmation_status: 'unconfirmed',
              match_reason: '同名候选项目但 target_id 不同。',
              confidence_hint: 'medium',
              source_kind: 'research_project',
              source_path_display: 'backend/data/research_projects/rp_agent_duplicate_title.json',
              summary: '第二个同名 ResearchProject 候选，用于校验按钮绑定当前卡片。',
              project_status: 'active',
              linked_articles: [],
              linked_themes: [],
              linked_projects: [],
              project_asset_summary: {
                topic_cluster_count: 1,
                evidence_count: 1,
                concept_count: 1,
                review_snapshot_count: 0,
              },
              provenance: { source_file: 'backend/data/research_projects/rp_agent_duplicate_title.json', mutation: false },
              diagnostics: { missing_definition: false, missing_article_provenance: true, promotion_supported: true },
              risk_note: '只读候选 ResearchProject；P27 不写入项目引用。',
              promotion_supported: true,
              promotion_action: 'create_topic_cluster_link',
            },
          ],
          evidence: [
            {
              target_type: 'evidence',
              target_id: 'rp_agent:ev_harness',
              target_title: 'Agent Harness evidence',
              association_type: 'candidate',
              match_reason: '本地字段命中：harness',
              matched_fields: ['evidence'],
              confidence_hint: 'low',
              source_kind: 'research_project.evidence_items',
              parent_research_project_id: 'rp_agent',
              parent_research_project_title: '华为云 Agent-ready 企业软件栈战略研究',
              source_path_display: 'backend/data/research_projects/rp_agent.json',
              risk_note: 'Evidence 是 project-scoped 线索；P27 不建立正式证据 link。',
            },
          ],
          insights: [],
          notes: [],
          artifacts: [],
        },
        counts: {
          direct_wiki_topic_count: 1,
          direct_kfc_theme_count: 1,
          direct_research_project_count: 1,
          indirect_article_count: 1,
          candidate_concept_count: 1,
          candidate_theme_count: 2,
          candidate_research_project_count: 2,
          candidate_evidence_count: 1,
          candidate_insight_count: 0,
          candidate_note_count: 0,
          candidate_artifact_count: 0,
          derived_concept_count: 1,
        },
        formal_empty_state: {
          kfc_theme: {
            message: '尚未建立正式 KFC Theme 链接；候选 Theme 需要人工确认后才会进入正式区。',
            candidate_count: 1,
          },
          research_project: {
            message: '尚未建立正式 ResearchProject 链接；候选项目不会自动创建或自动关联。',
            candidate_count: 1,
          },
        },
        warnings: [
          {
            type: 'no_formal_kfc_asset_links',
            message: '当前 Cluster 没有正式 KFC asset link；以下 Theme/Concept/ResearchProject 仅为只读候选。',
          },
        ],
      },
    })
    getTopicClusterPromotionBasket.mockResolvedValue({
      data: {
        cluster_id: 'tc_agent_ready',
        counts: {
          pending: 1,
          materialized_concept: 0,
          linked: 0,
          candidate_created: 0,
          added_to_project_evidence: 0,
          ignored: 0,
        },
        items: [
          {
            promotion_id: 'lp_agent_harness',
            slice_id: 'ms_agent_harness',
            lead_type: 'concept_lead',
            title: 'Agent Harness',
            summary: '从 Wiki 粗加工提取的 Agent Harness 概念线索。',
            source_quote: 'Agent Harness 需要权限审批、回滚和审计。',
            source_context: '企业 Agent Harness 需要权限审批、回滚和审计，作为执行治理层。',
            extraction_reason: 'core_concepts 命中 Agent Harness。',
            confidence: 0.82,
            source: {
              source_article_id: 'src_agent',
              source_title: 'Agent Harness 工作流笔记',
              source_markdown_path: '/tmp/agent.md',
              source_content_hash: 'sha256:agent',
              linked_wiki_topic: 'agent-harness',
            },
            linked_topic_cluster: 'tc_agent_ready',
            review_status: 'pending',
            decision: null,
            target: null,
            candidate: null,
            created_at: '2026-05-15T10:00:00',
            updated_at: '2026-05-15T10:00:00',
          },
        ],
      },
    })
    getTopicClusterPromotionChanges.mockResolvedValue({
      data: {
        cluster_id: 'tc_agent_ready',
        items: [
          {
            change_id: 'chg_demo',
            action: 'create_concept_from_lead',
            actor: 'human',
            timestamp: '2026-05-15T10:02:00',
            reason: '从 KFC 加工篮沉淀为可用概念资产。',
          },
        ],
        total: 1,
      },
    })
    getTopicClusterArticleProcessingReview.mockResolvedValue({
      data: {
        cluster_id: 'tc_agent_ready',
        article_id: 'src_agent',
        article_title: 'Agent Harness 工作流笔记',
        summary: {
          candidate_count: 3,
          total_candidates: 3,
          concept_leads: 1,
          evidence_leads: 1,
          relation_candidates: 1,
          needs_review: 2,
          high_risk: 1,
          low_quality: 0,
          pending_count: 3,
          reviewed_count: 0,
          changed_count: 0,
          rejected_count: 0,
          unresolved_risk_count: 2,
          relation_candidates_pending: 1,
          quote_issues_pending: 1,
          completion_status: 'at_risk',
          completion_status_label: '有风险待处理',
          status_counts: { pending: 2, pending_review: 1 },
        },
        article_completion: {
          status_code: 'at_risk',
          status_label: '有风险待处理',
          total_candidates: 3,
          pending_count: 3,
          reviewed_count: 0,
          changed_count: 0,
          rejected_count: 0,
          unresolved_risk_count: 2,
          relation_candidates_pending: 1,
          quote_issues_pending: 1,
        },
        review_groups: [
          { group_id: 'pending_review', title: '待审核', description: '尚未形成明确 reviewer decision 的候选。', count: 3, card_ids: ['lp_agent_harness', 'lp_agent_evidence', 'relcand_agent_harness_runtime'] },
          { group_id: 'high_confidence_quick_confirm', title: '高置信可快速确认', description: '置信度较高、无阻断风险。', count: 1, card_ids: ['lp_agent_harness'] },
          { group_id: 'low_confidence_manual_judgment', title: '低置信 / 需人工判断', description: '需要逐项判断。', count: 1, card_ids: ['relcand_agent_harness_runtime'] },
          { group_id: 'weak_quote_review', title: '证据弱 / 引文需核对', description: 'quote 需要核对。', count: 1, card_ids: ['lp_agent_evidence'] },
          { group_id: 'relation_pending', title: '关系候选待确认', description: '关系候选待确认。', count: 1, card_ids: ['relcand_agent_harness_runtime'] },
          { group_id: 'processed', title: '已处理', description: '已产生本地 reviewer decision。', count: 0, card_ids: [] },
        ],
        candidate_cards: [
          {
            card_id: 'lp_agent_harness',
            candidate_id: 'lp_agent_harness',
            candidate_type: 'concept_lead',
            candidate_kind: 'concept',
            title: 'Agent Harness',
            summary: '从 Wiki 粗加工提取的 Agent Harness 概念线索。',
            status: 'pending',
            review_status: 'pending',
            confidence_bucket: 'high',
            review_group_ids: ['pending_review', 'high_confidence_quick_confirm'],
            batch_eligible: true,
            batch_action_types: ['confirm_high_confidence_concepts'],
            recommended_action: 'select_best_registry_match',
            alternative_matches: [
              { concept_id: 'canon_agent_harness', concept_name: 'Agent Harness', reason: '名称完全一致' },
              { concept_id: 'canon_agent_runtime', concept_name: 'Agent Runtime', reason: '上位运行时概念' },
            ],
            quote: 'Agent Harness 需要权限审批、回滚和审计。',
            context: '企业 Agent Harness 需要权限审批、回滚和审计。',
            why: '核心概念命中。',
            confidence: 0.82,
            risk_flags: [],
            risk_flag_details: [],
            original_snapshot: { title: 'Agent Harness', quote: 'Agent Harness 需要权限审批、回滚和审计。', status: 'pending' },
            current_snapshot: { title: 'Agent Harness', quote: 'Agent Harness 需要权限审批、回滚和审计。', status: 'pending' },
            review_trail: [],
          },
          {
            card_id: 'lp_agent_evidence',
            candidate_id: 'lp_agent_evidence',
            candidate_type: 'evidence_lead',
            candidate_kind: 'evidence',
            title: '权限审批证据',
            summary: '证据片段。',
            status: 'pending',
            review_status: 'pending',
            confidence_bucket: 'medium',
            review_group_ids: ['pending_review', 'weak_quote_review'],
            batch_eligible: false,
            batch_action_types: [],
            quote: '权限审批、回滚和审计。',
            context: '作为执行治理层。',
            why: '支持 Harness 治理。',
            confidence: 0.74,
            risk_flags: ['quote:needs_verification'],
            risk_flag_details: [{ code: 'quote:needs_verification', label: '引文需核对', severity: 'warning' }],
            needs_quote_review: true,
            original_snapshot: { title: '权限审批证据', quote: '权限审批、回滚和审计。', status: 'pending' },
            current_snapshot: { title: '权限审批证据', quote: '权限审批、回滚和审计。', status: 'pending' },
            review_trail: [],
          },
          {
            card_id: 'relcand_agent_harness_runtime',
            candidate_id: 'relcand_agent_harness_runtime',
            candidate_type: 'relation_candidate',
            candidate_kind: 'relation',
            title: 'Agent Harness - contains - Agent Runtime',
            summary: '文章把 Runtime 放在 Harness 内解释。',
            status: 'pending_review',
            review_status: 'pending_review',
            confidence_bucket: 'medium',
            review_group_ids: ['pending_review', 'low_confidence_manual_judgment', 'relation_pending'],
            batch_eligible: false,
            batch_action_types: [],
            subject_concept: 'Agent Harness',
            relation_type: 'contains',
            object_concept: 'Agent Runtime',
            alternative_relation_types: [{ type: 'enables', reason: '偏能力支撑' }],
            quote: 'Harness 管权限审批、回滚和审计。',
            context: '执行治理层上下文。',
            why: '结构关系候选。',
            confidence: 0.68,
            risk_flags: ['low_confidence'],
            risk_flag_details: [{ code: 'low_confidence', label: '低置信匹配', severity: 'warning' }],
            original_snapshot: { title: 'Agent Harness - contains - Agent Runtime', quote: 'Harness 管权限审批、回滚和审计。', relation_type: 'contains', status: 'pending_review' },
            current_snapshot: { title: 'Agent Harness - contains - Agent Runtime', quote: 'Harness 管权限审批、回滚和审计。', relation_type: 'contains', status: 'pending_review' },
            review_trail: [],
          },
        ],
        review_trail: { compact_items: [], total: 0 },
        provenance: {
          review_trail_source: 'backend/data/kfc_change_log/kfc_changes.jsonl',
        },
      },
    })
    createTopicClusterMaterialSlice.mockResolvedValue({
      data: {
        slice: {
          slice_id: 'ms_created',
          slice_type: 'concept_lead',
          review_status: 'promoted',
        },
        promotion: {
          promotion_id: 'lp_created',
          lead_type: 'concept_lead',
          review_status: 'pending',
        },
      },
    })
    applyLeadPromotionAction.mockResolvedValue({
      data: {
        promotion_id: 'lp_agent_harness',
        review_status: 'ignored',
        decision: 'ignore',
      },
    })
    applyRelationCandidateAction.mockResolvedValue({
      data: {
        relation_candidate_id: 'relcand_agent_harness_runtime',
        review_status: 'confirmed',
        relation_type: 'contains',
      },
    })
    applyArticleProcessingBatchAction.mockResolvedValue({
      data: {
        batch_id: 'batch_test',
        action_type: 'confirm_high_confidence_concepts',
        applied: [{ card_id: 'lp_agent_harness', status: 'confirmed' }],
        skipped: [],
        summary: { requested: 1, applied: 1, skipped: 0 },
      },
    })
    getLeadPromotionTrace.mockResolvedValue({
      data: {
        trace: {
          article_id: 'src_agent',
          slice_id: 'ms_agent_harness',
          promotion_id: 'lp_agent_harness',
        },
      },
    })
    getThemePanorama.mockResolvedValue({
      data: {
        theme: {
          theme_id: 'gtheme_agent',
          name: 'AI Agent系统架构与上下文管理',
          description: '完整 Theme Hub 视角。',
          status: 'active',
        },
        stats: {
          concept_count: 13,
          member_count: 13,
          candidate_count: 0,
          article_count: 2,
          relation_count: 0,
        },
        grouped_concepts: {
          core: [
            {
              entry_id: 'canon_mcp',
              canonical_name: 'MCP',
              concept_type: 'Technology',
              description: 'Model Context Protocol。',
              role: 'member',
              score: 0.9,
            },
            ...Array.from({ length: 12 }, (_, index) => ({
              entry_id: `canon_extra_${index + 1}`,
              canonical_name: `完整概念 ${index + 1}`,
              concept_type: 'Concept',
              description: `完整概念 ${index + 1} 的说明。`,
              role: 'member',
              score: 0.8,
            })),
          ],
          bridge: [],
          peripheral: [],
        },
        bridge_relations: [],
        articles: [],
        suggested_memberships: [],
        silent_failures: {},
      },
    })
    updateTopicCluster.mockResolvedValue({
      data: {
        cluster: {
          cluster_id: 'tc_agent_ready',
          title: 'Updated Agent Stack',
          description: 'Updated desc',
          status: 'active',
          strategic_relevance: 'high',
          counts: { wiki_topics: 1, kfc_themes: 1, research_projects: 1 },
        },
        warnings: [],
      },
    })
    createTopicClusterLink.mockResolvedValue({
      data: {
        link: { link_id: 'tcl_new', target_type: 'wiki_topic', target_id: 'new-topic' },
        warnings: [{ code: 'target_unresolved' }],
      },
    })
    updateTopicClusterLink.mockResolvedValue({ data: { link: {}, warnings: [] } })
    deleteTopicClusterLink.mockResolvedValue({ data: { link_id: 'tcl_wiki', deleted: true } })
    getResearchProject.mockRejectedValue(new Error('no current project'))
    updateResearchProject.mockResolvedValue({ data: { id: 'rp_current', title: 'Current Project' } })
    getRegistryConcept.mockImplementation((entryId) => Promise.resolve({
      data: {
        entry_id: entryId,
        canonical_name: entryId === 'canon_mcp' ? 'MCP' : 'Agent Harness',
        concept_type: entryId === 'canon_mcp' ? 'Technology' : 'Solution',
        description: entryId === 'canon_mcp' ? 'Model Context Protocol。' : 'Agent Harness 的执行治理概念详情。',
        aliases: entryId === 'canon_mcp' ? ['Model Context Protocol'] : ['执行治理外壳'],
        source_links: entryId === 'canon_mcp'
          ? [{ project_id: 'proj_agent', project_name: 'Agent source project', concept_key: 'mcp' }]
          : [],
      },
    }))
    listCrossRelations.mockImplementation(({ entry_id: entryId } = {}) => Promise.resolve({
      data: entryId === 'canon_mcp'
        ? [{
            relation_id: 'xrel_mcp_agent_harness',
            source_entry_id: 'canon_mcp',
            target_entry_id: 'canon_agent_harness',
            relation_type: 'design_inspiration',
            directionality: 'bidirectional',
            confidence: 0.82,
            source: 'auto',
            review_status: 'unreviewed',
            reason: 'MCP 与 Agent Harness 共同支撑工具编排上下文。',
          }]
        : [],
    }))
    listRegistryConcepts.mockResolvedValue({
      data: {
        entries: [
          { entry_id: 'canon_mcp', canonical_name: 'MCP', concept_type: 'Technology' },
          { entry_id: 'canon_agent_harness', canonical_name: 'Agent Harness', concept_type: 'Solution' },
        ],
      },
    })
    getRegistryConceptGraph.mockResolvedValue({
      data: {
        concept_id: 'canon_mcp',
        graph_status: 'not_available',
        node_count: 0,
        edge_count: 0,
        cross_article_link_count: 0,
        graph: null,
      },
    })
    getWikiIntakeCandidate.mockResolvedValue({
      data: {
        candidate: {
          candidate_id: 'src_agent',
          source_id: 'src_agent',
          source_type: 'wechat_article',
          title: 'Agent Harness 工作流笔记',
          status: 'completed',
          source_file_path: '/tmp/agent.md',
          content_hash: 'sha256:agent',
          auto_processed: {
            processed_at: '2026-05-13T11:21:15+08:00',
            topic_id: 'agent-ready-enterprise-stack',
            compile_run_id: 'compile_agent',
            verified_digest_md_path: '/tmp/agent-digest.md',
          },
        },
        content: '# Agent Harness 工作流笔记\n\n这是 Markdown 原文。',
        decision_digest: {
          markdown: '# 预消化结果\n\n摘要内容。',
          payload: { summary: '摘要内容' },
        },
        topic_context: {
          topic_id: 'agent-ready-enterprise-stack',
          title: 'Agent-ready 企业软件栈',
          article_count: 1,
          needs_review_count: 0,
          cluster_links: [{ cluster_id: 'tc_agent_ready', title: 'Agent-ready 企业软件栈' }],
        },
      },
    })
    window.confirm = vi.fn(() => true)
  })

  it('renders cluster description and grouped link sections', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    expect(getTopicCluster).toHaveBeenCalledWith('tc_agent_ready', { includeCounts: true, includeArticles: true })
    expect(getTopicClusterAssetIndex).toHaveBeenCalledWith('tc_agent_ready')
    expect(wrapper.text()).toContain('聚合企业软件 Agent 化和 Harness。')
    expect(wrapper.text()).toContain('KFC 枢纽')
    expect(wrapper.text()).toContain('研究项目')
    expect(wrapper.find('.topic-folder-card').text()).toContain('Wiki 主题')
    expect(wrapper.find('.topic-folder-card').text()).toContain('2 篇文章')
    expect(wrapper.find('.topic-folder-card').text()).toContain('点击展开/收起文章')
    expect(wrapper.findAll('button').some((button) => button.text() === '展开文章')).toBe(false)
    expect(wrapper.findAll('.article-card')).toHaveLength(0)
    expect(wrapper.text()).toContain('研究资产索引')
    expect(wrapper.text()).toContain('3 正式')
    expect(wrapper.text()).toContain('候选')
    expect(wrapper.text()).toContain('正式/候选状态显示在资产卡片上')
    expect(wrapper.text()).not.toContain('概览')
    expect(wrapper.text()).not.toContain('审阅结论')
    expect(wrapper.text()).not.toContain('KFC 资产关系摘要')
    expect(wrapper.text()).not.toContain('进入 KFC 资产关系管理')
    expect(wrapper.text()).not.toContain('正式关联资产')
    expect(wrapper.text()).not.toContain('KFC Theme = 0 表示没有正式关联')
    expect(wrapper.text()).not.toContain('AI Agent系统架构与上下文管理')
    expect(wrapper.text()).not.toContain('Agent Harness 执行治理')
    expect(wrapper.text()).not.toContain('后续研究线索')
    expect(wrapper.text()).not.toContain('阅读 Intake')
    expect(wrapper.text()).not.toContain('查看消化结果')
    expect(wrapper.text()).not.toContain('来源文件')
    await wrapper.findAll('button').find((button) => button.text() === '文章').trigger('click')
    await wrapper.find('.topic-folder-card').trigger('click')
    expect(wrapper.text()).toContain('打开原文')
    expect(wrapper.html()).toContain('https://example.com/agent-harness')
    const articleCard = wrapper.findAll('.article-card').find((card) => card.text().includes('Agent Harness 工作流笔记'))
    await articleCard.trigger('click')
    await flushPromises()
    expect(getWikiIntakeCandidate).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('文章: Agent Harness 工作流笔记')
    expect(wrapper.text()).toContain('文章属于当前主题簇的原因')
    expect(wrapper.text()).toContain('查看 Intake 详情')
    expect(wrapper.text()).toContain('文章概念线索')
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('MCP')
    expect(wrapper.text()).not.toContain("{'concept'")
    expect(wrapper.text()).not.toContain("'summary'")
    expect(wrapper.text()).not.toContain('素材加工台详情')
    expect(wrapper.text()).not.toContain('阅读视图')
    expect(wrapper.text()).not.toContain('Markdown 原文')
    expect(wrapper.text()).not.toContain('预消化结果')
    expect(wrapper.text()).not.toContain('元数据')
    expect(wrapper.text()).not.toContain('这是 Markdown 原文。')
    expect(wrapper.find('a[href="/workspace/wiki-intake?candidate=src_agent"]').attributes('target')).toBe('_blank')
    await wrapper.findAll('button').find((button) => button.text() === '查看 Intake 详情').trigger('click')
    await flushPromises()
    expect(getWikiIntakeCandidate).toHaveBeenCalledWith('src_agent')
    const intakePane = wrapper.find('.preview-pane--wiki-intake')
    expect(intakePane.exists()).toBe(true)
    expect(intakePane.find('.intake-preview-section').exists()).toBe(true)
    expect(intakePane.find('.embedded-intake-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('Wiki Intake')
    expect(wrapper.text()).toContain('Agent Harness 工作流笔记')
    expect(wrapper.text()).toContain('素材加工台详情')
    expect(wrapper.text()).toContain('来自 Wiki Topic: Agent-ready 企业软件栈')
    expect(wrapper.text()).toContain('阅读视图')
    expect(wrapper.text()).toContain('Markdown 原文')
    expect(wrapper.text()).toContain('预消化结果')
    expect(wrapper.text()).toContain('元数据')
    expect(wrapper.text()).toContain('这是 Markdown 原文。')
    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    expect(wrapper.text()).toContain('KFC 资产关系管理')
    expect(wrapper.text()).toContain('KFC 主题关系')
    expect(wrapper.text()).toContain('KFC 概念资产')
    expect(wrapper.text()).toContain('研究项目关系')
    expect(wrapper.text()).toContain('已正式关联')
    expect(wrapper.text()).toContain('来自已关联主题')
    expect(wrapper.text()).toContain('Agent Harness 沉淀概念')
    expect(wrapper.text()).toContain('从 KFC 加工篮自动沉淀的可用 Concept 资产')
    expect(wrapper.text()).toContain('Agent Harness 执行治理')
    expect(wrapper.text()).toContain('自动沉淀资产可继续编辑、解除绑定或废弃')
    const themeHubLink = wrapper.find('a[href="/workspace/themes/gtheme_agent_candidate"]')
    expect(themeHubLink.attributes('target')).toBe('_blank')
    expect(themeHubLink.attributes('rel')).toContain('noopener')
    await wrapper.findAll('button').find((button) => button.text() === '证据线索').trigger('click')
    expect(wrapper.text()).toContain('所属研究项目：华为云 Agent-ready 企业软件栈战略研究')
    expect(wrapper.text()).toContain('证据、洞察、笔记和草稿材料都是项目范围或只读候选')
    expect(wrapper.text()).not.toContain('自动建链')
    expect(wrapper.text()).not.toContain('自动创建 ResearchProject')
    expect(wrapper.text()).not.toContain('运行模型')
  })

  it('renders asset index error without hiding loaded cluster detail', async () => {
    getTopicClusterAssetIndex.mockRejectedValue(new Error('asset-index failed'))
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('Agent-ready 企业软件栈')
    expect(wrapper.text()).toContain('asset-index failed')
  })

  it('adds article concept and evidence slices to the KFC promotion basket', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.find('.topic-folder-card').trigger('click')
    const conceptButton = wrapper.findAll('button').find((button) => button.text() === '加入加工篮')
    await conceptButton.trigger('click')
    await flushPromises()

    expect(createTopicClusterMaterialSlice).toHaveBeenCalledWith(
      'tc_agent_ready',
      expect.objectContaining({
        slice_type: 'concept_lead',
        title: 'Agent Harness',
        summary: '从 Wiki 粗加工提取的 Agent Harness 概念线索。',
        source_article_id: 'src_agent',
        source_markdown_path: '/tmp/agent.md',
        linked_wiki_topic: 'agent-ready-enterprise-stack',
        create_promotion: true,
        created_from: 'topic_cluster_detail.article_card.concept_lead',
      }),
    )
    expect(wrapper.text()).toContain('KFC 加工篮')

    const evidenceButton = wrapper.findAll('button').find((button) => button.text() === '证据片段')
    await evidenceButton.trigger('click')
    await flushPromises()
    expect(createTopicClusterMaterialSlice).toHaveBeenLastCalledWith(
      'tc_agent_ready',
      expect.objectContaining({
        slice_type: 'evidence_slice',
        title: 'Agent Harness 工作流笔记',
        source_article_id: 'src_agent',
      }),
    )
  })

  it('renders the KFC promotion basket with primary actions and collapsed trace', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('KFC 加工篮')).trigger('click')
    await flushPromises()

    expect(getTopicClusterPromotionBasket).toHaveBeenCalledWith('tc_agent_ready')
    expect(wrapper.text()).toContain('任务队列')
    expect(wrapper.text()).toContain('待处理 1')
    expect(wrapper.text()).toContain('已沉淀 0')
    expect(wrapper.text()).toContain('建议关联已有概念')
    expect(wrapper.text()).toContain('推荐动作')
    expect(wrapper.text()).toContain('匹配原因')
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('关联已有概念')
    expect(wrapper.text()).toContain('沉淀为新概念')
    expect(wrapper.text()).toContain('作为项目证据')
    expect(wrapper.text()).toContain('忽略')
    expect(wrapper.text()).toContain('匹配已有概念')
    expect(wrapper.text()).not.toContain('批量沉淀为新概念')
    expect(wrapper.text()).toContain('置信度 82%')
    expect(wrapper.text()).toContain('core_concepts 命中 Agent Harness。')
    const trace = wrapper.find('.promotion-trace-details')
    expect(trace.exists()).toBe(true)
    expect(trace.attributes('open')).toBeUndefined()
  })

  it('preserves full processing context when opening concept matching from article leads and basket items', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.find('.topic-folder-card').trigger('click')
    await flushPromises()
    await wrapper.find('.article-paper-card').trigger('click')
    await flushPromises()

    const articleLeadHref = wrapper
      .findAll('a')
      .find((link) => link.attributes('href')?.includes('query=Agent+Harness'))
      ?.attributes('href')
    expect(articleLeadHref).toContain('/workspace/registry')
    expect(articleLeadHref).toContain('from=lead')
    expect(articleLeadHref).toContain('query=Agent+Harness')
    expect(articleLeadHref).toContain('lead_id=lp_agent_harness')
    expect(articleLeadHref).toContain('promotion_id=lp_agent_harness')
    expect(articleLeadHref).toContain('slice_id=ms_agent_harness')
    expect(articleLeadHref).toContain('article_id=src_agent')
    expect(articleLeadHref).toContain('cluster_id=tc_agent_ready')
    expect(articleLeadHref).toContain('selected=canon_agent_harness')
    expect(wrapper.text()).toContain('匹配：Agent Harness')

    await wrapper.findAll('button').find((button) => button.text().includes('KFC 加工篮')).trigger('click')
    await flushPromises()
    const basketHref = wrapper
      .findAll('a')
      .filter((link) => link.text() === '匹配已有概念')
      .at(-1)
      ?.attributes('href')
    expect(basketHref).toContain('from=basket')
    expect(basketHref).toContain('lead_id=lp_agent_harness')
    expect(basketHref).toContain('promotion_id=lp_agent_harness')
    expect(basketHref).toContain('slice_id=ms_agent_harness')
    expect(basketHref).toContain('article_id=src_agent')
    expect(basketHref).toContain('cluster_id=tc_agent_ready')
    expect(basketHref).toContain('selected=canon_agent_harness')
  })

  it('renders article processing review cards and persists P0 correction actions', async () => {
    window.prompt = vi.fn().mockReturnValueOnce('enables')
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.find('.topic-folder-card').trigger('click')
    await flushPromises()
    await wrapper.find('.article-paper-card').trigger('click')
    await flushPromises()

    expect(getTopicClusterArticleProcessingReview).toHaveBeenCalledWith('tc_agent_ready', 'src_agent')
    expect(wrapper.text()).toContain('文章加工摘要')
    expect(wrapper.text()).toContain('概念线索')
    expect(wrapper.text()).toContain('证据线索')
    expect(wrapper.text()).toContain('关系候选')
    expect(wrapper.text()).toContain('注册表备选项')
    expect(wrapper.text()).toContain('Agent Runtime')
    expect(wrapper.text()).toContain('引文较弱')
    expect(wrapper.text()).toContain('修改关系类型')

    await wrapper.findAll('.alternative-match-btn').find((button) => button.text().includes('Agent Runtime')).trigger('click')
    await flushPromises()
    expect(applyLeadPromotionAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'lp_agent_harness',
      expect.objectContaining({
        action: 'switch_registry_match',
        target: expect.objectContaining({ registry_entry_id: 'canon_agent_runtime' }),
      }),
    )

    await wrapper.findAll('button').find((button) => button.text() === '引文较弱').trigger('click')
    await flushPromises()
    expect(applyLeadPromotionAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'lp_agent_harness',
      expect.objectContaining({ action: 'review_quote', quote_status: 'weak' }),
    )

    await wrapper.findAll('button').find((button) => button.text() === '修改关系类型').trigger('click')
    await flushPromises()
    expect(applyRelationCandidateAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'relcand_agent_harness_runtime',
      expect.objectContaining({ action: 'change_relation_type', relation_type: 'enables' }),
    )
  })

  it('renders P1 grouped article review workspace and sends explicit batch selections', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.find('.topic-folder-card').trigger('click')
    await flushPromises()
    await wrapper.find('.article-paper-card').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="article-completion-summary"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="article-concept-leads"]').exists()).toBe(true)
    expect(wrapper.find('.concept-lead-row').exists()).toBe(true)
    expect(wrapper.html().indexOf('文章概念线索')).toBeLessThan(wrapper.html().indexOf('文章加工摘要'))
    expect(wrapper.text()).toContain('有风险待处理')
    expect(wrapper.text()).toContain('待审核')
    expect(wrapper.text()).toContain('高置信可快速确认')
    expect(wrapper.text()).toContain('低置信 / 需人工判断')
    expect(wrapper.text()).toContain('证据弱 / 引文需核对')
    expect(wrapper.text()).toContain('关系候选待确认')
    expect(wrapper.find('[data-review-group="processed"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('引文需核对')
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('contains')
    expect(wrapper.text()).toContain('Agent Runtime')

    expect(wrapper.findAll('button').some((button) => button.text().includes('批量确认概念'))).toBe(false)
    expect(wrapper.text()).not.toContain('0 项')

    const highGroup = wrapper.find('[data-review-group="high_confidence_quick_confirm"]')
    const checkbox = highGroup.find('input[type="checkbox"]')
    expect(checkbox.attributes('disabled')).toBeUndefined()
    await checkbox.setValue(true)
    await flushPromises()

    expect(wrapper.findAll('button').some((button) => button.text().includes('批量确认概念') && button.text().includes('1 项'))).toBe(true)
    await wrapper.findAll('button').find((button) => button.text().includes('批量确认概念') && button.text().includes('1 项')).trigger('click')
    await flushPromises()

    expect(applyArticleProcessingBatchAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'src_agent',
      expect.objectContaining({
        action_type: 'confirm_high_confidence_concepts',
        card_ids: ['lp_agent_harness'],
        reviewer: 'local',
      }),
    )
    expect(wrapper.text()).toContain('已应用 1 / 已跳过 0')
  })

  it('shows post-materialization state and governance actions in the KFC basket', async () => {
    getTopicClusterPromotionBasket.mockResolvedValue({
      data: {
        cluster_id: 'tc_agent_ready',
        counts: {
          pending: 0,
          materialized_concept: 1,
          linked: 0,
          candidate_created: 0,
          added_to_project_evidence: 0,
          ignored: 0,
        },
        items: [
          {
            promotion_id: 'lp_materialized',
            slice_id: 'ms_agent_harness',
            lead_type: 'concept_lead',
            title: 'Agent Harness',
            summary: '从 Wiki 粗加工提取的 Agent Harness 概念线索。',
            source_quote: 'Agent Harness 需要权限审批、回滚和审计。',
            source_context: '企业 Agent Harness 需要权限审批、回滚和审计。',
            extraction_reason: 'core_concepts 命中 Agent Harness。',
            confidence: 0.91,
            source: {
              source_article_id: 'src_agent',
              source_title: 'Agent Harness 工作流笔记',
              source_markdown_path: '/tmp/agent.md',
              source_content_hash: 'sha256:agent',
              linked_wiki_topic: 'agent-harness',
            },
            linked_topic_cluster: 'tc_agent_ready',
            linked_research_project: 'rp_current',
            review_status: 'materialized_concept',
            decision: 'deposit_as_new_concept',
            target: {
              target_type: 'concept_registry_entry',
              target_id: 'canon_agent_harness',
              target_label: 'Agent Harness',
            },
            concept: { concept_id: 'canon_agent_harness', asset_type: 'concept' },
            materialized_concept: {
              concept_id: 'canon_agent_harness',
              canonical_name: 'Agent Harness',
              lifecycle_status: 'active',
              quality_state: 'machine_generated',
              review_state: 'unreviewed',
            },
            created_at: '2026-05-15T10:00:00',
            updated_at: '2026-05-15T10:02:00',
          },
        ],
      },
    })
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('KFC 加工篮')).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已沉淀 1')
    expect(wrapper.text()).toContain('已沉淀为概念')
    expect(wrapper.text()).toContain('查看概念')
    expect(wrapper.text()).toContain('编辑概念')
    expect(wrapper.text()).toContain('解除关联')
    expect(wrapper.text()).toContain('标记错误 / 废弃')
    expect(wrapper.text()).toContain('合并到已有条目')
    expect(wrapper.text()).not.toContain('沉淀为新概念')
  })

  it('applies lead promotion actions through the basket API', async () => {
    window.localStorage.setItem('knowledge-fabric:current-research-project', JSON.stringify({
      id: 'rp_current',
      title: 'Current Project',
      status: 'active',
    }))
    getResearchProject.mockResolvedValue({
      data: {
        id: 'rp_current',
        title: 'Current Project',
        status: 'active',
        linked_concepts: [],
        evidence_items: [],
      },
    })
    window.prompt = vi.fn()
      .mockReturnValueOnce('canon_agent_harness')
      .mockReturnValueOnce('忽略低价值线索')
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text().includes('KFC 加工篮')).trigger('click')
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '关联已有概念').trigger('click')
    await flushPromises()
    expect(applyLeadPromotionAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'lp_agent_harness',
      expect.objectContaining({
        action: 'link_existing_registry_entry',
        target: expect.objectContaining({ registry_entry_id: 'canon_agent_harness' }),
      }),
    )

    await wrapper.findAll('button').find((button) => button.text() === '沉淀为新概念').trigger('click')
    await flushPromises()
    expect(applyLeadPromotionAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'lp_agent_harness',
      expect.objectContaining({
        action: 'deposit_as_new_concept',
        concept: expect.objectContaining({ label: 'Agent Harness' }),
      }),
    )

    await wrapper.findAll('button').find((button) => button.text() === '作为项目证据').trigger('click')
    await flushPromises()
    expect(applyLeadPromotionAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'lp_agent_harness',
      expect.objectContaining({
        action: 'add_as_project_evidence',
        target: expect.objectContaining({ research_project_id: 'rp_current' }),
      }),
    )

    await wrapper.findAll('button').find((button) => button.text() === '忽略').trigger('click')
    await flushPromises()
    expect(applyLeadPromotionAction).toHaveBeenCalledWith(
      'tc_agent_ready',
      'lp_agent_harness',
      expect.objectContaining({ action: 'ignore', reason: '忽略低价值线索' }),
    )
  })

  it('renders an error state when the cluster cannot load', async () => {
    getTopicCluster.mockRejectedValue(new Error('topic cluster not found'))
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('加载失败')
    expect(wrapper.text()).toContain('topic cluster not found')
  })

  it('edits cluster metadata', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.find('.edit-btn').trigger('click')
    await wrapper.find('input').setValue('Updated Agent Stack')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(updateTopicCluster).toHaveBeenCalledWith(
      'tc_agent_ready',
      expect.objectContaining({ title: 'Updated Agent Stack' }),
    )
    expect(wrapper.text()).toContain('Updated Agent Stack')
  })

  it('adds, patches, and removes links', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '系统诊断').trigger('click')
    const addButton = wrapper.findAll('button').find((button) => button.text().includes('添加关联'))
    await addButton.trigger('click')
    const inputs = wrapper.findAll('input')
    await inputs.at(0).setValue('new-topic')
    await wrapper.findAll('form').at(0).trigger('submit.prevent')
    await flushPromises()

    expect(createTopicClusterLink).toHaveBeenCalledWith(
      'tc_agent_ready',
      expect.objectContaining({ target_type: 'wiki_topic', target_id: 'new-topic' }),
    )

    const roleSelect = wrapper.find('.link-actions select')
    await roleSelect.setValue('supporting')
    await flushPromises()
    expect(updateTopicClusterLink).toHaveBeenCalledWith('tcl_wiki', { role: 'supporting' })

    const removeButton = wrapper.find('.danger-btn')
    await removeButton.trigger('click')
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('不会删除主题、研究项目、概念或 Markdown'))
    expect(deleteTopicClusterLink).toHaveBeenCalledWith('tcl_wiki')
    expect(getTopicCluster).toHaveBeenCalledTimes(1)
    expect(getTopicClusterAssetIndex).toHaveBeenCalledTimes(1)
  })

  it('explains empty formal KFC and ResearchProject panels while showing candidates', async () => {
    getTopicCluster.mockResolvedValueOnce({
      data: {
        cluster: {
          cluster_id: 'tc_agent_ready',
          title: 'Agent-ready 企业软件栈',
          status: 'active',
          strategic_relevance: 'high',
          counts: { wiki_topics: 1, kfc_themes: 0, research_projects: 0 },
          article_count: 0,
          linked_topic_articles: [],
        },
        links_by_type: { wiki_topic: [], kfc_theme: [], research_project: [] },
        warnings: [],
      },
    })
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    expect(wrapper.text()).toContain('KFC 主题关系')
    expect(wrapper.text()).toContain('KFC 概念资产')
    expect(wrapper.text()).toContain('研究项目关系')
    expect(wrapper.text()).toContain('华为云 Agent-ready 企业软件栈战略研究')
  })

  it('promotes a supported candidate with local state and no confirm or page reload', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const promoteButton = wrapper.findAll('button').find((button) => button.text() === '建立关联')
    await promoteButton.trigger('click')
    await flushPromises()

    expect(window.confirm).not.toHaveBeenCalled()
    expect(createTopicClusterLink).toHaveBeenCalledWith(
      'tc_agent_ready',
      expect.objectContaining({
        target_type: 'kfc_theme',
        target_id: 'gtheme_agent_candidate',
        status: 'accepted',
        source: 'candidate_promotion',
        review_decision: expect.objectContaining({ decision: 'accepted' }),
      }),
    )
    expect(getTopicCluster).toHaveBeenCalledTimes(1)
    expect(getTopicClusterAssetIndex).toHaveBeenCalledTimes(1)
    const promotedCard = wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('Agent Harness 执行治理'))
    expect(promotedCard.text()).toContain('已正式关联')
    expect(promotedCard.text()).toContain('取消主题关联')
    expect(promotedCard.text()).not.toContain('建立关联')
  })

  it('keeps KFC Theme card order stable when states change locally', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const initialOrder = relationshipCardIds(wrapper, 'kfc_theme')
    expect(initialOrder).toEqual(['gtheme_agent', 'gtheme_agent_candidate', 'gtheme_agent_candidate_2'])

    const candidateCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-id') === 'gtheme_agent_candidate_2')
    await candidateCard.findAll('button').find((button) => button.text() === '建立关联').trigger('click')
    await flushPromises()
    expect(relationshipCardIds(wrapper, 'kfc_theme')).toEqual(initialOrder)
    expect(candidateCard.attributes('data-state')).toBe('linked')
    expect(candidateCard.text()).toContain('取消主题关联')

    const linkedCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-id') === 'gtheme_agent')
    await linkedCard.findAll('button').find((button) => button.text() === '取消主题关联').trigger('click')
    await flushPromises()
    expect(relationshipCardIds(wrapper, 'kfc_theme')).toEqual(initialOrder)
    expect(linkedCard.attributes('data-state')).toBe('candidate')
    expect(linkedCard.text()).toContain('建立关联')
  })

  it('keeps ignored and restored cards in place while changing their visual state', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const initialOrder = relationshipCardIds(wrapper, 'kfc_theme')
    const candidateCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-id') === 'gtheme_agent_candidate')

    await candidateCard.findAll('button').find((button) => button.text() === '忽略候选').trigger('click')
    await flushPromises()
    expect(relationshipCardIds(wrapper, 'kfc_theme')).toEqual(initialOrder)
    expect(candidateCard.attributes('data-state')).toBe('ignored')
    expect(candidateCard.text()).toContain('已忽略')
    expect(candidateCard.text()).toContain('恢复候选')

    await candidateCard.findAll('button').find((button) => button.text() === '恢复候选').trigger('click')
    await flushPromises()
    expect(relationshipCardIds(wrapper, 'kfc_theme')).toEqual(initialOrder)
    expect(candidateCard.attributes('data-state')).toBe('candidate')
    expect(candidateCard.text()).toContain('候选')
  })

  it('promotes the exact clicked Theme card when duplicate titles exist', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const duplicateThemeCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-id') === 'gtheme_agent_candidate_2')
    expect(duplicateThemeCard.text()).toContain('Agent Harness 执行治理')
    await duplicateThemeCard.findAll('button').find((button) => button.text() === '建立关联').trigger('click')
    await flushPromises()

    expect(createTopicClusterLink).toHaveBeenCalledWith(
      'tc_agent_ready',
      expect.objectContaining({
        target_type: 'kfc_theme',
        target_id: 'gtheme_agent_candidate_2',
        target_title: 'Agent Harness 执行治理',
      }),
    )
    expect(duplicateThemeCard.text()).toContain('gtheme_agent_candidate_2')
  })

  it('promotes the exact clicked ResearchProject card when duplicate titles exist', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const duplicateProjectCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-id') === 'rp_agent_duplicate_title')
    expect(duplicateProjectCard.text()).toContain('华为云 Agent-ready 企业软件栈战略研究')
    await duplicateProjectCard.findAll('button').find((button) => button.text() === '关联当前主题簇到项目').trigger('click')
    await flushPromises()

    expect(createTopicClusterLink).toHaveBeenCalledWith(
      'tc_agent_ready',
      expect.objectContaining({
        target_type: 'research_project',
        target_id: 'rp_agent_duplicate_title',
        target_title: '华为云 Agent-ready 企业软件栈战略研究',
      }),
    )
  })

  it('rolls back local promotion state and shows inline error when promotion fails', async () => {
    createTopicClusterLink.mockRejectedValueOnce(new Error('sidecar write failed'))
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const promoteButton = wrapper.findAll('button').find((button) => button.text() === '建立关联')
    await promoteButton.trigger('click')
    await flushPromises()

    expect(window.confirm).not.toHaveBeenCalled()
    const candidateCard = wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('Agent Harness 执行治理'))
    expect(candidateCard.text()).toContain('候选')
    expect(candidateCard.text()).toContain('建立关联')
    expect(candidateCard.text()).toContain('sidecar write failed')
  })

  it('shows cancel action for legacy confirmed Theme direct links', async () => {
    getTopicClusterAssetIndex.mockResolvedValueOnce({
      data: {
        cluster_id: 'tc_agent_ready',
        cluster_title: 'Agent-ready 企业软件栈',
        generated_at: '2026-05-13T12:00:00+08:00',
        direct_links: {
          wiki_topics: [],
          kfc_themes: [
            {
              link_id: 'tcl_theme_legacy',
              target_type: 'kfc_theme',
              target_id: 'gtheme_legacy',
              target_title: 'AI开发流程质量控制',
              association_type: 'formal',
              confirmation_status: 'confirmed',
              status: 'accepted',
              rationale: 'Promoted from Topic Cluster candidate.',
            },
          ],
          research_projects: [],
        },
        indirect_assets: { articles: [], wiki_topics: [], representative_articles: [] },
        candidate_assets: { kfc_themes: [], concepts: [], research_projects: [], evidence: [], insights: [], notes: [], artifacts: [] },
        counts: {
          direct_wiki_topic_count: 0,
          direct_kfc_theme_count: 1,
          direct_research_project_count: 0,
          indirect_article_count: 0,
          candidate_concept_count: 0,
          candidate_theme_count: 0,
          candidate_research_project_count: 0,
          candidate_evidence_count: 0,
          candidate_insight_count: 0,
          candidate_note_count: 0,
          candidate_artifact_count: 0,
        },
        warnings: [],
      },
    })
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    expect(wrapper.text()).toContain('AI开发流程质量控制')
    expect(wrapper.text()).toContain('已正式关联')
    const cancelButton = wrapper.findAll('button').find((button) => button.text() === '取消主题关联')
    expect(cancelButton.exists()).toBe(true)
    await cancelButton.trigger('click')
    await flushPromises()
    expect(window.confirm).not.toHaveBeenCalled()
    expect(deleteTopicClusterLink).toHaveBeenCalledWith('tcl_theme_legacy')
    expect(getTopicCluster).toHaveBeenCalledTimes(1)
    expect(getTopicClusterAssetIndex).toHaveBeenCalledTimes(1)
    const candidateCard = wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('AI开发流程质量控制'))
    expect(candidateCard.text()).toContain('候选')
    expect(candidateCard.text()).toContain('建立关联')
  })

  it('rolls back unlink state and shows inline error when unlink fails', async () => {
    deleteTopicClusterLink.mockRejectedValueOnce(new Error('delete failed'))
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const cancelButton = wrapper.findAll('button').find((button) => button.text() === '取消主题关联')
    await cancelButton.trigger('click')
    await flushPromises()

    expect(window.confirm).not.toHaveBeenCalled()
    const themeCard = wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('AI Agent系统架构与上下文管理'))
    expect(themeCard.text()).toContain('已正式关联')
    expect(themeCard.text()).toContain('取消主题关联')
    expect(themeCard.text()).toContain('delete failed')
  })

  it('adds and removes concept basket state without confirm or Cluster-Concept links', async () => {
    window.localStorage.setItem('knowledge-fabric:current-research-project', JSON.stringify({
      id: 'rp_current',
      title: 'Current Project',
      linked_concepts: [],
      linked_topic_clusters: [],
    }))
    getResearchProject.mockResolvedValue({
      data: {
        id: 'rp_current',
        title: 'Current Project',
        linked_concepts: [],
        linked_topic_clusters: [],
      },
    })
    updateResearchProject
      .mockResolvedValueOnce({
        data: {
          id: 'rp_current',
          title: 'Current Project',
          linked_concepts: [{ entry_id: 'canon_agent_harness', title: 'Agent Harness' }],
          linked_topic_clusters: [],
        },
      })
      .mockResolvedValueOnce({
        data: {
          id: 'rp_current',
          title: 'Current Project',
          linked_concepts: [],
          linked_topic_clusters: [],
        },
      })
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const conceptCard = () => wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('概念 / Solution'))
    await conceptCard().findAll('button').find((button) => button.text() === '加入当前项目概念篮').trigger('click')
    await flushPromises()

    expect(window.confirm).not.toHaveBeenCalled()
    expect(createTopicClusterLink).not.toHaveBeenCalled()
    expect(conceptCard().text()).toContain('已加入当前项目')
    expect(conceptCard().text()).toContain('移出项目概念篮')
    expect(conceptCard().text()).not.toContain('取消关联')

    await conceptCard().findAll('button').find((button) => button.text() === '移出项目概念篮').trigger('click')
    await flushPromises()
    expect(window.confirm).not.toHaveBeenCalled()
    expect(createTopicClusterLink).not.toHaveBeenCalled()
    expect(conceptCard().text()).toContain('候选')
    expect(conceptCard().text()).toContain('加入当前项目概念篮')
  })

  it('filters grouped KFC candidates and opens the right-side exploration pane with missing-state copy', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    expect(wrapper.text()).toContain('Agent Harness')
    const selects = wrapper.findAll('.candidate-filters select')
    await selects.at(3).setValue('medium')
    expect(wrapper.text()).not.toContain('概念 / Solution')
    await selects.at(3).setValue('high')
    expect(wrapper.text()).toContain('概念 / Solution')

    const conceptCard = wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('概念 / Solution'))
    await conceptCard.findAll('button').find((button) => button.text() === '右侧查看').trigger('click')
    expect(wrapper.text()).toContain('关系探索工作台')
    expect(wrapper.text()).toContain('概念: Agent Harness')
    expect(wrapper.text()).toContain('暂无定义/摘要')
    expect(wrapper.text()).toContain('暂无文章级来源链路')
    expect(wrapper.text()).toContain('概念不建立 主题簇-概念 正式关联')
  })

  it('opens only canonical Concept registry ids and does not route extracted concept leads by label', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const canonicalConceptCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-type') === 'concept' && card.attributes('data-target-id') === 'canon_agent_harness')
    expect(canonicalConceptCard.findAll('a').some((link) => link.attributes('href') === '/workspace/entry/canon_agent_harness')).toBe(true)

    await wrapper.findAll('button').find((button) => button.text() === '文章').trigger('click')
    await wrapper.find('.topic-folder-card').trigger('click')
    const articleCard = wrapper.findAll('.article-card')
      .find((card) => card.text().includes('Agent Harness 工作流笔记'))
    await articleCard.trigger('click')
    await wrapper.findAll('.preview-related-row')
      .find((button) => button.text().includes('MCP'))
      .trigger('click')

    expect(wrapper.text()).toContain('概念线索: MCP')
    expect(wrapper.text()).toContain('尚未解析到概念注册表条目')
    expect(wrapper.findAll('a').some((link) => link.attributes('href') === '/workspace/entry/MCP')).toBe(false)
    expect(wrapper.findAll('a').some((link) => {
      const href = link.attributes('href') || ''
      return href.startsWith('/workspace/registry?')
        && href.includes('tab=concepts')
        && href.includes('query=MCP')
        && href.includes('from=lead')
        && href.includes('cluster_id=tc_agent_ready')
        && href.includes('article_id=src_agent')
    })).toBe(true)
    expect(createTopicClusterLink).not.toHaveBeenCalled()
    expect(updateResearchProject).not.toHaveBeenCalled()
  })

  it('embeds canonical Concept detail from Theme related Concepts in the second right-side pane', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const themeCard = wrapper.findAll('.candidate-review-card')
      .find((card) => card.attributes('data-target-type') === 'kfc_theme' && card.text().includes('AI Agent系统架构与上下文管理'))
    await themeCard.findAll('button').find((button) => button.text() === '右侧查看').trigger('click')
    await flushPromises()
    expect(getThemePanorama).toHaveBeenCalledWith('gtheme_agent')
    expect(wrapper.text()).toContain('主题下的概念（13）')
    expect(wrapper.text()).not.toContain('关联对象')
    expect(themeCard.classes()).toContain('selected')
    const provenanceStrip = wrapper.find('.provenance-strip')
    expect(provenanceStrip.exists()).toBe(true)
    expect(provenanceStrip.text()).toContain('状态 已正式关联')
    expect(provenanceStrip.text()).toContain('来源 已有正式关联记录')
    expect(provenanceStrip.text()).toContain('概念 1')
    expect(wrapper.find('.provenance-details').element.open).toBe(false)
    expect(wrapper.findAll('.theme-concept-row')).toHaveLength(13)
    expect(wrapper.text()).toContain('完整概念 12')

    const conceptButton = wrapper.findAll('.theme-concept-row')
      .find((button) => button.text().includes('MCP'))
    const appContent = wrapper.find('.app-content')
    const stackEl = wrapper.find('.exploration-stack').element
    const stackScrollTo = vi.fn(function scrollToStub(options) {
      this.scrollTop = options?.top || 0
    })
    stackEl.scrollTop = 180
    stackEl.scrollTo = stackScrollTo
    const rectSpy = vi.spyOn(Element.prototype, 'getBoundingClientRect')
      .mockImplementation(function getBoundingClientRectStub() {
        if (this.classList?.contains('exploration-stack')) {
          return { top: 100, bottom: 700, left: 0, right: 600, width: 600, height: 600, x: 0, y: 100, toJSON: () => ({}) }
        }
        if (this.classList?.contains('preview-pane') && this.dataset?.paneKey?.startsWith('concept_detail:')) {
          return { top: 160, bottom: 1260, left: 0, right: 560, width: 560, height: 1100, x: 0, y: 160, toJSON: () => ({}) }
        }
        return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON: () => ({}) }
      })
    appContent.element.scrollTop = 640
    Element.prototype.scrollIntoView.mockClear()
    await conceptButton.trigger('click')
    await flushPromises()
    rectSpy.mockRestore()

    expect(wrapper.findAll('.preview-pane')).toHaveLength(2)
    expect(conceptButton.classes()).toContain('selected')
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
    expect(appContent.element.scrollTop).toBe(640)
    expect(stackScrollTo).not.toHaveBeenCalled()
    expect(stackEl.scrollTop).toBe(180)
    expect(getRegistryConcept).toHaveBeenCalledWith('canon_mcp')
    expect(listCrossRelations).toHaveBeenCalledWith({ entry_id: 'canon_mcp' })
    expect(wrapper.text()).toContain('Cluster')
    expect(wrapper.text()).toContain('Theme')
    expect(wrapper.text()).toContain('Concept')
    expect(wrapper.text()).not.toContain('CANONICAL CONCEPT')
    expect(wrapper.text()).not.toContain('CONCEPT WORKBENCH')
    expect(wrapper.text()).not.toContain('概念工作台')
    expect(wrapper.text()).toContain('MCP')
    expect(wrapper.text()).toContain('Model Context Protocol。')
    expect(wrapper.text()).toContain('相关概念')
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('MCP 与 Agent Harness 共同支撑工具编排上下文。')
    expect(wrapper.text()).not.toContain('概念是知识线索和项目概念资产')
    expect(wrapper.text()).not.toContain('不建立主题簇-概念正式关联')
	    expect(wrapper.text()).not.toContain('项目来源默认折叠')
	    expect(wrapper.text()).not.toContain('跨文关系默认折叠')
	    const sourceTraceLink = wrapper.findAll('.preview-pane').at(1).findAll('a')
	      .find((link) => link.text() === '查看原文')
	    expect(sourceTraceLink.exists()).toBe(true)
	    expect(sourceTraceLink.attributes('href')).toBe('/workspace/proj_agent/article?view=reading&focusNode=mcp&from=registry')
	    expect(sourceTraceLink.attributes('title')).toBe('在文章阅读视图中查看该概念的来源位置')
	    const conceptPane = wrapper.find('.concept-detail-preview-section')
	    expect(conceptPane.text().indexOf('相关概念')).toBeLessThan(conceptPane.text().indexOf('元信息 / 治理 / 研究项目'))
	    expect(conceptPane.text()).toContain('正式关系')
	    expect(conceptPane.text()).toContain('MCP')
	    expect(conceptPane.text()).toContain('启发')
	    expect(conceptPane.text()).toContain('→')
	    expect(conceptPane.text()).toContain('Agent Harness')
	    expect(conceptPane.text()).toContain('完整概念 1')
	    expect(conceptPane.text()).toContain('同主题邻近')
	    expect(conceptPane.text()).toContain('暂无正式关系说明。')
	    expect(wrapper.text()).toContain('Agent source project')
	    expect(sourceTraceLink.attributes('href')).not.toBe('/workspace/entry/canon_mcp')
	    await conceptPane
	      .findAll('button')
	      .find((button) => button.text().includes('Agent Harness'))
	      .trigger('click')
	    await flushPromises()
	    const panesAfterFallback = wrapper.findAll('.preview-pane')
	    const fallbackPane = panesAfterFallback.at(panesAfterFallback.length - 1)
	    const fallbackLink = fallbackPane.findAll('a').find((link) => link.text() === '打开概念')
	    expect(fallbackLink.exists()).toBe(true)
	    expect(fallbackLink.attributes('href')).toBe('/workspace/entry/canon_agent_harness')
	    expect(fallbackPane.findAll('a').some((link) => link.text() === '查看原文')).toBe(false)
	    expect(createTopicClusterLink).not.toHaveBeenCalled()
	  })

  it('opens Wiki Topic, Article, and second-level related previews without navigating away', async () => {
    const wrapper = mount(TopicClusterDetailPage, {
      global: { stubs: { RouterLink: routerLinkStub, 'router-link': routerLinkStub } },
    })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '文章').trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === '右侧查看').trigger('click')
    expect(wrapper.text()).toContain('Wiki 主题: Agent-ready 企业软件栈')
    expect(wrapper.text()).toContain('关系探索工作台')
    expect(wrapper.findAll('.preview-related-row')).toHaveLength(2)
    expect(wrapper.text()).toContain('Agent Harness 复盘记录')

    const relatedArticleButton = wrapper.findAll('.preview-related-row')
      .find((button) => button.text().includes('Agent Harness 工作流笔记'))
    await relatedArticleButton.trigger('click')
    expect(wrapper.findAll('.preview-pane')).toHaveLength(2)
    expect(wrapper.text()).toContain('文章: Agent Harness 工作流笔记')
    expect(wrapper.text()).toContain('文章概念线索')
    expect(getTopicCluster).toHaveBeenCalledTimes(1)
    expect(getTopicClusterAssetIndex).toHaveBeenCalledTimes(1)
  })

  it('never promotes Concept candidates into TopicClusterLink', async () => {
    const wrapper = mount(TopicClusterDetailPage)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'KFC 枢纽').trigger('click')
    const conceptCard = wrapper.findAll('.candidate-review-card').find((card) => card.text().includes('概念 / Solution'))
    expect(conceptCard.text()).toContain('加入当前项目概念篮')
    expect(conceptCard.text()).not.toContain('建议建立正式关联')
    await conceptCard.find('button').trigger('click')
    expect(createTopicClusterLink).not.toHaveBeenCalled()
  })
})
