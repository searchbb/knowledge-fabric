"""Computed traceability view for strategic ResearchProjects."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any

from ..models.research_project import ResearchProject, ResearchProjectStore


LANES = [
    {"lane_id": "evidence", "title": "Evidence", "asset_types": ["evidence_item", "evidence_matrix_row"]},
    {"lane_id": "synthesis", "title": "Synthesis", "asset_types": ["insight_card"]},
    {
        "lane_id": "decision",
        "title": "Decision",
        "asset_types": ["strategic_option", "validation_plan", "leadership_decision_record"],
    },
    {"lane_id": "materials", "title": "Materials", "asset_types": ["artifact_draft", "artifact_pack"]},
    {"lane_id": "briefing", "title": "Leadership Briefing", "asset_types": ["leadership_briefing"]},
]

ASSET_CONFIG = {
    "evidence_item": {"id_field": "evidence_id", "lane_id": "evidence", "index_field": "evidence_items"},
    "evidence_matrix_row": {"id_field": "id", "lane_id": "evidence", "index_field": "evidence_matrix_rows"},
    "insight_card": {"id_field": "id", "lane_id": "synthesis", "index_field": "insight_cards"},
    "artifact_draft": {"id_field": "id", "lane_id": "materials", "index_field": "artifact_drafts"},
    "artifact_pack": {"id_field": "pack_id", "lane_id": "materials", "index_field": "artifact_packs"},
    "strategic_option": {"id_field": "option_id", "lane_id": "decision", "index_field": "strategic_options"},
    "validation_plan": {"id_field": "plan_id", "lane_id": "decision", "index_field": "validation_plans"},
    "leadership_decision_record": {
        "id_field": "decision_id",
        "lane_id": "decision",
        "index_field": "leadership_decision_records",
    },
    "leadership_briefing": {"id_field": "briefing_id", "lane_id": "briefing", "index_field": "leadership_briefings"},
}

REF_TYPE_BY_FIELD = {
    "supporting_evidence_ids": "evidence_item",
    "counter_evidence_ids": "evidence_item",
    "source_evidence_ids": "evidence_item",
    "source_evidence_matrix_row_ids": "evidence_matrix_row",
    "source_matrix_row_ids": "evidence_matrix_row",
    "matrix_row_ids": "evidence_matrix_row",
    "related_insight_ids": "insight_card",
    "source_insight_ids": "insight_card",
    "source_artifact_draft_ids": "artifact_draft",
    "source_artifact_pack_ids": "artifact_pack",
    "linked_artifact_draft_ids": "artifact_draft",
    "artifact_draft_id": "artifact_draft",
    "linked_option_ids": "strategic_option",
    "chosen_option_id": "strategic_option",
    "rejected_option_ids": "strategic_option",
    "deferred_option_ids": "strategic_option",
    "linked_validation_plan_ids": "validation_plan",
    "linked_decision_record_ids": "leadership_decision_record",
}

RELATION_BY_FIELD = {
    "supporting_evidence_ids": "supports",
    "counter_evidence_ids": "challenges",
    "related_insight_ids": "relates_to",
    "source_evidence_ids": "supports",
    "source_evidence_matrix_row_ids": "supports",
    "source_matrix_row_ids": "supports",
    "matrix_row_ids": "supports",
    "source_insight_ids": "supports",
    "source_artifact_draft_ids": "materializes",
    "source_artifact_pack_ids": "packages",
    "linked_artifact_draft_ids": "materializes",
    "artifact_draft_id": "materializes",
    "linked_option_ids": "plans",
    "chosen_option_id": "selects",
    "rejected_option_ids": "rejects",
    "deferred_option_ids": "defers",
    "linked_validation_plan_ids": "validates",
    "linked_decision_record_ids": "decides",
}

REF_ASSET_TYPE_ALIASES = {
    "evidence": "evidence_item",
    "evidence_item": "evidence_item",
    "evidence_matrix_row": "evidence_matrix_row",
    "matrix_row": "evidence_matrix_row",
    "insight": "insight_card",
    "insight_card": "insight_card",
    "artifact_draft": "artifact_draft",
    "artifact_pack": "artifact_pack",
    "strategic_option": "strategic_option",
    "validation_plan": "validation_plan",
    "leadership_decision_record": "leadership_decision_record",
    "leadership_briefing": "leadership_briefing",
}


def build_traceability_map(
    project_id: str,
    *,
    store: ResearchProjectStore | None = None,
    briefing_id: str | None = None,
    asset_type: str | None = None,
    issue_severity: str | None = None,
) -> dict[str, Any] | None:
    store = store or ResearchProjectStore()
    project = store.get(project_id)
    if project is None:
        return None

    assets = _collect_project_assets(project, store)
    nodes = _derive_nodes(assets)
    edges, reference_issues = _derive_edges(assets)
    semantic_issues = _derive_semantic_issues(assets, edges)
    issues = sorted(reference_issues + semantic_issues, key=lambda item: item["issue_id"])
    orphans = _derive_orphans(nodes, edges)

    if briefing_id:
        nodes, edges, issues, orphans = _filter_by_briefing(briefing_id, nodes, edges, issues, orphans)
    if asset_type:
        nodes, edges, issues, orphans = _filter_by_asset_type(asset_type, nodes, edges, issues, orphans)
    if issue_severity:
        issues = [issue for issue in issues if issue.get("severity") == issue_severity]

    summary = _summarize(nodes, edges, issues, orphans)
    return {
        "project_id": project_id,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "view_type": "strategic_research_traceability_map",
        "traceability_readiness": _readiness(summary),
        "summary": summary,
        "lanes": LANES,
        "nodes": nodes,
        "edges": edges,
        "issues": issues,
        "orphans": orphans,
        "filters": {
            "briefing_id": briefing_id or "",
            "asset_type": asset_type or "",
            "issue_severity": issue_severity or "",
        },
    }


def _collect_project_assets(project: ResearchProject, store: ResearchProjectStore) -> dict[str, dict[str, dict[str, Any]]]:
    assets: dict[str, dict[str, dict[str, Any]]] = {asset_type: {} for asset_type in ASSET_CONFIG}
    project_id = project.id
    assets["evidence_item"] = {
        str(item.get("evidence_id")): dict(item)
        for item in project.evidence_items
        if isinstance(item, dict) and item.get("evidence_id")
    }

    for asset_type, config in ASSET_CONFIG.items():
        if asset_type == "evidence_item":
            continue
        id_field = config["id_field"]
        index_field = config["index_field"]
        prefix = str(id_field).split("_")[0]
        if asset_type == "evidence_matrix_row":
            prefix = "emr"
        elif asset_type == "insight_card":
            prefix = "ic"
        elif asset_type == "artifact_draft":
            prefix = "ad"
        elif asset_type == "artifact_pack":
            prefix = "ap"
        elif asset_type == "strategic_option":
            prefix = "so"
        elif asset_type == "validation_plan":
            prefix = "vp"
        elif asset_type == "leadership_decision_record":
            prefix = "ldr"
        elif asset_type == "leadership_briefing":
            prefix = "lb"
        loaded = store._list_assets(project_id, str(index_field), prefix)
        for item in loaded:
            asset_id = item.get(id_field)
            if asset_id:
                assets[asset_type][str(asset_id)] = dict(item)
    return assets


def _derive_nodes(assets: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for asset_type in ASSET_CONFIG:
        config = ASSET_CONFIG[asset_type]
        for asset_id, asset in sorted(assets[asset_type].items()):
            nodes.append({
                "node_id": _node_id(asset_type, asset_id),
                "asset_type": asset_type,
                "asset_id": asset_id,
                "title": _title(asset, asset_id),
                "status": asset.get("status") or asset.get("decision_status") or "",
                "review_state": asset.get("review_state") or "",
                "readiness": asset.get("readiness") or asset.get("material_readiness") or "",
                "approval_state": asset.get("approval_state") or "",
                "lane_id": config["lane_id"],
                "source_fields": _source_fields(asset),
                "issue_counts": {"blocking": 0, "warning": 0, "info": 0},
            })
    return nodes


def _derive_edges(
    assets: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edges: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen_edges: set[str] = set()
    for asset_type in ASSET_CONFIG:
        for asset_id, asset in sorted(assets[asset_type].items()):
            refs = _extract_refs(asset_type, asset)
            for ref in refs:
                target_type = ref["asset_type"]
                target_id = ref["asset_id"]
                field = ref["field"]
                if target_type not in assets or target_id not in assets[target_type]:
                    issues.append(_missing_reference_issue(asset_type, asset_id, field, target_type, target_id, ref.get("required", False)))
                    continue
                from_node = _node_id(target_type, target_id)
                to_node = _node_id(asset_type, asset_id)
                edge_id = f"{from_node}->{to_node}:{field}"
                if edge_id in seen_edges:
                    continue
                seen_edges.add(edge_id)
                edges.append({
                    "edge_id": edge_id,
                    "from_node_id": from_node,
                    "to_node_id": to_node,
                    "relation_type": ref.get("relation_type") or RELATION_BY_FIELD.get(field, "references"),
                    "source_field": field,
                    "valid": True,
                })
    edges.sort(key=lambda item: item["edge_id"])
    issues.sort(key=lambda item: item["issue_id"])
    return edges, issues


def _extract_refs(asset_type: str, asset: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for field, ref_type in REF_TYPE_BY_FIELD.items():
        _append_field_refs(refs, asset.get(field), field, ref_type)

    if asset_type == "leadership_decision_record":
        for idx, rationale in enumerate(asset.get("rationale") or []):
            if isinstance(rationale, dict):
                _append_field_refs(refs, rationale.get("source_insight_ids"), f"rationale[{idx}].source_insight_ids", "insight_card")
                _append_field_refs(refs, rationale.get("source_evidence_ids"), f"rationale[{idx}].source_evidence_ids", "evidence_item")

    if asset_type == "artifact_pack":
        for idx, item in enumerate(asset.get("items") or []):
            if isinstance(item, dict):
                _append_field_refs(refs, item.get("artifact_draft_id"), f"items[{idx}].artifact_draft_id", "artifact_draft")
        for idx, page in enumerate(asset.get("pages") or []):
            if isinstance(page, dict):
                _append_field_refs(refs, page.get("source_artifact_draft_id"), f"pages[{idx}].source_artifact_draft_id", "artifact_draft")
                _append_field_refs(refs, page.get("source_insight_ids"), f"pages[{idx}].source_insight_ids", "insight_card")
                _append_field_refs(refs, page.get("source_evidence_ids"), f"pages[{idx}].source_evidence_ids", "evidence_item")
                _append_field_refs(refs, page.get("source_matrix_row_ids"), f"pages[{idx}].source_matrix_row_ids", "evidence_matrix_row")
        for idx, file_ref in enumerate(asset.get("file_refs") or []):
            if isinstance(file_ref, dict):
                _append_field_refs(refs, file_ref.get("linked_artifact_draft_ids"), f"file_refs[{idx}].linked_artifact_draft_ids", "artifact_draft")

    if asset_type == "leadership_briefing":
        for idx, source_ref in enumerate(asset.get("source_asset_refs") or []):
            _append_structured_ref(refs, source_ref, f"source_asset_refs[{idx}]")
        for idx, section in enumerate(asset.get("sections") or []):
            if isinstance(section, dict):
                for ref_idx, source_ref in enumerate(section.get("source_refs") or []):
                    _append_structured_ref(refs, source_ref, f"sections[{idx}].source_refs[{ref_idx}]")
        for idx, ask in enumerate(asset.get("decision_asks") or []):
            if isinstance(ask, dict):
                _append_field_refs(refs, ask.get("linked_option_ids"), f"decision_asks[{idx}].linked_option_ids", "strategic_option", required=True)
                _append_field_refs(refs, ask.get("linked_validation_plan_ids"), f"decision_asks[{idx}].linked_validation_plan_ids", "validation_plan")
                _append_field_refs(refs, ask.get("linked_decision_record_ids"), f"decision_asks[{idx}].linked_decision_record_ids", "leadership_decision_record")
    return refs


def _append_field_refs(
    refs: list[dict[str, Any]],
    raw: Any,
    field: str,
    asset_type: str,
    *,
    required: bool = False,
) -> None:
    values = raw if isinstance(raw, list) else ([raw] if raw else [])
    for value in values:
        if value:
            refs.append({
                "asset_type": asset_type,
                "asset_id": str(value),
                "field": field,
                "required": required,
            })


def _append_structured_ref(refs: list[dict[str, Any]], source_ref: Any, field: str) -> None:
    if not isinstance(source_ref, dict):
        return
    raw_type = str(source_ref.get("asset_type") or "")
    asset_type = REF_ASSET_TYPE_ALIASES.get(raw_type)
    asset_id = str(source_ref.get("asset_id") or "")
    if asset_type and asset_id:
        refs.append({
            "asset_type": asset_type,
            "asset_id": asset_id,
            "field": field,
            "required": bool(source_ref.get("required")),
            "relation_type": "cites",
        })


def _derive_semantic_issues(
    assets: dict[str, dict[str, dict[str, Any]]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    incoming = defaultdict(set)
    for edge in edges:
        incoming[edge["to_node_id"]].add(edge["from_node_id"])

    for insight_id, insight in assets["insight_card"].items():
        has_support = bool(insight.get("supporting_evidence_ids") or insight.get("matrix_row_ids"))
        if not has_support:
            issues.append(_issue("warning", "unsupported_insight", "insight_card", insight_id, "supporting_evidence_ids", "Insight has no evidence or matrix support."))

    for option_id, option in assets["strategic_option"].items():
        if not (option.get("source_insight_ids") or option.get("source_evidence_ids") or option.get("source_evidence_matrix_row_ids")):
            issues.append(_issue("warning", "unsupported_option", "strategic_option", option_id, "source_insight_ids", "Strategic option has no linked insight or evidence."))

    for plan_id, plan in assets["validation_plan"].items():
        if not plan.get("linked_option_ids"):
            issues.append(_issue("warning", "unlinked_validation_plan", "validation_plan", plan_id, "linked_option_ids", "Validation plan has no linked strategic option."))

    for draft_id, draft in assets["artifact_draft"].items():
        if not (draft.get("source_insight_ids") or draft.get("source_evidence_ids")):
            issues.append(_issue("warning", "unsupported_artifact_draft", "artifact_draft", draft_id, "source_insight_ids", "Artifact draft has no linked insight or evidence."))

    for pack_id, pack in assets["artifact_pack"].items():
        if not (pack.get("source_artifact_draft_ids") or pack.get("items") or pack.get("pages")):
            issues.append(_issue("warning", "thin_artifact_pack", "artifact_pack", pack_id, "source_artifact_draft_ids", "Artifact pack has no drafts, pages, or items."))

    for decision_id, decision in assets["leadership_decision_record"].items():
        if not decision.get("linked_option_ids"):
            issues.append(_issue("blocking", "decision_without_option", "leadership_decision_record", decision_id, "linked_option_ids", "Leadership decision record has no linked strategic option."))

    for briefing_id, briefing in assets["leadership_briefing"].items():
        required_refs = [
            ref for ref in (briefing.get("source_asset_refs") or [])
            if isinstance(ref, dict) and ref.get("required")
        ]
        ready_like = briefing.get("status") in {"in_review", "approved"} or briefing.get("readiness") in {"ready", "approved"}
        if ready_like and not required_refs:
            issues.append(_issue("warning", "briefing_without_required_sources", "leadership_briefing", briefing_id, "source_asset_refs", "Leadership briefing is marked ready without required source refs."))
        if not briefing.get("decision_asks") and (briefing.get("executive_summary") or {}).get("decision_required") is True:
            issues.append(_issue("blocking", "briefing_without_decision_ask", "leadership_briefing", briefing_id, "decision_asks", "Leadership briefing requires a decision ask but none is present."))
    return issues


def _derive_orphans(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, str]]:
    connected = set()
    for edge in edges:
        connected.add(edge["from_node_id"])
        connected.add(edge["to_node_id"])
    orphans = []
    for node in nodes:
        if node["node_id"] not in connected:
            reason = "No incoming or outgoing explicit traceability edge."
            if node["asset_type"] == "evidence_item":
                reason = "Evidence item is unused by downstream assets."
            orphans.append({"node_id": node["node_id"], "reason": reason})
    return sorted(orphans, key=lambda item: item["node_id"])


def _summarize(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    orphans: list[dict[str, Any]],
) -> dict[str, Any]:
    issue_counts = defaultdict(int)
    issues_by_node = defaultdict(lambda: {"blocking": 0, "warning": 0, "info": 0})
    for issue in issues:
        severity = issue.get("severity") or "info"
        issue_counts[severity] += 1
        node_id = _node_id(issue.get("asset_type", ""), issue.get("asset_id", ""))
        issues_by_node[node_id][severity] += 1
    for node in nodes:
        node["issue_counts"] = dict(issues_by_node[node["node_id"]])
    briefing_nodes = [node for node in nodes if node["asset_type"] == "leadership_briefing"]
    briefing_issue_ids = {
        issue.get("asset_id")
        for issue in issues
        if issue.get("asset_type") == "leadership_briefing" and issue.get("severity") == "blocking"
    }
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "blocking_issue_count": issue_counts["blocking"],
        "warning_issue_count": issue_counts["warning"],
        "orphan_node_count": len(orphans),
        "missing_reference_count": sum(1 for issue in issues if issue.get("issue_type") == "missing_reference"),
        "briefing_coverage": {
            "leadership_briefing_count": len(briefing_nodes),
            "briefings_with_required_refs": len([
                node for node in briefing_nodes
                if any(edge["to_node_id"] == node["node_id"] for edge in edges)
            ]),
            "briefings_with_blocking_issues": len(briefing_issue_ids),
        },
    }


def _filter_by_briefing(
    briefing_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    orphans: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    start = _node_id("leadership_briefing", briefing_id)
    adjacency = defaultdict(set)
    for edge in edges:
        adjacency[edge["from_node_id"]].add(edge["to_node_id"])
        adjacency[edge["to_node_id"]].add(edge["from_node_id"])
    keep = {start}
    pending = deque([start])
    while pending:
        current = pending.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in keep:
                keep.add(neighbor)
                pending.append(neighbor)
    nodes = [node for node in nodes if node["node_id"] in keep]
    edges = [edge for edge in edges if edge["from_node_id"] in keep and edge["to_node_id"] in keep]
    issues = [issue for issue in issues if _node_id(issue.get("asset_type", ""), issue.get("asset_id", "")) in keep]
    orphans = [orphan for orphan in orphans if orphan["node_id"] in keep]
    return nodes, edges, issues, orphans


def _filter_by_asset_type(
    asset_type: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    orphans: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = [node for node in nodes if node["asset_type"] == asset_type]
    keep = {node["node_id"] for node in nodes}
    edges = [edge for edge in edges if edge["from_node_id"] in keep or edge["to_node_id"] in keep]
    issues = [issue for issue in issues if issue.get("asset_type") == asset_type]
    orphans = [orphan for orphan in orphans if orphan["node_id"] in keep]
    return nodes, edges, issues, orphans


def _missing_reference_issue(
    asset_type: str,
    asset_id: str,
    field: str,
    ref_type: str,
    ref_id: str,
    required: bool,
) -> dict[str, Any]:
    severity = "blocking" if required or asset_type in {"leadership_briefing", "leadership_decision_record", "validation_plan"} else "warning"
    issue_id = f"missing-ref:{asset_type}:{asset_id}:{field}:{ref_type}:{ref_id}"
    return {
        "issue_id": issue_id,
        "severity": severity,
        "issue_type": "missing_reference",
        "asset_type": asset_type,
        "asset_id": asset_id,
        "field": field,
        "missing_ref": ref_id,
        "missing_asset_type": ref_type,
        "message": f"{asset_type} {asset_id} references missing {ref_type} {ref_id}.",
    }


def _issue(severity: str, issue_type: str, asset_type: str, asset_id: str, field: str, message: str) -> dict[str, Any]:
    return {
        "issue_id": f"{issue_type}:{asset_type}:{asset_id}:{field}",
        "severity": severity,
        "issue_type": issue_type,
        "asset_type": asset_type,
        "asset_id": asset_id,
        "field": field,
        "message": message,
    }


def _readiness(summary: dict[str, Any]) -> str:
    if summary["blocking_issue_count"]:
        return "blocked"
    if summary["warning_issue_count"]:
        return "needs_review"
    return "ready"


def _source_fields(asset: dict[str, Any]) -> list[str]:
    fields = sorted(field for field in REF_TYPE_BY_FIELD if asset.get(field))
    if asset.get("source_asset_refs"):
        fields.append("source_asset_refs")
    return fields


def _title(asset: dict[str, Any], fallback: str) -> str:
    return str(asset.get("title") or asset.get("question") or asset.get("claim") or fallback)


def _node_id(asset_type: str, asset_id: str) -> str:
    return f"{asset_type}:{asset_id}"
