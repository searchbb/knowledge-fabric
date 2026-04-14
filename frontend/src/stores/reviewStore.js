import { reactive } from 'vue'
import {
  REVIEW_FILTERS,
  REVIEW_DECISIONS,
  createEmptyReviewTaskViewModel,
  decorateReviewTask,
  matchesReviewFilter,
} from '../types/review'
import { getReviewView, putReviewDecision, deleteReviewDecision } from '../services/api/reviewApi'
import { buildTaskAssistantPreview } from '../services/review/reviewAssistantPreview'

export const reviewStore = reactive({
  items: [],
  selectedId: '',
  selectedTask: null,
  activeFilter: REVIEW_FILTERS[0].key,
  lastDecision: '',
  prototypeMode: true,
  summary: null,
  phase1Signals: null,
  articleTextAvailable: false,
  relatedProjectCount: 0,
  loading: false,
  error: '',
  projectId: '',
  savingById: {},
  errorById: {},
})

export { REVIEW_FILTERS, REVIEW_DECISIONS }

let seedSequence = 0

function replaceTask(nextTask) {
  const index = reviewStore.items.findIndex((item) => item.id === nextTask.id)
  if (index === -1) return

  reviewStore.items.splice(index, 1, nextTask)
  if (reviewStore.selectedId === nextTask.id) {
    reviewStore.selectedTask = nextTask
  }
}

export async function loadReviewView(payload) {
  const currentSequence = ++seedSequence
  reviewStore.loading = true
  reviewStore.error = ''
  try {
    const projectId = payload.projectId || payload.project?.project_id
    if (!projectId) {
      reviewStore.items = []
      reviewStore.selectedId = ''
      reviewStore.selectedTask = null
      reviewStore.summary = null
      reviewStore.phase1Signals = null
      reviewStore.articleTextAvailable = false
      reviewStore.relatedProjectCount = 0
      return
    }

    const response = await getReviewView(projectId)
    if (currentSequence !== seedSequence) return

    const view = response?.data || {}
    const summary = view.summary || null
    const items = (view.items || []).map((item) => decorateReviewTask(item))

    reviewStore.projectId = projectId
    reviewStore.items = items
    reviewStore.activeFilter = REVIEW_FILTERS[0].key
    reviewStore.selectedId = items[0]?.id || ''
    reviewStore.selectedTask = items[0] || createEmptyReviewTaskViewModel()
    reviewStore.lastDecision = ''
    reviewStore.prototypeMode = view.prototypeMode !== false
    reviewStore.summary = summary
    reviewStore.phase1Signals = view.phase1Signals || null
    reviewStore.articleTextAvailable = Boolean(summary?.articleTextAvailable)
    reviewStore.relatedProjectCount = summary?.relatedProjectCount || 0
    reviewStore.savingById = {}
    reviewStore.errorById = {}
  } catch (error) {
    reviewStore.error = error.message || '校验视图原型加载失败'
    reviewStore.items = []
    reviewStore.selectedId = ''
    reviewStore.selectedTask = null
    reviewStore.summary = null
    reviewStore.phase1Signals = null
  } finally {
    if (currentSequence === seedSequence) {
      reviewStore.loading = false
    }
  }
}

export function selectReviewTask(taskId) {
  const nextTask = reviewStore.items.find((item) => item.id === taskId)
  if (!nextTask) return

  reviewStore.selectedId = nextTask.id
  reviewStore.selectedTask = nextTask
}

export function setReviewFilter(filterKey) {
  reviewStore.activeFilter = REVIEW_FILTERS.some((item) => item.key === filterKey)
    ? filterKey
    : REVIEW_FILTERS[0].key

  const visibleTasks = getVisibleReviewTasks()
  if (!visibleTasks.some((item) => item.id === reviewStore.selectedId)) {
    selectReviewTask(visibleTasks[0]?.id || reviewStore.items[0]?.id || '')
  }
}

export function getVisibleReviewTasks() {
  return reviewStore.items.filter((item) => matchesReviewFilter(item, reviewStore.activeFilter))
}

export async function applyPrototypeDecision(decisionKey) {
  const decision = REVIEW_DECISIONS.find((item) => item.key === decisionKey)
  const index = reviewStore.items.findIndex((item) => item.id === reviewStore.selectedId)
  if (!decision || index === -1) return

  const task = reviewStore.items[index]
  const nextTask = decorateReviewTask({
    ...task,
    status: decision.status,
    lastDecisionLabel: `刚刚标记为${decision.label}`,
  })

  replaceTask(nextTask)
  reviewStore.lastDecision = decision.label

  const visibleTasks = getVisibleReviewTasks()
  if (!visibleTasks.some((item) => item.id === nextTask.id)) {
    selectReviewTask(visibleTasks[0]?.id || reviewStore.items[0]?.id || '')
  }

  // Persist to backend
  if (reviewStore.projectId) {
    _persistDecision(task.id, decision.status, nextTask.note || nextTask.manualNote || '')
  }
}

export function updateReviewManualNote(note) {
  const task = reviewStore.items.find((item) => item.id === reviewStore.selectedId)
  if (!task) return

  const nextTask = decorateReviewTask({
    ...task,
    manualNote: note,
    note: note,
  })

  nextTask.assistantPreview = buildTaskAssistantPreview(nextTask)
  replaceTask(nextTask)
}

export async function saveReviewNote(itemId) {
  const task = reviewStore.items.find((item) => item.id === itemId)
  if (!task || !reviewStore.projectId) return

  const status = task.status === 'pending' ? 'questioned' : task.status
  await _persistDecision(itemId, status, task.note || task.manualNote || '')
}

export async function clearReviewDecision(itemId) {
  if (!reviewStore.projectId) return

  reviewStore.savingById[itemId] = true
  delete reviewStore.errorById[itemId]
  try {
    await deleteReviewDecision(reviewStore.projectId, itemId)
    const task = reviewStore.items.find((item) => item.id === itemId)
    if (task) {
      replaceTask(decorateReviewTask({ ...task, status: 'pending', note: '', lastDecisionLabel: '' }))
    }
  } catch (err) {
    reviewStore.errorById[itemId] = err.message || '清除失败'
  } finally {
    reviewStore.savingById[itemId] = false
  }
}

async function _persistDecision(itemId, status, note) {
  reviewStore.savingById[itemId] = true
  delete reviewStore.errorById[itemId]
  try {
    await putReviewDecision(reviewStore.projectId, itemId, { status, note })
  } catch (err) {
    reviewStore.errorById[itemId] = err.message || '保存失败'
  } finally {
    reviewStore.savingById[itemId] = false
  }
}
