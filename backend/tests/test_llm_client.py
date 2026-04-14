from types import SimpleNamespace

from pydantic import BaseModel

from app.utils.llm_client import (
    LLMClient,
    build_structured_json_response_format,
    is_local_openai_compatible_base_url,
)
from app.utils.upstream_errors import (
    UpstreamErrorKind,
    classify_upstream_error,
    is_adaptive_split_candidate,
    is_context_overflow_error,
)


def make_llm_client(fake_client, max_retries: int = 2) -> LLMClient:
    client = LLMClient.__new__(LLMClient)
    client.api_key = "test-key"
    client.base_url = "https://example.invalid/v1"
    client.model = "test-model"
    client.timeout_seconds = 123
    client.client = fake_client
    client.max_retries = max_retries
    return client


def test_classify_upstream_error_detects_common_categories():
    assert classify_upstream_error(RuntimeError("429 usage limit exceeded")) == UpstreamErrorKind.RATE_LIMIT
    assert classify_upstream_error(RuntimeError("503 service unavailable")) == UpstreamErrorKind.TRANSIENT
    assert classify_upstream_error(RuntimeError("authentication failed")) == UpstreamErrorKind.FATAL
    assert classify_upstream_error(RuntimeError("something odd")) == UpstreamErrorKind.UNKNOWN


def test_context_overflow_is_split_candidate_but_not_retryable():
    exc = RuntimeError("400 Context size has been exceeded.")

    assert classify_upstream_error(exc) == UpstreamErrorKind.FATAL
    assert is_context_overflow_error(exc) is True
    assert is_adaptive_split_candidate(exc, UpstreamErrorKind.FATAL) is True


def test_llama_cpp_context_overflow_is_also_split_candidate():
    exc = RuntimeError(
        "The number of tokens to keep from the initial prompt is greater than the context length (n_keep: 4843>= n_ctx: 4096)."
    )

    assert is_context_overflow_error(exc) is True
    assert is_adaptive_split_candidate(exc, UpstreamErrorKind.UNKNOWN) is True


def test_llm_client_chat_retries_rate_limit_then_succeeds(monkeypatch):
    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("429 usage limit exceeded")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="<think>ignore</think>{\"ok\":true}"))]
            )

    completions = FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client = make_llm_client(fake_client)

    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleep_calls.append(seconds))

    text = client.chat([{"role": "user", "content": "hello"}], response_format={"type": "json_object"})

    assert text == "{\"ok\":true}"
    assert completions.calls == 3
    assert sleep_calls == [2.0, 5.0]


def test_llm_client_chat_passes_timeout_to_openai_create():
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = make_llm_client(fake_client)

    assert client.chat([{"role": "user", "content": "hello"}]) == "ok"
    assert captured_kwargs["timeout"] == 123


def test_llm_client_chat_raises_after_retryable_errors_are_exhausted(monkeypatch):
    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            raise RuntimeError("429 usage limit exceeded")

    completions = FakeCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client = make_llm_client(fake_client)

    monkeypatch.setattr("time.sleep", lambda seconds: None)

    try:
        client.chat([{"role": "user", "content": "hello"}])
    except RuntimeError as exc:
        assert "429" in str(exc)
    else:
        raise AssertionError("expected retry exhaustion to raise")

    assert completions.calls == 3


def test_local_openai_compatible_base_url_detection():
    assert is_local_openai_compatible_base_url("http://127.0.0.1:1234/v1") is True
    assert is_local_openai_compatible_base_url("http://localhost:8000/v1") is True
    assert is_local_openai_compatible_base_url("https://api.minimaxi.com/v1") is False


def test_build_structured_json_response_format_prefers_json_schema_for_local():
    class DemoSchema(BaseModel):
        title: str
        summary: str

    response_format = build_structured_json_response_format(
        "http://127.0.0.1:1234/v1",
        response_model=DemoSchema,
    )

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "DemoSchema"


def test_build_structured_json_response_format_uses_generic_schema_without_model():
    response_format = build_structured_json_response_format("http://127.0.0.1:1234/v1")

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"]["type"] == "object"
    assert response_format["json_schema"]["schema"]["additionalProperties"] is True


def test_llm_client_chat_rewrites_json_object_to_json_schema_for_local_base_url():
    captured_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = make_llm_client(fake_client)
    client.base_url = "http://127.0.0.1:1234/v1"

    result = client.chat_json([{"role": "user", "content": "test"}])

    assert result == {"ok": True}
    assert captured_kwargs["response_format"]["type"] == "json_schema"


def test_chat_json_repairs_truncated_json():
    """chat_json should use json_repair to fix truncated JSON (missing closing brace)."""
    try:
        import json_repair  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("json_repair not installed")

    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true'))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = make_llm_client(fake_client)

    result = client.chat_json([{"role": "user", "content": "test"}])
    assert result == {"ok": True}


def test_chat_json_raises_on_unparseable():
    """chat_json should raise ValueError when input is completely unparseable."""
    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not json at all"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = make_llm_client(fake_client)

    import pytest
    with pytest.raises(ValueError, match="JSON格式无效"):
        client.chat_json([{"role": "user", "content": "test"}])
