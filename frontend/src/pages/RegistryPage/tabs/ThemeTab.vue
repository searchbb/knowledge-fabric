<template>
  <div class="tab-content">
    <div class="toolbar">
      <button class="btn-primary" @click="openCreate">新建全局主题</button>
    </div>

    <div v-if="loading" class="state-card">正在加载全局主题...</div>
    <div v-else-if="error" class="state-card error-card">{{ error }}</div>

    <div v-else class="tab-layout">
      <!-- List -->
      <article class="card queue-card">
        <div class="card-header">
          <div class="card-title">全局主题</div>
          <div class="pill">{{ themes.length }}</div>
        </div>
        <div v-if="!themes.length" class="empty-state">暂无全局主题</div>
        <div v-else class="candidate-list">
          <button
            v-for="t in themes"
            :key="t.theme_id"
            class="candidate-button"
            :class="{ active: t.theme_id === selectedId }"
            @click="selectTheme(t)"
          >
            <div class="candidate-topline">
              <span class="candidate-name">{{ t.name }}</span>
              <span class="candidate-status">{{ t.source_project_clusters?.length || 0 }} 项目</span>
            </div>
            <div class="candidate-meta">
              {{ t.concept_entry_ids?.length || 0 }} 概念 · {{ t.status }}
            </div>
          </button>
        </div>
      </article>

      <!-- Detail -->
      <article class="card detail-card">
        <template v-if="selected">
          <div class="card-header">
            <div>
              <div class="detail-kicker">Global Theme</div>
              <h3 class="detail-title">{{ selected.name }}</h3>
            </div>
            <span class="chip">{{ selected.status }}</span>
          </div>
          <p v-if="selected.description" class="section-copy mini-copy">{{ selected.description }}</p>

          <section class="detail-section">
            <div class="subsection-title">关联概念 ({{ selected.concept_entry_ids?.length || 0 }})</div>
            <div class="chip-wrap" v-if="selected.concept_entry_ids?.length">
              <span v-for="cid in selected.concept_entry_ids" :key="cid" class="chip soft chip-clickable">
                <a
                  :href="`/workspace/entry/${cid}`"
                  target="_blank"
                  class="chip-link"
                  :title="`新窗口查看概念详情：${resolveConceptLabel(cid)}`"
                >{{ resolveConceptLabel(cid) }}</a>
                <button class="chip-remove" @click.stop="handleDetachConcept(cid)" :title="`从主题移除 ${cid}`">×</button>
              </span>
            </div>
            <div v-else class="empty-note">未关联概念</div>
          </section>

          <section class="detail-section">
            <div class="subsection-title">项目簇链接 ({{ selected.source_project_clusters?.length || 0 }})</div>
            <div v-if="selected.source_project_clusters?.length" class="link-list">
              <div v-for="link in selected.source_project_clusters" :key="link.project_id + link.cluster_id" class="link-item">
                <span class="link-project">{{ link.cluster_name || link.cluster_id }}</span>
                <span class="link-concept">{{ link.project_id }}</span>
              </div>
            </div>
            <div v-else class="empty-note">未链接项目簇</div>
          </section>

          <div class="action-row">
            <button class="btn-small" @click="openEdit" :disabled="saving">编辑</button>
            <button class="btn-small btn-danger" @click="handleDelete" :disabled="saving">删除</button>
          </div>
        </template>
        <div v-else class="empty-state">选择左侧主题查看详情</div>
      </article>

      <!-- Action -->
      <article class="card action-card">
        <template v-if="panel === 'create'">
          <div class="card-title">新建全局主题</div>
          <div class="form-group">
            <label>名称</label>
            <input v-model="form.name" class="form-input" placeholder="主题名称" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="form.description" class="form-input" rows="3" />
          </div>
          <div class="action-row">
            <button class="btn-primary" @click="handleCreate" :disabled="saving || !form.name.trim()">{{ saving ? '...' : '创建' }}</button>
            <button class="btn-small" @click="closePanel">取消</button>
          </div>
        </template>

        <template v-else-if="panel === 'edit' && selected">
          <div class="card-title">编辑主题</div>
          <div class="form-group">
            <label>名称</label>
            <input v-model="editForm.name" class="form-input" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="editForm.description" class="form-input" rows="3" />
          </div>
          <div class="form-group">
            <label>状态</label>
            <select v-model="editForm.status" class="form-input">
              <option value="active">active</option>
              <option value="archived">archived</option>
            </select>
          </div>
          <div class="action-row">
            <button class="btn-primary" @click="handleEdit" :disabled="saving || !editForm.name.trim()">{{ saving ? '...' : '保存' }}</button>
            <button class="btn-small" @click="closePanel">取消</button>
          </div>
        </template>

        <template v-else-if="selected">
          <div class="card-title">关联概念</div>
          <p class="section-copy mini-copy">从全局注册表选择概念条目挂接到当前主题。</p>
          <div class="form-group">
            <label>注册表条目</label>
            <select v-model="attachEntryId" class="form-input">
              <option value="">— 选择 canonical 概念 —</option>
              <option
                v-for="e in availableEntries"
                :key="e.entry_id"
                :value="e.entry_id"
              >
                {{ e.canonical_name }} ({{ e.concept_type }})
              </option>
            </select>
          </div>
          <div class="action-row">
            <button
              class="btn-primary"
              @click="handleAttachConcept"
              :disabled="saving || !attachEntryId"
            >{{ saving ? '...' : '挂接概念' }}</button>
          </div>
          <div v-if="actionError" class="error-text">{{ actionError }}</div>
        </template>

        <template v-else>
          <div class="card-title">操作</div>
          <p class="section-copy mini-copy">选择主题后可编辑、删除或挂接概念。</p>
        </template>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import service from '../../../api/index'
import { registryStore, loadEntries } from '../../../stores/registryStore'

const themes = ref([])
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const selectedId = ref('')
const selected = ref(null)
const panel = ref('default') // 'default' | 'create' | 'edit'
const saving = ref(false)
const form = ref({ name: '', description: '' })
const editForm = ref({ name: '', description: '', status: 'active' })
const attachEntryId = ref('')

const availableEntries = computed(() => {
  const attached = new Set(selected.value?.concept_entry_ids || [])
  return (registryStore.entries || []).filter((e) => !attached.has(e.entry_id))
})

function resolveConceptLabel(entryId) {
  const entry = (registryStore.entries || []).find((e) => e.entry_id === entryId)
  return entry ? `${entry.canonical_name} (${entry.concept_type})` : entryId
}

async function loadThemes() {
  loading.value = true
  try {
    const res = await service({ url: '/api/registry/themes', method: 'get' })
    themes.value = res.data?.themes || []
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function selectTheme(t) {
  selectedId.value = t.theme_id
  selected.value = t
  panel.value = 'default'
  actionError.value = ''
  attachEntryId.value = ''
}

function openCreate() {
  panel.value = 'create'
  form.value = { name: '', description: '' }
  actionError.value = ''
}

function openEdit() {
  if (!selected.value) return
  panel.value = 'edit'
  editForm.value = {
    name: selected.value.name || '',
    description: selected.value.description || '',
    status: selected.value.status || 'active',
  }
  actionError.value = ''
}

function closePanel() {
  panel.value = 'default'
  actionError.value = ''
}

async function handleCreate() {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    const res = await service({
      url: '/api/registry/themes', method: 'post',
      data: { name: form.value.name, description: form.value.description },
    })
    const created = res.data
    themes.value.unshift(created)
    selectTheme(created)
  } catch (e) {
    actionError.value = e.message || '创建失败'
  } finally {
    saving.value = false
  }
}

async function handleEdit() {
  if (!selected.value) return
  saving.value = true
  try {
    const res = await service({
      url: `/api/registry/themes/${selected.value.theme_id}`,
      method: 'put',
      data: {
        name: editForm.value.name,
        description: editForm.value.description,
        status: editForm.value.status,
      },
    })
    const updated = res.data
    const idx = themes.value.findIndex((t) => t.theme_id === updated.theme_id)
    if (idx !== -1) themes.value[idx] = updated
    selected.value = updated
    panel.value = 'default'
  } catch (e) {
    actionError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!selected.value) return
  if (!confirm(`确定删除主题 "${selected.value.name}" 吗？此操作不可撤销。`)) return
  saving.value = true
  try {
    await service({
      url: `/api/registry/themes/${selected.value.theme_id}`,
      method: 'delete',
    })
    themes.value = themes.value.filter((t) => t.theme_id !== selected.value.theme_id)
    selected.value = null
    selectedId.value = ''
    panel.value = 'default'
  } catch (e) {
    actionError.value = e.message || '删除失败'
  } finally {
    saving.value = false
  }
}

async function handleAttachConcept() {
  if (!selected.value || !attachEntryId.value) return
  saving.value = true
  try {
    const res = await service({
      url: `/api/registry/themes/${selected.value.theme_id}/concepts:attach`,
      method: 'post',
      data: { concept_entry_ids: [attachEntryId.value] },
    })
    const updated = res.data
    const idx = themes.value.findIndex((t) => t.theme_id === updated.theme_id)
    if (idx !== -1) themes.value[idx] = updated
    selected.value = updated
    attachEntryId.value = ''
  } catch (e) {
    actionError.value = e.message || '挂接失败'
  } finally {
    saving.value = false
  }
}

async function handleDetachConcept(entryId) {
  if (!selected.value) return
  saving.value = true
  try {
    const res = await service({
      url: `/api/registry/themes/${selected.value.theme_id}/concepts:detach`,
      method: 'post',
      data: { concept_entry_ids: [entryId] },
    })
    const updated = res.data
    const idx = themes.value.findIndex((t) => t.theme_id === updated.theme_id)
    if (idx !== -1) themes.value[idx] = updated
    selected.value = updated
  } catch (e) {
    actionError.value = e.message || '移除失败'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadThemes()
  // Also preload registry entries so attach dropdown has options
  if (!registryStore.entries?.length) loadEntries()
})
</script>

<style scoped>
.tab-content { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.tab-layout { display: grid; grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(260px, 320px); gap: 16px; align-items: start; }
.card, .state-card { border: 1px solid #d4dce8; background: linear-gradient(180deg, #fcfdff 0%, #f5f8ff 100%); border-radius: 18px; padding: 18px; }
.error-card { border-color: #e2b0a8; background: #fff8f6; }
.card-title { font-weight: 700; color: #211c18; margin-bottom: 10px; }
.card-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.pill, .chip { display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; border: 1px solid #d4dce8; color: #4a6fa5; background: rgba(245, 248, 255, 0.95); font-size: 12px; font-weight: 600; }
.chip.soft { background: rgba(255, 255, 255, 0.72); color: #5a6573; gap: 6px; }
.chip-clickable { cursor: pointer; }
.chip-clickable:hover { background: #e8efff; }
.chip-link { text-decoration: none; color: inherit; }
.chip-link:hover { color: #2c5282; }
.chip-remove { background: transparent; border: none; color: #b94c4c; font-size: 14px; line-height: 1; cursor: pointer; padding: 0 2px; }
.chip-remove:hover { color: #7d2a2a; }
.chip-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.candidate-list { display: flex; flex-direction: column; gap: 10px; }
.candidate-button { width: 100%; text-align: left; border: 1px solid #d4dce8; background: rgba(255, 255, 255, 0.85); border-radius: 16px; padding: 14px; cursor: pointer; transition: border-color 140ms ease, transform 140ms ease; }
.candidate-button:hover, .candidate-button.active { border-color: #4a6fa5; transform: translateY(-1px); box-shadow: 0 10px 24px rgba(74, 111, 165, 0.08); }
.candidate-topline { display: flex; justify-content: space-between; gap: 12px; }
.candidate-name { color: #1e1813; font-weight: 700; }
.candidate-status, .candidate-meta { color: #5a6573; font-size: 13px; }
.detail-kicker, .subsection-title { color: #5a6573; font-size: 13px; }
.detail-title { margin: 6px 0 0; font-size: 24px; color: #1a1713; }
.detail-section { margin-top: 18px; }
.section-copy, .mini-copy { color: #5a6573; line-height: 1.6; font-size: 13px; margin: 0; }
.empty-state, .empty-note { color: #7a8090; font-size: 13px; line-height: 1.6; }
.link-list { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.link-item { display: flex; justify-content: space-between; align-items: center; gap: 10px; border: 1px solid #e4e8f0; border-radius: 12px; padding: 10px 12px; background: #fff; }
.link-project { font-weight: 600; color: #1d1d1d; font-size: 13px; }
.link-concept { color: #5a6573; font-size: 12px; flex: 1; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; font-weight: 600; color: #5a6573; margin-bottom: 4px; }
.form-input { width: 100%; border: 1px solid #d4dce8; border-radius: 8px; padding: 8px 10px; font-size: 13px; outline: none; box-sizing: border-box; font-family: inherit; }
.form-input:focus { border-color: #4a6fa5; }
.action-row { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
.btn-primary { background: #4a6fa5; color: #fff; border: none; border-radius: 12px; padding: 10px 18px; font-weight: 600; cursor: pointer; font-size: 14px; white-space: nowrap; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-small { border: 1px solid #d4dce8; background: #fff; border-radius: 8px; padding: 6px 12px; font-size: 12px; cursor: pointer; }
.btn-small:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-small.btn-danger { border-color: #e2b0a8; color: #b94c4c; }
.btn-small.btn-danger:hover { background: #fff5f3; }
.error-text { color: #b94c4c; font-size: 12px; margin-top: 8px; }
@media (max-width: 1240px) { .tab-layout { grid-template-columns: minmax(240px, 320px) minmax(0, 1fr); } .action-card { grid-column: span 2; } }
@media (max-width: 960px) { .tab-layout { grid-template-columns: 1fr; } .action-card { grid-column: auto; } }
</style>
