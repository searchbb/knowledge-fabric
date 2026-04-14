export function buildTaskAssistantPreview(task) {
  const focusText = task.focusTerms?.length ? task.focusTerms.join(' / ') : task.title
  const candidateText = task.crossArticleCandidates?.length
    ? task.crossArticleCandidates.slice(0, 2).map((item) => item.name).join('、')
    : '当前单篇证据'

  if (task.manualNote) {
    return `已记录你的说明：“${task.manualNote}”。下一步建议 AI 先核对 ${focusText} 的原文片段与局部子图，再优先比对 ${candidateText}，最后给出可审计的 ${task.kindLabel} 处理建议。`
  }

  return `建议先围绕 ${focusText} 检查原文片段、局部子图和 ${candidateText} 的候选信息，再决定是合并、关联还是暂不处理。`
}
