import { reactive } from 'vue'

export const DEFAULT_WORKSPACE_VIEW = 'article'

export const WORKSPACE_NAV_ITEMS = [
  {
    key: 'article',
    label: '文章视图',
    description: '验收单篇抽取、阅读骨架与当前图谱状态',
  },
  {
    key: 'concepts',
    label: '概念视图',
    description: '面向 canonical 概念与 local concept 对齐',
  },
  {
    key: 'themes',
    label: '主题视图',
    description: '面向 theme 主干、聚类与主题关系',
  },
  {
    key: 'evolution',
    label: '演化视图',
    description: '面向时间增长、补充与结构演进',
  },
  {
    key: 'review',
    label: '校验视图',
    description: '面向待归一、待确认关系与人工审核队列',
  },
]

export function normalizeWorkspaceView(value) {
  return WORKSPACE_NAV_ITEMS.some((item) => item.key === value)
    ? value
    : DEFAULT_WORKSPACE_VIEW
}

export const workspaceStore = reactive({
  currentProjectId: '',
  currentView: DEFAULT_WORKSPACE_VIEW,
  currentStep: 'phase1',
  project: null,
  graphData: null,
  phase1TaskResult: null,
  loading: false,
  error: '',
})
