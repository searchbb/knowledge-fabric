"""
抽取层对照测试服务

三组对照：
1. 旧版 MiroFish + Zep baseline
2. Zep + 新技术文章 ontology
3. 本地 Graphiti + 新技术文章 ontology
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import Field, create_model
from zep_cloud import EntityEdgeSourceTarget
from zep_cloud.client import Zep
from zep_cloud.external_clients.ontology import EdgeModel, EntityModel, EntityText

from ..config import Config
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_edges, fetch_all_nodes
from .graph_builder import GraphBuilderService
from .legacy_social_ontology_generator import LegacySocialOntologyGenerator
from .ontology_generator import OntologyGenerator
from .text_processor import TextProcessor

logger = get_logger("mirofish.extraction_benchmark")

_DEFAULT_ENTITY_LABELS = {"Entity", "Node", "__Entity__"}
_CORE_EDGE_TYPES = ("HAS_PROBLEM", "SOLVES", "IMPLEMENTED_BY")
_RESERVED_ATTRS = {"name", "uuid", "group_id", "created_at", "summary", "name_embedding"}


@dataclass
class GraphBenchmarkMetrics:
    node_count: int
    edge_count: int
    entity_type_counts: Dict[str, int]
    edge_type_counts: Dict[str, int]
    unexpected_entity_types: List[str]
    unexpected_edge_types: List[str]
    orphan_edge_count: int
    invalid_edge_count: int
    invalid_edge_rate: float
    entity_type_coverage: float
    edge_type_coverage: float
    core_backbone_edges: Dict[str, int]
    core_backbone_score: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkRunResult:
    provider: str
    graph_id: Optional[str]
    duration_seconds: float
    chunk_count: int
    profile: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    metrics: Optional[GraphBenchmarkMetrics] = None
    preview: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["metrics"] = self.metrics.to_dict() if self.metrics is not None else None
        return data


def _first_entity_label(labels: Sequence[str] | None) -> str:
    for label in labels or []:
        if label and label not in _DEFAULT_ENTITY_LABELS:
            return label
    return ""


def _build_allowed_edge_pairs(ontology: Dict[str, Any]) -> set[tuple[str, str, str]]:
    allowed_pairs: set[tuple[str, str, str]] = set()
    for edge_def in ontology.get("edge_types", []):
        edge_name = edge_def.get("name")
        if not edge_name:
            continue
        for source_target in edge_def.get("source_targets", []):
            source = source_target.get("source")
            target = source_target.get("target")
            if source and target:
                allowed_pairs.add((source, edge_name, target))
    return allowed_pairs


def summarize_graph_data(graph_data: Dict[str, Any], ontology: Dict[str, Any]) -> GraphBenchmarkMetrics:
    nodes = graph_data.get("nodes", []) or []
    edges = graph_data.get("edges", []) or []

    ontology_entity_types = {
        entity_def.get("name")
        for entity_def in ontology.get("entity_types", [])
        if entity_def.get("name")
    }
    ontology_edge_types = {
        edge_def.get("name")
        for edge_def in ontology.get("edge_types", [])
        if edge_def.get("name")
    }
    allowed_edge_pairs = _build_allowed_edge_pairs(ontology)

    entity_type_counts: Dict[str, int] = {}
    node_type_by_uuid: Dict[str, str] = {}
    node_name_by_uuid: Dict[str, str] = {}
    for node in nodes:
        node_uuid = str(node.get("uuid", ""))
        node_type = _first_entity_label(node.get("labels", []))
        if node_uuid:
            node_type_by_uuid[node_uuid] = node_type
            node_name_by_uuid[node_uuid] = str(node.get("name", ""))
        if node_type:
            entity_type_counts[node_type] = entity_type_counts.get(node_type, 0) + 1

    edge_type_counts: Dict[str, int] = {}
    orphan_edge_count = 0
    invalid_edge_count = 0
    core_backbone_edges = {edge_name: 0 for edge_name in _CORE_EDGE_TYPES if edge_name in ontology_edge_types}

    for edge in edges:
        edge_name = str(edge.get("name") or edge.get("fact_type") or "").strip()
        if not edge_name:
            continue

        edge_type_counts[edge_name] = edge_type_counts.get(edge_name, 0) + 1

        source_uuid = str(edge.get("source_node_uuid", ""))
        target_uuid = str(edge.get("target_node_uuid", ""))
        source_type = node_type_by_uuid.get(source_uuid, "")
        target_type = node_type_by_uuid.get(target_uuid, "")

        if not source_type or not target_type:
            orphan_edge_count += 1
            invalid_edge_count += 1
            continue

        if allowed_edge_pairs and (source_type, edge_name, target_type) not in allowed_edge_pairs:
            invalid_edge_count += 1
            continue

        if edge_name in core_backbone_edges:
            core_backbone_edges[edge_name] += 1

    entity_types_present = set(entity_type_counts)
    edge_types_present = set(edge_type_counts)

    entity_type_coverage = (
        len(entity_types_present & ontology_entity_types) / len(ontology_entity_types)
        if ontology_entity_types else 0.0
    )
    edge_type_coverage = (
        len(edge_types_present & ontology_edge_types) / len(ontology_edge_types)
        if ontology_edge_types else 0.0
    )

    return GraphBenchmarkMetrics(
        node_count=len(nodes),
        edge_count=len(edges),
        entity_type_counts=entity_type_counts,
        edge_type_counts=edge_type_counts,
        unexpected_entity_types=sorted(entity_types_present - ontology_entity_types),
        unexpected_edge_types=sorted(edge_types_present - ontology_edge_types),
        orphan_edge_count=orphan_edge_count,
        invalid_edge_count=invalid_edge_count,
        invalid_edge_rate=(invalid_edge_count / len(edges)) if edges else 0.0,
        entity_type_coverage=entity_type_coverage,
        edge_type_coverage=edge_type_coverage,
        core_backbone_edges=core_backbone_edges,
        core_backbone_score=sum(1 for count in core_backbone_edges.values() if count > 0),
    )


def compare_benchmark_runs(
    local_metrics: Optional[GraphBenchmarkMetrics],
    zep_metrics: Optional[GraphBenchmarkMetrics],
) -> Dict[str, Any]:
    if local_metrics is None or zep_metrics is None:
        return {
            "status": "incomplete",
            "reason": "missing_metrics",
            "local_available": local_metrics is not None,
            "zep_available": zep_metrics is not None,
        }

    def _ratio(numerator: int, denominator: int) -> Optional[float]:
        if denominator <= 0:
            return None
        return round(numerator / denominator, 4)

    return {
        "status": "ok",
        "node_count_ratio_vs_zep": _ratio(local_metrics.node_count, zep_metrics.node_count),
        "edge_count_ratio_vs_zep": _ratio(local_metrics.edge_count, zep_metrics.edge_count),
        "entity_type_coverage_delta": round(
            local_metrics.entity_type_coverage - zep_metrics.entity_type_coverage, 4
        ),
        "edge_type_coverage_delta": round(
            local_metrics.edge_type_coverage - zep_metrics.edge_type_coverage, 4
        ),
        "invalid_edge_rate_delta": round(
            local_metrics.invalid_edge_rate - zep_metrics.invalid_edge_rate, 4
        ),
        "core_backbone_score_delta": local_metrics.core_backbone_score - zep_metrics.core_backbone_score,
        "local_core_backbone": local_metrics.core_backbone_edges,
        "zep_core_backbone": zep_metrics.core_backbone_edges,
    }


def compare_run_summaries(
    left: BenchmarkRunResult,
    right: BenchmarkRunResult,
) -> Dict[str, Any]:
    result = {
        "status": "ok",
        "left_profile": left.profile or left.provider,
        "right_profile": right.profile or right.provider,
        "left_status": left.status,
        "right_status": right.status,
        "left_duration_seconds": left.duration_seconds,
        "right_duration_seconds": right.duration_seconds,
        "left_error": left.error,
        "right_error": right.error,
    }

    if left.duration_seconds > 0 and right.duration_seconds > 0:
        result["duration_ratio_left_vs_right"] = round(left.duration_seconds / right.duration_seconds, 4)
    else:
        result["duration_ratio_left_vs_right"] = None

    if left.metrics is not None and right.metrics is not None:
        result["left_node_count"] = left.metrics.node_count
        result["right_node_count"] = right.metrics.node_count
        result["left_edge_count"] = left.metrics.edge_count
        result["right_edge_count"] = right.metrics.edge_count
        result["node_count_ratio_left_vs_right"] = (
            round(left.metrics.node_count / right.metrics.node_count, 4)
            if right.metrics.node_count > 0 else None
        )
        result["edge_count_ratio_left_vs_right"] = (
            round(left.metrics.edge_count / right.metrics.edge_count, 4)
            if right.metrics.edge_count > 0 else None
        )
    else:
        result["status"] = "incomplete"
        result["left_node_count"] = left.metrics.node_count if left.metrics else None
        result["right_node_count"] = right.metrics.node_count if right.metrics else None
        result["left_edge_count"] = left.metrics.edge_count if left.metrics else None
        result["right_edge_count"] = right.metrics.edge_count if right.metrics else None
        result["node_count_ratio_left_vs_right"] = None
        result["edge_count_ratio_left_vs_right"] = None

    return result


def build_zep_ontology_classes(
    ontology: Dict[str, Any],
) -> tuple[dict[str, type[EntityModel]], dict[str, Any]]:
    entity_models: dict[str, type[EntityModel]] = {}
    edge_models: dict[str, Any] = {}

    for entity_def in ontology.get("entity_types", []):
        name = entity_def.get("name")
        if not name:
            continue

        fields: Dict[str, Any] = {}
        for attr_def in entity_def.get("attributes", []):
            attr_name = str(attr_def.get("name", "")).strip()
            if not attr_name:
                continue
            if attr_name.lower() in _RESERVED_ATTRS:
                attr_name = f"entity_{attr_name}"
            fields[attr_name] = (
                EntityText,
                Field(default=None, description=attr_def.get("description", attr_name)),
            )

        model = create_model(name, __base__=EntityModel, **fields)
        model.__doc__ = entity_def.get("description") or f"{name} entity"
        entity_models[name] = model

    for edge_def in ontology.get("edge_types", []):
        name = edge_def.get("name")
        if not name:
            continue

        fields: Dict[str, Any] = {}
        for attr_def in edge_def.get("attributes", []):
            attr_name = str(attr_def.get("name", "")).strip()
            if not attr_name:
                continue
            if attr_name.lower() in _RESERVED_ATTRS:
                attr_name = f"edge_{attr_name}"
            fields[attr_name] = (
                EntityText,
                Field(default=None, description=attr_def.get("description", attr_name)),
            )

        model = create_model(name, __base__=EdgeModel, **fields)
        model.__doc__ = edge_def.get("description") or f"{name} edge"

        source_targets = [
            EntityEdgeSourceTarget(
                source=source_target.get("source"),
                target=source_target.get("target"),
            )
            for source_target in edge_def.get("source_targets", [])
            if source_target.get("source") and source_target.get("target")
        ]
        edge_models[name] = (model, source_targets) if source_targets else model

    return entity_models, edge_models


class ExtractionBenchmarkService:
    """运行本地抽取层和 Zep 对照组的统一 benchmark。"""

    def __init__(
        self,
        ontology_generator: Optional[OntologyGenerator] = None,
        legacy_social_generator: Optional[LegacySocialOntologyGenerator] = None,
        local_builder: Optional[GraphBuilderService] = None,
        zep_client: Optional[Zep] = None,
    ):
        self.ontology_generator = ontology_generator or OntologyGenerator()
        self.legacy_social_generator = legacy_social_generator or LegacySocialOntologyGenerator()
        self.local_builder = local_builder or GraphBuilderService()
        self.zep_client = zep_client

    def prepare_text(
        self,
        file_path: str,
        chunk_size: int = Config.DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = Config.DEFAULT_CHUNK_OVERLAP,
    ) -> Dict[str, Any]:
        raw_text = FileParser.extract_text(file_path)
        text = TextProcessor.preprocess_text(raw_text)
        chunks = TextProcessor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

        return {
            "text": text,
            "chunks": chunks,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "text_stats": TextProcessor.get_text_stats(text),
        }

    def generate_ontology(self, text: str, simulation_requirement: Optional[str] = None) -> Dict[str, Any]:
        requirement = simulation_requirement or (
            "针对技术类文章生成固定 schema 的知识抽取本体，用于比较不同图谱抽取后端的效果。"
        )
        return self.ontology_generator.generate([text], requirement)

    def generate_legacy_ontology(
        self,
        text: str,
        simulation_requirement: Optional[str] = None,
    ) -> Dict[str, Any]:
        requirement = simulation_requirement or "请根据文本设计适合社会媒体舆论模拟的实体类型和关系类型。"
        return self.legacy_social_generator.generate([text], requirement)

    def run_local(
        self,
        ontology: Dict[str, Any],
        chunks: List[str],
        graph_name: str,
    ) -> BenchmarkRunResult:
        start = time.perf_counter()
        graph_id = self.local_builder.create_graph(graph_name)
        self.local_builder.set_ontology(graph_id, ontology)
        self.local_builder.add_text_batches(graph_id, chunks)
        self.local_builder._run_async(self.local_builder.prune_invalid_edges_async(graph_id))
        graph_data = self.local_builder.get_graph_data(graph_id)
        duration = time.perf_counter() - start
        metrics = summarize_graph_data(graph_data, ontology)

        return BenchmarkRunResult(
            provider="local_graphiti",
            graph_id=graph_id,
            duration_seconds=round(duration, 3),
            chunk_count=len(chunks),
            profile="local_technical",
            settings={"ontology_profile": "technical", "backend": "graphiti"},
            metrics=metrics,
            preview=self._preview_graph_data(graph_data),
        )

    def run_zep(
        self,
        ontology: Dict[str, Any],
        chunks: List[str],
        graph_name: str,
        mode: str = "batch",
        wait_mode: str = "episodes_processed",
        batch_size: int = 3,
        poll_timeout: int = 300,
        poll_interval: int = 5,
        profile: Optional[str] = None,
        ontology_profile: str = "technical",
    ) -> BenchmarkRunResult:
        if not Config.ZEP_API_KEY:
            raise ValueError("ZEP_API_KEY 未配置，无法运行 Zep 对照测试")

        client = self.zep_client or Zep(api_key=Config.ZEP_API_KEY)
        graph_id = f"zepbench_{uuid.uuid4().hex[:16]}"
        start = time.perf_counter()

        client.graph.create(
            graph_id=graph_id,
            name=graph_name,
            description="MiroFish extraction benchmark control group",
        )

        entity_models, edge_models = build_zep_ontology_classes(ontology)
        client.graph.set_ontology(
            entities=entity_models,
            edges=edge_models,
            graph_ids=[graph_id],
        )
        episode_uuids = self._ingest_zep_chunks(
            client=client,
            graph_id=graph_id,
            graph_name=graph_name,
            chunks=chunks,
            mode=mode,
            batch_size=batch_size,
        )

        if wait_mode == "episodes_processed":
            self._wait_for_zep_episodes(
                client=client,
                episode_uuids=episode_uuids,
                timeout_seconds=poll_timeout,
                poll_interval_seconds=poll_interval,
            )
            graph_data = self._fetch_zep_graph_data(client=client, graph_id=graph_id)
        else:
            graph_data = self._wait_for_zep_graph(
                client=client,
                graph_id=graph_id,
                timeout_seconds=poll_timeout,
                poll_interval_seconds=poll_interval,
            )
        duration = time.perf_counter() - start
        metrics = summarize_graph_data(graph_data, ontology)

        return BenchmarkRunResult(
            provider="zep_control",
            graph_id=graph_id,
            duration_seconds=round(duration, 3),
            chunk_count=len(chunks),
            profile=profile or "zep_control",
            settings={
                "ontology_profile": ontology_profile,
                "backend": "zep",
                "mode": mode,
                "wait_mode": wait_mode,
                "batch_size": batch_size,
            },
            metrics=metrics,
            preview=self._preview_graph_data(graph_data),
        )

    def run_benchmark(
        self,
        file_path: str,
        simulation_requirement: Optional[str] = None,
        chunk_size: int = Config.DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = Config.DEFAULT_CHUNK_OVERLAP,
        zep_legacy_mode: str = "batch",
        zep_technical_mode: str = "batch",
    ) -> Dict[str, Any]:
        prepared = self.prepare_text(
            file_path=file_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        technical_ontology = self.generate_ontology(
            prepared["text"],
            simulation_requirement=simulation_requirement,
        )
        legacy_ontology = self.generate_legacy_ontology(prepared["text"])

        base_name = Path(file_path).stem[:40]
        try:
            zep_legacy_result = self.run_zep(
                ontology=legacy_ontology,
                chunks=prepared["chunks"],
                graph_name=f"{base_name}_legacy_zep",
                mode=zep_legacy_mode,
                wait_mode="episodes_processed",
                batch_size=3,
                profile="zep_legacy_baseline",
                ontology_profile="legacy_social",
            )
        except Exception as exc:
            logger.exception("Legacy Zep benchmark run failed")
            zep_legacy_result = self._failed_run(
                provider="zep_control",
                chunk_count=len(prepared["chunks"]),
                error=str(exc),
                profile="zep_legacy_baseline",
                settings={"ontology_profile": "legacy_social", "backend": "zep", "mode": zep_legacy_mode},
            )

        try:
            zep_technical_result = self.run_zep(
                ontology=technical_ontology,
                chunks=prepared["chunks"],
                graph_name=f"{base_name}_technical_zep",
                mode=zep_technical_mode,
                wait_mode="episodes_processed",
                batch_size=3,
                profile="zep_technical_control",
                ontology_profile="technical",
            )
        except Exception as exc:
            logger.exception("Technical Zep benchmark run failed")
            zep_technical_result = self._failed_run(
                provider="zep_control",
                chunk_count=len(prepared["chunks"]),
                error=str(exc),
                profile="zep_technical_control",
                settings={"ontology_profile": "technical", "backend": "zep", "mode": zep_technical_mode},
            )

        local_result = self.run_local(
            ontology=technical_ontology,
            chunks=prepared["chunks"],
            graph_name=f"{base_name}_local",
        )

        return {
            "run_at": datetime.now().isoformat(),
            "file_path": file_path,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "chunk_count": len(prepared["chunks"]),
            "text_stats": prepared["text_stats"],
            "ontologies": {
                "legacy_social": {
                    "entity_types": legacy_ontology.get("entity_types", []),
                    "edge_types": legacy_ontology.get("edge_types", []),
                    "analysis_summary": legacy_ontology.get("analysis_summary", ""),
                },
                "technical": {
                    "entity_types": technical_ontology.get("entity_types", []),
                    "edge_types": technical_ontology.get("edge_types", []),
                    "analysis_summary": technical_ontology.get("analysis_summary", ""),
                },
            },
            "runs": {
                "zep_legacy_baseline": zep_legacy_result.to_dict(),
                "zep_technical_control": zep_technical_result.to_dict(),
                "local_technical": local_result.to_dict(),
            },
            "comparisons": {
                "same_task_local_vs_zep_technical": compare_benchmark_runs(
                    local_result.metrics,
                    zep_technical_result.metrics,
                ),
                "zep_legacy_vs_zep_technical": compare_run_summaries(
                    zep_legacy_result,
                    zep_technical_result,
                ),
            },
            "notes": [
                "zep_legacy_baseline 用旧版社交模拟 ontology 复刻原始 MiroFish + Zep 路径。",
                "zep_technical_control 与 local_technical 共享同一套技术文章 ontology，可用于同任务质量对照。",
                "zep_legacy_vs_zep_technical 主要用于看 schema 切换对 Zep 的影响，不能直接当成同任务语义质量差值。",
            ],
        }

    def _failed_run(
        self,
        provider: str,
        chunk_count: int,
        error: str,
        profile: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkRunResult:
        return BenchmarkRunResult(
            provider=provider,
            graph_id=None,
            duration_seconds=0.0,
            chunk_count=chunk_count,
            profile=profile,
            settings=settings or {},
            metrics=None,
            preview={},
            status="failed",
            error=error,
        )

    def _ingest_zep_chunks(
        self,
        client: Zep,
        graph_id: str,
        graph_name: str,
        chunks: List[str],
        mode: str,
        batch_size: int,
    ) -> List[str]:
        from zep_cloud.types.episode_data import EpisodeData

        episode_uuids: List[str] = []
        base_time = datetime.utcnow()

        if mode == "batch":
            for start in range(0, len(chunks), batch_size):
                batch_chunks = chunks[start:start + batch_size]
                episodes = [
                    EpisodeData(
                        data=chunk,
                        type="text",
                    )
                    for chunk in batch_chunks
                ]
                batch_result = client.graph.add_batch(episodes=episodes, graph_id=graph_id)
                for episode in batch_result or []:
                    episode_uuid = getattr(episode, "uuid_", None) or getattr(episode, "uuid", None)
                    if episode_uuid:
                        episode_uuids.append(str(episode_uuid))
                time.sleep(1)
            return episode_uuids

        for index, chunk in enumerate(chunks):
            episode = client.graph.add(
                data=chunk,
                type="text",
                created_at=(base_time + timedelta(seconds=index)).isoformat(),
                graph_id=graph_id,
                source_description=f"benchmark:{graph_name}:chunk_{index + 1}",
            )
            episode_uuid = getattr(episode, "uuid_", None) or getattr(episode, "uuid", None)
            if episode_uuid:
                episode_uuids.append(str(episode_uuid))

        return episode_uuids

    def _wait_for_zep_episodes(
        self,
        client: Zep,
        episode_uuids: List[str],
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> None:
        if not episode_uuids:
            return

        deadline = time.time() + timeout_seconds
        pending = set(episode_uuids)

        while pending and time.time() < deadline:
            for episode_uuid in list(pending):
                try:
                    episode = client.graph.episode.get(uuid_=episode_uuid)
                except Exception:
                    continue

                if getattr(episode, "processed", False):
                    pending.remove(episode_uuid)

            if pending:
                time.sleep(poll_interval_seconds)

        if pending:
            logger.warning("Zep episode wait timeout: %s pending for graph ingestion", len(pending))

    def _wait_for_zep_graph(
        self,
        client: Zep,
        graph_id: str,
        timeout_seconds: int = 300,
        poll_interval_seconds: int = 5,
    ) -> Dict[str, Any]:
        last_counts = (-1, -1)
        stable_rounds = 0
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            nodes = fetch_all_nodes(client, graph_id)
            edges = fetch_all_edges(client, graph_id)
            counts = (len(nodes), len(edges))

            if counts == last_counts and counts != (0, 0):
                stable_rounds += 1
                if stable_rounds >= 2:
                    return self._normalize_zep_graph_data(nodes, edges)
            else:
                stable_rounds = 0
                last_counts = counts

            time.sleep(poll_interval_seconds)

        logger.warning("Zep graph polling timeout: graph_id=%s counts=%s", graph_id, last_counts)
        return self._fetch_zep_graph_data(client=client, graph_id=graph_id)

    def _fetch_zep_graph_data(self, client: Zep, graph_id: str) -> Dict[str, Any]:
        nodes = fetch_all_nodes(client, graph_id)
        edges = fetch_all_edges(client, graph_id)
        return self._normalize_zep_graph_data(nodes, edges)

    def _normalize_zep_graph_data(self, nodes: List[Any], edges: List[Any]) -> Dict[str, Any]:
        node_rows = []
        node_name_by_uuid: Dict[str, str] = {}

        for node in nodes:
            node_uuid = getattr(node, "uuid_", None) or getattr(node, "uuid", "")
            node_name = getattr(node, "name", "") or ""
            labels = list(getattr(node, "labels", []) or [])
            node_name_by_uuid[node_uuid] = node_name
            node_rows.append(
                {
                    "uuid": node_uuid,
                    "name": node_name,
                    "labels": [label for label in labels if label not in _DEFAULT_ENTITY_LABELS],
                    "summary": getattr(node, "summary", "") or "",
                    "attributes": getattr(node, "attributes", {}) or {},
                    "created_at": str(getattr(node, "created_at", "") or "") or None,
                }
            )

        edge_rows = []
        for edge in edges:
            source_uuid = getattr(edge, "source_node_uuid", "")
            target_uuid = getattr(edge, "target_node_uuid", "")
            edge_rows.append(
                {
                    "uuid": getattr(edge, "uuid_", None) or getattr(edge, "uuid", ""),
                    "name": getattr(edge, "name", "") or "",
                    "fact": getattr(edge, "fact", "") or "",
                    "fact_type": getattr(edge, "name", "") or "",
                    "source_node_uuid": source_uuid,
                    "target_node_uuid": target_uuid,
                    "source_node_name": node_name_by_uuid.get(source_uuid, ""),
                    "target_node_name": node_name_by_uuid.get(target_uuid, ""),
                    "attributes": getattr(edge, "attributes", {}) or {},
                    "created_at": str(getattr(edge, "created_at", "") or "") or None,
                    "valid_at": str(getattr(edge, "valid_at", "") or "") or None,
                    "invalid_at": str(getattr(edge, "invalid_at", "") or "") or None,
                    "expired_at": str(getattr(edge, "expired_at", "") or "") or None,
                    "episodes": [],
                }
            )

        return {
            "nodes": node_rows,
            "edges": edge_rows,
            "node_count": len(node_rows),
            "edge_count": len(edge_rows),
        }

    def _preview_graph_data(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        nodes = graph_data.get("nodes", []) or []
        edges = graph_data.get("edges", []) or []

        return {
            "node_samples": [
                {
                    "name": node.get("name", ""),
                    "labels": node.get("labels", []),
                }
                for node in nodes[:12]
            ],
            "edge_samples": [
                {
                    "name": edge.get("name", ""),
                    "source": edge.get("source_node_name", ""),
                    "target": edge.get("target_node_name", ""),
                    "fact": edge.get("fact", ""),
                }
                for edge in edges[:20]
            ],
        }


def write_benchmark_report(report: Dict[str, Any], output_path: Optional[str] = None) -> str:
    if output_path is None:
        benchmark_dir = Path(Config.UPLOAD_FOLDER) / "benchmarks"
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(benchmark_dir / f"extraction_benchmark_{timestamp}.json")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
