<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">知识工作台</div>
      <div class="nav-links">
        <RouterLink to="/workspace/overview" class="workspace-link">
          进入 Phase 2 工作台 <span class="arrow">→</span>
        </RouterLink>
      </div>
    </nav>

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">从文档到结构，从信息到知识</span>
            <span class="version-text">/ v0.1-预览版</span>
          </div>
          
          <h1 class="main-title">
            上传一篇内容<br>
            <span class="gradient-text">看见它的知识骨架</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              即使只有一段文字，<span class="highlight-bold">知识工作台</span> 也能把其中的信息重组为可阅读、可检查、可迭代的知识结构。通过实体关系抽取、主线骨架整理与阅读视图呈现，帮助你快速看见内容真正的组织方式
            </p>
            <p class="slogan-text">
              把文档变成可阅读、可检查、可迭代的知识结构<span class="blinking-cursor">_</span>
            </p>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <div class="knowledge-visual" aria-label="从非结构化文本到语义图谱，再到阅读骨架与知识网络的流程示意图">
            <div class="visual-grid"></div>

            <div class="pipeline-stage pipeline-stage-text">
              <div class="pipeline-stage-label">非结构化文本</div>
              <div class="text-sheet text-sheet-back"></div>
              <div class="text-sheet text-sheet-front">
                <div class="sheet-toolbar">
                  <span class="sheet-dot"></span>
                  <span class="sheet-dot"></span>
                  <span class="sheet-dot"></span>
                </div>
                <div class="sheet-title">文章 / 笔记 / 报告</div>
                <div class="sheet-line w-92"></div>
                <div class="sheet-line w-72"></div>
                <div class="sheet-line w-86"></div>
                <div class="sheet-line w-64"></div>
                <div class="sheet-markups">
                  <span class="markup-pill">问题</span>
                  <span class="markup-pill">方案</span>
                  <span class="markup-pill">架构</span>
                </div>
              </div>
            </div>

            <div class="pipeline-arrow arrow-a">
              <span class="arrow-token">抽取</span>
            </div>

            <div class="pipeline-stage pipeline-stage-graph">
              <div class="pipeline-stage-label">语义图谱</div>
              <div class="graph-panel-frame">
                <svg class="graph-network" viewBox="0 0 180 180" aria-hidden="true">
                  <path d="M90 28 L50 72 L90 96 L130 72 Z" />
                  <path d="M50 72 L38 124 L90 148 L142 124 L130 72" />
                  <path d="M90 28 L90 96 L90 148" />
                  <circle cx="90" cy="28" r="8" />
                  <circle cx="50" cy="72" r="8" />
                  <circle cx="130" cy="72" r="8" />
                  <circle cx="38" cy="124" r="8" />
                  <circle cx="90" cy="96" r="8" />
                  <circle cx="142" cy="124" r="8" />
                  <circle cx="90" cy="148" r="8" />
                </svg>
                <div class="graph-legend-row">
                  <span class="mini-tag tag-problem">问题</span>
                  <span class="mini-tag tag-solution">方案</span>
                  <span class="mini-tag tag-arch">架构</span>
                </div>
              </div>
            </div>

            <div class="pipeline-arrow arrow-b">
              <span class="arrow-token">整理</span>
            </div>

            <div class="pipeline-stage pipeline-stage-outline">
              <div class="pipeline-stage-label">阅读骨架</div>
              <div class="outline-panel">
                <div class="outline-heading">文章主线</div>
                <div class="outline-step">
                  <span class="outline-dot dot-problem"></span>
                  <span class="outline-step-label">问题</span>
                </div>
                <div class="outline-line"></div>
                <div class="outline-step">
                  <span class="outline-dot dot-solution"></span>
                  <span class="outline-step-label">方案</span>
                </div>
                <div class="outline-line"></div>
                <div class="outline-step">
                  <span class="outline-dot dot-arch"></span>
                  <span class="outline-step-label">架构</span>
                </div>
                <div class="outline-groups">
                  <span class="outline-chip">机制</span>
                  <span class="outline-chip">技术</span>
                  <span class="outline-chip">指标</span>
                  <span class="outline-chip">案例</span>
                </div>
              </div>
            </div>

            <div class="pipeline-arrow arrow-c">
              <span class="arrow-token">联结</span>
            </div>

            <div class="pipeline-stage pipeline-stage-ocean">
              <div class="pipeline-stage-label">知识网络</div>
              <div class="ocean-panel">
                <svg class="ocean-links" viewBox="0 0 190 190" aria-hidden="true">
                  <path d="M34 54 C76 42, 104 46, 150 64" />
                  <path d="M34 54 C58 86, 78 102, 116 124" />
                  <path d="M150 64 C136 104, 126 124, 98 154" />
                  <path d="M62 142 C88 128, 110 124, 150 132" />
                  <path d="M116 124 C138 118, 148 104, 150 64" />
                  <path d="M34 54 C44 114, 44 124, 62 142" />
                </svg>
                <div class="ocean-node ocean-node-a">概念</div>
                <div class="ocean-node ocean-node-b">方法</div>
                <div class="ocean-node ocean-node-c">案例</div>
                <div class="ocean-node ocean-node-d">观点</div>
                <div class="ocean-node ocean-node-e">证据</div>
                <div class="ocean-node ocean-node-f">关联</div>
                <div class="ocean-wave wave-1"></div>
                <div class="ocean-wave wave-2"></div>
              </div>
            </div>
          </div>
          
          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> 系统状态
          </div>
          
          <h2 class="section-title">准备就绪</h2>
          <p class="section-desc">
            上传 Markdown、PDF、TXT 后，系统会自动解析内容并生成图谱与阅读骨架
          </p>
          
          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">多格式输入</div>
              <div class="metric-label">支持 Markdown / PDF / TXT</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">双视图检查</div>
              <div class="metric-label">关系图 + 阅读视图联动查看</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 (新增区域) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> 工作流序列
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">文档解析</div>
                  <div class="step-desc">清洗文本内容，提取本体候选与分析摘要</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">图谱构建</div>
                  <div class="step-desc">抽取实体与关系，生成知识图谱与结构约束</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">阅读整理</div>
                  <div class="step-desc">生成主线骨架、结构分层与证据分组</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">环境搭建</div>
                  <div class="step-desc">为后续模拟、报告和多角色分析准备上下文</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">深度互动</div>
                  <div class="step-desc">围绕图谱持续提问、检查结果并迭代 schema</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：交互控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- 上传区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / 上传内容</span>
                <span class="console-meta">支持格式: PDF, MD, TXT</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">拖拽文件上传</div>
                  <div class="upload-hint">或点击浏览文件系统</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分割线 -->
            <div class="console-divider">
              <span>输入参数</span>
            </div>

            <!-- 输入区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / 解析目标</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// 用自然语言描述你想如何理解这篇内容（例：提取文章的核心问题、方案、架构与关键证据）"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">模式: 知识建模</div>
              </div>
            </div>

            <!-- Obsidian vault 落地位置选择 -->
            <div v-if="vaultEnabled" class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 03 / 归档位置 (Obsidian vault)</span>
                <span class="console-meta" v-if="vaultRoot">{{ vaultRoot }}</span>
              </div>
              <div class="input-wrapper">
                <select
                  v-model="formData.vaultRelativeDir"
                  class="code-input vault-select"
                  :disabled="loading || vaultLoading"
                >
                  <option value="" disabled>{{ vaultLoading ? '加载主题列表中...' : '-- 选择 md 归档到哪个 vault 目录 --' }}</option>
                  <option v-for="theme in vaultThemes" :key="theme.relative_path" :value="theme.relative_path">
                    {{ theme.label }}{{ theme.has_notes_subdir ? '  (有 笔记库 子目录)' : '' }}
                  </option>
                </select>
                <div v-if="vaultError" class="vault-error">vault 状态异常: {{ vaultError }}</div>
                <div v-else class="model-badge">真源:写入 Obsidian,OB 里可直接打开编辑</div>
              </div>
            </div>
            <div v-else-if="vaultStatusChecked && !vaultEnabled" class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 03 / 归档位置</span>
                <span class="console-meta">Obsidian vault 未启用,文件将写入 backend/uploads</span>
              </div>
            </div>

            <!-- 启动按钮 -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">开始解析</span>
                <span v-else>初始化中...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 历史项目数据库 -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { setPendingUpload } from '../store/pendingUpload'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import { getVaultStatus, listVaultThemes } from '../api/vault'

const router = useRouter()

// 表单数据
const formData = ref({
  simulationRequirement: '',
  vaultRelativeDir: ''  // 空表示:vault 未启用时走 backend/uploads
})

// 文件列表
const files = ref([])

// 状态
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// Obsidian vault 集成状态
const vaultEnabled = ref(false)
const vaultStatusChecked = ref(false)
const vaultRoot = ref('')
const vaultThemes = ref([])
const vaultLoading = ref(false)
const vaultError = ref('')

// 文件输入引用
const fileInput = ref(null)

// 计算属性:是否可以提交
// vault 启用时强制要求选目录(零 fallback:不让用户漏选);未启用则保持旧行为
const canSubmit = computed(() => {
  const base = formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
  if (!base) return false
  if (vaultEnabled.value && !formData.value.vaultRelativeDir) return false
  return true
})

// 挂载时拉 vault 状态 + 主题列表
onMounted(async () => {
  try {
    const status = await getVaultStatus()
    vaultStatusChecked.value = true
    if (status?.enabled) {
      vaultEnabled.value = true
      vaultRoot.value = status.vault_root || ''
      vaultLoading.value = true
      try {
        const res = await listVaultThemes()
        if (res?.success && Array.isArray(res.themes)) {
          vaultThemes.value = res.themes
        } else if (res?.error) {
          vaultError.value = res.error
        }
      } catch (e) {
        vaultError.value = e?.message || '主题列表加载失败'
      } finally {
        vaultLoading.value = false
      }
    } else if (status?.error) {
      vaultError.value = status.error
    }
  } catch (e) {
    vaultStatusChecked.value = true
    vaultError.value = e?.message || 'vault 状态检查失败'
  }
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 移除文件
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// 开始模拟 - 立即跳转，API调用在Process页面进行
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  // 存储待上传的数据(带上 vault 归档目录选择)
  setPendingUpload(
    files.value,
    formData.value.simulationRequirement,
    formData.value.vaultRelativeDir
  )
  
  // 立即跳转到Process页面（使用特殊标识表示新建项目）
  router.push({
    name: 'Process',
    params: { projectId: 'new' }
  })
}
</script>

<style scoped>
/* 全局变量与重置 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  /* 
    使用 Space Grotesk 作为主要标题字体，JetBrains Mono 作为代码/标签字体
    确保已在 index.html 引入这些 Google Fonts 
  */
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 顶部导航 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: 'Noto Sans SC', var(--font-mono);
  font-weight: 800;
  letter-spacing: 0.08em;
  font-size: 1.2rem;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 18px;
}

.workspace-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.3);
  transition: background 0.2s, border-color 0.2s;
}

.workspace-link:hover {
  background: rgba(255, 255, 255, 0.28);
  border-color: rgba(255, 255, 255, 0.5);
}

.arrow {
  font-family: sans-serif;
}

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 48px;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 0 1 50%;
  max-width: 620px;
  padding-right: 0;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}

.version-text {
  color: #999;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 1 1 50%;
  min-width: 700px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.knowledge-visual {
  width: 100%;
  max-width: 700px;
  min-height: 520px;
  position: relative;
  margin-right: 8px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background:
    radial-gradient(circle at 18% 20%, rgba(255, 107, 53, 0.10), transparent 22%),
    radial-gradient(circle at 84% 78%, rgba(75, 156, 211, 0.09), transparent 22%),
    linear-gradient(180deg, rgba(255,255,255,0.98), rgba(247,247,247,0.98));
  border-radius: 32px;
  overflow: hidden;
  box-shadow: 0 22px 44px rgba(0, 0, 0, 0.06);
}

.visual-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at center, black 62%, transparent 98%);
  pointer-events: none;
}

.pipeline-stage {
  position: absolute;
  top: 74px;
  width: 144px;
  height: 330px;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 20px;
  background: rgba(255,255,255,0.94);
  box-shadow: 0 14px 26px rgba(0,0,0,0.05);
}

.pipeline-stage-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  top: -14px;
  left: 14px;
  padding: 5px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid rgba(0,0,0,0.08);
  color: #444;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  box-shadow: 0 8px 18px rgba(0,0,0,0.05);
}

.pipeline-stage-text {
  left: 24px;
}

.pipeline-stage-graph {
  left: 190px;
}

.pipeline-stage-outline {
  left: 356px;
}

.pipeline-stage-ocean {
  left: 522px;
}

.pipeline-arrow {
  position: absolute;
  top: 214px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #111;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 22px rgba(0,0,0,0.16);
  z-index: 3;
}

.pipeline-arrow::before {
  content: '';
  position: absolute;
  left: -16px;
  width: 16px;
  height: 2px;
  background: rgba(0,0,0,0.12);
}

.pipeline-arrow::after {
  content: '';
  position: absolute;
  right: -16px;
  width: 16px;
  height: 2px;
  background: rgba(0,0,0,0.12);
}

.arrow-a { left: 166px; }
.arrow-b { left: 332px; }
.arrow-c { left: 498px; }

.arrow-token {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.text-sheet {
  position: absolute;
  border-radius: 16px;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.97);
}

.text-sheet-back {
  top: 54px;
  left: 24px;
  width: 88px;
  height: 120px;
  transform: rotate(-6deg);
  background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,248,248,0.92));
}

.text-sheet-front {
  top: 34px;
  left: 16px;
  width: 108px;
  height: 164px;
  padding: 12px;
  box-shadow: 0 12px 24px rgba(0,0,0,0.05);
}

.sheet-toolbar {
  display: flex;
  gap: 5px;
  margin-bottom: 10px;
}

.sheet-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0,0,0,0.24);
}

.sheet-title {
  font-size: 0.82rem;
  font-weight: 700;
  color: #111;
  line-height: 1.4;
  margin-bottom: 12px;
}

.sheet-line {
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(0,0,0,0.10), rgba(0,0,0,0.03));
  margin-bottom: 8px;
}

.sheet-line.w-92 { width: 92%; }
.sheet-line.w-72 { width: 72%; }
.sheet-line.w-86 { width: 86%; }
.sheet-line.w-64 { width: 64%; }

.sheet-markups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.markup-pill {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 107, 53, 0.08);
  border: 1px solid rgba(255, 107, 53, 0.16);
  color: #FF6B35;
  font-size: 0.66rem;
  font-weight: 700;
}

.graph-panel-frame {
  position: absolute;
  inset: 18px 14px 16px;
  border: 1px dashed rgba(0,0,0,0.12);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(250,250,250,0.95));
}

.graph-network {
  position: absolute;
  inset: 18px 10px 46px;
  width: calc(100% - 20px);
  height: calc(100% - 64px);
}

.graph-network path {
  fill: none;
  stroke: rgba(0, 0, 0, 0.18);
  stroke-width: 2.4;
  stroke-linecap: round;
}

.graph-network circle:nth-of-type(1),
.graph-network circle:nth-of-type(5) { fill: #8E7DBE; }
.graph-network circle:nth-of-type(2),
.graph-network circle:nth-of-type(4) { fill: #0B61A4; }
.graph-network circle:nth-of-type(3) { fill: #C5283D; }
.graph-network circle:nth-of-type(6) { fill: #E9724C; }
.graph-network circle:nth-of-type(7) { fill: #B56B45; }

.graph-legend-row {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mini-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 700;
  border: 1px solid transparent;
}

.tag-problem {
  color: #0B61A4;
  background: rgba(11, 97, 164, 0.10);
  border-color: rgba(11, 97, 164, 0.16);
}

.tag-solution {
  color: #C5283D;
  background: rgba(197, 40, 61, 0.10);
  border-color: rgba(197, 40, 61, 0.16);
}

.tag-arch {
  color: #B56B45;
  background: rgba(181, 107, 69, 0.10);
  border-color: rgba(181, 107, 69, 0.16);
}

.outline-panel {
  position: absolute;
  inset: 18px 14px 16px;
  border: 1px dashed rgba(0,0,0,0.12);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(250,250,250,0.95));
  padding: 18px 14px;
}

.outline-heading {
  font-size: 0.94rem;
  font-weight: 700;
  color: #111;
  margin-bottom: 16px;
}

.outline-step {
  display: flex;
  align-items: center;
  gap: 9px;
}

.outline-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-problem { background: #0B61A4; }
.dot-solution { background: #C5283D; }
.dot-arch { background: #B56B45; }

.outline-step-label {
  font-size: 0.86rem;
  font-weight: 700;
  color: #222;
}

.outline-line {
  width: 2px;
  height: 16px;
  margin-left: 4px;
  background: linear-gradient(180deg, rgba(0,0,0,0.18), rgba(0,0,0,0.05));
}

.outline-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 18px;
}

.outline-chip {
  padding: 5px 8px;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 700;
  color: #555;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.ocean-panel {
  position: absolute;
  inset: 18px 14px 16px;
  border: 1px dashed rgba(0,0,0,0.12);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(247, 250, 252, 0.96));
  overflow: hidden;
}

.ocean-links {
  position: absolute;
  inset: 18px 10px 30px;
  width: calc(100% - 20px);
  height: calc(100% - 48px);
}

.ocean-links path {
  fill: none;
  stroke: rgba(52, 108, 173, 0.28);
  stroke-width: 2.2;
  stroke-linecap: round;
}

.ocean-node {
  position: absolute;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 26px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 0.64rem;
  font-weight: 700;
  color: #234B70;
  background: rgba(255,255,255,0.96);
  border: 1px solid rgba(52, 108, 173, 0.16);
  box-shadow: 0 8px 16px rgba(0,0,0,0.04);
}

.ocean-node-a { top: 28px; left: 20px; }
.ocean-node-b { top: 38px; right: 16px; }
.ocean-node-c { top: 102px; left: 54px; }
.ocean-node-d { top: 88px; right: 34px; }
.ocean-node-e { bottom: 54px; left: 30px; }
.ocean-node-f { bottom: 38px; right: 20px; }

.ocean-wave {
  position: absolute;
  left: -10%;
  width: 120%;
  border-radius: 50%;
  border: 1px solid rgba(52, 108, 173, 0.16);
}

.wave-1 {
  bottom: -34px;
  height: 78px;
}

.wave-2 {
  bottom: -16px;
  height: 56px;
  opacity: 0.65;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* 左侧面板 */
.left-panel {
  flex: 0.8;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 项目模拟步骤介绍 */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* 右侧交互控制台 */
.right-panel {
  flex: 1.2;
}

.console-box {
  border: 1px solid #CCC; /* 外部实线 */
  padding: 8px; /* 内边距形成双重边框感 */
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.upload-zone {
  border: 1px dashed #CCC;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #FAFAFA;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #F0F0F0;
  border-color: #999;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 1px;
}

.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
}

.vault-select {
  min-height: 48px;
  padding: 12px 20px;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  background: transparent url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M4 6l4 4 4-4' stroke='%23666' fill='none' stroke-width='1.5'/></svg>") no-repeat right 16px center;
  background-size: 12px;
}

.vault-select:disabled {
  color: #AAA;
  cursor: wait;
}

.vault-error {
  margin-top: 6px;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #c62828;
  background: #fff5f5;
  border-left: 3px solid #c62828;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

/* 可点击状态（非禁用） */
.start-engine-btn:not(:disabled) {
  background: var(--black);
  border: 1px solid var(--black);
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  transform: none;
  border: 1px solid #E5E5E5;
}

/* 引导动画：微妙的边框脉冲 */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }
  
  .hero-section {
    flex-direction: column;
    gap: 24px;
  }
  
  .hero-left {
    margin-bottom: 40px;
    max-width: 100%;
  }
  
  .hero-right {
    min-width: 0;
    width: 100%;
    align-items: center;
  }

  .knowledge-visual {
    min-height: 460px;
    max-width: 100%;
    margin-bottom: 20px;
  }
}
</style>
