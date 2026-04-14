"""Explicit graph access helpers for the current local-first product stage."""

from __future__ import annotations

from typing import Any

from ..config import Config
from .graph_builder import GraphBuilderService as LocalGraphBuilderService
from .zep_graph_builder import ZepGraphBuilderService

GRAPH_BACKEND_LOCAL = "local"
GRAPH_BACKEND_LEGACY_ZEP = "legacy_zep"
SUPPORTED_GRAPH_BACKENDS = {GRAPH_BACKEND_LOCAL, GRAPH_BACKEND_LEGACY_ZEP}


def empty_graph_data(graph_id: str | None = None) -> dict[str, Any]:
    return {
        "graph_id": graph_id,
        "nodes": [],
        "edges": [],
        "node_count": 0,
        "edge_count": 0,
    }


def normalize_graph_backend(value: str | None) -> str:
    normalized = str(value or GRAPH_BACKEND_LOCAL).strip().lower()
    if normalized not in SUPPORTED_GRAPH_BACKENDS:
        supported = ", ".join(sorted(SUPPORTED_GRAPH_BACKENDS))
        raise ValueError(f"不支持的图谱后端: {value}，可选值: {supported}")
    return normalized


def load_graph_data_by_backend(graph_id: str | None, *, backend: str = GRAPH_BACKEND_LOCAL) -> dict[str, Any]:
    if not graph_id:
        return empty_graph_data(graph_id)

    selected = normalize_graph_backend(backend)
    if selected == GRAPH_BACKEND_LOCAL:
        return LocalGraphBuilderService().get_graph_data(graph_id)

    return ZepGraphBuilderService(api_key=Config.ZEP_API_KEY).get_graph_data(graph_id)


def delete_graph_by_backend(graph_id: str, *, backend: str = GRAPH_BACKEND_LOCAL) -> None:
    selected = normalize_graph_backend(backend)
    if selected == GRAPH_BACKEND_LOCAL:
        LocalGraphBuilderService().delete_graph(graph_id)
        return

    ZepGraphBuilderService(api_key=Config.ZEP_API_KEY).delete_graph(graph_id)
