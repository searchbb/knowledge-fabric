const STORAGE_KEY = 'knowledge-fabric:current-research-project'
const EVENT_NAME = 'knowledge-fabric:current-research-project-changed'

function canUseBrowserStorage() {
  return typeof window !== 'undefined' && Boolean(window.localStorage)
}

export function readCurrentResearchProject() {
  if (!canUseBrowserStorage()) return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.id) return null
    return {
      ...parsed,
      id: String(parsed.id),
      title: String(parsed.title || parsed.id),
      status: String(parsed.status || ''),
    }
  } catch {
    return null
  }
}

export function setCurrentResearchProject(project) {
  if (!project?.id || !canUseBrowserStorage()) return null
  const value = {
    ...project,
    id: String(project.id),
    title: String(project.title || project.id),
    status: String(project.status || ''),
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: value }))
  return value
}

export function clearCurrentResearchProject() {
  if (!canUseBrowserStorage()) return
  window.localStorage.removeItem(STORAGE_KEY)
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: null }))
}

export function subscribeCurrentResearchProject(callback) {
  if (typeof window === 'undefined') return () => {}
  const handleCustom = (event) => callback(event.detail || readCurrentResearchProject())
  const handleStorage = (event) => {
    if (event.key === STORAGE_KEY) callback(readCurrentResearchProject())
  }
  window.addEventListener(EVENT_NAME, handleCustom)
  window.addEventListener('storage', handleStorage)
  return () => {
    window.removeEventListener(EVENT_NAME, handleCustom)
    window.removeEventListener('storage', handleStorage)
  }
}
