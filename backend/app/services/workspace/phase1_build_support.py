"""Phase 1 build support helpers extracted from the graph API module.

These helpers are intentionally behavior-preserving wrappers around the legacy
Phase 1 flow so `backend/app/api/graph.py` can become a thinner adapter without
changing external contracts.
"""

from __future__ import annotations

from ...utils.logger import get_logger

logger = get_logger("mirofish.phase1")

PHASE1_MIN_SUCCESS_RATIO = 0.75
PHASE1_MIN_SUMMARY_COVERAGE_FOR_READING_STRUCTURE = 0.5
PHASE1_RESULT_VERSION = "phase1.v1"


def _default_phase1_diagnostics() -> dict:
    return {
        "provider": "",
        "chunk_count": 0,
        "processed_chunk_count": 0,
        "episode_count": 0,
        "soft_failed_chunk_count": 0,
        "soft_failed_chunks": [],
        "dropped_constraints": [],
        "retry_count": 0,
        "rate_limit_hit_count": 0,
        "aborted_due_to_rate_limit": False,
        "aborted_chunk_index": None,
        "abort_reason": "",
        "json_parse_repair_count": 0,
        "json_parse_retry_count": 0,
        "json_parse_failure_count": 0,
        "adaptive_split_count": 0,
        "adaptive_subchunk_count": 0,
        "summary_backfill_requested": 0,
        "summary_backfill_completed": 0,
        "summary_backfill_missing": [],
        "summary_backfill_error": "",
    }


def _normalize_phase1_diagnostics(
    diagnostics: dict | None,
    *,
    provider: str,
    chunk_count: int = 0,
    dropped_constraints: list[str] | None = None,
) -> dict:
    normalized = _default_phase1_diagnostics()
    if isinstance(diagnostics, dict):
        normalized.update(diagnostics)

    normalized["provider"] = provider

    int_keys = (
        "chunk_count",
        "processed_chunk_count",
        "episode_count",
        "soft_failed_chunk_count",
        "retry_count",
        "rate_limit_hit_count",
        "json_parse_repair_count",
        "json_parse_retry_count",
        "json_parse_failure_count",
        "adaptive_split_count",
        "adaptive_subchunk_count",
        "summary_backfill_requested",
        "summary_backfill_completed",
    )
    for key in int_keys:
        try:
            normalized[key] = max(int(normalized.get(key) or 0), 0)
        except (TypeError, ValueError):
            normalized[key] = 0

    normalized["chunk_count"] = max(normalized["chunk_count"], max(int(chunk_count or 0), 0))

    normalized["aborted_due_to_rate_limit"] = bool(normalized.get("aborted_due_to_rate_limit"))

    aborted_chunk_index = normalized.get("aborted_chunk_index")
    try:
        normalized["aborted_chunk_index"] = (
            max(int(aborted_chunk_index), 1) if aborted_chunk_index is not None else None
        )
    except (TypeError, ValueError):
        normalized["aborted_chunk_index"] = None

    soft_failed_chunks = normalized.get("soft_failed_chunks")
    normalized["soft_failed_chunks"] = soft_failed_chunks if isinstance(soft_failed_chunks, list) else []
    summary_backfill_missing = normalized.get("summary_backfill_missing")
    normalized["summary_backfill_missing"] = (
        summary_backfill_missing if isinstance(summary_backfill_missing, list) else []
    )

    merged_constraints = normalized.get("dropped_constraints")
    merged_constraints = merged_constraints if isinstance(merged_constraints, list) else []
    for constraint in dropped_constraints or []:
        if constraint and constraint not in merged_constraints:
            merged_constraints.append(constraint)
    normalized["dropped_constraints"] = merged_constraints

    normalized["abort_reason"] = str(normalized.get("abort_reason") or "")
    normalized["summary_backfill_error"] = str(normalized.get("summary_backfill_error") or "")
    return normalized


def _write_supplement_to_neo4j(builder, graph_id: str, supplement) -> None:
    """将补抽结果写入 Neo4j 图谱。"""

    async def _write():
        client = await builder._get_client()
        driver = client.driver

        async with driver.session() as session:
            for node in supplement.new_nodes:
                await session.run(
                    """
                    MERGE (n:Entity {name: $name, group_id: $group_id})
                    SET n:""" + node["type"] + """,
                        n.summary = $summary,
                        n.created_at = datetime()
                    """,
                    name=node["name"],
                    group_id=graph_id,
                    summary=node.get("summary", ""),
                )

            for edge in supplement.new_edges:
                await session.run(
                    """
                    MATCH (s:Entity {group_id: $group_id})
                    WHERE s.name = $source
                    MATCH (t:Entity {group_id: $group_id})
                    WHERE t.name = $target
                    MERGE (s)-[r:RELATES_TO {name: $relation, group_id: $group_id}]->(t)
                    SET r.fact = $fact,
                        r.fact_type = $relation,
                        r.created_at = datetime()
                    """,
                    group_id=graph_id,
                    source=edge["source"],
                    target=edge["target"],
                    relation=edge["relation"],
                    fact=edge.get("fact", ""),
                )

    builder._run_async(_write())


def _merge_duplicate_nodes(
    builder,
    graph_id: str,
    dupes: list,
    *,
    build_logger=None,
) -> None:
    """合并近似重复节点：将 merge 节点的边转移到 keep 节点，删除 merge 节点。"""
    active_logger = build_logger or logger

    async def _merge():
        client = await builder._get_client()
        driver = client.driver
        merged_uuids = set()
        for keep_uuid, merge_uuid, keep_name, merge_name, sim in dupes:
            if merge_uuid in merged_uuids:
                continue
            merged_uuids.add(merge_uuid)
            try:
                async with driver.session() as session:
                    await session.run(
                        """
                        MATCH (merge:Entity {uuid: $merge_uuid, group_id: $gid})
                        MATCH (keep:Entity {uuid: $keep_uuid, group_id: $gid})
                        OPTIONAL MATCH (other)-[r:RELATES_TO]->(merge)
                        WHERE other.uuid <> $keep_uuid AND other.uuid <> $merge_uuid
                        WITH keep, r, other
                        WHERE r IS NOT NULL
                        CREATE (other)-[nr:RELATES_TO]->(keep)
                        SET nr = properties(r)
                        DELETE r
                        """,
                        merge_uuid=merge_uuid,
                        keep_uuid=keep_uuid,
                        gid=graph_id,
                    )
                    await session.run(
                        """
                        MATCH (merge:Entity {uuid: $merge_uuid, group_id: $gid})
                        MATCH (keep:Entity {uuid: $keep_uuid, group_id: $gid})
                        OPTIONAL MATCH (merge)-[r:RELATES_TO]->(other)
                        WHERE other.uuid <> $keep_uuid AND other.uuid <> $merge_uuid
                        WITH keep, r, other
                        WHERE r IS NOT NULL
                        CREATE (keep)-[nr:RELATES_TO]->(other)
                        SET nr = properties(r)
                        DELETE r
                        """,
                        merge_uuid=merge_uuid,
                        keep_uuid=keep_uuid,
                        gid=graph_id,
                    )
                    await session.run(
                        "MATCH (n:Entity {uuid: $merge_uuid, group_id: $gid}) DETACH DELETE n",
                        merge_uuid=merge_uuid,
                        gid=graph_id,
                    )
                active_logger.info(
                    "合并节点: '%s' → '%s' (sim=%.2f)",
                    merge_name,
                    keep_name,
                    sim,
                )
            except Exception as exc:  # pragma: no cover - defensive logging only
                active_logger.warning("合并节点 '%s' 失败: %s", merge_name, exc)

    builder._run_async(_merge())


def _write_summaries_to_neo4j(builder, graph_id: str, summaries: dict) -> None:
    """将回填的 summary 写入 Neo4j 图谱。summaries: {node_name: summary_text}"""

    async def _write():
        client = await builder._get_client()
        driver = client.driver
        async with driver.session() as session:
            for name, summary in summaries.items():
                await session.run(
                    """
                    MATCH (n:Entity {name: $name, group_id: $group_id})
                    WHERE n.summary IS NULL OR n.summary = ''
                    SET n.summary = $summary
                    """,
                    name=name,
                    group_id=graph_id,
                    summary=summary,
                )

    builder._run_async(_write())


def _normalize_phase1_build_outcome(outcome: dict | None) -> dict:
    normalized = {
        "status": "unknown",
        "reason": "",
        "success_ratio": 0.0,
        "can_generate_reading_structure": False,
        "warnings": [],
    }
    if isinstance(outcome, dict):
        normalized.update(outcome)

    try:
        normalized["success_ratio"] = round(float(normalized.get("success_ratio") or 0.0), 3)
    except (TypeError, ValueError):
        normalized["success_ratio"] = 0.0

    normalized["status"] = str(normalized.get("status") or "unknown")
    normalized["reason"] = str(normalized.get("reason") or "")
    normalized["can_generate_reading_structure"] = bool(normalized.get("can_generate_reading_structure"))
    warnings = normalized.get("warnings")
    normalized["warnings"] = warnings if isinstance(warnings, list) else []
    return normalized


def _normalize_phase1_reading_structure_status(status: dict | None) -> dict:
    normalized = {
        "status": "not_started",
        "reason": "",
        "error_kind": "",
    }
    if isinstance(status, dict):
        normalized.update(status)
    normalized["status"] = str(normalized.get("status") or "not_started")
    normalized["reason"] = str(normalized.get("reason") or "")
    normalized["error_kind"] = str(normalized.get("error_kind") or "")
    return normalized


def _build_phase1_task_result(
    *,
    provider: str,
    project_id: str,
    graph_id: str | None,
    chunk_count: int,
    node_count: int,
    edge_count: int,
    diagnostics: dict | None,
    build_outcome: dict | None,
    reading_structure_status: dict | None,
    dropped_constraints: list[str] | None = None,
) -> dict:
    normalized_diagnostics = _normalize_phase1_diagnostics(
        diagnostics,
        provider=provider,
        chunk_count=chunk_count,
        dropped_constraints=dropped_constraints,
    )
    normalized_build_outcome = _normalize_phase1_build_outcome(build_outcome)
    normalized_reading_status = _normalize_phase1_reading_structure_status(reading_structure_status)

    return {
        "contract_version": PHASE1_RESULT_VERSION,
        "phase": "knowledge_workbench_phase1",
        "provider": provider,
        "project_id": project_id,
        "graph_id": graph_id,
        "node_count": node_count,
        "edge_count": edge_count,
        "chunk_count": chunk_count,
        "diagnostics": normalized_diagnostics,
        "build_outcome": normalized_build_outcome,
        "reading_structure_status": normalized_reading_status,
        "artifacts": {
            "graph": {
                "graph_id": graph_id,
                "node_count": node_count,
                "edge_count": edge_count,
                "build_status": normalized_build_outcome["status"],
            },
            "reading_structure": normalized_reading_status,
        },
    }


def _build_phase1_completion_decision(diagnostics: dict, graph_data: dict) -> dict:
    chunk_count = max(int((diagnostics or {}).get("chunk_count") or 0), 0)
    processed_chunk_count = max(int((diagnostics or {}).get("processed_chunk_count") or 0), 0)
    soft_failed_chunk_count = max(int((diagnostics or {}).get("soft_failed_chunk_count") or 0), 0)
    success_ratio = (processed_chunk_count / chunk_count) if chunk_count else 0.0
    node_count = max(int((graph_data or {}).get("node_count") or 0), 0)
    edge_count = max(int((graph_data or {}).get("edge_count") or 0), 0)
    nodes = (graph_data or {}).get("nodes") or []
    aborted_due_to_rate_limit = bool((diagnostics or {}).get("aborted_due_to_rate_limit"))
    summarized_node_count = sum(
        1 for node in nodes
        if isinstance(node, dict) and str(node.get("summary") or "").strip()
    )
    summary_coverage = (summarized_node_count / node_count) if node_count else 0.0

    warnings = []
    if soft_failed_chunk_count:
        warnings.append(f"{soft_failed_chunk_count} 个文本块未成功处理")
    if chunk_count and processed_chunk_count < chunk_count:
        warnings.append(f"文本块完成率 {processed_chunk_count}/{chunk_count}")

    if processed_chunk_count == 0:
        return {
            "status": "failed",
            "reason": "所有文本块都未成功处理",
            "success_ratio": round(success_ratio, 3),
            "can_generate_reading_structure": False,
            "warnings": warnings,
        }

    if aborted_due_to_rate_limit:
        return {
            "status": "failed",
            "reason": "触发上游限额并已提前中止，当前图谱不应标记为完成",
            "success_ratio": round(success_ratio, 3),
            "can_generate_reading_structure": False,
            "warnings": warnings,
        }

    if node_count == 0 and edge_count == 0:
        return {
            "status": "failed",
            "reason": "图谱构建完成但未产出任何节点或关系，请检查图谱抽取结果",
            "success_ratio": round(success_ratio, 3),
            "can_generate_reading_structure": False,
            "warnings": warnings,
        }

    if chunk_count and success_ratio < PHASE1_MIN_SUCCESS_RATIO:
        return {
            "status": "failed",
            "reason": f"文本块完成率不足 {PHASE1_MIN_SUCCESS_RATIO:.0%}，当前结果不应标记为完成",
            "success_ratio": round(success_ratio, 3),
            "can_generate_reading_structure": False,
            "warnings": warnings,
        }

    if node_count and summary_coverage < PHASE1_MIN_SUMMARY_COVERAGE_FOR_READING_STRUCTURE:
        warnings.append(f"summary 覆盖率过低 {summarized_node_count}/{node_count}")
        return {
            "status": "completed_with_warnings",
            "reason": (
                "summary 覆盖率不足 "
                f"{PHASE1_MIN_SUMMARY_COVERAGE_FOR_READING_STRUCTURE:.0%}，"
                "当前结果不应生成阅读骨架"
            ),
            "success_ratio": round(success_ratio, 3),
            "can_generate_reading_structure": False,
            "warnings": warnings,
        }

    return {
        "status": "completed_with_warnings" if warnings else "completed",
        "reason": "",
        "success_ratio": round(success_ratio, 3),
        "can_generate_reading_structure": bool(node_count or edge_count),
        "warnings": warnings,
    }
