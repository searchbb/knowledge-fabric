const demoCandidates = [
  {
    candidate_id: 'src_demo_agent_harness',
    source_id: 'src_demo_agent_harness',
    title: 'Agent Harness 工作流笔记',
    source_file_path: '/Users/mac/Downloads/OB笔记/Clippings/agent-harness.md',
    source_relative_path: 'agent-harness.md',
    content_hash: 'sha256:demo',
    status: 'pending',
    excerpt: '从 Clippings 进入 Wiki Intake 的示例素材。',
    source_type: 'local_markdown',
    duplicate_status: 'none',
    char_count: 820,
    line_count: 24,
    guessed_topics: [{ topic_id: 'agent-harness', score: 3 }],
    has_processing_result: false,
    has_digest: false,
    needs_human_review: false,
  },
  {
    candidate_id: 'src_demo_token_economy',
    source_id: 'src_demo_token_economy',
    title: 'Token Economy（词元经济）产业链全景报告',
    source_file_path: '/Users/mac/Downloads/OB笔记/Clippings/token-economy.md',
    source_relative_path: 'token-economy.md',
    content_hash: 'sha256:demo-token',
    status: 'completed',
    excerpt: 'Token 计量、模型服务成本和稳定币支付的示例素材。',
    source_type: 'wechat_article',
    source_url: 'https://example.com/token-economy',
    duplicate_status: 'none',
    char_count: 2200,
    line_count: 80,
    guessed_topics: [{ topic_id: 'ai-tokenization', score: 4 }],
    has_processing_result: true,
    has_digest: true,
    needs_human_review: false,
    auto_processed: {
      topic_id: 'ai-tokenization',
      processed_at: '2026-05-13T11:21:15+08:00',
      compile_run_id: 'compile_demo_token',
      raw_article_path: '/tmp/wiki_hub/topics/ai-tokenization/raw/articles/token-economy.md',
      verified_digest_md_path: '/tmp/wiki_hub/topics/ai-tokenization/digests/verified_digest/token-economy.md',
      sources_path: '/tmp/wiki_hub/topics/ai-tokenization/digests/claim_ledger/token-economy.sources.json',
    },
  },
]

const demoTopic = {
  topic_id: 'ai-tokenization',
  title: 'AI 分词与计费成本',
  display_name: 'AI 分词与计费成本',
  article_count: 1,
  completed_count: 1,
  needs_review_count: 0,
  last_processed_at: '2026-05-13T11:21:15+08:00',
  top_concepts: ['token economy', 'tokenization', '中文税', 'API pricing', 'stablecoin payment'],
  topic_keywords: ['token', 'pricing', 'inference cost'],
  cluster_ids: ['tc_demo_token_economy'],
  cluster_links: [{ cluster_id: 'tc_demo_token_economy', title: 'AI算力与Token经济', role: 'primary', status: 'accepted' }],
  cluster_coverage_status: 'linked',
  cluster_coverage: {
    topic_id: 'ai-tokenization',
    status: 'linked',
    linked_clusters: [{ cluster_id: 'tc_demo_token_economy', title: 'AI算力与Token经济', role: 'primary', status: 'accepted' }],
    candidate_clusters: [],
    candidate_count: 0,
    recommendation: '已正式关联到主题簇。',
    reason: '该主题已经有至少一个已接受的主题簇链接。',
    allowed_actions: { link_existing_cluster: true, request_new_cluster: false, mark_watch: false, mark_ignored: false, mark_needs_cluster: false },
  },
}

const demoCandidateTopic = {
  topic_id: 'cloud-data-ai-platform',
  title: 'Cloud Data and AI Platform',
  display_name: 'Cloud Data and AI Platform',
  article_count: 1,
  completed_count: 1,
  needs_review_count: 0,
  last_processed_at: '2026-05-14T10:25:52+08:00',
  top_concepts: ['cloud data', 'AI platform', 'serverless spark'],
  topic_keywords: ['cloud', 'data', 'ai', 'platform'],
  cluster_ids: [],
  cluster_links: [],
  representative_articles: [{ title: '阿里云智能大数据演进' }],
  cluster_coverage_status: 'candidate',
  cluster_coverage: {
    topic_id: 'cloud-data-ai-platform',
    status: 'candidate',
    linked_clusters: [],
    candidate_clusters: [
      {
        cluster_id: 'tc_demo_agent_ready',
        title: 'Agent-ready 企业软件栈',
        confidence: 0.66,
        confidence_label: 'medium',
        matched_terms: ['ai', 'platform'],
        reason: 'Matched topic/cluster terms: ai, platform',
        source: 'deterministic_metadata_match',
      },
    ],
    candidate_count: 1,
    recommendation: '存在候选 Cluster，等待人工确认。',
    reason: 'Matched candidate Cluster terms: ai, platform',
    allowed_actions: { link_existing_cluster: true, request_new_cluster: true, mark_watch: true, mark_ignored: true, mark_needs_cluster: true },
  },
}

const demoArticles = [
  {
    candidate_id: 'src_demo_token_economy',
    intake_item_id: 'src_demo_token_economy',
    source_id: 'src_demo_token_economy',
    topic_id: 'ai-tokenization',
    title: 'Token Economy（词元经济）产业链全景报告',
    source_url: 'https://example.com/token-economy',
    source_type: 'wechat_article',
    status: 'completed',
    processed_at: '2026-05-13T11:21:15+08:00',
    digest_summary: '该材料聚焦 Token Economy、模型计费和稳定币支付对 AI 服务商业化的影响。',
    top_concepts: ['token economy', 'stablecoin payment', 'AI pricing'],
    markdown_path: '/Users/mac/Downloads/OB笔记/Clippings/token-economy.md',
    raw_article_path: '/tmp/wiki_hub/topics/ai-tokenization/raw/articles/token-economy.md',
    verified_digest_md_path: '/tmp/wiki_hub/topics/ai-tokenization/digests/verified_digest/token-economy.md',
  },
]

demoTopic.representative_articles = demoArticles

export async function listWikiIntakeCandidates() {
  return {
    data: {
      items: demoCandidates,
      total: demoCandidates.length,
      stats: { total: 2, pending: 1, accepted: 0, deferred: 0, rejected: 0, duplicate: 0, needs_human_review: 0, completed: 1, by_status: { pending: 1, completed: 1 } },
      clippings_root: '/Users/mac/Downloads/OB笔记/Clippings',
      source_manifest: 'demo',
    },
  }
}

export async function listWikiTopics(options = {}) {
  const topics = [demoTopic, demoCandidateTopic]
  if (options.includeCoverage) {
    return {
      data: {
        topics,
        items: topics,
        total: topics.length,
        coverage_counts: { linked: 1, candidate: 1, needs_cluster: 0, watch: 0, ignored: 0 },
      },
    }
  }
  return { data: topics }
}

export async function getWikiTopicArticles(topicId) {
  if (topicId === demoCandidateTopic.topic_id) {
    return {
      data: {
        topic: demoCandidateTopic,
        articles: [
          {
            candidate_id: 'src_demo_cloud_data',
            source_id: 'src_demo_cloud_data',
            topic_id: demoCandidateTopic.topic_id,
            title: '阿里云智能大数据演进',
            source_type: 'wechat_article',
            status: 'completed',
            processed_at: '2026-05-14T10:25:52+08:00',
            digest_summary: '云上数据平台、统一元数据和 AI 工作负载的演进示例。',
            top_concepts: ['cloud data', 'serverless spark', 'AI platform'],
          },
        ],
      },
    }
  }
  if (topicId !== demoTopic.topic_id) {
    return { data: { topic: { topic_id: topicId, title: topicId, article_count: 0, cluster_links: [] }, articles: [] } }
  }
  return { data: { topic: demoTopic, articles: demoArticles } }
}

export async function getWikiTopicClusterCoverage(topicId) {
  const topic = [demoTopic, demoCandidateTopic].find((item) => item.topic_id === topicId)
  return { data: topic?.cluster_coverage || { topic_id: topicId, status: 'watch', candidate_clusters: [], linked_clusters: [], candidate_count: 0 } }
}

export async function setWikiTopicClusterCoverageOverride(topicId, payload) {
  const topic = [demoTopic, demoCandidateTopic].find((item) => item.topic_id === topicId) || demoCandidateTopic
  topic.cluster_coverage_status = payload.status
  topic.cluster_coverage = { ...topic.cluster_coverage, status: payload.status, manual_override: { ...payload, topic_id: topicId } }
  return { data: { override: topic.cluster_coverage.manual_override, coverage: topic.cluster_coverage } }
}

export async function linkWikiTopicToCluster(topicId, payload) {
  const topic = [demoTopic, demoCandidateTopic].find((item) => item.topic_id === topicId) || demoCandidateTopic
  const link = {
    link_id: `tcl_demo_${topicId}_${payload.cluster_id}`,
    cluster_id: payload.cluster_id,
    title: payload.cluster_title || payload.cluster_id,
    status: 'accepted',
    role: 'primary',
  }
  topic.cluster_ids = [payload.cluster_id]
  topic.cluster_links = [link]
  topic.cluster_coverage_status = 'linked'
  topic.cluster_coverage = { ...topic.cluster_coverage, status: 'linked', linked_clusters: [link], candidate_clusters: [] }
  return { data: { link, coverage: topic.cluster_coverage, created: true } }
}

export async function requestWikiTopicClusterProposal(topicId, payload = {}) {
  return {
    data: {
      request: {
        request_id: 'tcr_demo_topic_proposal',
        scope: 'wiki_topic',
        topic_id: topicId,
        suggested_title: payload.suggested_title || topicId,
        status: 'requested',
        rules: { proposal_only: true, do_not_auto_apply: true },
      },
      coverage: (await getWikiTopicClusterCoverage(topicId)).data,
    },
  }
}

export async function getWikiIntakeCandidate(candidateId) {
  const candidate = demoCandidates.find((item) => item.candidate_id === candidateId) || demoCandidates[0]
  const topic = [demoTopic, demoCandidateTopic].find((item) => item.topic_id === candidate.auto_processed?.topic_id) || demoTopic
  return {
    data: {
      candidate,
      content: '# Agent Harness 工作流笔记\n\n从 Clippings 进入 Wiki Intake 的示例素材。',
      topic_context: candidate.status === 'completed'
        ? {
            topic_id: topic.topic_id,
            title: topic.title,
            article_count: topic.article_count,
            completed_count: topic.completed_count,
            needs_review_count: 0,
            cluster_ids: topic.cluster_ids,
            cluster_links: topic.cluster_links,
            recent_same_topic_articles: topic.representative_articles || demoArticles,
          }
        : null,
    },
  }
}

export async function getWikiIntakeProcessedResult(candidateId) {
  const candidate = demoCandidates.find((item) => item.candidate_id === candidateId) || demoCandidates[0]
  const autoProcessed = candidate.auto_processed || null
  if (!autoProcessed) {
    return {
      data: {
        status: 'missing',
        auto_processed: null,
        verified_digest: { json: null, md: '' },
        claim_ledger: [],
        sources: null,
        raw_article_preview: '',
      },
    }
  }
  return {
    data: {
      status: 'complete',
      auto_processed: autoProcessed,
      verified_digest: {
        json: {
          routing_decision: {
            route_mode: 'recommended_topic',
            resolved_topic_id: autoProcessed.topic_id,
            resolved_topic_label: 'AI 分词与计费成本',
            original_confidence: 'high',
            original_confidence_score: 0.86,
          },
          source_summary: '该材料聚焦 Token Economy、模型计费和稳定币支付对 AI 服务商业化的影响。',
          verified_summary: '建议将该文作为 AI 分词与计费成本主题下的 source-only 案例材料，播放量、交易规模和未来趋势保留归因表述。',
          safe_wiki_wording: '据原文和公开转载页，该材料可用于记录 Token 计量、MaaS 定价和支付链路的行业讨论，不应写成已经验证的市场定论。',
          core_concepts: ['token economy', 'stablecoin payment', 'AI pricing'],
          research_gaps: [{ claim: 'MaaS 市场规模和增速', reason: '需要正式行业报告或监管统计交叉核验。' }],
        },
        md: '# 预消化摘要\n\nToken Economy 示例材料。',
      },
      claim_ledger: [
        {
          claim_id: 'c001',
          claim_text: 'Token 计量会影响 MaaS 商业化成本结构。',
          verification_status: 'verified',
          safe_wiki_wording: '可以归因表述为：原文认为 Token 计量正在影响 MaaS 成本结构。',
          supporting_urls: ['https://example.com/token-economy'],
        },
        {
          claim_id: 'c002',
          claim_text: '稳定币支付会成为 AI 服务的默认结算方式。',
          verification_status: 'uncertain',
          verification_notes: '趋势判断，缺少独立证据。',
        },
      ],
      sources: { schema_version: 'verification_sources_v1', sources: [{ title: 'Token Economy 示例材料', url: 'https://example.com/token-economy' }] },
      raw_article_preview: '# Token Economy\n\n示例正文。',
    },
  }
}

export async function changeWikiIntakeCandidatePrimaryTopic(candidateId, payload) {
  const candidate = demoCandidates.find((item) => item.candidate_id === candidateId) || demoCandidates[1]
  candidate.auto_processed = {
    ...(candidate.auto_processed || {}),
    topic_id: payload.topic_id,
    association_status: 'active',
    association_source: 'manual_correction',
  }
  candidate.status = 'completed'
  return { data: { association: candidate.auto_processed, detail: (await getWikiIntakeCandidate(candidateId)).data } }
}

export async function unlinkWikiIntakeCandidatePrimaryTopic(candidateId, payload = {}) {
  const candidate = demoCandidates.find((item) => item.candidate_id === candidateId) || demoCandidates[1]
  candidate.auto_processed = {
    ...(candidate.auto_processed || {}),
    topic_id: '',
    association_status: 'unlinked',
    correction_reason: payload.reason || '',
  }
  candidate.status = 'needs_human_review'
  return { data: { association: candidate.auto_processed, detail: (await getWikiIntakeCandidate(candidateId)).data } }
}

export async function scanWikiIntake() {
  return { data: { markdown_count: demoCandidates.length, duplicate_count: 0, manifest_path: 'demo' } }
}

export async function processNextWikiIntake() {
  return {
    data: {
      ok: true,
      adapter: 'demo',
      result: { status: 'completed' },
      enqueue: { created_count: 1 },
    },
  }
}

export async function createWikiIntakeDecision(payload) {
  return { data: { ...payload, decided_at: '2026-05-12T10:00:00+08:00' } }
}

export async function getWikiIntakeConfig() {
  return {
    data: {
      clippings_root: '/Users/mac/Downloads/OB笔记/Clippings',
      data_root: 'demo',
      clippings_readonly: true,
      runner_enabled: true,
      default_adapter: 'chatgpt_app_attachment',
    },
  }
}
