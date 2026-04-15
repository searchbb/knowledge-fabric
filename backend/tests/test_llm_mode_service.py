"""Unit tests for llm_mode_service — mode switching + param snapshots.

These tests use monkeypatch + tmp_path to redirect the mode file location
and stub Config values; no real LLM/Neo4j/filesystem side effects leak.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import llm_mode_service  # noqa: E402
from app.services.llm_mode_service import (  # noqa: E402
    VALID_MODES,
    get_graphiti_llm_params,
    get_llm_mode,
    set_llm_mode,
)


@pytest.fixture
def tmp_mode_file(monkeypatch, tmp_path):
    """Redirect the persistent mode file into a tmp dir for each test."""
    tmp_file = tmp_path / "llm_mode.json"
    monkeypatch.setattr(llm_mode_service, "_MODE_FILE", str(tmp_file))
    return tmp_file


# ----- VALID_MODES lock ---------------------------------------------


def test_valid_modes_includes_all_three():
    """Regression: any change here needs an explicit test update so we
    don't accidentally drop bailian (or one of the others)."""
    assert VALID_MODES == ('local', 'online', 'bailian')


# ----- set_llm_mode -------------------------------------------------


def test_set_mode_rejects_unknown(tmp_mode_file):
    with pytest.raises(ValueError):
        set_llm_mode("gibberish")


def test_set_mode_online_requires_deepseek_key(tmp_mode_file, monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config, "DEEPSEEK_API_KEY", None)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        set_llm_mode("online")


def test_set_mode_bailian_requires_bailian_key(tmp_mode_file, monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config, "BAILIAN_API_KEY", None)
    with pytest.raises(ValueError, match="BAILIAN_API_KEY"):
        set_llm_mode("bailian")


def test_set_mode_local_never_requires_key(tmp_mode_file, monkeypatch):
    """local mode has no provider-key guard — it's the safe fallback."""
    from app.config import Config
    monkeypatch.setattr(Config, "DEEPSEEK_API_KEY", None)
    monkeypatch.setattr(Config, "BAILIAN_API_KEY", None)
    payload = set_llm_mode("local")
    assert payload["mode"] == "local"


def test_set_mode_bailian_writes_file(tmp_mode_file, monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config, "BAILIAN_API_KEY", "sk-test")
    set_llm_mode("bailian", updated_by="test")
    data = json.loads(tmp_mode_file.read_text(encoding="utf-8"))
    assert data["mode"] == "bailian"
    assert data["updated_by"] == "test"


# ----- get_llm_mode -------------------------------------------------


def test_get_mode_creates_default_when_missing(tmp_mode_file, monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config, "LLM_MODE_DEFAULT", "bailian")
    payload = get_llm_mode()
    assert payload["mode"] == "bailian"
    # Also persisted.
    assert tmp_mode_file.exists()


def test_get_mode_falls_back_on_invalid_file_contents(tmp_mode_file):
    tmp_mode_file.write_text('{"mode": "not-a-real-mode"}', encoding="utf-8")
    payload = get_llm_mode()
    assert payload["mode"] in VALID_MODES


# ----- get_graphiti_llm_params --------------------------------------


def test_params_local_returns_qwen3_local_provider(tmp_mode_file, monkeypatch):
    set_llm_mode("local")
    params = get_graphiti_llm_params()
    assert params["mode"] == "local"
    assert params["provider"] == "qwen3_local"
    assert params["use_qwen3_no_think"] is True


def test_params_online_returns_deepseek_provider(tmp_mode_file, monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config, "DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setattr(Config, "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setattr(Config, "DEEPSEEK_MODEL_NAME", "deepseek-chat")
    monkeypatch.setattr(Config, "DEEPSEEK_SEMAPHORE_LIMIT", 6)
    monkeypatch.setattr(Config, "DEEPSEEK_BATCH_SIZE", 1)
    set_llm_mode("online")

    params = get_graphiti_llm_params()
    assert params["mode"] == "online"
    assert params["provider"] == "deepseek"
    assert params["api_key"] == "sk-deepseek-test"
    assert params["model"] == "deepseek-chat"
    assert params["use_qwen3_no_think"] is False


def test_params_bailian_returns_bailian_provider(tmp_mode_file, monkeypatch):
    from app.config import Config
    monkeypatch.setattr(Config, "BAILIAN_API_KEY", "sk-bailian-test")
    monkeypatch.setattr(
        Config, "BAILIAN_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr(Config, "BAILIAN_MODEL_NAME", "qwen3.5-plus")
    monkeypatch.setattr(Config, "BAILIAN_SEMAPHORE_LIMIT", 6)
    monkeypatch.setattr(Config, "BAILIAN_BATCH_SIZE", 1)
    set_llm_mode("bailian")

    params = get_graphiti_llm_params()
    assert params["mode"] == "bailian"
    assert params["provider"] == "bailian"
    assert params["api_key"] == "sk-bailian-test"
    assert params["model"] == "qwen3.5-plus"
    assert "dashscope" in params["base_url"]
    # graph_builder handles enable_thinking=False via extra_body when it
    # sees provider=='bailian'; not handled via use_qwen3_no_think (that
    # one is for the LM-Studio /no_think chat-template marker).
    assert params["use_qwen3_no_think"] is False


def test_params_bailian_missing_key_raises(tmp_mode_file, monkeypatch):
    """If the mode file somehow says 'bailian' but the key is gone, we
    fail loudly rather than silently running some other provider."""
    from app.config import Config
    # Write mode file directly, bypass set_llm_mode's guard.
    tmp_mode_file.write_text(
        '{"mode": "bailian", "updated_at": "x", "updated_by": "direct"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(Config, "BAILIAN_API_KEY", None)
    with pytest.raises(RuntimeError, match="BAILIAN_API_KEY"):
        get_graphiti_llm_params()
