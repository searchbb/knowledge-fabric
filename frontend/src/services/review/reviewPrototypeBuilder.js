import { createPrototypeReviewTasks, decorateReviewTask } from '../../types/review'

function uniqueBy(items, keyFn) {
  const seen = new Set()
  return items.filter((item) => {
    const key = keyFn(item)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function uniqueStrings(values) {
  return uniqueBy(
    values.map((value) => String(value || '').trim()).filter(Boolean),
    (value) => value,
  )
}

function normalizeText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

function extractTerms(text) {
  return uniqueStrings(
    String(text || '').match(/[A-Za-z][A-Za-z0-9.+-]*|[\u4e00-\u9fff]{2,}/g) || [],
  )
}

function shortenText(value, maxLength = 220) {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1)}…`
}

function getGraphNodes(graphData) {
  return graphData?.nodes || []
}

function getGraphEdges(graphData) {
  return graphData?.edges || []
}

function getNodeLabel(node) {
  return node?.labels?.[0] || 'Node'
}

function pickPrimaryNode(project, graphData) {
  const nodes = getGraphNodes(graphData)
  if (!nodes.length) return null

  const projectName = normalizeText(project?.name)
  const projectTerms = extractTerms(project?.name)

  const exactMatch = nodes.find((node) => {
    const nodeName = normalizeText(node.name)
    return nodeName && (projectName.includes(nodeName) || nodeName.includes(projectName))
  })
  if (exactMatch) return exactMatch

  for (const term of projectTerms) {
    const termMatch = nodes.find((node) => normalizeText(node.name).includes(normalizeText(term)))
    if (termMatch) return termMatch
  }

  return nodes[0]
}

function findFirstNodeByLabel(nodes, labels, excludedNames = new Set()) {
  return nodes.find((node) => labels.includes(getNodeLabel(node)) && !excludedNames.has(node.name))
}

function buildFocusNodes(task, project, graphData) {
  const nodes = getGraphNodes(graphData)
  const edges = getGraphEdges(graphData)
  if (!nodes.length) return []

  const primary = pickPrimaryNode(project, graphData)
  const selected = primary ? [primary] : []
  const excludedNames = new Set(selected.map((node) => node.name))

  if (task.kind === 'concept') {
    const mechanism = findFirstNodeByLabel(nodes, ['Mechanism'], excludedNames)
    const topic = findFirstNodeByLabel(nodes, ['Topic', 'Technology'], excludedNames)
    if (mechanism) {
      selected.push(mechanism)
      excludedNames.add(mechanism.name)
    }
    if (topic) {
      selected.push(topic)
      excludedNames.add(topic.name)
    }
  } else if (task.kind === 'relation') {
    const anchorEdge = edges.find((edge) => {
      if (!primary) return true
      return edge.source_node_uuid === primary.uuid || edge.target_node_uuid === primary.uuid
    }) || edges[0]

    if (anchorEdge) {
      const edgeNodes = nodes.filter((node) => (
        node.uuid === anchorEdge.source_node_uuid || node.uuid === anchorEdge.target_node_uuid
      ))
      edgeNodes.forEach((node) => {
        if (!excludedNames.has(node.name)) {
          selected.push(node)
          excludedNames.add(node.name)
        }
      })
    }

    const topic = findFirstNodeByLabel(nodes, ['Topic', 'Mechanism'], excludedNames)
    if (topic) {
      selected.push(topic)
    }
  } else if (task.kind === 'theme') {
    nodes
      .filter((node) => getNodeLabel(node) === 'Topic')
      .slice(0, 3)
      .forEach((node) => {
        if (!excludedNames.has(node.name)) {
          selected.push(node)
          excludedNames.add(node.name)
        }
      })
  } else {
    const problem = findFirstNodeByLabel(nodes, ['Problem', 'Metric'], excludedNames)
    const metric = findFirstNodeByLabel(nodes, ['Metric', 'Topic'], excludedNames)
    if (problem) {
      selected.push(problem)
      excludedNames.add(problem.name)
    }
    if (metric) {
      selected.push(metric)
    }
  }

  return uniqueBy(selected, (node) => node.uuid).slice(0, 4)
}

function buildLocalSubgraph(task, project, graphData) {
  const nodes = getGraphNodes(graphData)
  const edges = getGraphEdges(graphData)
  if (!nodes.length) {
    return {
      caption: '当前还没有图谱节点，后续这里会显示与任务直接相关的局部子图。',
      nodes: [],
      edges: [],
      focusTerms: [],
    }
  }

  const focusNodes = buildFocusNodes(task, project, graphData)
  const focusIds = new Set(focusNodes.map((node) => node.uuid))
  let selectedEdges = edges.filter((edge) => (
    focusIds.has(edge.source_node_uuid) || focusIds.has(edge.target_node_uuid)
  ))

  if (!selectedEdges.length) {
    selectedEdges = edges.slice(0, 4)
  }

  const selectedNodeMap = new Map(focusNodes.map((node) => [node.uuid, node]))
  selectedEdges.slice(0, 5).forEach((edge) => {
    const source = nodes.find((node) => node.uuid === edge.source_node_uuid)
    const target = nodes.find((node) => node.uuid === edge.target_node_uuid)
    if (source) selectedNodeMap.set(source.uuid, source)
    if (target) selectedNodeMap.set(target.uuid, target)
  })

  const selectedNodes = Array.from(selectedNodeMap.values()).slice(0, 6)
  const selectedNodeIds = new Set(selectedNodes.map((node) => node.uuid))
  const filteredEdges = selectedEdges
    .filter((edge) => selectedNodeIds.has(edge.source_node_uuid) && selectedNodeIds.has(edge.target_node_uuid))
    .slice(0, 5)

  return {
    caption: '局部子图只展示当前任务最相关的一小圈节点和关系，帮助你判断该往哪个抽象层归并。',
    focusTerms: focusNodes.map((node) => node.name),
    nodes: selectedNodes.map((node) => ({
      id: node.uuid,
      name: node.name,
      label: getNodeLabel(node),
      isFocus: focusIds.has(node.uuid),
    })),
    edges: filteredEdges.map((edge) => ({
      id: edge.uuid,
      source: edge.source_node_uuid,
      target: edge.target_node_uuid,
      label: edge.name || edge.fact_type || 'RELATED',
      fact: edge.fact || '',
    })),
  }
}

function splitArticleBlocks(articleText) {
  const blocks = []
  let currentHeading = ''

  const trailing = String(articleText || '')
    .split('\n')
    .reduce((current, rawLine) => {
      const line = rawLine.trim()

      if (!line) {
        if (current.length) {
          blocks.push({
            heading: currentHeading,
            text: current.join(' '),
          })
        }
        return []
      }

      if (line.startsWith('===')) return current

      if (/^#{1,6}\s/.test(line)) {
        currentHeading = line.replace(/^#{1,6}\s*/, '').trim()
        return current
      }

      current.push(line)
      return current
    }, [])

  if (trailing.length) {
    blocks.push({
      heading: currentHeading,
      text: trailing.join(' '),
    })
  }

  return blocks.filter((block) => block.text)
}

function buildSourceSnippets(task, articleText, focusTerms) {
  const blocks = splitArticleBlocks(articleText)
  if (!blocks.length) return []

  const ranked = blocks
    .map((block, index) => {
      const haystack = `${block.heading} ${block.text}`
      const matchedTerms = focusTerms.filter((term) => term && haystack.includes(term))
      return {
        id: `snippet-${task.id}-${index}`,
        heading: block.heading || '正文片段',
        text: shortenText(block.text, 240),
        matchedTerms: matchedTerms.slice(0, 4),
        score: matchedTerms.length,
      }
    })
    .sort((left, right) => right.score - left.score || left.text.length - right.text.length)

  const topHits = ranked.filter((item) => item.score > 0).slice(0, 3)
  if (topHits.length) return topHits

  return ranked.slice(0, 2)
}

function buildCrossArticleCandidates(task, currentProject, candidateProjects, focusTerms) {
  const currentId = currentProject?.project_id
  const completedProjects = (candidateProjects || []).filter((project) => (
    project.project_id !== currentId && project.status === 'graph_completed'
  ))

  const scored = completedProjects
    .map((project) => {
      const haystack = `${project.name || ''} ${project.analysis_summary || ''} ${project.reading_structure?.title || ''}`
      const matchedTerms = focusTerms.filter((term) => term && haystack.includes(term))
      const score = matchedTerms.length * 3 + (project.name === currentProject?.name ? 4 : 0)

      return {
        projectId: project.project_id,
        name: project.name,
        status: project.status,
        summary: shortenText(project.analysis_summary || '暂无摘要。', 140),
        matchedTerms,
        score,
      }
    })
    .sort((left, right) => right.score - left.score)

  const strongMatches = scored.filter((project) => project.score > 0).slice(0, 3)
  if (strongMatches.length) {
    return strongMatches.map((project) => ({
      ...project,
      reason: `命中 ${project.matchedTerms.join('、')}，适合当作跨文章候选参考。`,
    }))
  }

  return scored.slice(0, 3).map((project) => ({
    ...project,
    reason: `当前没有强命中项，先展示已完成项目作为跨文章候选占位。`,
  }))
}

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

export function buildReviewPrototype(payload) {
  return createPrototypeReviewTasks(payload).map((task) => {
    const subgraph = buildLocalSubgraph(task, payload.project, payload.graphData)
    const focusTerms = uniqueStrings([
      ...subgraph.focusTerms,
      ...extractTerms(task.title),
      ...extractTerms(task.summary),
    ]).slice(0, 6)

    const sourceSnippets = buildSourceSnippets(task, payload.articleText, focusTerms)
    const crossArticleCandidates = buildCrossArticleCandidates(
      task,
      payload.project,
      payload.candidateProjects,
      focusTerms,
    )

    const enrichedTask = {
      ...task,
      focusTerms,
      sourceSnippets,
      subgraph,
      crossArticleCandidates,
      manualNote: '',
    }

    return decorateReviewTask({
      ...enrichedTask,
      assistantPreview: buildTaskAssistantPreview(enrichedTask),
    })
  })
}
