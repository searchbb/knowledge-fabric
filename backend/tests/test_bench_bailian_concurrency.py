"""Unit tests for scripts/bench_bailian_concurrency.py.

Follows the project convention of running async code via `asyncio.run()`
inside sync test functions (no pytest-asyncio markers).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure backend/scripts is importable when running under pytest from backend/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.bench_bailian_concurrency import (  # noqa: E402
    BenchConfig,
    RequestResult,
    _parse_concurrency,
    _percentile,
    aggregate_results,
    call_model_once,
    chunk_text,
    classify_error,
    load_articles,
    main,
    run_sweep,
)


# ----- chunk_text -------------------------------------------------------


def test_chunk_text_empty_input_returns_empty_list():
    assert chunk_text("", chunk_size=100, overlap=10) == []


def test_chunk_text_shorter_than_chunk_returns_single_chunk():
    assert chunk_text("hello world", chunk_size=100, overlap=10) == ["hello world"]


def test_chunk_text_exact_chunk_size_returns_single_chunk():
    text = "a" * 100
    assert chunk_text(text, chunk_size=100, overlap=10) == [text]


def test_chunk_text_splits_long_text_with_overlap():
    text = "a" * 250
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    # step = 80; starts at 0, 80, 160; last chunk runs 160..250 (90 chars)
    assert len(chunks) == 3
    assert chunks[0] == "a" * 100
    assert chunks[1] == "a" * 100  # overlapping window of 100
    assert chunks[2] == "a" * 90  # tail (160..250)


def test_chunk_text_no_duplicated_suffix_when_step_aligns():
    text = "c" * 160
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    # step=80 → starts 0,80; 80+100=180 >= 160 so break
    assert len(chunks) == 2
    assert chunks[0] == "c" * 100
    assert chunks[1] == "c" * 80


def test_chunk_text_overlap_zero_no_overlap():
    text = "b" * 200
    chunks = chunk_text(text, chunk_size=50, overlap=0)
    assert len(chunks) == 4
    assert all(len(c) == 50 for c in chunks)


def test_chunk_text_rejects_bad_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=0, overlap=0)


def test_chunk_text_rejects_negative_overlap():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=10, overlap=-1)


def test_chunk_text_rejects_overlap_ge_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("x" * 100, chunk_size=50, overlap=50)


# ----- _percentile + aggregate_results ---------------------------------


def _mk_result(latency, success=True, prompt=100, completion=40, err=None):
    return RequestResult(
        chunk_id=0, concurrency=1, mode="summary", model="qwen-plus",
        input_chars=300, start_ts=0.0, end_ts=latency, latency_seconds=latency,
        success=success, error_type=err, response_chars=120,
        prompt_tokens=prompt if success else None,
        completion_tokens=completion if success else None,
        total_tokens=(prompt + completion) if success else None,
        attempts=1,
    )


def test_percentile_single_value():
    assert _percentile([7.5], 0.95) == 7.5


def test_percentile_interpolates():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert _percentile(vals, 0.50) == 3.0
    assert 4.5 <= _percentile(vals, 0.95) <= 5.0


def test_aggregate_results_empty():
    report = aggregate_results(
        [], concurrency=4, mode="summary", model="qwen-plus",
        article_name="x.md", wall_clock=0.0,
        input_price=0.0008, output_price=0.002,
    )
    assert report.total_chunks == 0
    assert report.success_rate == 0.0
    assert report.avg_latency_seconds == 0.0
    assert report.estimated_cost_cny == 0.0


def test_aggregate_results_all_success():
    results = [_mk_result(l) for l in (1.0, 2.0, 3.0, 4.0, 5.0)]
    report = aggregate_results(
        results, concurrency=2, mode="summary", model="qwen-plus",
        article_name="x.md", wall_clock=7.5,
        input_price=0.0008, output_price=0.002,
    )
    assert report.total_chunks == 5
    assert report.success_rate == 1.0
    assert report.avg_latency_seconds == 3.0
    assert report.p50_latency_seconds == 3.0
    assert 4.5 <= report.p95_latency_seconds <= 5.0
    assert report.total_wall_clock_seconds == 7.5


def test_aggregate_results_counts_failures_and_excludes_from_latency():
    results = [
        _mk_result(1.0, success=True),
        _mk_result(0.0, success=False, err="rate_limit"),
        _mk_result(0.0, success=False, err="timeout"),
    ]
    report = aggregate_results(
        results, concurrency=1, mode="summary", model="qwen-plus",
        article_name="x.md", wall_clock=1.0,
        input_price=0.0008, output_price=0.002,
    )
    assert report.success_rate == pytest.approx(1 / 3)
    assert report.error_counts == {"rate_limit": 1, "timeout": 1}
    assert report.avg_latency_seconds == 1.0  # only successes


def test_aggregate_results_cost_uses_reported_usage():
    results = [_mk_result(1.0, prompt=1000, completion=500)]
    report = aggregate_results(
        results, concurrency=1, mode="summary", model="qwen-plus",
        article_name="x.md", wall_clock=1.0,
        input_price=0.001, output_price=0.002,
    )
    # 1000 / 1000 * 0.001 + 500 / 1000 * 0.002 = 0.001 + 0.001 = 0.002
    assert report.estimated_cost_cny == pytest.approx(0.002)


# ----- classify_error --------------------------------------------------


def test_classify_error_rate_limit_by_status_code():
    class E(Exception):
        status_code = 429
    assert classify_error(E("rate limit")) == "rate_limit"


def test_classify_error_auth_by_status_code():
    class E(Exception):
        status_code = 401
    assert classify_error(E("nope")) == "auth"


def test_classify_error_timeout_by_type():
    assert classify_error(asyncio.TimeoutError()) == "timeout"


def test_classify_error_connection_by_type():
    assert classify_error(ConnectionError("boom")) == "connection"


def test_classify_error_generic():
    assert classify_error(RuntimeError("boom")) == "other"


def test_classify_error_timeout_by_class_name():
    class APITimeoutError(Exception):
        pass
    assert classify_error(APITimeoutError()) == "timeout"


# ----- call_model_once -------------------------------------------------


class _FakeUsage:
    def __init__(self, pt, ct):
        self.prompt_tokens = pt
        self.completion_tokens = ct
        self.total_tokens = pt + ct


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content, usage):
        self.choices = [_FakeChoice(content)]
        self.usage = usage


class _FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        r = self._responses.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeAsyncClient:
    def __init__(self, completions):
        self.chat = _FakeChat(completions)


def _ok(content='{"points":["a"]}', pt=100, ct=20):
    return _FakeCompletion(content, _FakeUsage(pt, ct))


def _cfg(**overrides):
    base = dict(
        model="qwen-plus", mode="summary", concurrency=1,
        chunk_size=3000, chunk_overlap=200,
        timeout_seconds=10, max_retries=2,
        input_price_per_1k_cny=0.0008, output_price_per_1k_cny=0.002,
        base_url="", api_key="",
    )
    base.update(overrides)
    return BenchConfig(**base)


def test_call_model_once_success_records_usage():
    fake = _FakeAsyncClient(_FakeCompletions([_ok(pt=50, ct=10)]))

    async def run():
        return await call_model_once(fake, chunk_id=0, chunk="some input", cfg=_cfg())

    res = asyncio.run(run())
    assert res.success is True
    assert res.prompt_tokens == 50
    assert res.completion_tokens == 10
    assert res.total_tokens == 60
    assert res.attempts == 1
    assert res.error_type is None


def test_call_model_once_uses_char_heuristic_when_usage_missing():
    fake_completion = _FakeCompletion("short reply", usage=None)
    fake = _FakeAsyncClient(_FakeCompletions([fake_completion]))

    async def run():
        return await call_model_once(fake, chunk_id=0, chunk="a" * 250, cfg=_cfg())

    res = asyncio.run(run())
    assert res.success is True
    assert res.prompt_tokens == int(250 / 2.5)
    assert res.completion_tokens == int(len("short reply") / 2.5)


def test_call_model_once_retries_on_rate_limit_then_succeeds():
    class Rate(Exception):
        status_code = 429

    fake = _FakeAsyncClient(_FakeCompletions([Rate(), _ok()]))

    async def run():
        # shrink retry backoff for test speed via patching? No, max_retries=2 and
        # first attempt hits rate_limit; backoff is 1 + jitter so ~1-1.5s. Acceptable.
        return await call_model_once(fake, chunk_id=0, chunk="x", cfg=_cfg())

    res = asyncio.run(run())
    assert res.success is True
    assert res.attempts == 2


def test_call_model_once_gives_up_after_max_retries():
    class Rate(Exception):
        status_code = 429

    fake = _FakeAsyncClient(_FakeCompletions([Rate(), Rate(), Rate()]))

    async def run():
        return await call_model_once(fake, chunk_id=0, chunk="x",
                                      cfg=_cfg(max_retries=2))

    res = asyncio.run(run())
    assert res.success is False
    assert res.error_type == "rate_limit"
    assert res.attempts == 3  # 1 initial + 2 retries


def test_call_model_once_no_retry_on_auth_error():
    class Auth(Exception):
        status_code = 401

    fake = _FakeAsyncClient(_FakeCompletions([Auth()]))

    async def run():
        return await call_model_once(fake, chunk_id=0, chunk="x", cfg=_cfg())

    res = asyncio.run(run())
    assert res.success is False
    assert res.error_type == "auth"
    assert res.attempts == 1  # no retry on non-transient


# ----- run_sweep ------------------------------------------------------


class _SlowCompletions:
    """Fake that sleeps to simulate latency + records peak in-flight."""
    def __init__(self, per_call_seconds=0.05):
        self.per_call_seconds = per_call_seconds
        self.in_flight = 0
        self.peak_in_flight = 0
        self.calls = 0

    async def create(self, **kwargs):
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        self.calls += 1
        try:
            await asyncio.sleep(self.per_call_seconds)
            return _FakeCompletion('{"points":["x"]}', _FakeUsage(100, 20))
        finally:
            self.in_flight -= 1


def test_run_sweep_respects_concurrency_ceiling():
    comp = _SlowCompletions()
    fake = _FakeAsyncClient(comp)
    chunks = ["chunk " + str(i) for i in range(10)]
    cfg = _cfg(concurrency=3)

    async def run():
        return await run_sweep(
            fake, chunks=chunks, cfg=cfg, article_name="x.md",
            input_price=cfg.input_price_per_1k_cny,
            output_price=cfg.output_price_per_1k_cny,
        )

    report = asyncio.run(run())
    assert report.total_chunks == 10
    assert report.success_rate == 1.0
    assert comp.peak_in_flight <= 3
    assert comp.peak_in_flight >= 2  # saturate with 10 chunks + cap 3


def test_run_sweep_handles_mixed_success_failure():
    class Rate(Exception):
        status_code = 429

    # 3 ok, 1 fatal rate_limit (3 attempts all fail)
    responses = [_ok(), _ok(), _ok(), Rate(), Rate(), Rate()]
    fake = _FakeAsyncClient(_FakeCompletions(responses))
    cfg = _cfg(concurrency=1, max_retries=2)

    async def run():
        return await run_sweep(
            fake, chunks=["a", "b", "c", "d"], cfg=cfg, article_name="x.md",
            input_price=0.001, output_price=0.001,
        )

    report = asyncio.run(run())
    assert report.total_chunks == 4
    assert report.success_rate == 0.75
    assert report.error_counts == {"rate_limit": 1}


# ----- loader + CLI + main ---------------------------------------------


def test_load_articles_from_single_file(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("hello world", encoding="utf-8")
    out = load_articles(article=str(p), directory=None)
    assert out == [("a.md", "hello world")]


def test_load_articles_from_directory(tmp_path):
    (tmp_path / "a.md").write_text("aaa", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("bbb", encoding="utf-8")
    out = load_articles(article=None, directory=str(tmp_path))
    assert len(out) == 2
    names = sorted(n for n, _ in out)
    assert names == ["a.md", "sub/b.md"]


def test_load_articles_raises_without_input():
    with pytest.raises(ValueError):
        load_articles(article=None, directory=None)


def test_load_articles_raises_on_bad_file():
    with pytest.raises(FileNotFoundError):
        load_articles(article="/does/not/exist.md", directory=None)


def test_parse_concurrency_valid():
    assert _parse_concurrency("1,2,4") == [1, 2, 4]
    assert _parse_concurrency("8") == [8]


def test_parse_concurrency_rejects_zero():
    with pytest.raises(ValueError):
        _parse_concurrency("0,2")


def test_parse_concurrency_rejects_empty():
    with pytest.raises(ValueError):
        _parse_concurrency("")


def test_main_dry_run(tmp_path, capsys):
    p = tmp_path / "a.md"
    p.write_text("x" * 5000, encoding="utf-8")
    rc = main([
        "--article", str(p), "--mode", "summary",
        "--concurrency", "1,2", "--dry-run",
        "--output", str(tmp_path / "out.json"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "a.md" in out
    assert "chunks=" in out


def test_main_errors_without_api_key_and_not_dry_run(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    p = tmp_path / "a.md"
    p.write_text("short", encoding="utf-8")
    rc = main([
        "--article", str(p),
        "--concurrency", "1",
        "--output", str(tmp_path / "out.json"),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no API key" in err
