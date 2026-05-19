import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/')
})

const candidate = {
  candidate_id: 'src_agent_harness',
  title: 'Agent Harness',
  source_type: 'markdown',
  source_file_path: '/Users/mac/Downloads/OB笔记/Clippings/agent-harness.md',
  source_relative_path: 'agent-harness.md',
  content_hash: 'hash_123',
  duplicate_status: 'none',
  guessed_topics: [{ topic_id: 'agent-harness' }],
  status: 'pending',
  size_bytes: 2048,
  excerpt: '正文 agent harness codex',
}

const completedCandidate = {
  ...candidate,
  status: 'completed',
  auto_processed: {
    processed_at: '2026-05-12T11:53:36+08:00',
    topic_id: 'agent-harness',
    compile_run_id: 'compile_test',
    raw_article_path: '/tmp/kfc-wiki-hub/topics/agent-harness/raw/articles/agent-harness.md',
    verified_digest_json_path: '/tmp/kfc-wiki-hub/topics/agent-harness/digests/verified_digest/agent-harness.json',
    verified_digest_md_path: '/tmp/kfc-wiki-hub/topics/agent-harness/digests/verified_digest/agent-harness.md',
    claim_ledger_path: '/tmp/kfc-wiki-hub/topics/agent-harness/digests/claim_ledger/agent-harness.jsonl',
    sources_path: '/tmp/kfc-wiki-hub/topics/agent-harness/digests/claim_ledger/agent-harness.sources.json',
    backfilled_from: '/tmp/kfc-wiki-intake/auto_processed_manifest.jsonl',
  },
}

const api = vi.hoisted(() => ({
  listWikiIntakeCandidates: vi.fn(),
  getWikiIntakeCandidate: vi.fn(),
  getWikiIntakeConfig: vi.fn(),
  listWikiTopics: vi.fn(),
  getWikiIntakeProcessedResult: vi.fn(),
  changeWikiIntakeCandidatePrimaryTopic: vi.fn(),
  unlinkWikiIntakeCandidatePrimaryTopic: vi.fn(),
  scanWikiIntake: vi.fn(),
  processNextWikiIntake: vi.fn(),
  createWikiIntakeDecision: vi.fn(),
  getOverview: vi.fn(),
}))

vi.mock('../../data/dataClient', () => ({
  ...api,
}))

import WikiIntakePage from '../WikiIntakePage.vue'

describe('WikiIntakePage', () => {
  function resetMocks(candidateOverride = candidate) {
    const items = Array.isArray(candidateOverride) ? candidateOverride : [candidateOverride]
    const detailById = new Map(items.map((item) => [item.candidate_id, item]))
    api.getWikiIntakeConfig.mockResolvedValue({
      data: { clippings_root: '/Users/mac/Downloads/OB笔记/Clippings', default_adapter: 'chatgpt_app_attachment' },
    })
    api.listWikiIntakeCandidates.mockResolvedValue({
      data: {
        items,
        stats: {
          total: items.length,
          pending: items.filter((item) => item.status === 'pending').length,
        },
      },
    })
    api.listWikiTopics.mockResolvedValue({
      data: [
        { topic_id: 'agent-harness', title: 'Agent Harness' },
        { topic_id: 'cloud-data-ai-platform', title: 'Cloud Data and AI Platform' },
      ],
    })
    api.getWikiIntakeCandidate.mockImplementation((candidateId) => {
      const selected = detailById.get(candidateId) || items[0]
      return Promise.resolve({
        data: {
          candidate: selected,
          content: `# ${selected.title}\n\n正文 ${selected.title}`,
          topic_context: selected.topic_context || null,
        },
      })
    })
    api.getWikiIntakeProcessedResult.mockImplementation((candidateId) => {
      const selected = detailById.get(candidateId) || items[0]
      if (selected.processed_result) return Promise.resolve({ data: selected.processed_result })
      return Promise.resolve({
        data: {
          status: 'complete',
          auto_processed: selected.auto_processed || null,
          verified_digest: {
            json: {
              routing_decision: {
                route_mode: selected.auto_processed?.route_mode || 'recommended_topic',
                resolved_topic_id: selected.auto_processed?.topic_id || 'agent-harness',
                resolved_topic_label: 'Agent Harness',
                original_confidence: 'high',
                original_confidence_score: 0.87,
                reason_codes: ['matched_existing_topic'],
              },
              source_digest: {
                one_sentence_summary: 'Harness digest summary',
                main_claim: 'Agent Harness 决定 agent 工作流上限。',
                key_points: ['编排工具调用', '沉淀审计链路', '支持人工复核'],
                core_concepts: [
                  {
                    concept: 'Agent 经济',
                    summary: '以能执行任务、接管流程或生成专用软件的 AI Agent 为核心的新商业组织方式。',
                    kfc_action_hint: 'review_for_kfc',
                  },
                  {
                    concept: 'SaaS 流程封装护城河',
                    summary: '传统 SaaS 通过固化企业流程形成粘性，文章认为 Agent 会削弱这种优势。',
                    kfc_action_hint: 'keep_as_article_clue',
                  },
                ],
                mechanism_summary: '通过统一运行时协调模型、工具和状态。',
                author_position: '作者倾向把 Harness 视为关键控制点。',
              },
              safe_wiki: {
                safe_summary: '建议作为 Agent Harness 主题下的 source-only 案例收录。',
                do_not_state_as_fact: ['不要写成所有 AI 编程上限都由 Harness 单独决定。'],
                follow_up_questions: ['补充一手产品文档。'],
              },
            },
            md: '# 预消化摘要\n\nHarness digest summary',
          },
          claim_ledger: [
            {
              claim_id: 'c001',
              claim_text: 'Agent Harness 决定 agent 工作流上限。',
              verification_status: 'verified',
              safe_wiki_wording: '可归因表述为文章观点。',
              supporting_urls: ['https://example.com/agent'],
            },
          ],
          sources: { schema_version: 'verification_sources_v1', sources: [{ title: 'Agent Harness', url: 'https://example.com/agent' }] },
          raw_article_preview: '# Agent Harness',
        },
      })
    })
    api.scanWikiIntake.mockResolvedValue({
      data: { markdown_count: 80, duplicate_count: 5 },
    })
    api.processNextWikiIntake.mockResolvedValue({
      data: { adapter: 'chatgpt_app_attachment', result: { status: 'completed' } },
    })
    api.createWikiIntakeDecision.mockResolvedValue({
      data: { candidate_id: candidate.candidate_id, decision_status: 'accepted' },
    })
    api.changeWikiIntakeCandidatePrimaryTopic.mockImplementation((candidateId, payload) => {
      const selected = { ...(detailById.get(candidateId) || items[0]) }
      selected.auto_processed = { ...(selected.auto_processed || {}), topic_id: payload.topic_id }
      selected.status = 'completed'
      return Promise.resolve({
        data: {
          association: selected.auto_processed,
          detail: {
            candidate: selected,
            content: `# ${selected.title}\n\n正文 ${selected.title}`,
            topic_context: { topic_id: payload.topic_id, title: 'Cloud Data and AI Platform', article_count: 1 },
          },
        },
      })
    })
    api.unlinkWikiIntakeCandidatePrimaryTopic.mockImplementation((candidateId) => {
      const selected = { ...(detailById.get(candidateId) || items[0]) }
      selected.auto_processed = { ...(selected.auto_processed || {}), topic_id: '', association_status: 'unlinked' }
      selected.status = 'needs_human_review'
      return Promise.resolve({
        data: {
          association: selected.auto_processed,
          detail: {
            candidate: selected,
            content: `# ${selected.title}\n\n正文 ${selected.title}`,
            topic_context: null,
          },
        },
      })
    })
    api.getOverview.mockResolvedValue({ data: { projects: [] } })
  }

  function mountPage(candidateOverride = candidate) {
    resetMocks(candidateOverride)
    return mount(WikiIntakePage, {
      global: {
        stubs: {
          AppShell: { template: '<main><slot /></main>', props: ['crumbs'] },
        },
      },
    })
  }

  it('loads config, candidates, and selected markdown detail', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(api.getWikiIntakeConfig).toHaveBeenCalled()
    expect(api.listWikiIntakeCandidates).toHaveBeenCalled()
    expect(api.getWikiIntakeCandidate).toHaveBeenCalledWith('src_agent_harness')
    expect(wrapper.text()).toContain('素材加工台')
    expect(wrapper.text()).toContain('Agent Harness')
    expect(wrapper.text()).toContain('待处理')
    expect(wrapper.text()).toContain('正文 agent harness codex')
  })

  it('keeps raw markdown and reader tabs available behind the digest-first tab order', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const tabs = wrapper.findAll('.detail-tab-btn')
    expect(tabs.map((tab) => tab.text())).toEqual(['预消化结果', 'Markdown 原文', '阅读视图', '元数据'])
    expect(tabs[2].classes()).toContain('active')
    expect(wrapper.find('.reader-tab-panel h1').text()).toBe('Agent Harness')

    await tabs[1].trigger('click')
    expect(wrapper.find('.preview-block pre').text()).toContain('# Agent Harness')
  })

  it('renders completed item as human-readable predigest before audit manifest', async () => {
    const wrapper = mountPage({
      ...completedCandidate,
      latest_processing: { status: 'completed', digest_path: '/tmp/pre_digest.json' },
    })
    await flushPromises()

    expect(api.getWikiIntakeProcessedResult).toHaveBeenCalledWith('src_agent_harness')
    expect(wrapper.findAll('.detail-tab-btn')[0].classes()).toContain('active')
    expect(wrapper.find('.digest-review-surface').text()).toContain('处理结论 / 推荐主题')
    expect(wrapper.find('.digest-review-surface').text()).toContain('推荐主题')
    expect(wrapper.find('.digest-review-surface').text()).toContain('Harness digest summary')
    expect(wrapper.find('.digest-review-surface').text()).toContain('候选概念')
    expect(wrapper.find('.digest-review-surface').text()).toContain('Agent 经济')
    expect(wrapper.find('.digest-review-surface').text()).toContain('以能执行任务、接管流程或生成专用软件的 AI Agent 为核心的新商业组织方式。')
    expect(wrapper.find('.digest-review-surface').text()).toContain('Candidate Concept')
    expect(wrapper.find('.digest-review-surface').text()).toContain('建议写入 Wiki 的安全摘要')
    expect(wrapper.find('.digest-review-surface').text()).toContain('不能直接当事实写')
    expect(wrapper.find('.digest-review-surface').text()).toContain('KFC 后续动作建议')
    expect(wrapper.find('.digest-review-surface').text()).toContain('建议匹配已有 KFC 概念')
    expect(wrapper.find('.digest-review-surface').text()).not.toContain('Canonical Concept')
    expect(wrapper.find('.digest-review-surface').text()).not.toContain('verified_digest_json_path')
    expect(wrapper.find('.audit-details').element.open).toBe(false)

    await wrapper.findAll('.detail-tab-btn')[3].trigger('click')
    expect(wrapper.text()).toContain('candidate_id')
    expect(wrapper.text()).toContain('source_id')
    expect(wrapper.text()).toContain('source_file_path')
    expect(wrapper.text()).toContain('content_hash')
    expect(wrapper.text()).toContain('agent-harness')
  })

  it('renders claim source URLs as new-tab links while leaving non-web sources as text', async () => {
    const wrapper = mountPage({
      ...completedCandidate,
      processed_result: {
        status: 'complete',
        auto_processed: completedCandidate.auto_processed,
        verified_digest: {
          json: {
            source_summary: 'Harness digest summary',
            safe_summary: '安全写法摘要。',
          },
          md: '',
        },
        claim_ledger: [
          {
            claim_id: 'c001',
            claim_text: 'Agent Harness 决定 agent 工作流上限。',
            verification_status: 'verified',
            supporting_urls: [
              'https://example.com/agent',
              '/tmp/local-sources.json',
              'file:///tmp/source.md',
            ],
          },
        ],
        sources: { sources: [{ title: 'Agent Harness', url: 'https://example.com/agent' }] },
      },
    })
    await flushPromises()

    const sourceLinks = wrapper.findAll('.source-details .source-url-link')
    expect(sourceLinks).toHaveLength(1)
    expect(sourceLinks[0].attributes('href')).toBe('https://example.com/agent')
    expect(sourceLinks[0].attributes('target')).toBe('_blank')
    expect(sourceLinks[0].attributes('rel')).toBe('noopener noreferrer')
    expect(wrapper.find('.source-details').text()).toContain('/tmp/local-sources.json')
    expect(wrapper.find('.source-details').text()).toContain('file:///tmp/source.md')
  })

  it('keeps manifest paths hidden by default but visible after expanding audit details', async () => {
    const wrapper = mountPage(completedCandidate)
    await flushPromises()

    const audit = wrapper.find('.audit-details')
    expect(audit.exists()).toBe(true)
    expect(audit.element.open).toBe(false)
    expect(wrapper.find('.digest-review-surface').text()).not.toContain('verified_digest_md_path')

    await audit.find('summary').trigger('click')
    expect(audit.element.open).toBe(true)
    expect(audit.text()).toContain('verified_digest_md_path')
    expect(audit.text()).toContain('/tmp/kfc-wiki-hub/topics/agent-harness/digests/verified_digest/agent-harness.md')
  })

  it('falls back gracefully when completed item only has the manifest', async () => {
    const wrapper = mountPage({
      ...completedCandidate,
      processed_result: {
        status: 'manifest_only',
        auto_processed: completedCandidate.auto_processed,
        verified_digest: { json: null, md: '' },
        claim_ledger: [],
        sources: null,
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无完整预消化摘要，仅有写入清单')
    expect(wrapper.find('.audit-details').exists()).toBe(true)
  })

  it('renders auto-created topic route mode as a readable topic message', async () => {
    const wrapper = mountPage({
      ...completedCandidate,
      auto_processed: {
        ...completedCandidate.auto_processed,
        topic_id: 'ai-native-interactive-media',
        route_mode: 'auto_created_topic',
      },
      processed_result: {
        status: 'complete',
        auto_processed: {
          ...completedCandidate.auto_processed,
          topic_id: 'ai-native-interactive-media',
          route_mode: 'auto_created_topic',
        },
        verified_digest: {
          json: {
            routing_decision: {
              route_mode: 'auto_created_topic',
              resolved_topic_id: 'ai-native-interactive-media',
              resolved_topic_label: 'AI Native Interactive Media & Games',
              original_confidence: 'high',
              original_confidence_score: 0.87,
            },
            source_summary: 'AI 互动视频案例摘要。',
            verified_summary: '安全写法摘要。',
            core_concepts: ['AI 原生互动视频'],
          },
          md: '',
        },
        claim_ledger: [],
        sources: { sources: [] },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('系统建议并自动创建了新主题：ai-native-interactive-media')
    expect(wrapper.text()).toContain('AI Native Interactive Media & Games')
  })

  it('scans Clippings and records human decisions through live provider calls', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button.primary-btn')[0].trigger('click')
    await flushPromises()

    expect(api.scanWikiIntake).toHaveBeenCalled()
    expect(wrapper.text()).toContain('扫描完成：80 条 Markdown，重复风险 5 条。')

    const note = wrapper.find('textarea')
    await note.setValue('确认进入 wiki')
    await wrapper.findAll('.decision-actions button')[0].trigger('click')
    await flushPromises()

    expect(api.createWikiIntakeDecision).toHaveBeenCalledWith({
      candidate_id: 'src_agent_harness',
      decision: 'accepted',
      target: 'wiki',
      note: '确认进入 wiki',
      operator: 'human',
    })
    expect(wrapper.text()).toContain('已记录决策：已接收')
  })

  it('runs a manual intake queue tick from the toolbar', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button.primary-btn')[1].trigger('click')
    await flushPromises()

    expect(api.processNextWikiIntake).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('手动处理完成：completed')
  })

  it('shows completed wiki artifacts instead of accept actions', async () => {
    const wrapper = mountPage(completedCandidate)
    await flushPromises()

    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.findAll('.detail-tab-btn')[0].classes()).toContain('active')
    expect(wrapper.text()).not.toContain('已进 Wiki')

    await wrapper.findAll('.detail-tab-btn')[1].trigger('click')

    expect(wrapper.text()).toContain('已进 Wiki')
    expect(wrapper.text()).toContain('agent-harness')
    expect(wrapper.text()).toContain('旧 intake 状态回填')
    expect(wrapper.text()).toContain('原文入库文件')
    expect(wrapper.find('.decision-actions').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('接收进 Wiki')
  })

  it('shows topic context for a completed intake item', async () => {
    const wrapper = mountPage({
      ...completedCandidate,
      topic_context: {
        topic_id: 'ai-tokenization',
        title: 'AI 分词与计费成本',
        article_count: 6,
        needs_review_count: 0,
        cluster_ids: ['tc_wiki_ai-tokenization'],
        cluster_links: [{ cluster_id: 'tc_wiki_ai-tokenization', title: 'AI 分词与计费成本' }],
        recent_same_topic_articles: [
          { candidate_id: 'src_token', title: 'Token Economy（词元经济）产业链全景报告' },
        ],
      },
    })
    await flushPromises()

    await wrapper.findAll('.detail-tab-btn')[1].trigger('click')

    expect(wrapper.text()).toContain('所属主题上下文')
    expect(wrapper.text()).toContain('AI 分词与计费成本')
    expect(wrapper.text()).toContain('当前主题文章数')
    expect(wrapper.text()).toContain('6 篇')
    expect(wrapper.text()).toContain('Token Economy（词元经济）产业链全景报告')
  })

  it('changes and unlinks the primary topic from the detail panel', async () => {
    const wrapper = mountPage({
      ...completedCandidate,
      topic_context: {
        topic_id: 'agent-harness',
        title: 'Agent Harness',
        article_count: 1,
        cluster_ids: [],
        cluster_links: [],
        recent_same_topic_articles: [],
      },
    })
    await flushPromises()

    await wrapper.findAll('.detail-tab-btn')[1].trigger('click')

    const select = wrapper.find('.topic-correction-panel select')
    await select.setValue('cloud-data-ai-platform')
    await wrapper.find('.topic-correction-panel input').setValue('Data+AI correction')
    await wrapper.findAll('.correction-actions button')[0].trigger('click')
    await flushPromises()

    expect(api.changeWikiIntakeCandidatePrimaryTopic).toHaveBeenCalledWith('src_agent_harness', {
      topic_id: 'cloud-data-ai-platform',
      reason: 'Data+AI correction',
      operator: 'human',
    })
    expect(wrapper.text()).toContain('已更换主主题：cloud-data-ai-platform')

    await wrapper.findAll('.detail-tab-btn')[1].trigger('click')

    await wrapper.findAll('.correction-actions button')[1].trigger('click')
    await flushPromises()

    expect(api.unlinkWikiIntakeCandidatePrimaryTopic).toHaveBeenCalledWith('src_agent_harness', {
      reason: '',
      operator: 'human',
    })
    expect(wrapper.text()).toContain('已解除当前主主题关联')
  })

  it('renders the intake workbench as bounded panes', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.intake-layout').exists()).toBe(true)
    expect(wrapper.find('.intake-status-pane').exists()).toBe(true)
    expect(wrapper.find('.intake-list-pane').exists()).toBe(true)
    expect(wrapper.find('.intake-detail-pane').exists()).toBe(true)
  })

  it('selects a lower article without page navigation and resets detail scroll', async () => {
    const lowerCandidate = {
      ...candidate,
      candidate_id: 'src_lower_article',
      title: 'Lower Article',
      source_relative_path: 'lower-article.md',
    }
    const wrapper = mountPage([candidate, lowerCandidate])
    await flushPromises()

    const detailPane = wrapper.find('.intake-detail-pane').element
    detailPane.scrollTop = 180
    await wrapper.findAll('.detail-tab-btn')[1].trigger('click')
    await wrapper.findAll('.candidate-row')[1].trigger('click')
    await flushPromises()

    expect(api.getWikiIntakeCandidate).toHaveBeenLastCalledWith('src_lower_article')
    expect(wrapper.findAll('.candidate-row')[1].classes()).toContain('selected')
    expect(wrapper.find('.detail-head h2').text()).toBe('Lower Article')
    expect(detailPane.scrollTop).toBe(0)
    expect(wrapper.findAll('.detail-tab-btn')[2].classes()).toContain('active')
    expect(window.location.search).toBe('?candidate=src_lower_article')
  })

  it('selects the candidate query parameter on initial load', async () => {
    const lowerCandidate = {
      ...candidate,
      candidate_id: 'src_lower_article',
      title: 'Lower Article',
      source_relative_path: 'lower-article.md',
    }
    window.history.replaceState(null, '', '/workspace/wiki-intake?candidate=src_lower_article')

    const wrapper = mountPage([candidate, lowerCandidate])
    await flushPromises()

    expect(api.getWikiIntakeCandidate).toHaveBeenCalledWith('src_lower_article')
    expect(wrapper.findAll('.candidate-row')[1].classes()).toContain('selected')
    expect(wrapper.find('.detail-head h2').text()).toBe('Lower Article')
  })
})
