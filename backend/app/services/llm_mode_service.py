"""
抽取模式开关服务 (local vs online DeepSeek)

设计要点 (GPT consult 2026-04-11):
1. 状态持久化在 backend/data/llm_mode.json，跨进程重启保留
2. 运行时可通过 GET/PUT /api/config/llm-mode 切换
3. 不支持热拔插：如果 _client 已经缓存并且有任务在跑，切换会被拒绝 (409)
4. get_graphiti_llm_params() 返回一个"快照 dict"，调用方拿到后立即用，不持有指针
5. 零 fallback：无效 mode 直接报错；DEEPSEEK_API_KEY 缺失直接报错，不假装降级

此服务只负责"参数快照"。真正的 LLM Client 构造、Graphiti 初始化、连接管理
仍然在 graph_builder.py::_get_client() 中完成。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict

from ..config import Config

logger = logging.getLogger('mirofish.llm_mode')

# 配置文件位置。与 pending-urls.json 放在同一个 backend/data/ 目录下。
_MODE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '..',
    'data',
    'llm_mode.json',
)
_MODE_FILE = os.path.abspath(_MODE_FILE)

# 合法的模式值。
VALID_MODES = ('local', 'online')

# 写入是全局串行的；读是无锁的（文件小、原子读取足够）。
_write_lock = threading.Lock()


def _ensure_dir() -> None:
    parent = os.path.dirname(_MODE_FILE)
    os.makedirs(parent, exist_ok=True)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _default_payload() -> Dict[str, Any]:
    return {
        'mode': Config.LLM_MODE_DEFAULT if Config.LLM_MODE_DEFAULT in VALID_MODES else 'local',
        'updated_at': _now_iso(),
        'updated_by': 'default',
    }


def get_llm_mode() -> Dict[str, Any]:
    """
    读取当前模式。如果文件不存在，用 Config.LLM_MODE_DEFAULT 初始化并写回。
    返回的 dict 至少包含 {mode, updated_at}。
    """
    if not os.path.exists(_MODE_FILE):
        payload = _default_payload()
        _write_locked(payload)
        return payload

    try:
        with open(_MODE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning('llm_mode.json 读失败，回退到默认 %s: %s', Config.LLM_MODE_DEFAULT, exc)
        payload = _default_payload()
        _write_locked(payload)
        return payload

    mode = str(data.get('mode', '')).strip().lower()
    if mode not in VALID_MODES:
        logger.warning('llm_mode.json 里的 mode=%r 非法，回退到默认 %s', mode, Config.LLM_MODE_DEFAULT)
        payload = _default_payload()
        _write_locked(payload)
        return payload

    data['mode'] = mode
    return data


def set_llm_mode(new_mode: str, *, updated_by: str = 'api') -> Dict[str, Any]:
    """
    写入新模式。非法值直接 raise ValueError，不做静默 fallback。
    返回新 payload。
    """
    normalized = str(new_mode or '').strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError(f'invalid mode {new_mode!r}; expected one of {VALID_MODES}')

    # 在线模式下要求 DeepSeek Key 必须配置好，否则直接拒绝——
    # 零 fallback：不允许切到一个"切完了跑不通"的模式。
    if normalized == 'online' and not Config.DEEPSEEK_API_KEY:
        raise ValueError(
            'DEEPSEEK_API_KEY 未配置；请先在 .env 写入 DEEPSEEK_API_KEY=sk-xxx 再切换到 online'
        )

    payload = {
        'mode': normalized,
        'updated_at': _now_iso(),
        'updated_by': updated_by,
    }
    _write_locked(payload)
    logger.info('LLM mode 已切换 → %s (updated_by=%s)', normalized, updated_by)
    return payload


def _write_locked(payload: Dict[str, Any]) -> None:
    with _write_lock:
        _ensure_dir()
        tmp_path = _MODE_FILE + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _MODE_FILE)


def get_graphiti_llm_params() -> Dict[str, Any]:
    """
    返回"启动一次 Graphiti bulk extraction 所需的全部参数"快照。

    graph_builder._get_client() 应该在任务启动时调用一次此函数，拿到的结果
    直接用来构造 MiniMaxLLMClient + 设置 SEMAPHORE_LIMIT。不要保留对此 dict
    的持有，每次 _get_client 重新取，这样前后两次 build 可以吃到不同的模式。

    返回字段：
        - mode: 'local' | 'online'
        - provider: 'qwen3_local' | 'deepseek'
        - api_key: str
        - base_url: str
        - model: str
        - semaphore_limit: int
        - batch_size: int
        - temperature: float | None  (None 表示用 graphiti 默认，provider 内部会有 tuned 默认)
        - max_tokens: int | None
        - use_qwen3_no_think: bool
    """
    mode_payload = get_llm_mode()
    mode = mode_payload['mode']

    if mode == 'online':
        if not Config.DEEPSEEK_API_KEY:
            # 不做 fallback：强烈要求 .env 里配好 DEEPSEEK_API_KEY。
            raise RuntimeError(
                'LLM mode=online 但 DEEPSEEK_API_KEY 未配置；请先在 .env 写入 key 再切换，'
                '或改回 local 模式。'
            )
        return {
            'mode': 'online',
            'provider': 'deepseek',
            'api_key': Config.DEEPSEEK_API_KEY,
            'base_url': Config.DEEPSEEK_BASE_URL,
            'model': Config.DEEPSEEK_MODEL_NAME,
            'semaphore_limit': Config.DEEPSEEK_SEMAPHORE_LIMIT,
            'batch_size': Config.DEEPSEEK_BATCH_SIZE,
            # GPT consult 2026-04-11:
            #   DeepSeek JSON 模式偶发返回空 content，要求 prompt 里出现 'json';
            #   Graphiti 已经在 system prompt 里写了 'Respond with JSON'，
            #   所以这里温度尽量低、但不要到 0（有极小概率触发 deepseek-chat
            #   的 determinism corner case）。
            'temperature': 0.1,
            'max_tokens': 4096,
            'use_qwen3_no_think': False,
        }

    # local 默认：保留原先的 qwen3_local 路径，不做任何行为变化。
    return {
        'mode': 'local',
        'provider': 'qwen3_local',
        'api_key': Config.GRAPHITI_LLM_API_KEY or 'lm-studio',
        'base_url': Config.GRAPHITI_LLM_BASE_URL,
        'model': Config.GRAPHITI_LLM_MODEL_NAME,
        'semaphore_limit': Config.GRAPHITI_SEMAPHORE_LIMIT,
        'batch_size': Config.GRAPHITI_BATCH_SIZE,
        'temperature': None,   # graph_builder 有 QWEN3_EXTRACT_TEMPERATURE
        'max_tokens': None,    # graph_builder 有 QWEN3_EXTRACT_MAX_TOKENS
        'use_qwen3_no_think': True,
    }


def get_mode_file_path() -> str:
    """暴露给测试 / 诊断接口的文件路径。"""
    return _MODE_FILE
