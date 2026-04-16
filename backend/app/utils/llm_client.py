"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from openai import OpenAI
from pydantic import BaseModel

from ..config import Config
from .upstream_errors import (
    classify_upstream_error,
    compute_retry_delay,
    is_retryable_upstream_error,
)


def is_local_openai_compatible_base_url(base_url: Optional[str]) -> bool:
    """Detect common local OpenAI-compatible endpoints such as LM Studio/Ollama/vLLM."""
    if not base_url:
        return False

    try:
        parsed = urlparse(base_url)
    except Exception:
        return False

    host = (parsed.hostname or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "0.0.0.0"}


def build_structured_json_response_format(
    base_url: Optional[str],
    response_model: Optional[type[BaseModel]] = None,
    *,
    schema_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Pick a structured output mode compatible with the configured endpoint."""
    mode = (getattr(Config, "LLM_RESPONSE_FORMAT_MODE", "auto") or "auto").strip().lower()

    if mode == "json_object":
        return {"type": "json_object"}
    if mode == "text":
        return {"type": "text"}

    use_json_schema = mode == "json_schema" or (
        mode == "auto" and is_local_openai_compatible_base_url(base_url)
    )
    if not use_json_schema:
        return {"type": "json_object"}

    if response_model is not None:
        schema_name = schema_name or getattr(response_model, "__name__", "structured_response")
        schema = response_model.model_json_schema()
    else:
        schema_name = schema_name or "json_response"
        schema = {
            "type": "object",
            "additionalProperties": True,
        }

    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "schema": schema,
        },
    }


class LLMClient:
    """LLM客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        # NOTE (2026-04-16): Earlier this constructor auto-routed bare LLMClient()
        # calls through llm_mode_service so every utility (ontology gen, theme
        # proposer, quality_gate.backfill_summaries, reading-structure
        # extraction) followed the auto-pipeline mode switch. That overshot the
        # user's intent: 百炼 was approved as the *graph extraction* provider
        # (Graphiti chunks), but Bailian's tail latency on the many-small
        # backfill summary calls is ~10-50x worse than DeepSeek (one 50-node
        # backfill batch took 16 min vs 21s on DeepSeek), which blew past the
        # pipeline stall watchdog. We keep the explicit routing only where the
        # user opted in (graph_builder uses get_graphiti_llm_params; the cross-
        # concept discoverer's _llm_judge passes params explicitly). Everyone
        # else stays on the static LLM_* env config.
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.timeout_seconds = Config.LLM_TIMEOUT_SECONDS

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.max_retries = 2
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self.timeout_seconds,
        }
        
        if response_format:
            normalized_response_format = response_format
            if response_format.get("type") == "json_object":
                normalized_response_format = build_structured_json_response_format(self.base_url)
            kwargs["response_format"] = normalized_response_format
        
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                return content
            except Exception as exc:
                last_error = exc
                error_kind = classify_upstream_error(exc)
                if attempt >= self.max_retries or not is_retryable_upstream_error(error_kind):
                    raise

                import time

                time.sleep(compute_retry_delay(attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM chat unexpectedly exited without a response")
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=build_structured_json_response_format(self.base_url)
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            # 尝试修复被 max_tokens 截断的 JSON（补闭合括号）
            repaired = _try_repair_truncated_json(cleaned_response)
            if repaired is not None:
                return repaired
            # 尝试用 json_repair 库（如果已安装）
            try:
                import json_repair
                result = json_repair.repair_json(cleaned_response, return_objects=True)
                if isinstance(result, dict):
                    return result
            except ImportError:
                pass
            except Exception:
                pass
            raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}")


def _try_repair_truncated_json(text: str) -> Optional[Dict[str, Any]]:
    """
    尝试修复被 max_tokens 截断的 JSON。
    策略：从末尾开始，逐步截掉不完整的部分，然后补上缺少的闭合括号。
    """
    if not text or text[0] != '{':
        return None

    # 去掉末尾不完整的 value（被截断的字符串/数字等）
    # 找到最后一个完整的 key-value 结束位置
    candidates = [text]
    # 尝试截到最后一个逗号、最后一个 }、最后一个 ]
    for ch in (',', '}', ']'):
        idx = text.rfind(ch)
        if idx > 0:
            candidates.append(text[:idx + 1])
            # 逗号后面补闭合
            if ch == ',':
                candidates.append(text[:idx])

    for candidate in candidates:
        # 数一下缺多少闭合括号
        open_braces = candidate.count('{') - candidate.count('}')
        open_brackets = candidate.count('[') - candidate.count(']')
        if open_braces < 0 or open_brackets < 0:
            continue
        patched = candidate + ']' * open_brackets + '}' * open_braces
        try:
            result = json.loads(patched)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue
    return None
