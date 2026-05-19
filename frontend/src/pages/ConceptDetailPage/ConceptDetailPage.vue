<template>
  <component :is="embedded ? 'div' : AppShell" v-bind="embedded ? { class: 'concept-embedded-shell' } : { crumbs }">
    <template v-if="!embedded" #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="fullPageHref" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

    <div class="concept-wrap" :class="{ embedded }">
      <div v-if="loading" class="state-card">正在加载概念详情...</div>
      <div v-else-if="loadError" class="state-card error-card">{{ loadError }}</div>

      <template v-else-if="entry">
        <article v-if="embedded" class="concept-compact-pane" data-testid="concept-compact-pane">
          <header class="compact-concept-header">
            <div class="compact-title-row">
              <h1 class="compact-concept-title">{{ entry.canonical_name }}</h1>
              <span class="concept-type-chip">{{ entry.concept_type }}</span>
            </div>
            <dl class="compact-context-list">
              <div>
                <dt>来自</dt>
                <dd>{{ sourceSummary.primaryLabel }}</dd>
              </div>
              <div>
                <dt>关联</dt>
                <dd>{{ compactContextLabel }}</dd>
              </div>
            </dl>
            <div class="compact-actions">
              <a
                v-if="primarySourceHref"
                class="btn-sm"
                :href="primarySourceHref"
                target="_blank"
                rel="noopener"
                title="在文章阅读视图中查看该概念的来源位置"
              >查看原文</a>
              <a v-else class="btn-sm" :href="fullPageHref" target="_blank" rel="noopener">打开概念</a>
              <a class="btn-sm" :href="fullPageHref" target="_blank" rel="noopener">完整工作台</a>
            </div>
            <p v-if="entry.description" class="compact-concept-desc">{{ entry.description }}</p>
          </header>

          <section class="compact-section compact-related-section" data-testid="embedded-related-concepts">
            <div class="compact-section-head">
              <h2>相关概念</h2>
              <span>{{ relatedConceptRows.length }}</span>
            </div>
            <div v-if="relatedConceptRows.length" class="compact-related-list">
              <button
                v-for="row in relatedConceptRows"
                :key="`${row.entryId}:${row.relationLabel}:${row.sourceKind}`"
                :class="['compact-related-row', { 'compact-related-row--formal': row.formal }]"
                type="button"
                @click="navigateToConcept(row.entryId)"
              >
                <span class="compact-relation-kind">{{ row.sourceKind }}</span>
                <div class="compact-relation-edge">
                  <strong>{{ row.subjectName }}</strong>
                  <span class="compact-relation-arrow">→</span>
                  <span class="compact-relation-label">{{ row.relationLabel }}</span>
                  <span class="compact-relation-arrow">→</span>
                  <strong>{{ row.objectName }}</strong>
                </div>
                <p>{{ row.explanation }}</p>
                <small v-if="row.type">{{ row.type }}</small>
              </button>
            </div>
            <p v-else class="empty-note compact-note">暂无已记录的相邻概念。</p>
          </section>

          <section class="compact-section compact-source-section">
            <div class="compact-section-head">
              <h2>来源证据</h2>
              <span>{{ hasKfcProvenance ? '已追溯' : '待补充' }}</span>
            </div>
            <dl class="compact-evidence-list">
              <div>
                <dt>{{ sourceSummary.kindLabel }}</dt>
                <dd>{{ sourceSummary.primaryLabel }}</dd>
              </div>
              <div v-if="sourceEvidenceQuote">
                <dt>原文片段</dt>
                <dd>{{ sourceEvidenceQuote }}</dd>
              </div>
              <div v-if="sourceEvidenceContext">
                <dt>上下文</dt>
                <dd>{{ sourceEvidenceContext }}</dd>
              </div>
            </dl>
          </section>

          <section class="compact-section compact-definition-section">
            <div class="compact-section-head">
              <h2>定义摘要</h2>
            </div>
            <p>{{ entry.definition || entry.description || '暂无定义。可后续补充。' }}</p>
          </section>

          <details class="compact-section compact-meta-section">
            <summary>元信息 / 治理 / 研究项目</summary>
            <dl class="compact-evidence-list compact-meta-list">
              <div><dt>概念类型</dt><dd>{{ entry.concept_type }}</dd></div>
              <div><dt>状态</dt><dd>{{ entry.lifecycle_status || 'active' }} / {{ entry.quality_state || 'machine_generated' }} / {{ entry.review_state || 'unreviewed' }}</dd></div>
              <div><dt>当前研究项目</dt><dd>{{ currentProjectStatus.label }}</dd></div>
              <div><dt>推荐处理</dt><dd>{{ reviewWorkDetail }}</dd></div>
            </dl>
          </details>
        </article>

        <template v-else>
        <!-- Header -->
        <header class="concept-header">
          <div class="section-badge">CONCEPT WORKBENCH</div>
          <div class="section-badge legacy-canonical-badge">CANONICAL CONCEPT</div>
          <h2 class="workbench-title">概念工作台</h2>
          <div class="concept-title-row">
            <h1 class="concept-title">{{ entry.canonical_name }}</h1>
            <span class="concept-type-chip">{{ entry.concept_type }}</span>
          </div>
          <p v-if="entry.description" class="concept-desc">{{ entry.description }}</p>
          <p v-else class="concept-desc-empty">暂无描述</p>
          <div v-if="entry.aliases?.length" class="alias-row">
            <span class="alias-label">别名</span>
            <span v-for="a in entry.aliases" :key="a" class="alias-chip">{{ a }}</span>
          </div>

          <section class="workbench-status-panel">
            <div>
              <span class="status-label">概念身份</span>
              <strong>{{ conceptIdentityLabel }}</strong>
              <small>{{ entry.lifecycle_status || 'active' }} / {{ entry.quality_state || 'unknown' }} / {{ entry.review_state || 'unknown' }}</small>
            </div>
            <div>
              <span class="status-label">当前研究项目</span>
              <strong>{{ currentProjectStatus.label }}</strong>
              <small>{{ currentProjectStatus.detail }}</small>
            </div>
            <div>
              <span class="status-label">推荐处理</span>
              <strong>{{ reviewWorkLabel }}</strong>
              <small>{{ reviewWorkDetail }}</small>
            </div>
          </section>

          <details v-if="activeWorkbenchTab === 'source' && hasKfcProvenance" class="concept-provenance">
            <summary>来源追溯</summary>
            <dl>
              <div><dt>状态</dt><dd>{{ entry.lifecycle_status || 'active' }} / {{ entry.quality_state || 'unknown' }} / {{ entry.review_state || 'unknown' }}</dd></div>
              <div><dt>来源</dt><dd>{{ sourceSummary.primaryLabel }}</dd></div>
              <div v-if="sourceSummary.primaryLink"><dt>来源键</dt><dd>{{ sourceSummary.primaryLink.concept_key || '暂无' }}</dd></div>
              <div><dt>Markdown</dt><dd>{{ entry.source_markdown_path || '暂无路径' }}</dd></div>
              <div><dt>Content hash</dt><dd>{{ entry.source_content_hash || '暂无 hash' }}</dd></div>
              <div><dt>引文</dt><dd>{{ entry.source_quote || entry.source_excerpt || '暂无引文' }}</dd></div>
              <div><dt>上下文</dt><dd>{{ entry.source_context || '暂无上下文' }}</dd></div>
              <div><dt>Created</dt><dd>{{ entry.created_from || 'unknown' }} / {{ entry.created_by || 'unknown' }} / {{ formatPercent(entry.confidence) }}</dd></div>
            </dl>
          </details>
        </header>

        <nav class="workbench-tabs" aria-label="概念工作台视图">
          <button
            v-for="tab in workbenchTabs"
            :key="tab.key"
            type="button"
            :class="['workbench-tab', { active: activeWorkbenchTab === tab.key }]"
            @click="activeWorkbenchTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </nav>

        <section v-if="activeWorkbenchTab === 'overview'" class="section overview-section">
          <div class="section-head">
            <h2 class="section-title">{{ entry.canonical_name }}</h2>
            <span class="section-counter">{{ entry.concept_type }} · {{ entry.lifecycle_status || 'active' }} · {{ entry.quality_state || 'machine_generated' }} · {{ entry.review_state || 'unreviewed' }}</span>
          </div>
          <p class="overview-definition">{{ entry.definition || entry.description || '暂无定义。' }}</p>
          <div class="overview-grid">
            <div>
              <span>来源</span>
              <strong>{{ sourceSummary.primaryLabel }}</strong>
            </div>
            <div>
              <span>当前项目状态</span>
              <strong>{{ currentProjectStatus.label }}</strong>
            </div>
            <div>
              <span>待处理</span>
              <strong>{{ reviewWorkDetail }}</strong>
            </div>
          </div>
          <div class="overview-actions">
            <button class="btn-sm" type="button" @click="activeWorkbenchTab = 'project'">加入当前研究项目</button>
            <button class="btn-sm" type="button" @click="activeWorkbenchTab = 'graph'">审查 {{ unreviewedCount }} 条关系</button>
            <button class="btn-sm" type="button" @click="activeWorkbenchTab = 'source'">查看来源证据</button>
            <button class="btn-sm" type="button" @click="activeWorkbenchTab = 'graph'">打开图谱邻域</button>
            <button class="btn-sm" type="button" @click="activeWorkbenchTab = 'governance'">编辑概念</button>
          </div>
        </section>

        <!-- Summary counters -->
        <div v-if="activeWorkbenchTab === 'overview'" class="summary-grid">
          <article class="summary-card">
            <div class="card-title">项目链接</div>
            <div class="metric-value">{{ entry.source_links?.length || 0 }}</div>
          </article>
          <article class="summary-card">
            <div class="card-title">跨文关系</div>
            <div class="metric-value">{{ activeRelations.length }}</div>
          </article>
          <article class="summary-card">
            <div class="card-title">待审</div>
            <div class="metric-value">{{ unreviewedCount }}</div>
          </article>
          <article class="summary-card">
            <div class="card-title">KFC 来源图谱</div>
            <div class="metric-value">{{ materialGraphSummary.node_count || entry.graph_node_count || 0 }}</div>
          </article>
        </div>

        <section v-if="activeWorkbenchTab === 'overview'" class="section identity-section">
          <div class="section-head">
            <h2 class="section-title">概念身份</h2>
            <span class="section-counter">{{ entry.concept_type }}</span>
          </div>
          <dl class="identity-grid">
            <div><dt>名称</dt><dd>{{ entry.canonical_name }}</dd></div>
            <div><dt>别名</dt><dd>{{ entry.aliases?.length ? entry.aliases.join(' / ') : '暂无别名' }}</dd></div>
            <div><dt>生命周期</dt><dd>{{ entry.lifecycle_status || 'active' }}</dd></div>
            <div><dt>质量 / 审查</dt><dd>{{ entry.quality_state || 'unknown' }} / {{ entry.review_state || 'unknown' }}</dd></div>
          </dl>
        </section>

        <section v-if="activeWorkbenchTab === 'source'" class="section evidence-section">
          <div class="section-head">
            <h2 class="section-title">来源与证据</h2>
            <span class="section-counter">{{ hasKfcProvenance ? '已追溯' : '待补充' }}</span>
          </div>
          <div class="evidence-grid">
            <div>
              <span>{{ sourceSummary.kindLabel }}</span>
              <strong>{{ sourceSummary.primaryLabel }}</strong>
            </div>
            <div>
              <span>{{ sourceSummary.primaryLink ? '来源键' : '材料片段' }}</span>
              <strong>{{ sourceSummary.primaryLink?.concept_key || entry.source_material_slice_id || materialSliceNode?.id || '暂无' }}</strong>
            </div>
            <div class="wide">
              <span>引文</span>
              <p>{{ sourceEvidenceQuote }}</p>
            </div>
            <div class="wide">
              <span>上下文</span>
              <p>{{ sourceEvidenceContext }}</p>
            </div>
          </div>
          <div v-if="sourceEvidenceItems.length" class="source-link-strip">
            <article
              v-for="link in sourceEvidenceItems"
              :key="`${link.project_id}:${link.concept_key}:${link.source_node_uuid || ''}`"
              class="source-link-card"
              :class="{ active: link.project_id === currentProjectId }"
            >
              <span>{{ link.project_id === currentProjectId ? '当前来源' : '来源项目' }}</span>
              <strong>{{ link.project_name || link.project_id }}</strong>
              <small>{{ link.concept_key || '暂无来源键' }} · {{ link.group_title || link.group_label || link.project_id }}</small>
              <p v-if="link.source_excerpt || link.source_text" class="source-link-quote">
                {{ link.source_excerpt || link.source_text }}
              </p>
              <a
                v-if="link.project_id"
                class="source-locate-link"
                :href="articleHref(link)"
                target="_blank"
                rel="noopener"
                title="在阅读图谱中定位该概念节点"
              >定位到阅读图谱 ↗</a>
            </article>
          </div>
          <details class="technical-trace-details">
            <summary>展开技术追踪信息</summary>
            <dl class="identity-grid compact">
              <div><dt>markdown path</dt><dd>{{ entry.source_markdown_path || '暂无路径' }}</dd></div>
              <div><dt>content hash</dt><dd>{{ entry.source_content_hash || '暂无 hash' }}</dd></div>
              <div><dt>source_article_id</dt><dd>{{ entry.source_article_id || sourceSummary.primaryLink?.project_id || '暂无' }}</dd></div>
              <div><dt>source_material_slice_id</dt><dd>{{ entry.source_material_slice_id || materialSliceNode?.id || '暂无' }}</dd></div>
              <div><dt>created_by</dt><dd>{{ entry.created_by || 'unknown' }}</dd></div>
              <div><dt>created_at</dt><dd>{{ entry.created_at || 'unknown' }}</dd></div>
            </dl>
          </details>
        </section>

        <!-- Section: deterministic KFC material graph -->
        <section v-if="activeWorkbenchTab === 'graph'" class="section material-graph-section" data-testid="kfc-material-graph-section">
          <div class="section-head">
            <h2 class="section-title">来源/材料图谱</h2>
            <span class="section-counter">KFC 来源图谱</span>
            <span class="section-counter">{{ materialGraphStatusLabel }}</span>
            <button
              v-if="embedded"
              class="btn-sm section-toggle"
              type="button"
              @click="embeddedOpenSections.materialGraph = !embeddedOpenSections.materialGraph"
            >
              {{ embeddedOpenSections.materialGraph ? '收起' : '展开' }}
            </button>
          </div>

          <div v-if="embedded && !embeddedOpenSections.materialGraph" class="empty-note compact-note">
            来源图谱默认折叠；需要看原文片段和跨文线索时再展开。
          </div>
          <template v-else>
            <div v-if="graphLoading" class="empty-note">正在加载 KFC 来源图谱...</div>
            <div v-else-if="graphError" class="empty-note error-text">{{ graphError }}</div>
            <template v-else>
              <div class="material-graph-toolbar">
                <div class="graph-metrics">
                  <span>节点 {{ materialGraphSummary.node_count || 0 }}</span>
                  <span>关系 {{ materialGraphSummary.edge_count || 0 }}</span>
                  <span>跨文线索 {{ materialGraphSummary.cross_article_link_count || 0 }}</span>
                </div>
                <div class="graph-actions">
                  <button class="btn-sm" :disabled="graphSnapshotting" @click="handleCreateGraphSnapshot">
                    {{ graphSnapshotting ? '生成中...' : (materialGraph ? '刷新确定性快照' : '生成确定性快照') }}
                  </button>
                  <button class="btn-sm" :disabled="graphRequesting || !materialGraph" @click="handleCreateGraphificationRequest">
                    {{ graphRequesting ? '写入中...' : '请求外部图谱化建议' }}
                  </button>
                </div>
              </div>

              <p class="graph-boundary-note">
                KFC 只保存概念、来源片段、确定性关系快照和外部图谱化请求；这是该概念从文章材料沉淀出来时形成的确定性来源图谱，不代表完整知识图谱；这里不会直接调用模型、Codex、runner 或后台调度器。
              </p>

              <div v-if="!materialGraph" class="empty-note">
                尚未生成来源图谱快照。进入快照后，这个概念对应的原文片段会作为可追溯素材进入 KFC 图谱资产。
              </div>

              <div v-else class="material-graph-body">
                <div class="semantic-chain-card">
                  <strong>来源链路</strong>
                  <span>文章 -> 材料片段 -> {{ entry.canonical_name }} -> 主题簇</span>
                  <small>节点与边明细默认折叠；这里优先展示语义摘要。</small>
                </div>
                <div class="graph-source-card">
                  <div class="source-title">{{ sourceArticleNode?.label || entry.source_article_title || entry.source_article_id || '来源文章' }}</div>
                  <p>{{ materialSliceText }}</p>
                  <small>{{ entry.source_markdown_path || materialSliceNode?.data?.path || '暂无路径' }}</small>
                </div>
                <div v-if="materialSliceNodes.length" class="linked-source-slices">
                  <strong>关联来源片段</strong>
                  <article v-for="node in materialSliceNodes" :key="nodeKey(node)" class="linked-source-slice">
                    <span>{{ node.label || node.ref_id }}</span>
                    <p>{{ node.source_quote || node.data?.source_quote || '暂无 quote' }}</p>
                    <small>{{ node.source_context || node.data?.source_context || '暂无 context' }}</small>
                  </article>
                </div>

                <details class="technical-trace-details">
                  <summary>查看节点与边明细</summary>
                <div class="graph-columns">
                  <div>
                    <h3>图谱节点</h3>
                    <ul class="graph-list">
                      <li v-for="node in graphNodes" :key="nodeKey(node)">
                        <span class="node-type">{{ nodeType(node) }}</span>
                        <strong>{{ node.label }}</strong>
                      </li>
                    </ul>
                  </div>
                  <div>
                    <h3>关系与跨文线索</h3>
                    <ul class="graph-list">
                      <li v-for="edge in graphEdges" :key="edgeKey(edge)">
                        <span class="node-type">{{ edgeType(edge) }}</span>
                        <strong>{{ edge.label || `${edge.source} -> ${edge.target}` }}</strong>
                      </li>
                    </ul>
                    <div v-if="crossArticleLinks.length" class="cross-link-strip">
                      <span v-for="link in crossArticleLinks" :key="link.target_concept_id || link.label">
                        {{ link.label || link.target_concept_id }}
                      </span>
                    </div>
                  </div>
                </div>
                </details>

                <p v-if="graphRequestMessage" class="request-note">{{ graphRequestMessage }}</p>
              </div>
            </template>
          </template>
        </section>

        <!-- Section: project links -->
        <section v-if="activeWorkbenchTab === 'project'" class="section">
          <div class="section-head">
            <h2 class="section-title">研究项目使用</h2>
            <span class="section-counter">{{ entry.source_links?.length || 0 }}</span>
            <button
              v-if="embedded"
              class="btn-sm section-toggle"
              type="button"
              @click="embeddedOpenSections.sourceLinks = !embeddedOpenSections.sourceLinks"
            >
              {{ embeddedOpenSections.sourceLinks ? '收起' : '展开' }}
            </button>
          </div>
          <div v-if="embedded && !embeddedOpenSections.sourceLinks" class="empty-note compact-note">
            项目来源默认折叠；需要追溯来源文章时再展开。
          </div>
          <div v-else-if="entry.source_links?.length" class="link-list">
            <div v-for="link in entry.source_links" :key="link.project_id + link.concept_key" class="link-row">
              <div class="link-main">
                <span class="link-project">{{ link.project_name || link.project_id }}</span>
                <span class="link-arrow">→</span>
                <span class="link-concept">{{ entry.concept_type }}:{{ link.concept_key }}</span>
              </div>
              <div class="link-actions">
                <a
                  class="btn-sm"
                  :href="articleHref(link)"
                  target="_blank"
                  rel="noopener"
                  title="在新页面打开文章图谱并聚焦该节点"
                >打开来源文章 ↗</a>
                <button class="btn-sm btn-danger" @click="handleUnlink(link)">解绑</button>
              </div>
            </div>
          </div>
          <div v-else class="empty-note">尚未关联任何项目概念。</div>
          <div class="project-usage-note">
            <strong>当前项目状态：{{ currentProjectStatus.label }}</strong>
            <span>{{ currentProjectStatus.detail }}</span>
          </div>
          <div v-if="!currentProjectStatus.label.startsWith('已进入')" class="project-role-panel">
            <strong>加入当前研究项目</strong>
            <p>选择该概念在当前研究项目中的角色。当前前端只表达人工使用入口，不直接创建外部 runner 任务。</p>
            <div class="role-options">
              <button v-for="role in projectRoleOptions" :key="role" class="btn-sm" type="button" disabled>{{ role }}</button>
            </div>
          </div>
        </section>

        <!-- Section: cross-article relations -->
        <section v-if="activeWorkbenchTab === 'graph'" class="section">
          <div class="section-head">
            <h2 class="section-title">概念邻域</h2>
            <span class="section-counter">{{ filteredRelations.length }}</span>
            <button
              v-if="embedded"
              class="btn-sm section-toggle"
              type="button"
              @click="embeddedOpenSections.relations = !embeddedOpenSections.relations"
            >
              {{ embeddedOpenSections.relations ? '收起' : '展开' }}
            </button>
          </div>

          <!-- Filter bar -->
          <div v-if="embedded && !embeddedOpenSections.relations" class="empty-note compact-note">
            跨文关系默认折叠；需要审阅关系网络时再展开或新页打开。
          </div>
          <template v-else>
          <div class="xrel-filters">
            <div class="filter-group">
              <button
                v-for="s in statusOpts"
                :key="s.value"
                class="filter-chip"
                :class="{ active: filter.status === s.value }"
                @click="filter.status = s.value"
              >{{ s.label }}</button>
            </div>

            <div class="filter-group">
              <select v-model="filter.type" class="filter-select">
                <option value="all">全部类型</option>
                <option v-for="t in typeOpts" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
              <select v-model="filter.sort" class="filter-select">
                <option value="confidence_desc">置信度最高</option>
                <option value="created_desc">最近发现</option>
              </select>
            </div>
          </div>

            <div v-if="relationsLoading" class="empty-note">加载中...</div>
            <div v-else-if="!filteredRelations.length" class="empty-note">
              {{ allRelations.length ? '当前筛选下无匹配关系' : '暂无跨文关系。可在"跨文关系"列表页手动发现。' }}
            </div>
            <div v-else class="xrel-list">
              <div class="neighborhood-summary">
                <span>跨文章关系 {{ allRelations.length }}</span>
                <span>待确认关系 {{ unreviewedCount }}</span>
                <span>相关概念 {{ Object.keys(conceptMap).length }}</span>
              </div>
              <CrossRelationCard
                v-for="rel in filteredRelations"
                :key="rel.relation_id"
                :relation="rel"
                :conceptMap="conceptMap"
                :currentEntryId="entryId"
                @navigate="navigateToConcept"
                @review="handleReview"
                @type-change="handleUpdateRelationType"
                @delete="handleDelete"
              />
            </div>
          </template>
        </section>

        <!-- Actions -->
        <section v-if="activeWorkbenchTab === 'governance'" class="section governance-section">
          <div class="section-head">
            <h2 class="section-title">治理</h2>
            <span class="section-counter">{{ entry.review_state || 'unreviewed' }}</span>
          </div>
          <div class="governance-grid">
            <button class="btn-sm" type="button">编辑概念</button>
            <button class="btn-sm" type="button">修改别名</button>
            <button class="btn-sm" type="button">修改定义</button>
            <button class="btn-sm" type="button">合并概念</button>
            <button class="btn-sm" type="button">解除错误关系</button>
            <button class="btn-sm" type="button">查看变更日志</button>
          </div>
          <details class="danger-zone">
            <summary>高级危险区</summary>
            <p>物理删除只在高级危险区暴露，并保留二次确认；主流程使用“标记为废弃”。</p>
            <button class="btn-sm btn-danger" type="button">标记为废弃</button>
            <button v-if="!embedded" class="btn-sm btn-danger" @click="handleDeleteEntry">删除条目</button>
          </details>
        </section>

        <div v-if="!embedded && activeWorkbenchTab === 'governance'" class="concept-actions">
          <button class="btn-sm" @click="openInRegistry">在注册表中打开</button>
        </div>
        </template>
      </template>

      <div v-else class="state-card">未找到条目 {{ entryId }}</div>
    </div>
  </component>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import CrossRelationCard from '../../components/CrossRelationCard.vue'
import { buildSourceArticleGraphHref } from '../../utils/articleGraphRoute'
// Reads flip live/demo via dataClient; writes stay on the live API
// (the axios interceptor blocks mutations in demo mode).
import {
  getRegistryConcept,
  getRegistryConceptGraph,
  listCrossRelations,
  listRegistryConcepts,
} from '../../data/dataClient'
import {
  createRegistryConceptGraphificationRequest,
  createRegistryConceptGraphSnapshot,
  unlinkProjectConcept,
  updateCrossRelation,
  deleteCrossRelation,
  deleteRegistryConcept,
} from '../../services/api/registryApi'
import { appMode } from '../../runtime/appMode'

const route = useRoute()
const router = useRouter()
const props = defineProps({
  entryId: {
    type: String,
    default: '',
  },
  embedded: {
    type: Boolean,
    default: false,
  },
  contextLabel: {
    type: String,
    default: '',
  },
  relatedConcepts: {
    type: Array,
    default: () => [],
  },
})
const emit = defineEmits(['navigate', 'loaded'])

const entry = ref(null)
const loading = ref(false)
const loadError = ref('')

const allRelations = ref([])
const relationsLoading = ref(false)
const materialGraph = ref(null)
const materialGraphSummary = ref({})
const graphLoading = ref(false)
const graphError = ref('')
const graphSnapshotting = ref(false)
const graphRequesting = ref(false)
const graphRequestMessage = ref('')
const entryIndex = ref({}) // entry_id -> entry, for peer concept name resolution
const activeWorkbenchTab = ref('overview')
const workbenchTabs = [
  { key: 'overview', label: '概览' },
  { key: 'source', label: '来源证据' },
  { key: 'graph', label: '图谱邻域' },
  { key: 'project', label: '研究项目' },
  { key: 'governance', label: '治理' },
]
const projectRoleOptions = ['核心概念', '背景概念', '证据概念', '对比案例', '待验证假设', '方法论概念', '风险/限制']
const embeddedOpenSections = reactive({
  sourceLinks: true,
  relations: true,
  materialGraph: true,
})

const filter = reactive({
  status: 'all',
  type: 'all',
  sort: 'confidence_desc',
})

const statusOpts = [
  { value: 'all', label: '全部' },
  { value: 'accepted', label: '已接受' },
  { value: 'unreviewed', label: '待审' },
  { value: 'rejected', label: '已驳回' },
]

const typeOpts = [
  { value: 'design_inspiration', label: '设计启示' },
  { value: 'technical_foundation', label: '技术支撑' },
  { value: 'problem_solution', label: '问题-方案' },
  { value: 'contrast_reference', label: '对比参照' },
  { value: 'capability_constraint', label: '能力约束' },
  { value: 'pattern_reuse', label: '模式借鉴' },
]
const compactRelationLabels = {
  related_to: '相关',
  supports: '支撑',
  contradicts: '矛盾',
  refines: '细化',
  depends_on: '依赖',
  example_of: '实例',
  causes: '导致',
  compares_with: '对比',
  derived_from: '来源',
  design_inspiration: '启发',
  technical_foundation: '支撑',
  problem_solution: '解决/缓解',
  contrast_reference: '对比',
  capability_constraint: '约束',
  pattern_reuse: '复用',
}

const entryId = computed(() => props.entryId || route.params.entryId || '')
const embedded = computed(() => props.embedded)
const fullPageHref = computed(() => (entryId.value ? `/workspace/entry/${entryId.value}` : route.fullPath))
const graphNodes = computed(() => materialGraph.value?.nodes || [])
const graphEdges = computed(() => materialGraph.value?.edges || [])
const crossArticleLinks = computed(() => materialGraph.value?.cross_article_links || [])
const sourceArticleNode = computed(() => graphNodes.value.find((node) => nodeType(node) === 'source_article') || null)
const materialSliceNode = computed(() => graphNodes.value.find((node) => nodeType(node) === 'material_slice') || null)
const materialSliceNodes = computed(() => graphNodes.value.filter((node) => nodeType(node) === 'material_slice'))
const materialSliceText = computed(() =>
  materialSliceNode.value?.data?.text
  || materialSliceNode.value?.source_quote
  || entry.value?.source_quote
  || entry.value?.source_excerpt
  || '暂无来源片段文本。'
)
const queryProjectId = computed(() => {
  const raw = route.query.project_id || route.query.projectId || route.query.current_project_id || ''
  return Array.isArray(raw) ? (raw[0] || '') : raw
})
const sourceSummary = computed(() => {
  const links = entry.value?.source_links || []
  const matched = queryProjectId.value
    ? links.filter((link) => link.project_id === queryProjectId.value)
    : []
  const primaryLink = matched[0] || links[0] || null
  if (primaryLink) {
    return {
      kindLabel: matched.length ? '当前来源' : '来源项目',
      primaryLabel: primaryLink.project_name || primaryLink.project_id || '未命名来源项目',
      primaryLink,
      links: matched.length ? [...matched, ...links.filter((link) => link.project_id !== queryProjectId.value)] : links,
    }
  }
  const legacyLabel = entry.value?.source_article_title || entry.value?.source_article_id || ''
  if (legacyLabel) {
    return {
      kindLabel: '来源文章',
      primaryLabel: legacyLabel,
      primaryLink: null,
      links: [],
    }
  }
  return {
    kindLabel: '来源',
    primaryLabel: '未记录来源',
    primaryLink: null,
    links: [],
  }
})
const sourceEvidenceRefs = computed(() => entry.value?.source_evidence_refs || [])
const sourceEvidenceItems = computed(() => {
  const refs = sourceEvidenceRefs.value
  const base = refs.length ? refs : sourceSummary.value.links
  if (!queryProjectId.value) return base
  return [
    ...base.filter((link) => link.project_id === queryProjectId.value),
    ...base.filter((link) => link.project_id !== queryProjectId.value),
  ]
})
const primarySourceEvidence = computed(() => {
  const current = queryProjectId.value
    ? sourceEvidenceItems.value.find((ref) => ref.project_id === queryProjectId.value)
    : null
  return current || sourceEvidenceItems.value.find((ref) => !ref.degraded) || sourceEvidenceItems.value[0] || null
})
const sourceEvidenceQuote = computed(() =>
  entry.value?.source_quote
  || entry.value?.source_excerpt
  || primarySourceEvidence.value?.source_excerpt
  || primarySourceEvidence.value?.source_text
  || materialSliceText.value
)
const sourceEvidenceContext = computed(() =>
  entry.value?.source_context
  || primarySourceEvidence.value?.source_context
  || primarySourceEvidence.value?.source_text
  || '暂无 context'
)
const primarySourceHref = computed(() => {
  const link = primarySourceEvidence.value || sourceSummary.value.primaryLink
  return link?.project_id ? articleHref(link) : ''
})
const compactContextLabel = computed(() => {
  if (props.contextLabel) return props.contextLabel
  const topicNodes = graphNodes.value
    .filter((node) => nodeType(node) === 'topic_cluster')
    .map((node) => node.label || node.ref_id || node.id)
    .filter(Boolean)
  if (topicNodes.length) return topicNodes.slice(0, 2).join(' / ')
  const link = primarySourceEvidence.value || sourceSummary.value.primaryLink
  const group = link?.group_title || link?.group_label || ''
  if (group) return group
  return currentProjectStatus.value.label
})
const materialGraphStatusLabel = computed(() => {
  const status = materialGraphSummary.value.graph_status || entry.value?.graph_status || ''
  if (status === 'snapshot_available') return '已生成'
  if (materialGraph.value) return '已生成'
  return '未生成'
})
const conceptIdentityLabel = computed(() => `${entry.value?.concept_type || '概念'} · ${entry.value?.canonical_name || entryId.value}`)
const currentProjectId = computed(() => {
  if (queryProjectId.value) return queryProjectId.value
  const linked = entry.value?.linked_research_project_ids || []
  if (linked.length) return linked[0]
  const sourceProject = (entry.value?.source_links || [])[0]?.project_id
  return sourceProject || ''
})
const currentProjectStatus = computed(() => {
  const projectId = currentProjectId.value
  if (!projectId) {
    return {
      label: '当前页面未携带研究项目上下文',
      detail: '可从加工篮、注册表搜索或 主题簇 带 project_id 进入。',
    }
  }
  const linkedProjectIds = new Set([
    ...(entry.value?.linked_research_project_ids || []),
    ...(entry.value?.source_links || []).map((link) => link.project_id).filter(Boolean),
  ])
  if (linkedProjectIds.has(projectId)) {
    return {
      label: '已进入当前研究项目',
      detail: `项目 ${projectId} 已通过 source link 或 linked_research_project_ids 关联该概念。`,
    }
  }
  return {
    label: '未进入当前研究项目',
    detail: `当前上下文项目 ${projectId} 尚未在该概念的项目链接中确认。`,
  }
})
const reviewWorkLabel = computed(() => {
  if (unreviewedCount.value > 0) return '审查待确认关系'
  if (!entry.value?.description && !entry.value?.definition) return '补充定义'
  if (!hasKfcProvenance.value) return '补充来源证据'
  return '可作为稳定概念使用'
})
const reviewWorkDetail = computed(() => {
  if (unreviewedCount.value > 0) return `${unreviewedCount.value} 条跨文关系待确认。`
  if (!entry.value?.description && !entry.value?.definition) return '缺少定义或描述。'
  if (!hasKfcProvenance.value) return '缺少文章、quote 或材料片段追溯。'
  return '暂无明显待办。'
})

const crumbs = computed(() => {
  const tail = entry.value?.canonical_name || entryId.value || '概念详情'
  return [
    { label: '跨项目', to: '/workspace/registry' },
    { label: '概念注册表', to: '/workspace/registry' },
    { label: tail },
  ]
})

const activeRelations = computed(() =>
  allRelations.value.filter((r) => r.review_status === 'accepted' || r.review_status === 'unreviewed')
)
const unreviewedCount = computed(() =>
  allRelations.value.filter((r) => r.review_status === 'unreviewed').length
)
const hasKfcProvenance = computed(() => Boolean(
  entry.value?.source_article_id
  || entry.value?.source_markdown_path
  || entry.value?.source_quote
  || (entry.value?.source_links || []).length
  || entry.value?.quality_state
))

const filteredRelations = computed(() => {
  let list = [...allRelations.value]
  if (filter.status !== 'all') list = list.filter((r) => r.review_status === filter.status)
  if (filter.type !== 'all') list = list.filter((r) => r.relation_type === filter.type)
  if (filter.sort === 'confidence_desc') {
    list.sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
  } else if (filter.sort === 'created_desc') {
    list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  }
  return list
})
const relatedConceptRows = computed(() => {
  const rows = []
  for (const rel of allRelations.value) {
    const sourceId = rel.source_entry_id || rel.source_entry?.entry_id || ''
    const targetId = rel.target_entry_id || rel.target_entry?.entry_id || ''
    const peerId = sourceId === entryId.value ? targetId : sourceId
    if (!peerId || peerId === entryId.value) continue
    const peer = conceptMap.value[peerId] || (peerId === sourceId ? rel.source_entry : rel.target_entry) || {}
    if (rows.some((item) => item.entryId === peerId)) continue
    const currentName = entry.value?.canonical_name || entryId.value
    const peerName = peer.canonical_name || peer.name || peer.title || peerId
    const currentIsSource = sourceId === entryId.value
    rows.push({
      entryId: peerId,
      name: peerName,
      type: peer.concept_type || '',
      subjectName: currentIsSource ? currentName : peerName,
      objectName: currentIsSource ? peerName : currentName,
      relationLabel: relationTypeLabel(rel),
      explanation: relationExplanation(rel),
      sourceKind: '正式关系',
      formal: true,
    })
  }
  for (const concept of props.relatedConcepts || []) {
    const relatedId = relatedConceptId(concept)
    if (!relatedId || relatedId === entryId.value) continue
    if (rows.some((item) => item.entryId === relatedId)) continue
    const relatedName = concept.target_title || concept.canonical_name || concept.title || concept.name || relatedId
    rows.push({
      entryId: relatedId,
      name: relatedName,
      type: concept.concept_type || concept.target_subtype || '',
      subjectName: entry.value?.canonical_name || entryId.value,
      objectName: relatedName,
      relationLabel: '同主题邻近',
      explanation: concept.relation_reason || concept.reason || '暂无正式关系说明。',
      sourceKind: '同主题邻近',
      formal: false,
    })
  }
  const graphRows = [
    ...graphNodes.value
      .filter((node) => nodeType(node) === 'related_concept')
      .map((node) => ({
        entryId: node.entry_id || node.ref_id || node.id?.replace(/^concept:/, '') || '',
        name: node.label || node.ref_id || node.id,
        type: node.concept_type || '',
        subjectName: entry.value?.canonical_name || entryId.value,
        objectName: node.label || node.ref_id || node.id,
        relationLabel: graphRelationLabel(node),
        explanation: graphRelationExplanation(node),
        sourceKind: '来源图谱',
        formal: true,
      })),
    ...crossArticleLinks.value.map((link) => ({
      entryId: link.target_concept_id || link.entry_id || '',
      name: link.label || link.target_concept_id || link.entry_id,
      type: link.concept_type || '',
      subjectName: entry.value?.canonical_name || entryId.value,
      objectName: link.label || link.target_concept_id || link.entry_id,
      relationLabel: link.relation_type ? relationTypeLabel(link) : '跨文线索',
      explanation: relationExplanation(link),
      sourceKind: '跨文线索',
      formal: true,
    })),
  ]
  for (const row of graphRows) {
    if (!row.entryId || row.entryId === entryId.value) continue
    if (rows.some((item) => item.entryId === row.entryId)) continue
    rows.push(row)
  }
  return rows.slice(0, 6)
})

// Build a concept map for CrossRelationCard (entry_id -> {canonical_name, concept_type}).
// Pre-loaded from the global registry so peer concepts resolve to real names instead of
// raw IDs. Current entry + any relation-embedded peer info layered on top as a safety net.
const conceptMap = computed(() => {
  const map = { ...entryIndex.value }
  if (entry.value) map[entry.value.entry_id] = entry.value
  for (const rel of allRelations.value) {
    if (rel.source_entry && !map[rel.source_entry.entry_id]) {
      map[rel.source_entry.entry_id] = rel.source_entry
    }
    if (rel.target_entry && !map[rel.target_entry.entry_id]) {
      map[rel.target_entry.entry_id] = rel.target_entry
    }
  }
  return map
})

function formatPercent(value) {
  if (typeof value !== 'number') return value || 'unknown'
  return `${Math.round(value * 100)}%`
}

function relationTypeLabel(relation) {
  if (relation?.relation_label) return relation.relation_label
  if (relation?.edge_label) return relation.edge_label
  if (relation?.label && !relation?.target_concept_id) return relation.label
  if (compactRelationLabels[relation?.relation_type]) return compactRelationLabels[relation.relation_type]
  const typeLabel = typeOpts.find((item) => item.value === relation?.relation_type)?.label
  if (typeLabel) return typeLabel
  if (relation?.relation_type) return relation.relation_type
  if (relation?.type) return relation.type
  return '相关'
}

function relationExplanation(relation) {
  return relation?.summary
    || relation?.rationale
    || relation?.description
    || relation?.evidence
    || relation?.reason
    || relation?.source_excerpt
    || relation?.source_text
    || '暂无关系说明。'
}

function graphRelationLabel(node) {
  const edge = graphEdgeForRelatedNode(node)
  if (edge) return relationTypeLabel(edge)
  return node.relation_label || node.relation_type || '来源图谱'
}

function graphRelationExplanation(node) {
  const edge = graphEdgeForRelatedNode(node)
  return relationExplanation(edge || node)
}

function graphEdgeForRelatedNode(node) {
  const id = node?.id || node?.node_id || node?.ref_id || ''
  if (!id) return null
  return graphEdges.value.find((edge) => edge?.source === id || edge?.target === id) || null
}

function relatedConceptId(concept) {
  return concept?.entry_id || concept?.concept_id || concept?.target_id || concept?.id || ''
}

function nodeKey(node) {
  return node?.id || node?.node_id || node?.ref_id || node?.label
}

function nodeType(node) {
  return node?.type || node?.node_type || 'node'
}

function edgeKey(edge) {
  return edge?.id || edge?.edge_id || `${edge?.source || ''}:${edge?.target || ''}:${edge?.edge_type || edge?.type || ''}`
}

function edgeType(edge) {
  return edge?.type || edge?.edge_type || 'edge'
}

async function loadEntryIndex() {
  try {
    const res = await listRegistryConcepts()
    const map = {}
    for (const e of res.data?.entries || []) map[e.entry_id] = e
    entryIndex.value = map
  } catch (_e) { /* non-critical for page render */ }
}

async function loadEntry() {
  if (!entryId.value) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await getRegistryConcept(entryId.value)
    entry.value = res.data || null
    if (entry.value) emit('loaded', entry.value)
  } catch (e) {
    // Clear stale entry so live↔demo switches don't leave the previous
    // concept's data visible alongside the new error.
    entry.value = null
    loadError.value = e.message || '加载条目失败'
  } finally {
    loading.value = false
  }
}

async function loadRelations() {
  if (!entryId.value) return
  relationsLoading.value = true
  try {
    const res = await listCrossRelations({ entry_id: entryId.value })
    // Backend returns data as a flat array under `data`, not `data.relations`.
    allRelations.value = Array.isArray(res.data) ? res.data : (res.data?.relations || [])
  } catch (_e) {
    allRelations.value = []
  } finally {
    relationsLoading.value = false
  }
}

async function loadMaterialGraph() {
  if (!entryId.value) return
  graphLoading.value = true
  graphError.value = ''
  try {
    const res = await getRegistryConceptGraph(entryId.value)
    const data = res.data || {}
    materialGraphSummary.value = {
      concept_id: data.concept_id || entryId.value,
      graph_status: data.graph_status || 'not_available',
      material_graph_id: data.material_graph_id || '',
      node_count: data.node_count || 0,
      edge_count: data.edge_count || 0,
      cross_article_link_count: data.cross_article_link_count || 0,
    }
    materialGraph.value = data.graph || null
  } catch (e) {
    materialGraph.value = null
    materialGraphSummary.value = {}
    graphError.value = e.message || 'KFC 来源图谱加载失败'
  } finally {
    graphLoading.value = false
  }
}

async function handleCreateGraphSnapshot() {
  graphSnapshotting.value = true
  graphError.value = ''
  try {
    const res = await createRegistryConceptGraphSnapshot(entryId.value, { actor: 'human' })
    const data = res.data || {}
    materialGraphSummary.value = {
      concept_id: data.concept_id || entryId.value,
      graph_status: data.graph_status || 'snapshot_available',
      material_graph_id: data.material_graph_id || '',
      node_count: data.node_count || 0,
      edge_count: data.edge_count || 0,
      cross_article_link_count: data.cross_article_link_count || 0,
    }
    materialGraph.value = data.graph || null
    await loadEntry()
  } catch (e) {
    graphError.value = e.message || '生成 KFC 来源图谱失败'
  } finally {
    graphSnapshotting.value = false
  }
}

async function handleCreateGraphificationRequest() {
  graphRequesting.value = true
  graphError.value = ''
  try {
    const res = await createRegistryConceptGraphificationRequest(entryId.value, {
      reason: 'Request external cross-article graphification proposal for this KFC material graph.',
      requested_by: 'human',
    })
    const req = res.data || {}
    graphRequestMessage.value = `已写入外部图谱化请求 ${req.request_id || ''}，等待外部 runner/Codex 处理。`
    await Promise.all([loadEntry(), loadMaterialGraph()])
  } catch (e) {
    graphError.value = e.message || '写入外部图谱化请求失败'
  } finally {
    graphRequesting.value = false
  }
}

function articleHref(link) {
  return buildSourceArticleGraphHref(link, { from: 'registry' })
}

async function handleUnlink(link) {
  if (!confirm(`确定解绑项目 ${link.project_name || link.project_id} 的 ${link.concept_key}？`)) return
  try {
    await unlinkProjectConcept(entryId.value, {
      project_id: link.project_id,
      concept_key: link.concept_key,
    })
    await loadEntry()
  } catch (e) {
    alert('解绑失败: ' + (e.message || ''))
  }
}

async function handleReview(relationId, reviewStatus) {
  try {
    await updateCrossRelation(relationId, { review_status: reviewStatus })
    await loadRelations()
  } catch (e) {
    alert('审阅失败: ' + (e.message || ''))
  }
}

async function handleUpdateRelationType(relationId, relationType) {
  try {
    await updateCrossRelation(relationId, { relation_type: relationType })
    await loadRelations()
  } catch (e) {
    alert('关系类型更新失败: ' + (e.message || ''))
  }
}

async function handleDelete(relationId) {
  if (!confirm('确定删除此跨文关系？')) return
  try {
    await deleteCrossRelation(relationId)
    await loadRelations()
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
  }
}

async function handleDeleteEntry() {
  if (!entry.value) return
  if (!confirm(`确定删除条目 "${entry.value.canonical_name}"？相关链接会一并丢失。`)) return
  try {
    await deleteRegistryConcept(entryId.value)
    router.push('/workspace/registry')
  } catch (e) {
    alert('删除失败: ' + (e.message || ''))
  }
}

function navigateToConcept(targetEntryId) {
  if (!targetEntryId || targetEntryId === entryId.value) return
  if (embedded.value) {
    emit('navigate', targetEntryId)
    return
  }
  router.push(`/workspace/entry/${targetEntryId}`)
}

function openInRegistry() {
  router.push(`/workspace/registry?tab=concepts&select=${entryId.value}`)
}

onMounted(async () => {
  await Promise.all([loadEntry(), loadRelations(), loadEntryIndex(), loadMaterialGraph()])
})

watch(entryId, async (next) => {
  if (!next) return
  if (embedded.value) {
    embeddedOpenSections.sourceLinks = true
    embeddedOpenSections.relations = true
    embeddedOpenSections.materialGraph = true
  }
  await Promise.all([loadEntry(), loadRelations(), loadMaterialGraph()])
})

// Reload entry + relations when live/demo flips.
watch(appMode, async () => {
  await Promise.all([loadEntry(), loadRelations(), loadEntryIndex(), loadMaterialGraph()])
})
</script>

<style scoped>
.concept-wrap {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.concept-wrap.embedded {
  max-width: none;
  margin: 0;
  gap: 16px;
}
.concept-embedded-shell {
  display: block;
}
.concept-wrap.embedded .concept-title {
  font-size: 20px;
}
.concept-compact-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.compact-concept-header,
.compact-section {
  border: 1px solid #d4dce8;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
}
.compact-concept-header {
  background: #fbfcfe;
}
.compact-title-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}
.compact-concept-title {
  margin: 0;
  color: #181818;
  font-size: 20px;
  line-height: 1.25;
}
.compact-context-list,
.compact-evidence-list {
  display: grid;
  gap: 8px;
  margin: 10px 0 0;
}
.compact-context-list div,
.compact-evidence-list div {
  min-width: 0;
}
.compact-context-list dt,
.compact-evidence-list dt {
  color: #6b7280;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.compact-context-list dd,
.compact-evidence-list dd {
  margin: 2px 0 0;
  color: #1f2937;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.compact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.compact-concept-desc {
  margin: 10px 0 0;
  color: #3f4552;
  font-size: 13px;
  line-height: 1.55;
}
.compact-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.compact-section-head h2 {
  margin: 0;
  color: #181818;
  font-size: 15px;
}
.compact-section-head span {
  border-radius: 999px;
  background: #f3f4f7;
  color: #6b7280;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
}
.compact-related-list {
  display: grid;
  gap: 8px;
}
.compact-related-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 9px 10px;
  text-align: left;
  cursor: pointer;
}
.compact-related-row:hover {
  border-color: #a9bbd9;
  background: #f8fbff;
}
.compact-related-row--formal {
  border-color: #bfdbfe;
}
.compact-relation-kind {
  align-self: flex-start;
  border-radius: 999px;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 7px;
}
.compact-related-row--formal .compact-relation-kind {
  background: #eff6ff;
  color: #1d4ed8;
}
.compact-relation-edge {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
}
.compact-relation-edge strong {
  color: #1f2937;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.compact-relation-label {
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  padding: 2px 6px;
}
.compact-relation-arrow {
  color: #6b7280;
  font-size: 12px;
  font-weight: 800;
}
.compact-related-row p {
  margin: 0;
  color: #4b5563;
  font-size: 12px;
  line-height: 1.45;
}
.compact-related-row small {
  align-self: flex-start;
  color: #4a6fa5;
  font-size: 11px;
  font-weight: 800;
}
.compact-definition-section p {
  margin: 0;
  color: #374151;
  font-size: 13px;
  line-height: 1.55;
}
.compact-meta-section summary {
  cursor: pointer;
  color: #4b5563;
  font-size: 13px;
  font-weight: 800;
}
.compact-meta-list {
  margin-top: 10px;
}
.workbench-tabs {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 4px;
  padding: 6px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(8px);
}
.workbench-tab {
  border: 0;
  border-radius: 6px;
  padding: 8px 12px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.workbench-tab.active {
  background: #eff6ff;
  color: #1d4ed8;
}
.overview-section {
  border-color: #bfdbfe;
  background: #f8fbff;
}
.overview-definition {
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.65;
}
.overview-grid,
.governance-grid,
.role-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.overview-grid > div,
.project-role-panel,
.semantic-chain-card {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.72);
}
.overview-grid span,
.semantic-chain-card small {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 800;
}
.overview-grid strong,
.semantic-chain-card strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
}
.overview-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.technical-trace-details,
.danger-zone {
  border: 1px solid var(--border-muted);
  border-radius: 8px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.58);
}
.technical-trace-details summary,
.danger-zone summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 900;
}
.identity-grid.compact {
  margin-top: 10px;
}
.semantic-chain-card {
  margin-bottom: 12px;
}
.project-role-panel {
  margin-top: 14px;
}
.project-role-panel p {
  margin: 6px 0 10px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}
.governance-section {
  border-color: #fecaca;
}
.danger-zone {
  margin-top: 14px;
  border-color: #fecaca;
  background: #fffafa;
}
.danger-zone p {
  color: #991b1b;
  font-size: 13px;
}
.concept-wrap.embedded .summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.concept-wrap.embedded .summary-card,
.concept-wrap.embedded .section {
  border-radius: 10px;
  padding: 12px;
}
.concept-wrap.embedded .link-row {
  align-items: flex-start;
  flex-direction: column;
  gap: 8px;
}
.concept-wrap.embedded .link-list,
.concept-wrap.embedded .xrel-list {
  max-height: 360px;
  overflow: auto;
  padding-right: 2px;
}
.section-toggle {
  margin-left: auto;
}
.compact-note {
  padding: 4px 0 0;
}

.topbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #4a6fa5;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover { background: #f0f4ff; border-color: #a9bbd9; }

/* Header */
.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #4a6fa5;
  font-weight: 700;
}
.legacy-canonical-badge {
  margin-top: 2px;
  color: #6b7280;
  font-size: 10px;
}
.workbench-title {
  margin: 4px 0 0;
  color: #1f2937;
  font-size: 18px;
}
.concept-title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin: 6px 0;
}
.concept-title { margin: 0; font-size: 28px; color: #181818; }
.concept-type-chip {
  font-size: 12px;
  color: #4a6fa5;
  background: #f0f4ff;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid #d4dce8;
}
.concept-desc {
  font-size: 14px;
  line-height: 1.65;
  color: #3f4552;
  margin: 6px 0 10px;
}
.concept-desc-empty {
  font-size: 13px;
  color: #a5a9b3;
  font-style: italic;
  margin: 6px 0 10px;
}

.alias-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.alias-label {
  font-size: 12px;
  font-weight: 700;
  color: #6d6256;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.alias-chip {
  font-size: 12px;
  color: #5a6573;
  background: #f5f8ff;
  border: 1px solid #d4dce8;
  padding: 3px 9px;
  border-radius: 6px;
}
.workbench-status-panel {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.workbench-status-panel > div {
  border: 1px solid #d4dce8;
  border-radius: 10px;
  padding: 10px;
  background: #f8fafc;
}
.workbench-status-panel strong,
.workbench-status-panel small {
  display: block;
}
.workbench-status-panel strong {
  margin-top: 3px;
  color: #1f2937;
  font-size: 13px;
}
.workbench-status-panel small {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
}
.status-label {
  color: #4a6fa5;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Summary */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.identity-grid,
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.identity-grid {
  margin: 0;
}
.identity-grid div,
.evidence-grid > div,
.project-usage-note,
.neighborhood-summary {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 9px;
  background: #fff;
}
.identity-grid dt,
.evidence-grid span {
  color: #6b7280;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.identity-grid dd {
  margin: 4px 0 0;
  color: #1f2937;
  font-size: 13px;
}
.evidence-grid strong,
.evidence-grid p {
  display: block;
  margin: 4px 0 0;
  color: #1f2937;
  font-size: 13px;
  line-height: 1.55;
}
.evidence-grid .wide {
  grid-column: 1 / -1;
}
.source-link-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.source-link-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 9px 10px;
  background: #fff;
}
.source-link-card.active {
  border-color: #e3b873;
  background: #fffaf0;
}
.source-link-card span,
.source-link-card strong,
.source-link-card small {
  display: block;
}
.source-link-card span {
  color: #9a5a12;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.source-link-card strong {
  margin-top: 4px;
  color: #1f2937;
  font-size: 13px;
}
.source-link-card small {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
}
.source-link-quote {
  margin: 8px 0 0;
  color: #374151;
  font-size: 12px;
  line-height: 1.55;
}
.source-locate-link {
  display: inline-block;
  margin-top: 9px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}
.source-locate-link:hover {
  text-decoration: underline;
}
.project-usage-note {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #4b5563;
  font-size: 12px;
}
.project-usage-note strong {
  color: #1f2937;
}
.neighborhood-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #4b5563;
  font-size: 12px;
}
.neighborhood-summary span {
  border-radius: 999px;
  padding: 3px 8px;
  background: #f3f4f6;
}
.summary-card {
  border: 1px solid #d4dce8;
  border-radius: 14px;
  padding: 14px 16px;
  background: #fff;
}
.card-title {
  font-size: 12px;
  font-weight: 700;
  color: #6d6256;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #181818;
}

/* Sections */
.section {
  border: 1px solid #d4dce8;
  border-radius: 16px;
  padding: 20px;
  background: #fff;
}
.section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #181818;
}
.section-counter {
  font-size: 12px;
  color: #9a8d7c;
  background: #f3f4f7;
  padding: 2px 8px;
  border-radius: 10px;
}

.empty-note {
  color: #9a8d7c;
  font-size: 13px;
  padding: 12px 4px;
}
.error-card {
  border-color: #e2b0a8;
  background: #fff8f6;
  color: #c62828;
}
.state-card {
  border: 1px solid #d4dce8;
  border-radius: 14px;
  padding: 14px 18px;
}

/* Links */
.link-list { display: flex; flex-direction: column; gap: 10px; }
.link-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  background: #fafbfc;
}
.link-main { display: flex; align-items: center; gap: 8px; font-size: 13px; min-width: 0; }
.link-project { font-weight: 600; color: #1d1d1d; }
.link-arrow { color: #9a8d7c; }
.link-concept {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #5a6573;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link-actions { display: flex; gap: 6px; flex-shrink: 0; }

.concept-provenance {
  margin-top: 14px;
  border: 1px solid #dfe6ee;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fafbfc;
}
.concept-provenance summary {
  cursor: pointer;
  color: #5a6573;
  font-size: 13px;
  font-weight: 700;
}
.concept-provenance dl {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin: 10px 0 0;
}
.concept-provenance dt {
  color: #8b94a1;
  font-size: 11px;
}
.concept-provenance dd {
  margin: 2px 0 0;
  color: #303846;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.btn-sm {
  display: inline-flex;
  align-items: center;
  padding: 5px 11px;
  border-radius: 8px;
  border: 1px solid #d4dce8;
  background: #fff;
  color: #4a6fa5;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
}
.btn-sm:hover { background: #f0f4ff; border-color: #a9bbd9; }
.btn-danger { color: #c62828; border-color: #ef9a9a; }
.btn-danger:hover { background: #ffebee; }

/* Filters */
.xrel-filters {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef1f5;
}
.filter-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.filter-chip {
  padding: 4px 10px;
  border: 1px solid #d4dce8;
  border-radius: 999px;
  background: #fff;
  color: #6d6256;
  font-size: 12px;
  cursor: pointer;
}
.filter-chip.active {
  background: #4a6fa5;
  color: #fff;
  border-color: #4a6fa5;
}
.filter-select {
  padding: 5px 10px;
  border: 1px solid #d4dce8;
  border-radius: 8px;
  background: #fff;
  font-size: 12px;
}

.xrel-list { display: flex; flex-direction: column; gap: 10px; }

.concept-actions {
  display: flex;
  gap: 10px;
  padding-top: 8px;
}

.material-graph-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef1f5;
}
.graph-metrics,
.graph-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.graph-metrics span,
.cross-link-strip span {
  display: inline-flex;
  align-items: center;
  border: 1px solid #d4dce8;
  border-radius: 999px;
  background: #f7f9fc;
  color: #4f5a69;
  font-size: 12px;
  padding: 4px 9px;
}
.graph-boundary-note {
  border: 1px solid #d4dce8;
  border-left: 3px solid #4a6fa5;
  border-radius: 8px;
  background: #f7f9ff;
  color: #4f5a69;
  font-size: 12px;
  line-height: 1.55;
  margin: 12px 0;
  padding: 8px 10px;
}
.material-graph-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.graph-source-card {
  border: 1px solid #dfe6ee;
  border-radius: 10px;
  background: #fafbfc;
  padding: 12px;
}
.source-title {
  font-size: 13px;
  font-weight: 700;
  color: #303846;
  margin-bottom: 6px;
}
.graph-source-card p {
  margin: 0;
  color: #303846;
  font-size: 13px;
  line-height: 1.6;
}
.graph-source-card small {
  display: block;
  color: #8b94a1;
  font-size: 11px;
  margin-top: 8px;
  overflow-wrap: anywhere;
}
.linked-source-slices {
  display: grid;
  gap: 8px;
}
.linked-source-slices > strong {
  color: #303846;
  font-size: 13px;
}
.linked-source-slice {
  border: 1px solid #d8eadf;
  border-radius: 8px;
  background: #f6fbf7;
  padding: 10px;
}
.linked-source-slice span {
  display: block;
  color: #4f5a69;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
}
.linked-source-slice p {
  color: #26332c;
  font-size: 13px;
  line-height: 1.55;
  margin: 0;
}
.linked-source-slice small {
  color: #66746c;
  display: block;
  font-size: 11px;
  line-height: 1.45;
  margin-top: 6px;
}
.graph-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.graph-columns h3 {
  color: #303846;
  font-size: 13px;
  margin: 0 0 8px;
}
.graph-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.graph-list li {
  display: flex;
  gap: 8px;
  align-items: baseline;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  background: #fff;
  padding: 8px 10px;
  min-width: 0;
}
.graph-list strong {
  color: #303846;
  font-size: 12px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.node-type {
  flex-shrink: 0;
  color: #6d6256;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.cross-link-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.request-note {
  border: 1px solid #cde7d3;
  border-radius: 8px;
  background: #f4fbf5;
  color: #2e7d32;
  font-size: 12px;
  margin: 0;
  padding: 8px 10px;
}
.error-text { color: #c62828; }

@media (max-width: 760px) {
  .summary-grid,
  .concept-wrap.embedded .summary-grid,
  .graph-columns {
    grid-template-columns: 1fr;
  }
}
</style>
