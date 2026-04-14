"""Project-scoped theme candidate aggregation for the Phase 2 workspace."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ...models.project import ProjectManager
from .project_workspace_sources import load_graph_data, load_phase1_task_result

_THEME_LIMITATIONS = [
    "当前输出是项目内 theme candidates，不是 canonical theme truth source。",
    "当前不提供 merge / split / writeback / approval 等治理动作。",
    "当前不做跨项目 theme 对齐，也不声称已完成聚类算法。",
]


class ThemeViewNotFoundError(RuntimeError):
    """Raised when the requested project does not exist."""


def _node_label(node: dict[str, Any]) -> str:
    labels = [label for label in (node.get("labels") or []) if label != "Entity"]
    return labels[0] if labels else "Node"


def _sample_node_names(nodes: list[dict[str, Any]], limit: int = 4) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        name = str(node.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names[:limit]


def _group_graph_nodes(graph_data: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], Counter[str]]:
    nodes = list(graph_data.get("nodes") or [])
    edges = list(graph_data.get("edges") or [])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edge_hits: Counter[str] = Counter()

    node_by_id = {str(node.get("uuid")): node for node in nodes if node.get("uuid")}

    for node in nodes:
        grouped[_node_label(node)].append(node)

    for edge in edges:
        source = node_by_id.get(str(edge.get("source_node_uuid") or ""))
        target = node_by_id.get(str(edge.get("target_node_uuid") or ""))
        if source:
            edge_hits[_node_label(source)] += 1
        if target:
            edge_hits[_node_label(target)] += 1

    grouped.pop("Node", None)
    return grouped, edge_hits


def _safe_stage(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {
        "title": str(raw.get("title") or ""),
        "summary": str(raw.get("summary") or ""),
    }


def build_theme_candidates(
    *,
    reading_structure: dict[str, Any],
    graph_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str], int]:
    grouped_nodes, edge_hits = _group_graph_nodes(graph_data)
    group_titles = dict(reading_structure.get("group_titles") or {})

    candidates: list[dict[str, Any]] = []
    covered_labels: set[str] = set()

    for label, nodes in sorted(grouped_nodes.items(), key=lambda item: (-len(item[1]), item[0])):
        title = str(group_titles.get(label) or label).strip()
        sample_nodes = _sample_node_names(nodes)
        covered_labels.add(label)
        candidates.append(
            {
                "candidateKey": f"reading_group:{label.lower()}",
                "title": title or label,
                "kind": "reading_group",
                "summary": (
                    f"围绕 {('、'.join(sample_nodes[:3]) or label)} 等 {label} 节点形成的主题候选，"
                    "先用于承接项目内 theme 主干的只读总览。"
                ),
                "supportSignals": [
                    f"阅读分组：{title or label}",
                    f"图谱标签：{label}",
                    f"候选节点数：{len(nodes)}",
                ],
                "evidence": {
                    "nodeCount": len(nodes),
                    "edgeCount": int(edge_hits.get(label, 0)),
                    "readingGroupRefs": [title or label],
                    "topLabels": [label],
                    "sampleNodes": sample_nodes,
                },
                "sourceRefs": [
                    f"reading_structure.group_titles.{label}",
                    f"graph.labels.{label}",
                ],
            }
        )

    unassigned_labels = [label for label in grouped_nodes.keys() if label not in covered_labels]
    uncovered_nodes_count = sum(len(grouped_nodes[label]) for label in unassigned_labels)

    # Keep this conservative: only mark reading groups as unassigned when the
    # reading structure contains a non-empty custom label without graph support.
    unassigned_reading_groups = [
        str(title).strip()
        for label, title in group_titles.items()
        if str(title or "").strip() and label not in grouped_nodes
    ][:4]

    return candidates, unassigned_reading_groups, unassigned_labels, uncovered_nodes_count


class ThemeViewService:
    """Builds a project-scoped, read-only theme candidate view model."""

    def build_project_view(self, project_id: str) -> dict[str, Any]:
        project = ProjectManager.get_project(project_id)
        if not project:
            raise ThemeViewNotFoundError(f"项目不存在: {project_id}")

        reading_structure = dict(project.reading_structure or {})
        phase1_task_result = load_phase1_task_result(project)
        graph_data = load_graph_data(project.graph_id)
        nodes = list(graph_data.get("nodes") or [])
        edges = list(graph_data.get("edges") or [])
        warnings = list((phase1_task_result.get("build_outcome") or {}).get("warnings") or [])

        theme_candidates, unassigned_groups, unassigned_labels, uncovered_nodes_count = build_theme_candidates(
            reading_structure=reading_structure,
            graph_data=graph_data,
        )

        # Overlay persisted theme decisions
        persisted = (project.theme_decisions or {}).get("items") or {}
        for candidate in theme_candidates:
            decision = persisted.get(candidate.get("candidateKey"))
            if decision:
                candidate["status"] = decision.get("status", "unreviewed")
                candidate["note"] = decision.get("note", "")
                candidate["decisionUpdatedAt"] = decision.get("updated_at")

        generated_from = []
        if project.analysis_summary:
            generated_from.append("analysis_summary")
        if reading_structure:
            generated_from.append("reading_structure")
        if nodes or edges:
            generated_from.append("graph_data")
        if phase1_task_result:
            generated_from.append("phase1_task_result")

        if reading_structure and (nodes or edges):
            data_completeness = "reading_structure_with_graph"
            empty_reason = ""
        elif reading_structure:
            data_completeness = "reading_structure_only"
            empty_reason = "当前缺少图谱证据，主题候选只能依赖阅读骨架。"
        elif nodes or edges:
            data_completeness = "graph_only"
            empty_reason = "当前没有阅读骨架，主题候选只能依赖图谱标签分组。"
        else:
            data_completeness = "empty"
            empty_reason = "当前项目还没有阅读骨架或图谱，无法生成主题候选。"

        return {
            "meta": {
                "projectId": project.project_id,
                "projectName": project.name,
                "graphId": project.graph_id,
                "phase1Status": str((phase1_task_result.get("build_outcome") or {}).get("status") or "unknown"),
                "viewVersion": "theme-candidates-v1",
                "generatedFrom": generated_from,
                "generatedAt": project.updated_at,
            },
            "themeDecisionsVersion": (project.theme_decisions or {}).get("version", 0),
            "overview": {
                "summaryText": str(project.analysis_summary or reading_structure.get("summary") or "当前项目还没有可复用的主题摘要。"),
                "candidateCount": len(theme_candidates),
                "confirmedCount": sum(1 for c in theme_candidates if c.get("status") == "confirmed"),
                "dismissedCount": sum(1 for c in theme_candidates if c.get("status") == "dismissed"),
                "nodeCount": int(graph_data.get("node_count") or len(nodes)),
                "edgeCount": int(graph_data.get("edge_count") or len(edges)),
                "readingGroupCount": len([item for item in theme_candidates if item["kind"] == "reading_group"]),
                "uncoveredNodesCount": uncovered_nodes_count,
            },
            "backbone": {
                "title": str(reading_structure.get("title") or project.name or "暂无阅读主线"),
                "summary": str(reading_structure.get("summary") or project.analysis_summary or ""),
                "problem": _safe_stage(reading_structure.get("problem")),
                "solution": _safe_stage(reading_structure.get("solution")),
                "architecture": _safe_stage(reading_structure.get("architecture")),
                "articleSections": list(reading_structure.get("article_sections") or []),
            },
            "themeCandidates": theme_candidates,
            "diagnostics": {
                "warnings": warnings,
                "emptyReason": empty_reason,
                "dataCompleteness": data_completeness,
                "unassignedReadingGroups": unassigned_groups,
                "unassignedLabels": unassigned_labels,
                "uncoveredNodesCount": uncovered_nodes_count,
            },
            "limitations": list(_THEME_LIMITATIONS),
            "clusters": list(project.theme_clusters or []),
        }
