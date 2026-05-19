<template>
  <AppShell :crumbs="crumbs">
    <section class="topic-detail">
      <div v-if="loading" class="state-card">加载中...</div>
      <div v-else-if="error" class="state-card error-card">
        <div class="error-title">加载失败</div>
        <div>{{ error }}</div>
      </div>
      <template v-else-if="cluster">
        <router-link to="/workspace/topic-clusters" class="back-link">返回主题汇集</router-link>
        <header class="detail-head">
          <div>
            <div class="section-badge">主题簇</div>
            <h1>{{ cluster.title }}</h1>
            <p>{{ cluster.description || '暂无描述' }}</p>
            <div class="meta-line">
              <span>{{ cluster.cluster_id }}</span>
              <span>{{ cluster.status }}</span>
              <span>{{ relevanceLabel(cluster.strategic_relevance) }}</span>
              <span v-if="cluster.updated_at">更新 {{ cluster.updated_at }}</span>
            </div>
            <button class="secondary-btn edit-btn" @click="startEdit">编辑主题簇</button>
          </div>
          <div class="count-grid">
            <div><strong>{{ cluster.counts?.wiki_topics || 0 }}</strong><span>Wiki</span></div>
            <div><strong>{{ cluster.article_count || 0 }}</strong><span>文章</span></div>
            <div><strong>{{ cluster.counts?.kfc_themes || 0 }}</strong><span>KFC 主题</span></div>
            <div><strong>{{ cluster.counts?.research_projects || 0 }}</strong><span>研究项目</span></div>
          </div>
        </header>

        <section v-if="currentResearchProject" class="current-project-panel">
          <div>
            <div class="section-badge">当前研究项目</div>
            <h2>{{ currentResearchProject.title }}</h2>
            <p>
              {{ currentProjectLinked ? '当前项目已显式关联该主题簇。' : '该主题簇还未加入当前研究项目；候选不会自动加入。' }}
            </p>
          </div>
          <div class="current-project-actions">
            <RouterLink
              class="secondary-btn"
              :to="`/workspace/research?project=${currentResearchProject.id}`"
              target="_blank"
              rel="noopener noreferrer"
            >
              回到项目
            </RouterLink>
            <button
              class="primary-btn"
              type="button"
              :disabled="currentProjectLinked || linkingCurrentProject"
              @click="linkCurrentProjectToCluster"
            >
              {{ currentProjectLinked ? '当前项目已关联' : (linkingCurrentProject ? '关联中...' : '关联到当前研究项目') }}
            </button>
          </div>
        </section>

        <div v-if="warnings.length" class="warning-bar">
          有 {{ warnings.length }} 个 sidecar 读取警告，异常文件已跳过。
        </div>

        <div :class="['cluster-workbench', explorationPanes.length > 1 ? 'stack-two' : 'stack-one']">
          <main class="cluster-main-column">
        <section class="asset-index-panel">
          <div class="panel-head">
            <div>
              <h2>研究资产索引</h2>
              <p>正式/候选状态显示在资产卡片上；本区只读，不自动创建关联。</p>
            </div>
            <div class="asset-head-meta" aria-label="资产索引数量摘要">
              <span class="readonly-pill">只读</span>
              <span><strong>{{ directLinkTotal }}</strong> 正式</span>
              <span><strong>{{ candidateTotal }}</strong> 候选</span>
              <span><strong>{{ assetIndex?.counts?.indirect_article_count || 0 }}</strong> 文章</span>
            </div>
          </div>
          <div v-if="assetIndexLoading" class="empty-note">资产索引加载中...</div>
          <div v-else-if="assetIndexError" class="asset-error">{{ assetIndexError }}</div>
          <template v-else-if="assetIndex">
            <div v-if="assetIndexWarnings.length" class="asset-warning">
              {{ assetIndexWarnings[0].message || '当前候选只是只读匹配，不是正式 link。' }}
            </div>
            <nav class="review-tabs" aria-label="主题簇 review sections">
              <button
                v-for="tab in reviewTabs"
                :key="tab.key"
                type="button"
                :class="{ active: activeTab === tab.key }"
                @click="activeTab = tab.key"
              >
                <span>{{ tab.label }}</span>
                <strong class="tab-count" :data-count="tab.count" aria-hidden="true" />
              </button>
            </nav>

            <section v-if="activeTab === 'articles'" class="tab-panel">
              <div class="tab-headline">
                <h3>文章</h3>
                <p>来自正式 Wiki Topic link 的文章，默认可信度高于候选资产；点击文章卡片在右侧查看摘要，显式操作只保留原文和项目证据篮。</p>
              </div>
              <div v-if="!linkedTopicArticles.length" class="empty-note">暂无已聚合文章。</div>
              <article v-for="group in linkedTopicArticles" :key="group.topic_id" class="topic-article-group">
                <div
                  class="group-head topic-folder-card topic-folder-card--toggle"
                  role="button"
                  tabindex="0"
                  :aria-expanded="isTopicGroupExpanded(group)"
                  @click="toggleTopicGroup(group)"
                  @keydown.enter.prevent="toggleTopicGroup(group)"
                  @keydown.space.prevent="toggleTopicGroup(group)"
                >
                  <span class="topic-folder-card__rail" aria-hidden="true" />
                  <div class="topic-folder-card__header">
                    <span class="asset-badge asset-badge--wiki-topic">Wiki 主题</span>
                    <strong class="topic-folder-card__title">{{ group.title || group.topic_id }}</strong>
                    <span class="topic-folder-card__meta">topic_id: {{ group.topic_id }}</span>
                    <small>点击展开/收起文章</small>
                  </div>
                  <div class="group-actions topic-folder-card__actions" @click.stop>
                    <span class="topic-folder-card__count">{{ topicArticleCount(group) }} 篇文章</span>
                    <button class="inline-action" type="button" @click="openWikiTopicPreview(group)">右侧查看</button>
                    <router-link
                      class="inline-link"
                      :to="`/workspace/wiki-topics/${group.topic_id}`"
                      target="_blank"
                      rel="noopener noreferrer"
                      @click.stop
                    >
                      新页打开
                    </router-link>
                  </div>
                </div>
                <ul v-if="isTopicGroupExpanded(group) && topicArticleItems(group).length" class="article-paper-list">
                  <li v-for="article in topicArticleItems(group)" :key="articleKey(article)">
                    <div
                      class="article-card article-paper-card clickable-card"
                      tabindex="0"
                      role="button"
                      @click="openArticlePreview(article, group, $event)"
                      @keydown.enter.prevent="openArticlePreview(article, group)"
                    >
                      <div class="article-paper-card__meta">
                        <span class="asset-badge asset-badge--article">文章</span>
                        <strong>{{ article.title }}</strong>
                        <small>{{ article.processed_at }}</small>
                      </div>
                      <div v-if="articleConceptLeads(article).length" class="article-concepts">
                        <span
                          v-for="(concept, conceptIndex) in articleConceptLeads(article).slice(0, 5)"
                          :key="`${concept.title}-${conceptIndex}`"
                          :title="concept.summary || concept.title"
                        >
                          {{ concept.title }}
                        </span>
                      </div>
                      <div class="article-reasons article-reasons--compact">
                        <span>匹配原因</span>
                        <small>{{ articleReasons(article, group)[0] }}</small>
                        <details v-if="articleReasons(article, group).length > 1">
                          <summary>更多原因</summary>
                          <small v-for="reason in articleReasons(article, group).slice(1)" :key="reason">{{ reason }}</small>
                        </details>
                      </div>
                      <div class="article-actions" @click.stop>
                        <a v-if="article.source_url" :href="article.source_url" target="_blank" rel="noopener noreferrer">打开原文</a>
                        <button
                          class="article-action-btn"
                          type="button"
                          :disabled="isArticleSlicePending(article, 'concept_lead')"
                          @click="addArticleSliceToPromotionBasket(article, group, 'concept_lead')"
                        >
                          {{ isArticleSlicePending(article, 'concept_lead') ? '加入中...' : '加入加工篮' }}
                        </button>
                        <button
                          class="article-action-btn"
                          type="button"
                          :disabled="isArticleSlicePending(article, 'evidence_slice')"
                          @click="addArticleSliceToPromotionBasket(article, group, 'evidence_slice')"
                        >
                          {{ isArticleSlicePending(article, 'evidence_slice') ? '加入中...' : '证据片段' }}
                        </button>
                        <button
                          class="article-action-btn"
                          type="button"
                          :disabled="!currentResearchProjectDetail?.id"
                          @click="addArticleToCurrentEvidenceBasket(article)"
                        >
                          {{ currentResearchProjectDetail?.id ? '加入当前项目证据篮' : '先选择当前研究项目' }}
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>
                <div v-else-if="isTopicGroupExpanded(group)" class="empty-note">该主题暂无已处理文章。</div>
              </article>
            </section>

            <section v-else-if="activeTab === 'kfc'" class="tab-panel kfc-review-panel">
              <div class="tab-headline">
                <h3>KFC 资产关系管理</h3>
                <p>同一类资产放在同一治理区，用已关联、候选、已忽略、派生和已加入当前项目区分。自动沉淀的 概念 是可用 KFC 资产，带来源追溯和事后治理入口。</p>
              </div>
              <div class="relationship-summary-strip" aria-label="KFC relationship status summary">
                <div v-for="summary in relationshipHubSummary" :key="summary.key">
                  <strong>{{ summary.count }}</strong>
                  <span>{{ summary.label }}</span>
                </div>
              </div>
              <section
                v-for="group in kfcRelationshipGroups"
                :key="group.key"
                class="candidate-review-section"
              >
                <div class="candidate-section-head">
                  <div>
                    <h3>{{ group.title }}</h3>
                    <p>{{ group.description }}</p>
                  </div>
                  <strong>{{ group.filteredItems.length }} / {{ group.items.length }}</strong>
                </div>
                <div class="candidate-filters">
                  <label>
                    <span>相关度</span>
                    <select v-model="candidateFilters[group.key].confidence">
                      <option value="all">全部</option>
                      <option value="high">高</option>
                      <option value="medium">中</option>
                      <option value="low">低</option>
                    </select>
                  </label>
                  <label>
                    <span>状态</span>
                    <select v-model="candidateFilters[group.key].status">
                      <option value="all">全部</option>
                      <option value="linked">已关联</option>
                      <option value="candidate">候选</option>
                      <option value="ignored">已忽略</option>
                      <option value="derived_from_linked_theme">来自已关联资产</option>
                      <option value="selected_for_current_project">已加入当前项目</option>
                    </select>
                  </label>
                  <label>
                    <span>来源</span>
                    <select v-model="candidateFilters[group.key].source">
                      <option value="all">全部来源</option>
                      <option v-for="source in group.sourceOptions" :key="source" :value="source">{{ source }}</option>
                    </select>
                  </label>
                </div>
                <div v-if="!group.filteredItems.length" class="empty-note">无符合条件资产。</div>
                <div v-else class="candidate-card-grid">
                  <article
                    v-for="item in group.filteredItems"
                    :key="candidateKey(item)"
                    :class="['candidate-review-card', 'clickable-card', `state-${relationState(item)}`, { selected: isCandidatePreviewOpen(item) }]"
                    :data-target-id="item.target_id"
                    :data-target-type="item.target_type"
                    :data-state="relationState(item)"
                    tabindex="0"
                    role="button"
                    @click="openCandidatePreview(item, $event)"
                    @keydown.enter.prevent="openCandidatePreview(item)"
                  >
                    <div class="candidate-card-head">
                      <div>
                        <h4>{{ item.target_title }}</h4>
                        <span>{{ candidateMetaLabel(item) }}</span>
                      </div>
                      <span :class="['status-chip', `status-${relationState(item)}`]">{{ candidateStatusLabel(item) }}</span>
                    </div>
                    <p class="candidate-summary">{{ candidateSummary(item) }}</p>
                    <p class="candidate-reason">
                      <span>{{ relationReasonTitle(item) }}</span>
                      {{ item.match_reason || item.rationale || '暂无关系说明。' }}
                    </p>
                    <div v-if="candidateMetricBadges(item).length" class="candidate-metrics">
                      <span v-for="metric in candidateMetricBadges(item)" :key="metric">{{ metric }}</span>
                    </div>
                    <div class="candidate-source-line">
                      <span>{{ candidateSourceLabel(item) }}</span>
                      <small>{{ shortSourcePath(item) }}</small>
                    </div>
                    <div class="candidate-actions" @click.stop>
                      <button class="secondary-btn" type="button" @click="openCandidatePreview(item)">右侧查看</button>
                      <button v-if="item.link_record" class="secondary-btn" type="button" @click="openCandidatePreview(item)">查看关联记录</button>
                      <RouterLink
                        v-if="candidatePrimaryRoute(item)"
                        class="secondary-btn"
                        :to="candidatePrimaryRoute(item)"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        新页打开
                      </RouterLink>
                      <RouterLink
                        v-else-if="isConceptLead(item)"
                        class="secondary-btn"
                        :to="conceptRegistrySearchRoute(item)"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        匹配已有概念
                      </RouterLink>
                      <button
                        v-if="item.target_type === 'concept' && relationState(item) !== 'selected_for_current_project'"
                        class="secondary-btn"
                        type="button"
                        :disabled="!currentResearchProjectDetail?.id || isActionPending(item)"
                        @click="addConceptToCurrentProject(item)"
                      >
                        {{ isActionPending(item) ? '处理中...' : '加入当前项目概念篮' }}
                      </button>
                      <button
                        v-if="item.target_type === 'concept' && relationState(item) === 'selected_for_current_project'"
                        class="secondary-btn"
                        type="button"
                        :disabled="!currentResearchProjectDetail?.id || isActionPending(item)"
                        @click="removeConceptFromCurrentProject(item)"
                      >
                        {{ isActionPending(item) ? '处理中...' : '移出项目概念篮' }}
                      </button>
                      <button
                        v-if="item.promotion_supported && relationState(item) === 'candidate'"
                        class="primary-btn"
                        type="button"
                        :disabled="isActionPending(item)"
                        @click="promoteCandidate(item)"
                      >
                        {{ isActionPending(item) ? '处理中...' : promoteCandidateLabel(item) }}
                      </button>
                      <button
                        v-if="relationState(item) === 'linked' && removableRelationAction(item)"
                        class="secondary-btn danger-btn"
                        type="button"
                        :disabled="isActionPending(item)"
                        @click="removeFormalAssetLink(item)"
                      >
                        {{ isActionPending(item) ? '处理中...' : removableRelationLabel(item) }}
                      </button>
                      <button v-if="relationState(item) === 'candidate'" class="secondary-btn" type="button" @click="setCandidateStatus(item, 'ignored')">忽略候选</button>
                      <button v-if="relationState(item) === 'ignored'" class="secondary-btn" type="button" @click="setCandidateStatus(item, 'candidate')">恢复候选</button>
                    </div>
                    <p v-if="cardActionError(item)" class="inline-error card-action-error">{{ cardActionError(item) }}</p>
                  </article>
                </div>
              </section>
            </section>

            <section v-else-if="activeTab === 'projects'" class="tab-panel overview-grid two-col">
              <section class="formal-empty-panel">
                <h3>研究项目</h3>
                <p>{{ formalEmptyState.research_project?.message || '暂无正式研究项目关联。' }}</p>
                <strong>发现 {{ assetIndex?.counts?.candidate_research_project_count || 0 }} 个候选研究项目，其中高置信候选 {{ highResearchProjects.length }} 个。</strong>
              </section>
              <AssetList title="正式研究项目" :items="formalResearchProjects" />
              <AssetList title="高置信研究项目候选" :items="highResearchProjects" :limit="5" @promote="promoteCandidate" />
              <details class="folded-section">
                <summary>展开弱相关或重复项目（{{ foldedResearchProjects.length }}）</summary>
                <AssetList title="弱相关研究项目候选" :items="foldedResearchProjects" :limit="10" @promote="promoteCandidate" />
              </details>
            </section>

            <section v-else-if="activeTab === 'clues'" class="tab-panel">
              <div class="tab-headline">
                <h3>证据线索</h3>
                <p>证据、洞察、笔记和草稿材料都是项目范围或只读候选，不作为主题簇级正式结论直接晋升。</p>
              </div>
              <div class="clue-summary-grid">
                <div v-for="summary in clueSummaries" :key="summary.key">
                  <strong>{{ summary.count }}</strong>
                  <span>{{ summary.label }}</span>
                  <small>{{ summary.note }}</small>
                </div>
              </div>
              <details class="folded-section" open>
                <summary>项目内证据线索（{{ evidenceClues.length }}）</summary>
                <AssetList title="证据候选" :items="evidenceClues" :limit="10" />
              </details>
              <details class="folded-section">
                <summary>洞察 / 笔记 / 草稿材料线索（{{ insightClues.length + noteClues.length + artifactClues.length }}）</summary>
                <AssetList title="洞察候选" :items="nonLowInsightClues" :limit="10" />
                <AssetList title="Notes candidates" :items="noteClues" :limit="10" />
                <AssetList title="Artifacts / Drafts" :items="artifactClues" :limit="5" empty-text="暂无 Artifact / Draft 候选。" />
              </details>
            </section>

            <section v-else class="tab-panel diagnostics-panel">
              <div class="tab-headline">
                <h3>系统诊断</h3>
                <p>保留 provenance、人工编辑和底层 link 检查入口；默认不进入主审阅流。</p>
              </div>
              <section class="asset-group">
                <h3>研究概览</h3>
                <dl>
                  <div>
                    <dt>主题簇</dt>
                    <dd>{{ assetIndex.cluster_title }}</dd>
                  </div>
                  <div>
                    <dt>战略相关性</dt>
                    <dd>{{ relevanceLabel(cluster.strategic_relevance) }}</dd>
                  </div>
                  <div>
                    <dt>生成时间</dt>
                    <dd>{{ assetIndex.generated_at }}</dd>
                  </div>
                </dl>
              </section>
            </section>
          </template>
          <div v-else class="empty-note">暂无资产索引。</div>
        </section>

        <aside v-if="selectedCandidate" class="candidate-drawer" aria-label="KFC asset relationship detail">
          <div class="candidate-drawer-backdrop" @click="closeCandidateDrawer" />
          <section class="candidate-drawer-panel">
            <div class="drawer-head">
              <div>
                <span class="section-badge">KFC ASSET RELATION</span>
                <h2>{{ selectedCandidate.target_title }}</h2>
                <p>{{ candidateTypeLabel(selectedCandidate) }} / {{ selectedCandidate.confidence_hint || relationStateLabel(selectedCandidate) }} / {{ candidateStatusLabel(selectedCandidate) }}</p>
              </div>
              <button class="secondary-btn" type="button" @click="closeCandidateDrawer">关闭</button>
            </div>
            <section class="drawer-section">
              <h3>基本信息</h3>
              <dl class="drawer-dl">
                <div><dt>ID</dt><dd>{{ selectedCandidate.target_id }}</dd></div>
                <div><dt>类型</dt><dd>{{ candidateTypeLabel(selectedCandidate) }}</dd></div>
                <div><dt>Canonical</dt><dd>{{ selectedCandidate.canonical ? '是' : '否' }} / {{ selectedCandidate.canonical_status || 'candidate' }}</dd></div>
                <div><dt>关系状态</dt><dd>{{ candidateStatusLabel(selectedCandidate) }}</dd></div>
                <div v-if="selectedCandidate.concept_type"><dt>分类</dt><dd>{{ selectedCandidate.concept_type }}</dd></div>
                <div v-if="selectedCandidate.project_status"><dt>项目状态</dt><dd>{{ selectedCandidate.project_status }}</dd></div>
                <div v-if="selectedCandidate.updated_at"><dt>最近更新</dt><dd>{{ selectedCandidate.updated_at }}</dd></div>
              </dl>
            </section>
            <section class="drawer-section">
              <h3>定义 / 说明</h3>
              <p>{{ candidateSummary(selectedCandidate) }}</p>
              <p v-if="selectedCandidate.aliases?.length" class="drawer-muted">别名：{{ selectedCandidate.aliases.join(', ') }}</p>
            </section>
            <section v-if="selectedCandidate.link_record" class="drawer-section">
              <h3>关联记录</h3>
              <dl class="drawer-dl">
                <div><dt>link_id</dt><dd>{{ selectedCandidate.link_record.link_id || selectedCandidate.link_id }}</dd></div>
                <div><dt>link_status</dt><dd>{{ selectedCandidate.link_record.link_status || selectedCandidate.status || 'linked' }}</dd></div>
                <div><dt>created_at</dt><dd>{{ selectedCandidate.link_record.created_at || '暂无创建时间' }}</dd></div>
                <div><dt>source_path</dt><dd>{{ selectedCandidate.link_record.source_path || selectedCandidate.source_path_display || 'topic_cluster_links' }}</dd></div>
              </dl>
            </section>
            <section class="drawer-section">
              <h3>为什么匹配当前主题簇</h3>
              <p>{{ selectedCandidate.match_reason || '暂无匹配原因。' }}</p>
              <dl class="drawer-dl">
                <div><dt>命中字段</dt><dd>{{ listOrMissing(selectedCandidate.matched_fields, '暂无命中字段') }}</dd></div>
                <div><dt>命中关键词</dt><dd>{{ listOrMissing(selectedCandidate.matched_terms, '暂无命中关键词') }}</dd></div>
              </dl>
            </section>
            <section class="drawer-section">
              <h3>来源与上下文</h3>
              <dl class="drawer-dl">
                <div><dt>来源类型</dt><dd>{{ selectedCandidate.source_kind || 'unknown' }}</dd></div>
                <div><dt>source_path</dt><dd>{{ selectedCandidate.source_path_display || selectedCandidate.source_path || '暂无来源路径' }}</dd></div>
                <div><dt>关联文章</dt><dd>{{ linkedItemsLabel(selectedCandidate.linked_articles, '暂无文章级来源链路，无法直接追溯到具体文章。') }}</dd></div>
                <div><dt>关联主题</dt><dd>{{ linkedItemsLabel(selectedCandidate.linked_themes, '暂无关联主题。') }}</dd></div>
                <div><dt>关联项目</dt><dd>{{ linkedItemsLabel(selectedCandidate.linked_projects, '暂无关联研究项目。') }}</dd></div>
                <div v-if="selectedCandidate.member_concepts?.length"><dt>主题内概念</dt><dd>{{ linkedItemsLabel(selectedCandidate.member_concepts, '暂无概念成员。') }}</dd></div>
                <div v-if="selectedCandidate.project_asset_summary"><dt>项目资产</dt><dd>{{ projectAssetSummaryLabel(selectedCandidate.project_asset_summary) }}</dd></div>
              </dl>
            </section>
            <section class="drawer-section">
              <h3>系统诊断</h3>
              <dl class="drawer-dl">
                <div><dt>provenance</dt><dd>{{ selectedCandidate.provenance?.source_file || 'local_asset_index' }} / mutation={{ selectedCandidate.provenance?.mutation === false ? 'false' : 'unknown' }}</dd></div>
                <div><dt>边界说明</dt><dd>{{ selectedCandidate.risk_note || selectedCandidate.diagnostics?.risk_note || '只读候选。' }}</dd></div>
                <div v-if="selectedCandidate.diagnostics?.missing_definition"><dt>定义状态</dt><dd>暂无定义/摘要，当前候选仅基于本地字段匹配生成。</dd></div>
                <div v-if="selectedCandidate.diagnostics?.concept_cluster_link_unsupported"><dt>概念 边界</dt><dd>不支持正式 主题簇-概念 关联。</dd></div>
              </dl>
            </section>
            <div class="drawer-actions">
              <RouterLink
                v-if="candidatePrimaryRoute(selectedCandidate)"
                class="secondary-btn"
                :to="candidatePrimaryRoute(selectedCandidate)"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ candidatePrimaryRouteLabel(selectedCandidate) }}
              </RouterLink>
              <RouterLink
                v-else-if="isConceptLead(selectedCandidate)"
                class="secondary-btn"
                :to="conceptRegistrySearchRoute(selectedCandidate)"
                target="_blank"
                rel="noopener noreferrer"
              >
                匹配已有概念
              </RouterLink>
              <button
                v-if="selectedCandidate.target_type === 'concept' && relationState(selectedCandidate) !== 'selected_for_current_project'"
                class="secondary-btn"
                type="button"
                :disabled="!currentResearchProjectDetail?.id || isActionPending(selectedCandidate)"
                @click="addConceptToCurrentProject(selectedCandidate)"
              >
                {{ isActionPending(selectedCandidate) ? '处理中...' : '加入当前项目概念篮' }}
              </button>
              <button
                v-if="selectedCandidate.target_type === 'concept' && relationState(selectedCandidate) === 'selected_for_current_project'"
                class="secondary-btn"
                type="button"
                :disabled="!currentResearchProjectDetail?.id || isActionPending(selectedCandidate)"
                @click="removeConceptFromCurrentProject(selectedCandidate)"
              >
                {{ isActionPending(selectedCandidate) ? '处理中...' : '移出项目概念篮' }}
              </button>
              <button
                v-if="selectedCandidate.promotion_supported && relationState(selectedCandidate) === 'candidate'"
                class="primary-btn"
                type="button"
                :disabled="isActionPending(selectedCandidate)"
                @click="promoteCandidate(selectedCandidate)"
              >
                {{ isActionPending(selectedCandidate) ? '处理中...' : promoteCandidateLabel(selectedCandidate) }}
              </button>
              <button
                v-if="relationState(selectedCandidate) === 'linked' && removableRelationAction(selectedCandidate)"
                class="secondary-btn danger-btn"
                type="button"
                :disabled="isActionPending(selectedCandidate)"
                @click="removeFormalAssetLink(selectedCandidate)"
              >
                {{ isActionPending(selectedCandidate) ? '处理中...' : removableRelationLabel(selectedCandidate) }}
              </button>
              <button v-if="relationState(selectedCandidate) === 'candidate'" class="secondary-btn" type="button" @click="setCandidateStatus(selectedCandidate, 'ignored')">忽略候选</button>
              <button v-if="relationState(selectedCandidate) === 'ignored'" class="secondary-btn" type="button" @click="setCandidateStatus(selectedCandidate, 'candidate')">恢复候选</button>
            </div>
            <p v-if="cardActionError(selectedCandidate)" class="inline-error card-action-error">{{ cardActionError(selectedCandidate) }}</p>
          </section>
        </aside>

        <form v-if="activeTab === 'diagnostics' && editingCluster" class="edit-panel" @submit.prevent="saveCluster">
          <div class="form-grid">
            <label>
              <span>标题</span>
              <input v-model="clusterForm.title" />
            </label>
            <label>
              <span>状态</span>
              <select v-model="clusterForm.status">
                <option value="candidate">candidate</option>
                <option value="active">active</option>
                <option value="needs_review">needs_review</option>
                <option value="retired">retired</option>
              </select>
            </label>
            <label>
              <span>战略相关度</span>
              <select v-model="clusterForm.strategic_relevance">
                <option value="unknown">unknown</option>
                <option value="high">high</option>
                <option value="medium">medium</option>
                <option value="low">low</option>
              </select>
            </label>
          </div>
          <label>
            <span>描述</span>
            <textarea v-model="clusterForm.description" rows="3" />
          </label>
          <div class="form-actions">
            <button class="primary-btn" type="submit" :disabled="savingCluster">保存</button>
            <button class="secondary-btn" type="button" @click="editingCluster = false">取消</button>
            <span v-if="actionError" class="inline-error">{{ actionError }}</span>
          </div>
        </form>

        <section v-if="activeTab === 'diagnostics'" class="edit-panel">
          <div class="panel-head">
            <h3>手工添加关联</h3>
            <button class="secondary-btn" type="button" @click="showAddLink = !showAddLink">
              {{ showAddLink ? '取消添加' : '添加关联' }}
            </button>
          </div>
          <form v-if="showAddLink" class="link-form" @submit.prevent="saveLink">
            <div class="form-grid">
              <label>
                <span>目标类型</span>
                <select v-model="linkForm.target_type">
                  <option value="wiki_topic">wiki_topic</option>
                  <option value="kfc_theme">kfc_theme</option>
                  <option value="research_project">research_project</option>
                </select>
              </label>
              <label>
                <span>目标 ID</span>
                <input v-model="linkForm.target_id" placeholder="agent-harness" />
              </label>
              <label>
                <span>目标标题</span>
                <input v-model="linkForm.target_title" placeholder="可选显示名" />
              </label>
              <label>
                <span>角色</span>
                <select v-model="linkForm.role">
                  <option value="primary">primary</option>
                  <option value="supporting">supporting</option>
                  <option value="candidate">candidate</option>
                </select>
              </label>
              <label>
                <span>状态</span>
                <select v-model="linkForm.status">
                  <option value="candidate">candidate</option>
                  <option value="accepted">accepted</option>
                  <option value="needs_review">needs_review</option>
                  <option value="rejected">rejected</option>
                </select>
              </label>
            </div>
            <label>
              <span>关联理由</span>
              <textarea v-model="linkForm.rationale" rows="2" />
            </label>
            <div class="form-actions">
              <button class="primary-btn" type="submit" :disabled="savingLink">保存 Link</button>
              <span v-if="linkWarning" class="inline-warning">{{ linkWarning }}</span>
              <span v-if="actionError" class="inline-error">{{ actionError }}</span>
            </div>
          </form>
        </section>

        <div v-if="activeTab === 'diagnostics'" class="detail-grid">
          <TopicClusterLinkList
            title="Wiki 预消化主题"
            :links="linksByType.wiki_topic || []"
            editable
            @update-link="patchLink"
            @remove-link="removeLink"
          />
          <section class="articles-panel">
            <h3>主题簇下聚合文章</h3>
            <div v-if="!linkedTopicArticles.length" class="empty-note">暂无已聚合文章。</div>
            <article v-for="group in linkedTopicArticles" :key="group.topic_id" class="topic-article-group">
              <div class="group-head topic-folder-card">
                <span class="topic-folder-card__rail" aria-hidden="true" />
                <div class="topic-folder-card__header">
                  <span class="asset-badge asset-badge--wiki-topic">Wiki 主题</span>
                  <strong class="topic-folder-card__title">{{ group.title || group.topic_id }}</strong>
                  <span class="topic-folder-card__meta">topic_id: {{ group.topic_id }}</span>
                </div>
                  <div class="group-actions topic-folder-card__actions">
                    <span class="topic-folder-card__count">{{ topicArticleCount(group) }} 篇文章</span>
                    <button class="inline-action" type="button" @click="openWikiTopicPreview(group)">右侧查看</button>
                    <router-link
                      class="inline-link"
                      :to="`/workspace/wiki-topics/${group.topic_id}`"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      新页打开
                    </router-link>
                  </div>
                </div>
                <ul v-if="group.articles?.length" class="article-paper-list">
                  <li v-for="article in group.articles.slice(0, 8)" :key="article.candidate_id || article.source_id">
                  <div
                    class="article-card article-paper-card clickable-card"
                    tabindex="0"
                    role="button"
                    @click="openArticlePreview(article, group, $event)"
                    @keydown.enter.prevent="openArticlePreview(article, group)"
                  >
                    <div class="article-paper-card__meta">
                      <span class="asset-badge asset-badge--article">Article</span>
                      <strong>{{ article.title }}</strong>
                      <small>{{ article.processed_at }}</small>
                    </div>
                    <div v-if="articleConceptLeads(article).length" class="article-concepts">
                      <span
                        v-for="(concept, conceptIndex) in articleConceptLeads(article).slice(0, 5)"
                        :key="`${concept.title}-${conceptIndex}`"
                        :title="concept.summary || concept.title"
                      >
                        {{ concept.title }}
                      </span>
                    </div>
                    <div class="article-reasons article-reasons--compact">
                      <span>匹配原因</span>
                      <small>{{ articleReasons(article, group)[0] }}</small>
                      <details v-if="articleReasons(article, group).length > 1">
                        <summary>更多原因</summary>
                        <small v-for="reason in articleReasons(article, group).slice(1)" :key="reason">{{ reason }}</small>
                      </details>
                    </div>
                  <div class="article-actions" @click.stop>
                    <a v-if="article.source_url" :href="article.source_url" target="_blank" rel="noopener noreferrer">打开原文</a>
                    <button
                      class="article-action-btn"
                      type="button"
                      :disabled="isArticleSlicePending(article, 'concept_lead')"
                      @click="addArticleSliceToPromotionBasket(article, group, 'concept_lead')"
                    >
                      {{ isArticleSlicePending(article, 'concept_lead') ? '加入中...' : '加入加工篮' }}
                    </button>
                    <button
                      class="article-action-btn"
                      type="button"
                      :disabled="isArticleSlicePending(article, 'evidence_slice')"
                      @click="addArticleSliceToPromotionBasket(article, group, 'evidence_slice')"
                    >
                      {{ isArticleSlicePending(article, 'evidence_slice') ? '加入中...' : '证据片段' }}
                    </button>
                    <button
                      class="article-action-btn"
                      type="button"
                      :disabled="!currentResearchProjectDetail?.id"
                      @click="addArticleToCurrentEvidenceBasket(article)"
                      >
                        {{ currentResearchProjectDetail?.id ? '加入当前项目证据篮' : '先选择当前研究项目' }}
                      </button>
                    </div>
                  </div>
                </li>
              </ul>
              <div v-else class="empty-note">该主题暂无已处理文章。</div>
            </article>
          </section>
          <section v-if="!(linksByType.kfc_theme || []).length" class="formal-empty-panel">
            <h3>KFC 主题枢纽</h3>
            <p>{{ formalEmptyState.kfc_theme?.message || '尚未建立正式 KFC 主题链接。' }}</p>
            <strong>发现 {{ assetIndex?.counts?.candidate_theme_count || 0 }} 个候选主题</strong>
          </section>
          <TopicClusterLinkList
            title="KFC 主题枢纽"
            :links="linksByType.kfc_theme || []"
            editable
            @update-link="patchLink"
            @remove-link="removeLink"
          />
          <section v-if="!(linksByType.research_project || []).length" class="formal-empty-panel">
            <h3>研究项目</h3>
            <p>{{ formalEmptyState.research_project?.message || '尚未建立正式 研究项目 链接。' }}</p>
            <strong>发现 {{ assetIndex?.counts?.candidate_research_project_count || 0 }} 个候选 研究项目</strong>
          </section>
          <TopicClusterLinkList
            title="研究项目"
            :links="linksByType.research_project || []"
            editable
            @update-link="patchLink"
            @remove-link="removeLink"
          />
        </div>
          </main>
          <aside class="exploration-stack" aria-label="主题簇探索工作台">
            <div class="exploration-stack-head">
              <div>
                <span class="section-badge">关系探索</span>
                <h2>关系探索工作台</h2>
              </div>
              <div class="exploration-stack-actions">
                <button class="secondary-btn" type="button" @click="openPromotionBasketPane">
                  KFC 加工篮 {{ promotionBasketCount ? `(${promotionBasketCount})` : '' }}
                </button>
                <button v-if="explorationPanes.length" class="secondary-btn" type="button" @click="clearExplorationStack">清空</button>
              </div>
            </div>
            <div class="exploration-path" aria-label="探索路径">
              <span>{{ cluster.title }}</span>
              <span v-for="pane in explorationPanes" :key="pane.key">{{ pane.pathLabel || pane.typeLabel }}: {{ pane.title }}</span>
            </div>
            <div v-if="!explorationPanes.length" class="empty-preview">
              <strong>选择左侧资产开始探索</strong>
              <span>单击 Wiki 主题、文章、主题、概念或研究项目会在这里打开详情；新页打开保留为显式操作。</span>
            </div>
            <div v-else class="exploration-pane-grid">
                <section
                  v-for="(pane, index) in explorationPanes"
                  :key="pane.key"
                  :class="[
                    'preview-pane',
                    {
                      pinned: pane.pinned,
                      'preview-pane--just-opened': pane.key === justOpenedPaneKey,
                      'preview-pane--wiki-topic': pane.kind === 'wiki_topic',
                      'preview-pane--article': pane.kind === 'article',
                      'preview-pane--wiki-intake': pane.kind === 'wiki_intake',
                    },
                  ]"
                  :data-pane-key="pane.key"
                  tabindex="-1"
                >
                <header class="preview-pane-head">
                  <div>
                    <span :class="['preview-type', pane.kind === 'wiki_topic' ? 'asset-badge--wiki-topic' : '', pane.kind === 'article' ? 'asset-badge--article' : '']">{{ pane.typeLabel }}</span>
                    <h3>{{ pane.title }}</h3>
                    <p>{{ pane.subtitle }}</p>
                  </div>
                  <div class="preview-pane-actions">
                    <a
                      v-if="pane.kind === 'article' && pane.entity.source_url"
                      class="secondary-btn"
                      :href="pane.entity.source_url"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      原文
                    </a>
                    <button class="secondary-btn" type="button" @click="togglePanePin(index)">{{ pane.pinned ? '取消固定' : '固定' }}</button>
                    <RouterLink
                      v-if="pane.route"
                      class="secondary-btn"
                      :to="pane.route"
                      target="_blank"
                      rel="noopener noreferrer"
                      :title="pane.routeTitle || undefined"
                    >
                      {{ pane.routeLabel || '新页打开' }}
                    </RouterLink>
                    <button class="secondary-btn" type="button" @click="closePreviewPane(index)">收起</button>
                  </div>
                </header>
                <div v-if="pane.contextPath?.length" class="pane-context-strip" aria-label="Pane context path">
                  <span v-for="(part, partIndex) in pane.contextPath" :key="`${pane.key}-${partIndex}`">
                    <small>{{ part.label }}</small>
                    {{ part.title }}
                  </span>
                </div>

                <section
                  v-if="pane.kind !== 'concept_detail'"
                  :class="['preview-section', { 'preview-section--topic-summary': pane.kind === 'wiki_topic', 'article-brief-section': pane.kind === 'article' }]"
                >
                  <div class="preview-section-title">
                    <h4>摘要</h4>
                    <span v-if="pane.kind === 'wiki_topic'" class="topic-folder-card__count">
                      {{ topicArticleCount(pane.entity) }} articles
                    </span>
                    <button
                      v-if="pane.kind === 'article' && (pane.entity.candidate_id || pane.entity.source_id)"
                      class="preview-inline-link"
                      type="button"
                      @click="openArticleIntakePanel(pane.entity, pane.entity, $event, { secondary: true })"
                    >
                      查看 Intake 详情
                    </button>
                  </div>
                  <p>{{ previewSummary(pane) }}</p>
                </section>

                <section
                  v-if="pane.kind === 'article' && previewRelatedItems(pane).length"
                  class="preview-section article-concept-leads-section"
                  data-testid="article-concept-leads"
                >
                  <div class="preview-section-title">
                    <h4>文章概念线索</h4>
                    <span class="topic-folder-card__count">{{ previewRelatedItems(pane).length }} 个线索</span>
                  </div>
                  <article
                    v-for="item in previewRelatedItems(pane)"
                    :key="item.key"
                    :class="['preview-related-row', 'article-lead-row', 'concept-lead-row', { selected: isRelatedPreviewOpen(item) }]"
                    role="button"
                    tabindex="0"
                    @click="openRelatedPreview(item, pane, { secondary: true })"
                    @keydown.enter.prevent="openRelatedPreview(item, pane, { secondary: true })"
                  >
                    <button
                      class="article-lead-main"
                      type="button"
                      @click="openRelatedPreview(item, pane, { secondary: true })"
                    >
                      <strong :title="item.title">{{ item.title }}</strong>
                      <span>
                        来源：当前文章 · {{ articleConceptLeadStatusLabel(pane.entity, item.title) }}
                        <template v-if="articleConceptLeadMatchedConceptLabel(pane.entity, item.title)">
                          · 匹配：{{ articleConceptLeadMatchedConceptLabel(pane.entity, item.title) }}
                        </template>
                      </span>
                      <small>推荐：{{ articleConceptLeadRecommendedAction(pane.entity, item.title) }}</small>
                    </button>
                    <div class="article-lead-actions" @click.stop>
                      <span :class="['lead-status-chip', articleConceptLeadStatusClass(pane.entity, item.title)]">
                        {{ articleConceptLeadStatusLabel(pane.entity, item.title) }}
                      </span>
                      <button
                        class="article-action-btn"
                        type="button"
                        :disabled="isArticleConceptLeadPending(pane.entity, item.title) || isArticleConceptLeadInBasket(pane.entity, item.title)"
                        @click="addArticleConceptLeadToPromotionBasket(pane.entity, item.title)"
                      >
                        {{ isArticleConceptLeadInBasket(pane.entity, item.title) ? '已入篮' : (isArticleConceptLeadPending(pane.entity, item.title) ? '加入中...' : '加入篮') }}
                      </button>
                      <RouterLink
                        class="article-action-link"
                        :to="conceptRegistrySearchRoute({ ...item.entity, target_title: item.title, sourceArticle: pane.entity })"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        匹配
                      </RouterLink>
                    </div>
                  </article>
                </section>

                <section v-if="pane.kind === 'wiki_topic'" class="preview-section preview-section--topic-articles">
                  <h4>全部文章</h4>
                  <div v-if="!topicArticleItems(pane.entity).length" class="empty-note">暂无已聚合文章。</div>
                  <button
                    v-for="article in topicArticleItems(pane.entity)"
                    :key="articleKey(article)"
                    :class="['preview-related-row', 'preview-related-row--paper', { selected: isPaneOpen(paneKey('article', article)) }]"
                    type="button"
                    @click="openArticlePreview(article, pane.entity, null, { secondary: true })"
                  >
                    <strong>{{ article.title }}</strong>
                    <span>{{ article.processed_at || article.candidate_id || article.source_id }}</span>
                  </button>
                </section>

                <section v-if="pane.kind === 'article'" class="preview-section article-processing-review">
                  <div class="preview-section-title">
                    <h4>文章加工摘要</h4>
                    <button
                      class="preview-inline-link"
                      type="button"
                      :disabled="articleProcessingLoading[articleKey(pane.entity)]"
                      @click="loadArticleProcessingReview(pane.entity)"
                    >
                      {{ articleProcessingLoading[articleKey(pane.entity)] ? '刷新中...' : '刷新审查包' }}
                    </button>
                  </div>
                  <p v-if="articleProcessingLoading[articleKey(pane.entity)]">加工审查包加载中...</p>
                  <p v-else-if="articleProcessingErrors[articleKey(pane.entity)]" class="inline-error">
                    {{ articleProcessingErrors[articleKey(pane.entity)] }}
                  </p>
                  <template v-else-if="articleProcessingReview(pane.entity)">
                    <div class="article-completion-panel" data-testid="article-completion-summary">
                      <div>
                        <span class="section-badge">文章候选审阅</span>
                        <strong>{{ articleProcessingCompletionLabel(articleProcessingReview(pane.entity)) }}</strong>
                        <small>{{ articleProcessingReview(pane.entity).article_id }}</small>
                      </div>
                      <div class="processing-summary-strip">
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.total_candidates || articleProcessingReview(pane.entity).summary?.candidate_count || 0 }}</strong> 总候选</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.pending_count || 0 }}</strong> 待处理</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.reviewed_count || 0 }}</strong> 已处理</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.changed_count || 0 }}</strong> 已变更</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.rejected_count || 0 }}</strong> 已拒绝</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.unresolved_risk_count || 0 }}</strong> 未解风险</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.relation_candidates_pending || 0 }}</strong> 关系待确认</span>
                        <span><strong>{{ articleProcessingReview(pane.entity).summary?.quote_issues_pending || 0 }}</strong> 引文待核对</span>
                      </div>
                    </div>
                    <div v-if="!articleProcessingReview(pane.entity).candidate_cards?.length" class="promotion-empty-state">
                      <strong>暂无加工候选。</strong>
                      <p>从文章概念线索加入加工篮，或让前半段处理器写入 relation candidate sidecar 后，这里会出现统一审查卡。</p>
                    </div>
                    <div v-if="articleProcessingReview(pane.entity).candidate_cards?.length" class="processing-review-workspace">
                      <details
                        v-for="group in articleProcessingGroups(articleProcessingReview(pane.entity))"
                        :key="group.group_id"
                        class="processing-review-group"
                        :data-review-group="group.group_id"
                        :open="isProcessingGroupOpenByDefault(articleProcessingReview(pane.entity), group)"
                      >
                        <summary class="processing-group-head">
                          <div>
                            <h5>{{ group.title }}</h5>
                            <p>{{ group.description }}</p>
                          </div>
                          <span>{{ group.count }} 项</span>
                        </summary>
                        <div
                          v-if="cardsForProcessingGroup(articleProcessingReview(pane.entity), group).length"
                          :class="[
                            'processing-batch-bar',
                            { 'processing-batch-bar--ready': selectedProcessingBatchActionsForGroup(pane.entity, articleProcessingReview(pane.entity), group).length },
                          ]"
                        >
                          <span>{{ processingBatchStateLabel(pane.entity, articleProcessingReview(pane.entity), group) }}</span>
                          <button
                            v-for="action in selectedProcessingBatchActionsForGroup(pane.entity, articleProcessingReview(pane.entity), group)"
                            :key="`${group.group_id}-${action.type}`"
                            :class="['processing-batch-button', { 'processing-batch-button--danger': action.danger }]"
                            type="button"
                            @click="applyProcessingBatchAction(pane.entity, action.type)"
                          >
                            <span>{{ action.label }}</span>
                            <strong>{{ action.selectedCount }} 项</strong>
                          </button>
                        </div>
                        <div v-if="processingBatchResult(pane.entity)" class="batch-result-line">
                          已应用 {{ processingBatchResult(pane.entity).summary?.applied || 0 }} / 已跳过 {{ processingBatchResult(pane.entity).summary?.skipped || 0 }}
                          <small v-for="item in processingBatchResult(pane.entity).skipped || []" :key="`${item.card_id}-${item.reason}`">{{ item.card_id }}: {{ item.reason }}</small>
                        </div>
                        <div v-if="!cardsForProcessingGroup(articleProcessingReview(pane.entity), group).length" class="processing-group-empty">
                          这个分组暂无候选。
                        </div>
                        <article
                          v-for="card in cardsForProcessingGroup(articleProcessingReview(pane.entity), group)"
                          :key="`${group.group_id}-${card.candidate_id}`"
                          class="processing-candidate-card"
                          :data-candidate-type="card.candidate_type"
                          :data-candidate-id="card.candidate_id"
                        >
                          <div class="processing-card-select">
                            <input
                              type="checkbox"
                              :checked="isProcessingCardSelected(pane.entity, card)"
                              :disabled="!card.batch_eligible || isProcessingActionPending(card)"
                              :aria-label="`选择 ${card.title}`"
                              @change="toggleProcessingCardSelection(pane.entity, card, $event.target.checked)"
                            >
                            <span>{{ card.batch_eligible ? '可批量' : '需单项处理' }}</span>
                          </div>
                          <div class="promotion-card-head">
                            <div>
                              <span class="asset-badge asset-badge--article">{{ candidateCardTypeLabel(card) }}</span>
                              <h4>{{ card.title }}</h4>
                            </div>
                            <span :class="['status-chip', `status-${card.status}`]">{{ processingStatusLabel(card.status) }}</span>
                          </div>
                          <div v-if="card.candidate_type === 'relation_candidate'" class="relation-readable-card">
                            <strong>{{ card.subject_concept || card.relation?.source_label }}</strong>
                            <span>{{ card.relation_type }}</span>
                            <strong>{{ card.object_concept || card.relation?.target_label }}</strong>
                          </div>
                          <p>{{ card.summary || card.why || card.quote || '暂无摘要。' }}</p>
                          <dl class="preview-dl compact-dl">
                            <div v-if="card.relation_type"><dt>关系</dt><dd>{{ card.subject_concept }} -> {{ card.relation_type }} -> {{ card.object_concept }}</dd></div>
                            <div><dt>原始引文</dt><dd>{{ card.original_snapshot?.quote || card.quote || '暂无引文' }}</dd></div>
                            <div v-if="card.current_snapshot?.quote && card.current_snapshot.quote !== card.original_snapshot?.quote"><dt>已审引文</dt><dd>{{ card.current_snapshot.quote }}</dd></div>
                            <div><dt>上下文</dt><dd>{{ card.context || '暂无上下文' }}</dd></div>
                            <div><dt>原因</dt><dd>{{ card.why || card.recommended_action || '暂无解释。' }}</dd></div>
                            <div><dt>置信度</dt><dd>{{ card.confidence_bucket || card.confidence_band || formatPercent(card.confidence) }}</dd></div>
                            <div><dt>来源</dt><dd>{{ card.source?.source_material_slice_id || card.source?.source_article_id || '暂无来源切片' }}</dd></div>
                          </dl>
                          <div v-if="card.alternative_matches?.length" class="registry-alternative-area">
                            <strong>注册表备选项</strong>
                            <button
                              v-for="alt in card.alternative_matches.slice(0, 3)"
                              :key="alt.concept_id || alt.concept_name"
                              class="alternative-match-btn"
                              type="button"
                              :disabled="isProcessingActionPending(card)"
                              @click="switchProcessingCandidateMatch(card, alt, pane.entity)"
                            >
                              <span>{{ alt.concept_name || alt.concept_id }}</span>
                              <small>{{ alt.reason || '切换到该概念' }}</small>
                            </button>
                          </div>
                          <div v-if="card.risk_flag_details?.length || card.risk_flags?.length" class="processing-risk-line">
                            <span v-for="flag in processingRiskLabels(card)" :key="flag">{{ flag }}</span>
                          </div>
                          <div v-if="card.candidate_type === 'relation_candidate'" class="drawer-actions">
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="confirmRelationCandidate(card, pane.entity)">确认关系</button>
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="changeRelationCandidateType(card, pane.entity)">修改关系类型</button>
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="rejectRelationCandidate(card, pane.entity)">拒绝关系</button>
                          </div>
                          <div v-else class="drawer-actions">
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="reviewProcessingQuote(card, 'weak', pane.entity)">引文较弱</button>
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="reviewProcessingQuote(card, 'wrong', pane.entity)">引文错误</button>
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="reviewProcessingQuote(card, 'needs_verification', pane.entity)">需要核验</button>
                            <button class="secondary-btn" type="button" :disabled="isProcessingActionPending(card)" @click="requestBetterProcessingQuote(card, pane.entity)">请求更好引文</button>
                          </div>
                        </article>
                      </details>
                    </div>
                    <details v-if="articleProcessingTrail(articleProcessingReview(pane.entity)).length" class="review-trail-panel">
                      <summary>审计与追溯</summary>
                      <article
                        v-for="event in articleProcessingTrail(articleProcessingReview(pane.entity))"
                        :key="event.action_id || `${event.card_id}-${event.timestamp}`"
                        class="review-trail-item"
                      >
                        <div>
                          <strong>{{ event.action_type }}</strong>
                          <span>{{ event.timestamp }}</span>
                          <small>{{ event.card_id }}</small>
                        </div>
                        <dl class="preview-dl compact-dl">
                          <div><dt>之前</dt><dd>{{ reviewTrailValue(event.before) }}</dd></div>
                          <div><dt>之后</dt><dd>{{ reviewTrailValue(event.after) }}</dd></div>
                          <div><dt>审核人</dt><dd>{{ event.reviewer || 'human' }}</dd></div>
                        </dl>
                      </article>
                    </details>
                  </template>
                  <p v-else class="empty-note">尚未加载文章加工审查包。</p>
                </section>

                <section v-if="pane.kind === 'asset'" class="preview-section compact-provenance-section">
                  <div class="provenance-strip" aria-label="来源摘要">
                    <span v-for="chip in compactProvenanceChips(pane.entity)" :key="chip">{{ chip }}</span>
                  </div>
                  <details class="provenance-details">
                    <summary>来源详情</summary>
                    <dl class="preview-dl">
                      <div><dt>ID</dt><dd>{{ pane.entity.target_id }}</dd></div>
                      <div><dt>关系状态</dt><dd>{{ candidateStatusLabel(pane.entity) }}</dd></div>
                      <div><dt>来源关系</dt><dd>{{ candidateSourceLabel(pane.entity) }}</dd></div>
                      <div><dt>source_path</dt><dd>{{ pane.entity.source_path_display || pane.entity.source_path || '暂无来源路径' }}</dd></div>
                      <div><dt>关联文章</dt><dd>{{ linkedItemsLabel(pane.entity.linked_articles, '暂无文章级来源链路，无法直接追溯到具体文章。') }}</dd></div>
                      <div><dt>关联主题</dt><dd>{{ linkedItemsLabel(pane.entity.linked_themes, '暂无关联主题。') }}</dd></div>
                      <div><dt>关联项目</dt><dd>{{ linkedItemsLabel(pane.entity.linked_projects, '暂无关联研究项目。') }}</dd></div>
                      <div v-if="pane.entity.concept_type"><dt>概念类型</dt><dd>{{ pane.entity.concept_type }}</dd></div>
                      <div v-if="pane.entity.project_asset_summary"><dt>项目资产</dt><dd>{{ projectAssetSummaryLabel(pane.entity.project_asset_summary) }}</dd></div>
                    </dl>
                  </details>
                </section>

                <section v-if="pane.kind === 'asset' && isConceptLead(pane.entity)" class="preview-section unresolved-concept-notice">
                  <h4>注册表状态</h4>
                  <p>该概念只是文章提取线索，尚未解析到概念注册表条目。</p>
                  <RouterLink
                    class="secondary-btn"
                    :to="conceptRegistrySearchRoute(pane.entity)"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    匹配已有概念
                  </RouterLink>
                </section>

                <section v-if="pane.kind === 'asset' && pane.entity.link_record" class="preview-section">
                  <h4>关联记录</h4>
                  <dl class="preview-dl">
                    <div><dt>link_id</dt><dd>{{ pane.entity.link_record.link_id || pane.entity.link_id }}</dd></div>
                    <div><dt>link_status</dt><dd>{{ pane.entity.link_record.link_status || pane.entity.status || 'linked' }}</dd></div>
                    <div><dt>created_at</dt><dd>{{ pane.entity.link_record.created_at || '暂无创建时间' }}</dd></div>
                  </dl>
                </section>

                <section v-if="isThemeAssetPane(pane)" class="preview-section theme-concepts-section">
                  <div class="preview-section-title">
                    <h4>{{ themeConceptTitle(pane.entity) }}</h4>
                    <RouterLink
                      class="preview-inline-link"
                      :to="candidatePrimaryRoute(pane.entity)"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      打开主题枢纽
                    </RouterLink>
                  </div>
                  <p v-if="themePanoramaLoading(pane.entity)">正在加载完整主题概念...</p>
                  <p v-else-if="themePanoramaError(pane.entity)" class="inline-error">{{ themePanoramaError(pane.entity) }}</p>
                  <template v-else>
                    <div v-if="themeConceptItems(pane.entity).length" class="theme-concept-list">
                      <button
                        v-for="item in themeConceptItems(pane.entity)"
                        :key="item.key"
                        :class="['preview-related-row', 'theme-concept-row', { selected: isRelatedPreviewOpen(item) }]"
                        type="button"
                        @click="openRelatedPreview(item, pane, { secondary: true })"
                      >
                        <strong>{{ item.title }}</strong>
                        <span>{{ item.typeLabel }}</span>
                      </button>
                    </div>
                    <p v-else>该主题暂无概念。</p>
                  </template>
                </section>

                <section v-if="pane.kind === 'wiki_intake'" class="preview-section intake-preview-section">
                  <WikiIntakeEmbeddedPanel :candidate-id="pane.entity.candidate_id" />
                </section>

                <section v-if="pane.kind === 'promotion_basket'" class="preview-section promotion-basket-section">
                  <div class="promotion-basket-summary">
                    <span>任务队列 {{ promotionBasketCount || 0 }}</span>
                    <span>待处理 {{ promotionBasketCounts.pending || 0 }}</span>
                    <span>已沉淀 {{ promotionBasketCounts.materialized_concept || 0 }}</span>
                    <span>已关联 {{ promotionBasketCounts.linked || 0 }}</span>
                    <span>证据 {{ promotionBasketCounts.added_to_project_evidence || 0 }}</span>
                    <span>忽略 {{ promotionBasketCounts.ignored || 0 }}</span>
                  </div>
                  <details v-if="recentPromotionChanges.length" class="promotion-changes-panel">
                    <summary>最近 KFC 变更</summary>
                    <ul>
                      <li v-for="change in recentPromotionChanges" :key="change.change_id">
                        <strong>{{ changeActionLabel(change.action) }}</strong>
                        <span>{{ change.reason || change.actor || change.timestamp }}</span>
                      </li>
                    </ul>
                  </details>
                  <p v-if="promotionBasketLoading">加工篮加载中...</p>
                  <p v-else-if="promotionBasketError" class="inline-error">{{ promotionBasketError }}</p>
                  <div v-else-if="!promotionBasketItems.length" class="promotion-empty-state">
                    <strong>还没有待加工素材。</strong>
                    <p>从左侧文章的“文章概念线索”卡片点击“加入 KFC 加工篮”后，这里会出现待处理素材。</p>
                  </div>
                  <div v-else class="promotion-basket-list promotion-task-queue">
                    <section
                      v-for="group in promotionBasketGroups"
                      :key="group.key"
                      class="promotion-basket-group"
                      :data-group-key="group.key"
                    >
                      <header class="promotion-group-head">
                        <div>
                          <h4>{{ group.title }}</h4>
                          <p>{{ group.description }}</p>
                        </div>
                        <div class="promotion-group-actions">
                          <button
                            v-if="group.batchEvidence"
                            class="secondary-btn"
                            type="button"
                            :disabled="!currentResearchProjectDetail?.id || group.items.every(isPromotionActionPending)"
                            @click="batchAddGroupAsProjectEvidence(group)"
                          >
                            批量加入项目证据
                          </button>
                          <button
                            v-if="group.batchIgnore"
                            class="secondary-btn"
                            type="button"
                            :disabled="group.items.every(isPromotionActionPending)"
                            @click="batchIgnoreGroup(group)"
                          >
                            批量忽略
                          </button>
                        </div>
                      </header>
                      <article
                        v-for="item in group.items"
                        :key="item.promotion_id"
                        class="promotion-basket-card"
                        :data-promotion-id="item.promotion_id"
                        :data-review-status="item.review_status"
                      >
                      <div class="promotion-card-head">
                        <div>
                          <span class="asset-badge asset-badge--article">{{ leadTypeLabel(item.lead_type) }}</span>
                          <h4>{{ item.title }}</h4>
                        </div>
                        <span :class="['status-chip', `status-${item.review_status}`]">{{ promotionStatusLabel(item.review_status) }}</span>
                      </div>
                      <p>{{ item.summary || item.source_quote || '暂无摘要。' }}</p>
                      <div class="promotion-source-line">
                        <span>{{ item.source?.source_title || item.source?.source_article_id || '文章' }}</span>
                        <small>{{ shortPath(item.source?.source_markdown_path || item.source?.source_content_hash || '') }}</small>
                      </div>
                      <div class="promotion-recommendation-line">
                        <span>推荐动作：{{ promotionRecommendedAction(item).label }}</span>
                        <small>匹配原因：{{ promotionRecommendedAction(item).reason }}</small>
                      </div>
                      <div v-if="promotionMatchHints(item).length" class="promotion-match-hints">
                        <strong>可能已有概念</strong>
                        <span v-for="hint in promotionMatchHints(item)" :key="hint.id || hint.label">
                          {{ hint.label }} · {{ hint.reason }}
                        </span>
                      </div>
                      <div v-if="item.extraction_reason || item.confidence !== undefined" class="promotion-quality-line">
                        <span>{{ item.extraction_reason || 'Wiki 粗加工线索' }}</span>
                        <small v-if="item.confidence !== undefined">置信度 {{ formatPercent(item.confidence) }}</small>
                      </div>
                      <details class="promotion-trace-details">
                        <summary>来源与追踪</summary>
                        <dl class="preview-dl">
                          <div><dt>文章</dt><dd>{{ item.source?.source_article_id || 'unknown' }}</dd></div>
                          <div><dt>片段</dt><dd>{{ item.slice_id }}</dd></div>
                          <div><dt>加工项</dt><dd>{{ item.promotion_id }}</dd></div>
                          <div><dt>Wiki 主题</dt><dd>{{ item.source?.linked_wiki_topic || 'unknown' }}</dd></div>
                          <div><dt>主题簇</dt><dd>{{ item.linked_topic_cluster || 'unknown' }}</dd></div>
                          <div><dt>研究项目</dt><dd>{{ item.linked_research_project || '未绑定' }}</dd></div>
                          <div><dt>Markdown</dt><dd>{{ item.source?.source_markdown_path || '暂无路径' }}</dd></div>
                          <div><dt>Hash</dt><dd>{{ item.source?.source_content_hash || '暂无 hash' }}</dd></div>
                          <div><dt>引文</dt><dd>{{ item.source_quote || '暂无引文' }}</dd></div>
                          <div><dt>上下文</dt><dd>{{ item.source_context || item.source_excerpt || '暂无上下文' }}</dd></div>
                          <div><dt>来源动作</dt><dd>{{ item.decision || item.lead_type }}</dd></div>
                        </dl>
                      </details>
                      <div v-if="item.review_status !== 'pending'" class="promotion-result-panel">
                        <strong>{{ promotionResultLabel(item) }}</strong>
                        <span v-if="promotionTargetLabel(item)">{{ promotionTargetLabel(item) }}</span>
                      </div>
                      <div v-if="item.review_status === 'pending'" class="drawer-actions">
                        <button
                          v-if="item.lead_type === 'concept_lead'"
                          class="secondary-btn"
                          type="button"
                          :disabled="isPromotionActionPending(item)"
                          @click="linkPromotionToExistingRegistry(item)"
                        >
                          关联已有概念
                        </button>
                        <button
                          v-if="item.lead_type === 'concept_lead'"
                          class="secondary-btn"
                          type="button"
                          :disabled="isPromotionActionPending(item)"
                          @click="depositPromotionAsNewConcept(item)"
                        >
                          沉淀为新概念
                        </button>
                        <button
                          class="secondary-btn"
                          type="button"
                          :disabled="!currentResearchProjectDetail?.id || isPromotionActionPending(item)"
                          @click="addPromotionAsProjectEvidence(item)"
                        >
                          作为项目证据
                        </button>
                        <button
                          class="secondary-btn"
                          type="button"
                          :disabled="isPromotionActionPending(item)"
                          @click="ignoreLeadPromotion(item)"
                        >
                          忽略
                        </button>
                        <RouterLink
                          v-if="item.lead_type === 'concept_lead'"
                          class="secondary-btn"
                          :to="conceptRegistrySearchRoute(item)"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          匹配已有概念
                        </RouterLink>
                      </div>
                      <div v-else class="drawer-actions promotion-governance-actions">
                        <RouterLink
                          v-if="promotionConceptRoute(item)"
                          class="secondary-btn"
                          :to="promotionConceptRoute(item)"
                        >
                          查看概念
                        </RouterLink>
                        <RouterLink
                          v-if="promotionConceptRoute(item)"
                          class="secondary-btn"
                          :to="promotionConceptRoute(item)"
                        >
                          编辑概念
                        </RouterLink>
                        <button
                          v-if="item.target?.target_type === 'concept_registry_entry'"
                          class="secondary-btn"
                          type="button"
                          :disabled="isPromotionActionPending(item)"
                          @click="unlinkPromotionTarget(item)"
                        >
                          解除关联
                        </button>
                        <button
                          v-if="promotionConceptId(item)"
                          class="secondary-btn"
                          type="button"
                          :disabled="isPromotionActionPending(item)"
                          @click="deprecatePromotionConcept(item)"
                        >
                          标记错误 / 废弃
                        </button>
                        <button class="secondary-btn" type="button" disabled>合并到已有条目</button>
                      </div>
                      <p v-if="promotionActionError(item)" class="inline-error card-action-error">{{ promotionActionError(item) }}</p>
                      </article>
                    </section>
                  </div>
                </section>

                <section v-if="pane.kind === 'concept_detail'" class="preview-section concept-detail-preview-section">
	                  <ConceptDetailPage
	                    :entry-id="pane.entity.entry_id"
	                    embedded
	                    :context-label="pane.entity.context_label"
	                    :related-concepts="pane.entity.related_concepts || []"
	                    @navigate="openConceptDetailById($event, { secondary: true })"
	                    @loaded="updateConceptPaneSource(pane.key, $event)"
	                  />
                </section>

                <section v-if="pane.kind !== 'article' && previewRelatedItems(pane).length" class="preview-section">
                  <h4>{{ relatedItemsSectionTitle(pane) }}</h4>
                  <article
                    v-for="item in previewRelatedItems(pane)"
                    :key="item.key"
                    :class="['preview-related-row', 'article-lead-row', { selected: isRelatedPreviewOpen(item) }]"
                    role="button"
                    tabindex="0"
                    @click="openRelatedPreview(item, pane, { secondary: true })"
                    @keydown.enter.prevent="openRelatedPreview(item, pane, { secondary: true })"
                  >
                    <button
                      class="article-lead-main"
                      type="button"
                      @click="openRelatedPreview(item, pane, { secondary: true })"
                    >
                      <strong>{{ item.title }}</strong>
                      <span>{{ item.typeLabel }} · 来源：当前文章</span>
                    </button>
                    <div v-if="pane.kind === 'article' && item.typeLabel === '概念线索'" class="article-lead-actions" @click.stop>
                      <span :class="['lead-status-chip', articleConceptLeadStatusClass(pane.entity, item.title)]">
                        {{ articleConceptLeadStatusLabel(pane.entity, item.title) }}
                      </span>
                      <span class="lead-recommendation">推荐动作：{{ articleConceptLeadRecommendedAction(pane.entity, item.title) }}</span>
                      <span v-if="articleConceptLeadMatchedConceptLabel(pane.entity, item.title)" class="lead-linked-concept">
                        匹配概念：{{ articleConceptLeadMatchedConceptLabel(pane.entity, item.title) }}
                      </span>
                      <button
                        class="article-action-btn"
                        type="button"
                        :disabled="isArticleConceptLeadPending(pane.entity, item.title) || isArticleConceptLeadInBasket(pane.entity, item.title)"
                        @click="addArticleConceptLeadToPromotionBasket(pane.entity, item.title)"
                      >
                        {{ isArticleConceptLeadInBasket(pane.entity, item.title) ? '已加入加工篮' : (isArticleConceptLeadPending(pane.entity, item.title) ? '加入中...' : '加入加工篮') }}
                      </button>
                      <RouterLink
                        class="article-action-link"
                        :to="conceptRegistrySearchRoute({ ...item.entity, target_title: item.title, sourceArticle: pane.entity })"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        匹配已有概念
                      </RouterLink>
                    </div>
                  </article>
                </section>

                <section v-if="pane.kind === 'asset'" class="preview-section">
                  <h4>可执行操作</h4>
                  <div class="drawer-actions">
                    <RouterLink
                      v-if="isConceptLead(pane.entity)"
                      class="secondary-btn"
                      :to="conceptRegistrySearchRoute(pane.entity)"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      匹配已有概念
                    </RouterLink>
                    <button
                      v-if="pane.entity.target_type === 'concept' && relationState(pane.entity) !== 'selected_for_current_project'"
                      class="secondary-btn"
                      type="button"
                      :disabled="!currentResearchProjectDetail?.id || isActionPending(pane.entity)"
                      @click="addConceptToCurrentProject(pane.entity)"
                    >
                      {{ isActionPending(pane.entity) ? '处理中...' : '加入当前项目概念篮' }}
                    </button>
                    <button
                      v-if="pane.entity.target_type === 'concept' && relationState(pane.entity) === 'selected_for_current_project'"
                      class="secondary-btn"
                      type="button"
                      :disabled="!currentResearchProjectDetail?.id || isActionPending(pane.entity)"
                      @click="removeConceptFromCurrentProject(pane.entity)"
                    >
                      {{ isActionPending(pane.entity) ? '处理中...' : '移出项目概念篮' }}
                    </button>
                    <button
                      v-if="pane.entity.promotion_supported && relationState(pane.entity) === 'candidate'"
                      class="primary-btn"
                      type="button"
                      :disabled="isActionPending(pane.entity)"
                      @click="promoteCandidate(pane.entity)"
                    >
                      {{ isActionPending(pane.entity) ? '处理中...' : promoteCandidateLabel(pane.entity) }}
                    </button>
                    <button
                      v-if="relationState(pane.entity) === 'linked' && removableRelationAction(pane.entity)"
                      class="secondary-btn danger-btn"
                      type="button"
                      :disabled="isActionPending(pane.entity)"
                      @click="removeFormalAssetLink(pane.entity)"
                    >
                      {{ isActionPending(pane.entity) ? '处理中...' : removableRelationLabel(pane.entity) }}
                    </button>
                  </div>
                  <p v-if="pane.entity.diagnostics?.concept_cluster_link_unsupported" class="drawer-muted">概念不建立 主题簇-概念 正式关联。</p>
                  <p v-if="cardActionError(pane.entity)" class="inline-error card-action-error">{{ cardActionError(pane.entity) }}</p>
                </section>
              </section>
            </div>
          </aside>
        </div>
      </template>
    </section>
  </AppShell>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import AssetList from '../components/topic-clusters/TopicClusterAssetList.vue'
import TopicClusterLinkList from '../components/topic-clusters/TopicClusterLinkList.vue'
import WikiIntakeEmbeddedPanel from '../components/wiki-intake/WikiIntakeEmbeddedPanel.vue'
import ConceptDetailPage from './ConceptDetailPage/ConceptDetailPage.vue'
import {
  createTopicClusterLink,
  createTopicClusterMaterialSlice,
  deleteTopicClusterLink,
  applyArticleProcessingBatchAction,
  applyRelationCandidateAction,
  applyLeadPromotionAction,
  getResearchProject,
  getTopicClusterArticleProcessingReview,
  getTopicClusterPromotionBasket,
  getTopicClusterPromotionChanges,
  getThemePanorama,
  getTopicCluster,
  getTopicClusterAssetIndex,
  updateTopicCluster,
  updateTopicClusterLink,
  updateResearchProject,
} from '../data/dataClient'
import { readCurrentResearchProject, setCurrentResearchProject, subscribeCurrentResearchProject } from '../utils/currentResearchProjectContext'
import { buildSourceArticleGraphHref } from '../utils/articleGraphRoute'

const route = useRoute()
const cluster = ref(null)
const linksByType = ref({ wiki_topic: [], kfc_theme: [], research_project: [] })
const linkedTopicArticles = computed(() => cluster.value?.linked_topic_articles || [])
const assetIndex = ref(null)
const assetIndexLoading = ref(false)
const assetIndexError = ref('')
const warnings = ref([])
const loading = ref(false)
const error = ref('')
const editingCluster = ref(false)
const savingCluster = ref(false)
const savingLink = ref(false)
const showAddLink = ref(false)
const actionError = ref('')
const linkWarning = ref('')
const activeTab = ref('articles')
const currentResearchProject = ref(null)
const currentResearchProjectDetail = ref(null)
const linkingCurrentProject = ref(false)
const selectedCandidate = ref(null)
const explorationPanes = ref([])
const promotionBasket = ref({ counts: {}, items: [] })
const promotionChanges = ref({ items: [] })
const promotionBasketLoading = ref(false)
const promotionBasketError = ref('')
const articleProcessingReviews = ref({})
const articleProcessingLoading = ref({})
const articleProcessingErrors = ref({})
const articleProcessingSelections = ref({})
const articleProcessingBatchResults = ref({})
const justOpenedPaneKey = ref('')
const themePanoramaById = ref({})
const themePanoramaLoadingById = ref({})
const themePanoramaErrorById = ref({})
const expandedTopicIds = ref(new Set())
const candidateLocalStatuses = ref({})
const relationshipOverrides = ref({})
const actionPending = ref({})
const actionErrors = ref({})
const articleSlicePending = ref({})
const promotionActionPending = ref({})
const promotionActionErrors = ref({})
const candidateFilters = ref({
  theme: { confidence: 'all', status: 'all', source: 'all' },
  concept: { confidence: 'all', status: 'all', source: 'all' },
  project: { confidence: 'all', status: 'all', source: 'all' },
})
let unsubscribeResearchProject = () => {}
let justOpenedPaneTimer = null
const clusterForm = ref({ title: '', description: '', status: 'candidate', strategic_relevance: 'unknown' })
const linkForm = ref({
  target_type: 'wiki_topic',
  target_id: '',
  target_title: '',
  role: 'candidate',
  status: 'candidate',
  rationale: '',
})

const assetIndexWarnings = computed(() => assetIndex.value?.warnings || [])
const directLinkTotal = computed(() => {
  const counts = assetIndex.value?.counts || {}
  return (counts.direct_wiki_topic_count || 0) + (counts.direct_kfc_theme_count || 0) + (counts.direct_research_project_count || 0)
})
const candidateTotal = computed(() => {
  const counts = assetIndex.value?.counts || {}
  return (
    (counts.candidate_concept_count || 0)
    + (counts.candidate_theme_count || 0)
    + (counts.candidate_research_project_count || 0)
    + (counts.candidate_evidence_count || 0)
    + (counts.candidate_insight_count || 0)
    + (counts.candidate_note_count || 0)
    + (counts.candidate_artifact_count || 0)
  )
})
const formalEmptyState = computed(() => assetIndex.value?.formal_empty_state || {})
const reviewTabs = computed(() => [
  { key: 'articles', label: '文章', count: articleAssets.value.length || cluster.value?.article_count || 0 },
  { key: 'kfc', label: 'KFC 枢纽', count: relationshipHubSummary.value.find((item) => item.key === 'all')?.count || 0 },
  { key: 'projects', label: '研究项目', count: formalResearchProjects.value.length + candidateResearchProjects.value.length },
  { key: 'clues', label: '证据线索', count: evidenceClues.value.length + insightClues.value.length + noteClues.value.length + artifactClues.value.length },
  { key: 'diagnostics', label: '系统诊断', count: warnings.value.length + assetIndexWarnings.value.length },
])
const candidateAssets = computed(() => assetIndex.value?.candidate_assets || {})
const formalAssets = computed(() => assetIndex.value?.formal_assets || {})
const derivedAssets = computed(() => assetIndex.value?.derived_assets || {})
const ignoredAssets = computed(() => assetIndex.value?.ignored_assets || {})
const articleAssets = computed(() => assetIndex.value?.indirect_assets?.articles || [])
const representativeArticleAssets = computed(() => articleAssets.value.slice(0, 5))
const promotionBasketItems = computed(() => promotionBasket.value?.items || [])
const promotionBasketCounts = computed(() => promotionBasket.value?.counts || {})
const promotionBasketCount = computed(() => promotionBasketItems.value.length)
const recentPromotionChanges = computed(() => promotionChanges.value?.items || [])
const promotionBasketGroups = computed(() => {
  const groups = {
    link_existing: {
      key: 'link_existing',
      title: '建议关联已有概念',
      description: '适合先确认目标概念正确；这里不会自动创建新概念。',
      batchEvidence: false,
      batchIgnore: true,
      items: [],
    },
    deposit_new: {
      key: 'deposit_new',
      title: '建议沉淀为新概念',
      description: '会进入正式概念库条目，建议逐条处理。',
      batchEvidence: false,
      batchIgnore: true,
      items: [],
    },
    project_evidence: {
      key: 'project_evidence',
      title: '建议加入项目证据',
      description: '适合批量处理；只进入当前研究项目证据集，不创建新概念。',
      batchEvidence: true,
      batchIgnore: true,
      items: [],
    },
    manual_review: {
      key: 'manual_review',
      title: '需要人工判断',
      description: '数据不足或动作边界不清晰，不建议批量沉淀。',
      batchEvidence: false,
      batchIgnore: true,
      items: [],
    },
    processed: {
      key: 'processed',
      title: '已处理',
      description: '用于回溯处理结果，不计入待办优先级。',
      batchEvidence: false,
      batchIgnore: false,
      items: [],
    },
  }
  for (const item of promotionBasketItems.value) {
    const action = promotionRecommendedAction(item)
    groups[action.group]?.items.push(item)
  }
  return Object.values(groups).filter((group) => group.items.length)
})

function topicGroupKey(group = {}) {
  return group.topic_id || group.title || ''
}

function topicArticleItems(group = {}) {
  return group.articles || []
}

function topicArticleCount(group = {}) {
  return topicArticleItems(group).length || group.article_count || 0
}

function articleKey(article = {}) {
  return article.candidate_id || article.source_id || article.title || ''
}

function articleProcessingReview(article = {}) {
  return articleProcessingReviews.value[articleKey(article)] || null
}

function articleProcessingGroups(review = {}) {
  const groups = review.review_groups || []
  if (groups.length) {
    const visibleGroups = groups.filter((group) => (group.count || group.card_ids?.length || 0) > 0)
    return visibleGroups.length ? visibleGroups : groups.slice(0, 1)
  }
  return [
    { group_id: 'pending_review', title: '待审核', description: '', count: review.candidate_cards?.length || 0, card_ids: (review.candidate_cards || []).map((card) => card.card_id || card.candidate_id) },
  ]
}

function cardsForProcessingGroup(review = {}, group = {}) {
  const ids = new Set(group.card_ids || [])
  return (review.candidate_cards || []).filter((card) => ids.has(card.card_id || card.candidate_id))
}

function articleProcessingTrail(review = {}) {
  return review.review_trail?.compact_items || []
}

function articleProcessingCompletionLabel(review = {}) {
  return review.article_completion?.status_label || review.summary?.completion_status_label || '审核中'
}

function processingSelectionKey(article = {}, card = {}) {
  return `${articleKey(article)}::${card.card_id || card.candidate_id || ''}`
}

function isProcessingCardSelected(article = {}, card = {}) {
  return Boolean(articleProcessingSelections.value[processingSelectionKey(article, card)])
}

function toggleProcessingCardSelection(article = {}, card = {}, checked = false) {
  const key = processingSelectionKey(article, card)
  const next = { ...articleProcessingSelections.value }
  if (checked) next[key] = card.card_id || card.candidate_id
  else delete next[key]
  articleProcessingSelections.value = next
}

function selectedProcessingCards(article = {}) {
  const review = articleProcessingReview(article)
  if (!review) return []
  return (review.candidate_cards || []).filter((card) => isProcessingCardSelected(article, card))
}

function selectedProcessingCountForGroup(article = {}, group = {}) {
  const ids = new Set(group.card_ids || [])
  return selectedProcessingCards(article).filter((card) => ids.has(card.card_id || card.candidate_id)).length
}

function selectedProcessingActionCount(article = {}, actionType = '') {
  return selectedProcessingCards(article)
    .filter((card) => (card.batch_action_types || []).includes(actionType))
    .length
}

const PROCESSING_BATCH_ACTIONS = [
  { type: 'confirm_high_confidence_concepts', label: '批量确认概念', danger: false },
  { type: 'mark_evidence_reviewed', label: '批量标记证据已审', danger: false },
  { type: 'reject_weak_relations', label: '批量拒绝弱关系', danger: true },
]

function processingCardsForGroupWithAction(review = {}, group = {}, actionType = '') {
  return cardsForProcessingGroup(review, group)
    .filter((card) => (card.batch_action_types || []).includes(actionType))
}

function selectedProcessingCardsForGroupWithAction(article = {}, review = {}, group = {}, actionType = '') {
  const ids = new Set(processingCardsForGroupWithAction(review, group, actionType).map((card) => card.card_id || card.candidate_id))
  return selectedProcessingCards(article)
    .filter((card) => ids.has(card.card_id || card.candidate_id))
}

function selectedProcessingBatchActionsForGroup(article = {}, review = {}, group = {}) {
  return PROCESSING_BATCH_ACTIONS
    .map((action) => ({
      ...action,
      eligibleCount: processingCardsForGroupWithAction(review, group, action.type).length,
      selectedCount: selectedProcessingCardsForGroupWithAction(article, review, group, action.type).length,
    }))
    .filter((action) => action.eligibleCount > 0 && action.selectedCount > 0)
}

function processingBatchStateLabel(article = {}, review = {}, group = {}) {
  const cards = cardsForProcessingGroup(review, group)
  const selectedCount = selectedProcessingCountForGroup(article, group)
  const eligibleCount = cards.filter((card) => card.batch_eligible && (card.batch_action_types || []).length).length
  if (!eligibleCount) return '本组暂无可批量处理项'
  if (!selectedCount) return `可批量处理 ${eligibleCount} 项，勾选后显示操作`
  return `已选 ${selectedCount} 项`
}

function isProcessingGroupOpenByDefault(review = {}, group = {}) {
  const cards = cardsForProcessingGroup(review, group)
  if (!cards.length) return false
  if (['pending_review', 'high_confidence_quick_confirm', 'weak_quote_review', 'relation_pending'].includes(group.group_id)) return true
  return cards.some((card) => (card.risk_flags || []).length || card.risk_flag_details?.length)
}

function processingBatchResult(article = {}) {
  return articleProcessingBatchResults.value[articleKey(article)] || null
}

async function applyProcessingBatchAction(article = {}, actionType = '') {
  if (!cluster.value?.cluster_id || !actionType) return
  const articleId = article.candidate_id || article.source_id || article.target_id || ''
  const cards = selectedProcessingCards(article).filter((card) => (card.batch_action_types || []).includes(actionType))
  const cardIds = cards.map((card) => card.card_id || card.candidate_id).filter(Boolean)
  if (!articleId || !cardIds.length) return
  actionError.value = ''
  try {
    const response = await applyArticleProcessingBatchAction(cluster.value.cluster_id, articleId, {
      action_type: actionType,
      card_ids: cardIds,
      reviewer: 'local',
      note: processingBatchNote(actionType),
    })
    articleProcessingBatchResults.value = {
      ...articleProcessingBatchResults.value,
      [articleKey(article)]: response?.data || null,
    }
    const nextSelections = { ...articleProcessingSelections.value }
    for (const card of cards) delete nextSelections[processingSelectionKey(article, card)]
    articleProcessingSelections.value = nextSelections
    await loadArticleProcessingReview(article)
  } catch (err) {
    actionError.value = err?.message || '批量审查失败'
  }
}

function processingBatchNote(actionType = '') {
  const map = {
    confirm_high_confidence_concepts: 'P1 批量确认高置信 概念线索。',
    mark_evidence_reviewed: 'P1 批量标记证据线索已审。',
    reject_weak_relations: 'P1 批量拒绝弱关系候选。',
  }
  return map[actionType] || 'P1 批量审查。'
}

function processingRiskLabels(card = {}) {
  if (card.risk_flag_details?.length) {
    return card.risk_flag_details.map((flag) => flag.label || flag.code).filter(Boolean)
  }
  return card.risk_flags || []
}

function reviewTrailValue(value = {}) {
  return Object.entries(value || {})
    .filter(([, item]) => item !== undefined && item !== null && item !== '')
    .map(([key, item]) => `${key}: ${item}`)
    .join(' / ') || '无'
}

async function loadArticleProcessingReview(article = {}) {
  const key = articleKey(article)
  const articleId = article.candidate_id || article.source_id || article.target_id || ''
  if (!cluster.value?.cluster_id || !key || !articleId) return
  articleProcessingLoading.value = { ...articleProcessingLoading.value, [key]: true }
  articleProcessingErrors.value = { ...articleProcessingErrors.value, [key]: '' }
  try {
    const response = await getTopicClusterArticleProcessingReview(cluster.value.cluster_id, articleId)
    articleProcessingReviews.value = {
      ...articleProcessingReviews.value,
      [key]: response?.data || null,
    }
  } catch (err) {
    articleProcessingErrors.value = {
      ...articleProcessingErrors.value,
      [key]: err?.message || '文章加工审查包加载失败',
    }
  } finally {
    articleProcessingLoading.value = { ...articleProcessingLoading.value, [key]: false }
  }
}

function articleSliceKey(article = {}, sliceType = 'concept_lead') {
  return `${articleKey(article)}:${sliceType}`
}

function isArticleSlicePending(article, sliceType) {
  return Boolean(articleSlicePending.value[articleSliceKey(article, sliceType)])
}

function articleConceptLeadKey(article = {}, title = '') {
  return `${articleSliceKey(article, 'concept_lead')}:${title}`
}

function isArticleConceptLeadPending(article = {}, title = '') {
  return Boolean(articleSlicePending.value[articleConceptLeadKey(article, title)])
}

function normalizeConceptName(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '')
}

function registryHintSources() {
  const sourceLists = [
    formalAssets.value?.concepts,
    candidateAssets.value?.concepts,
    derivedAssets.value?.concepts,
    ignoredAssets.value?.concepts,
  ].filter(Array.isArray)
  return sourceLists.flat().filter(Boolean)
}

function promotionMatchHints(item = {}) {
  const label = item.title || item.target?.target_label || ''
  const normalized = normalizeConceptName(label)
  if (!normalized) return []
  const hints = []
  const known = [
    item.materialized_concept,
    item.target?.target_type === 'concept_registry_entry' ? item.target : null,
    ...registryHintSources(),
  ].filter(Boolean)
  const seen = new Set()
  for (const candidate of known) {
    const candidateLabel = candidate.canonical_name || candidate.target_title || candidate.target_label || candidate.label || candidate.title || candidate.target_id || ''
    const candidateId = candidate.entry_id || candidate.concept_id || candidate.target_id || candidate.id || candidateLabel
    if (!candidateId || seen.has(candidateId)) continue
    const candidateNormalized = normalizeConceptName(candidateLabel)
    const aliases = candidate.aliases || []
    const aliasHit = aliases.some((alias) => normalizeConceptName(alias) === normalized)
    if (candidateNormalized === normalized || aliasHit) {
      seen.add(candidateId)
      hints.push({
        id: candidateId,
        label: candidateLabel,
        reason: aliasHit ? 'Alias 命中' : '名称完全一致',
      })
    }
  }
  return hints.slice(0, 3)
}

function promotionRecommendedAction(item = {}) {
  const status = item.review_status || 'pending'
  if (status !== 'pending') {
    return { group: 'processed', label: promotionResultLabel(item), reason: promotionStatusLabel(status) }
  }
  const hints = promotionMatchHints(item)
  if (hints.length || item.target?.target_id || item.concept?.concept_id || item.materialized_concept?.concept_id) {
    return { group: 'link_existing', label: '关联已有概念', reason: hints[0]?.reason || '已有目标或概念线索' }
  }
  if (item.lead_type === 'evidence_slice') {
    return { group: 'project_evidence', label: '作为项目证据', reason: item.source_quote || item.source_context ? '具备原文证据片段' : '证据片段' }
  }
  if (item.lead_type === 'concept_lead') {
    return { group: 'deposit_new', label: '沉淀为新概念', reason: '尚未找到确定性已有概念' }
  }
  return { group: 'manual_review', label: '人工判断', reason: '素材类型或目标状态不足' }
}

function isTopicGroupExpanded(group) {
  const key = topicGroupKey(group)
  return key ? expandedTopicIds.value.has(key) : false
}

function toggleTopicGroup(group) {
  const key = topicGroupKey(group)
  if (!key) return
  const next = new Set(expandedTopicIds.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedTopicIds.value = next
}

const baseFormalKfcThemes = computed(() => formalAssets.value.kfc_themes || assetIndex.value?.direct_links?.kfc_themes || [])
const baseFormalConcepts = computed(() => formalAssets.value.concepts || [])
const baseFormalResearchProjects = computed(() => formalAssets.value.research_projects || assetIndex.value?.direct_links?.research_projects || [])
const derivedConcepts = computed(() => derivedAssets.value.concepts || [])
const baseCandidateKfcThemes = computed(() => candidateAssets.value.kfc_themes || [])
const candidateConcepts = computed(() => candidateAssets.value.concepts || [])
const baseCandidateResearchProjects = computed(() => candidateAssets.value.research_projects || [])
const formalKfcThemes = computed(() => projectedFormalAssetItems(baseFormalKfcThemes.value, baseCandidateKfcThemes.value))
const candidateKfcThemes = computed(() => projectedCandidateAssetItems(baseCandidateKfcThemes.value, baseFormalKfcThemes.value))
const formalResearchProjects = computed(() => projectedFormalAssetItems(baseFormalResearchProjects.value, baseCandidateResearchProjects.value))
const candidateResearchProjects = computed(() => projectedCandidateAssetItems(baseCandidateResearchProjects.value, baseFormalResearchProjects.value))
const projectSelectedConcepts = computed(() => {
  const existing = currentResearchProjectDetail.value?.linked_concepts || []
  return existing.map((concept) => {
    const id = concept.entry_id || concept.concept_id || concept.id || concept.target_id || concept.title
    return {
      target_type: 'concept',
      target_id: id,
      target_title: concept.title || concept.name || id,
      display_type: concept.concept_type || '概念',
      concept_type: concept.concept_type || '',
      summary: concept.rationale || '',
      relation_state: 'selected_for_current_project',
      association_type: 'project_basket',
      confirmation_status: 'confirmed',
      source_kind: 'current_research_project',
      source_path_display: currentResearchProjectDetail.value?.id || '',
      match_reason: '已加入当前项目概念篮。',
      supported_actions: ['view_detail', 'open_concept_registry', 'remove_from_current_project_concept_basket'],
      promotion_supported: false,
    }
  }).filter((item) => item.target_id)
})
const currentProjectConceptIds = computed(() => new Set(
  (currentResearchProjectDetail.value?.linked_concepts || [])
    .map((concept) => concept.entry_id || concept.concept_id || concept.id || concept.target_id || concept.title)
    .filter(Boolean),
))
const relationshipCandidateTotal = computed(() => candidateKfcThemes.value.length + candidateConcepts.value.length + candidateResearchProjects.value.length)
const highConcepts = computed(() => filterByConfidence(candidateConcepts.value, 'high'))
const highResearchProjects = computed(() => filterByConfidence(candidateResearchProjects.value, 'high'))
const foldedResearchProjects = computed(() => filterNotByConfidence(candidateResearchProjects.value, 'high'))
const kfcThemeRelationshipItems = computed(() => relationshipGroupItems([
  ...baseFormalKfcThemes.value,
  ...baseCandidateKfcThemes.value,
  ...(ignoredAssets.value.kfc_themes || []),
]))
const conceptRelationshipItems = computed(() => relationshipGroupItems([
  ...baseFormalConcepts.value,
  ...derivedConcepts.value,
  ...candidateConcepts.value,
  ...projectSelectedConcepts.value,
  ...(ignoredAssets.value.concepts || []),
]))
const researchProjectRelationshipItems = computed(() => relationshipGroupItems([
  ...baseFormalResearchProjects.value,
  ...baseCandidateResearchProjects.value,
  ...(ignoredAssets.value.research_projects || []),
]))
const kfcRelationshipGroups = computed(() => [
  {
    key: 'theme',
    title: 'KFC 主题关系',
    description: '同时展示已正式关联、候选和已忽略主题。取消主题关联只移除 TopicClusterLink，不删除主题。',
    items: kfcThemeRelationshipItems.value,
  },
  {
    key: 'concept',
    title: 'KFC 概念资产',
    description: '展示已正式沉淀到 KFC 的概念、来自已关联主题的派生线索、候选线索和当前项目概念篮条目；自动沉淀资产可继续编辑、解除绑定或废弃。',
    items: conceptRelationshipItems.value,
  },
  {
    key: 'project',
    title: '研究项目关系',
    description: '同时展示已关联项目、候选项目和已忽略项目；不会自动创建研究项目。',
    items: researchProjectRelationshipItems.value,
  },
].map((group) => ({
  ...group,
  sourceOptions: sourceOptions(group.items),
  filteredItems: filterCandidates(group.items, candidateFilters.value[group.key]),
})))
const relationshipHubSummary = computed(() => {
  const items = kfcRelationshipGroups.value.flatMap((group) => group.items)
  const countState = (state) => items.filter((item) => relationState(item) === state).length
  return [
    { key: 'all', label: '全部资产', count: items.length },
    { key: 'linked', label: '已关联', count: countState('linked') },
    { key: 'candidate', label: '候选', count: countState('candidate') },
    { key: 'derived', label: '派生线索', count: countState('derived_from_linked_theme') },
    { key: 'selected', label: '当前项目', count: countState('selected_for_current_project') },
    { key: 'ignored', label: '已忽略', count: countState('ignored') },
  ]
})
const evidenceClues = computed(() => candidateAssets.value.evidence || [])
const insightClues = computed(() => candidateAssets.value.insights || [])
const nonLowInsightClues = computed(() => (candidateAssets.value.insights || []).filter((item) => item.confidence_hint !== 'low'))
const noteClues = computed(() => candidateAssets.value.notes || [])
const artifactClues = computed(() => candidateAssets.value.artifacts || [])
const clueSummaries = computed(() => [
  { key: 'evidence', label: '证据线索', count: evidenceClues.value.length, note: '项目内证据，默认折叠审阅。' },
  { key: 'insights', label: '洞察线索', count: insightClues.value.length, note: '历史项目判断，不代表当前主题簇结论。' },
  { key: 'notes', label: '笔记', count: noteClues.value.length, note: '无详情页时仅展示只读元数据。' },
  { key: 'artifacts', label: '草稿材料', count: artifactClues.value.length, note: '草稿材料默认降级。' },
])
const currentProjectLinked = computed(() => {
  const clusterId = cluster.value?.cluster_id
  const snapshot = readCurrentResearchProject() || currentResearchProjectDetail.value || currentResearchProject.value || {}
  const links = [
    ...(currentResearchProjectDetail.value?.linked_topic_clusters || []),
    ...(currentResearchProject.value?.linked_topic_clusters || []),
    ...(snapshot.linked_topic_clusters || []),
  ]
  return Boolean(clusterId && links.some((item) => item.cluster_id === clusterId))
})

const crumbs = computed(() => [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '主题汇集', to: '/workspace/topic-clusters' },
  { label: cluster.value?.title || '主题簇' },
])

function relevanceLabel(value) {
  const map = {
    high: '战略相关度高',
    medium: '战略相关度中',
    low: '战略相关度低',
    unknown: '相关度待定',
  }
  return map[value] || value || '相关度待定'
}

function filterByConfidence(items, confidence) {
  return items.filter((item) => item.confidence_hint === confidence)
}

function filterNotByConfidence(items, confidence) {
  return items.filter((item) => item.confidence_hint !== confidence)
}

function candidateKey(item) {
  return `${item?.target_type || 'candidate'}:${item?.target_id || item?.target_title || ''}`
}

function relationshipOverride(item) {
  return relationshipOverrides.value[candidateKey(item)] || null
}

function itemActionKey(item) {
  return candidateKey(item)
}

function cardActionError(item) {
  return actionErrors.value[itemActionKey(item)] || ''
}

function clearCardActionError(item) {
  const key = itemActionKey(item)
  if (!actionErrors.value[key]) return
  const next = { ...actionErrors.value }
  delete next[key]
  actionErrors.value = next
}

function setCardActionError(item, message) {
  actionErrors.value = {
    ...actionErrors.value,
    [itemActionKey(item)]: message,
  }
}

function isActionPending(item) {
  return Boolean(actionPending.value[itemActionKey(item)])
}

function setActionPending(item, pending) {
  const key = itemActionKey(item)
  const next = { ...actionPending.value }
  if (pending) next[key] = true
  else delete next[key]
  actionPending.value = next
}

function setRelationshipOverride(item, override) {
  const key = candidateKey(item)
  relationshipOverrides.value = {
    ...relationshipOverrides.value,
    [key]: override,
  }
  if (selectedCandidate.value && candidateKey(selectedCandidate.value) === candidateKey(item)) {
    selectedCandidate.value = applyRelationshipOverride(selectedCandidate.value)
  }
  explorationPanes.value = explorationPanes.value.map((pane) => (
    pane.kind === 'asset' && candidateKey(pane.entity) === key
      ? { ...pane, entity: applyRelationshipOverride(pane.entity), key: paneKey('asset', applyRelationshipOverride(pane.entity)) }
      : pane
  ))
}

function restoreRelationshipOverride(item, previous) {
  const key = candidateKey(item)
  const next = { ...relationshipOverrides.value }
  if (previous === undefined) delete next[key]
  else next[key] = previous
  relationshipOverrides.value = next
  if (selectedCandidate.value && candidateKey(selectedCandidate.value) === key) {
    selectedCandidate.value = applyRelationshipOverride(selectedCandidate.value)
  }
  explorationPanes.value = explorationPanes.value.map((pane) => (
    pane.kind === 'asset' && candidateKey(pane.entity) === key
      ? { ...pane, entity: applyRelationshipOverride(pane.entity), key: paneKey('asset', applyRelationshipOverride(pane.entity)) }
      : pane
  ))
}

function applyRelationshipOverride(item) {
  const override = relationshipOverride(item)
  if (!override) return item
  const next = { ...item, ...override }
  if (Object.prototype.hasOwnProperty.call(override, 'link_record')) next.link_record = override.link_record
  if (Object.prototype.hasOwnProperty.call(override, 'link_id')) next.link_id = override.link_id
  if (Object.prototype.hasOwnProperty.call(override, 'promotion_supported')) next.promotion_supported = override.promotion_supported
  return next
}

function dedupeAssetItems(items) {
  const seen = new Set()
  return items.filter((item) => {
    const key = candidateKey(item)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function relationshipGroupItems(items) {
  return dedupeAssetItems(items.map(applyRelationshipOverride))
}

function projectedFormalAssetItems(formalItems, candidateItems) {
  const promotedCandidates = candidateItems.filter((item) => relationState(item) === 'linked')
  return dedupeAssetItems([...formalItems, ...promotedCandidates].map(applyRelationshipOverride))
    .filter((item) => relationState(item) === 'linked')
}

function projectedCandidateAssetItems(candidateItems, formalItems) {
  const unlinkedFormal = formalItems.filter((item) => relationshipOverride(item)?.relation_state === 'candidate')
  return dedupeAssetItems([...unlinkedFormal, ...candidateItems].map(applyRelationshipOverride))
    .filter((item) => relationState(item) !== 'linked')
}

function candidateStatus(item) {
  return relationState(item)
}

function relationState(item) {
  const override = relationshipOverride(item)
  const state = candidateLocalStatuses.value[candidateKey(item)] || override?.relation_state || item?.relation_state || item?.confirmation_status || item?.status || 'candidate'
  if (state === 'unconfirmed') return 'candidate'
  if (item?.target_type === 'concept' && state !== 'ignored' && currentProjectConceptIds.value.has(item?.target_id)) return 'selected_for_current_project'
  if ((state === 'accepted' || state === 'confirmed') && item?.target_type !== 'concept') return 'linked'
  return state
}

function candidateStatusLabel(item) {
  const map = {
    linked: '已正式关联',
    candidate: '候选',
    unconfirmed: '候选',
    accepted: '已加入当前项目',
    ignored: '已忽略',
    derived_from_linked_theme: '来自已关联主题',
    selected_for_current_project: '已加入当前项目',
  }
  return map[candidateStatus(item)] || candidateStatus(item)
}

function relationStateLabel(item) {
  return candidateStatusLabel(item)
}

function setCandidateStatus(item, status) {
  candidateLocalStatuses.value = {
    ...candidateLocalStatuses.value,
    [candidateKey(item)]: status,
  }
  if (selectedCandidate.value && candidateKey(selectedCandidate.value) === candidateKey(item)) {
    selectedCandidate.value = applyRelationshipOverride(selectedCandidate.value)
  }
  explorationPanes.value = explorationPanes.value.map((pane) => (
    pane.kind === 'asset' && candidateKey(pane.entity) === candidateKey(item)
      ? { ...pane, entity: applyRelationshipOverride(pane.entity) }
      : pane
  ))
}

function restoreCandidateStatus(item, previous) {
  const key = candidateKey(item)
  const next = { ...candidateLocalStatuses.value }
  if (previous === undefined) delete next[key]
  else next[key] = previous
  candidateLocalStatuses.value = next
  if (selectedCandidate.value && candidateKey(selectedCandidate.value) === key) {
    selectedCandidate.value = applyRelationshipOverride(selectedCandidate.value)
  }
  explorationPanes.value = explorationPanes.value.map((pane) => (
    pane.kind === 'asset' && candidateKey(pane.entity) === key
      ? { ...pane, entity: applyRelationshipOverride(pane.entity) }
      : pane
  ))
}

function filterCandidates(items, filters) {
  return items.filter((item) => {
    const confidenceMatch = filters.confidence === 'all' || item.confidence_hint === filters.confidence
    const statusMatch = filters.status === 'all' || relationState(item) === filters.status
    const sourceMatch = filters.source === 'all' || item.source_kind === filters.source
    return confidenceMatch && statusMatch && sourceMatch
  })
}

function sourceOptions(items) {
  return [...new Set(items.map((item) => item.source_kind).filter(Boolean))].sort()
}

function candidateTypeLabel(item) {
  if (isConceptLead(item)) return '概念线索'
  const map = {
    kfc_theme: '主题',
    concept: item?.concept_type ? `概念 / ${item.concept_type}` : '概念',
    research_project: '研究项目',
  }
  return map[item?.target_type] || item?.display_type || item?.target_type || '候选'
}

function shortCandidateId(item) {
  const id = item?.target_id || 'no-id'
  if (id.length <= 32) return id
  return `${id.slice(0, 18)}...${id.slice(-8)}`
}

function candidateMetaLabel(item) {
  const parts = [
    candidateTypeLabel(item),
    shortCandidateId(item),
    item?.confidence_hint ? `相关度 ${item.confidence_hint}` : '',
    item?.source_kind || '',
  ].filter(Boolean)
  return parts.join(' · ')
}

function candidateSourceLabel(item) {
  if (item?.link_record) return `关联记录 ${item.link_record.link_id || item.link_id || ''}`.trim()
  if (item?.association_type === 'derived') return '来自已关联主题'
  if (item?.association_type === 'project_basket') return '当前项目概念篮'
  return item?.source_kind || 'local_asset_index'
}

function shortSourcePath(item) {
  const value = item?.source_path_display || item?.source_path || item?.provenance?.source_file || ''
  if (!value) return '暂无来源路径'
  if (value.length <= 54) return value
  return `...${value.slice(-51)}`
}

function shortPath(value = '') {
  if (!value) return '暂无来源'
  if (value.length <= 54) return value
  return `...${value.slice(-51)}`
}

function candidateMetricBadges(item) {
  const badges = []
  if (item?.member_concepts?.length) badges.push(`概念 ${item.member_concepts.length}`)
  if (item?.linked_articles?.length) badges.push(`文章 ${item.linked_articles.length}`)
  if (item?.linked_projects?.length) badges.push(`项目 ${item.linked_projects.length}`)
  if (item?.project_asset_summary) {
    const summary = item.project_asset_summary
    if (summary.evidence_count !== undefined) badges.push(`证据 ${summary.evidence_count || 0}`)
    if (summary.concept_count !== undefined) badges.push(`概念 ${summary.concept_count || 0}`)
  if (summary.topic_cluster_count !== undefined) badges.push(`主题簇 ${summary.topic_cluster_count || 0}`)
  }
  if (item?.matched_terms?.length) badges.push(`关键词 ${item.matched_terms.slice(0, 3).join(', ')}`)
  return badges.slice(0, 4)
}

function relationReasonTitle(item) {
  if (relationState(item) === 'linked') return '为什么关联'
  if (relationState(item) === 'derived_from_linked_theme') return '来源关系'
  if (relationState(item) === 'selected_for_current_project') return '用途'
  if (relationState(item) === 'ignored') return '忽略原因'
  return '为什么相关'
}

function candidateSummary(item) {
  const summary = item?.summary || item?.definition || item?.description || ''
  if (summary) return summary
  if (isConceptLead(item)) return '暂无定义/摘要，该概念只是文章提取线索，尚未解析到概念注册表条目。'
  if (item?.target_type === 'concept') return '暂无定义/摘要，当前候选仅基于 概念库 名称和本地关键词命中生成。'
  return '暂无定义/摘要，当前候选仅基于本地字段匹配生成。'
}

function conceptRegistryEntryId(item) {
  if (item?.target_type !== 'concept') return ''
  const explicitId = item?.canonical_id || item?.matched_entry_id || item?.registry_entry_id || item?.entry_id || item?.target_entry_id
  if (explicitId) return explicitId
  const targetId = item?.target_id || ''
  if (!targetId) return ''
  if (targetId.startsWith('canon_')) return targetId
  return ''
}

function isConceptLead(item) {
  return item?.target_type === 'concept' && !conceptRegistryEntryId(item)
}

function conceptRegistrySearchRoute(item) {
  const query = item?.target_title || item?.title || item?.target_id || ''
  const articleSource = item?.sourceArticle || item?.article || null
  const promotionContext = !item?.promotion_id && articleSource
    ? articleConceptLeadPromotion(articleSource, query)
    : null
  const source = item?.source || promotionContext?.source || articleSource || {}
  const selected = conceptRegistryEntryId(item) || promotionConceptId(item) || bestRegistryMatchForLead(item, promotionContext)
  const promotionId = item?.promotion_id || promotionContext?.promotion_id || ''
  const contextQuery = {
    tab: 'concepts',
    query,
    from: item?.promotion_id ? 'basket' : 'lead',
    cluster_id: cluster.value?.cluster_id || item?.linked_topic_cluster || promotionContext?.linked_topic_cluster || '',
    project_id: currentResearchProjectDetail.value?.id || currentResearchProject.value?.id || item?.linked_research_project || promotionContext?.linked_research_project || '',
    lead_id: item?.source_lead_id || item?.lead_id || promotionId || item?.key || '',
    promotion_id: promotionId,
    slice_id: item?.slice_id || item?.source_slice_id || promotionContext?.slice_id || '',
    article_id: source.source_article_id || source.candidate_id || source.source_id || item?.source_article_id || '',
    selected,
  }
  Object.keys(contextQuery).forEach((key) => {
    if (!contextQuery[key]) delete contextQuery[key]
  })
  return {
    path: '/workspace/registry',
    query: contextQuery,
  }
}

function bestRegistryMatchForLead(item = {}, promotionContext = null) {
  const direct = promotionConceptId(promotionContext || item) || conceptRegistryEntryId(item)
  if (direct) return direct
  const hints = promotionMatchHints(promotionContext || item)
  const hinted = hints.find((hint) => String(hint.id || '').startsWith('canon_'))
  return hinted?.id || ''
}

function candidatePrimaryRoute(item) {
  if (item?.target_type === 'kfc_theme') return `/workspace/themes/${item.target_id}`
  if (item?.target_type === 'concept') {
    const entryId = conceptRegistryEntryId(item)
    return entryId ? `/workspace/entry/${entryId}` : ''
  }
  if (item?.target_type === 'research_project') return item.drilldown_route || `/workspace/research?project=${item.target_id}`
  return item?.drilldown_route || ''
}

function candidatePrimaryRouteLabel(item) {
  if (item?.target_type === 'kfc_theme') return '打开主题枢纽'
  if (item?.target_type === 'concept') return '打开注册表'
  if (item?.target_type === 'research_project') return '打开项目'
  return '打开详情'
}

function themeEntityId(entity = {}) {
  return entity?.target_type === 'kfc_theme' ? (entity.target_id || entity.theme_id || entity.id || '') : ''
}

function promoteCandidateLabel(item) {
  if (item?.target_type === 'kfc_theme') return '建立关联'
  if (item?.target_type === 'research_project') return '关联当前主题簇到项目'
  return '建议建立正式关联'
}

function removableRelationAction(item) {
  return item?.supported_actions?.includes('unlink_theme') || item?.supported_actions?.includes('unlink_project') || item?.link_id
}

function removableRelationLabel(item) {
  if (item?.target_type === 'kfc_theme') return '取消主题关联'
  if (item?.target_type === 'research_project') return '取消项目关联'
  return '取消关联'
}

function paneKey(kind, entity) {
  if (kind === 'wiki_topic') return `wiki_topic:${entity?.topic_id || entity?.target_id || entity?.title || ''}`
  if (kind === 'article') return `article:${entity?.candidate_id || entity?.source_id || entity?.target_id || entity?.title || ''}`
  return `${entity?.target_type || kind}:${entity?.target_id || entity?.target_title || entity?.title || ''}`
}

function traceableConceptSourceLink(entity = {}) {
  const links = [
    ...(entity?.source_links || []),
    ...(entity?.source_evidence_refs || []),
  ]
  return links.find((link) => link?.project_id && link?.concept_key) || null
}

function conceptPaneRouteState(entity = {}, entryId = '') {
  const sourceLink = traceableConceptSourceLink(entity)
  if (sourceLink) {
    return {
      route: buildSourceArticleGraphHref(sourceLink, { from: 'registry' }),
      routeLabel: '查看原文',
      routeTitle: '在文章阅读视图中查看该概念的来源位置',
    }
  }
  if (entryId) {
    return {
      route: `/workspace/entry/${entryId}`,
      routeLabel: '打开概念',
      routeTitle: '打开完整概念工作台',
    }
  }
  return { route: '', routeLabel: '', routeTitle: '' }
}

function candidatePreviewPane(item) {
  const entity = applyRelationshipOverride(item)
  const typeLabel = candidateTypeLabel(entity)
  return {
    key: paneKey('asset', entity),
    kind: 'asset',
    typeLabel,
    pathLabel: previewPathTypeLabel(entity),
    title: entity.target_title || entity.target_id || 'Untitled asset',
    subtitle: `${candidateStatusLabel(entity)} · 来自 ${cluster.value?.title || '主题簇根节点'}`,
    contextPath: [
      { label: '主题簇', title: cluster.value?.title || '主题簇根节点' },
      { label: previewPathTypeLabel(entity), title: entity.target_title || entity.target_id || typeLabel },
    ],
    entity,
    route: candidatePrimaryRoute(entity),
    pinned: false,
  }
}

function conceptDetailPreviewPane(item, source = {}) {
  const entity = applyRelationshipOverride(item)
  const entryId = conceptRegistryEntryId(entity)
  const routeState = conceptPaneRouteState(entity, entryId)
  const sourceContext = source.title
    ? [{ label: source.typeLabel || '来源', title: source.title }]
    : []
  return {
    key: `concept_detail:${entryId}`,
    kind: 'concept_detail',
    typeLabel: '概念详情',
    pathLabel: '概念',
    title: entity.target_title || entryId || '概念',
    subtitle: `${source.relationLabel || '概念注册表详情'} · 来自 ${cluster.value?.title || '主题簇根节点'}`,
    contextPath: [
      { label: '主题簇', title: cluster.value?.title || '主题簇根节点' },
      ...sourceContext,
      { label: '概念', title: entity.target_title || entryId || '概念' },
    ],
    entity: {
      ...entity,
      entry_id: entryId,
      context_label: source.contextLabel || source.title || cluster.value?.title || '',
      related_concepts: source.relatedConcepts || entity.related_concepts || [],
    },
    ...routeState,
    pinned: false,
  }
}

function updateConceptPaneSource(key, entryData = {}) {
  if (!key || !entryData) return
  explorationPanes.value = explorationPanes.value.map((pane) => {
    if (pane.key !== key || pane.kind !== 'concept_detail') return pane
    const entity = {
      ...pane.entity,
      ...entryData,
      target_type: 'concept',
      target_id: pane.entity?.target_id || entryData.entry_id || entryData.concept_id || '',
      target_title: pane.entity?.target_title || entryData.canonical_name || entryData.entry_id || '',
      entry_id: pane.entity?.entry_id || entryData.entry_id || entryData.concept_id || '',
    }
    return {
      ...pane,
      entity,
      ...conceptPaneRouteState(entity, entity.entry_id),
    }
  })
}

function wikiTopicPreviewPane(group) {
  return {
    key: paneKey('wiki_topic', group),
    kind: 'wiki_topic',
    typeLabel: 'Wiki 主题',
    pathLabel: 'Wiki 主题',
    title: group.title || group.topic_id || 'Wiki 主题',
    subtitle: `来自 ${cluster.value?.title || '主题簇根节点'} · 文章 ${group.articles?.length || group.article_count || 0}`,
    entity: group,
    route: group.topic_id ? `/workspace/wiki-topics/${group.topic_id}` : '',
    pinned: false,
  }
}

function articlePreviewPane(article, group = {}) {
  return {
    key: paneKey('article', article),
    kind: 'article',
    typeLabel: '文章',
    pathLabel: '文章',
    title: article.title || article.target_title || article.candidate_id || article.source_id || '文章',
    subtitle: `来自 Wiki Topic: ${group.title || group.topic_id || article.topic_id || 'unknown'}`,
    entity: { ...article, topic_title: group.title || article.topic_title, topic_id: group.topic_id || article.topic_id },
    route: wikiIntakeHref(article),
    pinned: false,
  }
}

function intakePreviewPane(article, group = {}) {
  const candidateId = article?.candidate_id || article?.source_id || ''
  const topicTitle = group.topic_title || group.title || article.topic_title
  const topicId = group.topic_id || article.topic_id
  return {
    key: `wiki_intake:${candidateId || article?.title || ''}`,
    kind: 'wiki_intake',
    typeLabel: 'Wiki Intake',
    pathLabel: 'Intake',
    title: article?.title || article?.target_title || candidateId || 'Wiki Intake',
    subtitle: `素材加工台详情 · 来自 Wiki Topic: ${topicTitle || topicId || 'unknown'}`,
    entity: { ...article, candidate_id: candidateId, topic_title: topicTitle, topic_id: topicId },
    route: wikiIntakeHref(article),
    pinned: false,
  }
}

function promotionBasketPane() {
  return {
    key: 'promotion_basket',
    kind: 'promotion_basket',
    typeLabel: 'KFC 加工篮',
    pathLabel: 'KFC 加工篮',
    title: 'KFC 加工篮',
    subtitle: `${promotionBasketCount.value || 0} 个待加工素材 · 来自 ${cluster.value?.title || '主题簇根节点'}`,
    entity: { cluster_id: cluster.value?.cluster_id || '' },
    route: '',
    pinned: false,
  }
}

function previewPathTypeLabel(entity) {
  if (entity?.target_type === 'kfc_theme') return '主题'
  if (entity?.target_type === 'research_project') return '项目'
  if (entity?.target_type === 'concept') return isConceptLead(entity) ? '概念线索' : '概念'
  return candidateTypeLabel(entity)
}

function openPreviewPane(pane, event = null, options = {}) {
  if (event?.metaKey || event?.ctrlKey) {
    if (pane.route) window.open(pane.route, '_blank', 'noopener')
    return
  }
  const pageScroller = document.querySelector('.app-content')
  const pageScrollTop = pageScroller?.scrollTop
  const current = explorationPanes.value
  const primaryPinned = current[0]?.pinned
  const existingIndex = current.findIndex((item) => item.key === pane.key)
  let targetIndex = 0
  if (existingIndex >= 0) {
    targetIndex = existingIndex
  } else if (options.secondary || primaryPinned) {
    targetIndex = Math.min(Math.max(current.length, 1), 2)
  }
  const next = [...current]
  next[targetIndex] = {
    ...pane,
    pinned: next[targetIndex]?.key === pane.key ? next[targetIndex].pinned : false,
  }
  explorationPanes.value = next.slice(0, 3).filter(Boolean)
  focusOpenedPane(pane.key, { pageScroller, pageScrollTop })
}

function scrollPaneWithinExplorationStack(paneEl) {
  const stackEl = paneEl?.closest?.('.exploration-stack')
  if (!paneEl || !stackEl) return
  const paneRect = paneEl.getBoundingClientRect()
  const stackRect = stackEl.getBoundingClientRect()
  const margin = 12
  const topDelta = paneRect.top - stackRect.top
  const paneTopVisible = paneRect.top >= stackRect.top + margin && paneRect.top <= stackRect.bottom - margin
  if (paneTopVisible) return
  let nextScrollTop = stackEl.scrollTop + topDelta - margin
  if (typeof stackEl.scrollTo === 'function') {
    stackEl.scrollTo({ top: Math.max(0, nextScrollTop), behavior: 'auto' })
  } else {
    stackEl.scrollTop = Math.max(0, nextScrollTop)
  }
}

function restorePageScroll(scroller, scrollTop) {
  if (!scroller || typeof scrollTop !== 'number') return
  scroller.scrollTop = scrollTop
}

async function focusOpenedPane(key = '', options = {}) {
  if (!key) return
  await nextTick()
  justOpenedPaneKey.value = key
  restorePageScroll(options.pageScroller, options.pageScrollTop)
  if (justOpenedPaneTimer) window.clearTimeout(justOpenedPaneTimer)
  const paneEl = Array.from(document.querySelectorAll('.preview-pane'))
    .find((item) => item.dataset.paneKey === key)
  scrollPaneWithinExplorationStack(paneEl)
  paneEl?.focus?.({ preventScroll: true })
  restorePageScroll(options.pageScroller, options.pageScrollTop)
  window.requestAnimationFrame?.(() => {
    restorePageScroll(options.pageScroller, options.pageScrollTop)
  })
  justOpenedPaneTimer = window.setTimeout(() => {
    if (justOpenedPaneKey.value === key) justOpenedPaneKey.value = ''
  }, 1200)
}

function openCandidatePreview(item, event = null, options = {}) {
  if (!item) return
  openPreviewPane(candidatePreviewPane(item), event, options)
  ensureThemePanorama(item)
}

function openCandidateDrawer(item) {
  openCandidatePreview(item)
}

function openWikiTopicPreview(group, event = null, options = {}) {
  if (!group) return
  openPreviewPane(wikiTopicPreviewPane(group), event, options)
}

function openArticlePreview(article, group = {}, event = null, options = {}) {
  if (!article) return
  openPreviewPane(articlePreviewPane(article, group), event, options)
  loadArticleProcessingReview(article)
}

function openArticleIntakePanel(article, group = {}, event = null, options = {}) {
  if (!article) return
  openPreviewPane(intakePreviewPane(article, group), event, options)
}

function openPromotionBasketPane(event = null, options = {}) {
  openPreviewPane(promotionBasketPane(), event, options)
}

function openConceptDetailById(entryId, options = {}) {
  if (!entryId) return
  openPreviewPane(conceptDetailPreviewPane({
    target_type: 'concept',
    target_id: entryId,
    target_title: entryId,
    entry_id: entryId,
  }), null, options)
}

function isPaneOpen(key) {
  return explorationPanes.value.some((pane) => pane.key === key)
}

function candidatePreviewKeys(item) {
  const entity = applyRelationshipOverride(item)
  const keys = [paneKey('asset', entity)]
  const entryId = conceptRegistryEntryId(entity)
  if (entryId) keys.push(`concept_detail:${entryId}`)
  return keys
}

function isCandidatePreviewOpen(item) {
  return candidatePreviewKeys(item).some(isPaneOpen)
}

function relatedPreviewKey(item) {
  if (item.article) return paneKey('article', item.article)
  if (item.entity?.target_type === 'concept' && conceptRegistryEntryId(item.entity)) {
    return `concept_detail:${conceptRegistryEntryId(item.entity)}`
  }
  return paneKey('asset', item.entity || {})
}

function isRelatedPreviewOpen(item) {
  return isPaneOpen(relatedPreviewKey(item))
}

function clearExplorationStack() {
  explorationPanes.value = []
  selectedCandidate.value = null
}

function closePreviewPane(index) {
  explorationPanes.value = explorationPanes.value.filter((_, paneIndex) => paneIndex !== index)
}

function togglePanePin(index) {
  explorationPanes.value = explorationPanes.value.map((pane, paneIndex) => (
    paneIndex === index ? { ...pane, pinned: !pane.pinned } : pane
  ))
}

function previewSummary(pane) {
  if (pane.kind === 'wiki_topic') {
    return `当前主题簇通过 Wiki 主题聚合 ${pane.entity.articles?.length || pane.entity.article_count || 0} 篇文章。`
  }
  if (pane.kind === 'article') {
    return pane.entity.digest_summary || pane.entity.summary || `文章属于当前主题簇的原因：${articleReasons(pane.entity, pane.entity).join('；')}`
  }
  if (pane.kind === 'wiki_intake') {
    return '从素材加工台读取该文章的 Intake 记录，可在右侧直接查看阅读视图、Markdown 原文、预消化结果和元数据。'
  }
  return candidateSummary(pane.entity)
}

function normalizeRelatedItem(raw, fallbackType = 'asset') {
  const canonicalId = raw.canonical_id || raw.matched_entry_id || raw.registry_entry_id || raw.entry_id || raw.target_entry_id || ''
  const targetId = canonicalId || raw.concept_id || raw.theme_id || raw.project_id || raw.id || raw.target_id || raw.title || raw.name
  const targetTitle = raw.title || raw.name || raw.target_title || targetId
  let targetType = raw.target_type || fallbackType
  if (canonicalId || raw.concept_id || fallbackType === 'concept') targetType = 'concept'
  if (raw.theme_id || fallbackType === 'kfc_theme') targetType = 'kfc_theme'
  if (raw.project_id || fallbackType === 'research_project') targetType = 'research_project'
  const conceptLead = targetType === 'concept' && !canonicalId && !String(targetId || '').startsWith('canon_')
  return {
    key: `${targetType}:${targetId}`,
    typeLabel: candidateTypeLabel({
      target_type: targetType,
      target_id: targetId,
      canonical_id: raw.canonical_id,
      matched_entry_id: raw.matched_entry_id,
      registry_entry_id: raw.registry_entry_id,
      entry_id: raw.entry_id,
      concept_type: raw.concept_type,
    }),
    title: targetTitle,
    entity: {
      ...raw,
      canonical_id: raw.canonical_id,
      matched_entry_id: raw.matched_entry_id,
      registry_entry_id: raw.registry_entry_id,
      entry_id: raw.entry_id,
      target_type: targetType,
      target_id: targetId,
      target_title: targetTitle,
      relation_state: raw.relation_state || 'candidate',
      association_type: raw.association_type || 'reference',
      source_kind: raw.source_kind || 'preview_related_reference',
      summary: raw.summary || raw.description || '',
      promotion_supported: false,
      concept_lead: conceptLead,
    },
  }
}

function parseConceptLiteral(value = '') {
  const text = String(value || '').trim()
  if (!text.startsWith('{') || !text.includes('concept')) return null
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object') return parsed
  } catch (_) {
    // Some legacy wiki outputs stored Python-style dict strings.
  }
  const conceptMatch = text.match(/['"]concept['"]\s*:\s*['"]([^'"]+)['"]/)
  const summaryMatch = text.match(/['"]summary['"]\s*:\s*['"]([^'"]+)['"]/)
  if (!conceptMatch) return null
  return {
    concept: conceptMatch[1],
    summary: summaryMatch?.[1] || '',
  }
}

function normalizeArticleConcept(value) {
  const raw = typeof value === 'string' ? (parseConceptLiteral(value) || value) : value
  if (raw && typeof raw === 'object') {
    const title = String(raw.title || raw.concept || raw.name || '').trim()
    if (!title) return null
    return {
      title,
      summary: String(raw.summary || raw.description || raw.body || '').trim(),
    }
  }
  const title = String(raw || '').trim()
  return title ? { title, summary: '' } : null
}

function articleConceptLeads(article = {}) {
  const source = article.top_concept_details?.length ? article.top_concept_details : (article.top_concepts || [])
  const seen = new Set()
  return source
    .map((item) => normalizeArticleConcept(item))
    .filter((item) => {
      if (!item || seen.has(item.title)) return false
      seen.add(item.title)
      return true
    })
}

function articleConceptLabels(article = {}) {
  return articleConceptLeads(article).map((item) => item.title)
}

function articleConceptSummary(article = {}, title = '') {
  return articleConceptLeads(article).find((item) => item.title === title)?.summary || ''
}

function previewRelatedItems(pane) {
  if (pane.kind === 'wiki_topic') return []
  if (pane.kind === 'article') {
    return articleConceptLeads(pane.entity).slice(0, 8).map((concept) => ({
      ...normalizeRelatedItem({ title: concept.title, summary: concept.summary }, 'concept'),
      key: `article-concept-lead:${articleKey(pane.entity)}:${concept.title}`,
      typeLabel: '概念线索',
      sourceArticle: pane.entity,
    }))
  }
  if (isThemeAssetPane(pane)) return []
  const entity = pane.entity || {}
  const related = [
    ...(entity.member_concepts || []).map((item) => normalizeRelatedItem(item, 'concept')),
    ...(entity.linked_themes || []).map((item) => normalizeRelatedItem(item, 'kfc_theme')),
    ...(entity.linked_projects || []).map((item) => normalizeRelatedItem(item, 'research_project')),
    ...(entity.linked_articles || []).map((item) => ({
      key: `article:${item.candidate_id || item.source_id || item.title}`,
      typeLabel: '文章',
      title: item.title || item.candidate_id || item.source_id,
      article: item,
    })),
  ]
  return related.slice(0, 10)
}

function isThemeAssetPane(pane = {}) {
  return pane.kind === 'asset' && pane.entity?.target_type === 'kfc_theme'
}

function themePanoramaId(entity = {}) {
  return themeEntityId(entity)
}

function themePanorama(entity = {}) {
  const id = themePanoramaId(entity)
  return id ? themePanoramaById.value[id] : null
}

function themePanoramaLoading(entity = {}) {
  const id = themePanoramaId(entity)
  return id ? !!themePanoramaLoadingById.value[id] : false
}

function themePanoramaError(entity = {}) {
  const id = themePanoramaId(entity)
  return id ? themePanoramaErrorById.value[id] || '' : ''
}

function themeConceptGroups(entity = {}) {
  const groups = themePanorama(entity)?.grouped_concepts
  if (!groups) return []
  return [
    ...(groups.core || []),
    ...(groups.bridge || []),
    ...(groups.peripheral || []),
  ]
}

function themeConceptCount(entity = {}) {
  const panorama = themePanorama(entity)
  if (panorama?.stats?.concept_count != null) return panorama.stats.concept_count
  return (entity.member_concepts || []).length
}

function themeConceptTitle(entity = {}) {
  const panorama = themePanorama(entity)
  if (panorama) return `主题下的概念（${themeConceptCount(entity)}）`
  if (themePanoramaLoading(entity)) return '主题下的概念（加载中）'
  return `概念预览（${(entity.member_concepts || []).length}）`
}

function themeConceptItems(entity = {}) {
  const concepts = themeConceptGroups(entity)
  if (concepts.length) {
    return concepts.map((concept) => normalizeRelatedItem({
      ...concept,
      title: concept.canonical_name || concept.title || concept.entry_id,
      entry_id: concept.entry_id,
      target_id: concept.entry_id,
      concept_type: concept.concept_type,
      summary: concept.description,
      relation_state: 'member',
    }, 'concept'))
  }
  return (entity.member_concepts || []).map((item) => normalizeRelatedItem(item, 'concept'))
}

async function ensureThemePanorama(entity = {}) {
  const themeId = themeEntityId(entity)
  if (!themeId || themePanoramaById.value[themeId] || themePanoramaLoadingById.value[themeId]) return
  themePanoramaLoadingById.value = { ...themePanoramaLoadingById.value, [themeId]: true }
  themePanoramaErrorById.value = { ...themePanoramaErrorById.value, [themeId]: '' }
  try {
    const response = await getThemePanorama(themeId)
    themePanoramaById.value = { ...themePanoramaById.value, [themeId]: response.data || null }
  } catch (err) {
    themePanoramaErrorById.value = {
      ...themePanoramaErrorById.value,
      [themeId]: err?.message || '主题概念加载失败',
    }
  } finally {
    themePanoramaLoadingById.value = { ...themePanoramaLoadingById.value, [themeId]: false }
  }
}

function relatedItemsSectionTitle(pane) {
  if (pane.kind === 'article') return '文章概念线索'
  if (pane.kind === 'asset' && pane.entity?.target_type === 'kfc_theme') return '主题下的概念'
  if (pane.kind === 'asset' && pane.entity?.target_type === 'concept') return '概念关联来源'
  return '关联资产'
}

function openRelatedPreview(item, parentPane, options = {}) {
  if (item.article) {
    openArticlePreview(item.article, parentPane.entity || {}, null, options)
    return
  }
  if (item.entity?.target_type === 'concept' && conceptRegistryEntryId(item.entity)) {
    const relatedSourceItems = isThemeAssetPane(parentPane)
      ? themeConceptItems(parentPane.entity || {})
      : previewRelatedItems(parentPane)
    const relatedConcepts = relatedSourceItems
      .filter((related) => related.entity?.target_type === 'concept')
      .map((related) => related.entity)
    openPreviewPane(conceptDetailPreviewPane(item.entity, {
      title: parentPane.title,
      typeLabel: parentPane.pathLabel || parentPane.typeLabel,
      relationLabel: relatedItemsSectionTitle(parentPane),
      contextLabel: `${parentPane.title || parentPane.pathLabel || '来源'} / ${cluster.value?.title || '主题簇根节点'}`,
      relatedConcepts,
    }), null, options)
    return
  }
  openCandidatePreview(item.entity, null, options)
}

function closeCandidateDrawer() {
  selectedCandidate.value = null
}

function listOrMissing(items, missing) {
  return items?.length ? items.join(', ') : missing
}

function linkedItemsLabel(items, missing) {
  if (!items?.length) return missing
  return items
    .slice(0, 8)
    .map((item) => item.title || item.name || item.target_title || item.entry_id || item.theme_id || item.project_id || item.id)
    .filter(Boolean)
    .join('，') || missing
}

function compactProvenanceSourceLabel(item) {
  if (item?.association_type === 'derived') return '来自已关联主题'
  if (item?.association_type === 'project_basket') return '当前项目概念篮'
  if (item?.link_record || item?.association_type === 'formal') return '已有正式关联记录'
  return item?.source_kind || 'local_asset_index'
}

function compactProvenanceChips(item) {
  return [
    `状态 ${candidateStatusLabel(item)}`,
    `来源 ${compactProvenanceSourceLabel(item)}`,
    item?.confidence_hint ? `相关度 ${item.confidence_hint}` : '',
    ...candidateMetricBadges(item).slice(0, 2),
  ].filter(Boolean).slice(0, 4)
}

function projectAssetSummaryLabel(summary) {
  const entries = [
    ['主题簇', summary.topic_cluster_count],
    ['证据', summary.evidence_count],
    ['概念', summary.concept_count],
    ['主题', summary.theme_count],
    ['审核快照', summary.review_snapshot_count],
  ].filter(([, value]) => value !== undefined)
  return entries.map(([label, value]) => `${label}: ${value || 0}`).join('；') || '暂无项目资产统计。'
}

function wikiIntakeHref(article) {
  const candidateId = article?.candidate_id || article?.source_id || ''
  return candidateId ? `/workspace/wiki-intake?candidate=${candidateId}` : '/workspace/wiki-intake'
}

function articleReasons(article, group) {
  if (article?.belongs_to_cluster_reason?.length) return article.belongs_to_cluster_reason
  const reasons = [
    `formal wiki_topic link: ${group.topic_id}`,
    'article topic_id matched linked wiki topic',
  ]
  const conceptLabels = articleConceptLabels(article)
  if (conceptLabels.length) {
    reasons.push(`top concepts overlap: ${conceptLabels.slice(0, 5).join(', ')}`)
  }
  return reasons
}

function leadTypeLabel(value) {
  const map = {
    concept_lead: '概念线索',
    evidence_slice: '证据片段',
  }
  return map[value] || value || 'Lead'
}

function promotionStatusLabel(value) {
  const map = {
    pending: '待处理',
    linked: '已关联',
    materialized_concept: '已沉淀',
    candidate_created: '旧候选',
    added_to_project_evidence: '已入证据',
    ignored: '已忽略',
    deprecated: '已废弃',
    unlinked: '已解除',
  }
  return map[value] || value || '待处理'
}

function processingStatusLabel(value) {
  const map = {
    pending: '待处理',
    pending_review: '待审查',
    needs_revision: '需修正',
    reviewed: '已审',
    confirmed: '已确认',
    rejected: '已拒绝',
    linked: '已关联',
    materialized_concept: '已沉淀',
    ignored: '已忽略',
    review_quote: '引文已标记',
    replace_quote: '引文待替换',
  }
  return map[value] || promotionStatusLabel(value)
}

function candidateCardTypeLabel(card = {}) {
  const map = {
    concept_lead: '概念线索',
    evidence_lead: '证据线索',
    relation_candidate: '关系候选',
  }
  return map[card.candidate_type] || card.candidate_type || '候选'
}

function promotionResultLabel(item = {}) {
  const map = {
    linked: '已关联到',
    materialized_concept: '已沉淀为概念',
    candidate_created: '已创建旧候选',
    added_to_project_evidence: '已作为项目证据',
    ignored: '已忽略',
    deprecated: '已标记为错误 / 废弃',
    unlinked: '已解除关联',
  }
  return map[item.review_status] || promotionStatusLabel(item.review_status)
}

function changeActionLabel(action) {
  const map = {
    create_concept_from_lead: '新增概念',
    link_lead_to_existing_concept: '新增关系',
    add_lead_as_project_evidence: '新增项目证据',
    ignore_lead: '忽略素材',
    unlink_concept_relation: '解除绑定',
    deprecate_concept: '废弃资产',
    update_concept: '编辑资产',
  }
  return map[action] || action || '变更'
}

function promotionConceptId(item = {}) {
  return item.concept?.concept_id || item.materialized_concept?.concept_id || item.target?.target_id || ''
}

function promotionConceptRoute(item = {}) {
  const conceptId = promotionConceptId(item)
  return conceptId && String(conceptId).startsWith('canon_') ? `/workspace/entry/${conceptId}` : ''
}

function promotionTargetLabel(item = {}) {
  if (item.target?.target_label) return item.target.target_label
  if (item.materialized_concept?.canonical_name) return item.materialized_concept.canonical_name
  if (item.target?.evidence_item_id) return item.target.evidence_item_id
  if (item.target?.target_id) return item.target.target_id
  return ''
}

function formatPercent(value) {
  if (typeof value !== 'number') return value || 'unknown'
  return `${Math.round(value * 100)}%`
}

function promotionActionKey(item) {
  return item?.promotion_id || ''
}

function processingActionKey(item) {
  return item?.candidate_id || ''
}

function isProcessingActionPending(item) {
  return Boolean(promotionActionPending.value[processingActionKey(item)])
}

function setProcessingActionPending(item, pending) {
  const key = processingActionKey(item)
  const next = { ...promotionActionPending.value }
  if (pending) next[key] = true
  else delete next[key]
  promotionActionPending.value = next
}

function isPromotionActionPending(item) {
  return Boolean(promotionActionPending.value[promotionActionKey(item)])
}

function setPromotionActionPending(item, pending) {
  const key = promotionActionKey(item)
  const next = { ...promotionActionPending.value }
  if (pending) next[key] = true
  else delete next[key]
  promotionActionPending.value = next
}

function promotionActionError(item) {
  return promotionActionErrors.value[promotionActionKey(item)] || ''
}

function setPromotionActionError(item, message) {
  promotionActionErrors.value = {
    ...promotionActionErrors.value,
    [promotionActionKey(item)]: message,
  }
}

function clearPromotionActionError(item) {
  const key = promotionActionKey(item)
  if (!promotionActionErrors.value[key]) return
  const next = { ...promotionActionErrors.value }
  delete next[key]
  promotionActionErrors.value = next
}

function promotionSourceFromArticle(article = {}, group = {}) {
  return {
    source_article_id: article.candidate_id || article.source_id || article.target_id || article.title || '',
    source_markdown_path: article.markdown_path || article.raw_article_path || '',
    source_content_hash: article.content_hash || article.source_content_hash || '',
    source_title: article.title || article.target_title || '',
    source_url: article.source_url || '',
    linked_wiki_topic: group.topic_id || article.topic_id || '',
    linked_research_project: currentResearchProjectDetail.value?.id || '',
  }
}

function slicePayloadFromArticle(article = {}, group = {}, sliceType = 'concept_lead') {
  const topConcept = articleConceptLeads(article)[0]
  const source = promotionSourceFromArticle(article, group)
  const title = sliceType === 'concept_lead'
    ? (topConcept?.title || article.title || article.target_title || '概念线索')
    : (article.title || article.target_title || '证据片段')
  const summary = sliceType === 'concept_lead'
    ? (topConcept?.summary || article.digest_summary || article.summary || article.title || '')
    : (article.digest_summary || article.summary || article.title || '')
  return {
    slice_type: sliceType,
    title,
    summary,
    source_quote: summary || title,
    source_span: {},
    ...source,
    create_promotion: true,
    created_from: `topic_cluster_detail.article_card.${sliceType}`,
  }
}

function slicePayloadFromArticleConceptLead(article = {}, title = '') {
  const source = promotionSourceFromArticle(article, article)
  const conceptSummary = articleConceptSummary(article, title)
  const summary = conceptSummary || article.digest_summary || article.summary || article.title || ''
  return {
    slice_type: 'concept_lead',
    title: title || article.title || '概念线索',
    summary: summary || title,
    source_quote: summary || title || article.title || '',
    source_span: {},
    ...source,
    create_promotion: true,
    created_from: 'topic_cluster_detail.article_concept_lead_card',
  }
}

function isArticleConceptLeadInBasket(article = {}, title = '') {
  const sourceArticleId = promotionSourceFromArticle(article, article).source_article_id
  return promotionBasketItems.value.some((item) => (
    item.lead_type === 'concept_lead'
    && item.title === title
    && item.source?.source_article_id === sourceArticleId
    && item.review_status !== 'ignored'
  ))
}

function articleConceptLeadPromotion(article = {}, title = '') {
  const sourceArticleId = promotionSourceFromArticle(article, article).source_article_id
  return promotionBasketItems.value.find((item) => (
    item.lead_type === 'concept_lead'
    && item.title === title
    && item.source?.source_article_id === sourceArticleId
  )) || null
}

function articleConceptLeadStatusLabel(article = {}, title = '') {
  const pending = isArticleConceptLeadPending(article, title)
  if (pending) return '已加入加工篮'
  const promotion = articleConceptLeadPromotion(article, title)
  if (!promotion) return '未处理'
  const status = promotion.review_status
  if (status === 'linked') return '已关联已有概念'
  if (status === 'materialized_concept') return '已沉淀为新概念'
  if (status === 'ignored') return '已忽略'
  if (status === 'candidate_created') return '已匹配'
  return '已加入加工篮'
}

function articleConceptLeadStatusClass(article = {}, title = '') {
  const label = articleConceptLeadStatusLabel(article, title)
  if (label.includes('忽略')) return 'lead-status-chip--muted'
  if (label.includes('关联') || label.includes('沉淀')) return 'lead-status-chip--done'
  if (label.includes('匹配') || label.includes('加入')) return 'lead-status-chip--working'
  return 'lead-status-chip--new'
}

function articleConceptLeadRecommendedAction(article = {}, title = '') {
  const status = articleConceptLeadStatusLabel(article, title)
  if (status === '未处理') return '匹配已有概念'
  if (status === '已加入加工篮' || status === '已匹配') return '关联已有概念 / 沉淀为新概念'
  if (status === '已关联已有概念') return '打开概念工作台'
  if (status === '已沉淀为新概念') return '审查概念邻域'
  return '保留处理记录'
}

function articleConceptLeadMatchedConceptLabel(article = {}, title = '') {
  const promotion = articleConceptLeadPromotion(article, title)
  if (!promotion) return ''
  const direct = promotion.materialized_concept?.canonical_name
    || promotion.target?.target_label
    || promotion.target?.registry_entry_label
  if (direct) return direct
  return promotionMatchHints(promotion)[0]?.label || ''
}

async function loadPromotionBasket() {
  if (!cluster.value?.cluster_id && !route.params.clusterId) return
  promotionBasketLoading.value = true
  promotionBasketError.value = ''
  try {
    const response = await getTopicClusterPromotionBasket(cluster.value?.cluster_id || route.params.clusterId)
    promotionBasket.value = response?.data || { counts: {}, items: [] }
    const changes = await getTopicClusterPromotionChanges(cluster.value?.cluster_id || route.params.clusterId, { limit: 8 })
    promotionChanges.value = changes?.data || { items: [] }
  } catch (err) {
    promotionBasket.value = { counts: {}, items: [] }
    promotionChanges.value = { items: [] }
    promotionBasketError.value = err?.message || 'KFC 加工篮加载失败'
  } finally {
    promotionBasketLoading.value = false
  }
}

async function addArticleSliceToPromotionBasket(article, group = {}, sliceType = 'concept_lead') {
  if (!cluster.value?.cluster_id || !article) return
  const key = articleSliceKey(article, sliceType)
  articleSlicePending.value = { ...articleSlicePending.value, [key]: true }
  actionError.value = ''
  try {
    await createTopicClusterMaterialSlice(cluster.value.cluster_id, slicePayloadFromArticle(article, group, sliceType))
    await loadPromotionBasket()
    openPromotionBasketPane(null, { secondary: true })
  } catch (err) {
    actionError.value = err?.message || '加入 KFC 加工篮失败'
  } finally {
    const next = { ...articleSlicePending.value }
    delete next[key]
    articleSlicePending.value = next
  }
}

async function addArticleConceptLeadToPromotionBasket(article = {}, title = '') {
  if (!cluster.value?.cluster_id || !article || !title) return
  const key = articleConceptLeadKey(article, title)
  articleSlicePending.value = { ...articleSlicePending.value, [key]: true }
  actionError.value = ''
  try {
    await createTopicClusterMaterialSlice(cluster.value.cluster_id, slicePayloadFromArticleConceptLead(article, title))
    await loadPromotionBasket()
    openPromotionBasketPane(null, { secondary: true })
  } catch (err) {
    actionError.value = err?.message || '加入 KFC 加工篮失败'
  } finally {
    const next = { ...articleSlicePending.value }
    delete next[key]
    articleSlicePending.value = next
  }
}

async function applyPromotionAction(item, payload) {
  if (!cluster.value?.cluster_id || !item?.promotion_id) return
  clearPromotionActionError(item)
  setPromotionActionPending(item, true)
  try {
    await applyLeadPromotionAction(cluster.value.cluster_id, item.promotion_id, payload)
    await loadPromotionBasket()
    openPromotionBasketPane(null, { secondary: true })
  } catch (err) {
    setPromotionActionError(item, err?.message || '加工篮操作失败')
  } finally {
    setPromotionActionPending(item, false)
  }
}

async function applyProcessingPromotionAction(card, article, payload) {
  if (!cluster.value?.cluster_id || !card?.candidate_id) return
  setProcessingActionPending(card, true)
  try {
    await applyLeadPromotionAction(cluster.value.cluster_id, card.candidate_id, payload)
    await loadPromotionBasket()
    await loadArticleProcessingReview(article)
  } catch (err) {
    actionError.value = err?.message || '文章加工审查操作失败'
  } finally {
    setProcessingActionPending(card, false)
  }
}

async function applyProcessingRelationAction(card, article, payload) {
  if (!cluster.value?.cluster_id || !card?.candidate_id) return
  setProcessingActionPending(card, true)
  try {
    await applyRelationCandidateAction(cluster.value.cluster_id, card.candidate_id, payload)
    await loadArticleProcessingReview(article)
  } catch (err) {
    actionError.value = err?.message || '关系候选审查失败'
  } finally {
    setProcessingActionPending(card, false)
  }
}

function switchProcessingCandidateMatch(card, alternative, article) {
  const conceptId = alternative?.concept_id || alternative?.entry_id || alternative?.target_id
  if (!conceptId) return
  applyProcessingPromotionAction(card, article, {
    action: 'switch_registry_match',
    target: {
      registry_entry_id: conceptId,
      registry_entry_label: alternative.concept_name || alternative.label || conceptId,
    },
    note: alternative.reason || '人工从文章加工摘要切换匹配概念。',
  })
}

function reviewProcessingQuote(card, quoteStatus, article) {
  applyProcessingPromotionAction(card, article, {
    action: 'review_quote',
    quote_status: quoteStatus,
    note: `文章加工摘要标记引文: ${quoteStatus}`,
  })
}

function requestBetterProcessingQuote(card, article) {
  applyProcessingPromotionAction(card, article, {
    action: 'replace_quote',
    note: '文章加工摘要请求替换为更强引文。',
  })
}

function confirmRelationCandidate(card, article) {
  applyProcessingRelationAction(card, article, {
    action: 'confirm',
    relation_type: card.relation_type,
    note: '人工确认关系候选。',
  })
}

function changeRelationCandidateType(card, article) {
  const nextType = window.prompt?.('Relation type', card.relation_type || 'related_to')
  if (!nextType) return
  applyProcessingRelationAction(card, article, {
    action: 'change_relation_type',
    relation_type: nextType.trim(),
    note: '人工修正 relation_type。',
  })
}

function rejectRelationCandidate(card, article) {
  applyProcessingRelationAction(card, article, {
    action: 'reject',
    relation_type: card.relation_type,
    note: '人工拒绝关系候选。',
  })
}

function linkPromotionToExistingRegistry(item) {
  const registryEntryId = window.prompt?.('Registry Entry ID', item.target?.target_id || '')
  if (!registryEntryId) return
  applyPromotionAction(item, {
    action: 'link_existing_registry_entry',
    target: {
      registry_entry_id: registryEntryId.trim(),
      registry_entry_label: item.title,
    },
    note: '人工从 KFC 加工篮关联已有注册表条目。',
  })
}

function depositPromotionAsNewConcept(item) {
  applyPromotionAction(item, {
    action: 'deposit_as_new_concept',
    concept: {
      label: item.title,
      definition: item.summary || item.source_quote || '',
      aliases: [],
    },
    created_by: 'human',
    note: '从 KFC 加工篮沉淀为可用概念资产。',
  })
}

function addPromotionAsProjectEvidence(item) {
  if (!currentResearchProjectDetail.value?.id) return
  applyPromotionAction(item, {
    action: 'add_as_project_evidence',
    target: { research_project_id: currentResearchProjectDetail.value.id },
    evidence: {
      title: item.title,
      claim: item.summary || item.source_quote || item.title,
      evidence_type: 'article_slice',
      note: '来自 Wiki 粗加工后的 Material Slice。',
    },
  })
}

async function batchAddGroupAsProjectEvidence(group) {
  if (!currentResearchProjectDetail.value?.id) return
  const items = group.items.filter((item) => item.review_status === 'pending')
  if (!items.length) return
  if (!window.confirm?.(`将 ${items.length} 条素材批量加入当前项目证据？`)) return
  for (const item of items) {
    await applyPromotionAction(item, {
      action: 'add_as_project_evidence',
      target: { research_project_id: currentResearchProjectDetail.value.id },
      evidence: {
        title: item.title,
        claim: item.summary || item.source_quote || item.title,
        evidence_type: 'article_slice',
        note: '来自 KFC 加工篮批量证据处理。',
      },
    })
  }
}

function ignoreLeadPromotion(item) {
  const reason = window.prompt?.('忽略原因', '不进入当前 KFC 加工链路') || '不进入当前 KFC 加工链路'
  applyPromotionAction(item, { action: 'ignore', reason })
}

async function batchIgnoreGroup(group) {
  const items = group.items.filter((item) => item.review_status === 'pending')
  if (!items.length) return
  if (!window.confirm?.(`批量忽略 ${items.length} 条待处理素材？`)) return
  for (const item of items) {
    await applyPromotionAction(item, {
      action: 'ignore',
      reason: '批量处理：不进入当前 KFC 加工链路。',
    })
  }
}

function deprecatePromotionConcept(item) {
  const reason = window.prompt?.('标记错误 / 废弃原因', '自动沉淀结果需要治理修正') || '自动沉淀结果需要治理修正'
  applyPromotionAction(item, { action: 'deprecate_materialized_concept', reason })
}

function unlinkPromotionTarget(item) {
  applyPromotionAction(item, {
    action: 'unlink_promotion_target',
    target_type: item.review_status === 'materialized_concept' ? 'topic_cluster' : 'concept_registry_entry',
    target_id: item.review_status === 'materialized_concept' ? (item.linked_topic_cluster || cluster.value?.cluster_id) : item.target?.target_id,
  })
}

async function loadDetail() {
  const clusterId = route.params.clusterId
  loading.value = true
  assetIndexLoading.value = true
  error.value = ''
  assetIndexError.value = ''
  try {
    const response = await getTopicCluster(clusterId, { includeCounts: true, includeArticles: true })
    const data = response.data || {}
    cluster.value = data.cluster || null
    linksByType.value = data.links_by_type || { wiki_topic: [], kfc_theme: [], research_project: [] }
    warnings.value = data.warnings || []
    expandedTopicIds.value = new Set()
    await loadPromotionBasket()
    try {
      const assetResponse = await getTopicClusterAssetIndex(clusterId)
      assetIndex.value = assetResponse.data || null
    } catch (assetErr) {
      assetIndex.value = null
      assetIndexError.value = assetErr?.message || '资产索引加载失败'
    }
  } catch (err) {
    cluster.value = null
    linksByType.value = { wiki_topic: [], kfc_theme: [], research_project: [] }
    assetIndex.value = null
    error.value = err?.message || '主题簇 加载失败'
  } finally {
    loading.value = false
    assetIndexLoading.value = false
  }
}

async function refreshCurrentResearchProjectDetail() {
  const current = readCurrentResearchProject()
  currentResearchProject.value = current
  currentResearchProjectDetail.value = current
  if (!current?.id) return
  try {
    const response = await getResearchProject(current.id)
    const project = response?.data || null
    currentResearchProjectDetail.value = project || null
  } catch {
    currentResearchProjectDetail.value = null
  }
}

async function linkCurrentProjectToCluster() {
  if (!currentResearchProjectDetail.value?.id || !cluster.value?.cluster_id || currentProjectLinked.value) return
  linkingCurrentProject.value = true
  actionError.value = ''
  const previousProject = currentResearchProjectDetail.value
  const previousCurrentProject = currentResearchProject.value
  const projectCandidate = [...candidateResearchProjects.value, ...formalResearchProjects.value]
    .find((item) => item.target_id === previousProject.id)
  const previousOverride = projectCandidate ? relationshipOverrides.value[candidateKey(projectCandidate)] : undefined
  try {
    const project = currentResearchProjectDetail.value
    const next = [
      ...(project.linked_topic_clusters || []),
      {
        cluster_id: cluster.value.cluster_id,
        title: cluster.value.title,
        article_count: cluster.value.article_count || 0,
        wiki_topic_count: cluster.value.counts?.wiki_topics || 0,
        theme_count: cluster.value.counts?.kfc_themes || 0,
        concept_count: assetIndex.value?.counts?.candidate_concept_count || 0,
        rationale: '人工从 主题簇 详情页关联到当前研究项目。',
        linked_by: 'human',
        linked_from: 'topic_cluster_detail',
        linked_at: new Date().toISOString(),
      },
    ]
    const optimisticProject = { ...project, linked_topic_clusters: next }
    currentResearchProjectDetail.value = optimisticProject
    currentResearchProject.value = optimisticProject
    setCurrentResearchProject(optimisticProject)
    if (projectCandidate) {
      setRelationshipOverride(projectCandidate, {
        relation_state: 'linked',
        association_type: 'formal',
        confirmation_status: 'confirmed',
        status: 'accepted',
        promotion_supported: false,
        supported_actions: ['view_detail', 'open_project', 'unlink_project'],
      })
    }
    const response = await updateResearchProject(project.id, { linked_topic_clusters: next })
    currentResearchProjectDetail.value = response?.data || currentResearchProjectDetail.value
    if (response?.data) setCurrentResearchProject(response.data)
  } catch (err) {
    currentResearchProjectDetail.value = previousProject
    currentResearchProject.value = previousCurrentProject
    if (previousProject) setCurrentResearchProject(previousProject)
    if (projectCandidate) restoreRelationshipOverride(projectCandidate, previousOverride)
    actionError.value = err?.message || '关联当前研究项目失败'
  } finally {
    linkingCurrentProject.value = false
  }
}

async function addConceptToCurrentProject(item) {
  if (!currentResearchProjectDetail.value?.id || !item?.target_id) return
  actionError.value = ''
  clearCardActionError(item)
  setActionPending(item, true)
  const previousProject = currentResearchProjectDetail.value
  const previousStatus = candidateLocalStatuses.value[candidateKey(item)]
  try {
    const project = currentResearchProjectDetail.value
    const existing = project.linked_concepts || []
    if (existing.some((concept) => (concept.entry_id || concept.concept_id || concept.id) === item.target_id)) {
      setCandidateStatus(item, 'selected_for_current_project')
      return
    }
    const next = [
      ...existing,
      {
        entry_id: item.target_id,
        title: item.target_title,
        concept_type: item.concept_type || item.display_type || '概念',
        source: 'topic_cluster_candidate_review',
        cluster_id: cluster.value?.cluster_id || '',
        rationale: item.match_reason || '人工从 主题簇 候选审阅加入当前项目概念篮。',
        linked_by: 'human',
        linked_at: new Date().toISOString(),
      },
    ]
    currentResearchProjectDetail.value = { ...project, linked_concepts: next }
    setCandidateStatus(item, 'selected_for_current_project')
    const response = await updateResearchProject(project.id, { linked_concepts: next })
    currentResearchProjectDetail.value = response?.data || currentResearchProjectDetail.value
    if (response?.data) setCurrentResearchProject(response.data)
    setCandidateStatus(item, 'selected_for_current_project')
  } catch (err) {
    currentResearchProjectDetail.value = previousProject
    restoreCandidateStatus(item, previousStatus)
    setCardActionError(item, err?.message || '加入当前项目概念篮失败')
    actionError.value = err?.message || '加入当前项目概念篮失败'
  } finally {
    setActionPending(item, false)
  }
}

async function removeConceptFromCurrentProject(item) {
  if (!currentResearchProjectDetail.value?.id || !item?.target_id) return
  actionError.value = ''
  clearCardActionError(item)
  setActionPending(item, true)
  const previousProject = currentResearchProjectDetail.value
  const previousStatus = candidateLocalStatuses.value[candidateKey(item)]
  const nextStatus = item.association_type === 'derived' ? 'derived_from_linked_theme' : 'candidate'
  try {
    const project = currentResearchProjectDetail.value
    const next = (project.linked_concepts || []).filter((concept) => (
      (concept.entry_id || concept.concept_id || concept.id || concept.target_id) !== item.target_id
    ))
    currentResearchProjectDetail.value = { ...project, linked_concepts: next }
    setCandidateStatus(item, nextStatus)
    const response = await updateResearchProject(project.id, { linked_concepts: next })
    currentResearchProjectDetail.value = response?.data || currentResearchProjectDetail.value
    if (response?.data) setCurrentResearchProject(response.data)
    setCandidateStatus(item, nextStatus)
  } catch (err) {
    currentResearchProjectDetail.value = previousProject
    restoreCandidateStatus(item, previousStatus)
    setCardActionError(item, err?.message || '移出当前项目概念篮失败')
    actionError.value = err?.message || '移出当前项目概念篮失败'
  } finally {
    setActionPending(item, false)
  }
}

async function addArticleToCurrentEvidenceBasket(article) {
  if (!currentResearchProjectDetail.value?.id || !article) return
  actionError.value = ''
  try {
    const project = currentResearchProjectDetail.value
    const evidenceId = `ev_article_${article.candidate_id || article.source_id || Date.now()}`
    const existing = project.evidence_items || []
    if (existing.some((item) => item.evidence_id === evidenceId || item.source_candidate_id === article.candidate_id)) return
    const next = [
      ...existing,
      {
        evidence_id: evidenceId,
        title: article.title || article.candidate_id || '文章证据',
        evidence_type: 'article',
        status: 'candidate',
        source_candidate_id: article.candidate_id || article.source_id || '',
        source_url: article.source_url || '',
        markdown_path: article.markdown_path || '',
        verified_digest_md_path: article.verified_digest_md_path || '',
        cluster_id: cluster.value?.cluster_id || '',
        claim: article.digest_summary || article.title || '',
        origin: 'topic_cluster_article_review',
        added_by: 'human',
        added_at: new Date().toISOString(),
      },
    ]
    const response = await updateResearchProject(project.id, { evidence_items: next })
    currentResearchProjectDetail.value = response?.data || currentResearchProjectDetail.value
    if (response?.data) setCurrentResearchProject(response.data)
  } catch (err) {
    actionError.value = err?.message || '加入当前项目证据篮失败'
  }
}

function startEdit() {
  actionError.value = ''
  activeTab.value = 'diagnostics'
  clusterForm.value = {
    title: cluster.value?.title || '',
    description: cluster.value?.description || '',
    status: cluster.value?.status || 'candidate',
    strategic_relevance: cluster.value?.strategic_relevance || 'unknown',
  }
  editingCluster.value = true
}

async function saveCluster() {
  actionError.value = ''
  if (!clusterForm.value.title.trim()) {
    actionError.value = '标题不能为空'
    return
  }
  savingCluster.value = true
  try {
    const response = await updateTopicCluster(cluster.value.cluster_id, {
      title: clusterForm.value.title.trim(),
      description: clusterForm.value.description,
      status: clusterForm.value.status,
      strategic_relevance: clusterForm.value.strategic_relevance,
    })
    cluster.value = response.data?.cluster || cluster.value
    editingCluster.value = false
  } catch (err) {
    actionError.value = err?.message || '保存失败'
  } finally {
    savingCluster.value = false
  }
}

async function saveLink() {
  actionError.value = ''
  linkWarning.value = ''
  if (!linkForm.value.target_id.trim()) {
    actionError.value = 'Target ID 不能为空'
    return
  }
  savingLink.value = true
  try {
    const response = await createTopicClusterLink(cluster.value.cluster_id, {
      ...linkForm.value,
      target_id: linkForm.value.target_id.trim(),
      target_title: linkForm.value.target_title.trim(),
    })
    const warning = response.data?.warnings?.[0]
    if (warning) linkWarning.value = '已保存，但 target 未解析；Phase 1 允许手工引用。'
    showAddLink.value = false
    linkForm.value = {
      target_type: 'wiki_topic',
      target_id: '',
      target_title: '',
      role: 'candidate',
      status: 'candidate',
      rationale: '',
    }
    const createdLink = response.data?.link
    if (createdLink?.target_type) {
      linksByType.value = {
        ...linksByType.value,
        [createdLink.target_type]: [
          ...(linksByType.value[createdLink.target_type] || []),
          createdLink,
        ],
      }
    }
  } catch (err) {
    actionError.value = err?.message || '保存 Link 失败'
  } finally {
    savingLink.value = false
  }
}

function confidenceToNumber(value) {
  const map = { high: 0.85, medium: 0.6, low: 0.35 }
  return map[value] ?? null
}

async function promoteCandidate(item) {
  actionError.value = ''
  linkWarning.value = ''
  if (!item?.promotion_supported) return
  if (!item?.target_id) {
    setCardActionError(item, '缺少 target_id，无法建立关联。')
    return
  }
  clearCardActionError(item)
  setActionPending(item, true)
  savingLink.value = true
  const previousOverride = relationshipOverrides.value[candidateKey(item)]
  const previousStatus = candidateLocalStatuses.value[candidateKey(item)]
  const optimisticLinkId = item.link_id || item.link_record?.link_id || `local_${candidateKey(item).replace(/[^a-zA-Z0-9_-]/g, '_')}`
  setRelationshipOverride(item, {
    relation_state: 'linked',
    association_type: 'formal',
    confirmation_status: 'confirmed',
    status: 'accepted',
    link_id: optimisticLinkId,
    link_record: {
      ...(item.link_record || {}),
      link_id: optimisticLinkId,
      link_status: 'accepted',
      created_at: new Date().toISOString(),
      source_path: 'topic_cluster_links',
    },
    promotion_supported: false,
    supported_actions: [
      ...(item.supported_actions || []),
      item.target_type === 'kfc_theme' ? 'unlink_theme' : 'unlink_project',
    ],
  })
  setCandidateStatus(item, 'linked')
  try {
    const response = await createTopicClusterLink(cluster.value.cluster_id, {
      target_type: item.target_type,
      target_id: item.target_id,
      target_title: item.target_title || item.target_id,
      role: 'supporting',
      status: 'accepted',
      source: 'candidate_promotion',
      confidence: confidenceToNumber(item.confidence_hint),
      rationale: `Promoted from 主题簇 candidate. ${item.match_reason || ''}`.trim(),
      review_decision: {
        decision: 'accepted',
        reviewed_by: 'human',
        reviewed_at: new Date().toISOString(),
        reason: item.match_reason || '',
        candidate_source_kind: item.source_kind || '',
        candidate_source_path: item.source_path_display || item.source_path || '',
        candidate_confidence_hint: item.confidence_hint || '',
      },
    })
    const createdLink = response?.data?.link || {}
    const linkId = createdLink.link_id || optimisticLinkId
    setRelationshipOverride(item, {
      relation_state: 'linked',
      association_type: 'formal',
      confirmation_status: 'confirmed',
      status: createdLink.status || 'accepted',
      link_id: linkId,
      link_record: {
        ...(item.link_record || {}),
        link_id: linkId,
        link_status: createdLink.status || 'accepted',
        created_at: createdLink.created_at || new Date().toISOString(),
        source_path: createdLink.source_path || 'topic_cluster_links',
      },
      promotion_supported: false,
      supported_actions: [
        ...(item.supported_actions || []),
        item.target_type === 'kfc_theme' ? 'unlink_theme' : 'unlink_project',
      ],
    })
  } catch (err) {
    restoreRelationshipOverride(item, previousOverride)
    restoreCandidateStatus(item, previousStatus)
    setCardActionError(item, err?.message || '提升候选关联失败')
    actionError.value = err?.message || '提升候选关联失败'
  } finally {
    setActionPending(item, false)
    savingLink.value = false
  }
}

async function removeFormalAssetLink(item) {
  const linkId = item?.link_record?.link_id || item?.link_id
  if (!linkId) return
  actionError.value = ''
  clearCardActionError(item)
  setActionPending(item, true)
  const previousOverride = relationshipOverrides.value[candidateKey(item)]
  const previousStatus = candidateLocalStatuses.value[candidateKey(item)]
  setRelationshipOverride(item, {
    relation_state: 'candidate',
    association_type: 'candidate',
    confirmation_status: 'unconfirmed',
    status: 'candidate',
    link_id: '',
    link_record: null,
    promotion_supported: item.target_type !== 'concept',
    supported_actions: (item.supported_actions || []).filter((action) => !['unlink_theme', 'unlink_project'].includes(action)),
  })
  setCandidateStatus(item, 'candidate')
  try {
    await deleteTopicClusterLink(linkId)
  } catch (err) {
    restoreRelationshipOverride(item, previousOverride)
    restoreCandidateStatus(item, previousStatus)
    setCardActionError(item, err?.message || '取消关联失败')
    actionError.value = err?.message || '取消关联失败'
  } finally {
    setActionPending(item, false)
  }
}

async function patchLink(link, patch) {
  actionError.value = ''
  try {
    const response = await updateTopicClusterLink(link.link_id, patch)
    const updated = response?.data?.link || { ...link, ...patch }
    linksByType.value = Object.fromEntries(
      Object.entries(linksByType.value).map(([type, links]) => [
        type,
        links.map((existing) => (existing.link_id === link.link_id ? { ...existing, ...updated } : existing)),
      ]),
    )
  } catch (err) {
    actionError.value = err?.message || '更新 Link 失败'
  }
}

async function removeLink(link) {
  const ok = window.confirm('删除这条关联记录？只会移除主题簇关联关系记录，不会删除主题、研究项目、概念或 Markdown。')
  if (!ok) return
  actionError.value = ''
  try {
    await deleteTopicClusterLink(link.link_id)
    linksByType.value = Object.fromEntries(
      Object.entries(linksByType.value).map(([type, links]) => [
        type,
        links.filter((existing) => existing.link_id !== link.link_id),
      ]),
    )
  } catch (err) {
    actionError.value = err?.message || '移除 Link 失败'
  }
}

onMounted(() => {
  loadDetail()
  refreshCurrentResearchProjectDetail()
  unsubscribeResearchProject = subscribeCurrentResearchProject(() => {
    refreshCurrentResearchProjectDetail()
  })
})
onBeforeUnmount(() => {
  unsubscribeResearchProject()
  if (justOpenedPaneTimer) window.clearTimeout(justOpenedPaneTimer)
})
watch(() => route.params.clusterId, loadDetail)
</script>

<style scoped>
.topic-detail {
  --asset-topic-accent: #4b6f9f;
  --asset-topic-accent-strong: #2f5f97;
  --asset-topic-surface: #eef4f8;
  --asset-topic-surface-strong: #e3edf5;
  --asset-article-accent: #b49365;
  --asset-article-surface: #fffdf8;
  --asset-article-border: #eadcc4;
  --asset-concept-accent: #24785f;
  --asset-project-accent: #6d5ca8;
  --asset-theme-accent: #9a5b00;
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
  color: var(--kfc-text, var(--text-primary));
}
.back-link {
  width: fit-content;
  color: var(--accent-primary-hover);
  text-decoration: none;
  font-weight: 700;
  font-size: 13px;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.current-project-panel {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-left: 4px solid var(--state-current-project);
  border-radius: 8px;
  background: var(--kfc-surface, var(--bg-surface));
  padding: 14px;
}
.current-project-panel h2 {
  margin: 4px 0;
  font-size: 18px;
}
.current-project-panel p {
  margin: 0;
  color: var(--text-secondary);
}
.current-project-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.section-badge {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--accent-primary-hover);
}
h1 {
  margin: 4px 0 8px;
  font-size: 28px;
}
.detail-head p {
  margin: 0;
  max-width: 780px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.meta-line span {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 12px;
  color: var(--text-muted);
}
.edit-btn {
  margin-top: 12px;
}
.count-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(90px, 1fr));
  gap: 8px;
}
.count-grid div {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 12px;
  background: var(--kfc-surface, var(--bg-surface));
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.count-grid strong {
  font-size: 22px;
}
.count-grid span {
  font-size: 12px;
  color: var(--text-muted);
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.cluster-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 520px);
  gap: 16px;
  align-items: start;
}
.cluster-workbench.stack-two {
  grid-template-columns: minmax(320px, 0.42fr) minmax(0, 1.58fr);
}
.cluster-main-column {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.notes-panel,
.articles-panel,
.state-card,
.asset-index-panel,
.asset-group,
.warning-bar {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 16px;
  background: var(--kfc-surface, var(--bg-surface));
}
.edit-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 16px;
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
}
.panel-head h3 {
  margin: 0;
  font-size: 15px;
}
.asset-index-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.asset-index-panel h2 {
  margin: 0;
  font-size: 20px;
}
.asset-index-panel .panel-head p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.asset-head-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  min-width: 260px;
}
.asset-head-meta span {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 999px;
  padding: 4px 9px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  white-space: nowrap;
}
.asset-head-meta strong {
  color: var(--text-primary);
  font-size: 14px;
}
.readonly-pill {
  border: 1px solid var(--state-readonly);
  border-radius: 999px;
  padding: 4px 9px;
  background: rgba(100, 116, 139, 0.12);
  color: var(--state-readonly);
  font-size: 12px;
  font-weight: 700;
}
.formal-empty-panel {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
}
.formal-empty-panel h3 {
  margin: 0 0 4px;
  font-size: 13px;
}
.formal-empty-panel p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
}
.formal-empty-panel strong {
  display: block;
  margin-top: 8px;
  color: var(--accent-primary-hover);
  font-size: 13px;
}
.asset-note {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
}
.asset-note {
  margin: 0;
}
.review-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: flex-end;
  border-bottom: 1px solid var(--kfc-border, var(--border-default));
  padding: 4px 0 0 6px;
}
.review-tabs button {
  position: relative;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  padding: 10px 15px 11px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 44px;
}
.review-tabs .tab-count {
  min-width: 22px;
  border-radius: 999px;
  padding: 1px 7px;
  background: rgba(139, 94, 60, 0.12);
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 11px;
  line-height: 1.5;
  text-align: center;
}
.review-tabs .tab-count::before {
  content: attr(data-count);
}
.review-tabs button.active {
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
}
.review-tabs button.active::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 3px;
  border-radius: 999px 999px 0 0;
  background: var(--kfc-primary, var(--accent-primary));
}
.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tab-headline h3,
.review-conclusion h3 {
  margin: 0 0 4px;
  font-size: 16px;
}
.tab-headline p,
.review-conclusion p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.review-conclusion {
  border: 1px solid rgba(183, 121, 31, 0.35);
  border-radius: 8px;
  padding: 14px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(220px, 0.8fr);
  gap: 16px;
}
.next-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 13px;
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.overview-grid.two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.candidate-kpis,
.clue-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.clue-summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.candidate-kpis div,
.clue-summary-grid div {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 10px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.candidate-kpis strong,
.clue-summary-grid strong {
  font-size: 19px;
}
.candidate-kpis span,
.clue-summary-grid span,
.clue-summary-grid small {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}
.overview-asset-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.overview-asset-list article {
  border-top: 1px solid var(--border-muted);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.overview-asset-list span {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.review-tasks ol {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.folded-section {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 10px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
}
.folded-section summary {
  cursor: pointer;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 800;
}
.folded-section .asset-list {
  margin-top: 10px;
}
.kfc-review-panel,
.candidate-review-section,
.candidate-card-grid,
.candidate-review-card,
.candidate-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.relationship-summary-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(92px, 1fr));
  gap: 8px;
}
.relationship-summary-strip div {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 9px 10px;
  background: linear-gradient(180deg, var(--kfc-surface, var(--bg-surface)) 0%, var(--kfc-surface-muted, var(--bg-surface-2)) 100%);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.relationship-summary-strip strong {
  color: var(--text-primary);
  font-size: 18px;
}
.relationship-summary-strip span {
  color: var(--text-muted);
  font-size: 12px;
}
.candidate-review-section {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 14px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
}
.candidate-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.candidate-section-head h3,
.candidate-review-card h4,
.drawer-head h2,
.drawer-section h3 {
  margin: 0;
}
.candidate-section-head p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.candidate-section-head strong,
.status-chip {
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 4px 8px;
  color: var(--text-muted);
  font-size: 12px;
  white-space: nowrap;
}
.candidate-filters {
  display: grid;
  grid-template-columns: repeat(3, minmax(160px, 1fr));
  gap: 10px;
}
.candidate-filters label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--text-muted);
  font-size: 12px;
}
.candidate-filters select {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 7px 9px;
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--text-primary);
}
.candidate-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
.candidate-review-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 12px 12px 12px 15px;
  background: var(--kfc-surface, var(--bg-surface));
  box-shadow: 0 1px 2px rgba(63, 52, 42, 0.05);
}
.candidate-review-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--state-readonly);
}
.candidate-review-card.state-linked {
  border-color: rgba(47, 111, 159, 0.35);
  background: var(--kfc-surface, var(--bg-surface));
}
.candidate-review-card.state-linked::before,
.status-chip.status-linked {
  background: var(--state-linked);
}
.candidate-review-card.state-candidate::before,
.status-chip.status-candidate {
  background: var(--state-candidate);
}
.candidate-review-card.state-ignored {
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  opacity: 0.72;
}
.candidate-review-card.state-ignored::before,
.status-chip.status-ignored {
  background: var(--state-ignored);
}
.status-chip.status-pending {
  background: var(--state-candidate);
}
.status-chip.status-candidate_created {
  background: var(--asset-concept-accent);
}
.status-chip.status-added_to_project_evidence {
  background: var(--state-current-project);
}
.candidate-review-card.state-derived_from_linked_theme::before,
.status-chip.status-derived_from_linked_theme {
  background: var(--state-derived);
}
.candidate-review-card.state-selected_for_current_project::before,
.status-chip.status-selected_for_current_project {
  background: var(--state-current-project);
}
.candidate-review-card.selected {
  border-color: var(--kfc-primary, var(--accent-primary));
  box-shadow: 0 0 0 2px rgba(47, 111, 159, 0.12);
}
.candidate-review-card.selected::after {
  content: "右侧查看中";
  position: absolute;
  top: 10px;
  right: 10px;
  border: 1px solid rgba(47, 111, 159, 0.2);
  border-radius: 999px;
  padding: 2px 7px;
  background: #f0f6ff;
  color: var(--kfc-primary, var(--accent-primary));
  font-size: 11px;
  font-weight: 700;
}
.candidate-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.candidate-card-head h4 {
  font-size: 14px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.candidate-card-head span {
  color: var(--text-muted);
  font-size: 12px;
}
.candidate-card-head .status-chip {
  color: #ffffff;
  border-color: transparent;
  font-weight: 800;
  line-height: 1.2;
}
.candidate-summary,
.candidate-reason {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
}
.candidate-summary {
  color: var(--text-primary);
}
.candidate-reason span {
  color: var(--text-primary);
  font-weight: 800;
}
.candidate-metrics,
.candidate-source-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.candidate-metrics span {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 999px;
  padding: 2px 7px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}
.candidate-source-line {
  justify-content: space-between;
  border-top: 1px solid var(--border-muted);
  padding-top: 8px;
  color: var(--text-muted);
  font-size: 12px;
}
.candidate-source-line small {
  max-width: 64%;
  overflow-wrap: anywhere;
  text-align: right;
}
.candidate-actions {
  flex-direction: row;
  flex-wrap: wrap;
}
.clickable-card {
  cursor: pointer;
}
.clickable-card:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}
.status-chip {
  color: #ffffff;
  border-color: transparent;
}
.card-action-error {
  margin: 0;
  font-size: 12px;
}
.exploration-stack {
  position: sticky;
  top: 14px;
  max-height: calc(100vh - 28px);
  overflow: auto;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #fbf4e6;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.exploration-stack-head,
.preview-pane-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.exploration-stack-head h2,
.preview-pane-head h3,
.preview-section h4 {
  margin: 0;
}
.exploration-stack-head h2 {
  font-size: 17px;
}
.exploration-stack-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.exploration-path {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}
.exploration-path span {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 6px;
  padding: 3px 8px;
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
}
.exploration-path span:not(:first-child)::before {
  content: "> ";
  color: var(--text-muted);
}
.pane-context-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 6px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-secondary);
  font-size: 12px;
}
.pane-context-strip span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--kfc-surface, var(--bg-surface));
}
.pane-context-strip span:not(:last-child)::after {
  content: ">";
  color: var(--text-muted);
}
.pane-context-strip small {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}
.empty-preview {
  border: 1px dashed var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 18px;
  background: var(--kfc-surface, var(--bg-surface));
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.empty-preview span,
.preview-pane-head p,
.preview-section p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}
.exploration-pane-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 12px;
}
.preview-pane {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: var(--kfc-surface, var(--bg-surface));
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.preview-pane--just-opened {
  box-shadow: 0 0 0 2px rgba(75, 111, 159, 0.34), 0 12px 28px rgba(35, 49, 70, 0.12);
}
.preview-pane--wiki-topic {
  border-color: rgba(75, 111, 159, 0.42);
  background:
    linear-gradient(90deg, rgba(75, 111, 159, 0.14), transparent 22px),
    var(--asset-topic-surface);
  box-shadow: inset 4px 0 0 var(--asset-topic-accent);
}
.preview-pane--article {
  border-color: var(--asset-article-border);
  background: var(--asset-article-surface);
}
.preview-pane--wiki-intake {
  grid-column: 1 / -1;
  min-height: clamp(620px, calc(100vh - 90px), 940px);
  max-height: none;
  overflow: hidden;
}
.preview-pane.pinned {
  border-color: var(--kfc-primary, var(--accent-primary));
  border-top: 4px solid var(--kfc-primary, var(--accent-primary));
  box-shadow: 0 0 0 2px var(--accent-soft);
}
.preview-type {
  display: inline-flex;
  width: fit-content;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--accent-primary-hover);
  font-size: 11px;
  font-weight: 800;
}
.asset-badge,
.preview-type {
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.asset-badge {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border: 1px solid var(--border-default);
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 10px;
  font-weight: 850;
  line-height: 1.2;
}
.asset-badge--wiki-topic {
  border-color: rgba(75, 111, 159, 0.34);
  background: rgba(75, 111, 159, 0.12);
  color: var(--asset-topic-accent-strong);
}
.asset-badge--article {
  border-color: rgba(180, 147, 101, 0.36);
  background: rgba(180, 147, 101, 0.12);
  color: #775a31;
}
.preview-pane-head h3 {
  margin-top: 6px;
  font-size: 16px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.preview-pane-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.preview-section {
  border-top: 1px solid var(--border-muted);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.preview-section--topic-summary {
  border: 1px solid rgba(75, 111, 159, 0.18);
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.48);
}
.preview-section--topic-articles {
  gap: 6px;
}
.preview-section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.preview-section h4 {
  font-size: 13px;
}
.article-brief-section p {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.article-concept-leads-section {
  gap: 6px;
}
.preview-inline-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.preview-dl {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}
.preview-dl dt {
  color: var(--text-muted);
  font-size: 11px;
}
.preview-dl dd {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.article-processing-review {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.processing-summary-strip,
.processing-risk-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.processing-summary-strip span,
.processing-risk-line span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 8px;
  background: var(--bg-muted);
  color: var(--text-secondary);
  font-size: 12px;
}
.article-completion-panel,
.processing-review-group,
.review-trail-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.72);
}
.article-completion-panel {
  display: grid;
  gap: 8px;
}
.article-completion-panel > div:first-child {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.article-completion-panel strong {
  font-size: 15px;
}
.article-completion-panel small {
  color: var(--text-muted);
}
.processing-review-workspace {
  display: grid;
  gap: 10px;
}
.processing-review-group {
  display: grid;
  gap: 10px;
}
.processing-review-group > summary {
  cursor: pointer;
  list-style: none;
}
.processing-review-group > summary::-webkit-details-marker {
  display: none;
}
.processing-group-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.processing-group-head h5,
.processing-group-head p {
  margin: 0;
}
.processing-group-head h5 {
  font-size: 14px;
}
.processing-group-head p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}
.processing-group-head > span {
  align-self: flex-start;
  border: 1px solid var(--border-muted);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--text-muted);
  font-size: 12px;
}
.processing-batch-bar,
.batch-result-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.processing-batch-bar > span,
.batch-result-line {
  color: var(--text-muted);
  font-size: 12px;
}
.batch-result-line small {
  border: 1px solid var(--border-muted);
  border-radius: 999px;
  padding: 2px 7px;
}
.processing-batch-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(75, 111, 159, 0.26);
  border-radius: 999px;
  padding: 4px 9px;
  background: rgba(75, 111, 159, 0.08);
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.processing-batch-button--danger {
  border-color: rgba(203, 59, 43, 0.28);
  background: rgba(203, 59, 43, 0.08);
  color: var(--state-danger);
}
.processing-group-empty {
  color: var(--text-muted);
  font-size: 12px;
}
.processing-candidate-card {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  display: grid;
  gap: 8px;
}
.processing-card-select {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}
.processing-card-select input {
  width: 16px;
  height: 16px;
}
.relation-readable-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(75, 111, 159, 0.24);
  border-radius: 8px;
  padding: 8px;
  background: rgba(75, 111, 159, 0.08);
}
.relation-readable-card strong {
  overflow-wrap: anywhere;
}
.relation-readable-card span {
  border: 1px solid var(--border-muted);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--accent-primary-hover);
  font-size: 12px;
  font-weight: 800;
}
.compact-dl {
  margin: 10px 0;
}
.registry-alternative-area {
  display: grid;
  gap: 8px;
  margin: 10px 0;
}
.alternative-match-btn {
  display: grid;
  gap: 2px;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface-2);
  color: var(--text-primary);
  cursor: pointer;
}
.alternative-match-btn:hover:not(:disabled) {
  border-color: var(--accent-primary);
  background: var(--bg-muted);
}
.alternative-match-btn small {
  color: var(--text-secondary);
  line-height: 1.45;
}
.review-trail-panel summary {
  cursor: pointer;
  font-weight: 800;
}
.review-trail-item {
  border-top: 1px solid var(--border-muted);
  padding: 8px 0;
}
.review-trail-item > div:first-child {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.review-trail-item span,
.review-trail-item small {
  color: var(--text-muted);
  font-size: 12px;
}
.compact-provenance-section {
  gap: 6px;
}
.provenance-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.provenance-strip span {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 999px;
  padding: 3px 8px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 800;
}
.provenance-details {
  color: var(--text-secondary);
  font-size: 12px;
}
.provenance-details summary {
  width: fit-content;
  cursor: pointer;
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-weight: 800;
}
.provenance-details .preview-dl {
  margin-top: 8px;
}
.preview-related-row {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  cursor: pointer;
  text-align: left;
}
.preview-related-row--paper {
  border-color: var(--asset-article-border);
  background: var(--asset-article-surface);
  box-shadow: inset 3px 0 0 rgba(180, 147, 101, 0.42);
}
.preview-related-row span {
  color: var(--text-muted);
  font-size: 12px;
}
.preview-related-row.selected {
  border-color: var(--kfc-primary, var(--accent-primary));
  background: #f0f6ff;
  box-shadow: inset 3px 0 0 var(--kfc-primary, var(--accent-primary));
}
.theme-concepts-section {
  min-height: 0;
}
.theme-concept-list {
  max-height: 360px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 2px;
}
.theme-concept-row {
  min-height: 48px;
}
.intake-preview-section {
  flex: 1 1 auto;
  min-height: clamp(360px, calc(100vh - 230px), 720px);
  overflow: hidden;
}
.intake-preview-section :deep(.embedded-intake-panel) {
  height: 100%;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
}
.promotion-basket-section {
  gap: 10px;
}
.promotion-basket-summary,
.promotion-source-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.promotion-basket-summary span {
  border: 1px solid var(--border-muted);
  border-radius: 999px;
  padding: 3px 7px;
  background: rgba(255, 255, 255, 0.55);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
}
.promotion-changes-panel {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.45);
}
.promotion-changes-panel summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}
.promotion-changes-panel ul {
  margin: 8px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  list-style: none;
}
.promotion-changes-panel li {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--text-secondary);
  font-size: 12px;
}
.promotion-basket-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.promotion-task-queue {
  gap: 16px;
}
.promotion-basket-group {
  border: 1px solid var(--border-muted);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.58);
}
.promotion-group-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.promotion-group-head h4 {
  margin: 0 0 4px;
  font-size: 14px;
}
.promotion-group-head p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}
.promotion-group-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}
.promotion-basket-card {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.62);
}
.promotion-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.promotion-card-head h4 {
  margin: 4px 0 0;
}
.promotion-basket-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}
.promotion-source-line span {
  font-weight: 800;
}
.promotion-source-line small {
  color: var(--text-muted);
  overflow-wrap: anywhere;
}
.promotion-quality-line,
.promotion-recommendation-line,
.promotion-result-panel {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 6px;
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  padding: 7px;
  background: rgba(255, 255, 255, 0.45);
  color: var(--text-secondary);
  font-size: 12px;
}
.promotion-recommendation-line {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #9a3412;
}
.promotion-recommendation-line span {
  font-weight: 800;
}
.promotion-match-hints {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 7px;
  background: #f0fdf4;
  color: #166534;
  font-size: 12px;
}
.promotion-match-hints strong {
  margin-right: 2px;
}
.promotion-match-hints span {
  border-radius: 999px;
  padding: 2px 6px;
  background: #dcfce7;
}
.lead-status-chip,
.lead-recommendation,
.lead-linked-concept {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}
.lead-status-chip--new {
  background: #f5f3ff;
  color: #6d28d9;
}
.lead-status-chip--working {
  background: #fff7ed;
  color: #9a3412;
}
.lead-status-chip--done {
  background: #eff6ff;
  color: #1d4ed8;
}
.lead-status-chip--muted {
  background: #f3f4f6;
  color: #4b5563;
}
.lead-recommendation {
  border: 1px solid #fed7aa;
  background: #fffbeb;
  color: #92400e;
}
.lead-linked-concept {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}
.promotion-result-panel strong {
  color: var(--text-primary);
}
.promotion-trace-details {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  padding: 7px;
  background: rgba(255, 255, 255, 0.45);
}
.promotion-trace-details summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}
.preview-link-row,
.group-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.preview-link-row a,
.inline-action {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 5px 8px;
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
.candidate-drawer {
  position: fixed;
  inset: 0;
  z-index: 30;
  pointer-events: none;
}
.candidate-drawer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
  pointer-events: auto;
}
.candidate-drawer-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: min(520px, 100vw);
  height: 100%;
  overflow: auto;
  background: var(--kfc-surface, var(--bg-surface));
  border-left: 1px solid var(--kfc-border, var(--border-default));
  padding: 18px;
  box-shadow: -12px 0 24px rgba(15, 23, 42, 0.14);
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.drawer-head p,
.drawer-section p,
.drawer-muted {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}
.drawer-section {
  border-top: 1px solid var(--border-default);
  padding-top: 12px;
}
.drawer-section h3 {
  font-size: 14px;
}
.drawer-dl {
  margin: 8px 0 0;
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}
.drawer-dl dt {
  color: var(--text-muted);
  font-size: 11px;
}
.drawer-dl dd {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.drawer-actions {
  border-top: 1px solid var(--border-default);
  padding-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.asset-index-grid {
  display: grid;
  grid-template-columns: minmax(210px, 0.8fr) minmax(280px, 1.2fr) minmax(280px, 1.2fr);
  gap: 12px;
}
.asset-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.asset-group h3 {
  margin: 0;
  font-size: 15px;
}
.asset-group dl {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.asset-group dt {
  color: var(--text-muted);
  font-size: 12px;
}
.asset-group dd {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  overflow-wrap: anywhere;
}
.asset-warning,
.asset-error {
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
}
.asset-warning {
  border: 1px solid rgba(192, 86, 33, 0.32);
  background: rgba(192, 86, 33, 0.08);
  color: var(--state-warning);
}
.asset-error {
  border: 1px solid #f2b8b5;
  background: #fff1f0;
  color: #8c1d18;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
.edit-panel label,
.link-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.edit-panel input,
.edit-panel select,
.edit-panel textarea,
.link-form input,
.link-form select,
.link-form textarea {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font: inherit;
}
.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.primary-btn,
.secondary-btn {
  border-radius: 8px;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
}
.primary-btn {
  border: 1px solid var(--kfc-primary, var(--accent-primary));
  background: var(--kfc-primary, var(--accent-primary));
  color: white;
}
.primary-btn:hover:not(:disabled) {
  border-color: var(--kfc-primary-hover, var(--accent-primary-hover));
  background: var(--kfc-primary-hover, var(--accent-primary-hover));
}
.secondary-btn {
  border: 1px solid var(--kfc-border, var(--border-default));
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--text-secondary);
}
.secondary-btn:hover:not(:disabled) {
  border-color: var(--kfc-primary, var(--accent-primary));
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
}
.danger-btn {
  border-color: var(--state-danger);
  color: var(--state-danger);
}
.inline-error {
  color: #8c1d18;
  font-size: 13px;
}
.inline-warning {
  color: var(--state-warning);
  font-size: 13px;
}
.articles-panel h3,
.notes-panel h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.topic-article-group {
  padding: 14px 0 4px;
}
.topic-article-group:first-of-type {
  padding-top: 4px;
}
.group-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.group-head > div:not(.group-actions) {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.topic-folder-card {
  position: relative;
  border: 1px solid rgba(75, 111, 159, 0.28);
  border-radius: 8px;
  padding: 13px 14px 13px 18px;
  background:
    linear-gradient(90deg, rgba(75, 111, 159, 0.12), rgba(75, 111, 159, 0.02) 58%, rgba(255, 255, 255, 0.18)),
    var(--asset-topic-surface);
  box-shadow: 0 1px 0 rgba(75, 111, 159, 0.12);
}
.topic-folder-card__rail {
  position: absolute;
  inset: 10px auto 10px 0;
  width: 5px;
  border-radius: 0 999px 999px 0;
  background: var(--asset-topic-accent);
}
.topic-folder-card::before {
  content: "";
  position: absolute;
  top: -7px;
  left: 18px;
  width: 92px;
  height: 8px;
  border: 1px solid rgba(75, 111, 159, 0.24);
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
  background: var(--asset-topic-surface-strong);
}
.topic-folder-card--toggle {
  cursor: pointer;
}
.topic-folder-card--toggle:hover,
.topic-folder-card--toggle:focus-visible {
  border-color: rgba(75, 111, 159, 0.48);
  box-shadow:
    0 1px 0 rgba(75, 111, 159, 0.12),
    0 0 0 2px rgba(75, 111, 159, 0.12);
  outline: none;
}
.topic-folder-card__header {
  min-width: 0;
  max-width: min(680px, 100%);
}
.topic-folder-card__title {
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.topic-folder-card__meta {
  color: var(--text-muted);
  font-size: 12px;
}
.topic-folder-card__count {
  display: inline-flex;
  align-items: center;
  border: 1px solid rgba(75, 111, 159, 0.34);
  border-radius: 999px;
  padding: 4px 9px;
  background: rgba(75, 111, 159, 0.12);
  color: var(--asset-topic-accent-strong);
  font-size: 12px;
  font-weight: 850;
  white-space: nowrap;
}
.topic-folder-card__actions {
  align-items: center;
  justify-content: flex-end;
}
.topic-folder-card--toggle:hover .topic-folder-card__title {
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
}
.group-head span,
.empty-note,
.topic-article-group small {
  color: var(--text-muted);
  font-size: 12px;
}
.group-head .asset-badge--wiki-topic {
  color: var(--asset-topic-accent-strong);
  font-size: 10px;
}
.group-head .topic-folder-card__count {
  color: var(--asset-topic-accent-strong);
  font-size: 12px;
}
.topic-article-group ul {
  margin: 10px 0 0 12px;
  padding: 0;
  list-style: none;
  color: var(--text-secondary);
  line-height: 1.7;
}
.article-paper-list {
  display: grid;
  gap: 8px;
  border-left: 1px dashed rgba(180, 147, 101, 0.34);
  padding-left: 12px;
}
.topic-article-group li {
  margin-bottom: 0;
}
.article-card {
  border: 1px solid var(--asset-article-border);
  border-left: 3px solid rgba(180, 147, 101, 0.62);
  border-radius: 8px;
  padding: 9px 10px;
  background: var(--asset-article-surface);
  display: flex;
  flex-direction: column;
  gap: 7px;
  box-shadow: 0 1px 0 rgba(80, 59, 31, 0.05);
  transition: border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease;
}
.article-card:hover,
.article-card:focus {
  border-color: rgba(180, 147, 101, 0.78);
  background: #fffaf0;
  box-shadow: 0 6px 16px rgba(80, 59, 31, 0.08);
  outline: none;
}
.article-card strong {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
}
.article-paper-card__meta {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 3px 8px;
  align-items: center;
}
.article-paper-card__meta strong {
  overflow-wrap: anywhere;
}
.article-paper-card__meta small {
  grid-column: 2;
}
.article-concepts,
.article-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.article-concepts span {
  border: 1px solid rgba(36, 120, 95, 0.18);
  border-radius: 999px;
  padding: 1px 6px;
  background: rgba(36, 120, 95, 0.06);
  color: #477464;
  font-size: 10px;
}
.article-reasons {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.article-reasons--compact {
  border: 1px solid rgba(180, 147, 101, 0.18);
  border-radius: 7px;
  padding: 6px 8px;
  background: rgba(180, 147, 101, 0.05);
}
.article-reasons span {
  color: #775a31;
  font-size: 12px;
  font-weight: 800;
}
.article-reasons details {
  margin-top: 1px;
}
.article-reasons summary {
  width: fit-content;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 800;
}
.article-reasons details small {
  display: block;
  margin-top: 2px;
}
.article-actions a,
.article-action-link,
.article-action-btn {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 4px 7px;
  background: var(--kfc-surface, var(--bg-surface));
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
.article-action-btn:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}
.article-lead-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.concept-lead-row {
  min-height: 64px;
  padding: 8px 10px;
}
.article-lead-main {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.article-lead-main strong,
.article-lead-main span {
  display: block;
}
.article-lead-main strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.article-lead-main span,
.article-lead-main small {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.article-lead-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.promotion-empty-state {
  border: 1px dashed var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 14px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
}
.promotion-empty-state strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.promotion-empty-state p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.inline-link {
  color: var(--kfc-primary-hover, var(--accent-primary-hover));
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}
.notes-panel p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.followup-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.followup-list article {
  border: 1px solid var(--kfc-border, var(--border-default));
  border-radius: 8px;
  padding: 10px;
  background: var(--kfc-surface-muted, var(--bg-surface-2));
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.followup-list span,
.followup-list small {
  color: var(--text-muted);
  font-size: 12px;
}
.warning-bar {
  border-color: rgba(192, 86, 33, 0.32);
  background: rgba(192, 86, 33, 0.08);
  color: var(--state-warning);
}
.error-card {
  border-color: #f2b8b5;
  background: #fff1f0;
  color: #8c1d18;
}
.error-title {
  font-weight: 800;
  margin-bottom: 4px;
}
@media (max-width: 920px) {
  .detail-head,
  .detail-grid,
  .cluster-workbench,
  .cluster-workbench.stack-two,
  .asset-index-grid,
  .overview-grid,
  .overview-grid.two-col,
  .review-conclusion,
  .clue-summary-grid,
  .relationship-summary-strip,
  .candidate-filters {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
  .count-grid,
  .candidate-kpis {
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .panel-head,
  .asset-head-meta {
    align-items: flex-start;
    justify-content: flex-start;
    min-width: 0;
  }
  .exploration-stack {
    position: static;
    max-height: none;
  }
  .preview-pane--wiki-intake {
    grid-column: auto;
    min-height: 0;
    max-height: none;
  }
  .intake-preview-section :deep(.embedded-intake-panel) {
    height: auto;
    max-height: none;
  }
  .exploration-pane-grid {
    grid-template-columns: 1fr;
  }
}
</style>
