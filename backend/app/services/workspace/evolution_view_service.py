"""Project-scoped evolution snapshot aggregation for the Phase 2 workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ...models.project import ProjectManager
from .project_workspace_sources import load_graph_data, load_phase1_task_result

_EVOLUTION_LIMITATIONS = [
    "当前只展示项目内演化就绪度快照，不代表持久化的历史时间轴。",
    "当前没有 canonical/theme/review 的审计历史，因此不展示真实治理演化。",
    "图谱 created_at 覆盖率依赖 builder 返回结果，不能假设所有项目都有完整时间信号。",
]


class EvolutionViewNotFoundError(RuntimeError):
    """Raised when the requested project does not exist."""


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _coverage_label(covered: int, total: int) -> str:
    if total <= 0 or covered <= 0:
        return "none"
    if covered >= total:
        return "consistent"
    return "partial"


def _timestamp_signal_summary(graph_data: dict[str, Any]) -> tuple[int, int, str, str]:
    nodes = list(graph_data.get("nodes") or [])
    edges = list(graph_data.get("edges") or [])
    node_timestamp_count = 0
    edge_timestamp_count = 0

    for node in nodes:
        timestamp = _parse_timestamp(node.get("created_at"))
        if not timestamp:
            continue
        node_timestamp_count += 1

    for edge in edges:
        timestamp = _parse_timestamp(edge.get("created_at"))
        if not timestamp:
            continue
        edge_timestamp_count += 1
    return (
        node_timestamp_count,
        edge_timestamp_count,
        _coverage_label(node_timestamp_count, len(nodes)),
        _coverage_label(edge_timestamp_count, len(edges)),
    )


class EvolutionViewService:
    """Builds a project-scoped, read-only evolution snapshot view model."""

    def build_project_view(self, project_id: str) -> dict[str, Any]:
        project = ProjectManager.get_project(project_id)
        if not project:
            raise EvolutionViewNotFoundError(f"项目不存在: {project_id}")

        phase1_task_result = load_phase1_task_result(project)
        graph_data = load_graph_data(project.graph_id)
        warnings = list((phase1_task_result.get("build_outcome") or {}).get("warnings") or [])
        nodes = list(graph_data.get("nodes") or [])
        edges = list(graph_data.get("edges") or [])
        reading_structure = dict(project.reading_structure or {})
        node_timestamp_count, edge_timestamp_count, node_coverage_label, edge_coverage_label = _timestamp_signal_summary(graph_data)

        generated_from = ["project_metadata"]
        if phase1_task_result:
            generated_from.append("phase1_task_result")
        if nodes or edges:
            generated_from.append("graph_data")
        if node_timestamp_count or edge_timestamp_count:
            generated_from.append("graph_created_at")

        timestamp_signal_available = bool(node_timestamp_count or edge_timestamp_count)
        if nodes or edges and timestamp_signal_available:
            data_completeness = "snapshot_with_timestamp_diagnostics"
            empty_reason = ""
        elif nodes or edges:
            data_completeness = "project_graph_no_timestamps"
            empty_reason = "当前项目图谱可用，但 builder 返回里没有稳定的 created_at 时间信号，因此无法展示真实时间线。"
        elif project.created_at or project.updated_at:
            data_completeness = "project_metadata_only"
            empty_reason = "当前只有项目级时间锚点，尚未形成图谱增长快照。"
        else:
            data_completeness = "empty"
            empty_reason = "当前项目还没有可用的演化信号。"

        return {
            "meta": {
                "projectId": project.project_id,
                "projectName": project.name,
                "graphId": project.graph_id,
                "phase1Status": str((phase1_task_result.get("build_outcome") or {}).get("status") or "unknown"),
                "viewVersion": "evolution-snapshot-v1",
                "generatedFrom": generated_from,
                "generatedAt": project.updated_at,
            },
            "projectOverview": {
                "createdAt": str(project.created_at or ""),
                "updatedAt": str(project.updated_at or ""),
                "hasGraph": bool(project.graph_id),
                "graphNodeCount": int(graph_data.get("node_count") or len(nodes)),
                "graphEdgeCount": int(graph_data.get("edge_count") or len(edges)),
                "hasReadingStructure": bool(project.reading_structure),
                "hasAnalysisSummary": bool(project.analysis_summary),
            },
            "knowledgeAssetSnapshot": {
                "readingStructureStatus": (
                    str((phase1_task_result.get("reading_structure_status") or {}).get("status") or "available")
                    if project.reading_structure
                    else "missing"
                ),
                "analysisSummaryStatus": "available" if project.analysis_summary else "missing",
                "graphStatus": "available" if project.graph_id else "missing",
                "availableViews": [
                    view
                    for view, enabled in [
                        ("article", True),
                        ("concept", bool(project.graph_id)),
                        ("theme", bool(project.graph_id or project.reading_structure)),
                        ("review", bool(project.graph_id or warnings)),
                        ("evolution", True),
                    ]
                    if enabled
                ],
                "evidenceCounts": {
                    "nodes": int(graph_data.get("node_count") or len(nodes)),
                    "edges": int(graph_data.get("edge_count") or len(edges)),
                    "readingGroupsCount": len(list(reading_structure.get("group_titles") or {})),
                    "warningsCount": len(warnings),
                },
            },
            "traceabilityAndSignalQuality": {
                "supportsTimeOrdering": "limited" if timestamp_signal_available else "false",
                "timeSignals": {
                    "projectCreatedAt": str(project.created_at or ""),
                    "projectUpdatedAt": str(project.updated_at or ""),
                    "nodeCreatedAtCoverage": node_coverage_label,
                    "edgeCreatedAtCoverage": edge_coverage_label,
                },
                "derivationNotes": [
                    "当前页面基于项目级元数据和当前图谱快照生成。",
                    "当前结果不代表历史版本序列，也不代表 concept/theme 的真实时间演化。",
                ],
                "confidenceFlags": {
                    "historicalSeriesAvailable": False,
                    "nodeTimestampConsistency": node_coverage_label if timestamp_signal_available else "unknown",
                    "crossProjectComparisonSupported": False,
                },
            },
            "nextCapabilitiesGap": {
                "missingCapabilities": [
                    "per-project snapshot history",
                    "concept merge/change log",
                    "theme evolution log",
                    "review audit history",
                    "stable event timestamps",
                ],
                "recommendedNextStep": "先补 project snapshot persistence 或 audit 历史，再考虑真正的 evolution timeline。",
                "readinessLevel": "snapshot_only",
            },
            "diagnostics": {
                "warnings": warnings,
                "emptyReason": empty_reason,
                "dataCompleteness": data_completeness,
                "timestampSignalAvailable": timestamp_signal_available,
            },
        }
