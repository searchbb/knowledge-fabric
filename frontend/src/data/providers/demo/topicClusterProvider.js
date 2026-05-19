const clone = (value) => JSON.parse(JSON.stringify(value))

const clusters = [
  {
    cluster_id: 'tc_demo_agent_ready',
    title: 'Agent-ready 企业软件栈',
    description: '聚合企业软件 Agent 化、Harness、权限审批、执行日志和战略控制点。',
    status: 'active',
    strategic_relevance: 'high',
    updated_at: '2026-05-12T10:00:00',
  },
  {
    cluster_id: 'tc_demo_token_economy',
    title: 'AI算力与Token经济',
    description: '聚合算力基础设施、Token 计量、MaaS 市场和 AI 服务经济。',
    status: 'active',
    strategic_relevance: 'high',
    updated_at: '2026-05-12T10:00:00',
  },
]

const links = [
  {
    link_id: 'tcl_demo_agent_wiki',
    cluster_id: 'tc_demo_agent_ready',
    target_type: 'wiki_topic',
    target_id: 'agent-ready-enterprise-stack',
    target_title: 'Agent-ready 企业软件栈',
    role: 'primary',
    status: 'candidate',
    confidence: 0.82,
    rationale: 'Demo Wiki 预消化入口。',
  },
  {
    link_id: 'tcl_demo_agent_theme',
    cluster_id: 'tc_demo_agent_ready',
    target_type: 'kfc_theme',
    target_id: 'gtheme_demo_agent',
    target_title: 'AI Agent系统架构与上下文管理',
    role: 'primary',
    status: 'accepted',
    confidence: 0.86,
    rationale: 'Demo KFC Theme 枢纽。',
  },
  {
    link_id: 'tcl_demo_token_wiki',
    cluster_id: 'tc_demo_token_economy',
    target_type: 'wiki_topic',
    target_id: 'ai-token',
    target_title: 'AI Token',
    role: 'primary',
    status: 'accepted',
    confidence: 0.88,
    rationale: 'Demo Token 经济预消化入口。',
  },
  {
    link_id: 'tcl_demo_token_theme',
    cluster_id: 'tc_demo_token_economy',
    target_type: 'kfc_theme',
    target_id: 'gtheme_demo_token',
    target_title: 'AI算力产业链与Token经济',
    role: 'primary',
    status: 'accepted',
    confidence: 0.9,
    rationale: 'Demo KFC Theme 枢纽。',
  },
]

const refreshRequests = [
  {
    request_id: 'tcr_demo_recent_001',
    type: 'topic_cluster_recluster',
    object_type: 'topic_cluster_refresh_request',
    schema_version: 1,
    scope: 'all',
    status: 'requested',
    created_by: 'human',
    created_at: '2026-05-12T10:00:00',
    updated_at: '2026-05-12T10:00:00',
    inputs: {
      include_wiki_topics: true,
      include_kfc_themes: true,
      include_kfc_concepts: false,
      include_research_projects: false,
    },
    rules: {
      do_not_auto_apply: true,
      proposal_only: true,
      preserve_human_accepted_links: true,
      human_review_required: true,
      kfc_must_not_execute_model: true,
      kfc_must_not_start_external_process: true,
      kfc_must_not_auto_create_research_project: true,
    },
  },
]

const proposals = [
  {
    proposal_id: 'tcp_demo_agent_ready',
    request_id: 'tcr_demo_recent_001',
    status: 'ready_for_review',
    created_at: '2026-05-12T10:05:00',
    summary: { new_clusters: 1, candidate_links: 1 },
    warnings: [{ code: 'manual_review', message: 'Merge suggestions are review-only.' }],
    actions: [
      {
        action_id: 'create_cluster:tc_demo_new_agent_ready',
        action_type: 'create_cluster',
        confidence: 0.86,
        rationale: '多个主题围绕 Agent-ready 企业软件栈展开。',
        payload: {
          cluster_id: 'tc_demo_new_agent_ready',
          title: 'Agent-ready 企业软件栈扩展',
          description: 'Demo proposal cluster',
          status: 'candidate',
          strategic_relevance: 'high',
        },
      },
      {
        action_id: 'add_link:tcl_demo_new_harness',
        action_type: 'add_link',
        confidence: 0.78,
        rationale: 'Agent Harness 是该 Cluster 的支撑主题。',
        payload: {
          link_id: 'tcl_demo_new_harness',
          cluster_id: 'tc_demo_agent_ready',
          target_type: 'wiki_topic',
          target_id: 'agent-harness',
          target_title: 'Agent Harness',
          role: 'supporting',
          status: 'candidate',
        },
      },
      {
        action_id: 'merge_cluster:tc_old->tc_new',
        action_type: 'merge_cluster',
        confidence: 0.42,
        rationale: '需要人工判断是否合并。',
        payload: { from_cluster_id: 'tc_old', to_cluster_id: 'tc_new' },
      },
    ],
  },
]
const proposalApplications = []
const materialSlices = []
const leadPromotions = []
const relationCandidates = []
const conceptRegistryCandidates = []
const demoConceptRegistryEntries = []

function nextId(prefix) {
  return `${prefix}_demo_${Math.random().toString(16).slice(2, 10)}`
}

function countsFor(clusterId) {
  const selected = links.filter((link) => link.cluster_id === clusterId && link.status !== 'rejected' && !link.deleted)
  return {
    wiki_topics: selected.filter((link) => link.target_type === 'wiki_topic').length,
    kfc_themes: selected.filter((link) => link.target_type === 'kfc_theme').length,
    research_projects: selected.filter((link) => link.target_type === 'research_project').length,
    candidate_links: selected.filter((link) => link.status === 'candidate').length,
    needs_review_links: selected.filter((link) => link.status === 'needs_review').length,
  }
}

const demoTopicArticles = {
  'ai-token': [
    {
      candidate_id: 'src_demo_token_economy',
      source_id: 'src_demo_token_economy',
      topic_id: 'ai-token',
      topic_title: 'AI Token',
      title: 'Token Economy（词元经济）产业链全景报告',
      source_url: 'https://example.com/token-economy',
      status: 'completed',
      processed_at: '2026-05-13T11:21:15+08:00',
      digest_summary: 'Token 计量、模型服务成本和稳定币支付的示例材料。',
      top_concepts: ['token economy', 'AI pricing'],
    },
  ],
}

function withAggregation(cluster, options = {}) {
  const item = { ...clone(cluster), counts: countsFor(cluster.cluster_id) }
  if (!options.includeCounts && !options.includeArticles) return item
  const wikiLinks = links.filter((link) => link.cluster_id === cluster.cluster_id && link.target_type === 'wiki_topic' && link.status !== 'rejected' && !link.deleted)
  const articleGroups = wikiLinks.map((link) => ({
    topic_id: link.target_id,
    title: link.target_title || link.target_id,
    article_count: demoTopicArticles[link.target_id]?.length || 0,
    articles: clone(demoTopicArticles[link.target_id] || []),
  }))
  const representativeArticles = articleGroups.flatMap((group) => group.articles.map((article) => ({ ...article, topic_title: group.title }))).slice(0, 5)
  Object.assign(item, {
    wiki_topic_count: wikiLinks.length,
    kfc_theme_count: links.filter((link) => link.cluster_id === cluster.cluster_id && link.target_type === 'kfc_theme' && link.status !== 'rejected' && !link.deleted).length,
    research_project_count: links.filter((link) => link.cluster_id === cluster.cluster_id && link.target_type === 'research_project' && link.status !== 'rejected' && !link.deleted).length,
    article_count: articleGroups.reduce((total, group) => total + group.article_count, 0),
    representative_articles: representativeArticles,
  })
  if (options.includeArticles) item.linked_topic_articles = articleGroups
  return item
}

function linksByType(clusterId) {
  const grouped = { kfc_theme: [], research_project: [], wiki_topic: [] }
  for (const link of links.filter((item) => item.cluster_id === clusterId && !item.deleted)) {
    grouped[link.target_type].push(clone(link))
  }
  return grouped
}

export async function listTopicClusters(options = {}) {
  const items = clusters.map((cluster) => withAggregation(cluster, options))
  return { success: true, data: { items, total: items.length, warnings: [] } }
}

export async function createTopicCluster(payload) {
  const now = new Date().toISOString()
  const cluster = {
    cluster_id: payload.cluster_id || nextId('tc'),
    title: payload.title,
    description: payload.description || '',
    status: payload.status || 'candidate',
    strategic_relevance: payload.strategic_relevance || 'unknown',
    owner: payload.owner || null,
    created_source: 'demo',
    created_at: now,
    updated_at: now,
  }
  clusters.push(cluster)
  return { success: true, data: { cluster: { ...clone(cluster), counts: countsFor(cluster.cluster_id) }, warnings: [] } }
}

export async function getTopicCluster(clusterId, options = {}) {
  const cluster = clusters.find((item) => item.cluster_id === clusterId)
  if (!cluster) throw new Error(`Demo data not available for topic cluster "${clusterId}".`)
  return {
    success: true,
    data: {
      cluster: withAggregation(cluster, options),
      links_by_type: linksByType(clusterId),
      warnings: [],
    },
  }
}

export async function getTopicClusterAssetIndex(clusterId) {
  const cluster = clusters.find((item) => item.cluster_id === clusterId)
  if (!cluster) throw new Error(`Demo data not available for topic cluster "${clusterId}".`)
  const aggregated = withAggregation(cluster, { includeCounts: true, includeArticles: true })
  const direct = linksByType(clusterId)
  const articles = (aggregated.linked_topic_articles || []).flatMap((group) =>
    (group.articles || []).map((article) => ({
      target_type: 'article',
      target_id: article.candidate_id || article.source_id || article.title,
      target_title: article.title,
      topic_id: group.topic_id,
      topic_title: group.title,
      source_url: article.source_url || '',
      processed_at: article.processed_at || '',
      top_concepts: article.top_concepts || [],
      digest_summary: article.digest_summary || '',
      belongs_to_cluster_reason: [
        `formal wiki_topic link: ${group.topic_id}`,
        'article topic_id matched linked wiki topic',
        ...(article.top_concepts?.length ? [`top concepts overlap: ${article.top_concepts.slice(0, 5).join(', ')}`] : []),
      ],
      routes: {
        wiki_topic: `/workspace/wiki-topics/${group.topic_id}`,
        wiki_intake: `/workspace/wiki-intake?candidate=${article.candidate_id || article.source_id || ''}`,
        ...(article.source_url ? { source_url: article.source_url } : {}),
      },
      association_kind: 'indirect_aggregation',
    })),
  )
  const directLinks = {
    wiki_topics: direct.wiki_topic.map((link) => ({ ...clone(link), association_kind: 'direct_link' })),
    kfc_themes: direct.kfc_theme.map((link) => ({ ...clone(link), association_kind: 'direct_link' })),
    research_projects: direct.research_project.map((link) => ({ ...clone(link), association_kind: 'direct_link' })),
  }
  const candidateTheme = {
    target_type: 'kfc_theme',
    target_id: 'gtheme_demo_harness_candidate',
    target_title: 'Agent Harness 执行治理',
    match_reason: '本地字段命中：agent, harness, 执行治理',
    matched_terms: ['agent', 'harness', '执行治理'],
    matched_fields: ['title', 'description'],
    association_type: 'candidate',
    confirmation_status: 'unconfirmed',
    confidence_hint: 'medium',
    source_kind: 'global_themes',
    source_path: 'backend/uploads/projects/global_themes.json',
    source_path_display: 'backend/uploads/projects/global_themes.json',
    why_candidate: { matched_fields: ['title', 'description'], strong_terms: ['harness', '执行治理'], weak_terms: ['agent'], score_breakdown: { title: 2, description: 1 } },
    risk_note: '只读候选主题；不是正式主题簇链接。',
    promotion_supported: true,
    promotion_action: 'create_topic_cluster_link',
  }
  const candidateConcept = {
    target_type: 'concept',
    target_id: 'canon_demo_agent_harness',
    target_title: 'Agent Harness',
    match_reason: '本地字段命中：agent, harness',
    matched_terms: ['agent', 'harness'],
    matched_fields: ['title'],
    association_type: 'candidate',
    confirmation_status: 'unconfirmed',
    confidence_hint: 'medium',
    source_kind: 'concept_registry',
    source_path: 'backend/uploads/projects/concept_registry.json',
    source_path_display: 'backend/uploads/projects/concept_registry.json',
    why_candidate: { matched_fields: ['title'], strong_terms: ['harness'], weak_terms: ['agent'], score_breakdown: { title: 2 } },
    risk_note: '只读候选概念；P27 不扩展写入 link target_type。',
    promotion_supported: false,
  }
  const candidateProject = {
    target_type: 'research_project',
    target_id: 'rp_demo_agent_harness',
    target_title: 'Agent-ready 战略研究',
    match_reason: '本地字段命中：agent, harness',
    matched_terms: ['agent', 'harness'],
    matched_fields: ['title', 'background'],
    association_type: 'candidate',
    confirmation_status: 'unconfirmed',
    confidence_hint: 'medium',
    source_kind: 'research_project',
    source_path: 'backend/data/research_projects/rp_demo_agent_harness.json',
    source_path_display: 'backend/data/research_projects/rp_demo_agent_harness.json',
    why_candidate: { matched_fields: ['title', 'background'], strong_terms: ['harness'], weak_terms: ['agent'], score_breakdown: { title: 2, background: 1 } },
    risk_note: '只读候选研究项目；P27 不写入项目引用。',
    promotion_supported: true,
    promotion_action: 'create_topic_cluster_link',
    drilldown_route: '/workspace/research?project=rp_demo_agent_harness',
  }
  const noFormalKfcLinks = directLinks.kfc_themes.length === 0 && directLinks.research_projects.length === 0
  return {
    success: true,
    data: {
      cluster_id: cluster.cluster_id,
      cluster_title: cluster.title,
      generated_at: new Date().toISOString(),
      direct_links: directLinks,
      indirect_assets: {
        articles,
        wiki_topics: (aggregated.linked_topic_articles || []).map((group) => ({
          topic_id: group.topic_id,
          title: group.title,
          article_count: group.article_count,
          association_kind: 'indirect_aggregation',
        })),
        representative_articles: clone(aggregated.representative_articles || []),
      },
      candidate_assets: {
        kfc_themes: directLinks.kfc_themes.length ? [] : [candidateTheme],
        concepts: [candidateConcept],
        research_projects: directLinks.research_projects.length ? [] : [candidateProject],
        evidence: [
          {
            ...candidateProject,
            target_type: 'evidence',
            target_id: 'rp_demo_agent_harness:ev_demo_harness',
            target_title: 'Agent Harness evidence',
            source_kind: 'research_project.evidence_items',
            parent_research_project_id: 'rp_demo_agent_harness',
            parent_research_project_title: 'Agent-ready 战略研究',
            risk_note: '证据是项目内线索；P27 不建立正式证据链接。',
          },
        ],
        insights: [
          {
            ...candidateProject,
            target_type: 'insight',
            target_id: 'rp_demo_agent_harness:ic_demo_harness',
            target_title: '执行治理层是长期控制点',
            source_kind: 'research_project.insight_cards',
            parent_research_project_id: 'rp_demo_agent_harness',
            parent_research_project_title: 'Agent-ready 战略研究',
            risk_note: '洞察是项目内线索；P27 不采纳为正式研究结论。',
          },
        ],
        notes: [
          {
            ...candidateConcept,
            target_type: 'note',
            target_id: 'note_demo_agent_harness',
            target_title: 'Agent Harness 定价判断',
            source_kind: 'notes',
            source_path: 'backend/data/notes/note_demo_agent_harness.md',
            risk_note: '笔记是只读线索；P27 不写入正式研究资产。',
          },
        ],
        artifacts: [],
      },
      counts: {
        direct_wiki_topic_count: directLinks.wiki_topics.length,
        direct_kfc_theme_count: directLinks.kfc_themes.length,
        direct_research_project_count: directLinks.research_projects.length,
        indirect_article_count: articles.length,
        candidate_concept_count: 1,
        candidate_theme_count: directLinks.kfc_themes.length ? 0 : 1,
        candidate_research_project_count: directLinks.research_projects.length ? 0 : 1,
        candidate_evidence_count: 1,
        candidate_insight_count: 1,
        candidate_note_count: 1,
        candidate_artifact_count: 0,
      },
      formal_empty_state: {
        kfc_theme: {
          message: '尚未建立正式 KFC 主题链接；候选主题需要人工确认后才会进入正式区。',
          candidate_count: directLinks.kfc_themes.length ? 0 : 1,
          has_formal_links: directLinks.kfc_themes.length > 0,
          suggested_action: '审阅候选主题，并只在人工确认后建立主题簇链接。',
        },
        research_project: {
          message: '尚未建立正式研究项目链接；候选项目不会自动创建或自动关联。',
          candidate_count: directLinks.research_projects.length ? 0 : 1,
          has_formal_links: directLinks.research_projects.length > 0,
          suggested_action: '审阅候选研究项目，并只在人工确认后建立主题簇链接。',
        },
      },
      warnings: noFormalKfcLinks
        ? [
            {
              type: 'no_formal_kfc_asset_links',
              message: '当前主题簇没有正式 KFC 资产链接；以下主题、概念、研究项目仅为只读候选。',
            },
          ]
        : [],
      provenance: {
        direct_links_source: 'demo/topic_cluster_links',
        wiki_articles_source: 'demo/wiki_topics',
        themes_source: 'demo/global_themes',
        concepts_source: 'demo/concept_registry',
        research_projects_source: 'demo/research_projects',
        notes_source: 'demo/notes',
      },
    },
  }
}

function promotionCounts(items) {
  return ['pending', 'materialized_concept', 'linked', 'candidate_created', 'added_to_project_evidence', 'ignored', 'deprecated', 'unlinked']
    .reduce((counts, status) => ({
      ...counts,
      [status]: items.filter((item) => item.review_status === status).length,
    }), {})
}

function basketItem(promotion) {
  const materialSlice = materialSlices.find((item) => item.slice_id === promotion.slice_id) || {}
  return {
    promotion_id: promotion.promotion_id,
    slice_id: promotion.slice_id,
    lead_type: promotion.lead_type,
    title: promotion.title,
    display_title: materialSlice.display_title || promotion.title,
    summary: promotion.summary,
    source_quote: materialSlice.source_quote || '',
    source_excerpt: materialSlice.source_excerpt || '',
    source_context: materialSlice.source_context || '',
    extraction_reason: materialSlice.extraction_reason || '',
    confidence: materialSlice.confidence ?? 0.72,
    recommended_action: materialSlice.recommended_action || '',
    why_this_is_a_concept: materialSlice.why_this_is_a_concept || '',
    risk: clone(materialSlice.risk || []),
    alternative_matches: clone(materialSlice.alternative_matches || []),
    quote_review: clone(promotion.quote_review || {}),
    action_history: clone(promotion.action_history || []),
    source: {
      source_article_id: materialSlice.source_article_id || '',
      source_title: materialSlice.source_title || '',
      source_markdown_path: materialSlice.source_markdown_path || '',
      source_content_hash: materialSlice.source_content_hash || '',
      source_url: materialSlice.source_url || '',
      linked_wiki_topic: materialSlice.linked_wiki_topic || '',
    },
    linked_topic_cluster: promotion.linked_topic_cluster,
    linked_research_project: promotion.linked_research_project || '',
    review_status: promotion.review_status,
    decision: promotion.decision || null,
    target: promotion.target || null,
    candidate: promotion.candidate || null,
    concept: promotion.concept || null,
    materialized_concept: clone(demoConceptRegistryEntries.find((item) => item.concept_id === promotion.concept?.concept_id) || null),
    created_at: promotion.created_at,
    updated_at: promotion.updated_at,
  }
}

export async function getTopicClusterPromotionBasket(clusterId) {
  const cluster = clusters.find((item) => item.cluster_id === clusterId)
  if (!cluster) throw new Error(`Demo data not available for topic cluster "${clusterId}".`)
  const items = leadPromotions
    .filter((item) => item.linked_topic_cluster === clusterId)
    .map(basketItem)
  return {
    success: true,
    data: {
      cluster_id: clusterId,
      counts: promotionCounts(items),
      items,
      provenance: {
        material_slices_source: 'demo/material_slices',
        lead_promotions_source: 'demo/lead_promotions',
        concept_registry_candidates_source: 'demo/concept_registry_candidates',
        mutation: 'sidecar_only',
      },
    },
  }
}

function articleProcessingCardFromPromotion(item) {
  const quoteStatus = item.quote_review?.status || ''
  const riskFlags = [
    ...(item.risk || []),
    ...(quoteStatus ? [`quote:${quoteStatus}`] : []),
  ]
  return {
    candidate_id: item.promotion_id,
    candidate_type: item.lead_type === 'evidence_slice' ? 'evidence_lead' : 'concept_lead',
    title: item.title,
    summary: item.summary,
    status: item.review_status,
    quality_state: quoteStatus || (riskFlags.length ? 'needs_review' : 'normal'),
    recommended_action: item.recommended_action || (item.lead_type === 'evidence_slice' ? 'review_evidence_quote' : 'confirm_or_deposit_concept_lead'),
    alternative_matches: clone(item.alternative_matches || []),
    quote: item.source_quote,
    context: item.source_context || item.source_excerpt || '',
    why: item.why_this_is_a_concept || item.extraction_reason || '',
    confidence: item.confidence,
    risk_flags: riskFlags,
    source: clone(item.source || {}),
    review_trail: clone(item.action_history || []),
    quote_review: clone(item.quote_review || {}),
  }
}

function articleProcessingCardFromRelation(item) {
  return {
    candidate_id: item.relation_candidate_id,
    candidate_type: 'relation_candidate',
    title: `${item.subject_concept} - ${item.relation_type} - ${item.object_concept}`,
    summary: item.why_relation_exists || '',
    status: item.review_status || 'pending_review',
    quality_state: item.review_status === 'needs_revision' ? 'needs_review' : 'normal',
    subject_concept: item.subject_concept,
    relation_type: item.relation_type,
    object_concept: item.object_concept,
    alternative_relation_types: clone(item.possible_alternative_relation_types || []),
    quote: item.source_quote || '',
    context: item.source_context || '',
    why: item.why_relation_exists || '',
    confidence: item.confidence ?? 0.72,
    risk_flags: item.review_status === 'needs_revision' ? ['relation_type_needs_revision'] : [],
    source: {
      source_article_id: item.source_article_id || '',
      source_title: item.source_title || '',
      source_markdown_path: item.source_markdown_path || '',
      source_content_hash: item.source_content_hash || '',
    },
    review_trail: clone(item.action_history || []),
  }
}

export async function getTopicClusterArticleProcessingReview(clusterId, articleId) {
  const basket = await getTopicClusterPromotionBasket(clusterId)
  const promotionCards = basket.data.items
    .filter((item) => item.source?.source_article_id === articleId)
    .map(articleProcessingCardFromPromotion)
  const relationCards = relationCandidates
    .filter((item) => item.linked_topic_cluster === clusterId && item.source_article_id === articleId)
    .map(articleProcessingCardFromRelation)
  const candidateCards = [...promotionCards, ...relationCards]
  const summary = candidateCards.reduce((acc, card) => {
    acc.candidate_count += 1
    if (card.candidate_type === 'concept_lead') acc.concept_leads += 1
    if (card.candidate_type === 'evidence_lead') acc.evidence_leads += 1
    if (card.candidate_type === 'relation_candidate') acc.relation_candidates += 1
    if (card.risk_flags?.length) acc.high_risk += 1
    if (card.quality_state && !['normal', ''].includes(card.quality_state)) acc.low_quality += 1
    if (['pending', 'pending_review', 'needs_revision'].includes(card.status) || card.risk_flags?.length) acc.needs_review += 1
    acc.status_counts[card.status] = (acc.status_counts[card.status] || 0) + 1
    return acc
  }, {
    candidate_count: 0,
    concept_leads: 0,
    evidence_leads: 0,
    relation_candidates: 0,
    needs_review: 0,
    high_risk: 0,
    low_quality: 0,
    status_counts: {},
  })
  return {
    success: true,
    data: {
      cluster_id: clusterId,
      article_id: articleId,
      article_title: candidateCards[0]?.source?.source_title || '',
      summary,
      candidate_cards: candidateCards,
      provenance: {
        material_slices_source: 'demo/material_slices',
        lead_promotions_source: 'demo/lead_promotions',
        relation_candidates_source: 'demo/relation_candidates',
        review_trail_source: 'demo/kfc_changes',
        mutation: 'front_half_review_sidecars',
      },
    },
  }
}

export async function applyArticleProcessingBatchAction(clusterId, articleId, payload = {}) {
  const actionType = payload.action_type || payload.action
  const cardIds = Array.isArray(payload.card_ids) ? payload.card_ids : []
  if (payload.group_id) throw new Error('batch action requires explicit card_ids')
  const batchId = `batch_demo_${Date.now()}`
  const applied = []
  const skipped = []
  const review = await getTopicClusterArticleProcessingReview(clusterId, articleId)
  const cardsById = new Map((review.data.candidate_cards || []).map((card) => [card.card_id || card.candidate_id, card]))
  for (const cardId of cardIds) {
    const card = cardsById.get(cardId)
    if (!card) {
      skipped.push({ card_id: cardId, reason: 'not_found_in_article' })
      continue
    }
    if (!(card.batch_action_types || []).includes(actionType)) {
      skipped.push({ card_id: cardId, reason: 'not_batch_eligible' })
      continue
    }
    if (actionType === 'reject_weak_relations') {
      const result = await applyRelationCandidateAction(clusterId, cardId, {
        action: 'reject',
        relation_type: card.relation_type,
        batch_id: batchId,
        note: payload.note,
      })
      applied.push({ card_id: cardId, candidate_type: card.candidate_type, action_type: actionType, status: result.data.review_status, batch_id: batchId })
      continue
    }
    const promotion = leadPromotions.find((item) => item.promotion_id === cardId && item.linked_topic_cluster === clusterId)
    if (!promotion) {
      skipped.push({ card_id: cardId, reason: 'not_found' })
      continue
    }
    promotion.review_status = actionType === 'confirm_high_confidence_concepts' ? 'confirmed' : 'reviewed'
    promotion.decision = actionType === 'confirm_high_confidence_concepts' ? 'confirm_review' : 'mark_reviewed'
    promotion.action_history = [
      ...(promotion.action_history || []),
      {
        action_id: `act_demo_${Date.now()}_${applied.length}`,
        action: promotion.decision,
        actor: payload.reviewer || 'local',
        batch_id: batchId,
        created_at: new Date().toISOString(),
        note: payload.note || '',
      },
    ]
    applied.push({ card_id: cardId, candidate_type: card.candidate_type, action_type: actionType, status: promotion.review_status, batch_id: batchId })
  }
  return {
    success: true,
    data: {
      cluster_id: clusterId,
      article_id: articleId,
      batch_id: batchId,
      action_type: actionType,
      applied,
      skipped,
      summary: { requested: cardIds.length, applied: applied.length, skipped: skipped.length },
    },
  }
}

export async function getTopicClusterPromotionChanges(clusterId) {
  const items = leadPromotions
    .filter((item) => item.linked_topic_cluster === clusterId && item.decision)
    .map((item) => ({
      change_id: `chg_${item.promotion_id}`,
      action: item.decision,
      actor: 'human',
      timestamp: item.updated_at,
      cluster_id: clusterId,
      source_ids: { source_lead_id: item.promotion_id, source_material_slice_id: item.slice_id },
      after: { target: item.target || null, concept: item.concept || null },
      reason: item.action_history?.at?.(-1)?.note || '',
    }))
  return { success: true, data: { cluster_id: clusterId, items, total: items.length } }
}

export async function createTopicClusterMaterialSlice(clusterId, payload) {
  const cluster = clusters.find((item) => item.cluster_id === clusterId)
  if (!cluster) throw new Error(`Demo data not available for topic cluster "${clusterId}".`)
  const now = new Date().toISOString()
  const materialSlice = {
    slice_id: nextId('ms'),
    slice_type: payload.slice_type,
    title: payload.title,
    display_title: payload.display_title || payload.title,
    summary: payload.summary || '',
    source_quote: payload.source_quote || '',
    source_excerpt: payload.source_excerpt || '',
    source_context: payload.source_context || payload.source_quote || '',
    source_span: payload.source_span || {},
    source_article_id: payload.source_article_id || '',
    source_markdown_path: payload.source_markdown_path || '',
    source_content_hash: payload.source_content_hash || '',
    source_title: payload.source_title || '',
    source_url: payload.source_url || '',
    linked_topic_cluster: clusterId,
    linked_wiki_topic: payload.linked_wiki_topic || '',
    linked_research_project: payload.linked_research_project || '',
    extraction_reason: payload.extraction_reason || '来自 Wiki 粗加工的概念/证据线索。',
    confidence: payload.confidence ?? 0.72,
    recommended_action: payload.recommended_action || '',
    why_this_is_a_concept: payload.why_this_is_a_concept || '',
    risk: clone(payload.risk || []),
    alternative_matches: clone(payload.alternative_matches || []),
    created_from: payload.created_from || 'topic_cluster_detail',
    created_by: 'human',
    review_status: 'promoted',
    created_at: now,
    updated_at: now,
  }
  const promotion = {
    promotion_id: nextId('lp'),
    slice_id: materialSlice.slice_id,
    lead_type: materialSlice.slice_type,
    title: materialSlice.title,
    summary: materialSlice.summary,
    linked_topic_cluster: clusterId,
    linked_research_project: materialSlice.linked_research_project,
    review_status: 'pending',
    decision: null,
    target: null,
    candidate: null,
    action_history: [],
    created_from: 'material_slice',
    created_by: 'human',
    created_at: now,
    updated_at: now,
  }
  materialSlices.unshift(materialSlice)
  leadPromotions.unshift(promotion)
  return { success: true, data: { slice: clone(materialSlice), promotion: clone(promotion) } }
}

export async function applyLeadPromotionAction(clusterId, promotionId, payload) {
  const promotion = leadPromotions.find((item) => item.promotion_id === promotionId && item.linked_topic_cluster === clusterId)
  if (!promotion) throw new Error(`Demo data not available for lead promotion "${promotionId}".`)
  const now = new Date().toISOString()
  const historyItem = {
    action: payload.action,
    actor: 'human',
    created_at: now,
    note: payload.note || payload.reason || '',
  }
  if (payload.action === 'link_existing_registry_entry' || payload.action === 'switch_registry_match') {
    promotion.review_status = 'linked'
    promotion.decision = payload.action
    promotion.target = {
      target_type: 'concept_registry_entry',
      target_id: payload.target?.registry_entry_id || payload.target?.target_id || '',
      target_label: payload.target?.registry_entry_label || payload.target?.target_label || '',
    }
  } else if (payload.action === 'deposit_as_new_concept') {
    const concept = {
      concept_id: nextId('canon'),
      entry_id: '',
      canonical_name: payload.concept?.label || promotion.title,
      label: payload.concept?.label || promotion.title,
      asset_type: 'concept',
      lifecycle_status: 'active',
      quality_state: 'machine_generated',
      review_state: 'unreviewed',
      confidence: 0.72,
      source_lead_id: promotionId,
      source_material_slice_id: promotion.slice_id,
      linked_topic_cluster_ids: [clusterId],
      linked_research_project_ids: promotion.linked_research_project ? [promotion.linked_research_project] : [],
      created_at: now,
      updated_at: now,
    }
    concept.entry_id = concept.concept_id
    demoConceptRegistryEntries.unshift(concept)
    promotion.review_status = 'materialized_concept'
    promotion.decision = payload.action
    promotion.target = {
      target_type: 'concept_registry_entry',
      target_id: concept.concept_id,
      target_label: concept.label,
    }
    promotion.concept = { concept_id: concept.concept_id, asset_type: 'concept' }
  } else if (payload.action === 'create_new_registry_candidate') {
    const candidate = {
      candidate_id: nextId('crc'),
      candidate_type: 'concept',
      label: payload.candidate?.label || promotion.title,
      source_promotion_id: promotionId,
      source_slice_id: promotion.slice_id,
      linked_topic_cluster: clusterId,
      review_status: 'proposed',
      created_at: now,
      updated_at: now,
    }
    conceptRegistryCandidates.unshift(candidate)
    promotion.review_status = 'candidate_created'
    promotion.decision = payload.action
    promotion.candidate = { candidate_id: candidate.candidate_id, candidate_type: 'concept_registry_candidate' }
  } else if (payload.action === 'add_as_project_evidence') {
    promotion.review_status = 'added_to_project_evidence'
    promotion.decision = payload.action
    promotion.target = {
      target_type: 'research_project',
      target_id: payload.target?.research_project_id || payload.target?.target_id || '',
      evidence_item_id: nextId('ev'),
    }
  } else if (payload.action === 'ignore') {
    promotion.review_status = 'ignored'
    promotion.decision = payload.action
    promotion.target = null
  } else if (payload.action === 'deprecate_materialized_concept') {
    promotion.review_status = 'deprecated'
    promotion.decision = payload.action
  } else if (payload.action === 'unlink_promotion_target') {
    promotion.review_status = 'unlinked'
    promotion.decision = payload.action
  } else if (payload.action === 'review_quote' || payload.action === 'replace_quote') {
    promotion.decision = payload.action
    promotion.quote_review = {
      status: payload.action === 'replace_quote' ? (payload.replacement_quote ? 'replaced' : 'replace_requested') : payload.quote_status,
      note: payload.note || payload.reason || '',
      replacement_quote: payload.replacement_quote || '',
      replacement_context: payload.replacement_context || '',
      actor: 'human',
      updated_at: now,
    }
    historyItem.quote_status = promotion.quote_review.status
  }
  promotion.action_history = [...(promotion.action_history || []), historyItem]
  promotion.updated_at = now
  return { success: true, data: clone(promotion) }
}

export async function createTopicClusterRelationCandidate(clusterId, payload) {
  const now = new Date().toISOString()
  const candidate = {
    relation_candidate_id: payload.relation_candidate_id || nextId('relcand'),
    candidate_type: 'relation_candidate',
    linked_topic_cluster: clusterId,
    source_article_id: payload.source_article_id || '',
    source_title: payload.source_title || '',
    source_markdown_path: payload.source_markdown_path || '',
    source_content_hash: payload.source_content_hash || '',
    source_quote: payload.source_quote || '',
    source_context: payload.source_context || '',
    subject_concept: payload.subject_concept || '',
    relation_type: payload.relation_type || 'related_to',
    object_concept: payload.object_concept || '',
    why_relation_exists: payload.why_relation_exists || '',
    confidence: payload.confidence ?? 0.72,
    possible_alternative_relation_types: clone(payload.possible_alternative_relation_types || []),
    review_status: 'pending_review',
    action_history: [],
    created_at: now,
    updated_at: now,
  }
  relationCandidates.unshift(candidate)
  return { success: true, data: clone(candidate) }
}

export async function applyRelationCandidateAction(clusterId, relationCandidateId, payload) {
  const candidate = relationCandidates.find((item) => item.linked_topic_cluster === clusterId && item.relation_candidate_id === relationCandidateId)
  if (!candidate) throw new Error(`Demo data not available for relation candidate "${relationCandidateId}".`)
  const now = new Date().toISOString()
  const relationTypeBefore = candidate.relation_type
  candidate.relation_type = payload.relation_type || candidate.relation_type
  candidate.review_status = payload.action === 'confirm' ? 'confirmed' : payload.action === 'reject' ? 'rejected' : 'needs_revision'
  candidate.action_history = [
    ...(candidate.action_history || []),
    {
      action: payload.action,
      actor: 'human',
      created_at: now,
      relation_type_before: relationTypeBefore,
      relation_type_after: candidate.relation_type,
      note: payload.note || payload.reason || '',
    },
  ]
  candidate.updated_at = now
  return { success: true, data: clone(candidate) }
}

export async function getLeadPromotionTrace(clusterId, promotionId) {
  const promotion = leadPromotions.find((item) => item.promotion_id === promotionId && item.linked_topic_cluster === clusterId)
  if (!promotion) throw new Error(`Demo data not available for lead promotion "${promotionId}".`)
  const materialSlice = materialSlices.find((item) => item.slice_id === promotion.slice_id) || null
  return {
    success: true,
    data: {
      promotion: clone(promotion),
      slice: clone(materialSlice),
      registry_candidate: clone(conceptRegistryCandidates.find((item) => item.candidate_id === promotion.candidate?.candidate_id) || null),
      trace: {
        article_id: materialSlice?.source_article_id || '',
        slice_id: promotion.slice_id,
        promotion_id: promotionId,
        target_type: promotion.target?.target_type || '',
        target_id: promotion.target?.target_id || '',
      },
    },
  }
}

export async function updateTopicCluster(clusterId, payload) {
  const cluster = clusters.find((item) => item.cluster_id === clusterId)
  if (!cluster) throw new Error(`Demo data not available for topic cluster "${clusterId}".`)
  Object.assign(cluster, payload, { updated_at: new Date().toISOString() })
  return { success: true, data: { cluster: { ...clone(cluster), counts: countsFor(clusterId) }, warnings: [] } }
}

export async function getTopicClusterLinks(clusterId) {
  return {
    success: true,
    data: {
      items: links.filter((link) => link.cluster_id === clusterId && !link.deleted).map((link) => clone(link)),
      warnings: [],
    },
  }
}

export async function createTopicClusterLink(clusterId, payload) {
  const cluster = clusters.find((item) => item.cluster_id === clusterId)
  if (!cluster) throw new Error(`Demo data not available for topic cluster "${clusterId}".`)
  const now = new Date().toISOString()
  const link = {
    link_id: payload.link_id || nextId('tcl'),
    cluster_id: clusterId,
    target_type: payload.target_type,
    target_id: payload.target_id,
    target_title: payload.target_title || payload.target_id,
    role: payload.role || 'candidate',
    status: payload.status || 'candidate',
    confidence: payload.confidence ?? null,
    rationale: payload.rationale || '',
    review_decision: payload.review_decision || null,
    created_at: now,
    updated_at: now,
  }
  links.push(link)
  return {
    success: true,
    data: {
      link: clone(link),
      warnings: [
        {
          code: 'target_unresolved',
          message: 'Target existence is not required in Phase 1; link was saved as a manual reference.',
        },
      ],
    },
  }
}

export async function updateTopicClusterLink(linkId, payload) {
  const link = links.find((item) => item.link_id === linkId)
  if (!link) throw new Error(`Demo data not available for topic cluster link "${linkId}".`)
  Object.assign(link, payload, { updated_at: new Date().toISOString() })
  return { success: true, data: { link: clone(link), warnings: [] } }
}

export async function deleteTopicClusterLink(linkId) {
  const link = links.find((item) => item.link_id === linkId)
  if (!link) throw new Error(`Demo data not available for topic cluster link "${linkId}".`)
  link.deleted = true
  link.deleted_at = new Date().toISOString()
  return { success: true, data: { link_id: linkId, deleted: true } }
}

export async function createTopicClusterRefreshRequest(payload) {
  const now = new Date().toISOString()
  const request = {
    request_id: nextId('tcr'),
    type: 'topic_cluster_recluster',
    object_type: 'topic_cluster_refresh_request',
    schema_version: 1,
    scope: payload.scope || 'all',
    status: 'requested',
    created_by: 'human',
    created_at: now,
    updated_at: now,
    inputs: {
      include_wiki_topics: payload.inputs?.include_wiki_topics ?? true,
      include_kfc_themes: payload.inputs?.include_kfc_themes ?? true,
      include_kfc_concepts: payload.inputs?.include_kfc_concepts ?? false,
      include_research_projects: payload.inputs?.include_research_projects ?? false,
    },
    rules: {
      do_not_auto_apply: true,
      proposal_only: true,
      preserve_human_accepted_links: true,
      human_review_required: true,
      kfc_must_not_execute_model: true,
      kfc_must_not_start_external_process: true,
      kfc_must_not_auto_create_research_project: true,
    },
  }
  refreshRequests.unshift(request)
  return { success: true, data: clone(request) }
}

export async function listTopicClusterRefreshRequests() {
  return { success: true, data: { items: clone(refreshRequests), total: refreshRequests.length, warnings: [] } }
}

export async function getTopicClusterRefreshRequest(requestId) {
  const request = refreshRequests.find((item) => item.request_id === requestId)
  if (!request) throw new Error(`Demo data not available for topic cluster refresh request "${requestId}".`)
  return { success: true, data: clone(request) }
}

export async function listTopicClusterProposals() {
  const items = proposals.map((proposal) => {
    const supported = proposal.actions.filter((action) => ['create_cluster', 'add_link'].includes(action.action_type))
    return {
      proposal_id: proposal.proposal_id,
      request_id: proposal.request_id,
      status: proposal.status,
      created_at: proposal.created_at,
      summary: clone(proposal.summary),
      action_count: proposal.actions.length,
      supported_action_count: supported.length,
      unsupported_action_count: proposal.actions.length - supported.length,
      warning_count: proposal.warnings.length,
      latest_application: proposalApplications.find((item) => item.proposal_id === proposal.proposal_id) || null,
    }
  })
  return { success: true, data: { items, total: items.length, warnings: [] } }
}

export async function getTopicClusterProposal(proposalId) {
  const proposal = proposals.find((item) => item.proposal_id === proposalId)
  if (!proposal) throw new Error(`Demo data not available for topic cluster proposal "${proposalId}".`)
  return {
    success: true,
    data: {
      proposal: clone(proposal),
      applications: clone(proposalApplications.filter((item) => item.proposal_id === proposalId)),
    },
  }
}

export async function applyTopicClusterProposal(proposalId, payload) {
  const application = {
    application_id: nextId('tcpa'),
    proposal_id: proposalId,
    applied_at: new Date().toISOString(),
    accepted_actions: payload.accepted_actions || [],
    rejected_actions: payload.rejected_actions || [],
    created_cluster_ids: payload.accepted_actions?.filter((id) => id.startsWith('create_cluster:')).map((id) => id.split(':')[1]) || [],
    created_link_ids: payload.accepted_actions?.filter((id) => id.startsWith('add_link:')).map((id) => id.split(':')[1]) || [],
    skipped_existing_cluster_ids: [],
    skipped_existing_link_ids: [],
  }
  proposalApplications.unshift(application)
  return { success: true, data: clone(application) }
}

export async function findTopicClustersByTarget(targetType, targetId) {
  const items = links
    .filter((link) => link.target_type === targetType && link.target_id === targetId && !link.deleted)
    .map((link) => ({
      cluster: {
        ...clone(clusters.find((cluster) => cluster.cluster_id === link.cluster_id)),
        counts: countsFor(link.cluster_id),
      },
      link: clone(link),
    }))
  return { success: true, data: { items, total: items.length, warnings: [] } }
}
