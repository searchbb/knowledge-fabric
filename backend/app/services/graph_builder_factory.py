"""
图谱构建器选择器

只负责为第一阶段返回当前使用的构建器实现，并校验最小配置。
不要在这里引入更重的抽象。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..config import Config
from .graph_builder import GraphBuilderService
from .zep_graph_builder import ZepGraphBuilderService

SUPPORTED_GRAPH_BUILDERS = {"local", "zep"}
DEFAULT_GRAPH_BUILDER_PROVIDER = "local"


def get_graph_builder_provider(provider: Optional[str] = None) -> str:
    """返回当前启用的 builder provider。"""
    selected = (
        provider
        or os.environ.get("GRAPH_BUILDER_PROVIDER")
        or DEFAULT_GRAPH_BUILDER_PROVIDER
    )
    normalized = str(selected).strip().lower()
    if normalized not in SUPPORTED_GRAPH_BUILDERS:
        supported = ", ".join(sorted(SUPPORTED_GRAPH_BUILDERS))
        raise ValueError(f"不支持的 GRAPH_BUILDER_PROVIDER: {selected}，可选值: {supported}")
    return normalized


def validate_graph_builder_config(provider: Optional[str] = None) -> List[str]:
    """按 provider 校验最小必需配置。"""
    try:
        selected = get_graph_builder_provider(provider)
    except ValueError as exc:
        return [str(exc)]

    errors: List[str] = []
    if selected == "zep" and not Config.ZEP_API_KEY:
        errors.append("ZEP_API_KEY未配置")
    return errors


def get_graph_builder(provider: Optional[str] = None):
    """返回当前启用的图谱构建器实例。"""
    selected = get_graph_builder_provider(provider)
    if selected == "local":
        return GraphBuilderService()
    return ZepGraphBuilderService(api_key=Config.ZEP_API_KEY)
