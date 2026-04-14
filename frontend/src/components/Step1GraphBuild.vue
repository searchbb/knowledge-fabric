<template>
  <div class="workbench-panel">
    <div class="scroll-container">
      <!-- Step 01: Ontology -->
      <div class="step-card" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">本体生成</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 0" class="badge success">已完成</span>
            <span v-else-if="currentPhase === 0" class="badge processing">生成中</span>
            <span v-else class="badge pending">等待</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/graph/ontology/generate</p>
          <p class="description">
            LLM分析文档内容与模拟需求，提取出现实种子，自动生成合适的本体结构
          </p>

          <!-- Loading / Progress -->
          <div v-if="currentPhase === 0 && ontologyProgress" class="progress-section">
            <div class="spinner-sm"></div>
            <span>{{ ontologyProgress.message || '正在分析文档...' }}</span>
          </div>

          <!-- Detail Overlay -->
          <div v-if="selectedOntologyItem" class="ontology-detail-overlay">
            <div class="detail-header">
               <div class="detail-title-group">
                  <span class="detail-type-badge">{{ selectedOntologyItem.itemType === 'entity' ? 'ENTITY' : 'RELATION' }}</span>
                  <span class="detail-name">{{ selectedOntologyItem.name }}</span>
               </div>
               <button class="close-btn" @click="selectedOntologyItem = null">×</button>
            </div>
            <div class="detail-body">
               <div class="detail-desc">{{ selectedOntologyItem.description }}</div>
               
               <!-- Attributes -->
               <div class="detail-section" v-if="selectedOntologyItem.attributes?.length">
                  <span class="section-label">ATTRIBUTES</span>
                  <div class="attr-list">
                     <div v-for="attr in selectedOntologyItem.attributes" :key="attr.name" class="attr-item">
                        <span class="attr-name">{{ attr.name }}</span>
                        <span class="attr-type">({{ attr.type }})</span>
                        <span class="attr-desc">{{ attr.description }}</span>
                     </div>
                  </div>
               </div>

               <!-- Examples (Entity) -->
               <div class="detail-section" v-if="selectedOntologyItem.examples?.length">
                  <span class="section-label">EXAMPLES</span>
                  <div class="example-list">
                     <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="example-tag">{{ ex }}</span>
                  </div>
               </div>

               <!-- Source/Target (Relation) -->
               <div class="detail-section" v-if="selectedOntologyItem.source_targets?.length">
                  <span class="section-label">CONNECTIONS</span>
                  <div class="conn-list">
                     <div v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="conn-item">
                        <span class="conn-node">{{ conn.source }}</span>
                        <span class="conn-arrow">→</span>
                        <span class="conn-node">{{ conn.target }}</span>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <!-- Generated Entity Tags -->
          <div v-if="projectData?.ontology?.entity_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED ENTITY TYPES</span>
            <div class="tags-list">
              <span 
                v-for="entity in projectData.ontology.entity_types" 
                :key="entity.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(entity, 'entity')"
              >
                {{ entity.name }}
              </span>
            </div>
          </div>

          <!-- Generated Relation Tags -->
          <div v-if="projectData?.ontology?.edge_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED RELATION TYPES</span>
            <div class="tags-list">
              <span 
                v-for="rel in projectData.ontology.edge_types" 
                :key="rel.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(rel, 'relation')"
              >
                {{ rel.name }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Graph Build -->
      <div class="step-card" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">GraphRAG构建</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 1" class="badge success">已完成</span>
            <span v-else-if="currentPhase === 1" class="badge processing">{{ buildProgress?.progress || 0 }}%</span>
            <span v-else class="badge pending">等待</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/graph/build</p>
          <p class="description">
            基于生成的本体，将文档自动分块后调用当前图谱 provider 构建知识图谱，并整理阅读骨架与阶段性诊断结果
          </p>

          <div v-if="buildProgress" class="build-progress-inline">
            <div class="build-progress-track">
              <div class="build-progress-fill" :style="{ width: `${buildProgress.progress || 0}%` }"></div>
            </div>
            <div class="build-progress-meta">
              <span class="build-progress-message">{{ buildProgress.message || '等待构建任务开始...' }}</span>
              <span class="build-progress-percent">{{ buildProgress.progress || 0 }}%</span>
            </div>
          </div>
          
          <!-- Stats Cards -->
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.nodes }}</span>
              <span class="stat-label">实体节点</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.edges }}</span>
              <span class="stat-label">关系边</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.types }}</span>
              <span class="stat-label">SCHEMA类型</span>
            </div>
          </div>

          <div v-if="shouldShowPhase1Diagnostics" class="phase1-diagnostics">
            <div class="diag-header">
              <span class="diag-title">PHASE-1 DIAGNOSTICS</span>
              <span v-if="phase1ContractVersion" class="diag-contract">{{ phase1ContractVersion }}</span>
            </div>

            <div class="diag-pill-row">
              <span class="diag-pill">
                Provider · {{ providerLabel }}
              </span>
              <span class="diag-pill" :class="statusToneClass(buildStatusMeta.tone)">
                构建 · {{ buildStatusMeta.label }}
              </span>
              <span class="diag-pill" :class="statusToneClass(readingStatusMeta.tone)">
                阅读骨架 · {{ readingStatusMeta.label }}
              </span>
            </div>

            <div class="diag-metrics-grid">
              <div class="diag-metric">
                <span class="diag-metric-label">文本块完成</span>
                <span class="diag-metric-value">{{ chunkProgressLabel }}</span>
              </div>
              <div class="diag-metric">
                <span class="diag-metric-label">成功率</span>
                <span class="diag-metric-value">{{ successRatioLabel }}</span>
              </div>
              <div class="diag-metric">
                <span class="diag-metric-label">重试次数</span>
                <span class="diag-metric-value">{{ retryCountLabel }}</span>
              </div>
              <div class="diag-metric">
                <span class="diag-metric-label">限流命中</span>
                <span class="diag-metric-value">{{ rateLimitLabel }}</span>
              </div>
            </div>

            <div v-if="fallbackSummary" class="diag-callout warning">
              {{ fallbackSummary }}
            </div>
            <div v-if="buildFailureReason" class="diag-callout error">
              {{ buildFailureReason }}
            </div>
            <div v-if="readingStatusReason" class="diag-callout muted">
              阅读骨架说明：{{ readingStatusReason }}
            </div>

            <div v-if="phase1Warnings.length" class="diag-warning-list">
              <div class="diag-warning-item" v-for="warning in phase1Warnings" :key="warning">
                {{ warning }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Complete -->
      <div class="step-card" :class="{ 'active': currentPhase === 2, 'completed': currentPhase >= 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">Phase-1 验收</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase >= 2" class="badge accent">已就绪</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">
            图谱与阅读骨架已生成。你可以先进入 Phase 2 工作台继续知识治理；如果要保留旧实验链，也可以进入旧环境搭建流程。
          </p>
          <div class="action-btn-row">
            <button
              class="action-btn workspace"
              :disabled="currentPhase < 2"
              @click="handleOpenWorkspace"
            >
              进入 Phase 2 工作台 ➝
            </button>
            <button 
              class="action-btn secondary" 
              :disabled="currentPhase < 2 || creatingSimulation"
              @click="handleEnterEnvSetup"
            >
              <span v-if="creatingSimulation" class="spinner-sm"></span>
              {{ creatingSimulation ? '创建中...' : '旧环境搭建流程（实验） ➝' }}
            </button>
          </div>
          <p class="legacy-note">
            兼容入口，仍依赖 legacy_zep 旧模拟链路，不属于 Phase 2 默认工作台主线。
          </p>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SYSTEM DASHBOARD</span>
        <span class="log-id">{{ projectData?.project_id || 'NO_PROJECT' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { createSimulation } from '../api/simulation'

const router = useRouter()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  buildError: { type: String, default: '' },
  graphData: Object,
  systemLogs: { type: Array, default: () => [] }
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const creatingSimulation = ref(false)

const handleOpenWorkspace = () => {
  if (!props.projectData?.project_id) {
    return
  }

  router.push({
    name: 'Workspace',
    params: {
      projectId: props.projectData.project_id,
      section: 'article',
    },
  })
}

// 进入环境搭建 - 创建 simulation 并跳转
const handleEnterEnvSetup = async () => {
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('缺少项目或图谱信息')
    return
  }
  
  creatingSimulation.value = true
  
  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true
    })
    
    if (res.success && res.data?.simulation_id) {
      // 跳转到 simulation 页面
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('创建模拟失败:', res.error)
      alert('创建模拟失败: ' + (res.error || '未知错误'))
    }
  } catch (err) {
    console.error('创建模拟异常:', err)
    alert('创建模拟异常: ' + err.message)
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const phase1Result = computed(() => props.buildProgress?.result || null)

const phase1ContractVersion = computed(() => phase1Result.value?.contract_version || '')

const phase1Diagnostics = computed(() => {
  const diagnostics = phase1Result.value?.diagnostics
  return diagnostics && typeof diagnostics === 'object' ? diagnostics : null
})

const phase1BuildOutcome = computed(() => {
  const outcome = phase1Result.value?.build_outcome
  return outcome && typeof outcome === 'object' ? outcome : null
})

const phase1ReadingStatus = computed(() => {
  const status = phase1Result.value?.reading_structure_status
  return status && typeof status === 'object' ? status : null
})

const providerLabel = computed(() => {
  const provider = phase1Result.value?.provider || phase1Diagnostics.value?.provider
  return provider ? String(provider).toUpperCase() : 'UNKNOWN'
})

const buildStatusMeta = computed(() => {
  const status = phase1BuildOutcome.value?.status || props.buildProgress?.status || ''
  switch (status) {
    case 'completed':
      return { label: '已完成', tone: 'success' }
    case 'completed_with_warnings':
      return { label: '完成但有告警', tone: 'warning' }
    case 'completed_with_fallback':
      return { label: 'Fallback 完成', tone: 'warning' }
    case 'failed':
      return { label: '失败', tone: 'error' }
    case 'processing':
    case 'pending':
      return { label: '处理中', tone: 'processing' }
    default:
      return { label: '等待结果', tone: 'muted' }
  }
})

const readingStatusMeta = computed(() => {
  const status = phase1ReadingStatus.value?.status || 'not_started'
  switch (status) {
    case 'generated':
      return { label: '已生成', tone: 'success' }
    case 'fallback':
      return { label: 'Fallback 生成', tone: 'warning' }
    case 'failed':
      return { label: '生成失败', tone: 'error' }
    case 'skipped':
      return { label: '已跳过', tone: 'muted' }
    default:
      return { label: '未开始', tone: 'muted' }
  }
})

const shouldShowPhase1Diagnostics = computed(() => {
  return Boolean(props.buildProgress || phase1Result.value || props.buildError)
})

const chunkProgressLabel = computed(() => {
  const total = phase1Diagnostics.value?.chunk_count || 0
  const processed = phase1Diagnostics.value?.processed_chunk_count || 0
  return total ? `${processed}/${total}` : '—'
})

const successRatioLabel = computed(() => {
  const ratio = phase1BuildOutcome.value?.success_ratio
  if (typeof ratio !== 'number') return '—'
  return `${Math.round(ratio * 100)}%`
})

const retryCountLabel = computed(() => `${phase1Diagnostics.value?.retry_count || 0}`)

const rateLimitLabel = computed(() => `${phase1Diagnostics.value?.rate_limit_hit_count || 0}`)

const fallbackSummary = computed(() => {
  if (!phase1Diagnostics.value?.fallback_graph_applied) return ''
  const mode = phase1Diagnostics.value?.fallback_graph_mode || 'heuristic_outline'
  const nodes = phase1Diagnostics.value?.fallback_graph_node_count || 0
  const edges = phase1Diagnostics.value?.fallback_graph_edge_count || 0
  return `已启用 fallback graph (${mode})，产出 ${nodes} 个节点 / ${edges} 条关系。`
})

const buildFailureReason = computed(() => {
  if (phase1BuildOutcome.value?.reason) return phase1BuildOutcome.value.reason
  if (buildStatusMeta.value.tone === 'error' && props.buildError) return props.buildError
  return ''
})

const readingStatusReason = computed(() => {
  const reason = phase1ReadingStatus.value?.reason || ''
  if (!reason) return ''
  if (phase1ReadingStatus.value?.status === 'generated') return ''
  return reason
})

const phase1Warnings = computed(() => {
  const warnings = phase1BuildOutcome.value?.warnings
  return Array.isArray(warnings) ? warnings : []
})

const statusToneClass = (tone) => `tone-${tone || 'muted'}`

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.workbench-panel {
  height: 100%;
  background-color: #FAFAFA;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-card {
  background: #FFF;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid #EAEAEA;
  transition: all 0.3s ease;
  position: relative; /* For absolute overlay */
}

.step-card.active {
  border-color: #FF5722;
  box-shadow: 0 4px 12px rgba(255, 87, 34, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
  color: #E0E0E0;
}

.step-card.active .step-num,
.step-card.completed .step-num {
  color: #000;
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.badge {
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.success { background: #E8F5E9; color: #2E7D32; }
.badge.processing { background: #FF5722; color: #FFF; }
.badge.accent { background: #FF5722; color: #FFF; }
.badge.pending { background: #F5F5F5; color: #999; }

.api-note {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #999;
  margin-bottom: 8px;
}

.description {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 16px;
}

.build-progress-inline {
  margin-bottom: 16px;
}

.build-progress-track {
  height: 8px;
  background: #F1F1F1;
  border-radius: 999px;
  overflow: hidden;
}

.build-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #FF5722 0%, #FF8A50 100%);
  border-radius: 999px;
  transition: width 0.25s ease;
}

.build-progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
  color: #555;
}

.build-progress-message {
  flex: 1;
  min-width: 0;
}

.build-progress-percent {
  font-family: 'JetBrains Mono', monospace;
  color: #111;
}

/* Step 01 Tags */
.tags-container {
  margin-top: 12px;
  transition: opacity 0.3s;
}

.tags-container.dimmed {
    opacity: 0.3;
    pointer-events: none;
}

.tag-label {
  display: block;
  font-size: 10px;
  color: #AAA;
  margin-bottom: 8px;
  font-weight: 600;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  background: #F5F5F5;
  border: 1px solid #EEE;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  color: #333;
  font-family: 'JetBrains Mono', monospace;
  transition: all 0.2s;
}

.entity-tag.clickable {
    cursor: pointer;
}

.entity-tag.clickable:hover {
    background: #E0E0E0;
    border-color: #CCC;
}

/* Ontology Detail Overlay */
.ontology-detail-overlay {
    position: absolute;
    top: 60px; /* Below header roughly */
    left: 20px;
    right: 20px;
    bottom: 20px;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(4px);
    z-index: 10;
    border: 1px solid #EAEAEA;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #EAEAEA;
    background: #FAFAFA;
}

.detail-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-type-badge {
    font-size: 9px;
    font-weight: 700;
    color: #FFF;
    background: #000;
    padding: 2px 6px;
    border-radius: 2px;
    text-transform: uppercase;
}

.detail-name {
    font-size: 14px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.close-btn {
    background: none;
    border: none;
    font-size: 18px;
    color: #999;
    cursor: pointer;
    line-height: 1;
}

.close-btn:hover {
    color: #333;
}

.detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}

.detail-desc {
    font-size: 12px;
    color: #444;
    line-height: 1.5;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px dashed #EAEAEA;
}

.detail-section {
    margin-bottom: 16px;
}

.section-label {
    display: block;
    font-size: 10px;
    font-weight: 600;
    color: #AAA;
    margin-bottom: 8px;
}

.attr-list, .conn-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.attr-item {
    font-size: 11px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: baseline;
    padding: 4px;
    background: #F9F9F9;
    border-radius: 4px;
}

.attr-name {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    color: #000;
}

.attr-type {
    color: #999;
    font-size: 10px;
}

.attr-desc {
    color: #555;
    flex: 1;
    min-width: 150px;
}

.example-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.example-tag {
    font-size: 11px;
    background: #FFF;
    border: 1px solid #E0E0E0;
    padding: 3px 8px;
    border-radius: 12px;
    color: #555;
}

.conn-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    padding: 6px;
    background: #F5F5F5;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
}

.conn-node {
    font-weight: 600;
    color: #333;
}

.conn-arrow {
    color: #BBB;
}

/* Step 02 Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  background: #F9F9F9;
  padding: 16px;
  border-radius: 6px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #000;
  font-family: 'JetBrains Mono', monospace;
}

.stat-label {
  font-size: 9px;
  color: #999;
  text-transform: uppercase;
  margin-top: 4px;
  display: block;
}

.phase1-diagnostics {
  margin-top: 16px;
  padding: 16px;
  border-radius: 8px;
  background: #FCFCFC;
  border: 1px solid #ECECEC;
}

.diag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.diag-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #999;
}

.diag-contract {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #666;
}

.diag-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.diag-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: #F3F3F3;
  color: #333;
  font-size: 11px;
  border: 1px solid #E8E8E8;
}

.tone-success {
  background: #E8F5E9;
  border-color: #CBE8CD;
  color: #23632B;
}

.tone-warning {
  background: #FFF3E0;
  border-color: #FFD7A6;
  color: #8F4B00;
}

.tone-error {
  background: #FDECEC;
  border-color: #F4C7C7;
  color: #A12626;
}

.tone-processing {
  background: #FFF0EB;
  border-color: #FFC7B8;
  color: #C7491E;
}

.tone-muted {
  background: #F3F3F3;
  border-color: #E8E8E8;
  color: #666;
}

.diag-metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.diag-metric {
  background: #FFF;
  border: 1px solid #EFEFEF;
  border-radius: 6px;
  padding: 10px 12px;
}

.diag-metric-label {
  display: block;
  font-size: 10px;
  color: #999;
  margin-bottom: 6px;
}

.diag-metric-value {
  display: block;
  font-size: 14px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: #111;
}

.diag-callout {
  margin-top: 12px;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 11px;
  line-height: 1.5;
}

.diag-callout.warning {
  background: #FFF7ED;
  color: #8F4B00;
  border: 1px solid #FFD7A6;
}

.diag-callout.error {
  background: #FEF2F2;
  color: #A12626;
  border: 1px solid #F5C2C7;
}

.diag-callout.muted {
  background: #F8F8F8;
  color: #555;
  border: 1px solid #ECECEC;
}

.diag-warning-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.diag-warning-item {
  font-size: 11px;
  color: #555;
  background: #FFF;
  border: 1px dashed #E6E6E6;
  border-radius: 6px;
  padding: 8px 10px;
}

/* Step 03 Button */
.action-btn-row {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: 12px;
}

.action-btn {
  width: 100%;
  background: #000;
  color: #FFF;
  border: none;
  padding: 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn.secondary {
  background: #F7F0E4;
  color: #6E4716;
  border: 1px solid #E2C797;
}

.action-btn.secondary:disabled {
  background: #F2EDE5;
  color: #B7A892;
  border-color: #E6DDD0;
}

.action-btn:disabled {
  background: #CCC;
  cursor: not-allowed;
}

.legacy-note {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #8B6C4A;
}

@media (max-width: 720px) {
  .action-btn-row {
    grid-template-columns: 1fr;
  }

  .stats-grid,
  .diag-metrics-grid {
    grid-template-columns: 1fr;
  }

  .build-progress-meta,
  .diag-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #FF5722;
  margin-bottom: 12px;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #FFCCBC;
  border-top-color: #FF5722;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* System Logs */
.system-logs {
  background: #000;
  color: #DDD;
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #222;
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #333;
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: #888;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px; /* Approx 4 lines visible */
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: #666;
  min-width: 75px;
}

.log-msg {
  color: #CCC;
  word-break: break-all;
}
</style>
