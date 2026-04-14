"""
Zep 图谱构建服务

用于当前主链的文章抽取执行：
- 在 Zep 创建图谱
- 设置当前 ontology
- 分批写入文本 chunks
- 等待 Zep 处理完成
- 读取 nodes / edges 供前端展示
"""

from __future__ import annotations

import time
import uuid
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from pydantic import Field
from zep_cloud import EpisodeData, EntityEdgeSourceTarget
from zep_cloud.client import Zep
from zep_cloud.external_clients.ontology import EdgeModel, EntityModel, EntityText

from ..config import Config
from ..utils.logger import get_logger
from ..utils.upstream_errors import UpstreamErrorKind, classify_upstream_error
from ..utils.zep_paging import fetch_all_edges, fetch_all_nodes

logger = get_logger("mirofish.zep_graph_builder")


@dataclass
class GraphInfo:
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


@dataclass(frozen=True)
class EpisodeHandle:
    uuid: str
    task_id: Optional[str] = None


class ZepGraphBuilderService:
    """当前主链使用的 Zep 图谱构建器。"""

    RESERVED_NAMES = {"uuid", "name", "group_id", "name_embedding", "summary", "created_at"}

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY 未配置")
        self.client = Zep(api_key=self.api_key)
        self._reset_build_stats(0)

    def _reset_build_stats(self, total_chunks: int) -> None:
        self._build_stats = {
            "chunk_count": max(int(total_chunks or 0), 0),
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
            "fallback_graph_applied": False,
            "fallback_graph_mode": "",
            "fallback_graph_node_count": 0,
            "fallback_graph_edge_count": 0,
            "json_parse_repair_count": 0,
            "json_parse_retry_count": 0,
            "json_parse_failure_count": 0,
        }

    def _ensure_build_stats(self) -> Dict[str, Any]:
        stats = getattr(self, "_build_stats", None)
        if not isinstance(stats, dict):
            self._reset_build_stats(0)
            stats = self._build_stats
        return stats

    def get_build_diagnostics(self) -> Dict[str, Any]:
        return dict(self._ensure_build_stats())

    def create_graph(self, name: str) -> str:
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self.client.graph.create(
            graph_id=graph_id,
            name=name,
            description="Knowledge Fabric Technical Article Graph",
        )
        logger.info("创建 Zep 图谱: graph_id=%s, name=%s", graph_id, name)
        return graph_id

    # Zep Cloud limits: max 10 entity types, max 10 edge types
    ZEP_MAX_ENTITY_TYPES = 10
    ZEP_MAX_EDGE_TYPES = 10

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """
        将当前 ontology 转成 Zep 可接受的动态模型定义。

        这里保留当前技术文章 schema，只是执行引擎切回 Zep。
        Zep Cloud 限制最多 10 种实体类型和 10 种边类型，超出部分自动截断。
        """
        warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

        entity_types: Dict[str, type[EntityModel]] = {}
        edge_definitions: Dict[str, Any] = {}

        raw_entity_defs = ontology.get("entity_types", [])
        if len(raw_entity_defs) > self.ZEP_MAX_ENTITY_TYPES:
            logger.warning(
                "Ontology has %d entity types, trimming to %d for Zep",
                len(raw_entity_defs), self.ZEP_MAX_ENTITY_TYPES,
            )
            raw_entity_defs = raw_entity_defs[:self.ZEP_MAX_ENTITY_TYPES]

        for entity_def in raw_entity_defs:
            name = entity_def["name"]
            description = entity_def.get("description", f"A {name} entity.")

            attrs: Dict[str, Any] = {"__doc__": description}
            annotations: Dict[str, Any] = {}
            for attr_def in entity_def.get("attributes", []):
                attr_name = self._safe_attr_name(attr_def["name"])
                attr_desc = attr_def.get("description", attr_name)
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[EntityText]

            attrs["__annotations__"] = annotations
            entity_class = type(name, (EntityModel,), attrs)
            entity_class.__doc__ = description
            entity_types[name] = entity_class

        raw_edge_defs = ontology.get("edge_types", [])
        if len(raw_edge_defs) > self.ZEP_MAX_EDGE_TYPES:
            logger.warning(
                "Ontology has %d edge types, trimming to %d for Zep",
                len(raw_edge_defs), self.ZEP_MAX_EDGE_TYPES,
            )
            raw_edge_defs = raw_edge_defs[:self.ZEP_MAX_EDGE_TYPES]

        for edge_def in raw_edge_defs:
            name = edge_def["name"]
            description = edge_def.get("description", f"A {name} relationship.")

            attrs: Dict[str, Any] = {"__doc__": description}
            annotations: Dict[str, Any] = {}
            for attr_def in edge_def.get("attributes", []):
                attr_name = self._safe_attr_name(attr_def["name"], prefix="edge_")
                attr_desc = attr_def.get("description", attr_name)
                attrs[attr_name] = Field(description=attr_desc, default=None)
                annotations[attr_name] = Optional[str]

            attrs["__annotations__"] = annotations
            class_name = "".join(word.capitalize() for word in name.split("_"))
            edge_class = type(class_name, (EdgeModel,), attrs)
            edge_class.__doc__ = description

            source_targets = [
                EntityEdgeSourceTarget(
                    source=source_target.get("source", "Entity"),
                    target=source_target.get("target", "Entity"),
                )
                for source_target in edge_def.get("source_targets", [])
            ]
            if source_targets:
                edge_definitions[name] = (edge_class, source_targets)

        if entity_types or edge_definitions:
            self.client.graph.set_ontology(
                graph_ids=[graph_id],
                entities=entity_types if entity_types else None,
                edges=edge_definitions if edge_definitions else None,
            )
        logger.info(
            "设置 Zep 本体完成: graph_id=%s, entity_types=%s, edge_types=%s",
            graph_id,
            len(entity_types),
            len(edge_definitions),
        )

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> List[EpisodeHandle]:
        """
        复刻旧版稳定写入方式：
        - 使用 add_batch
        - EpisodeData 只传最小 payload: data + type
        """
        episode_handles: List[EpisodeHandle] = []
        total_chunks = len(chunks)
        self._reset_build_stats(total_chunks)

        for start in range(0, total_chunks, batch_size):
            batch_chunks = chunks[start:start + batch_size]
            batch_num = start // batch_size + 1
            total_batches = (total_chunks + batch_size - 1) // batch_size

            if progress_callback:
                progress_callback(
                    f"发送第 {batch_num}/{total_batches} 批数据 ({len(batch_chunks)} 块)...",
                    (start + len(batch_chunks)) / total_chunks if total_chunks else 1.0,
                )

            episodes = [EpisodeData(data=chunk, type="text") for chunk in batch_chunks]
            try:
                batch_result = self.client.graph.add_batch(graph_id=graph_id, episodes=episodes)
            except Exception as exc:
                stats = self._ensure_build_stats()
                error_kind = classify_upstream_error(exc)
                stats["soft_failed_chunk_count"] += len(batch_chunks)
                stats["soft_failed_chunks"].append(
                    {
                        "batch_index": batch_num,
                        "chunk_start_index": start + 1,
                        "chunk_end_index": start + len(batch_chunks),
                        "error_kind": error_kind.value,
                        "reason": str(exc)[:300],
                    }
                )
                if error_kind == UpstreamErrorKind.RATE_LIMIT:
                    stats["rate_limit_hit_count"] += 1
                    stats["aborted_due_to_rate_limit"] = True
                    stats["aborted_chunk_index"] = start + 1
                    stats["abort_reason"] = (
                        f"batch_{batch_num} reached upstream rate limit while adding chunks"
                    )
                raise

            if batch_result and isinstance(batch_result, list):
                for episode in batch_result:
                    episode_uuid = getattr(episode, "uuid_", None) or getattr(episode, "uuid", None)
                    if episode_uuid:
                        episode_handles.append(
                            EpisodeHandle(
                                uuid=str(episode_uuid),
                                task_id=str(getattr(episode, "task_id", "") or "") or None,
                            )
                        )

            stats = self._ensure_build_stats()
            stats["processed_chunk_count"] += len(batch_chunks)
            stats["episode_count"] = len(episode_handles)

            time.sleep(1)

        return episode_handles

    def _wait_for_episodes(
        self,
        episode_uuids: List[EpisodeHandle],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        timeout: int = 600,
    ):
        handles = self._normalize_episode_handles(episode_uuids)

        if not handles:
            if progress_callback:
                progress_callback("无需等待（没有 episode）", 1.0)
            return

        start_time = time.time()
        pending_episodes = {handle.uuid: handle for handle in handles}
        total_episodes = len(handles)
        completed_count = 0
        failed_count = 0
        failed_items: List[str] = []

        if progress_callback:
            progress_callback(f"开始等待 {total_episodes} 个文本块处理...", 0.0)

        while pending_episodes:
            if time.time() - start_time > timeout:
                if progress_callback:
                    progress_callback(
                        f"部分文本块超时，已完成 {completed_count}/{total_episodes}",
                        completed_count / total_episodes if total_episodes else 1.0,
                    )
                break

            for episode_uuid, handle in list(pending_episodes.items()):
                task_status = self._get_task_status(handle.task_id)
                if task_status in {"succeeded", "completed", "success"}:
                    pending_episodes.pop(episode_uuid, None)
                    completed_count += 1
                    continue
                if task_status in {"failed", "error", "cancelled", "canceled"}:
                    pending_episodes.pop(episode_uuid, None)
                    failed_count += 1
                    failed_items.append(f"{episode_uuid}:{task_status}")
                    continue

                try:
                    episode = self.client.graph.episode.get(uuid_=episode_uuid)
                except Exception:
                    continue

                if not handle.task_id:
                    refreshed_task_id = getattr(episode, "task_id", None)
                    if refreshed_task_id:
                        pending_episodes[episode_uuid] = EpisodeHandle(
                            uuid=handle.uuid,
                            task_id=str(refreshed_task_id),
                        )

                if getattr(episode, "processed", False):
                    pending_episodes.pop(episode_uuid, None)
                    completed_count += 1

            if progress_callback:
                elapsed = int(time.time() - start_time)
                status_bits = [f"{completed_count}/{total_episodes} 完成", f"{len(pending_episodes)} 待处理"]
                if failed_count:
                    status_bits.append(f"{failed_count} 失败")
                progress_callback(
                    f"Zep处理中... {', '.join(status_bits)} ({elapsed}秒)",
                    completed_count / total_episodes if total_episodes else 1.0,
                )

            if pending_episodes:
                time.sleep(3)

        if failed_items:
            stats = self._ensure_build_stats()
            stats["soft_failed_chunk_count"] += failed_count
            stats["soft_failed_chunks"].extend(
                {
                    "episode_uuid": item.split(":", 1)[0],
                    "error_kind": "fatal",
                    "reason": item.split(":", 1)[1] if ":" in item else item,
                }
                for item in failed_items
            )
            raise RuntimeError(
                "Zep 有文本块处理失败: " + ", ".join(failed_items[:5])
            )

        if progress_callback:
            progress_callback(f"处理完成: {completed_count}/{total_episodes}", 1.0)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        node_map: Dict[str, str] = {}
        nodes_data = []
        for node in nodes:
            node_uuid = getattr(node, "uuid_", None) or getattr(node, "uuid", "")
            node_name = getattr(node, "name", "") or ""
            node_map[node_uuid] = node_name

            created_at = getattr(node, "created_at", None)
            nodes_data.append({
                "uuid": node_uuid,
                "name": node_name,
                "labels": getattr(node, "labels", []) or [],
                "summary": getattr(node, "summary", "") or "",
                "attributes": getattr(node, "attributes", {}) or {},
                "created_at": str(created_at) if created_at else None,
            })

        edges_data = []
        for edge in edges:
            created_at = getattr(edge, "created_at", None)
            valid_at = getattr(edge, "valid_at", None)
            invalid_at = getattr(edge, "invalid_at", None)
            expired_at = getattr(edge, "expired_at", None)
            episodes = getattr(edge, "episodes", None) or getattr(edge, "episode_ids", None)
            if episodes and not isinstance(episodes, list):
                episodes = [str(episodes)]
            elif episodes:
                episodes = [str(item) for item in episodes]

            edges_data.append({
                "uuid": getattr(edge, "uuid_", None) or getattr(edge, "uuid", ""),
                "name": getattr(edge, "name", "") or "",
                "fact": getattr(edge, "fact", "") or "",
                "fact_type": getattr(edge, "fact_type", None) or getattr(edge, "name", "") or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": node_map.get(edge.source_node_uuid, ""),
                "target_node_name": node_map.get(edge.target_node_uuid, ""),
                "attributes": getattr(edge, "attributes", {}) or {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": episodes or [],
            })

        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }

    def delete_graph(self, graph_id: str):
        self.client.graph.delete(graph_id=graph_id)

    def _safe_attr_name(self, attr_name: str, prefix: str = "entity_") -> str:
        if attr_name.lower() in self.RESERVED_NAMES:
            return f"{prefix}{attr_name}"
        return attr_name

    def _normalize_episode_handles(self, episode_uuids: List[Any]) -> List[EpisodeHandle]:
        handles: List[EpisodeHandle] = []
        for item in episode_uuids or []:
            if isinstance(item, EpisodeHandle):
                handles.append(item)
                continue
            if isinstance(item, str):
                handles.append(EpisodeHandle(uuid=item))
                continue
            if isinstance(item, dict):
                episode_uuid = item.get("uuid") or item.get("episode_uuid")
                if episode_uuid:
                    handles.append(
                        EpisodeHandle(
                            uuid=str(episode_uuid),
                            task_id=str(item.get("task_id")) if item.get("task_id") else None,
                        )
                    )
                continue

            episode_uuid = getattr(item, "uuid_", None) or getattr(item, "uuid", None)
            if episode_uuid:
                handles.append(
                    EpisodeHandle(
                        uuid=str(episode_uuid),
                        task_id=str(getattr(item, "task_id", "") or "") or None,
                    )
                )
        return handles

    def _get_task_status(self, task_id: Optional[str]) -> Optional[str]:
        if not task_id:
            return None
        try:
            task = self.client.task.get(task_id=task_id)
        except Exception:
            return None
        status = getattr(task, "status", None)
        if not status:
            return None
        return str(status).lower()
