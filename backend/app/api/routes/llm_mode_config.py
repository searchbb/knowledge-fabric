"""
REST surface for the LLM 抽取模式开关 (local / online DeepSeek / bailian qwen3).

端点：
    GET  /api/config/llm-mode
         返回当前模式 + 各 provider 是否配置好 + 当前是否有 in-flight URL,
         用于前端按钮 disable 的条件判断。

    PUT  /api/config/llm-mode
         body: {"mode": "local"|"online"|"bailian"}
         - 如果有 in-flight URL, 直接 409 拒绝（GPT consult 2026-04-11:
           不热拔插 in-flight Graphiti client，避免把 OpenAI 连接池/Neo4j
           状态弄坏）
         - 如果切到 online/bailian 但对应 provider 的 API_KEY 未配置, 400 拒绝
         - 切换成功返回新 payload；下一次 /api/auto/process-pending 会在
           graph_builder._get_client() 里 snapshot 到新模式并自动重建
           Graphiti client
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ...config import Config
from ...services.auto.pending_store import PendingUrlStore
from ...services.llm_mode_service import (
    VALID_MODES,
    get_llm_mode,
    set_llm_mode,
)


llm_mode_config_bp = Blueprint(
    "llm_mode_config",
    __name__,
    url_prefix="/api/config",
)


def _payload_with_meta() -> dict:
    """合并当前模式 + 环境信息，便于前端一次渲染所需全部状态。"""
    mode_payload = get_llm_mode()
    store = PendingUrlStore()
    buckets = store.load()
    in_flight_count = len(buckets.get("in_flight", []) or [])

    return {
        "mode": mode_payload["mode"],
        "updated_at": mode_payload.get("updated_at"),
        "updated_by": mode_payload.get("updated_by"),
        "valid_modes": list(VALID_MODES),
        "in_flight_count": in_flight_count,
        "deepseek_configured": bool(Config.DEEPSEEK_API_KEY),
        "deepseek_model": Config.DEEPSEEK_MODEL_NAME,
        "deepseek_semaphore": Config.DEEPSEEK_SEMAPHORE_LIMIT,
        "deepseek_base_url": Config.DEEPSEEK_BASE_URL,
        "bailian_configured": bool(Config.BAILIAN_API_KEY),
        "bailian_model": Config.BAILIAN_MODEL_NAME,
        "bailian_semaphore": Config.BAILIAN_SEMAPHORE_LIMIT,
        "bailian_base_url": Config.BAILIAN_BASE_URL,
        "local_model": Config.GRAPHITI_LLM_MODEL_NAME,
        "local_base_url": Config.GRAPHITI_LLM_BASE_URL,
        "local_semaphore": Config.GRAPHITI_SEMAPHORE_LIMIT,
    }


@llm_mode_config_bp.route("/llm-mode", methods=["GET"])
def get_mode():
    """返回当前模式 + 环境信息。"""
    return jsonify({"success": True, "data": _payload_with_meta()})


@llm_mode_config_bp.route("/llm-mode", methods=["PUT"])
def put_mode():
    """
    切换抽取模式。

    拒绝条件：
    - in_flight > 0                → 409
    - mode 非法                    → 400
    - mode=online 但 DEEPSEEK 缺失  → 400
    """
    body = request.get_json(silent=True) or {}
    new_mode = str(body.get("mode", "")).strip().lower()

    if new_mode not in VALID_MODES:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"invalid mode {new_mode!r}; expected one of {list(VALID_MODES)}",
                    "error_code": "INVALID_MODE",
                }
            ),
            400,
        )

    store = PendingUrlStore()
    buckets = store.load()
    in_flight = buckets.get("in_flight", []) or []
    if in_flight:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        f"有 {len(in_flight)} 个任务正在执行，"
                        "暂时不能切换抽取模式；请等当前任务完成后再切换"
                    ),
                    "error_code": "IN_FLIGHT",
                    "in_flight_count": len(in_flight),
                    "current_mode": get_llm_mode()["mode"],
                }
            ),
            409,
        )

    try:
        set_llm_mode(new_mode, updated_by="api")
    except ValueError as exc:
        msg = str(exc).lower()
        if "deepseek" in msg:
            error_code = "DEEPSEEK_NOT_CONFIGURED"
        elif "bailian" in msg:
            error_code = "BAILIAN_NOT_CONFIGURED"
        else:
            error_code = "INVALID_MODE"
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": error_code,
                }
            ),
            400,
        )

    return jsonify({"success": True, "data": _payload_with_meta()})
