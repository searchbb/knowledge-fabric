"""
图谱构建服务
使用 Graphiti + Neo4j 本地构建知识图谱（替代 Zep Cloud）
"""

import os
import re
import json
import uuid
import asyncio
import math
import typing
import logging
import difflib
from collections import Counter
from datetime import datetime
from types import UnionType
from typing import Dict, Any, List, Optional, Callable
from typing import get_args, get_origin
from dataclasses import dataclass

from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.bulk_utils import RawEpisode
import graphiti_core.helpers as _graphiti_helpers
from graphiti_core.llm_client.config import LLMConfig, DEFAULT_MAX_TOKENS, ModelSize
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.prompts.models import Message
from pydantic import BaseModel
from json_repair import repair_json

from ..config import Config
from ..models.task import TaskManager
from ..utils.file_parser import split_text_into_chunks
from ..utils.llm_client import build_structured_json_response_format
from ..utils.upstream_errors import (
    UpstreamErrorKind,
    classify_upstream_error,
    compute_retry_delay,
    is_adaptive_split_candidate,
    is_retryable_upstream_error,
)

logger = logging.getLogger('mirofish.graph_builder')

PHASE1_SCHEMA_SAFE_PROPERTIES = {"id", "uuid", "group_id"}
PHASE1_SCHEMA_RISK_PROPERTIES = {"name", "source_url"}
PHASE1_MAX_CHUNK_RETRIES = 2
PHASE1_BULK_CALL_TIMEOUT_SECONDS = int(os.environ.get("PHASE1_BULK_CALL_TIMEOUT_SECONDS", "60"))
PHASE1_SINGLE_CALL_TIMEOUT_SECONDS = int(
    os.environ.get("PHASE1_SINGLE_CALL_TIMEOUT_SECONDS", str(PHASE1_BULK_CALL_TIMEOUT_SECONDS))
)
PHASE1_MAX_TIMEOUT_SPLIT_DEPTH = int(os.environ.get("PHASE1_MAX_TIMEOUT_SPLIT_DEPTH", "2"))
PHASE1_TIMEOUT_SPLIT_MAX_CHUNK_SIZE = int(os.environ.get("PHASE1_TIMEOUT_SPLIT_MAX_CHUNK_SIZE", "520"))
PHASE1_TIMEOUT_SPLIT_MAX_OVERLAP = int(os.environ.get("PHASE1_TIMEOUT_SPLIT_MAX_OVERLAP", "80"))
PHASE1_TIMEOUT_SPLIT_MIN_CHUNK_SIZE = int(os.environ.get("PHASE1_TIMEOUT_SPLIT_MIN_CHUNK_SIZE", "220"))

# ============== qwen3-30b-a3b-2507 tuning (GPT consult 2026-04-11) ==============
#
# graphiti-core's LLMConfig defaults are temperature=1.0 + max_tokens=16384,
# which are wildly wrong for JSON-schema-constrained extraction on a local
# reasoning model. Two real-world WeChat long-form Chinese articles reliably
# stalled batch 2 of 3 at "正在处理批次 2/3" until the 240s no-progress
# watchdog fired. Root cause per GPT: Qwen3 reasoning-first generation +
# response_format json_object entered a "think forever, never emit valid
# JSON" spiral, made worse by temperature=1.0 randomness and a 16k token
# ceiling giving reasoning unlimited room to wander.
#
# These constants tighten the screws at the LLM call site:
# - QWEN3_EXTRACT_TEMPERATURE  : 0.1 — near-deterministic, still allows the
#                                minimal sampling graphiti's JSON schema
#                                negotiation needs.
# - QWEN3_EXTRACT_MAX_TOKENS   : 4096 — enough for a rich JSON output on a
#                                1800-char chunk, but capped so a runaway
#                                reasoning loop can't eat 10+ minutes.
# - QWEN3_NO_THINK_MARKER      : "/no_think" — Qwen3 chat template hard
#                                switch that disables the <think> block. We
#                                prepend it to the system prompt AND set
#                                extra_body={"chat_template_kwargs":
#                                {"enable_thinking": False}} as belt-and-
#                                suspenders so both LM Studio <=0.3.15
#                                (template-based) and >=0.3.16 (extra_body-
#                                aware) do the right thing.
QWEN3_EXTRACT_TEMPERATURE = float(os.environ.get("GRAPHITI_LLM_TEMPERATURE", "0.1"))
QWEN3_EXTRACT_MAX_TOKENS = int(os.environ.get("GRAPHITI_LLM_MAX_TOKENS", "4096"))
QWEN3_NO_THINK_MARKER = "/no_think"


class BuildCancelledError(Exception):
    """Raised by ``add_text_batches_async`` when cooperative cancel fires.

    This is not an upstream error — it means the task was cancelled on
    purpose (user abort, runner watchdog timeout, etc). Callers should
    translate it into a ``cancelled`` task state, not a ``failed`` one,
    and skip any retry / alternate-provider fallbacks.
    """

    def __init__(
        self,
        *,
        batch_index: int,
        total_batches: int,
        processed_chunks: int,
        total_chunks: int,
    ) -> None:
        self.batch_index = batch_index
        self.total_batches = total_batches
        self.processed_chunks = processed_chunks
        self.total_chunks = total_chunks
        super().__init__(
            f"build cancelled at batch {batch_index}/{total_batches} "
            f"({processed_chunks}/{total_chunks} chunks processed)"
        )


# ============== 类型触发规则 ==============

# 每种实体类型的触发条件（pattern-based，不是定义）
_TYPE_TRIGGER_RULES = {
    "Topic": "When text introduces or frames a broad subject area, research field, or domain.",
    "Problem": "When text describes a deficiency, challenge, limitation, bottleneck, error source, gap, or unsolved issue. Look for words like: problem, challenge, limitation, however, but, gap, issue, drawback, weakness.",
    "Solution": "When text proposes a method, framework, approach, strategy, or system that addresses a problem.",
    "Architecture": "When text explicitly describes a system architecture, multi-component design, or layered structure with named components. Do NOT use for general methodologies.",
    "Layer": "When text explicitly names layers, tiers, or modules within an architecture. Do NOT invent layers the text doesn't describe.",
    "Mechanism": "When text describes a specific technique, algorithm, design pattern, or operational mechanism used within a solution.",
    "Decision": "When text explicitly compares alternatives and states a choice with reasoning (e.g. 'we chose X over Y because...'). Do NOT invent decisions the author didn't make.",
    "Technology": "When text mentions a specific tool, framework, library, protocol, model, dataset, or software system by name.",
    "Metric": "When text names an abstract measurement dimension or evaluation criterion without a specific value (e.g. 'accuracy', 'latency', 'coverage').",
    "Evidence": "When text states a concrete data point, experimental result, or quantitative finding WITH specific numbers (e.g. '20.47% improvement', '171 task chains from 1484 log lines'). These are factual observations, not abstract metrics.",
    "Insight": "When text presents the author's conclusion, core finding, principle, lesson learned, or forward-looking judgment. Usually found in conclusions, summaries, or contribution sections.",
    "Example": "When text provides a concrete illustration, use case, scenario, or sample to explain a concept.",
}

# 关键边模式（论证链）
_ARGUMENTATION_EDGE_PATTERNS = """Priority edge patterns (argumentation chain):
- Topic --HAS_PROBLEM--> Problem (topic contains problems)
- Solution --SOLVES--> Problem (solution addresses problem)
- Solution --USES_MECHANISM--> Mechanism (solution uses technique)
- Solution --USES_TECHNOLOGY--> Technology (solution uses tool)
- Solution --EVIDENCED_BY--> Evidence (solution supported by data)
- Mechanism --PRODUCES--> Evidence (mechanism produces results)
- Solution --PRODUCES--> Insight (solution leads to conclusion)
- Insight --EVIDENCED_BY--> Evidence (conclusion supported by data)
- Solution --HAS_EXAMPLE--> Example (solution demonstrated by case)"""


def ontology_to_extraction_brief(ontology: dict) -> str:
    """将 ontology 编译为 Graphiti 可用的精简抽取合同。

    原则：短而强，避免挤压 chunk 文本的上下文空间。
    只保留最高 ROI 的部分：类型列表 + 文章锚点 + 关键约束。
    """
    entity_types = ontology.get("entity_types", [])
    edge_types = ontology.get("edge_types", [])
    entity_names = [e["name"] for e in entity_types]
    edge_names = [e["name"] for e in edge_types]

    # --- 类型列表 + 文章锚点 ---
    type_lines = []
    for et in entity_types:
        name = et["name"]
        trigger = _TYPE_TRIGGER_RULES.get(name, "")
        examples = et.get("examples", [])
        # 只用一行：类型名 + 简短触发 + 锚点
        parts = [f"{name}"]
        if trigger:
            # 取触发规则的第一句
            first_sentence = trigger.split(".")[0] + "."
            parts.append(first_sentence)
        if examples:
            anchors = ", ".join(str(ex) for ex in examples[:2])
            parts.append(f"e.g. {anchors}")
        type_lines.append(" — ".join(parts))

    brief = f"""Extract the article's argumentation structure. Entity types: {', '.join(entity_names)}. Edge types: {', '.join(edge_names)}.

TYPES & ANCHORS:
{chr(10).join(type_lines)}

KEY RULES:
1. Extract Problem/Evidence/Insight entities — don't skip them for Solution/Technology.
2. Evidence = concrete data WITH numbers. Insight = author's conclusions. Problem = challenges/gaps.
3. Entity names must be specific (not generic "problem" or "framework").
4. A framework vs its sub-module = different entities. A result vs its conclusion = different entities.
5. Attributes must be simple strings. Each entity item needs `name` + `entity_type_id`. Each edge needs `source_entity_name`, `target_entity_name`, `relation_type`, `fact`.

DEDUP RULES (critical):
6. Do NOT create near-duplicate entities. If two names describe the same concept (e.g. "hierarchical filtering" and "hierarchical filtering mechanism"), use ONE name consistently.
7. Reuse existing entity names from previous chunks. Check entity names already extracted before creating new ones.
8. Prefer shorter, cleaner names. "分层扩展过滤" is better than "分层扩展过滤机制".

BALANCE RULES:
9. Don't over-extract Mechanism/Technology at the expense of Problem/Evidence/Insight. Aim for balanced distribution across types.
10. Each chunk should contribute at most 2-3 Mechanism entities. Merge sub-steps of the same mechanism into one entity.

{_ARGUMENTATION_EDGE_PATTERNS}
"""
    return brief


# ============== OpenAI-compatible LLM 适配器 ==============
# 历史名字是 MiniMaxLLMClient，实际上这个类的 JSON 修复/字段规范化逻辑
# 对任何 OpenAI 兼容端点都有用。GPT consult 2026-04-11 之后引入了 provider
# 参数来区分"qwen3_local 本地 LM Studio"和"deepseek 在线 API"，
# 不再把 qwen3 的 /no_think 硬塞给每一个模型。

class MiniMaxLLMClient(OpenAIGenericClient):
    """OpenAI 兼容的 LLM 客户端，处理 <think>、markdown 包裹、字段别名和 JSON 修复。

    provider 参数：
        - "qwen3_local"  : 本地 LM Studio + qwen3-30b-a3b-2507，需要 /no_think
                            系统前缀 + extra_body chat_template_kwargs 才能关掉
                            reasoning spiral；
        - "deepseek"     : DeepSeek 在线 OpenAI 兼容 API，本身不是 thinking 模型，
                            不注入 /no_think；只设 temperature/max_tokens。
    """

    ROOT_FIELD_ALIASES = {
        "extracted_entities": ("entities", "nodes", "items"),
        # 注意 "facts": Bailian qwen3.5-plus 在 Graphiti 的 edge prompt 下
        # (prompt 文案是 "extract fact triples"，且每条记录里有 "fact" 字段)
        # 大概率会把顶层 key 写成 "facts" 而不是 "edges"。不加这个 alias
        # 就会静默丢边。详见 docs/superpowers/plans 2026-04-15 root-cause notes.
        "edges": ("relations", "relationships", "triples", "extracted_edges", "facts"),
        "summaries": ("entity_summaries", "summary_updates", "items"),
    }

    FIELD_ALIASES = {
        "name": ("entity_name", "entity_text", "node_name", "title"),
        "entity_type_id": ("type_id", "entity_type", "entity_type_name", "type", "label"),
        "source_entity_name": ("source_entity", "source_name", "source_node_name"),
        "target_entity_name": ("target_entity", "target_name", "target_node_name"),
        "relation_type": ("edge_name", "relationship_type", "fact_type", "relation", "type"),
        "fact": ("edge_fact", "relation_fact", "description", "statement"),
        "summary": ("entity_summary", "description", "content"),
    }

    def __init__(
        self,
        *args,
        provider: str = "qwen3_local",
        temperature_override: Optional[float] = None,
        max_tokens_override: Optional[int] = None,
        **kwargs,
    ):
        config = kwargs.get("config")
        if config is None and args:
            config = args[0]
        super().__init__(*args, **kwargs)
        self._response_base_url = getattr(config, "base_url", None)
        self._provider = provider
        self._temperature_override = temperature_override
        self._max_tokens_override = max_tokens_override
        self.json_parse_repair_count = 0
        self.json_parse_retry_count = 0
        self.json_parse_failure_count = 0
        # Incremented on every successful _generate_response call. Used by
        # add_text_batches_async as a live-progress heartbeat so the auto
        # pipeline watchdog can see that bulk extract is doing work even
        # while graphiti-core's per-batch progress_callback stays silent.
        self.llm_call_counter = 0

    def _build_response_format(
        self,
        response_model: type[BaseModel] | None = None,
    ) -> dict[str, typing.Any]:
        return build_structured_json_response_format(
            self._response_base_url,
            response_model=response_model,
        )

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        from openai.types.chat import ChatCompletionMessageParam
        openai_messages: list[ChatCompletionMessageParam] = []
        system_prepended = False
        use_qwen3_markers = self._provider == "qwen3_local"
        is_deepseek = self._provider == "deepseek"
        # When the "deepseek" provider slot is actually pointed at Bailian
        # (DashScope) running a qwen3.x model — e.g. for the 2026-04-15
        # provider-swap experiment — we need extra_body.chat_template_kwargs
        # to disable the model's default thinking mode, but we must NOT inject
        # the /no_think system prefix (that's a LM Studio chat-template marker
        # DashScope doesn't understand).
        model_lower = (getattr(self, "model", "") or "").lower()
        base_url_lower = (self._response_base_url or "").lower()
        is_dashscope_qwen3 = (
            is_deepseek
            and "dashscope" in base_url_lower
            and "qwen3" in model_lower
        )
        for m in messages:
            m.content = self._clean_input(m.content)
            if m.role == 'user':
                openai_messages.append({'role': 'user', 'content': m.content})
            elif m.role == 'system':
                # qwen3-30b-a3b-2507 tuning (see module-level constants):
                # Prepend `/no_think` to the first system message so the
                # Qwen3 chat template skips its reasoning block on the
                # local runtime path. 仅在 provider==qwen3_local 时注入，
                # 避免把 qwen3 私有 chat_template 标记传给 DeepSeek 等不认识
                # 它的在线模型。
                content = m.content
                if use_qwen3_markers and not system_prepended:
                    content = f"{QWEN3_NO_THINK_MARKER}\n{content}"
                system_prepended = True
                openai_messages.append({'role': 'system', 'content': content})

        # If there was no system message at all, inject a minimal one so
        # the no_think marker still reaches qwen3.
        if not system_prepended and use_qwen3_markers:
            openai_messages.insert(0, {
                'role': 'system',
                'content': f"{QWEN3_NO_THINK_MARKER}\nYou are a precise knowledge graph extractor. Return valid JSON only.",
            })

        # DeepSeek enforces: when response_format={"type":"json_object"},
        # the prompt MUST contain the literal word "json". Graphiti's
        # internal dedup / edge-type-resolution prompts don't always
        # have it, so DeepSeek returns 400 invalid_request_error. Fix:
        # if the provider is DeepSeek and none of the messages mention
        # "json", inject a tiny guard sentence into the first system
        # message (or prepend one). This is a documented DeepSeek quirk
        # (GPT consult 2026-04-11).
        if is_deepseek:
            combined = " ".join(
                str(msg.get("content", "")) for msg in openai_messages
            ).lower()
            if "json" not in combined:
                guard = "Respond with valid JSON only."
                if openai_messages and openai_messages[0]["role"] == "system":
                    openai_messages[0]["content"] = (
                        guard + "\n" + openai_messages[0]["content"]
                    )
                else:
                    openai_messages.insert(
                        0,
                        {"role": "system", "content": guard},
                    )

        # Per-provider tuning:
        # - qwen3_local: 用模块常量 (temp=0.1 max_tokens=4096) + extra_body
        #   强关 reasoning。
        # - deepseek: 用 llm_mode_service 传进来的 override，不带 extra_body,
        #   也不带 chat_template_kwargs（DeepSeek 不认这个 key）。
        if use_qwen3_markers:
            tuned_temperature = QWEN3_EXTRACT_TEMPERATURE
            tuned_max_tokens = QWEN3_EXTRACT_MAX_TOKENS
            extra_body_kwargs: Dict[str, Any] = {
                "chat_template_kwargs": {"enable_thinking": False},
            }
        else:
            tuned_temperature = (
                self._temperature_override
                if self._temperature_override is not None
                else 0.1
            )
            tuned_max_tokens = (
                self._max_tokens_override
                if self._max_tokens_override is not None
                else 4096
            )
            extra_body_kwargs = None
            if is_dashscope_qwen3:
                # DashScope qwen3 series defaults thinking ON; turn it off
                # for structured extraction to keep latency predictable.
                extra_body_kwargs = {
                    "chat_template_kwargs": {"enable_thinking": False},
                }

        call_started = asyncio.get_event_loop().time()
        create_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": tuned_temperature,
            "max_tokens": tuned_max_tokens,
            "response_format": self._build_response_format(response_model),
        }
        if extra_body_kwargs is not None:
            create_kwargs["extra_body"] = extra_body_kwargs
        response = await self.client.chat.completions.create(**create_kwargs)
        call_elapsed_ms = int((asyncio.get_event_loop().time() - call_started) * 1000)
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        # Advance the heartbeat counter so add_text_batches_async's
        # background progress-bumper can prove we're making forward
        # progress inside a bulk extract call.
        self.llm_call_counter += 1
        logger.info(
            "LLM call #%d: model=%s prompt_tokens=%s completion_tokens=%s elapsed_ms=%d",
            self.llm_call_counter,
            self.model,
            prompt_tokens,
            completion_tokens,
            call_elapsed_ms,
        )
        result = response.choices[0].message.content or ''
        # 清理 MiniMax 的 <think> 标签
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        parsed = self._parse_llm_json(result)

        # 修复字段名：当 LLM 返回 list 而 response_model 期望 dict 时
        if response_model is not None and isinstance(parsed, list):
            for field_name, field_info in response_model.model_fields.items():
                annotation = field_info.annotation
                if hasattr(annotation, '__origin__') and annotation.__origin__ is list:
                    parsed = {field_name: parsed}
                    break
            else:
                parsed = {'items': parsed}

        entity_type_lookup = self._extract_entity_type_lookup(messages)
        entity_name_lookup = self._extract_entity_name_lookup(messages)

        # 按 response_model 递归规范化，而不是只做零散 alias 替换
        # Capture pre-normalization parsed object for debug dump diffing.
        _pre_normalize = parsed
        validation_error = None
        if response_model is not None:
            parsed = self._normalize_for_model(
                parsed,
                response_model,
                entity_type_lookup,
                entity_name_lookup,
            )
            parsed = self._sanitize_model_payload(parsed, response_model)
            try:
                validated = response_model.model_validate(parsed)
                parsed = validated.model_dump(exclude_none=True)
            except Exception as exc:
                validation_error = f"{type(exc).__name__}: {exc}"[:600]
                logger.warning(
                    "LLM response validation still failed for %s: %s; normalized=%s",
                    response_model.__name__,
                    exc,
                    self._preview_json(parsed),
                )

        # === Provider-compatibility diagnostic scaffold (OFF by default). ===
        #
        # Set DEBUG_LLM_DUMP=/path/to/file.jsonl to append one JSONL record
        # per LLM call containing the raw model response plus the parsed
        # dict before/after normalization. Purpose: diagnose cases where a
        # new provider returns a JSON shape the normalizer doesn't handle
        # (e.g. the 2026-04-15 incident where Bailian qwen3.5-plus wrote
        # `{"facts": [...]}` instead of `{"edges": [...]}` and we silently
        # produced 0 edges — see tests/test_graph_builder_edge_alias.py).
        #
        # Default off → zero overhead. Do NOT enable in production: this
        # dump contains full prompt/response bodies and can grow large.
        # User messages are truncated to 500 chars to keep per-call records
        # small; raw_response_text is full so we can see the exact shape.
        _dump_path = os.environ.get("DEBUG_LLM_DUMP")
        if _dump_path:
            try:
                _dump_record = {
                    "model": getattr(self, "model", None),
                    "response_model": (
                        response_model.__name__ if response_model is not None else None
                    ),
                    "system_messages": [
                        (m.get("content") or "")[:1500]
                        for m in openai_messages if m.get("role") == "system"
                    ],
                    "user_messages_preview": [
                        (m.get("content") or "")[:500]
                        for m in openai_messages if m.get("role") == "user"
                    ],
                    "raw_response_text": result,  # full raw model output
                    "pre_normalize_parsed": _pre_normalize,
                    "post_normalize_parsed": parsed,
                    "validation_error": validation_error,
                    "call_elapsed_ms": call_elapsed_ms,
                }
                with open(_dump_path, "a", encoding="utf-8") as _df:
                    _df.write(json.dumps(_dump_record, ensure_ascii=False, default=str))
                    _df.write("\n")
            except Exception as _dump_exc:  # never break the build for debug
                logger.debug("debug dump failed: %s", _dump_exc)

        logger.debug(
            "MiniMax normalized response for %s: %s",
            response_model.__name__ if response_model is not None else "raw_json",
            self._preview_json(parsed),
        )

        return parsed

    def _parse_llm_json(self, raw_text: str) -> Any:
        candidates = []
        cleaned = self._clean_json_wrappers(raw_text)
        if cleaned:
            candidates.append(cleaned)

        extracted = self._extract_json_fragment(cleaned or raw_text)
        if extracted and extracted not in candidates:
            candidates.append(extracted)

        errors = []
        for candidate in candidates:
            repaired_variant = self._repair_json_text(candidate)
            for index, variant in enumerate((candidate, repaired_variant)):
                if not variant:
                    continue
                try:
                    if index == 1 and variant != candidate:
                        self._increment_counter("json_parse_repair_count")
                    return json.loads(variant)
                except json.JSONDecodeError as exc:
                    errors.append(f"{exc.msg} @ {exc.pos}")

            repaired_object = self._repair_json_object(repaired_variant or candidate)
            if repaired_object is not None:
                self._increment_counter("json_parse_repair_count")
                return repaired_object

        detail = "; ".join(errors[-4:]) if errors else "no candidate payload"
        self._increment_counter("json_parse_retry_count")
        self._increment_counter("json_parse_failure_count")
        raise ValueError(f"Unable to parse LLM JSON payload: {detail}")

    def _increment_counter(self, field_name: str, amount: int = 1) -> None:
        current = getattr(self, field_name, 0)
        setattr(self, field_name, current + amount)

    def _clean_json_wrappers(self, text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return cleaned.strip()

    def _extract_json_fragment(self, text: str) -> str:
        if not text:
            return ""

        first_index = next((index for index, char in enumerate(text) if char in "{["), None)
        if first_index is None:
            return text.strip()

        first_opener = text[first_index]
        first_closer = "}" if first_opener == "{" else "]"
        fragment = self._find_balanced_json_fragment(text, first_index, first_opener, first_closer)
        if fragment:
            return fragment.strip()

        fallback_end = max(text.rfind("}"), text.rfind("]"))
        if fallback_end > first_index:
            return text[first_index:fallback_end + 1].strip()

        for index in range(first_index + 1, len(text)):
            char = text[index]
            if char not in "{[":
                continue

            closer = "}" if char == "{" else "]"
            fragment = self._find_balanced_json_fragment(text, index, char, closer)
            if fragment:
                return fragment.strip()
        return text.strip()

    def _find_balanced_json_fragment(
        self,
        text: str,
        start: int,
        opener: str,
        closer: str,
    ) -> str:
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        return ""

    def _repair_json_text(self, text: str) -> str:
        repaired = self._extract_json_fragment(self._clean_json_wrappers(text))
        if not repaired:
            return repaired

        repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
        repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
        repaired = repaired.replace("\t", " ")
        repaired = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]', ' ', repaired)
        repaired = re.sub(r'(?<=[}\]0-9"])\s*(?="[^"]+"\s*:)', ', ', repaired)
        repaired = re.sub(r'(?<=})\s*(?={)', ', ', repaired)
        repaired = re.sub(r'(?<=])\s*(?={)', ', ', repaired)

        def _replace_newlines(match: re.Match[str]) -> str:
            string_value = match.group(0)
            string_value = string_value.replace("\n", " ").replace("\r", " ")
            return re.sub(r'\s+', ' ', string_value)

        repaired = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', _replace_newlines, repaired)
        repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

        if self._has_unbalanced_quotes(repaired):
            repaired += '"'

        open_brackets = repaired.count('[') - repaired.count(']')
        open_braces = repaired.count('{') - repaired.count('}')
        if open_brackets > 0:
            repaired += ']' * open_brackets
        if open_braces > 0:
            repaired += '}' * open_braces

        return repaired.strip()

    def _repair_json_object(self, text: str) -> Any | None:
        if not text:
            return None
        try:
            return repair_json(text, return_objects=True, skip_json_loads=True)
        except Exception:
            return None

    def _has_unbalanced_quotes(self, text: str) -> bool:
        quote_count = 0
        escaped = False
        for char in text:
            if char == '\\' and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                quote_count += 1
            escaped = False
        return quote_count % 2 == 1

    def _extract_entity_type_lookup(self, messages: list[Message]) -> dict[str, int]:
        lookup = {"entity": 0}
        pattern = re.compile(r"<ENTITY TYPES>\s*(.*?)\s*</ENTITY TYPES>", re.DOTALL | re.IGNORECASE)

        for message in messages:
            content = getattr(message, "content", "") or ""
            match = pattern.search(content)
            if not match:
                continue

            try:
                entity_types = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                entity_types = []

            if isinstance(entity_types, list):
                for item in entity_types:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("entity_type_name", "")).strip()
                    entity_type_id = item.get("entity_type_id")
                    if name and isinstance(entity_type_id, int):
                        lookup[name.lower()] = entity_type_id
            if len(lookup) > 1:
                break

        return lookup

    def _extract_entity_name_lookup(self, messages: list[Message]) -> list[str]:
        pattern = re.compile(r"<ENTITIES>\s*(.*?)\s*</ENTITIES>", re.DOTALL | re.IGNORECASE)

        for message in messages:
            content = getattr(message, "content", "") or ""
            match = pattern.search(content)
            if not match:
                continue

            try:
                entities = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

            if not isinstance(entities, list):
                continue

            names = []
            for item in entities:
                if isinstance(item, dict):
                    name = str(item.get("name", "")).strip()
                    if name:
                        names.append(name)
            if names:
                return names

        return []

    def _normalize_for_model(
        self,
        data: Any,
        model: type[BaseModel],
        entity_type_lookup: dict[str, int],
        entity_name_lookup: list[str],
    ) -> Any:
        return self._normalize_annotation(data, model, entity_type_lookup, entity_name_lookup)

    def _normalize_annotation(
        self,
        value: Any,
        annotation: Any,
        entity_type_lookup: dict[str, int],
        entity_name_lookup: list[str],
        field_name: str | None = None,
    ) -> Any:
        annotation = self._unwrap_optional(annotation)
        origin = get_origin(annotation)

        if annotation in (Any, typing.Any):
            return self._normalize_loose_value(value)

        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return self._normalize_model_payload(
                value,
                annotation,
                entity_type_lookup,
                entity_name_lookup,
            )

        if origin in (list, List):
            inner = get_args(annotation)[0] if get_args(annotation) else Any
            if value is None:
                return []
            if not isinstance(value, list):
                value = [value]
            return [
                self._normalize_annotation(
                    item,
                    inner,
                    entity_type_lookup,
                    entity_name_lookup,
                    field_name=field_name,
                )
                for item in value
            ]

        if origin in (dict, Dict):
            if not isinstance(value, dict):
                return {}
            return {str(k): self._normalize_loose_value(v) for k, v in value.items()}

        if annotation is str:
            return self._coerce_string(
                value,
                field_name=field_name,
                entity_name_lookup=entity_name_lookup,
            )
        if annotation is int:
            return self._coerce_int(value, entity_type_lookup)
        if annotation is float:
            return self._coerce_float(value)
        if annotation is bool:
            return self._coerce_bool(value)

        return self._normalize_loose_value(value)

    def _normalize_model_payload(
        self,
        value: Any,
        model: type[BaseModel],
        entity_type_lookup: dict[str, int],
        entity_name_lookup: list[str],
    ) -> dict[str, Any]:
        if isinstance(value, list):
            list_field = self._get_single_list_field(model)
            value = {list_field: value} if list_field is not None else {}
        elif not isinstance(value, dict):
            value = {}

        normalized: dict[str, Any] = {}
        expected_fields = model.model_fields

        for target_field, aliases in self.ROOT_FIELD_ALIASES.items():
            if target_field in expected_fields and target_field not in value:
                for alias in aliases:
                    if alias in value:
                        value[target_field] = value[alias]
                        break

        list_field = self._get_single_list_field(model)
        if list_field is not None and list_field not in value:
            inner_model = self._get_list_inner_model(expected_fields[list_field].annotation)
            if isinstance(value, dict) and inner_model is not None and self._looks_like_model_item(value, inner_model):
                value = {list_field: [value]}

        for field_name, field_info in expected_fields.items():
            raw_value = self._find_field_value(value, field_name)
            if raw_value is None:
                if field_name == "entity_type_id":
                    raw_value = 0
                elif field_name == "fact":
                    raw_value = self._build_fallback_fact(value)
                elif get_origin(self._unwrap_optional(field_info.annotation)) in (list, List):
                    raw_value = []

            if raw_value is None:
                continue

            normalized[field_name] = self._normalize_annotation(
                raw_value,
                field_info.annotation,
                entity_type_lookup,
                entity_name_lookup,
                field_name=field_name,
            )

        return normalized

    def _sanitize_model_payload(
        self,
        payload: Any,
        model: type[BaseModel],
    ) -> Any:
        """丢弃无法通过内部 item 校验的脏列表项，避免整块失败。"""
        if not isinstance(payload, dict):
            return payload

        list_field = self._get_single_list_field(model)
        if list_field is None or list_field not in payload:
            return payload

        inner_model = self._get_list_inner_model(model.model_fields[list_field].annotation)
        if inner_model is None or not isinstance(payload[list_field], list):
            return payload

        sanitized_items = []
        dropped_count = 0
        for item in payload[list_field]:
            try:
                validated_item = inner_model.model_validate(item)
            except Exception:
                dropped_count += 1
                continue
            sanitized_items.append(validated_item.model_dump(exclude_none=True))

        if dropped_count:
            logger.warning(
                "Dropped %s invalid items while sanitizing %s.%s",
                dropped_count,
                model.__name__,
                list_field,
            )

        payload[list_field] = sanitized_items
        return payload

    def _find_field_value(self, payload: dict[str, Any], field_name: str) -> Any:
        if field_name in payload:
            return payload[field_name]

        for alias in self.FIELD_ALIASES.get(field_name, ()):
            if alias in payload:
                return payload[alias]

        for prefix in ("entity_", "relation_", "edge_", "node_"):
            candidate = f"{prefix}{field_name}"
            if candidate in payload:
                return payload[candidate]

        return None

    def _build_fallback_fact(self, payload: dict[str, Any]) -> str | None:
        source = self._coerce_string(self._find_field_value(payload, "source_entity_name"), "source_entity_name")
        target = self._coerce_string(self._find_field_value(payload, "target_entity_name"), "target_entity_name")
        relation = self._coerce_string(self._find_field_value(payload, "relation_type"), "relation_type")
        if source and target and relation:
            return f"{source} {relation} {target}"
        return None

    def _unwrap_optional(self, annotation: Any) -> Any:
        origin = get_origin(annotation)
        if origin in (typing.Union, UnionType):
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(args) == 1:
                return args[0]
        return annotation

    def _get_single_list_field(self, model: type[BaseModel]) -> str | None:
        if len(model.model_fields) != 1:
            return None
        field_name, field_info = next(iter(model.model_fields.items()))
        if get_origin(self._unwrap_optional(field_info.annotation)) in (list, List):
            return field_name
        return None

    def _get_list_inner_model(self, annotation: Any) -> type[BaseModel] | None:
        annotation = self._unwrap_optional(annotation)
        if get_origin(annotation) not in (list, List):
            return None
        args = get_args(annotation)
        if not args:
            return None
        inner = self._unwrap_optional(args[0])
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return inner
        return None

    def _looks_like_model_item(self, payload: dict[str, Any], model: type[BaseModel]) -> bool:
        return any(self._find_field_value(payload, field_name) is not None for field_name in model.model_fields)

    def _coerce_string(
        self,
        value: Any,
        field_name: str | None = None,
        entity_name_lookup: list[str] | None = None,
    ) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            result = value.strip()
        elif isinstance(value, (int, float, bool)):
            result = str(value)
        elif isinstance(value, dict):
            for key in ("name", "entity_name", "node_name", "title", "label"):
                if key in value and value[key] is not None:
                    result = self._coerce_string(
                        value[key],
                        field_name=field_name,
                        entity_name_lookup=entity_name_lookup,
                    )
                    break
            else:
                result = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif isinstance(value, list):
            if all(not isinstance(item, (dict, list)) for item in value):
                result = "; ".join(str(item) for item in value)
            else:
                result = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            result = str(value)

        if field_name in {"source_entity_name", "target_entity_name"}:
            return self._resolve_entity_name(result, entity_name_lookup or [])
        return result

    def _resolve_entity_name(self, value: str | None, entity_name_lookup: list[str]) -> str | None:
        if value is None:
            return None

        candidate = value.strip()
        if not candidate or not entity_name_lookup:
            return candidate

        if candidate in entity_name_lookup:
            return candidate

        normalized_candidate = self._normalize_name_key(candidate)
        normalized_map = {self._normalize_name_key(name): name for name in entity_name_lookup}

        if normalized_candidate in normalized_map:
            return normalized_map[normalized_candidate]

        containment_matches = [
            name for name in entity_name_lookup
            if normalized_candidate and (
                normalized_candidate in self._normalize_name_key(name)
                or self._normalize_name_key(name) in normalized_candidate
            )
        ]
        if len(containment_matches) == 1:
            return containment_matches[0]

        close_matches = difflib.get_close_matches(candidate, entity_name_lookup, n=1, cutoff=0.72)
        if close_matches:
            return close_matches[0]

        normalized_candidates = list(normalized_map.keys())
        close_normalized = difflib.get_close_matches(
            normalized_candidate,
            normalized_candidates,
            n=1,
            cutoff=0.72,
        )
        if close_normalized:
            return normalized_map[close_normalized[0]]

        return candidate

    def _normalize_name_key(self, value: str) -> str:
        return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()

    def _coerce_int(self, value: Any, entity_type_lookup: dict[str, int]) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return int(stripped)
            return entity_type_lookup.get(stripped.lower(), 0)
        if isinstance(value, dict):
            for key in ("entity_type_id", "type_id", "entity_type_name", "entity_type", "name", "label", "type"):
                if key in value:
                    return self._coerce_int(value[key], entity_type_lookup)
        return 0

    def _coerce_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    def _coerce_bool(self, value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    def _normalize_loose_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._normalize_loose_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._normalize_loose_value(item) for item in value]
        return value

    def _preview_json(self, value: Any) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
        return text[:600] + ("..." if len(text) > 600 else "")


# ============== 本地 Embedder ==============

class LocalEmbedder(EmbedderClient):
    """使用 sentence-transformers 的本地 Embedder"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = None
        self._fallback_dimensions = 384
        self._fallback_reason = ""

        try:
            from sentence_transformers import SentenceTransformer
            try:
                self.model = SentenceTransformer(model_name, local_files_only=True)
            except TypeError:
                # 测试桩或旧版本 sentence-transformers 可能不支持 local_files_only。
                self.model = SentenceTransformer(model_name)
        except Exception as exc:
            self._fallback_reason = str(exc)
            logger.warning(
                "LocalEmbedder fallback activated for model %s: %s",
                model_name,
                exc,
            )

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self._fallback_dimensions
        normalized_text = " ".join((text or "").lower().split())
        if not normalized_text:
            return vector

        for index, char in enumerate(normalized_text):
            slot = (ord(char) * 17 + index * 31) % self._fallback_dimensions
            vector[slot] += 1.0 + ((ord(char) % 13) / 13.0)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    async def create(self, input_data: str | list[str]) -> list[float]:
        if isinstance(input_data, str):
            texts = [input_data]
        else:
            texts = list(input_data)

        if not texts:
            return [0.0] * self.get_dimensions()

        if self.model is None:
            return self._hash_embedding(texts[0])

        embeddings = self.model.encode(texts, normalize_embeddings=True)
        if getattr(embeddings, "ndim", 1) == 1:
            return embeddings.tolist()
        return embeddings[0].tolist()

    async def create_batch(self, input_data: list[str], batch_size: int = 64) -> list[list[float]]:
        if not input_data:
            return []

        if self.model is None:
            return [self._hash_embedding(text) for text in input_data]

        embeddings = self.model.encode(input_data, normalize_embeddings=True)
        if getattr(embeddings, "ndim", 1) == 1:
            return [embeddings.tolist()]
        return [embedding.tolist() for embedding in embeddings]

    def get_dimensions(self) -> int:
        if self.model is None:
            return self._fallback_dimensions
        return self.model.get_sentence_embedding_dimension()


# ============== 图谱信息 ==============

@dataclass
class GraphInfo:
    """图谱信息"""
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


# ============== 图谱构建服务 ==============

class GraphBuilderService:
    """
    图谱构建服务
    使用 Graphiti + Neo4j 本地构建知识图谱
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化图谱构建服务

        Args:
            api_key: 保留参数兼容性，不再使用
        """
        self._client = None  # 延迟初始化（需要 async）
        self._graph_driver = None
        self._llm_client = None
        self.task_manager = TaskManager()
        self._phase1_entity_labels: set[str] = set()
        self._build_stats: Dict[str, Any] = {}

    async def _get_client(self) -> Graphiti:
        """获取或创建 Graphiti 客户端（延迟初始化 + 模式快照）。

        设计（GPT consult 2026-04-11）:
        - 每次 _get_client 都从 llm_mode_service 读一次"参数快照"
        - 如果 self._client 还在、但快照里的 provider/base_url/model 和上一次不同,
          说明中间切过模式，扔掉旧的 client 重新建一个。实际切换请求本身已经
          在 /api/config/llm-mode 入口处阻塞 in-flight，保证此处不会打断正在
          跑的 extraction；这里只是"下一次任务自动吃到新模式"的最后一步。
        - GRAPHITI 的全局 SEMAPHORE_LIMIT 也在这里重置。
        """
        from .llm_mode_service import get_graphiti_llm_params

        params = get_graphiti_llm_params()
        snapshot = (params['provider'], params['base_url'], params['model'])

        if self._client is not None and getattr(self, '_client_snapshot', None) != snapshot:
            # 模式发生过切换：把旧 client 扔掉（对象 GC 后 OpenAI 连接池会自己关）。
            logger.info(
                'Graphiti 客户端将被重建：mode 从 %s 切到 %s',
                getattr(self, '_client_snapshot', None),
                snapshot,
            )
            self._client = None
            self._llm_client = None

        if self._client is None:
            # Graphiti 内部可能检查 OPENAI_API_KEY 环境变量
            os.environ['OPENAI_API_KEY'] = params['api_key'] or 'dummy'

            # LLMConfig 的 temperature/max_tokens 是 graphiti-core 内部的默认值,
            # 真正起作用的覆盖在 MiniMaxLLMClient._generate_response 里。
            # 但传一个合理值仍然有帮助：graphiti 部分代码会读它。
            llm_config_temperature = (
                params.get('temperature') if params.get('temperature') is not None
                else QWEN3_EXTRACT_TEMPERATURE
            )
            llm_config_max_tokens = (
                params.get('max_tokens') if params.get('max_tokens') is not None
                else QWEN3_EXTRACT_MAX_TOKENS
            )

            llm_client = MiniMaxLLMClient(
                config=LLMConfig(
                    api_key=params['api_key'],
                    base_url=params['base_url'],
                    model=params['model'],
                    small_model=params['model'],
                    temperature=llm_config_temperature,
                    max_tokens=llm_config_max_tokens,
                ),
                provider=params['provider'],
                temperature_override=params.get('temperature'),
                max_tokens_override=params.get('max_tokens'),
            )
            self._llm_client = llm_client
            embedder = LocalEmbedder()

            # mutate graphiti-core 的模块全局并发闸门。
            _graphiti_helpers.SEMAPHORE_LIMIT = params['semaphore_limit']

            self._client = Graphiti(
                uri=Config.NEO4J_URI,
                user=Config.NEO4J_USER,
                password=Config.NEO4J_PASSWORD,
                llm_client=llm_client,
                embedder=embedder,
            )
            self._client_snapshot = snapshot
            await self._client.build_indices_and_constraints()
            logger.info(
                "Graphiti 客户端初始化完成 mode=%s provider=%s model=%s base_url=%s semaphore=%s",
                params['mode'],
                params['provider'],
                params['model'],
                params['base_url'],
                params['semaphore_limit'],
            )

        return self._client

    async def _get_graph_driver(self) -> Neo4jDriver:
        """获取只读 Neo4j driver，避免只读查询触发完整 Graphiti/embedder 初始化。"""
        if self._graph_driver is None:
            self._graph_driver = Neo4jDriver(
                uri=Config.NEO4J_URI,
                user=Config.NEO4J_USER,
                password=Config.NEO4J_PASSWORD,
            )
        return self._graph_driver

    def create_graph(self, name: str) -> str:
        """创建图谱（返回逻辑 graph_id，Graphiti 无需显式创建）"""
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        logger.info(f"创建图谱: graph_id={graph_id}, name={name}")
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """
        设置图谱本体

        将 ontology JSON 转换为 Graphiti 的 entity_types/edge_types 参数格式，
        并生成 custom_extraction_instructions 指导 LLM 按认知结构抽取。
        """
        logger.info(f"设置本体: graph_id={graph_id}, "
                     f"entity_types={len(ontology.get('entity_types', []))}, "
                     f"edge_types={len(ontology.get('edge_types', []))}")

        # 转换 entity_types: Dict[str, Type[BaseModel]]
        self._graphiti_entity_types = {}
        self._phase1_entity_labels = set()
        for entity_def in ontology.get("entity_types", []):
            name = entity_def["name"]
            description = entity_def.get("description", f"{name}类型实体")
            self._phase1_entity_labels.add(name)

            # 构建 Pydantic 模型属性
            from pydantic import Field as PydanticField
            attrs = {"__doc__": description, "__annotations__": {}}
            for attr_def in entity_def.get("attributes", []):
                attr_name = attr_def["name"]
                # 跳过保留字
                if attr_name.lower() in {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}:
                    attr_name = f"entity_{attr_name}"
                attr_desc = attr_def.get("description", attr_name)
                attrs[attr_name] = PydanticField(description=attr_desc, default=None)
                attrs["__annotations__"][attr_name] = Optional[str]

            entity_class = type(name, (BaseModel,), attrs)
            self._graphiti_entity_types[name] = entity_class

        # 转换 edge_types: Dict[str, Type[BaseModel]]
        self._graphiti_edge_types = {}
        for edge_def in ontology.get("edge_types", []):
            name = edge_def["name"]
            description = edge_def.get("description", f"{name}关系")

            attrs = {"__doc__": description, "__annotations__": {}}
            edge_class = type(name, (BaseModel,), attrs)
            self._graphiti_edge_types[name] = edge_class

        # 构建 edge_type_map: Dict[Tuple[str, str], List[str]]
        self._graphiti_edge_type_map = {}
        self._allowed_edge_pairs = set()
        for edge_def in ontology.get("edge_types", []):
            edge_name = edge_def["name"]
            for st in edge_def.get("source_targets", []):
                source = st.get("source", "")
                target = st.get("target", "")
                if source and target:
                    key = (source, target)
                    self._allowed_edge_pairs.add((source, edge_name, target))
                    if key not in self._graphiti_edge_type_map:
                        self._graphiti_edge_type_map[key] = []
                    self._graphiti_edge_type_map[key].append(edge_name)

        # 构建 custom_extraction_instructions（编译 ontology 为"抽取合同"）
        self._custom_extraction_instructions = ontology_to_extraction_brief(ontology)

        logger.info(f"本体转换完成: {len(self._graphiti_entity_types)} entity types, "
                     f"{len(self._graphiti_edge_types)} edge types, "
                     f"{len(self._graphiti_edge_type_map)} edge type mappings")

    async def ensure_phase1_storage_compatibility_async(self, graph_id: str | None = None) -> list[str]:
        """删除会干扰 phase-1 动态 ontology 写入的全局唯一约束。"""
        client = await self._get_client()
        driver = client.driver
        target_labels = set(self._phase1_entity_labels)
        if not target_labels:
            return []

        result = await driver.execute_query(
            "SHOW CONSTRAINTS "
            "YIELD name, type, entityType, labelsOrTypes, properties "
            "RETURN name, type, entityType, labelsOrTypes, properties"
        )
        records = result.records if hasattr(result, 'records') else (result[0] if isinstance(result, tuple) else result)

        dropped_constraints: list[str] = []
        for record in records:
            constraint_type = record.get("type") or record["type"]
            entity_type = record.get("entityType") or record["entityType"]
            if constraint_type != "NODE_PROPERTY_UNIQUENESS" or entity_type != "NODE":
                continue

            labels = set(record.get("labelsOrTypes") or record["labelsOrTypes"] or [])
            properties = set(record.get("properties") or record["properties"] or [])
            if not labels.intersection(target_labels):
                continue
            if properties.issubset(PHASE1_SCHEMA_SAFE_PROPERTIES):
                continue
            if not properties.intersection(PHASE1_SCHEMA_RISK_PROPERTIES):
                continue

            constraint_name = record.get("name") or record["name"]
            escaped_name = str(constraint_name).replace("`", "``")
            await driver.execute_query(f"DROP CONSTRAINT `{escaped_name}` IF EXISTS")
            dropped_constraints.append(str(constraint_name))

        if dropped_constraints:
            logger.warning(
                "Phase-1 schema guard dropped conflicting constraints for %s: %s",
                graph_id or "unknown_graph",
                ", ".join(dropped_constraints),
            )

        return dropped_constraints

    def ensure_phase1_storage_compatibility(self, graph_id: str | None = None) -> list[str]:
        return self._run_async(self.ensure_phase1_storage_compatibility_async(graph_id))

    def _reset_build_stats(self, total_chunks: int) -> None:
        self._build_stats = {
            "chunk_count": total_chunks,
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
            "adaptive_split_count": 0,
            "adaptive_subchunk_count": 0,
        }

    def _with_timeout_context(
        self,
        exc: Exception,
        *,
        context: str,
        timeout_seconds: int,
    ) -> Exception:
        if isinstance(exc, TimeoutError):
            message = str(exc).strip() or f"{context} 请求超时（>{timeout_seconds}s）"
            return TimeoutError(message)
        return exc

    def get_build_diagnostics(self) -> Dict[str, Any]:
        diagnostics = dict(self._build_stats)
        llm_client = self._llm_client
        diagnostics["json_parse_repair_count"] = getattr(llm_client, "json_parse_repair_count", 0)
        diagnostics["json_parse_retry_count"] = getattr(llm_client, "json_parse_retry_count", 0)
        diagnostics["json_parse_failure_count"] = getattr(llm_client, "json_parse_failure_count", 0)
        return diagnostics

    async def _bulk_progress_heartbeat(
        self,
        *,
        bulk_task: "asyncio.Future",
        progress_callback: Optional[Callable],
        batch_index: int,
        total_batches: int,
        processed_before: int,
        total_chunks: int,
    ) -> None:
        """Bump task.message while ``add_episode_bulk`` is running.

        Reads the MiniMaxLLMClient's ``llm_call_counter`` every 10 seconds.
        If the counter advanced, emits a new ``progress_callback`` with the
        current count appended so that the auto-pipeline watchdog sees the
        task message change and resets its no-progress stall counter. If
        the counter did NOT advance, we also re-emit with the SAME count
        so a genuine model stall leaves the watchdog's stall counter
        alive and ready to fire at the 240s limit.

        Cancelled from the outer loop's ``finally`` once the bulk call
        returns or raises. Any heartbeat-triggered exception is swallowed
        — this is pure observability, not a critical path.
        """
        if progress_callback is None:
            return
        client = self._llm_client
        last_seen = getattr(client, "llm_call_counter", 0) if client else 0
        base_fraction = (
            processed_before / total_chunks if total_chunks else 0.0
        )
        try:
            while not bulk_task.done():
                await asyncio.sleep(10)
                if bulk_task.done():
                    break
                current = getattr(client, "llm_call_counter", last_seen)
                # Always emit — the *counter value* is part of the message
                # string, so even a message carrying the same count
                # advances the hash if the bumper just started. Watchdog
                # compares (progress, message) tuples.
                progress_callback(
                    f"正在处理批次 {batch_index}/{total_batches}"
                    f"（{processed_before}/{total_chunks} 块已完成, "
                    f"LLM 调用 {current}）...",
                    base_fraction,
                )
                last_seen = current
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            # Heartbeat must never propagate into the build path.
            logger.debug("bulk progress heartbeat failed", exc_info=True)

    async def add_text_batches_async(
        self,
        graph_id: str,
        chunks: List[str],
        source_description: str = "text_import",
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """异步批量添加文本到图谱（使用 add_episode_bulk）.

        ``cancel_check`` is a best-effort cooperative cancel hook. If
        provided, the builder calls it at each batch boundary and raises
        :class:`BuildCancelledError` when the hook returns ``True``. The
        currently-in-flight ``add_episode_bulk`` call still completes
        before the cancel is observed.
        """
        client = await self._get_client()
        total_chunks = len(chunks)
        self._reset_build_stats(total_chunks)
        batch_size = max(int(batch_size or 1), 1)

        if progress_callback:
            progress_callback(
                f"正在构建 {total_chunks} 个文本块的批量任务...",
                0.0,
            )

        # Build list[RawEpisode] from all chunks
        now = datetime.now()
        raw_episodes = [
            RawEpisode(
                name=f"chunk_{i + 1}",
                content=chunk,
                source_description=f"{source_description}:{graph_id}",
                source=EpisodeType.text,
                reference_time=now,
            )
            for i, chunk in enumerate(chunks)
        ]

        # Collect ontology kwargs
        kwargs: Dict[str, Any] = {}
        if hasattr(self, '_graphiti_entity_types') and self._graphiti_entity_types:
            kwargs['entity_types'] = self._graphiti_entity_types
        if hasattr(self, '_graphiti_edge_types') and self._graphiti_edge_types:
            kwargs['edge_types'] = self._graphiti_edge_types
        if hasattr(self, '_graphiti_edge_type_map') and self._graphiti_edge_type_map:
            kwargs['edge_type_map'] = self._graphiti_edge_type_map
        if hasattr(self, '_custom_extraction_instructions') and self._custom_extraction_instructions:
            kwargs['custom_extraction_instructions'] = self._custom_extraction_instructions

        all_episode_ids: list[str] = []
        total_batches = max((total_chunks + batch_size - 1) // batch_size, 1)

        for batch_index, start in enumerate(range(0, total_chunks, batch_size), start=1):
            # Cooperative cancel check at batch boundary. Called BEFORE any
            # LLM work is issued so we never start a new batch after the
            # user requested cancel. A currently-in-flight LLM call from
            # the previous batch is not interrupted — it finishes, then
            # the loop exits at the next iteration.
            if cancel_check is not None and cancel_check():
                logger.info(
                    "add_text_batches_async: cancel requested at batch %s/%s",
                    batch_index,
                    total_batches,
                )
                raise BuildCancelledError(
                    batch_index=batch_index,
                    total_batches=total_batches,
                    processed_chunks=len(all_episode_ids),
                    total_chunks=total_chunks,
                )

            batch_episodes = raw_episodes[start:start + batch_size]
            processed_before = len(all_episode_ids)
            split_batch_after_failure = False

            if progress_callback:
                progress_callback(
                    f"正在处理批次 {batch_index}/{total_batches}（{processed_before}/{total_chunks} 块已完成）...",
                    processed_before / total_chunks if total_chunks else 0.0,
                )

            last_error: Optional[Exception] = None
            for attempt in range(PHASE1_MAX_CHUNK_RETRIES + 1):
                try:
                    # Live-progress heartbeat: graphiti-core's add_episode_bulk
                    # can spend several minutes inside a single batch on a
                    # local reasoning model, during which the outer
                    # progress_callback never fires. Without a heartbeat,
                    # the auto-pipeline watchdog sees task.message stuck
                    # on "正在处理批次 N/M" for >240s and cancels the run
                    # even though internal LLM work is advancing. We read
                    # the MiniMaxLLMClient's llm_call_counter every 10s
                    # and bump the message iff it advanced — this reflects
                    # REAL forward progress, so if the model genuinely
                    # stalls the counter stays flat and the watchdog
                    # still fires correctly.
                    bulk_task = asyncio.ensure_future(
                        client.add_episode_bulk(
                            batch_episodes,
                            group_id=graph_id,
                            **kwargs,
                        )
                    )
                    heartbeat_task = asyncio.ensure_future(
                        self._bulk_progress_heartbeat(
                            bulk_task=bulk_task,
                            progress_callback=progress_callback,
                            batch_index=batch_index,
                            total_batches=total_batches,
                            processed_before=processed_before,
                            total_chunks=total_chunks,
                        )
                    )
                    try:
                        result = await asyncio.wait_for(
                            bulk_task,
                            timeout=PHASE1_BULK_CALL_TIMEOUT_SECONDS,
                        )
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except (asyncio.CancelledError, Exception):
                            pass
                    batch_episode_ids = [str(ep.uuid) for ep in (result.episodes or [])]
                    all_episode_ids.extend(batch_episode_ids)
                    self._build_stats["processed_chunk_count"] += len(batch_episodes)
                    self._build_stats["episode_count"] = len(all_episode_ids)
                    break
                except Exception as exc:
                    exc = self._with_timeout_context(
                        exc,
                        context=f"批次 {batch_index}/{total_batches} bulk 调用",
                        timeout_seconds=PHASE1_BULK_CALL_TIMEOUT_SECONDS,
                    )
                    last_error = exc
                    error_kind = classify_upstream_error(exc)
                    if error_kind == UpstreamErrorKind.RATE_LIMIT:
                        self._build_stats["rate_limit_hit_count"] += 1

                    should_retry = (
                        attempt < PHASE1_MAX_CHUNK_RETRIES
                        and is_retryable_upstream_error(error_kind)
                    )

                    if not should_retry:
                        if is_adaptive_split_candidate(exc, error_kind):
                            split_batch_after_failure = True
                            break
                        raise

                    delay = compute_retry_delay(attempt)
                    self._build_stats["retry_count"] += 1

                    logger.warning(
                        "add_episode_bulk 批次 %s/%s 失败(kind=%s)，%.1fs 后重试(%s/%s): %s",
                        batch_index,
                        total_batches,
                        error_kind.value,
                        delay,
                        attempt + 1,
                        PHASE1_MAX_CHUNK_RETRIES,
                        exc,
                    )
                    if progress_callback:
                        progress_callback(
                            f"批次 {batch_index}/{total_batches} 遇到 {error_kind.value}，{delay:.0f}s 后重试...",
                            processed_before / total_chunks if total_chunks else 0.0,
                        )
                    await asyncio.sleep(delay)

            if last_error is not None and self._build_stats["processed_chunk_count"] < start + len(batch_episodes):
                if not split_batch_after_failure:
                    raise last_error

                logger.warning(
                    "批次 %s/%s 在 bulk 模式下持续失败，切换为逐块提交: %s",
                    batch_index,
                    total_batches,
                    last_error,
                )
                if progress_callback:
                    progress_callback(
                        f"批次 {batch_index}/{total_batches} bulk 失败，切换为逐块提交...",
                        processed_before / total_chunks if total_chunks else 0.0,
                    )

                batch_episode_ids: list[str] = []
                for offset, raw_episode in enumerate(batch_episodes, start=1):
                    chunk_num = start + offset
                    chunk_episode_ids = await self._add_chunk_with_retries(
                        client=client,
                        chunk=raw_episode.content,
                        chunk_num=chunk_num,
                        total_chunks=total_chunks,
                        graph_id=graph_id,
                        source_description=source_description,
                        extra_kwargs=kwargs,
                        progress_callback=progress_callback,
                    )
                    batch_episode_ids.extend(chunk_episode_ids)

                all_episode_ids.extend(batch_episode_ids)
                self._build_stats["processed_chunk_count"] += len(batch_episodes)
                self._build_stats["episode_count"] = len(all_episode_ids)

        if progress_callback:
            progress_callback(
                f"全部 {total_chunks} 个文本块处理完成",
                1.0,
            )

        return all_episode_ids

    async def _add_chunk_with_retries(
        self,
        *,
        client: Graphiti,
        chunk: str,
        chunk_num: int,
        total_chunks: int,
        graph_id: str,
        source_description: str,
        extra_kwargs: Dict[str, Any],
        progress_callback: Optional[Callable] = None,
        split_depth: int = 0,
    ) -> list[str]:
        last_error = None

        for attempt in range(PHASE1_MAX_CHUNK_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    client.add_episode(
                        name=f"chunk_{chunk_num}",
                        episode_body=chunk,
                        source_description=f"{source_description}:{graph_id}",
                        reference_time=datetime.now(),
                        source=EpisodeType.text,
                        group_id=graph_id,
                        **extra_kwargs,
                    ),
                    timeout=PHASE1_SINGLE_CALL_TIMEOUT_SECONDS,
                )
                return [self._extract_episode_uuid(result)]
            except Exception as exc:
                exc = self._with_timeout_context(
                    exc,
                    context=f"文本块 {chunk_num}/{total_chunks}",
                    timeout_seconds=PHASE1_SINGLE_CALL_TIMEOUT_SECONDS,
                )
                last_error = exc
                error_kind = classify_upstream_error(exc)
                if error_kind == UpstreamErrorKind.RATE_LIMIT:
                    self._build_stats["rate_limit_hit_count"] += 1
                should_retry = (
                    attempt < PHASE1_MAX_CHUNK_RETRIES
                    and is_retryable_upstream_error(error_kind)
                )

                if not should_retry:
                    split_episode_ids = await self._split_chunk_after_retry_exhaustion(
                        client=client,
                        chunk=chunk,
                        chunk_num=chunk_num,
                        total_chunks=total_chunks,
                        graph_id=graph_id,
                        source_description=source_description,
                        extra_kwargs=extra_kwargs,
                        progress_callback=progress_callback,
                        split_depth=split_depth,
                        error_kind=error_kind,
                        last_error=exc,
                    )
                    if split_episode_ids is not None:
                        return split_episode_ids
                    raise

                delay = compute_retry_delay(attempt)
                self._build_stats["retry_count"] += 1

                logger.warning(
                    "文本块 %s/%s 处理失败(kind=%s)，%.1fs 后重试(%s/%s): %s",
                    chunk_num,
                    total_chunks,
                    error_kind.value,
                    delay,
                    attempt + 1,
                    PHASE1_MAX_CHUNK_RETRIES,
                    exc,
                )
                if progress_callback:
                    progress_callback(
                        f"文本块 {chunk_num}/{total_chunks} 遇到 {error_kind.value}，{delay:.0f}s 后重试...",
                        chunk_num / total_chunks if total_chunks else 0,
                    )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"文本块 {chunk_num} 未知失败")

    async def _split_chunk_after_retry_exhaustion(
        self,
        *,
        client: Graphiti,
        chunk: str,
        chunk_num: int,
        total_chunks: int,
        graph_id: str,
        source_description: str,
        extra_kwargs: Dict[str, Any],
        progress_callback: Optional[Callable],
        split_depth: int,
        error_kind: UpstreamErrorKind,
        last_error: Exception,
    ) -> list[str] | None:
        if not is_adaptive_split_candidate(last_error, error_kind):
            return None
        if split_depth >= PHASE1_MAX_TIMEOUT_SPLIT_DEPTH:
            return None

        subchunks = self._split_chunk_for_retry(chunk)
        if len(subchunks) <= 1:
            return None

        self._build_stats["adaptive_split_count"] += 1
        self._build_stats["adaptive_subchunk_count"] += len(subchunks)

        logger.warning(
            "文本块 %s/%s 持续 transient 失败，拆分为 %d 个子块后重试(depth=%d): %s",
            chunk_num,
            total_chunks,
            len(subchunks),
            split_depth + 1,
            last_error,
        )
        if progress_callback:
            progress_callback(
                f"文本块 {chunk_num}/{total_chunks} 持续失败，拆分为 {len(subchunks)} 个子块重试...",
                chunk_num / total_chunks if total_chunks else 0,
            )

        episode_ids: list[str] = []
        for subchunk in subchunks:
            sub_ids = await self._add_chunk_with_retries(
                client=client,
                chunk=subchunk,
                chunk_num=chunk_num,
                total_chunks=total_chunks,
                graph_id=graph_id,
                source_description=source_description,
                extra_kwargs=extra_kwargs,
                progress_callback=progress_callback,
                split_depth=split_depth + 1,
            )
            episode_ids.extend(sub_ids)
        return episode_ids

    def _split_chunk_for_retry(self, chunk: str) -> list[str]:
        text = (chunk or "").strip()
        if len(text) < PHASE1_TIMEOUT_SPLIT_MIN_CHUNK_SIZE * 2:
            return []

        target_size = max(
            PHASE1_TIMEOUT_SPLIT_MIN_CHUNK_SIZE,
            min(PHASE1_TIMEOUT_SPLIT_MAX_CHUNK_SIZE, max(len(text) // 2, PHASE1_TIMEOUT_SPLIT_MIN_CHUNK_SIZE)),
        )
        overlap = min(PHASE1_TIMEOUT_SPLIT_MAX_OVERLAP, max(target_size // 4, 40))
        chunks = [
            part.strip()
            for part in split_text_into_chunks(text, target_size, overlap)
            if (part or "").strip()
        ]
        if len(chunks) <= 1:
            return []
        if max(len(part) for part in chunks) >= len(text):
            return []
        return chunks

    def _extract_episode_uuid(self, episode_result: Any) -> str:
        episode_uuid = getattr(episode_result, "uuid", None)
        if episode_uuid:
            return str(episode_uuid)

        episode = getattr(episode_result, "episode", None)
        episode_uuid = getattr(episode, "uuid", None)
        if episode_uuid:
            return str(episode_uuid)

        raise AttributeError(f"无法从返回结果中提取 episode uuid: {type(episode_result).__name__}")

    def _remap_edge_name(
        self,
        edge_name: str,
        source_labels: list[str] | None,
        target_labels: list[str] | None,
    ) -> str | None:
        """尝试按 (source_label, target_label) 对将 edge_name 映射到 ontology 允许的名称。

        两阶段策略（GPT 建议）：
        1. 精确匹配：edge_name 完全命中 _allowed_edge_pairs → 原样返回
        2. 对映射：edge_name 不匹配但 (source, target) 对在 ontology 中有允许的 edge type → remap
        返回 None 表示该边无法被任何 ontology 规则接纳。
        """
        allowed_pairs = getattr(self, "_allowed_edge_pairs", set())
        edge_type_map = getattr(self, "_graphiti_edge_type_map", {})
        if not allowed_pairs:
            return edge_name  # 没有 ontology 约束，全部放行

        source_candidates = [
            label for label in (source_labels or [])
            if label and label not in {"Entity", "__Entity__"}
        ]
        target_candidates = [
            label for label in (target_labels or [])
            if label and label not in {"Entity", "__Entity__"}
        ]

        if not source_candidates or not target_candidates:
            return None  # 缺少类型标签，无法判断

        # 阶段 1：精确匹配
        for sl in source_candidates:
            for tl in target_candidates:
                if (sl, edge_name, tl) in allowed_pairs:
                    return edge_name

        # 阶段 2：按 (source, target) 对 remap 到 ontology 允许的第一个 edge type
        for sl in source_candidates:
            for tl in target_candidates:
                allowed_names = edge_type_map.get((sl, tl))
                if allowed_names:
                    logger.debug(
                        "Edge remap: '%s' (%s→%s) → '%s'",
                        edge_name, sl, tl, allowed_names[0],
                    )
                    return allowed_names[0]

        return None

    def _is_edge_allowed(
        self,
        edge_name: str,
        source_labels: list[str] | None,
        target_labels: list[str] | None,
    ) -> bool:
        """检查关系是否符合 ontology 规定的 source-target 约束。"""
        if not edge_name:
            return False

        allowed_pairs = getattr(self, "_allowed_edge_pairs", set())
        if not allowed_pairs:
            return True

        source_candidates = [
            label for label in (source_labels or [])
            if label and label not in {"Entity", "__Entity__"}
        ]
        target_candidates = [
            label for label in (target_labels or [])
            if label and label not in {"Entity", "__Entity__"}
        ]

        for source_label in source_candidates:
            for target_label in target_candidates:
                if (source_label, edge_name, target_label) in allowed_pairs:
                    return True
        return False

    async def prune_invalid_edges_async(self, graph_id: str) -> list[str]:
        """两阶段清洗：先规范化 edge name，再删除无法映射的边。"""
        client = await self._get_client()
        driver = client.driver

        if not getattr(self, "_allowed_edge_pairs", None):
            return []

        result = await driver.execute_query(
            "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
            "WHERE a.group_id = $group_id "
            "RETURN r.uuid AS uuid, r.name AS name, labels(a) AS source_labels, labels(b) AS target_labels",
            group_id=graph_id,
        )
        records = result.records if hasattr(result, "records") else (result[0] if isinstance(result, tuple) else result)

        invalid_edge_ids = []
        remapped_edges = []  # (uuid, new_name)
        for record in records:
            edge_uuid = record.get("uuid") or record["uuid"]
            edge_name = record.get("name") or record["name"]
            source_labels = record.get("source_labels") or record["source_labels"]
            target_labels = record.get("target_labels") or record["target_labels"]

            new_name = self._remap_edge_name(edge_name, source_labels, target_labels)
            if new_name is None:
                invalid_edge_ids.append(edge_uuid)
            elif new_name != edge_name:
                remapped_edges.append((edge_uuid, new_name))

        # 批量 remap edge names
        if remapped_edges:
            for euuid, new_name in remapped_edges:
                await driver.execute_query(
                    "MATCH ()-[r:RELATES_TO]->() WHERE r.uuid = $uuid SET r.name = $name",
                    uuid=euuid, name=new_name,
                )
            logger.info("已规范化 %s 条边的 edge name", len(remapped_edges))

        # 删除无法映射的边
        if invalid_edge_ids:
            await driver.execute_query(
                "MATCH ()-[r:RELATES_TO]->() WHERE r.uuid IN $edge_uuids DELETE r",
                edge_uuids=invalid_edge_ids,
            )
            logger.warning(
                "已删除 %s 条不符合 ontology 方向约束的关系（%s 条已 remap 保留）",
                len(invalid_edge_ids), len(remapped_edges),
            )

        return invalid_edge_ids

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[str]:
        """同步包装器（兼容现有调用方式）.

        ``cancel_check`` is forwarded to :meth:`add_text_batches_async` to
        enable cooperative cancel from callers that cannot share coroutines
        (e.g. the Flask build task thread).
        """
        return self._run_async(
            self.add_text_batches_async(
                graph_id,
                chunks,
                "text_import",
                batch_size,
                progress_callback,
                cancel_check,
            )
        )

    def _run_async(self, coro):
        """在后台线程中安全运行异步代码"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            if self._client is not None:
                try:
                    loop.run_until_complete(self._client.close())
                except Exception as exc:
                    logger.debug("关闭 Graphiti 客户端失败: %s", exc)
                finally:
                    self._client = None
            if self._graph_driver is not None:
                try:
                    loop.run_until_complete(self._graph_driver.close())
                except Exception as exc:
                    logger.debug("关闭 Neo4j driver 失败: %s", exc)
                finally:
                    self._graph_driver = None
            # 清理所有 pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def _wait_for_episodes(
        self,
        episode_uuids: List[str],
        progress_callback: Optional[Callable] = None,
        timeout: int = 600
    ):
        """等待所有 episode 处理完成

        Graphiti 的 add_episode 返回时数据已在 Neo4j 中，无需额外等待。
        保留此方法兼容现有调用流程。
        """
        if progress_callback:
            progress_callback(
                f"所有 {len(episode_uuids)} 个文本块已处理完成",
                1.0
            )

    async def _get_graph_info_async(self, graph_id: str) -> GraphInfo:
        """获取图谱信息（异步）"""
        client = await self._get_client()
        driver = client.driver

        # execute_query 返回 EagerResult(records, summary, keys)
        result = await driver.execute_query(
            "MATCH (n:Entity) WHERE n.group_id = $group_id "
            "RETURN n.name AS name, labels(n) AS labels",
            group_id=graph_id
        )
        node_records = result.records if hasattr(result, 'records') else (result[0] if isinstance(result, tuple) else result)

        result = await driver.execute_query(
            "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
            "WHERE a.group_id = $group_id "
            "RETURN count(r) AS cnt",
            group_id=graph_id
        )
        edge_records = result.records if hasattr(result, 'records') else (result[0] if isinstance(result, tuple) else result)

        # 统计实体类型
        entity_types = set()
        for record in node_records:
            labels = record.get("labels") or record["labels"]
            if labels:
                for label in labels:
                    if label not in ("Entity", "__Entity__"):
                        entity_types.add(label)

        edge_count = edge_records[0]["cnt"] if edge_records else 0

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(node_records),
            edge_count=edge_count,
            entity_types=list(entity_types)
        )

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱信息（同步包装）"""
        return self._run_async(self._get_graph_info_async(graph_id))

    def _normalize_node_labels(self, labels: list[str] | None) -> list[str]:
        return [
            label for label in (labels or [])
            if label and label not in ("Entity", "__Entity__")
        ]


    def _build_display_graph_data(
        self,
        graph_id: str,
        nodes_data: List[Dict[str, Any]],
        edges_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        deduped_edges: List[Dict[str, Any]] = []
        seen_edges = set()
        for edge in edges_data:
            source_uuid = edge.get("source_node_uuid")
            target_uuid = edge.get("target_node_uuid")
            relation_name = " ".join((edge.get("name") or edge.get("fact_type") or "").split())
            fact = " ".join((edge.get("fact") or "").split())
            if not source_uuid or not target_uuid:
                continue

            edge_key = (source_uuid, target_uuid, relation_name, fact)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            normalized_edge = dict(edge)
            normalized_edge["name"] = relation_name
            normalized_edge["fact_type"] = relation_name
            normalized_edge["fact"] = fact
            deduped_edges.append(normalized_edge)

        degree_map: Counter[str] = Counter()
        for edge in deduped_edges:
            degree_map[edge["source_node_uuid"]] += 1
            degree_map[edge["target_node_uuid"]] += 1

        filtered_nodes: List[Dict[str, Any]] = []
        dropped_unclassified = 0
        dropped_isolated = 0

        for node in nodes_data:
            normalized_node = dict(node)
            normalized_node["labels"] = self._normalize_node_labels(node.get("labels"))

            if not normalized_node["labels"]:
                dropped_unclassified += 1
                continue

            # 保留所有有类型标签的节点（包括孤立节点），让前端决定展示策略
            filtered_nodes.append(normalized_node)
            if degree_map.get(node["uuid"], 0) == 0:
                dropped_isolated += 1  # 仅统计，不丢弃

        kept_node_ids = {node["uuid"] for node in filtered_nodes}
        filtered_edges = [
            edge for edge in deduped_edges
            if edge["source_node_uuid"] in kept_node_ids and edge["target_node_uuid"] in kept_node_ids
        ]

        if dropped_unclassified or dropped_isolated or len(filtered_edges) != len(deduped_edges):
            logger.info(
                "Graph data normalized for %s: dropped_unclassified=%s isolated_kept=%s dropped_edges=%s total_nodes=%s total_edges=%s",
                graph_id,
                dropped_unclassified,
                dropped_isolated,
                len(deduped_edges) - len(filtered_edges),
                len(filtered_nodes),
                len(filtered_edges),
            )

        return {
            "graph_id": graph_id,
            "nodes": filtered_nodes,
            "edges": filtered_edges,
            "node_count": len(filtered_nodes),
            "edge_count": len(filtered_edges),
        }

    async def get_graph_data_async(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据（异步）"""
        driver = await self._get_graph_driver()

        # 获取所有实体节点
        result = await driver.execute_query(
            "MATCH (n:Entity) WHERE n.group_id = $group_id "
            "RETURN n.uuid AS uuid, n.name AS name, labels(n) AS labels, "
            "n.summary AS summary, n.created_at AS created_at "
            "ORDER BY n.name",
            group_id=graph_id
        )
        nodes_records = result.records if hasattr(result, 'records') else (result[0] if isinstance(result, tuple) else result)

        # 创建节点映射
        node_map = {}
        nodes_data = []
        for record in nodes_records:
            node_uuid = record["uuid"]
            node_name = record["name"]
            node_map[node_uuid] = node_name

            created_at = record.get("created_at")
            if created_at:
                created_at = str(created_at)

            nodes_data.append({
                "uuid": node_uuid,
                "name": node_name,
                "labels": self._normalize_node_labels(record["labels"] or []),
                "summary": record.get("summary") or "",
                "attributes": {},
                "created_at": created_at,
            })

        # 获取所有关系
        result = await driver.execute_query(
            "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
            "WHERE a.group_id = $group_id "
            "RETURN r.uuid AS uuid, r.name AS name, r.fact AS fact, "
            "a.uuid AS source_node_uuid, b.uuid AS target_node_uuid, "
            "a.name AS source_node_name, b.name AS target_node_name, "
            "r.created_at AS created_at, r.valid_at AS valid_at, "
            "r.invalid_at AS invalid_at, r.expired_at AS expired_at "
            "ORDER BY a.name",
            group_id=graph_id
        )
        edges_records = result.records if hasattr(result, 'records') else (result[0] if isinstance(result, tuple) else result)

        edges_data = []
        for record in edges_records:
            created_at = record.get("created_at")
            valid_at = record.get("valid_at")
            invalid_at = record.get("invalid_at")
            expired_at = record.get("expired_at")

            edges_data.append({
                "uuid": record["uuid"],
                "name": record["name"] or "",
                "fact": record["fact"] or "",
                "fact_type": record["name"] or "",
                "source_node_uuid": record["source_node_uuid"],
                "target_node_uuid": record["target_node_uuid"],
                "source_node_name": record["source_node_name"] or "",
                "target_node_name": record["target_node_name"] or "",
                "attributes": {},
                "created_at": str(created_at) if created_at else None,
                "valid_at": str(valid_at) if valid_at else None,
                "invalid_at": str(invalid_at) if invalid_at else None,
                "expired_at": str(expired_at) if expired_at else None,
                "episodes": [],
            })

        return self._build_display_graph_data(graph_id, nodes_data, edges_data)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据（同步包装）"""
        return self._run_async(self.get_graph_data_async(graph_id))

    async def delete_graph_async(self, graph_id: str):
        """删除图谱（异步）"""
        client = await self._get_client()
        driver = client.driver

        # 删除该 group_id 下的所有数据
        await driver.execute_query(
            "MATCH (n) WHERE n.group_id = $group_id DETACH DELETE n",
            group_id=graph_id
        )
        logger.info(f"图谱已删除: {graph_id}")

    def delete_graph(self, graph_id: str):
        """删除图谱（同步包装）"""
        self._run_async(self.delete_graph_async(graph_id))
