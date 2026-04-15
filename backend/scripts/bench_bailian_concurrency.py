"""Bailian (DashScope) concurrency benchmark.

Measures wall-clock, p50/p95 latency, success rate, token usage, and
estimated CNY cost when calling an OpenAI-compatible endpoint (default:
DashScope) at different concurrency levels, using real markdown articles
as input.

Not wired into the production pipeline. Run standalone:

    cd backend
    uv run python scripts/bench_bailian_concurrency.py \\
        --article uploads/projects/proj_XXXX/files/YYYY.md \\
        --concurrency 1,2,4 --mode summary

Env vars (CLI flags override):
    OPENAI_API_KEY / LLM_API_KEY    - API key
    OPENAI_BASE_URL / LLM_BASE_URL  - base URL (default: DashScope compat endpoint)
    BAILIAN_MODEL   / LLM_MODEL_NAME - model id (default: qwen-plus)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Default qwen-plus pricing in CNY per 1K tokens (as of 2026-04; override via CLI).
DEFAULT_INPUT_PRICE_PER_1K_CNY = 0.0008
DEFAULT_OUTPUT_PRICE_PER_1K_CNY = 0.002

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"
DEFAULT_CHUNK_SIZE = 3000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_MAX_RETRIES = 2
# Rough zh/en mix; only used when usage info is missing from the response.
CHARS_PER_TOKEN_HEURISTIC = 2.5


# -------------------------------------------------------------------
# Chunker
# -------------------------------------------------------------------


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Character-based sliding-window chunker.

    Deliberately simple and structure-agnostic so benchmark results are
    reproducible. Does NOT inject section prefixes — that's the production
    chunker's job; injecting them here would skew token counts.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += step
    return chunks


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------


@dataclass
class BenchConfig:
    model: str
    mode: str  # "summary" | "entity" | "edge"
    concurrency: int
    chunk_size: int
    chunk_overlap: int
    timeout_seconds: int
    max_retries: int
    input_price_per_1k_cny: float
    output_price_per_1k_cny: float
    base_url: str
    api_key: str


@dataclass
class RequestResult:
    chunk_id: int
    concurrency: int
    mode: str
    model: str
    input_chars: int
    start_ts: float
    end_ts: float
    latency_seconds: float
    success: bool
    error_type: str | None
    response_chars: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    attempts: int


@dataclass
class SweepReport:
    article_name: str
    mode: str
    model: str
    concurrency: int
    total_chunks: int
    total_wall_clock_seconds: float
    avg_latency_seconds: float
    p50_latency_seconds: float
    p95_latency_seconds: float
    success_rate: float
    error_counts: dict[str, int]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_cny: float
    input_price_per_1k_cny: float
    output_price_per_1k_cny: float
    results: list[RequestResult] = field(default_factory=list)


# -------------------------------------------------------------------
# Aggregation helpers
# -------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (NIST method, same as numpy default)."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def aggregate_results(
    results: list[RequestResult],
    *,
    concurrency: int,
    mode: str,
    model: str,
    article_name: str,
    wall_clock: float,
    input_price: float,
    output_price: float,
) -> SweepReport:
    successes = [r for r in results if r.success]
    latencies = [r.latency_seconds for r in successes]
    prompt_tokens = sum((r.prompt_tokens or 0) for r in successes)
    completion_tokens = sum((r.completion_tokens or 0) for r in successes)
    total_tokens = sum((r.total_tokens or 0) for r in successes)
    error_counts: dict[str, int] = {}
    for r in results:
        if not r.success and r.error_type:
            error_counts[r.error_type] = error_counts.get(r.error_type, 0) + 1
    cost = (
        prompt_tokens / 1000.0 * input_price
        + completion_tokens / 1000.0 * output_price
    )
    return SweepReport(
        article_name=article_name,
        mode=mode,
        model=model,
        concurrency=concurrency,
        total_chunks=len(results),
        total_wall_clock_seconds=wall_clock,
        avg_latency_seconds=statistics.mean(latencies) if latencies else 0.0,
        p50_latency_seconds=_percentile(latencies, 0.50),
        p95_latency_seconds=_percentile(latencies, 0.95),
        success_rate=len(successes) / len(results) if results else 0.0,
        error_counts=error_counts,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_cny=cost,
        input_price_per_1k_cny=input_price,
        output_price_per_1k_cny=output_price,
        results=results,
    )


# -------------------------------------------------------------------
# Prompts + error classification + model call
# -------------------------------------------------------------------


SUMMARY_PROMPT = (
    "你是一个技术文章要点提取助手。读下面这段内容，用 3-5 条要点总结。"
    "严格输出 JSON：{\"points\": [\"...\"]}。只输出 JSON，不要前后缀。"
)

ENTITY_PROMPT = (
    "你是一个实体抽取助手。从下面文本抽取关键实体，严格输出 JSON："
    "{\"entities\":[{\"name\":\"...\",\"type\":\"concept|person|org|product|other\"}]}。"
    "只输出 JSON，不要前后缀。"
)

EDGE_PROMPT = (
    "你是一个关系抽取助手。从下面文本抽取 subject-predicate-object 三元组，严格输出 JSON："
    "{\"triples\":[{\"subject\":\"...\",\"predicate\":\"...\",\"object\":\"...\"}]}。"
    "只输出 JSON，不要前后缀。"
)

_PROMPTS = {"summary": SUMMARY_PROMPT, "entity": ENTITY_PROMPT, "edge": EDGE_PROMPT}


def classify_error(exc: BaseException) -> str:
    """Bucket an exception into a coarse error class for reporting."""
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "auth"
    if isinstance(exc, (ConnectionError, OSError)):
        return "connection"
    name = exc.__class__.__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "ratelimit" in name or "rate_limit" in name:
        return "rate_limit"
    if "connection" in name or "apiconn" in name:
        return "connection"
    return "other"


async def call_model_once(
    client: Any,
    *,
    chunk_id: int,
    chunk: str,
    cfg: BenchConfig,
) -> RequestResult:
    """Call the chat completions API once, with bounded retry on transient errors."""
    system_prompt = _PROMPTS[cfg.mode]
    want_json = cfg.mode in ("summary", "entity", "edge")
    kwargs: dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chunk},
        ],
        "temperature": 0.0,
    }
    if want_json:
        kwargs["response_format"] = {"type": "json_object"}

    attempts = 0
    start = time.perf_counter()
    last_error: BaseException | None = None
    while attempts <= cfg.max_retries:
        attempts += 1
        try:
            completion = await asyncio.wait_for(
                client.chat.completions.create(**kwargs),
                timeout=cfg.timeout_seconds,
            )
            end = time.perf_counter()
            choices = getattr(completion, "choices", None) or []
            content = ""
            if choices:
                msg = getattr(choices[0], "message", None)
                content = (getattr(msg, "content", "") or "") if msg else ""
            usage = getattr(completion, "usage", None)
            pt = getattr(usage, "prompt_tokens", None) if usage else None
            ct = getattr(usage, "completion_tokens", None) if usage else None
            tt = getattr(usage, "total_tokens", None) if usage else None
            if pt is None:
                pt = int(len(chunk) / CHARS_PER_TOKEN_HEURISTIC)
            if ct is None:
                ct = int(len(content) / CHARS_PER_TOKEN_HEURISTIC)
            if tt is None:
                tt = pt + ct
            return RequestResult(
                chunk_id=chunk_id, concurrency=cfg.concurrency, mode=cfg.mode,
                model=cfg.model, input_chars=len(chunk),
                start_ts=start, end_ts=end, latency_seconds=end - start,
                success=True, error_type=None, response_chars=len(content),
                prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
                attempts=attempts,
            )
        except BaseException as exc:  # noqa: BLE001
            last_error = exc
            kind = classify_error(exc)
            # Retry only transient classes.
            if kind not in ("rate_limit", "timeout", "connection"):
                break
            if attempts > cfg.max_retries:
                break
            delay = min(8.0, 2 ** (attempts - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    end = time.perf_counter()
    return RequestResult(
        chunk_id=chunk_id, concurrency=cfg.concurrency, mode=cfg.mode,
        model=cfg.model, input_chars=len(chunk),
        start_ts=start, end_ts=end, latency_seconds=end - start,
        success=False,
        error_type=classify_error(last_error) if last_error else "other",
        response_chars=0, prompt_tokens=None, completion_tokens=None, total_tokens=None,
        attempts=attempts,
    )


# -------------------------------------------------------------------
# Concurrency orchestrator
# -------------------------------------------------------------------


async def run_sweep(
    client: Any,
    *,
    chunks: list[str],
    cfg: BenchConfig,
    article_name: str,
    input_price: float,
    output_price: float,
) -> SweepReport:
    """Run all chunks under a capped concurrency, return aggregated report."""
    semaphore = asyncio.Semaphore(cfg.concurrency)

    async def worker(idx: int, chunk: str) -> RequestResult:
        async with semaphore:
            return await call_model_once(client, chunk_id=idx, chunk=chunk, cfg=cfg)

    wall_start = time.perf_counter()
    results = await asyncio.gather(
        *(worker(i, c) for i, c in enumerate(chunks))
    )
    wall_clock = time.perf_counter() - wall_start
    return aggregate_results(
        list(results),
        concurrency=cfg.concurrency,
        mode=cfg.mode,
        model=cfg.model,
        article_name=article_name,
        wall_clock=wall_clock,
        input_price=input_price,
        output_price=output_price,
    )


# -------------------------------------------------------------------
# Corpus loader + CLI + reporter
# -------------------------------------------------------------------


def load_articles(*, article: str | None, directory: str | None) -> list[tuple[str, str]]:
    """Return list of (name, text). Raises on empty/invalid input."""
    out: list[tuple[str, str]] = []
    if article:
        p = Path(article)
        if not p.is_file():
            raise FileNotFoundError(f"article not found: {article}")
        out.append((p.name, p.read_text(encoding="utf-8")))
    if directory:
        d = Path(directory)
        if not d.is_dir():
            raise NotADirectoryError(f"not a directory: {directory}")
        for p in sorted(d.rglob("*.md")):
            out.append((str(p.relative_to(d)), p.read_text(encoding="utf-8")))
    if not out:
        raise ValueError("no articles loaded; pass --article or --dir")
    return out


def _resolve_credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    api_key = (
        args.api_key
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or ""
    )
    base_url = (
        args.base_url
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or DEFAULT_BASE_URL
    )
    model = (
        args.model
        or os.environ.get("BAILIAN_MODEL")
        or os.environ.get("LLM_MODEL_NAME")
        or DEFAULT_MODEL
    )
    return api_key, base_url, model


def _parse_concurrency(raw: str) -> list[int]:
    values = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not values or any(v < 1 for v in values):
        raise ValueError("--concurrency must be a comma-separated list of positive ints")
    return values


def _print_report_row(r: SweepReport) -> None:
    print(
        f"article={r.article_name}  mode={r.mode}  model={r.model}  concurrency={r.concurrency}\n"
        f"  chunks={r.total_chunks}  wall_clock={r.total_wall_clock_seconds:.1f}s  "
        f"avg={r.avg_latency_seconds:.1f}s  p50={r.p50_latency_seconds:.1f}s  "
        f"p95={r.p95_latency_seconds:.1f}s\n"
        f"  success_rate={r.success_rate * 100:.1f}%  errors={r.error_counts}\n"
        f"  prompt_tokens={r.prompt_tokens}  completion_tokens={r.completion_tokens}  "
        f"estimated_cost_cny={r.estimated_cost_cny:.4f}\n"
    )


def _write_json_report(path: Path, reports: list[SweepReport]) -> None:
    payload = [asdict(r) for r in reports]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Bailian/DashScope concurrency benchmark (standalone, not wired into main pipeline)."
    )
    src = p.add_argument_group("corpus")
    src.add_argument("--article", help="Path to a single .md file")
    src.add_argument("--dir", help="Directory to walk recursively for .md files")

    p.add_argument("--model",
                   help="Model ID (defaults to $BAILIAN_MODEL / $LLM_MODEL_NAME / qwen-plus)")
    p.add_argument("--mode", choices=("summary", "entity", "edge"), default="summary")
    p.add_argument("--concurrency", default="1,2,4",
                   help="Comma-separated concurrency levels to sweep (default: 1,2,4)")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    p.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    p.add_argument("--repeat", type=int, default=1,
                   help="Run each sweep this many times (each run appended to the report).")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    p.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    p.add_argument("--input-price-per-1k", type=float,
                   default=DEFAULT_INPUT_PRICE_PER_1K_CNY,
                   help="CNY per 1K prompt tokens (default is qwen-plus pricing)")
    p.add_argument("--output-price-per-1k", type=float,
                   default=DEFAULT_OUTPUT_PRICE_PER_1K_CNY)
    p.add_argument("--api-key", help="Overrides $OPENAI_API_KEY / $LLM_API_KEY")
    p.add_argument("--base-url", help="Overrides $OPENAI_BASE_URL / $LLM_BASE_URL")
    p.add_argument("--output", default="bench_results.json",
                   help="Path to write JSON report")
    p.add_argument("--dry-run", action="store_true",
                   help="Load and chunk articles, print plan, do NOT call the model.")
    return p


async def _async_main(args: argparse.Namespace) -> int:
    api_key, base_url, model = _resolve_credentials(args)
    articles = load_articles(article=args.article, directory=args.dir)
    concurrency_levels = _parse_concurrency(args.concurrency)

    # chunk up-front so chunk counts are deterministic across sweeps
    chunked: list[tuple[str, list[str]]] = []
    for name, text in articles:
        chunks = chunk_text(text, chunk_size=args.chunk_size, overlap=args.chunk_overlap)
        chunked.append((name, chunks))

    if args.dry_run:
        print("[dry-run] loaded articles (name, n_chunks, total_chars):")
        for name, chunks in chunked:
            print(f"  {name}  chunks={len(chunks)}  chars={sum(len(c) for c in chunks)}")
        print(
            f"[dry-run] concurrency sweep: {concurrency_levels}  "
            f"mode={args.mode}  model={model}  base_url={base_url}"
        )
        return 0

    if not api_key:
        print(
            "error: no API key. set OPENAI_API_KEY or LLM_API_KEY, or pass --api-key.",
            file=sys.stderr,
        )
        return 2

    from openai import AsyncOpenAI  # local import so --dry-run works without the dep
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    all_reports: list[SweepReport] = []
    try:
        for concurrency in concurrency_levels:
            for repeat_i in range(args.repeat):
                for name, chunks in chunked:
                    cfg = BenchConfig(
                        model=model, mode=args.mode, concurrency=concurrency,
                        chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
                        timeout_seconds=args.timeout, max_retries=args.max_retries,
                        input_price_per_1k_cny=args.input_price_per_1k,
                        output_price_per_1k_cny=args.output_price_per_1k,
                        base_url=base_url, api_key=api_key,
                    )
                    print(
                        f"\n[sweep] article={name} mode={args.mode} model={model} "
                        f"concurrency={concurrency} chunks={len(chunks)} "
                        f"repeat={repeat_i + 1}/{args.repeat}"
                    )
                    report = await run_sweep(
                        client, chunks=chunks, cfg=cfg, article_name=name,
                        input_price=args.input_price_per_1k,
                        output_price=args.output_price_per_1k,
                    )
                    _print_report_row(report)
                    all_reports.append(report)
    finally:
        await client.close()

    out_path = Path(args.output)
    _write_json_report(out_path, all_reports)
    print(f"\nwrote {len(all_reports)} sweep report(s) → {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
