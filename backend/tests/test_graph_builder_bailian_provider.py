"""Regression test: provider='bailian' must send enable_thinking=False.

Context: Bailian qwen3 series (qwen3.5-plus etc.) defaults thinking=on on
DashScope. For Graphiti's structured extraction we want thinking OFF, so
graph_builder._generate_response must inject
extra_body.chat_template_kwargs.enable_thinking=False whenever the
provider is 'bailian'.

Before P1 (formal bailian mode) this was done via a fragile
`is_dashscope_qwen3` heuristic that sniffed base_url + model_name. P1
retired that heuristic in favor of an explicit provider check, and this
test locks the new behavior in.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from graphiti_core.prompts.models import Message  # noqa: E402

from app.services.graph_builder import MiniMaxLLMClient  # noqa: E402


def _make_client(*, provider: str) -> MiniMaxLLMClient:
    """Build a bare MiniMaxLLMClient with just enough state to drive
    _generate_response, without actually opening an OpenAI connection."""
    client = MiniMaxLLMClient.__new__(MiniMaxLLMClient)
    client._provider = provider
    client._response_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    client._temperature_override = None
    client._max_tokens_override = None
    client.model = "qwen3.5-plus"
    client.json_parse_repair_count = 0
    client.json_parse_retry_count = 0
    client.json_parse_failure_count = 0
    client.llm_call_counter = 0

    # Mock the underlying openai client — we only care what create() gets.
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = '{"edges": []}'
    mock_completion.usage = MagicMock()
    mock_completion.usage.prompt_tokens = 10
    mock_completion.usage.completion_tokens = 2
    mock_completion.usage.total_tokens = 12

    openai_client = MagicMock()
    openai_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    client.client = openai_client
    return client


def _run_generate(provider: str) -> dict:
    """Call _generate_response and return the kwargs that hit create()."""
    client = _make_client(provider=provider)
    messages = [Message(role="system", content="extract edges"),
                Message(role="user", content="text")]
    asyncio.run(client._generate_response(messages, response_model=None))
    call_kwargs = client.client.chat.completions.create.call_args.kwargs
    return call_kwargs


def test_bailian_provider_sets_enable_thinking_false():
    kwargs = _run_generate("bailian")
    assert "extra_body" in kwargs, \
        "bailian provider must inject extra_body for DashScope qwen3"
    chat_template = kwargs["extra_body"].get("chat_template_kwargs", {})
    assert chat_template.get("enable_thinking") is False


def test_deepseek_provider_does_not_set_extra_body():
    """DeepSeek doesn't understand chat_template_kwargs; sending it could
    trigger a 400 invalid_request_error. Must stay off."""
    kwargs = _run_generate("deepseek")
    assert "extra_body" not in kwargs or not kwargs.get("extra_body")


def test_qwen3_local_still_sets_enable_thinking_false():
    """Regression: the LM Studio path was the original user of this
    extra_body; don't break it while adding bailian."""
    kwargs = _run_generate("qwen3_local")
    assert "extra_body" in kwargs
    chat_template = kwargs["extra_body"].get("chat_template_kwargs", {})
    assert chat_template.get("enable_thinking") is False


def test_bailian_provider_does_not_inject_no_think_system_prefix():
    """The /no_think marker is an LM-Studio chat-template quirk; DashScope
    qwen3 doesn't understand it. Must stay out of the bailian path."""
    client = _make_client(provider="bailian")
    messages = [Message(role="system", content="you are an expert"),
                Message(role="user", content="text")]
    asyncio.run(client._generate_response(messages, response_model=None))
    call_kwargs = client.client.chat.completions.create.call_args.kwargs
    system_msg_contents = [
        m["content"] for m in call_kwargs["messages"] if m["role"] == "system"
    ]
    joined = " ".join(system_msg_contents)
    assert "/no_think" not in joined, \
        "bailian provider must NOT inject /no_think system prefix"
