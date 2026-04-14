"""Project-scoped concept summary aggregation for the Phase 2 workspace."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ...models.project import ProjectManager
from .concept_normalization import resolve_merge_chains
from .project_workspace_sources import load_graph_data, load_phase1_task_result


class ConceptViewNotFoundError(RuntimeError):
    """Raised when the requested project does not exist."""


def _node_label(node: dict[str, Any]) -> str:
    labels = node.get("labels") or []
    return labels[0] if labels else "Node"


def _normalize_name(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _candidate_key(node: dict[str, Any]) -> str:
    name = _normalize_name(node.get("name"))
    label = _node_label(node)
    return f"{label}:{name}" if name else f"{label}:{node.get('uuid')}"


def _sample_evidence_for_candidate(
    group_nodes: list[dict[str, Any]],
    adjacency: dict[str, list[str]],
) -> list[str]:
    evidence: list[str] = []
    for node in group_nodes:
        summary = str(node.get("summary") or "").strip()
        if summary:
            evidence.append(summary)
        for neighbor_name in adjacency.get(str(node.get("uuid")), []):
            if neighbor_name:
                evidence.append(f"关联节点：{neighbor_name}")

    unique: list[str] = []
    seen = set()
    for item in evidence:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique[:3]


def build_candidate_concepts(graph_data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = list(graph_data.get("nodes") or [])
    edges = list(graph_data.get("edges") or [])
    if not nodes:
        return [], []

    node_by_id = {str(node.get("uuid")): node for node in nodes if node.get("uuid")}
    edge_hits: Counter[str] = Counter()
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        source_id = str(edge.get("source_node_uuid") or "")
        target_id = str(edge.get("target_node_uuid") or "")
        if source_id:
            edge_hits[source_id] += 1
        if target_id:
            edge_hits[target_id] += 1

        source_name = str(node_by_id.get(source_id, {}).get("name") or "").strip()
        target_name = str(node_by_id.get(target_id, {}).get("name") or "").strip()
        if source_id and target_name:
            adjacency[source_id].append(target_name)
        if target_id and source_name:
            adjacency[target_id].append(source_name)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        grouped[_candidate_key(node)].append(node)

    candidates: list[dict[str, Any]] = []
    for key, group_nodes in grouped.items():
        primary = group_nodes[0]
        source_node_ids = [str(node.get("uuid")) for node in group_nodes if node.get("uuid")]
        connected_count = sum(edge_hits.get(node_id, 0) for node_id in source_node_ids)
        candidates.append(
            {
                "key": key,
                "displayName": str(primary.get("name") or "Unnamed Concept"),
                "conceptType": _node_label(primary),
                "mentionCount": len(group_nodes),
                "connectedCount": connected_count,
                "sampleEvidence": _sample_evidence_for_candidate(group_nodes, adjacency),
                "sourceNodeIds": source_node_ids,
                "status": "unreviewed",
            }
        )

    candidates.sort(
        key=lambda item: (
            -int(item["mentionCount"]),
            -int(item["connectedCount"]),
            str(item["displayName"]).lower(),
        )
    )

    type_counts = Counter(item["conceptType"] for item in candidates)
    top_types = [
        {"type": concept_type, "count": count}
        for concept_type, count in type_counts.most_common(6)
    ]
    return candidates, top_types


class ConceptViewService:
    """Builds a project-scoped, read-only concept summary view model."""

    def build_project_view(self, project_id: str) -> dict[str, Any]:
        project = ProjectManager.get_project(project_id)
        if not project:
            raise ConceptViewNotFoundError(f"项目不存在: {project_id}")

        phase1_task_result = load_phase1_task_result(project)
        graph_data = load_graph_data(project.graph_id)
        nodes = list(graph_data.get("nodes") or [])
        edges = list(graph_data.get("edges") or [])
        warnings = list((phase1_task_result.get("build_outcome") or {}).get("warnings") or [])
        candidates, type_counts = build_candidate_concepts(graph_data)

        # Overlay persisted concept decisions + resolve merge chains
        persisted = (project.concept_decisions or {}).get("items") or {}
        merge_resolved = resolve_merge_chains(project.concept_decisions or {})
        for candidate in candidates:
            decision = persisted.get(candidate.get("key"))
            if decision:
                candidate["status"] = decision.get("status", candidate.get("status"))
                candidate["note"] = decision.get("note", "")
                candidate["canonicalName"] = decision.get("canonical_name", "")
                candidate["mergeTo"] = decision.get("merge_to", "")
                candidate["aliases"] = decision.get("aliases", [])
                candidate["decisionUpdatedAt"] = decision.get("updated_at")
            # Resolve transitive merge target
            final_target = merge_resolved.get(candidate.get("key"))
            if final_target:
                candidate["resolvedMergeTo"] = final_target

        if not project.graph_id:
            empty_reason = "当前项目还没有 graph_id，概念视图暂时无法生成候选总览。"
            data_completeness = "empty"
        elif not nodes:
            empty_reason = "当前图谱没有节点，概念候选总览为空。"
            data_completeness = "graph_empty"
        elif phase1_task_result:
            empty_reason = ""
            data_completeness = "graph_with_phase1_snapshot"
        else:
            empty_reason = ""
            data_completeness = "graph_only"

        return {
            "meta": {
                "projectId": project.project_id,
                "projectName": project.name,
                "graphId": project.graph_id,
                "phase1Status": str((phase1_task_result.get("build_outcome") or {}).get("status") or "unknown"),
                "sourceScope": "project_graph",
                "generatedAt": project.updated_at,
            },
            "conceptDecisionsVersion": (project.concept_decisions or {}).get("version", 0),
            "summary": {
                "nodeCount": int(graph_data.get("node_count") or len(nodes)),
                "edgeCount": int(graph_data.get("edge_count") or len(edges)),
                "typedNodeCount": sum(1 for node in nodes if node.get("labels")),
                "candidateConceptCount": len(candidates),
                "acceptedCount": sum(1 for c in candidates if c.get("status") == "accepted"),
                "rejectedCount": sum(1 for c in candidates if c.get("status") == "rejected"),
                "mergedCount": sum(1 for c in candidates if c.get("status") == "merged"),
                "canonicalCount": sum(1 for c in candidates if c.get("status") == "canonical"),
                "unreviewedCount": sum(1 for c in candidates if c.get("status") in ("unreviewed", "pending")),
                "relationCount": len(edges),
                "warningsCount": len(warnings),
            },
            "candidateConcepts": candidates,
            "diagnostics": {
                "warnings": warnings,
                "emptyReason": empty_reason,
                "dataCompleteness": data_completeness,
                "typeCounts": type_counts,
            },
        }
