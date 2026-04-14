"""Read-only review workspace aggregation for the Phase 2 prototype."""

from __future__ import annotations

import re
from typing import Any

from ...models.project import ProjectManager, ProjectStatus
from .project_workspace_sources import load_graph_data, load_phase1_task_result


class ReviewViewNotFoundError(RuntimeError):
    """Raised when the requested review workspace project cannot be found."""


_REVIEW_KIND_META = {
    "warning": {"label": "构建告警"},
    "concept": {"label": "概念归一"},
    "relation": {"label": "关系确认"},
    "theme": {"label": "主题归属"},
}

_REVIEW_SEVERITY_META = {
    "high": {"label": "高风险"},
    "medium": {"label": "中风险"},
    "low": {"label": "低风险"},
}

_REVIEW_STATUS_META = {
    "pending": {"label": "未处理"},
    "approved": {"label": "已通过"},
    "questioned": {"label": "已标记存疑"},
    "ignored": {"label": "已忽略"},
}


def _unique_by(items: list[Any], key_fn) -> list[Any]:
    seen: set[Any] = set()
    results: list[Any] = []
    for item in items:
        key = key_fn(item)
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results


def _unique_strings(values: list[Any]) -> list[str]:
    strings = [str(value or "").strip() for value in values]
    return _unique_by([value for value in strings if value], lambda value: value)


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _extract_terms(text: Any) -> list[str]:
    matched = re.findall(r"[A-Za-z][A-Za-z0-9.+-]*|[\u4e00-\u9fff]{2,}", str(text or ""))
    return _unique_strings(matched)


def _shorten_text(value: Any, max_length: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _graph_nodes(graph_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((graph_data or {}).get("nodes") or [])


def _graph_edges(graph_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((graph_data or {}).get("edges") or [])


def _node_label(node: dict[str, Any]) -> str:
    labels = node.get("labels") or []
    return labels[0] if labels else "Node"


def _reading_title(project: dict[str, Any]) -> str:
    reading = project.get("reading_structure") or {}
    return str(reading.get("title") or "暂无")


def _phase1_provider(phase1_task_result: dict[str, Any]) -> str:
    return str(phase1_task_result.get("provider") or "unknown")


def _decorate_review_task(task: dict[str, Any]) -> dict[str, Any]:
    kind = _REVIEW_KIND_META.get(task.get("kind"), _REVIEW_KIND_META["warning"])
    severity = _REVIEW_SEVERITY_META.get(task.get("severity"), _REVIEW_SEVERITY_META["medium"])
    status = _REVIEW_STATUS_META.get(task.get("status"), _REVIEW_STATUS_META["pending"])
    return {
        **task,
        "kindLabel": kind["label"],
        "severityLabel": severity["label"],
        "statusLabel": status["label"],
    }


def _create_empty_review_task() -> dict[str, Any]:
    return _decorate_review_task(
        {
            "id": "",
            "title": "",
            "kind": "warning",
            "severity": "medium",
            "status": "pending",
            "summary": "",
            "sourceLabel": "",
            "confidenceLabel": "",
            "documentLabel": "",
            "rationale": "",
            "evidence": [],
            "suggestions": [],
            "sourceSnippets": [],
            "subgraph": {
                "nodes": [],
                "edges": [],
                "caption": "",
                "focusTerms": [],
            },
            "crossArticleCandidates": [],
            "focusTerms": [],
            "manualNote": "",
            "assistantPreview": "",
            "lastDecisionLabel": "",
        }
    )


def _build_warning_task(
    *,
    warning: str,
    index: int,
    project: dict[str, Any],
    graph_data: dict[str, Any],
    phase1_task_result: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = phase1_task_result.get("diagnostics") or {}
    fallback_applied = bool(diagnostics.get("fallback_graph_applied"))
    graph_node_count = graph_data.get("node_count") or len(_graph_nodes(graph_data))
    graph_edge_count = graph_data.get("edge_count") or len(_graph_edges(graph_data))
    return _decorate_review_task(
        {
            "id": f"warning-{index + 1}",
            "title": f"核对构建告警 #{index + 1}",
            "kind": "warning",
            "severity": "high" if fallback_applied or index == 0 else "medium",
            "status": "pending",
            "summary": warning,
            "sourceLabel": "来自 Phase 1 build_outcome.warnings",
            "confidenceLabel": "优先级上调" if fallback_applied else "人工确认",
            "documentLabel": project.get("name") or "当前文章",
            "rationale": "先把系统认为不稳定的单篇信号收进 review 队列，再决定哪些需要升级成真实 ReviewTask。",
            "evidence": [
                {"label": "原始 warning", "value": warning},
                {
                    "label": "构建状态",
                    "value": str((phase1_task_result.get("build_outcome") or {}).get("status") or "unknown"),
                },
                {
                    "label": "阅读骨架状态",
                    "value": str((phase1_task_result.get("reading_structure_status") or {}).get("status") or "unknown"),
                },
                {"label": "图谱快照", "value": f"{graph_node_count} 节点 / {graph_edge_count} 关系"},
            ],
            "suggestions": [
                "如果这个 warning 会影响 canonical/theme 判断，应升级为真实人工任务。",
                "如果只是一次性抽取噪声，后续可以在规则层直接消化，不必进入长期队列。",
            ],
        }
    )


def _build_concept_task(
    *,
    project: dict[str, Any],
    graph_data: dict[str, Any],
    phase1_task_result: dict[str, Any],
) -> dict[str, Any]:
    graph_node_count = graph_data.get("node_count") or len(_graph_nodes(graph_data))
    return _decorate_review_task(
        {
            "id": "concept-alignment",
            "title": "归一本篇核心概念到 canonical",
            "kind": "concept",
            "severity": "high" if graph_node_count > 6 else "medium",
            "status": "pending",
            "summary": "用当前文章的局部图谱预演 local concept -> canonical 的人工确认入口，不提前绑定真实归一算法。",
            "sourceLabel": "来自图谱节点快照与阅读骨架",
            "confidenceLabel": "原型候选",
            "documentLabel": project.get("name") or "当前文章",
            "rationale": "Phase 2 的核心不是继续堆单篇抽取，而是让局部概念进入可确认、可写回的全局治理链路。",
            "evidence": [
                {"label": "单篇图谱节点", "value": f"{graph_node_count} 个节点"},
                {"label": "阅读骨架标题", "value": _reading_title(project)},
                {"label": "Provider", "value": _phase1_provider(phase1_task_result)},
                {
                    "label": "系统判断理由",
                    "value": "如果当前文章里出现高频或桥接概念，后续应进入 canonical entity 对齐与人工确认流程。",
                },
            ],
            "suggestions": [
                "将高频局部概念合并到已有 canonical。",
                "没有可靠候选时，为它建立新的 canonical 种子。",
            ],
        }
    )


def _build_relation_task(
    *,
    project: dict[str, Any],
    graph_data: dict[str, Any],
    phase1_task_result: dict[str, Any],
) -> dict[str, Any]:
    graph_edge_count = graph_data.get("edge_count") or len(_graph_edges(graph_data))
    diagnostics = phase1_task_result.get("diagnostics") or {}
    processed = diagnostics.get("processed_chunk_count") or 0
    total = diagnostics.get("chunk_count") or 0
    return _decorate_review_task(
        {
            "id": "relation-check",
            "title": "确认关系建议是否值得人工复核",
            "kind": "relation",
            "severity": "high" if graph_edge_count > 8 else "medium",
            "status": "pending",
            "summary": "关系确认型任务需要在 review 页中占一个明确位置，否则后续很容易重新堆回 Phase 1 调试页。",
            "sourceLabel": "来自关系数量与 chunk 处理诊断",
            "confidenceLabel": f"{processed}/{total} chunks" if total else "待确认",
            "documentLabel": project.get("name") or "当前文章",
            "rationale": "关系修正和概念归一不同，应该在同一个 review 心智模型里有自己的任务类型，而不是塞进日志或 warning 文案。",
            "evidence": [
                {"label": "单篇关系数", "value": f"{graph_edge_count} 条"},
                {"label": "chunk 处理进度", "value": f"{processed}/{total}" if total else "暂无"},
                {
                    "label": "Fallback 图谱",
                    "value": "已触发" if diagnostics.get("fallback_graph_applied") else "未触发",
                },
                {
                    "label": "系统判断理由",
                    "value": "如果关系抽取存在噪声，review 视图应让人直接看到证据并决定是通过、存疑还是忽略。",
                },
            ],
            "suggestions": [
                "把低置信关系放进待确认队列，而不是直接写入全局图。",
                "对高价值桥接关系保留人工确认入口。",
            ],
        }
    )


def _build_theme_task(*, project: dict[str, Any], phase1_task_result: dict[str, Any]) -> dict[str, Any]:
    warnings = list((phase1_task_result.get("build_outcome") or {}).get("warnings") or [])
    return _decorate_review_task(
        {
            "id": "theme-assignment",
            "title": "确认主题归属是否成立",
            "kind": "theme",
            "severity": "medium" if warnings else "low",
            "status": "pending",
            "summary": "用阅读骨架和分析摘要预演 theme / cluster 的人工治理入口，验证 review 页是否足以承载主题归属判断。",
            "sourceLabel": "来自阅读骨架与分析摘要",
            "confidenceLabel": "需要人工看证据" if warnings else "候选稳定",
            "documentLabel": project.get("name") or "当前文章",
            "rationale": "主题判断通常跨多篇文章演化，先把这个任务类型放进 prototype，后续接真实 theme 聚类结果时不必重做信息架构。",
            "evidence": [
                {"label": "阅读骨架标题", "value": _reading_title(project)},
                {"label": "分析摘要", "value": str(project.get("analysis_summary") or "当前项目尚未记录分析摘要。")},
                {"label": "当前 warning 数", "value": str(len(warnings))},
                {
                    "label": "系统判断理由",
                    "value": "主题归属不是图渲染附带信息，而是需要独立校验、可写回和可追踪的治理动作。",
                },
            ],
            "suggestions": [
                "保留 theme 作为工作台一级对象，不要继续塞回文章页。",
                "主题归属低置信时进入人工校验，而不是直接自动聚类定稿。",
            ],
        }
    )


def _create_prototype_review_tasks(
    *,
    project: dict[str, Any],
    graph_data: dict[str, Any],
    phase1_task_result: dict[str, Any],
) -> list[dict[str, Any]]:
    warnings = list((phase1_task_result.get("build_outcome") or {}).get("warnings") or [])
    warning_tasks = [
        _build_warning_task(
            warning=warning,
            index=index,
            project=project,
            graph_data=graph_data,
            phase1_task_result=phase1_task_result,
        )
        for index, warning in enumerate(warnings[:2])
    ]
    tasks = [
        *warning_tasks,
        _build_concept_task(project=project, graph_data=graph_data, phase1_task_result=phase1_task_result),
        _build_relation_task(project=project, graph_data=graph_data, phase1_task_result=phase1_task_result),
        _build_theme_task(project=project, phase1_task_result=phase1_task_result),
    ]
    return tasks or [_create_empty_review_task()]


def _pick_primary_node(project: dict[str, Any], graph_data: dict[str, Any]) -> dict[str, Any] | None:
    nodes = _graph_nodes(graph_data)
    if not nodes:
        return None

    project_name = _normalize_text(project.get("name"))
    project_terms = _extract_terms(project.get("name"))

    for node in nodes:
        node_name = _normalize_text(node.get("name"))
        if node_name and (project_name.startswith(node_name) or node_name.startswith(project_name) or project_name in node_name or node_name in project_name):
            return node

    for term in project_terms:
        normalized_term = _normalize_text(term)
        for node in nodes:
            if normalized_term in _normalize_text(node.get("name")):
                return node

    return nodes[0]


def _find_first_node_by_label(
    nodes: list[dict[str, Any]],
    labels: list[str],
    excluded_names: set[str],
) -> dict[str, Any] | None:
    for node in nodes:
        if _node_label(node) in labels and str(node.get("name") or "") not in excluded_names:
            return node
    return None


def _build_focus_nodes(
    task: dict[str, Any],
    project: dict[str, Any],
    graph_data: dict[str, Any],
) -> list[dict[str, Any]]:
    nodes = _graph_nodes(graph_data)
    edges = _graph_edges(graph_data)
    if not nodes:
        return []

    primary = _pick_primary_node(project, graph_data)
    selected = [primary] if primary else []
    excluded_names = {str(node.get("name") or "") for node in selected}

    if task.get("kind") == "concept":
        mechanism = _find_first_node_by_label(nodes, ["Mechanism"], excluded_names)
        topic = _find_first_node_by_label(nodes, ["Topic", "Technology"], excluded_names)
        if mechanism:
            selected.append(mechanism)
            excluded_names.add(str(mechanism.get("name") or ""))
        if topic:
            selected.append(topic)
            excluded_names.add(str(topic.get("name") or ""))
    elif task.get("kind") == "relation":
        anchor_edge = next(
            (
                edge
                for edge in edges
                if not primary
                or edge.get("source_node_uuid") == primary.get("uuid")
                or edge.get("target_node_uuid") == primary.get("uuid")
            ),
            edges[0] if edges else None,
        )
        if anchor_edge:
            for node in nodes:
                if node.get("uuid") in {
                    anchor_edge.get("source_node_uuid"),
                    anchor_edge.get("target_node_uuid"),
                } and str(node.get("name") or "") not in excluded_names:
                    selected.append(node)
                    excluded_names.add(str(node.get("name") or ""))

        topic = _find_first_node_by_label(nodes, ["Topic", "Mechanism"], excluded_names)
        if topic:
            selected.append(topic)
    elif task.get("kind") == "theme":
        for node in [item for item in nodes if _node_label(item) == "Topic"][:3]:
            node_name = str(node.get("name") or "")
            if node_name not in excluded_names:
                selected.append(node)
                excluded_names.add(node_name)
    else:
        problem = _find_first_node_by_label(nodes, ["Problem", "Metric"], excluded_names)
        metric = _find_first_node_by_label(nodes, ["Metric", "Topic"], excluded_names)
        if problem:
            selected.append(problem)
            excluded_names.add(str(problem.get("name") or ""))
        if metric:
            selected.append(metric)

    return _unique_by(selected, lambda node: node.get("uuid"))[:4]


def _build_local_subgraph(
    task: dict[str, Any],
    project: dict[str, Any],
    graph_data: dict[str, Any],
) -> dict[str, Any]:
    nodes = _graph_nodes(graph_data)
    edges = _graph_edges(graph_data)
    if not nodes:
        return {
            "caption": "当前还没有图谱节点，后续这里会显示与任务直接相关的局部子图。",
            "nodes": [],
            "edges": [],
            "focusTerms": [],
        }

    focus_nodes = _build_focus_nodes(task, project, graph_data)
    focus_ids = {node.get("uuid") for node in focus_nodes if node.get("uuid")}
    selected_edges = [
        edge
        for edge in edges
        if edge.get("source_node_uuid") in focus_ids or edge.get("target_node_uuid") in focus_ids
    ]
    if not selected_edges:
        selected_edges = edges[:4]

    selected_node_map = {
        node.get("uuid"): node
        for node in focus_nodes
        if node.get("uuid")
    }
    for edge in selected_edges[:5]:
        for node in nodes:
            if node.get("uuid") in {edge.get("source_node_uuid"), edge.get("target_node_uuid")}:
                selected_node_map[str(node.get("uuid"))] = node

    selected_nodes = list(selected_node_map.values())[:6]
    selected_node_ids = {node.get("uuid") for node in selected_nodes if node.get("uuid")}
    filtered_edges = [
        edge
        for edge in selected_edges
        if edge.get("source_node_uuid") in selected_node_ids and edge.get("target_node_uuid") in selected_node_ids
    ][:5]

    return {
        "caption": "局部子图只展示当前任务最相关的一小圈节点和关系，帮助你判断该往哪个抽象层归并。",
        "focusTerms": [str(node.get("name") or "") for node in focus_nodes if node.get("name")],
        "nodes": [
            {
                "id": node.get("uuid"),
                "name": node.get("name"),
                "label": _node_label(node),
                "isFocus": node.get("uuid") in focus_ids,
            }
            for node in selected_nodes
        ],
        "edges": [
            {
                "id": edge.get("uuid"),
                "source": edge.get("source_node_uuid"),
                "target": edge.get("target_node_uuid"),
                "label": edge.get("name") or edge.get("fact_type") or "RELATED",
                "fact": edge.get("fact") or "",
            }
            for edge in filtered_edges
        ],
    }


def _split_article_blocks(article_text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for raw_line in str(article_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if current_lines:
                blocks.append({"heading": current_heading, "text": " ".join(current_lines)})
                current_lines = []
            continue
        if line.startswith("==="):
            continue
        if re.match(r"^#{1,6}\s", line):
            current_heading = re.sub(r"^#{1,6}\s*", "", line).strip()
            continue
        current_lines.append(line)

    if current_lines:
        blocks.append({"heading": current_heading, "text": " ".join(current_lines)})
    return [block for block in blocks if block.get("text")]


def _build_source_snippets(task: dict[str, Any], article_text: str, focus_terms: list[str]) -> list[dict[str, Any]]:
    blocks = _split_article_blocks(article_text)
    if not blocks:
        return []

    ranked = []
    for index, block in enumerate(blocks):
        haystack = f"{block.get('heading', '')} {block.get('text', '')}"
        matched_terms = [term for term in focus_terms if term and term in haystack]
        ranked.append(
            {
                "id": f"snippet-{task.get('id')}-{index}",
                "heading": block.get("heading") or "正文片段",
                "text": _shorten_text(block.get("text"), 240),
                "matchedTerms": matched_terms[:4],
                "score": len(matched_terms),
            }
        )

    ranked.sort(key=lambda item: (-int(item["score"]), len(str(item["text"]))))
    top_hits = [item for item in ranked if item["score"] > 0][:3]
    return top_hits or ranked[:2]


def _build_cross_article_candidates(
    task: dict[str, Any],
    current_project: dict[str, Any],
    candidate_projects: list[dict[str, Any]],
    focus_terms: list[str],
) -> list[dict[str, Any]]:
    current_id = current_project.get("project_id")
    completed_projects = [
        project
        for project in candidate_projects
        if project.get("project_id") != current_id and project.get("status") == ProjectStatus.GRAPH_COMPLETED.value
    ]

    scored = []
    for project in completed_projects:
        haystack = " ".join(
            [
                str(project.get("name") or ""),
                str(project.get("analysis_summary") or ""),
                str((project.get("reading_structure") or {}).get("title") or ""),
            ]
        )
        matched_terms = [term for term in focus_terms if term and term in haystack]
        score = len(matched_terms) * 3 + (4 if project.get("name") == current_project.get("name") else 0)
        scored.append(
            {
                "projectId": project.get("project_id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "summary": _shorten_text(project.get("analysis_summary") or "暂无摘要。", 140),
                "matchedTerms": matched_terms,
                "score": score,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    strong_matches = [project for project in scored if project["score"] > 0][:3]
    if strong_matches:
        return [
            {
                **project,
                "reason": f"命中 {'、'.join(project['matchedTerms'])}，适合当作跨文章候选参考。",
            }
            for project in strong_matches
        ]

    return [
        {
            **project,
            "reason": "当前没有强命中项，先展示已完成项目作为跨文章候选占位。",
        }
        for project in scored[:3]
    ]


def build_task_assistant_preview(task: dict[str, Any]) -> str:
    focus_terms = task.get("focusTerms") or []
    focus_text = " / ".join(focus_terms) if focus_terms else str(task.get("title") or "")
    candidates = task.get("crossArticleCandidates") or []
    candidate_text = (
        "、".join([str(item.get("name") or "") for item in candidates[:2] if item.get("name")])
        if candidates
        else "当前单篇证据"
    )
    if task.get("manualNote"):
        return (
            f"已记录你的说明：“{task['manualNote']}”。下一步建议 AI 先核对 {focus_text} "
            f"的原文片段与局部子图，再优先比对 {candidate_text}，最后给出可审计的 "
            f"{task.get('kindLabel') or '校验任务'} 处理建议。"
        )
    return f"建议先围绕 {focus_text} 检查原文片段、局部子图和 {candidate_text} 的候选信息，再决定是合并、关联还是暂不处理。"


def build_review_view_model(
    *,
    project: dict[str, Any],
    graph_data: dict[str, Any],
    phase1_task_result: dict[str, Any],
    article_text: str,
    candidate_projects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks = _create_prototype_review_tasks(
        project=project,
        graph_data=graph_data,
        phase1_task_result=phase1_task_result,
    )
    results: list[dict[str, Any]] = []
    for task in tasks:
        subgraph = _build_local_subgraph(task, project, graph_data)
        focus_terms = _unique_strings(
            [
                *list(subgraph.get("focusTerms") or []),
                *_extract_terms(task.get("title")),
                *_extract_terms(task.get("summary")),
            ]
        )[:6]
        source_snippets = _build_source_snippets(task, article_text, focus_terms)
        cross_article_candidates = _build_cross_article_candidates(task, project, candidate_projects, focus_terms)
        enriched = _decorate_review_task(
            {
                **task,
                "focusTerms": focus_terms,
                "sourceSnippets": source_snippets,
                "subgraph": subgraph,
                "crossArticleCandidates": cross_article_candidates,
                "manualNote": "",
            }
        )
        enriched["assistantPreview"] = build_task_assistant_preview(enriched)
        results.append(enriched)
    return results or [_create_empty_review_task()]


class ReviewViewService:
    """Aggregates the read-only review workspace view model."""

    def build_project_view(self, project_id: str) -> dict[str, Any]:
        project = ProjectManager.get_project(project_id)
        if not project:
            raise ReviewViewNotFoundError(f"项目不存在: {project_id}")

        project_data = project.to_dict()
        article_text = ProjectManager.get_extracted_text(project_id) or ""
        phase1_task_result = load_phase1_task_result(project)
        graph_data = load_graph_data(project.graph_id)
        candidate_projects = [candidate.to_dict() for candidate in ProjectManager.list_projects(limit=120)]

        items = build_review_view_model(
            project=project_data,
            graph_data=graph_data,
            phase1_task_result=phase1_task_result,
            article_text=article_text,
            candidate_projects=candidate_projects,
        )

        # Overlay persisted review decisions onto generated items
        persisted_decisions = (project.review_decisions or {}).get("items") or {}
        for item in items:
            decision = persisted_decisions.get(item.get("id"))
            if decision:
                item["status"] = decision.get("status", item.get("status"))
                item["note"] = decision.get("note", "")
                item["decisionUpdatedAt"] = decision.get("updated_at")
                item["decisionUpdatedBy"] = decision.get("updated_by")
                # re-decorate status label
                status_meta = _REVIEW_STATUS_META.get(item["status"], _REVIEW_STATUS_META["pending"])
                item["statusLabel"] = status_meta["label"]

        warnings = list((phase1_task_result.get("build_outcome") or {}).get("warnings") or [])

        return {
            "project": {
                "project_id": project.project_id,
                "name": project.name,
                "status": project.status.value if isinstance(project.status, ProjectStatus) else project.status,
            },
            "prototypeMode": True,
            "reviewDecisionsVersion": (project.review_decisions or {}).get("version", 0),
            "summary": {
                "totalCount": len(items),
                "pendingCount": sum(1 for item in items if item.get("status") == "pending"),
                "approvedCount": sum(1 for item in items if item.get("status") == "approved"),
                "questionedCount": sum(1 for item in items if item.get("status") == "questioned"),
                "ignoredCount": sum(1 for item in items if item.get("status") == "ignored"),
                "highPriorityCount": sum(1 for item in items if item.get("severity") == "high"),
                "warningCount": len(warnings),
                "graphNodeCount": graph_data.get("node_count") or len(_graph_nodes(graph_data)),
                "graphEdgeCount": graph_data.get("edge_count") or len(_graph_edges(graph_data)),
                "articleTextAvailable": bool(article_text),
                "relatedProjectCount": len(candidate_projects),
            },
            "phase1Signals": {
                "provider": _phase1_provider(phase1_task_result),
                "build_outcome": {
                    "status": str((phase1_task_result.get("build_outcome") or {}).get("status") or "unknown"),
                    "warnings": warnings,
                },
                "reading_structure_status": {
                    "status": str((phase1_task_result.get("reading_structure_status") or {}).get("status") or "unknown"),
                },
            },
            "items": items,
        }
