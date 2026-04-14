export const WORKBENCH_VIEW_MODES = ['graph', 'split', 'workbench']

export const WORKBENCH_VIEW_LABELS = {
  graph: '图谱',
  split: '双栏',
  workbench: '工作台',
}

export function normalizeLayoutMode(value) {
  return WORKBENCH_VIEW_MODES.includes(value) ? value : 'split'
}

export function normalizeGraphPanelView(value) {
  return value === 'reading' ? 'reading' : 'graph'
}

export function buildWorkbenchPanelStyle(mode, side) {
  if (side === 'left') {
    if (mode === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
    if (mode === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
    return { width: '50%', opacity: 1, transform: 'translateX(0)' }
  }

  if (mode === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (mode === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
}

export function toggleWorkbenchMode(viewModeRef, target) {
  viewModeRef.value = viewModeRef.value === target ? 'split' : target
}

export function appendWorkbenchLog(logRef, msg, limit = 100) {
  const now = new Date()
  const time = now.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }) + '.' + now.getMilliseconds().toString().padStart(3, '0')

  logRef.value.push({ time, msg })
  if (logRef.value.length > limit) {
    logRef.value.shift()
  }
}
