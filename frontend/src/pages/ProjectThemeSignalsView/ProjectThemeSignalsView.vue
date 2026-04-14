<template>
  <section class="signals-view">
    <header class="signals-head">
      <div class="head-text">
        <div class="section-badge">PROJECT THEME SIGNALS</div>
        <p class="section-copy">
          本项目的概念在哪些全局主题下参与。想治理主题本身（新建、合并、分拆）请去
          <router-link to="/workspace/themes" class="inline-link">主题枢纽</router-link>。
        </p>
      </div>
      <div class="head-stats">
        <div class="stat-pill">
          <span class="pill-label">本项目概念</span>
          <span class="pill-value">{{ projectConceptCount }}</span>
        </div>
        <div class="stat-pill">
          <span class="pill-label">参与主题</span>
          <span class="pill-value">{{ participatingThemes.length }}</span>
        </div>
        <div class="stat-pill">
          <span class="pill-label">未归类概念</span>
          <span class="pill-value" :class="{ warn: orphanConcepts.length > 0 }">{{ orphanConcepts.length }}</span>
        </div>
      </div>
    </header>

    <div v-if="loading" class="state-card">加载中...</div>
    <div v-else-if="loadError" class="state-card error-card">{{ loadError }}</div>

    <template v-else>
      <!-- Participating themes -->
      <section v-if="participatingThemes.length" class="block">
        <div class="block-head">
          <h2 class="block-title">本项目参与的主题</h2>
          <span class="block-hint">按本项目贡献概念数排序</span>
        </div>
        <div class="theme-grid">
          <article
            v-for="t in participatingThemes"
            :key="t.theme_id"
            class="theme-card"
          >
            <div class="card-head">
              <h3 class="theme-name">{{ t.name }}</h3>
              <span class="theme-status" :class="t.status">{{ t.status }}</span>
            </div>
            <p v-if="t.description" class="theme-desc">{{ t.description }}</p>

            <div class="coverage">
              <div class="coverage-bar">
                <div class="coverage-fill" :style="{ width: t.coveragePercent + '%' }" />
              </div>
              <span class="coverage-text">
                <strong>{{ t.projectConceptCount }}</strong>
                / {{ t.totalConceptCount }} 概念来自本项目 ({{ t.coveragePercent }}%)
              </span>
            </div>

            <div v-if="t.projectConcepts.length" class="project-concepts">
              <div class="pc-label">本项目贡献的概念</div>
              <div class="pc-chips">
                <router-link
                  v-for="c in t.projectConcepts.slice(0, 6)"
                  :key="c.entry_id"
                  :to="`/workspace/entry/${c.entry_id}`"
                  class="pc-chip"
                  :title="c.canonical_name"
                >{{ c.canonical_name }}</router-link>
                <span v-if="t.projectConcepts.length > 6" class="pc-more">+{{ t.projectConcepts.length - 6 }}</span>
              </div>
            </div>

            <div class="card-actions">
              <router-link :to="`/workspace/themes/${t.theme_id}`" class="btn-sm primary">进入主题全景 →</router-link>
            </div>
          </article>
        </div>
      </section>

      <section v-else class="block empty-block">
        <div class="empty-icon">🧵</div>
        <div class="empty-title">本项目尚未参与任何全局主题</div>
        <p class="empty-body">
          本项目的概念还没有被归到全局主题下。可以去
          <router-link to="/workspace/themes" class="inline-link">主题枢纽</router-link>
          手动创建并绑定，或在
          <router-link to="/workspace/auto" class="inline-link">自动处理</router-link>
          里让 pipeline 提议归类。
        </p>
      </section>

      <!-- Orphan concepts (this project's concepts not in any theme) -->
      <section v-if="orphanConcepts.length" class="block orphan-block">
        <div class="block-head">
          <h2 class="block-title">本项目未归类的概念</h2>
          <span class="block-hint">{{ orphanConcepts.length }} 个，尚未归入任何全局主题</span>
        </div>
        <div class="orphan-chips">
          <router-link
            v-for="c in orphanConcepts"
            :key="c.entry_id"
            :to="`/workspace/entry/${c.entry_id}`"
            class="orphan-chip"
            :title="c.canonical_name"
          >
            <span class="orphan-type">[{{ c.concept_type }}]</span>
            {{ c.canonical_name }}
          </router-link>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { listRegistryConcepts } from '../../services/api/registryApi'
import { listGlobalThemes } from '../../services/api/themeApi'

const props = defineProps({
  project: { type: Object, default: null },
  // WorkspacePage passes these; we don't use them here but accept to avoid warnings.
  graphData: { type: Object, default: null },
  phase1TaskResult: { type: Object, default: null },
  refreshing: { type: Boolean, default: false },
  embedded: { type: Boolean, default: false },
})

const allEntries = ref([])
const allThemes = ref([])
const loading = ref(false)
const loadError = ref('')

const projectId = computed(() => props.project?.project_id || '')

// Entries that have a source_link pointing to this project.
const projectEntries = computed(() => {
  if (!projectId.value) return []
  return allEntries.value.filter((e) =>
    (e.source_links || []).some((link) => link.project_id === projectId.value)
  )
})

const projectConceptCount = computed(() => projectEntries.value.length)
const projectEntryIdSet = computed(() => new Set(projectEntries.value.map((e) => e.entry_id)))

// Build "themes this project participates in" with per-theme coverage stats.
// A theme "participates" when at least one of its member concepts has a
// source_link pointing to this project. Ranked by project contribution count.
const participatingThemes = computed(() => {
  if (!projectId.value) return []
  const entryMap = Object.fromEntries(allEntries.value.map((e) => [e.entry_id, e]))

  const enriched = []
  for (const theme of allThemes.value) {
    const memberIds = extractMemberIds(theme)
    const projectMembers = memberIds.filter((id) => projectEntryIdSet.value.has(id))
    if (projectMembers.length === 0) continue
    const projectConcepts = projectMembers
      .map((id) => entryMap[id])
      .filter(Boolean)
    const total = memberIds.length
    enriched.push({
      ...theme,
      totalConceptCount: total,
      projectConceptCount: projectMembers.length,
      coveragePercent: total > 0 ? Math.round((projectMembers.length / total) * 100) : 0,
      projectConcepts,
    })
  }
  enriched.sort((a, b) => b.projectConceptCount - a.projectConceptCount)
  return enriched
})

// Project concepts that aren't in any global theme.
const orphanConcepts = computed(() => {
  const participatingEntryIds = new Set()
  for (const theme of allThemes.value) {
    for (const id of extractMemberIds(theme)) participatingEntryIds.add(id)
  }
  return projectEntries.value.filter((e) => !participatingEntryIds.has(e.entry_id))
})

function extractMemberIds(theme) {
  // Theme schema: concept_memberships can be [{ entry_id, role, ... }] OR
  // concept_entry_ids: [id, id]. Handle both for forward compat.
  if (Array.isArray(theme.concept_memberships)) {
    return theme.concept_memberships
      .filter((m) => m?.role !== 'candidate') // active members only
      .map((m) => m.entry_id)
      .filter(Boolean)
  }
  if (Array.isArray(theme.concept_entry_ids)) return theme.concept_entry_ids
  return []
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [entryRes, themeRes] = await Promise.all([
      listRegistryConcepts(),
      listGlobalThemes(),
    ])
    allEntries.value = entryRes.data?.entries || []
    allThemes.value = themeRes.data?.themes || []
  } catch (e) {
    loadError.value = e.message || '加载主题线索失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
watch(projectId, (next, prev) => {
  if (next && next !== prev) loadAll()
})
</script>

<style scoped>
.signals-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.signals-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}
.section-badge {
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #4a6fa5;
  font-weight: 700;
}
.section-copy {
  margin: 6px 0 0;
  color: #62584d;
  font-size: 13px;
  line-height: 1.6;
  max-width: 680px;
}
.inline-link { color: #4a6fa5; text-decoration: underline; }

.head-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.stat-pill {
  display: inline-flex;
  flex-direction: column;
  padding: 8px 14px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #eadfcb;
  min-width: 90px;
}
.pill-label {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #9a8d7c;
  font-weight: 700;
}
.pill-value {
  font-size: 20px;
  font-weight: 700;
  color: #1d1d1d;
  margin-top: 2px;
}
.pill-value.warn { color: #e65100; }

.state-card {
  border: 1px solid #d4dce8;
  border-radius: 12px;
  padding: 14px 18px;
  background: #fff;
  color: #6d6256;
  font-size: 13px;
}
.error-card { border-color: #e2b0a8; background: #fff8f6; color: #c62828; }

.block {
  padding: 18px 20px;
  border: 1px solid #eadfcb;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.85);
}
.block-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
}
.block-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1d1d1d;
}
.block-hint {
  font-size: 12px;
  color: #9a8d7c;
}

.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}
.theme-card {
  border: 1px solid #eef1f5;
  border-radius: 14px;
  padding: 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
.theme-card:hover {
  border-color: #d8b079;
  box-shadow: 0 6px 14px rgba(159, 117, 51, 0.08);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.theme-name {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1d1d1d;
}
.theme-status {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f7;
  color: #6d6256;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.theme-status.active { background: #e8f5e9; color: #2e7d32; }
.theme-status.candidate { background: #fff3e0; color: #e65100; }

.theme-desc {
  margin: 0;
  font-size: 12px;
  color: #5a6573;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.coverage {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.coverage-bar {
  height: 6px;
  border-radius: 3px;
  background: #f3f4f7;
  overflow: hidden;
}
.coverage-fill {
  height: 100%;
  background: linear-gradient(90deg, #bf7d28 0%, #d8b079 100%);
  border-radius: 3px;
}
.coverage-text {
  font-size: 11px;
  color: #6d6256;
}
.coverage-text strong { color: #1d1d1d; font-weight: 700; }

.project-concepts {
  border-top: 1px solid #f3f4f7;
  padding-top: 10px;
}
.pc-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #9a6b2e;
  margin-bottom: 6px;
}
.pc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.pc-chip {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  background: #fff9ef;
  border: 1px solid #eadfcb;
  color: #3b342a;
  text-decoration: none;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-chip:hover { background: #fff3df; border-color: #d8b079; }
.pc-more {
  font-size: 11px;
  color: #9a8d7c;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
}
.btn-sm {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
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
.btn-sm.primary {
  background: #4a6fa5;
  border-color: #4a6fa5;
  color: #fff;
}
.btn-sm.primary:hover { background: #3c5d8a; border-color: #3c5d8a; }

/* Empty + orphan blocks */
.empty-block {
  text-align: center;
  padding: 40px 20px;
  border-style: dashed;
  background: rgba(255, 255, 255, 0.6);
}
.empty-icon { font-size: 32px; }
.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: #3b342a;
  margin: 8px 0 4px;
}
.empty-body {
  font-size: 13px;
  color: #62584d;
  margin: 0;
  max-width: 480px;
  margin-inline: auto;
  line-height: 1.6;
}

.orphan-block {
  background: linear-gradient(180deg, #fffbf0 0%, #fff8e8 100%);
  border-color: #e6d39b;
}
.orphan-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.orphan-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e6d39b;
  color: #77682a;
  text-decoration: none;
}
.orphan-chip:hover { background: #fff3df; border-color: #d8b079; color: #5a4e15; }
.orphan-type {
  font-size: 10px;
  color: #997200;
  font-family: 'JetBrains Mono', monospace;
}
</style>
