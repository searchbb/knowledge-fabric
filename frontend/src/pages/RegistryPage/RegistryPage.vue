<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <button class="topbar-btn" @click="handleExport" title="下载全部注册表 JSON">
        <span class="icon">⬇</span><span class="label">导出</span>
      </button>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <main class="registry-main">
      <!-- Tab bar (horizontal, replacing sidebar tabs) -->
      <nav class="registry-tabs" aria-label="注册表子视图">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="registry-tab"
          :class="{ active: activeTab === tab.key }"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <section class="phase2-page">
        <div class="section-badge">{{ activeTabMeta.badge }}</div>
        <h2 class="section-title">{{ registryModeTitle }}</h2>
        <p class="section-copy">{{ registryModeSubtitle }}</p>

        <!-- Theme / Evolution / Review tabs -->
        <ThemeTab v-if="activeTab === 'themes'" />
        <EvolutionTab v-else-if="activeTab === 'evolution'" />
        <ReviewTab v-else-if="activeTab === 'review'" />

        <!-- Concepts tab (default, existing content below) -->
        <template v-else>

        <div v-if="registryContext.active" class="registry-context-banner">
          <div>
            <div class="context-kicker">{{ leadMatchingMode ? '概念线索处理工作台' : '来自文章概念线索' }}</div>
            <h3>{{ registryContext.query || '未命名线索' }}</h3>
            <p>
              当前任务：判断这条文章概念线索如何进入 KFC
              <template v-if="registryContext.clusterId"> · 主题簇: {{ registryContext.clusterId }}</template>
              <template v-if="registryContext.projectId"> · 当前研究项目: {{ registryContext.projectId }}</template>
            </p>
            <dl v-if="leadMatchingMode" class="context-grid">
              <div><dt>当前线索</dt><dd>{{ registryContext.query || '未命名线索' }}</dd></div>
              <div><dt>来源文章</dt><dd>{{ registryContext.articleId || '未携带 article_id' }}</dd></div>
              <div><dt>主题簇</dt><dd>{{ registryContext.clusterId || '未携带 cluster_id' }}</dd></div>
              <div><dt>当前研究项目</dt><dd>{{ registryContext.projectId || '未携带 project_id' }}</dd></div>
              <div><dt>自动匹配结果</dt><dd>{{ autoSelectionMessage || '等待用户选择匹配项' }}</dd></div>
              <div><dt>当前关联状态</dt><dd>{{ leadAssociationStatus }}</dd></div>
            </dl>
            <p v-if="autoSelectionMessage" class="context-selection">{{ autoSelectionMessage }}</p>
          </div>
          <div class="context-actions">
            <router-link
              v-if="registryContext.clusterId"
              class="btn-small"
              :to="`/workspace/topic-clusters/${registryContext.clusterId}`"
            >返回加工篮</router-link>
            <router-link
              v-if="selectedEntry"
              class="btn-primary compact"
              :to="conceptWorkbenchRoute(selectedEntry.entry_id)"
            >打开概念工作台</router-link>
          </div>
        </div>

        <section v-if="leadMatchingMode" class="lead-decision-workspace">
          <div class="decision-hero">
            <div>
              <div class="context-kicker">当前任务</div>
              <h3>你正在处理文章线索：{{ registryContext.query || '未命名线索' }}</h3>
              <p>
                系统建议关联到已有概念：
                <strong>{{ selectedEntry?.canonical_name || '等待选择候选概念' }}</strong>
              </p>
              <p class="decision-explain">{{ leadDecisionExplanation }}</p>
            </div>
            <div class="decision-status-card" :class="{ done: leadAssociationCompleted }">
              <span>{{ leadAssociationCompleted ? '已完成' : '待确认' }}</span>
              <strong>{{ leadAssociationCompleted ? `已关联到 ${selectedEntry?.canonical_name}` : leadAssociationStatus }}</strong>
              <small>{{ leadAssociationCompleted ? '下一步：打开工作台、返回加工篮，或继续处理下一条线索。' : '请确认、换一个概念、新建概念，或暂不处理。' }}</small>
            </div>
          </div>

          <div class="decision-grid">
            <section class="decision-card decision-actions-card">
              <div class="subsection-title">你需要做什么</div>
              <template v-if="leadAssociationCompleted">
                <div class="completion-callout">
                  <strong>已完成：该线索已关联到 {{ selectedEntry?.canonical_name }}</strong>
                  <span>这条 lead 的 promotion 状态已经写回，后续可以在概念工作台查看来源证据。</span>
                </div>
                <div class="action-row">
                  <router-link
                    v-if="selectedEntry"
                    class="btn-primary compact"
                    :to="conceptWorkbenchRoute(selectedEntry.entry_id)"
                  >打开概念工作台</router-link>
                  <router-link
                    v-if="registryContext.clusterId"
                    class="btn-small"
                    :to="`/workspace/topic-clusters/${registryContext.clusterId}`"
                  >返回加工篮</router-link>
                </div>
              </template>
              <template v-else>
                <div class="action-row vertical">
                  <button
                    class="btn-primary"
                    type="button"
                    :disabled="leadLinking || !canLinkLeadToSelected"
                    @click="handleLinkSelectedConcept"
                  >
                    {{ leadLinking ? '关联中...' : linkPrimaryLabel }}
                  </button>
                  <button class="btn-small" type="button" @click="focusSearchInput">换一个已有概念</button>
                  <button class="btn-small" type="button" @click="showCreateForm = true">沉淀为新概念</button>
                  <button class="btn-small" type="button" disabled>暂不处理 / 忽略线索</button>
                </div>
                <p class="mini-copy section-copy">如果当前页面没有 promotion_id，只能完成自动选中；请先从加工篮进入再直接关联。</p>
              </template>
              <p v-if="leadLinkMessage" class="request-note">{{ leadLinkMessage }}</p>
            </section>

            <section class="decision-card">
              <div class="subsection-title">为什么推荐它</div>
              <dl class="decision-dl">
                <div><dt>原文线索</dt><dd>{{ registryContext.query || '未命名线索' }}</dd></div>
                <div><dt>目标概念</dt><dd>{{ selectedEntry?.canonical_name || '尚未选择' }}</dd></div>
                <div><dt>概念定义</dt><dd>{{ selectedEntry?.description || '该概念暂未补充定义，建议关联后在工作台治理。' }}</dd></div>
                <div><dt>匹配理由</dt><dd>{{ leadMatchReason }}</dd></div>
                <div><dt>可能风险</dt><dd>{{ leadMatchRisk }}</dd></div>
              </dl>
            </section>

            <section class="decision-card">
              <div class="subsection-title">关联后 KFC 会增加什么</div>
              <ul class="bring-in-checklist">
                <li>这条 source quote 会进入 {{ selectedEntry?.canonical_name || '目标概念' }} 概念工作台。</li>
                <li>保留 article / slice / lead / promotion 追溯。</li>
                <li>{{ registryContext.clusterId ? `建立与 主题簇 ${registryContext.clusterId} 的上下文关联。` : '等待补充 主题簇 上下文。' }}</li>
                <li>{{ filteredCrossRelations.length }} 条跨文关系可继续审查。</li>
              </ul>
            </section>
          </div>
        </section>

        <!-- Error: show FIRST when the backend failed. The stats row and
             toolbar below display "0" / active buttons, so rendering them
             above the error card reads as "empty registry" instead of
             "we never reached the backend". Surface the diagnosis before
             the shell so the user isn't misled. -->
        <div v-if="registryStore.error" class="state-card error-card">
          <div class="card-title">加载失败</div>
          <div class="metric-line">{{ registryStore.error }}</div>
        </div>

        <!-- Loading -->
        <div v-else-if="registryStore.loading" class="state-card">
          <div class="card-title">正在加载注册表</div>
        </div>

        <!-- Stats row (only when not erroring/loading) -->
        <div v-else class="summary-grid">
          <article class="card">
            <div class="card-title">注册表条目</div>
            <div class="metric-value">{{ registryStore.total }}</div>
          </article>
          <article class="card">
            <div class="card-title">项目链接数</div>
            <div class="metric-value">{{ totalLinks }}</div>
          </article>
          <article class="card">
            <div class="card-title">覆盖类型</div>
            <div class="metric-value">{{ uniqueTypes }}</div>
          </article>
        </div>

        <!-- Toolbar + main layout — same gating as stats row, but
             using v-if (not v-else) since they are siblings of the
             error/loading/stats triplet above, not part of its v-if chain. -->
        <template v-if="!registryStore.error && !registryStore.loading">
        <!-- Search bar + create button -->
        <div class="toolbar">
          <input
            ref="searchInputRef"
            class="search-input"
            type="text"
            placeholder="搜索概念名 / 别名..."
            v-model="searchQuery"
            @input="handleSearch"
          />
          <button class="btn-small" @click="openSuggestPanel">项目推荐</button>
          <button class="btn-primary" @click="showCreateForm = true">新建条目</button>
        </div>

        <!-- Main layout -->
        <div class="registry-layout">
          <!-- Left: entry list -->
          <article class="card queue-card">
            <div class="card-header">
              <div class="card-title">
                {{ searchQuery ? '搜索结果' : '全部条目' }}
              </div>
              <div class="pill">{{ displayEntries.length }}</div>
            </div>

            <div v-if="!displayEntries.length" class="empty-state">
              {{ searchQuery ? '没有匹配的条目' : '注册表为空，使用"新建条目"或"项目推荐"来添加' }}
            </div>

            <div v-if="leadMatchingMode && matchingCandidateGroups.length" class="candidate-list grouped-candidate-list">
              <section v-for="group in matchingCandidateGroups" :key="group.key" class="candidate-group">
                <div class="candidate-group-title">{{ group.label }}</div>
                <button
                  v-for="entry in group.items"
                  :key="`${group.key}:${entry.entry_id}`"
                  type="button"
                  class="candidate-button"
                  :class="{ active: entry.entry_id === registryStore.selectedEntryId }"
                  @click="handleSelectEntry(entry.entry_id)"
                >
                  <div class="candidate-topline">
                    <span class="candidate-name">{{ entry.canonical_name }}</span>
                    <span class="candidate-status">{{ entry.source_links?.length || 0 }} 链接</span>
                    <span v-if="registryStore.crossRelationCounts[entry.entry_id]" class="xrel-badge">
                      {{ registryStore.crossRelationCounts[entry.entry_id] }} 条关系
                    </span>
                  </div>
                  <div class="candidate-meta">
                    {{ entry.concept_type }}
                    <template v-if="entry.aliases?.length"> · {{ entry.aliases.length }} 别名</template>
                  </div>
                </button>
              </section>
            </div>

            <div v-else class="candidate-list">
              <button
                v-for="entry in displayEntries"
                :key="entry.entry_id"
                type="button"
                class="candidate-button"
                :class="{ active: entry.entry_id === registryStore.selectedEntryId }"
                @click="handleSelectEntry(entry.entry_id)"
              >
                <div class="candidate-topline">
                  <span class="candidate-name">{{ entry.canonical_name }}</span>
                  <span class="candidate-status">{{ entry.source_links?.length || 0 }} 链接</span>
                  <span v-if="registryStore.crossRelationCounts[entry.entry_id]" class="xrel-badge">
                    {{ registryStore.crossRelationCounts[entry.entry_id] }} 条关系
                  </span>
                </div>
                <div class="candidate-meta">
                  {{ entry.concept_type }}
                  <template v-if="entry.aliases?.length"> · {{ entry.aliases.length }} 别名</template>
                </div>
              </button>
            </div>
          </article>

          <!-- Middle: detail panel -->
          <article class="card detail-card">
            <template v-if="selectedEntry">
              <div class="card-header">
                <div>
                  <div class="detail-kicker">Canonical Entry</div>
                  <h3 class="detail-title">{{ selectedEntry.canonical_name }}</h3>
                </div>
                <div class="detail-badges">
                  <span class="chip">{{ selectedEntry.concept_type }}</span>
                  <button
                    v-if="leadMatchingMode && !leadAssociationCompleted"
                    class="btn-primary compact"
                    type="button"
                    :disabled="leadLinking || !canLinkLeadToSelected"
                    @click="handleLinkSelectedConcept"
                  >
                    {{ leadLinking ? '关联中...' : linkPrimaryLabel }}
                  </button>
                  <span v-if="leadMatchingMode && leadAssociationCompleted" class="chip success">已完成关联</span>
                  <router-link
                    :to="conceptWorkbenchRoute(selectedEntry.entry_id)"
                    class="open-detail-btn"
                    title="打开完整概念工作台（保留当前线索上下文）"
                  >打开概念工作台 →</router-link>
                </div>
              </div>

              <section v-if="leadMatchingMode" class="matching-panel task-explanation-panel">
                <div class="subsection-title">目标概念摘要</div>
                <p class="section-copy mini-copy">
                  {{ selectedEntry.description || '该概念暂无定义。确认关联后，可以在概念工作台补充定义、别名和治理状态。' }}
                </p>
                <details class="advanced-filter-details system-explain-details">
                  <summary>查看系统解释：局部图谱与关系路径</summary>
                  <div class="local-graph">
                    <div class="graph-node graph-node--lead">当前文章线索<br />{{ registryContext.query || selectedEntry.canonical_name }}</div>
                    <div class="graph-node graph-node--concept">正式概念<br />{{ selectedEntry.canonical_name }}</div>
                    <div class="graph-node graph-node--article">来源文章<br />{{ registryContext.articleId || 'unknown' }}</div>
                  </div>
                  <ol class="path-list">
                    <li v-for="step in leadRelationPath" :key="step">{{ step }}</li>
                  </ol>
                  <div class="matching-candidate-actions">
                    <span v-for="entry in relationRecommendationEntries" :key="entry.entry_id">
                      {{ entry.canonical_name }} · 可作为后续关系审查候选
                    </span>
                    <span v-if="!relationRecommendationEntries.length">暂无其他推荐关系候选。</span>
                  </div>
                </details>
              </section>
              <p v-if="leadLinkMessage" class="context-selection">{{ leadLinkMessage }}</p>

              <div v-if="selectedEntry.description" class="detail-sections">
                <section class="detail-section">
                  <div class="subsection-title">描述</div>
                  <p class="section-copy mini-copy">{{ selectedEntry.description }}</p>
                </section>
              </div>

              <div class="detail-sections">
                <section class="detail-section">
                  <div class="subsection-title">别名</div>
                  <div class="chip-wrap" v-if="selectedEntry.aliases?.length">
                    <span v-for="alias in selectedEntry.aliases" :key="alias" class="chip soft">{{ alias }}</span>
                  </div>
                  <div v-else class="empty-note">暂无别名</div>
                </section>

                <section class="detail-section">
                  <div class="subsection-title">项目链接 ({{ selectedEntry.source_links?.length || 0 }})</div>
                  <div v-if="selectedEntry.source_links?.length" class="link-list">
                    <div v-for="link in selectedEntry.source_links" :key="link.project_id + link.concept_key" class="link-item">
                      <a
                        class="link-project link-clickable"
                        :href="buildSourceArticleGraphHref(link, { from: 'registry' })"
                        target="_blank"
                        :title="`新窗口打开阅读视图，定位到 ${link.concept_key}`"
                      >{{ link.project_name || link.project_id }} ↗</a>
                      <div class="link-concept">{{ link.concept_key }}</div>
                      <button class="btn-small btn-danger" @click="handleUnlink(link)">解绑</button>
                    </div>
                  </div>
                  <div v-else class="empty-note">尚未关联任何项目概念</div>
                </section>

                <!-- Block 3: Cross-article relations (L3) -->
                <section class="detail-section">
                  <div class="subsection-title">
                    跨文章关联
                    <span v-if="registryStore.crossRelations.length" class="pill small">{{ filteredCrossRelations.length }}</span>
                  </div>
                  <div v-if="registryStore.crossRelationsLoading" class="empty-note">加载中...</div>
                  <div v-else-if="filteredCrossRelations.length" class="xrel-list">
                    <CrossRelationCard
                      v-for="rel in filteredCrossRelations"
                      :key="rel.relation_id"
                      :relation="rel"
                      :conceptMap="conceptMap"
                      :currentEntryId="registryStore.selectedEntryId"
                      @navigate="handleNavigateConcept"
                      @review="handleReviewRelation"
                      @type-change="handleUpdateRelationType"
                      @delete="handleDeleteRelation"
                    />
                  </div>
                  <div v-else class="empty-note">暂无跨文章关联</div>
                </section>
              </div>

              <div class="action-row">
                <button class="btn-small" @click="startEdit">编辑</button>
                <button class="btn-small btn-danger" @click="handleDelete">删除</button>
              </div>
            </template>

            <div v-else class="empty-state">
              选择左侧条目查看详情，或使用搜索查找特定概念
            </div>
          </article>

          <!-- Right: action panel -->
          <article class="card action-card">
            <!-- Create form -->
            <template v-if="showCreateForm">
              <div class="card-title">新建条目</div>
              <div class="form-group">
                <label>名称</label>
                <input v-model="formData.canonical_name" class="form-input" placeholder="Canonical 概念名" />
              </div>
              <div class="form-group">
                <label>类型</label>
                <input v-model="formData.concept_type" class="form-input" placeholder="概念" />
              </div>
              <div class="form-group">
                <label>别名 (逗号分隔)</label>
                <input v-model="formData.aliasesRaw" class="form-input" placeholder="AI, 人工智能" />
              </div>
              <div class="form-group">
                <label>描述</label>
                <textarea v-model="formData.description" class="form-input" rows="3" placeholder="可选描述" />
              </div>
              <div class="action-row">
                <button class="btn-primary" @click="handleCreate" :disabled="registryStore.saving">
                  {{ registryStore.saving ? '保存中...' : '创建' }}
                </button>
                <button class="btn-small" @click="resetForm">取消</button>
              </div>
            </template>

            <!-- Edit form -->
            <template v-else-if="editMode && selectedEntry">
              <div class="card-title">编辑条目</div>
              <div class="form-group">
                <label>名称</label>
                <input v-model="editData.canonical_name" class="form-input" />
              </div>
              <div class="form-group">
                <label>类型</label>
                <input v-model="editData.concept_type" class="form-input" />
              </div>
              <div class="form-group">
                <label>别名 (逗号分隔)</label>
                <input v-model="editData.aliasesRaw" class="form-input" />
              </div>
              <div class="form-group">
                <label>描述</label>
                <textarea v-model="editData.description" class="form-input" rows="3" />
              </div>
              <div class="action-row">
                <button class="btn-primary" @click="handleEdit" :disabled="registryStore.saving">
                  {{ registryStore.saving ? '保存中...' : '保存' }}
                </button>
                <button class="btn-small" @click="editMode = false">取消</button>
              </div>
            </template>

            <!-- Suggest panel -->
            <template v-else-if="currentPanel === 'suggest'">
              <div class="card-header">
                <div class="card-title">从项目推荐</div>
                <button class="btn-small" @click="closeSuggestPanel">关闭</button>
              </div>
              <p class="section-copy mini-copy">选择一个项目，将其已确认概念推荐到全局注册表。</p>
              <div class="form-group">
                <label>项目 ID</label>
                <input v-model="suggestProjectId" class="form-input" placeholder="proj_xxxx" />
              </div>
              <button
                class="btn-primary"
                @click="handleSuggest"
                :disabled="registryStore.suggestLoading || !suggestProjectId"
              >
                {{ registryStore.suggestLoading ? '分析中...' : '生成推荐' }}
              </button>

              <template v-if="registryStore.suggestResult">
                <div class="suggest-summary">
                  <div class="metric-line">项目：{{ registryStore.suggestResult.project_name }}</div>
                  <div class="metric-line">已确认概念：{{ registryStore.suggestResult.total_accepted }}</div>
                  <div class="metric-line">新候选：{{ registryStore.suggestResult.new_candidates?.length || 0 }}</div>
                  <div class="metric-line">已匹配：{{ registryStore.suggestResult.existing_matches?.length || 0 }}</div>
                  <div class="metric-line">跨类型提示：{{ registryStore.suggestResult.cross_type_matches?.length || 0 }}</div>
                  <div class="metric-line">已链接：{{ registryStore.suggestResult.already_linked?.length || 0 }}</div>
                </div>

                <div v-if="registryStore.suggestResult.new_candidates?.length" class="suggest-section">
                  <div class="subsection-title">可注册 ({{ registryStore.suggestResult.new_candidates.length }})</div>
                  <div v-for="c in registryStore.suggestResult.new_candidates" :key="c.concept_key" class="suggest-item">
                    <span class="candidate-name">{{ c.display_name }}</span>
                    <span class="candidate-meta">{{ c.concept_type }}</span>
                    <button class="btn-small" @click="quickCreate(c)">注册</button>
                  </div>
                </div>

                <div v-if="registryStore.suggestResult.existing_matches?.length" class="suggest-section">
                  <div class="subsection-title">可链接 ({{ registryStore.suggestResult.existing_matches.length }})</div>
                  <div v-for="c in registryStore.suggestResult.existing_matches" :key="c.concept_key" class="suggest-item">
                    <span class="candidate-name">{{ c.display_name }}</span>
                    <span class="candidate-meta">→ {{ c.matched_canonical_name }}</span>
                    <button class="btn-small" @click="quickLink(c)">链接</button>
                  </div>
                </div>

                <div v-if="registryStore.suggestResult.cross_type_matches?.length" class="suggest-section">
                  <div class="subsection-title">跨类型提示 ({{ registryStore.suggestResult.cross_type_matches.length }})</div>
                  <div v-for="c in registryStore.suggestResult.cross_type_matches" :key="c.concept_key" class="suggest-item">
                    <span class="candidate-name">{{ c.display_name }}</span>
                    <span class="candidate-meta">{{ c.concept_type }} → {{ c.matched_canonical_name }} [{{ c.matched_concept_type }}]</span>
                    <button class="btn-small" @click="quickLinkCrossType(c)">链接为别名</button>
                  </div>
                </div>
              </template>
            </template>

            <template v-else-if="leadMatchingMode">
              <div class="card-title">下一步</div>
              <div class="processing-panel">
                <div v-if="leadAssociationCompleted" class="completion-callout">
                  <strong>已完成关联</strong>
                  <span>下一步：打开概念工作台、返回加工篮，或继续处理下一条线索。</span>
                </div>
                <dl class="preview-dl compact">
                  <div><dt>当前线索</dt><dd>{{ registryContext.query || '未命名线索' }}</dd></div>
                  <div><dt>匹配结果</dt><dd>{{ selectedEntry ? `已自动选中 ${selectedEntry.canonical_name}` : '尚未选中概念' }}</dd></div>
                  <div><dt>推荐动作</dt><dd>{{ leadAssociationCompleted ? '打开概念工作台或返回加工篮' : (selectedEntry ? '确认关联已有概念' : '先选择候选概念') }}</dd></div>
                  <div><dt>关联状态</dt><dd>{{ leadAssociationStatus }}</dd></div>
                </dl>
                <div class="bring-in-list">
                  <strong>关联后 KFC 会增加</strong>
                  <span>{{ filteredCrossRelations.length }} 条跨文关系待审</span>
                  <span>1 个来源材料片段</span>
                  <span>{{ registryContext.clusterId ? '1 个 主题簇 关联' : '待补充 主题簇' }}</span>
                </div>
                <div class="action-row vertical">
                  <button
                    v-if="!leadAssociationCompleted"
                    class="btn-primary"
                    type="button"
                    :disabled="leadLinking || !canLinkLeadToSelected"
                    @click="handleLinkSelectedConcept"
                  >
                    {{ leadLinking ? '关联中...' : linkPrimaryLabel }}
                  </button>
                  <router-link
                    v-if="leadAssociationCompleted && selectedEntry"
                    class="btn-primary compact"
                    :to="conceptWorkbenchRoute(selectedEntry.entry_id)"
                  >打开概念工作台</router-link>
                  <button class="btn-small" type="button" @click="showCreateForm = true">沉淀为新概念</button>
                  <button class="btn-small" type="button" @click="focusSearchInput">换一个已有概念</button>
                  <button class="btn-small" type="button" disabled>暂不处理 / 忽略线索</button>
                </div>
                <p v-if="leadLinkMessage" class="request-note">{{ leadLinkMessage }}</p>
                <details class="advanced-filter-details">
                  <summary>高级筛选</summary>
                  <div class="xfilter-section">
                    <div class="xfilter-label">关系类型 / 状态 / 置信度 / 排序</div>
                    <p class="section-copy mini-copy">高级筛选保留在折叠区，避免压过处理动作。</p>
                  </div>
                </details>
              </div>
            </template>

            <!-- Default: cross-relation filters + action info -->
            <template v-else>
              <!-- Cross-relation filter panel (when concept has relations) -->
              <template v-if="selectedEntry && registryStore.crossRelations.length">
                <div class="card-title">跨文章关联筛选</div>

                <!-- Summary bar -->
                <div class="xfilter-summary">
                  {{ filteredCrossRelations.length }} 条关系
                  <span v-if="xrelFilterState.reviewStatus !== 'all'" class="xfilter-active"> · 已筛选</span>
                </div>

                <!-- Status tabs -->
                <div class="xfilter-tabs">
                  <button v-for="s in xrelStatusOptions" :key="s.value"
                    class="xfilter-tab" :class="{ active: xrelFilterState.reviewStatus === s.value }"
                    @click="xrelFilterState.reviewStatus = s.value">
                    {{ s.label }}
                  </button>
                </div>

                <!-- Relation type chips -->
                <div class="xfilter-section">
                  <div class="xfilter-label">关系类型</div>
                  <div class="xfilter-chips">
                    <button v-for="t in xrelTypeOptions" :key="t.value"
                      class="xfilter-chip" :class="{ active: xrelFilterState.types.includes(t.value) }"
                      @click="toggleXrelType(t.value)">
                      {{ t.label }}
                    </button>
                  </div>
                </div>

                <!-- Confidence + Sort row -->
                <div class="xfilter-row">
                  <div class="xfilter-half">
                    <div class="xfilter-label">置信度</div>
                    <select v-model="xrelFilterState.minConfidence" class="form-input xfilter-select">
                      <option :value="0">全部</option>
                      <option :value="0.6">&ge;60%</option>
                      <option :value="0.8">&ge;80%</option>
                    </select>
                  </div>
                  <div class="xfilter-half">
                    <div class="xfilter-label">排序</div>
                    <select v-model="xrelFilterState.sort" class="form-input xfilter-select">
                      <option value="confidence_desc">置信度最高</option>
                      <option value="created_desc">最近发现</option>
                    </select>
                  </div>
                </div>

                <!-- 动作 -->
                <div class="xfilter-actions">
                  <button class="btn-small" @click="resetXrelFilter">清空筛选</button>
                </div>

                <hr class="xfilter-divider" />
              </template>

              <div class="card-title">操作面板</div>
              <p class="section-copy mini-copy">
                选择左侧条目后可编辑、删除或管理项目链接。使用"项目推荐"批量导入概念。
              </p>
              <div v-if="registryStore.actionError" class="error-text">{{ registryStore.actionError }}</div>
            </template>
          </article>
        </div>
        </template><!-- /non-error, non-loading -->
        </template><!-- /concepts tab (default) -->
      </section>
    </main>
  </AppShell>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import ThemeTab from './tabs/ThemeTab.vue'
import EvolutionTab from './tabs/EvolutionTab.vue'
import ReviewTab from './tabs/ReviewTab.vue'
import CrossRelationCard from '../../components/CrossRelationCard.vue'
import { buildSourceArticleGraphHref } from '../../utils/articleGraphRoute'
import { applyLeadPromotionAction } from '../../services/api/topicClustersApi'
import {
  registryStore,
  loadEntries,
  selectEntry,
  addEntry,
  editEntry,
  removeEntry,
  unlinkConcept,
  searchEntries,
  loadSuggestions,
  linkConcept,
  loadCrossRelations,
  loadCrossRelationCounts,
  reviewCrossRelation,
  removeCrossRelation,
} from '../../stores/registryStore'
import { appMode } from '../../runtime/appMode'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'concepts', label: '概念' },
  { key: 'evolution', label: '演化日志' },
  { key: 'review', label: '审核队列' },
]

const tabMeta = {
  concepts: { badge: 'CONCEPT REGISTRY', title: '跨项目概念注册表', subtitle: '全局 canonical 概念的唯一真相源。各项目的已确认概念可以链接到这里，实现跨项目知识积累与对齐。' },
  evolution: { badge: 'EVOLUTION LOG', title: '演化日志', subtitle: '所有概念/主题的创建、更新、链接、审核等变更记录。' },
  review: { badge: 'REVIEW QUEUE', title: '审核队列', subtitle: '人工校验任务管理：认领、通过、重开、批量处理。' },
}

const activeTab = ref(route.query.tab || 'concepts')
const activeTabMeta = computed(() => tabMeta[activeTab.value] || tabMeta.concepts)

const selectedEntryName = computed(() => registryStore.selectedEntry?.canonical_name || '')

const crumbs = computed(() => {
  if (activeTab.value === 'evolution') {
    return [
      { label: '跨项目', to: '/workspace/registry' },
      { label: '演化日志' },
    ]
  }
  if (activeTab.value === 'review') {
    return [
      { label: '跨项目', to: '/workspace/registry' },
      { label: '审核队列' },
    ]
  }
  const base = [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '概念注册表', to: '/workspace/registry' },
  ]
  if (selectedEntryName.value) {
    return [...base, { label: selectedEntryName.value }]
  }
  return [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '概念注册表' },
  ]
})

function switchTab(key) {
  // "全局主题" 直接跳到新的 Hub-and-Spoke 主题页面
  if (key === 'themes') {
    router.push('/workspace/themes')
    return
  }
  activeTab.value = key
  router.replace({ query: { ...route.query, tab: key } })
}

// Gap #3 fix: react to URL changes made by OTHER components (e.g. the
// EvolutionTab clicking a concept_entry row which does router.replace to
// switch to tab=concepts + add ?select=canon_xxx). Without this watcher
// RegistryPage keeps its initial activeTab forever because Vue Router
// reuses the component instance on query-only changes.
watch(
  () => route.query.tab,
  (next) => {
    if (next && next !== activeTab.value) {
      activeTab.value = next
    }
  },
)

// Gap #3 fix: when a deep link carries ?select=canon_xxx, wait until the
// entries list is loaded, then select the target canonical so the middle
// detail panel populates. Runs on mount AND on any subsequent URL change.
watch(
  () => route.query.select,
  async (next) => {
    if (!next || typeof next !== 'string') return
    // Force the concept tab visible so the detail card actually renders.
    if (activeTab.value !== 'concepts') activeTab.value = 'concepts'
    // Wait for the store to have entries; if still empty, trigger a load.
    if (!registryStore.entries?.length) {
      try { await loadEntries() } catch (_err) { /* non-fatal */ }
    }
    selectEntry(next)
    loadCrossRelations(next)
    // Auto-scroll only the left entry list (not the whole page)
    nextTick(() => {
      setTimeout(() => {
        const activeBtn = document.querySelector('.candidate-button.active')
        if (!activeBtn) return
        const listContainer = activeBtn.closest('.candidate-list') || activeBtn.closest('.queue-card')
        if (listContainer) {
          const btnTop = activeBtn.offsetTop - listContainer.offsetTop
          listContainer.scrollTop = btnTop - listContainer.clientHeight / 2 + activeBtn.clientHeight / 2
        }
      }, 300)
    })
  },
  { immediate: true },
)

const currentPanel = ref('list')
const showCreateForm = ref(false)
const editMode = ref(false)
const searchInputRef = ref(null)
const searchQuery = ref(typeof route.query.query === 'string' ? route.query.query : '')
const suggestProjectId = ref('')
const autoSelectionMessage = ref('')

const formData = ref({
  canonical_name: '',
  concept_type: '概念',
  aliasesRaw: '',
  description: '',
})

const editData = ref({
  canonical_name: '',
  concept_type: '',
  aliasesRaw: '',
  description: '',
})

const lastProjectId = computed(() => route.query.from || '')

const selectedEntry = computed(() => registryStore.selectedEntry)
const leadMatchingMode = computed(() => ['lead', 'basket'].includes(registryContext.value.from))
const registryModeTitle = computed(() => {
  if (leadMatchingMode.value && activeTab.value === 'concepts') {
    return `概念匹配：${registryContext.value.query || '未命名线索'}`
  }
  return activeTabMeta.value.title
})
const registryModeSubtitle = computed(() => {
  if (leadMatchingMode.value && activeTab.value === 'concepts') {
    const parts = ['来自文章概念线索']
    if (registryContext.value.articleId) parts.push(registryContext.value.articleId)
    if (registryContext.value.projectId) parts.push(`当前研究项目 ${registryContext.value.projectId}`)
    return parts.join(' · ')
  }
  return activeTabMeta.value.subtitle
})
const leadLinking = ref(false)
const leadLinkMessage = ref('')
const leadLinkedEntryId = ref('')

const totalLinks = computed(() =>
  registryStore.entries.reduce((sum, e) => sum + (e.source_links?.length || 0), 0)
)

const uniqueTypes = computed(() =>
  new Set(registryStore.entries.map((e) => e.concept_type)).size
)

const displayEntries = computed(() => {
  if (searchQuery.value.trim()) return registryStore.searchResults
  return registryStore.entries
})

const registryContext = computed(() => {
  const query = typeof route.query.query === 'string' ? route.query.query : searchQuery.value
  const from = typeof route.query.from === 'string' ? route.query.from : ''
  return {
    active: Boolean(query || from === 'lead' || from === 'basket'),
    query,
    from,
    leadId: typeof route.query.lead_id === 'string' ? route.query.lead_id : '',
    promotionId: typeof route.query.promotion_id === 'string' ? route.query.promotion_id : '',
    sliceId: typeof route.query.slice_id === 'string' ? route.query.slice_id : '',
    articleId: typeof route.query.article_id === 'string' ? route.query.article_id : '',
    clusterId: typeof route.query.cluster_id === 'string' ? route.query.cluster_id : '',
    projectId: typeof route.query.project_id === 'string' ? route.query.project_id : '',
  }
})

const leadAssociationStatus = computed(() => {
  if (!selectedEntry.value) return '尚未完成关联'
  if (leadLinkedEntryId.value === selectedEntry.value.entry_id) {
    return `已关联到 ${selectedEntry.value.canonical_name}`
  }
  const sourceLeadId = registryContext.value.leadId || registryContext.value.promotionId
  const linkedByLead = sourceLeadId && (
    selectedEntry.value.source_lead_id === sourceLeadId
    || selectedEntry.value.source_promotion_id === registryContext.value.promotionId
  )
  const linkedByProject = registryContext.value.projectId && (selectedEntry.value.source_links || []).some((link) => (
    link.project_id === registryContext.value.projectId
  ))
  return linkedByLead || linkedByProject ? `已关联到 ${selectedEntry.value.canonical_name}` : '尚未完成关联'
})

const canLinkLeadToSelected = computed(() => Boolean(
  leadMatchingMode.value
  && selectedEntry.value?.entry_id
  && registryContext.value.clusterId
  && registryContext.value.promotionId
))

const linkPrimaryLabel = computed(() => {
  if (leadAssociationStatus.value.startsWith('已关联')) return '已关联到该概念'
  if (!canLinkLeadToSelected.value) return '先加入加工篮再关联'
  return '关联到该概念'
})

const leadAssociationCompleted = computed(() => leadAssociationStatus.value.startsWith('已关联'))

const leadDecisionExplanation = computed(() => {
  if (!selectedEntry.value) return '请先从左侧候选中选择一个已有概念，或沉淀为新概念。'
  if (leadAssociationCompleted.value) {
    return `该线索已进入 KFC，并关联到已有概念 ${selectedEntry.value.canonical_name}。`
  }
  if (!canLinkLeadToSelected.value) {
    return '该页面已自动选中候选概念，但缺少可写回的 promotion_id；请从加工篮进入后完成关联。'
  }
  return `该线索与已有概念 ${selectedEntry.value.canonical_name} 名称一致或语义接近，建议确认关联，而不是重复新建概念。`
})

const leadMatchReason = computed(() => {
  if (!selectedEntry.value) return '尚未选择候选概念。'
  const query = normalizeMatchValue(registryContext.value.query)
  const name = normalizeMatchValue(selectedEntry.value.canonical_name)
  if (query && name && query === name) return '名称完全一致，且 概念库已自动选中该规范概念。'
  if (autoSelectionMessage.value) return autoSelectionMessage.value
  return '搜索结果中该概念最接近当前文章线索。'
})

const leadMatchRisk = computed(() => {
  if (!selectedEntry.value) return '无法判断风险。'
  if (!selectedEntry.value.description) return '目标概念缺少定义，关联后建议在概念工作台补充定义。'
  return '未发现明显命名冲突；仍建议在工作台审查来源证据和候选关系。'
})

const matchingCandidateGroups = computed(() => {
  if (!leadMatchingMode.value) return []
  const results = displayEntries.value || []
  const exact = findExactSearchMatch(results, registryContext.value.query)
  const exactIds = new Set(exact ? [exact.entry_id] : [])
  const selected = selectedEntry.value && !exactIds.has(selectedEntry.value.entry_id)
    ? [selectedEntry.value]
    : []
  const similar = results.filter((entry) => !exactIds.has(entry.entry_id) && entry.entry_id !== selectedEntry.value?.entry_id).slice(0, 5)
  const groups = []
  if (exact) groups.push({ key: 'exact', label: '精确匹配', items: [exact] })
  if (selected.length) groups.push({ key: 'selected', label: '已自动选中', items: selected })
  if (similar.length) groups.push({ key: 'similar', label: '相近概念', items: similar })
  if (registryContext.value.articleId) {
    groups.push({
      key: 'same_article',
      label: '同篇文章概念',
      items: results.slice(0, 3),
    })
  }
  return groups.filter((group) => group.items.length)
})

const relationRecommendationEntries = computed(() =>
  (displayEntries.value || [])
    .filter((entry) => entry.entry_id !== selectedEntry.value?.entry_id)
    .slice(0, 4)
)

const leadRelationPath = computed(() => [
  `当前线索：${registryContext.value.query || selectedEntry.value?.canonical_name || '未命名线索'}`,
  `来源文章：${registryContext.value.articleId || '未携带 article_id'}`,
  `材料片段：${registryContext.value.sliceId || '待从加工篮补充'}`,
  `主题簇：${registryContext.value.clusterId || '未携带 cluster_id'}`,
  `候选概念：${selectedEntry.value?.canonical_name || '尚未选择'}`,
])

// -- Cross-relation filter state (local, no API calls) --
const xrelFilterState = ref({
  reviewStatus: 'all',
  types: ['design_inspiration', 'technical_foundation', 'problem_solution', 'contrast_reference', 'capability_constraint', 'pattern_reuse'],
  minConfidence: 0,
  sort: 'confidence_desc',
})

const xrelStatusOptions = [
  { value: 'all', label: '全部' },
  { value: 'accepted', label: '已接受' },
  { value: 'unreviewed', label: '待审阅' },
  { value: 'rejected', label: '已驳回' },
]

const xrelTypeOptions = [
  { value: 'design_inspiration', label: '设计启示' },
  { value: 'technical_foundation', label: '技术支撑' },
  { value: 'problem_solution', label: '问题-方案' },
  { value: 'contrast_reference', label: '对比参照' },
  { value: 'capability_constraint', label: '能力约束' },
  { value: 'pattern_reuse', label: '模式借鉴' },
]

const filteredCrossRelations = computed(() => {
  let list = [...registryStore.crossRelations]
  const f = xrelFilterState.value
  // Status filter
  if (f.reviewStatus !== 'all') {
    list = list.filter(r => r.review_status === f.reviewStatus)
  }
  // Type filter
  if (f.types.length < 6) {
    list = list.filter(r => f.types.includes(r.relation_type))
  }
  // Confidence filter
  if (f.minConfidence > 0) {
    list = list.filter(r => (r.confidence || 0) >= f.minConfidence)
  }
  // Sort
  if (f.sort === 'confidence_desc') {
    list.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
  } else if (f.sort === 'created_desc') {
    list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  }
  return list
})

function toggleXrelType(typeValue) {
  const types = xrelFilterState.value.types
  const idx = types.indexOf(typeValue)
  if (idx >= 0) {
    if (types.length > 1) types.splice(idx, 1)  // don't allow empty
  } else {
    types.push(typeValue)
  }
}

function resetXrelFilter() {
  xrelFilterState.value = {
    reviewStatus: 'all',
    types: ['design_inspiration', 'technical_foundation', 'problem_solution', 'contrast_reference', 'capability_constraint', 'pattern_reuse'],
    minConfidence: 0,
    sort: 'confidence_desc',
  }
}

let searchTimer = null
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (searchQuery.value.trim()) {
      searchEntries(searchQuery.value)
    } else {
      registryStore.searchResults = []
    }
  }, 300)
}

function focusSearchInput() {
  searchInputRef.value?.focus?.()
}

function normalizeMatchValue(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '')
}

function findExactSearchMatch(results, query) {
  const normalizedQuery = normalizeMatchValue(query)
  if (!normalizedQuery) return null
  return results.find((entry) => {
    if (normalizeMatchValue(entry.canonical_name) === normalizedQuery) return true
    return (entry.aliases || []).some((alias) => normalizeMatchValue(alias) === normalizedQuery)
  }) || null
}

async function runRouteSearchAndSelection() {
  const routeQuery = typeof route.query.query === 'string' ? route.query.query.trim() : ''
  const selectedFromUrl = typeof route.query.selected === 'string'
    ? route.query.selected
    : (typeof route.query.select === 'string' ? route.query.select : '')
  autoSelectionMessage.value = ''
  if (routeQuery && routeQuery !== searchQuery.value) {
    searchQuery.value = routeQuery
  }
  if (routeQuery) {
    await searchEntries(routeQuery)
  }
  if (selectedFromUrl) {
    await handleSelectEntry(selectedFromUrl)
    autoSelectionMessage.value = `已自动选中最可能匹配的概念：${registryStore.selectedEntry?.canonical_name || selectedFromUrl}`
    return
  }
  if (routeQuery) {
    const exact = findExactSearchMatch(registryStore.searchResults, routeQuery)
    if (exact) {
      await handleSelectEntry(exact.entry_id)
      autoSelectionMessage.value = `已自动选中最可能匹配的概念：${exact.canonical_name}`
    }
  }
}

function conceptWorkbenchRoute(entryId) {
  const query = {}
  for (const key of ['from', 'query', 'lead_id', 'promotion_id', 'slice_id', 'article_id', 'cluster_id', 'project_id']) {
    if (typeof route.query[key] === 'string' && route.query[key]) query[key] = route.query[key]
  }
  return { path: `/workspace/entry/${entryId}`, query }
}

async function handleLinkSelectedConcept() {
  if (!selectedEntry.value || !leadMatchingMode.value) return
  if (!canLinkLeadToSelected.value) {
    leadLinkMessage.value = '需要从加工篮进入并携带 promotion_id，才能直接完成关联。当前页面已自动选中匹配项，但尚未完成关联。'
    return
  }
  leadLinking.value = true
  leadLinkMessage.value = ''
  try {
    await applyLeadPromotionAction(registryContext.value.clusterId, registryContext.value.promotionId, {
      action: 'link_existing_registry_entry',
      target: {
        registry_entry_id: selectedEntry.value.entry_id,
        registry_entry_label: selectedEntry.value.canonical_name,
      },
      context: {
        lead_id: registryContext.value.leadId,
        promotion_id: registryContext.value.promotionId,
        slice_id: registryContext.value.sliceId,
        article_id: registryContext.value.articleId,
        cluster_id: registryContext.value.clusterId,
        project_id: registryContext.value.projectId,
      },
      note: '人工从概念匹配工作台关联已有注册表条目。',
    })
    leadLinkedEntryId.value = selectedEntry.value.entry_id
    leadLinkMessage.value = `已关联到该概念：${selectedEntry.value.canonical_name}`
    await selectEntry(selectedEntry.value.entry_id)
  } catch (err) {
    leadLinkMessage.value = err?.message || '关联失败，请返回加工篮重试。'
  } finally {
    leadLinking.value = false
  }
}

function handleSelectEntry(entryId) {
  selectEntry(entryId)
  loadCrossRelations(entryId)
  editMode.value = false
  showCreateForm.value = false
}

// -- Cross-relation handlers (L3) --
const conceptMap = computed(() => {
  const map = {}
  for (const e of registryStore.entries) {
    map[e.entry_id] = e
  }
  return map
})

function handleNavigateConcept(targetEntryId) {
  handleSelectEntry(targetEntryId)
}

async function handleReviewRelation(relationId, reviewStatus) {
  await reviewCrossRelation(relationId, { review_status: reviewStatus })
}

async function handleUpdateRelationType(relationId, relationType) {
  await reviewCrossRelation(relationId, { relation_type: relationType })
}

async function handleDeleteRelation(relationId) {
  if (!confirm('确定删除此跨文章关系？')) return
  const ok = await removeCrossRelation(relationId)
  if (ok) {
    // Refresh counts for current entry
    const entryIds = registryStore.entries.map(e => e.entry_id)
    loadCrossRelationCounts(entryIds)
  }
}

function resetForm() {
  showCreateForm.value = false
  formData.value = { canonical_name: '', concept_type: '概念', aliasesRaw: '', description: '' }
}

async function handleCreate() {
  const aliases = formData.value.aliasesRaw
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
  const entry = await addEntry({
    canonical_name: formData.value.canonical_name,
    concept_type: formData.value.concept_type || '概念',
    aliases,
    description: formData.value.description,
  })
  if (entry) {
    resetForm()
    selectEntry(entry.entry_id)
  }
}

function startEdit() {
  if (!selectedEntry.value) return
  editData.value = {
    canonical_name: selectedEntry.value.canonical_name,
    concept_type: selectedEntry.value.concept_type,
    aliasesRaw: (selectedEntry.value.aliases || []).join(', '),
    description: selectedEntry.value.description || '',
  }
  editMode.value = true
}

async function handleEdit() {
  const aliases = editData.value.aliasesRaw
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
  await editEntry(registryStore.selectedEntryId, {
    canonical_name: editData.value.canonical_name,
    concept_type: editData.value.concept_type,
    aliases,
    description: editData.value.description,
  })
  editMode.value = false
}

async function handleDelete() {
  if (!registryStore.selectedEntryId) return
  await removeEntry(registryStore.selectedEntryId)
}

async function handleUnlink(link) {
  await unlinkConcept(registryStore.selectedEntryId, {
    project_id: link.project_id,
    concept_key: link.concept_key,
  })
}

function openSuggestPanel() {
  currentPanel.value = 'suggest'
  showCreateForm.value = false
  editMode.value = false
  if (!suggestProjectId.value && lastProjectId.value) {
    suggestProjectId.value = lastProjectId.value
  }
}

function closeSuggestPanel() {
  currentPanel.value = 'list'
}

async function handleSuggest() {
  if (!suggestProjectId.value) return
  await loadSuggestions(suggestProjectId.value)
}

async function quickCreate(candidate) {
  const entry = await addEntry({
    canonical_name: candidate.display_name,
    concept_type: candidate.concept_type,
    aliases: [],
    description: '',
  })
  if (entry && suggestProjectId.value) {
    await linkConcept(entry.entry_id, {
      project_id: suggestProjectId.value,
      concept_key: candidate.concept_key,
      project_name: registryStore.suggestResult?.project_name || '',
    })
    // Refresh suggestions
    await loadSuggestions(suggestProjectId.value)
  }
}

async function quickLink(match) {
  await linkConcept(match.matched_entry_id, {
    project_id: suggestProjectId.value,
    concept_key: match.concept_key,
    project_name: registryStore.suggestResult?.project_name || '',
  })
  await loadSuggestions(suggestProjectId.value)
}

async function quickLinkCrossType(match) {
  // Cross-type linking: explicit user action to promote the cross-type hint to
  // a real registry link. Uses the same linkConcept backend call, so the
  // canonical entry on the registry side gains a new source_link.
  await linkConcept(match.matched_entry_id, {
    project_id: suggestProjectId.value,
    concept_key: match.concept_key,
    project_name: registryStore.suggestResult?.project_name || '',
  })
  await loadSuggestions(suggestProjectId.value)
}

async function handleExport() {
  try {
    const res = await fetch(
      (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001') + '/api/registry/export'
    )
    const json = await res.json()
    const blob = new Blob([JSON.stringify(json.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gewu-registry-export-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    registryStore.actionError = '导出失败: ' + (e.message || '')
  }
}

async function hydrateRegistry() {
  await loadEntries()
  const entryIds = registryStore.entries.map(e => e.entry_id)
  if (entryIds.length) loadCrossRelationCounts(entryIds)
  await runRouteSearchAndSelection()
  // Re-hydrate the currently-selected entry if one is set, so the
  // middle detail panel flips to the new data source too.
  if (registryStore.selectedEntryId) {
    await selectEntry(registryStore.selectedEntryId)
    await loadCrossRelations(registryStore.selectedEntryId)
  }
}

onMounted(hydrateRegistry)

watch(
  () => [route.query.query, route.query.selected, route.query.select, route.query.from],
  () => { runRouteSearchAndSelection() },
)

// Reload registry on mode flip so the list + counts switch together.
watch(appMode, () => { hydrateRegistry() })
</script>

<style scoped>
/* Legacy sidebar styles removed (now provided by AppShell). Topbar buttons & tabs first. */
.topbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: #fff;
  color: var(--accent-primary);
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover { background: var(--bg-muted); border-color: var(--border-strong); }
.topbar-btn .icon { font-size: 13px; }

.registry-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border-muted);
  margin-bottom: 20px;
}
.registry-tab {
  padding: 10px 18px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease;
}
.registry-tab:hover { color: var(--accent-primary); }
.registry-tab.active {
  color: var(--accent-primary);
  border-bottom-color: var(--accent-primary);
  font-weight: 700;
}

/* -- Main area (now inside AppShell) -- */
.registry-main {
  max-width: 1400px;
  margin: 0 auto;
}

.phase2-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.registry-context-banner {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid #c7d2fe;
  border-left: 4px solid #6366f1;
  border-radius: 10px;
  background: #f7f7ff;
}
.registry-context-banner h3 {
  margin: 2px 0 4px;
  color: #1f2937;
  font-size: 18px;
}
.registry-context-banner p {
  margin: 0;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
}
.context-kicker {
  color: #4f46e5;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.context-selection {
  margin-top: 6px !important;
  color: #047857 !important;
  font-weight: 700;
}
.context-grid,
.preview-dl.compact {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0 0;
}
.context-grid div,
.preview-dl.compact div {
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 8px;
  padding: 7px 8px;
  background: rgba(255, 255, 255, 0.68);
}
.context-grid dt,
.preview-dl.compact dt {
  color: #6b7280;
  font-size: 11px;
  font-weight: 800;
}
.context-grid dd,
.preview-dl.compact dd {
  margin: 2px 0 0;
  color: #1f2937;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.context-actions {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-shrink: 0;
}
.lead-decision-workspace {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 10px 24px rgba(30, 64, 175, 0.06);
}
.decision-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}
.decision-hero h3 {
  margin: 3px 0 6px;
  color: #111827;
  font-size: 22px;
}
.decision-hero p {
  margin: 0;
  color: #334155;
  line-height: 1.55;
}
.decision-explain {
  max-width: 760px;
  margin-top: 8px !important;
  color: #475569 !important;
}
.decision-status-card {
  width: min(260px, 100%);
  border: 1px solid #fed7aa;
  border-radius: 10px;
  padding: 12px;
  background: #fff7ed;
}
.decision-status-card.done {
  border-color: #bbf7d0;
  background: #f0fdf4;
}
.decision-status-card span,
.decision-status-card small {
  display: block;
  color: #64748b;
  font-size: 12px;
}
.decision-status-card strong {
  display: block;
  margin: 4px 0;
  color: #1f2937;
  overflow-wrap: anywhere;
}
.decision-grid {
  display: grid;
  grid-template-columns: minmax(240px, 0.9fr) minmax(260px, 1.15fr) minmax(240px, 1fr);
  gap: 12px;
}
.decision-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  background: #fff;
}
.decision-actions-card {
  border-color: #bfdbfe;
  background: #eff6ff;
}
.decision-dl {
  display: grid;
  gap: 8px;
  margin: 0;
}
.decision-dl div {
  display: grid;
  gap: 2px;
}
.decision-dl dt {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}
.decision-dl dd {
  margin: 0;
  color: #1e293b;
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.bring-in-checklist {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #334155;
  font-size: 13px;
  line-height: 1.65;
}
.completion-callout {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #bbf7d0;
  border-radius: 9px;
  padding: 10px;
  background: #f0fdf4;
  color: #166534;
  font-size: 13px;
  line-height: 1.45;
}
.completion-callout strong {
  color: #14532d;
}
.grouped-candidate-list {
  gap: 12px;
}
.candidate-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.candidate-group-title {
  color: #6b7280;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
}
.matching-tabs {
  display: inline-flex;
  width: fit-content;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  background: #f8fafc;
  margin: 12px 0;
}
.matching-tab {
  border: 0;
  border-radius: 6px;
  padding: 6px 10px;
  background: transparent;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.matching-tab.active {
  background: #fff;
  color: #1d4ed8;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12);
}
.matching-panel {
  border: 1px solid #dbeafe;
  border-radius: 8px;
  padding: 12px;
  background: #f8fbff;
}
.task-explanation-panel {
  margin-top: 12px;
}
.matching-candidate-actions,
.bring-in-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #334155;
  font-size: 12px;
}
.local-graph {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.graph-node {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px;
  text-align: center;
  font-size: 12px;
  font-weight: 800;
}
.graph-node--lead { background: #fff7ed; color: #9a3412; }
.graph-node--concept { background: #eff6ff; color: #1d4ed8; }
.graph-node--article { background: #f5f3ff; color: #6d28d9; }
.path-list {
  margin: 0;
  padding-left: 18px;
  color: #334155;
  font-size: 13px;
  line-height: 1.7;
}
.processing-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.action-row.vertical {
  flex-direction: column;
  align-items: stretch;
}
.advanced-filter-details {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.62);
}
.advanced-filter-details summary {
  cursor: pointer;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}
.system-explain-details {
  margin-top: 12px;
}
.system-explain-details[open] {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.btn-primary.compact {
  padding: 7px 12px;
  font-size: 12px;
  text-decoration: none;
}

.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent-primary);
  font-weight: 700;
}

.section-title {
  margin: 0;
  font-size: 28px;
  color: var(--text-primary);
}

.section-copy,
.metric-line {
  color: var(--text-secondary);
  line-height: 1.6;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.card,
.state-card {
  border: 1px solid var(--border-default);
  background: linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-surface-2) 100%);
  border-radius: 18px;
  padding: 18px;
}

.error-card {
  border-color: #e2b0a8;
  background: #fff8f6;
}

.card-title {
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  flex: 1;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  transition: border-color 200ms;
}

.search-input:focus {
  border-color: var(--accent-primary);
}

.btn-primary {
  background: var(--accent-primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 10px 18px;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
  transition: background 200ms;
  white-space: nowrap;
}

.btn-primary:hover {
  background: var(--accent-primary-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-small {
  border: 1px solid var(--border-default);
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-small:hover {
  background: var(--bg-surface-2);
}

.btn-danger {
  color: #c44;
  border-color: #e8b0b0;
}

.btn-danger:hover {
  background: #fff5f5;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.registry-layout {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(260px, 320px);
  gap: 16px;
  align-items: start;
}

.pill,
.chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  color: var(--accent-primary);
  background: rgba(245, 248, 255, 0.95);
  font-size: 12px;
  font-weight: 600;
}

.chip.soft {
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-secondary);
}
.chip.success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 65vh;
  overflow-y: auto;
}

.candidate-button {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-default);
  background: rgba(255, 255, 255, 0.85);
  border-radius: 16px;
  padding: 14px;
  cursor: pointer;
  transition: border-color 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}

.candidate-button:hover,
.candidate-button.active {
  border-color: var(--accent-primary);
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(74, 111, 165, 0.08);
}

.candidate-topline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.candidate-name {
  color: var(--text-primary);
  font-weight: 700;
}

.candidate-status,
.candidate-meta {
  color: var(--text-secondary);
  font-size: 13px;
}

.xrel-badge {
  font-size: 10px;
  font-weight: 600;
  color: #6366f1;
  background: #eef2ff;
  padding: 1px 5px;
  border-radius: 4px;
  margin-left: 4px;
}

.xrel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pill.small {
  font-size: 11px;
  padding: 1px 6px;
  margin-left: 6px;
}

/* -- Cross-relation filter panel -- */
.xfilter-summary {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}
.xfilter-active { color: var(--accent-primary); font-weight: 600; }

.xfilter-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.xfilter-tab {
  flex: 1;
  padding: 5px 0;
  font-size: 11px;
  border: none;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}
.xfilter-tab:not(:last-child) { border-right: 1px solid #e5e7eb; }
.xfilter-tab.active { background: var(--accent-primary); color: #fff; font-weight: 600; }
.xfilter-tab:hover:not(.active) { background: #f3f4f6; }

.xfilter-section { margin-bottom: 12px; }
.xfilter-label {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.xfilter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.xfilter-chip {
  font-size: 10px;
  padding: 3px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}
.xfilter-chip.active { background: #eef2ff; border-color: #6366f1; color: #4338ca; font-weight: 600; }
.xfilter-chip:hover:not(.active) { border-color: #9ca3af; }

.xfilter-row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.xfilter-half { flex: 1; }
.xfilter-select {
  font-size: 12px;
  padding: 4px 8px;
}

.xfilter-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.xfilter-divider {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 12px 0;
}

.detail-kicker,
.subsection-title {
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-title {
  margin: 6px 0 0;
  font-size: 24px;
  color: #1a1713;
}

.detail-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.open-detail-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--accent-primary);
  background: var(--accent-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}
.open-detail-btn:hover { background: #3c5d8a; border-color: #3c5d8a; }

.detail-sections {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 18px;
}

.mini-copy {
  font-size: 13px;
  margin: 0;
}

.empty-state,
.empty-note {
  color: #7a8090;
  font-size: 13px;
  line-height: 1.6;
}

.link-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  border: 1px solid #e4e8f0;
  border-radius: 12px;
  padding: 10px 12px;
  background: #fff;
}

.link-project {
  font-weight: 600;
  color: #1d1d1d;
  font-size: 13px;
}
.link-clickable {
  text-decoration: none;
  color: var(--accent-primary);
  cursor: pointer;
  transition: color 100ms;
}
.link-clickable:hover {
  color: #2c5282;
  text-decoration: underline;
}

.link-concept {
  color: var(--text-secondary);
  font-size: 12px;
  flex: 1;
}

.action-row {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.form-input {
  width: 100%;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--accent-primary);
}

.suggest-summary {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: #fff;
}

.suggest-section {
  margin-top: 16px;
}

.suggest-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-muted);
}

.suggest-item:last-child {
  border-bottom: none;
}

.error-text {
  color: #c44;
  font-size: 13px;
  margin-top: 10px;
}

@media (max-width: 1240px) {
  .registry-layout {
    grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  }
  .decision-grid {
    grid-template-columns: 1fr 1fr;
  }
  .action-card {
    grid-column: span 2;
  }
}

@media (max-width: 960px) {
  .registry-shell {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
  }
  .registry-layout {
    grid-template-columns: 1fr;
  }
  .registry-context-banner,
  .decision-hero {
    flex-direction: column;
  }
  .context-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .decision-grid,
  .local-graph {
    grid-template-columns: 1fr;
  }
  .action-card {
    grid-column: auto;
  }
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
