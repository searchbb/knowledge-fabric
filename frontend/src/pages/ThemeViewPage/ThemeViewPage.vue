<template>
  <AppShell :crumbs="crumbs">
    <template #topbar-actions>
      <CopyLinkButton />
      <a class="topbar-btn" :href="$route.fullPath" target="_blank" rel="noopener" title="在新页面打开">
        <span class="icon">↗</span><span class="label">新页</span>
      </a>
    </template>

  <section class="phase2-page">
    <div class="section-badge">THEME HUB</div>
    <h2 class="section-title">主题枢纽</h2>
    <p class="section-copy">
      全局知识域主题。每个主题是一个 hub 节点，连接来自不同文章的概念。
      用户可以创建/合并主题，auto-pipeline 会自动把概念归入已有主题。
    </p>

    <div v-if="error" class="state-card error-card">{{ error }}</div>

    <div class="hub-layout">
      <!-- Left: Theme list -->
      <aside class="theme-sidebar">
        <div class="sidebar-header">
          <div class="card-title">主题列表</div>
          <button class="btn-small" @click="showCreateModal = true">+ 新建主题</button>
        </div>
        <div v-if="loading" class="empty-note">加载中...</div>
        <div v-else-if="!themes.length" class="empty-note">
          暂无主题。点击"新建主题"创建第一个知识域。
        </div>
        <div v-else class="theme-list">
          <div
            v-for="t in themes"
            :key="t.theme_id"
            :class="['theme-item', selectedThemeId === t.theme_id ? 'theme-item-active' : '']"
            @click="selectTheme(t.theme_id)"
          >
            <div class="theme-item-name">{{ t.name }}</div>
            <div class="theme-item-meta">
              <span :class="['status-dot', t.status === 'active' ? 'dot-active' : 'dot-candidate']"></span>
              {{ t.status }} · {{ (t.concept_memberships || []).length }} 概念
            </div>
            <router-link
              :to="`/workspace/themes/${t.theme_id}`"
              class="enter-panorama-btn"
              @click.stop
            >进入全景 →</router-link>
          </div>
        </div>
      </aside>

      <!-- Center: Hub view for selected theme -->
      <main class="hub-center">
        <div v-if="!selectedThemeId" class="empty-hub">
          <p>← 选择一个主题查看 hub 视图</p>
        </div>
        <div v-else-if="hubLoading" class="empty-hub">加载中...</div>
        <div v-else-if="hubView" class="hub-content">
          <div class="hub-header">
            <h3 class="hub-title">{{ hubView.theme.name }}</h3>
            <span :class="['hub-status', hubView.theme.status === 'active' ? 'status-active' : 'status-candidate']">
              {{ hubView.theme.status }}
            </span>
            <router-link
              :to="`/workspace/themes/${hubView.theme.theme_id || selectedThemeId}`"
              class="enter-panorama-cta"
              title="进入主题全景页"
            >进入全景 →</router-link>
          </div>
          <p v-if="hubView.theme.description" class="hub-desc">{{ hubView.theme.description }}</p>
          <div v-if="hubView.theme.keywords?.length" class="hub-keywords">
            <span v-for="kw in hubView.theme.keywords" :key="kw" class="keyword-chip">{{ kw }}</span>
          </div>

          <div class="hub-stats">
            <span>{{ hubView.core_concepts.length }} 核心概念</span>
            <span>{{ hubView.candidate_concepts.length }} 待确认</span>
            <span>{{ (hubView.related_projects || []).length }} 篇文章</span>
          </div>

          <!-- Core concepts (members) -->
          <div v-if="hubView.core_concepts.length" class="concept-section">
            <div class="section-label">核心概念 (member)</div>
            <div class="concept-grid">
              <a
                v-for="c in hubView.core_concepts" :key="c.entry_id"
                class="concept-card member-card concept-link"
                :href="`/workspace/entry/${c.entry_id}`"
                target="_blank"
                :title="`新窗口查看概念详情：${c.canonical_name}`"
              >
                <div class="concept-name">{{ c.canonical_name }}</div>
                <div class="concept-meta">
                  <span class="concept-type">{{ c.concept_type }}</span>
                  <span class="concept-score">{{ (c.score * 100).toFixed(0) }}%</span>
                </div>
              </a>
            </div>
          </div>

          <!-- Candidate concepts -->
          <div v-if="hubView.candidate_concepts.length" class="concept-section">
            <div class="section-label">待确认概念 (candidate)</div>
            <div class="concept-grid">
              <div v-for="c in hubView.candidate_concepts" :key="c.entry_id" class="concept-card candidate-card">
                <a
                  class="concept-name concept-link"
                  :href="`/workspace/entry/${c.entry_id}`"
                  target="_blank"
                  :title="`新窗口查看概念详情：${c.canonical_name}`"
                >{{ c.canonical_name }}</a>
                <div class="concept-meta">
                  <span class="concept-type">{{ c.concept_type }}</span>
                  <span class="concept-score">{{ (c.score * 100).toFixed(0) }}%</span>
                </div>
                <div class="concept-actions">
                  <button class="btn-tiny btn-promote" @click.stop="doPromote(c.entry_id)">确认</button>
                  <button class="btn-tiny btn-reject" @click.stop="doReject(c.entry_id)">移除</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Related projects -->
          <div v-if="(hubView.related_projects || []).length" class="concept-section">
            <div class="section-label">相关文章</div>
            <div class="project-list">
              <div v-for="p in hubView.related_projects" :key="p.project_id" class="project-row">
                <span class="project-name">{{ p.project_name || p.project_id }}</span>
                <span class="project-count">{{ p.matched_concept_count }} 概念</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- Orphan concepts -->
    <article v-if="orphans.length" class="orphan-section">
      <div class="card-title">孤立概念 (未归入任何主题)</div>
      <div class="orphan-grid">
        <div v-for="o in orphans" :key="o.entry_id" class="orphan-chip">
          <span class="orphan-type">[{{ o.concept_type }}]</span>
          {{ o.canonical_name }}
        </div>
      </div>
    </article>

    <!-- Create theme modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-card">
        <div class="card-title">新建全局主题</div>
        <p class="section-copy mini-copy">
          主题名应该是跨文章的知识域（如"AI融入工作"、"RAG技术栈"），不要用文章标题。
        </p>
        <input v-model="newTheme.name" class="form-input" placeholder="主题名（如：AI Agent 架构）" />
        <textarea v-model="newTheme.description" class="form-input form-textarea" placeholder="一句话描述（可选）" rows="2"></textarea>
        <input v-model="newTheme.keywords" class="form-input" placeholder="关键词（逗号分隔，如：agent,工作流,LLM）" />
        <div class="modal-actions">
          <button class="btn-small" @click="showCreateModal = false">取消</button>
          <button class="btn-primary" :disabled="!newTheme.name.trim()" @click="doCreate">创建</button>
        </div>
        <div v-if="createError" class="add-result err">{{ createError }}</div>
      </div>
    </div>
  </section>
  </AppShell>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import AppShell from '../../components/common/AppShell.vue'
import CopyLinkButton from '../../components/common/CopyLinkButton.vue'
import {
  listGlobalThemes,
  getThemeHubView,
  createGlobalTheme,
  promoteCandidate,
  rejectCandidate,
  getOrphans,
} from '../../services/api/themeApi'

const crumbs = [
  { label: '跨项目', to: '/workspace/registry' },
  { label: '主题枢纽' },
]

const themes = ref([])
const selectedThemeId = ref('')
const hubView = ref(null)
const orphans = ref([])
const loading = ref(false)
const hubLoading = ref(false)
const error = ref('')
const showCreateModal = ref(false)
const createError = ref('')
const newTheme = reactive({ name: '', description: '', keywords: '' })

async function loadThemes() {
  loading.value = true
  error.value = ''
  try {
    const res = await listGlobalThemes()
    const d = res.data || {}
    themes.value = d.themes || []
  } catch (e) {
    error.value = e.message || '加载主题失败'
  } finally {
    loading.value = false
  }
}

async function selectTheme(themeId) {
  selectedThemeId.value = themeId
  hubLoading.value = true
  hubView.value = null
  try {
    const res = await getThemeHubView(themeId)
    hubView.value = res.data || null
  } catch (e) {
    error.value = `加载 hub 视图失败: ${e.message}`
  } finally {
    hubLoading.value = false
  }
}

async function loadOrphansConcepts() {
  try {
    const res = await getOrphans(200)
    orphans.value = (res.data || {}).orphans || []
  } catch (_e) { /* non-critical */ }
}

async function doCreate() {
  createError.value = ''
  try {
    const kws = newTheme.keywords.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    await createGlobalTheme({
      name: newTheme.name.trim(),
      description: newTheme.description.trim(),
      keywords: kws,
    })
    showCreateModal.value = false
    newTheme.name = ''
    newTheme.description = ''
    newTheme.keywords = ''
    await loadThemes()
  } catch (e) {
    createError.value = e.response?.data?.error || e.message || '创建失败'
  }
}

async function doPromote(entryId) {
  if (!selectedThemeId.value) return
  try {
    await promoteCandidate(selectedThemeId.value, [entryId])
    await selectTheme(selectedThemeId.value)
  } catch (e) {
    error.value = `确认失败: ${e.message}`
  }
}

async function doReject(entryId) {
  if (!selectedThemeId.value) return
  try {
    await rejectCandidate(selectedThemeId.value, [entryId])
    await selectTheme(selectedThemeId.value)
  } catch (e) {
    error.value = `移除失败: ${e.message}`
  }
}

onMounted(async () => {
  await loadThemes()
  await loadOrphansConcepts()
})
</script>

<style scoped>
.topbar-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 8px;
  border: 1px solid #d4dce8; background: #fff;
  color: #4a6fa5; font-size: 12px; font-weight: 500;
  text-decoration: none; cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
.topbar-btn:hover { background: #f0f4ff; border-color: #a9bbd9; }

.enter-panorama-btn {
  display: inline-block; margin-top: 6px;
  font-size: 11px; color: #4a6fa5;
  text-decoration: none; font-weight: 600;
}
.enter-panorama-btn:hover { text-decoration: underline; }

.enter-panorama-cta {
  margin-left: auto;
  padding: 6px 14px;
  border-radius: 8px;
  background: #4a6fa5;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}
.enter-panorama-cta:hover { background: #3c5d8a; }

.phase2-page { max-width: 1400px; margin: 0 auto; }
.embedded-hint {
  font-size: 13px;
  color: #9a8d7c;
  margin: 0 0 14px;
}
.inline-link { color: #4a6fa5; text-decoration: underline; }
.section-badge { font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: #4a6fa5; font-weight: 700; }
.section-title { margin: 8px 0 4px; font-size: 28px; color: #181818; }
.section-copy { color: #5a6573; line-height: 1.6; margin-bottom: 16px; }
.mini-copy { font-size: 13px; margin: 4px 0 12px; }

.state-card { border: 1px solid #d4dce8; border-radius: 14px; padding: 14px 18px; margin-bottom: 16px; }
.error-card { border-color: #e2b0a8; background: #fff8f6; color: #c62828; }

.hub-layout { display: grid; grid-template-columns: 280px 1fr; gap: 20px; min-height: 400px; }

/* Sidebar */
.theme-sidebar {
  border: 1px solid #d4dce8;
  border-radius: 16px;
  background: linear-gradient(180deg, #fcfdff 0%, #f5f8ff 100%);
  padding: 16px;
}
.sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.card-title { font-weight: 700; color: #211c18; }
.theme-list { display: flex; flex-direction: column; gap: 6px; }
.theme-item {
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 100ms ease;
}
.theme-item:hover { background: #eef3ff; }
.theme-item-active { border-color: #4a6fa5; background: #e8efff; }
.theme-item-name { font-weight: 600; font-size: 14px; color: #1d1d1d; }
.theme-item-meta { font-size: 11px; color: #7a8090; margin-top: 2px; display: flex; align-items: center; gap: 4px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.dot-active { background: #2e7d32; }
.dot-candidate { background: #e65100; }

/* Hub center */
.hub-center {
  border: 1px solid #d4dce8;
  border-radius: 16px;
  background: #fff;
  padding: 20px;
}
.empty-hub { display: flex; align-items: center; justify-content: center; color: #7a8090; min-height: 300px; }
.empty-note { color: #7a8090; font-size: 13px; padding: 8px 0; }
.hub-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; }
.hub-title { font-size: 22px; color: #1b1712; margin: 0; }
.hub-status { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
.status-active { background: #e8f5e9; color: #2e7d32; }
.status-candidate { background: #fff3e0; color: #e65100; }
.hub-desc { color: #5a6573; font-size: 14px; margin: 4px 0 8px; }
.hub-keywords { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.keyword-chip {
  font-size: 11px; padding: 2px 8px; border-radius: 6px;
  background: #f0f4ff; color: #4a6fa5; border: 1px solid #d4dce8;
}
.hub-stats { display: flex; gap: 16px; font-size: 13px; color: #5a6573; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #eef1f5; }

/* Concept sections */
.concept-section { margin-bottom: 18px; }
.section-label { font-weight: 700; font-size: 13px; color: #4a6fa5; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.06em; }
.concept-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.concept-card {
  border: 1px solid #d4dce8; border-radius: 12px; padding: 12px 14px;
  background: #fcfdff;
}
.member-card { border-left: 3px solid #2e7d32; }
.candidate-card { border-left: 3px solid #e65100; }
.concept-name { font-weight: 600; font-size: 14px; color: #1d1d1d; }
.concept-link { text-decoration: none; color: inherit; display: block; cursor: pointer; }
.concept-link:hover { background: #f0f4ff; }
a.concept-link { color: inherit; }
.concept-meta { display: flex; gap: 8px; margin-top: 4px; font-size: 11px; }
.concept-type { color: #7a8090; }
.concept-score { color: #4a6fa5; font-weight: 600; }
.concept-actions { display: flex; gap: 6px; margin-top: 8px; }
.btn-tiny { font-size: 11px; padding: 3px 10px; border-radius: 6px; border: 1px solid #d4dce8; background: #fff; cursor: pointer; }
.btn-promote { color: #2e7d32; border-color: #a5d6a7; }
.btn-promote:hover { background: #e8f5e9; }
.btn-reject { color: #c62828; border-color: #ef9a9a; }
.btn-reject:hover { background: #ffebee; }

/* Projects */
.project-list { display: flex; flex-direction: column; gap: 6px; }
.project-row { display: flex; justify-content: space-between; padding: 8px 12px; border: 1px solid #eef1f5; border-radius: 8px; font-size: 13px; }
.project-name { color: #1d1d1d; }
.project-count { color: #4a6fa5; font-weight: 600; }

/* Orphans */
.orphan-section {
  margin-top: 20px;
  border: 1px solid #d4dce8;
  border-radius: 16px;
  padding: 16px;
  background: linear-gradient(180deg, #fffbf0 0%, #fff8e8 100%);
}
.orphan-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.orphan-chip {
  font-size: 12px; padding: 4px 10px; border-radius: 8px;
  background: #fff; border: 1px solid #e6d39b; color: #77682a;
}
.orphan-type { color: #997200; font-size: 10px; }

/* Modal */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3); display: flex; align-items: center;
  justify-content: center; z-index: 1000;
}
.modal-card {
  background: #fff; border-radius: 18px; padding: 24px;
  width: 420px; max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
.form-input {
  width: 100%; border: 1px solid #d4dce8; border-radius: 10px;
  padding: 10px 12px; font-size: 14px; font-family: inherit;
  margin-bottom: 10px; outline: none; box-sizing: border-box;
}
.form-input:focus { border-color: #4a6fa5; }
.form-textarea { resize: vertical; }
.btn-primary {
  background: #4a6fa5; color: #fff; border: none; border-radius: 12px;
  padding: 10px 18px; font-weight: 600; cursor: pointer; font-size: 14px;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-small {
  border: 1px solid #d4dce8; background: #fff; border-radius: 8px;
  padding: 6px 12px; font-size: 12px; cursor: pointer; color: #4a6fa5;
}
.add-result { margin-top: 10px; font-size: 13px; padding: 8px 12px; border-radius: 8px; }
.add-result.err { background: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }

@media (max-width: 800px) {
  .hub-layout { grid-template-columns: 1fr; }
}
</style>
