"""
上游 LLM / API 错误分类工具

phase-1 只区分最少几类错误，用于：
- retry / backoff
- fail-fast
- 任务诊断
"""

from __future__ import annotations

from enum import Enum


class UpstreamErrorKind(str, Enum):
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    FATAL = "fatal"
    UNKNOWN = "unknown"


RATE_LIMIT_MARKERS = (
    "429",
    "rate limit",
    "too many requests",
    "quota exceeded",
    "usage limit exceeded",
    "insufficient_quota",
)

TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "temporary",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
    "connection error",
    "api connection",
    "service unavailable",
    "internal server error",
    "bad gateway",
    "gateway timeout",
    "502",
    # 503 Service Unavailable — DeepSeek official docs call this SERVER_OVERLOADED,
    # which is transient and should retry with backoff.
    "503",
    "504",
    "server_overloaded",
    "overloaded",
    "server busy",
)

FATAL_MARKERS = (
    "invalid_request_error",
    "invalid request",
    "maximum context length",
    "context length exceeded",
    "context size has been exceeded",
    "response_format",
    "unsupported",
    "authentication",
    "api key",
    "permission denied",
    "not authorized",
    "forbidden",
    "401",
    "403",
    # DeepSeek-specific fatal codes (from their public error doc):
    #   400 Invalid request body
    #   402 Insufficient balance (余额不足)  -> user has to go top up, no retry
    #   422 Invalid parameters               -> prompt/schema bug, no retry
    "402",
    "422",
    "insufficient balance",
    "invalid parameter",
    "invalid_parameters",
)

CONTEXT_OVERFLOW_MARKERS = (
    "maximum context length",
    "context length exceeded",
    "context size has been exceeded",
    "greater than the context length",
    "n_keep",
    "n_ctx",
    "prompt is too long",
    "too many tokens",
)


def classify_upstream_error(exc: Exception) -> UpstreamErrorKind:
    """基于异常名和消息做最小分类。"""
    text = f"{type(exc).__name__}: {exc}".lower()

    if any(marker in text for marker in RATE_LIMIT_MARKERS):
        return UpstreamErrorKind.RATE_LIMIT
    if any(marker in text for marker in TRANSIENT_MARKERS):
        return UpstreamErrorKind.TRANSIENT
    if any(marker in text for marker in FATAL_MARKERS):
        return UpstreamErrorKind.FATAL
    return UpstreamErrorKind.UNKNOWN


def is_context_overflow_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in CONTEXT_OVERFLOW_MARKERS)


def is_retryable_upstream_error(kind: UpstreamErrorKind) -> bool:
    return kind in {UpstreamErrorKind.RATE_LIMIT, UpstreamErrorKind.TRANSIENT}


def is_adaptive_split_candidate(exc: Exception, kind: UpstreamErrorKind) -> bool:
    return kind == UpstreamErrorKind.TRANSIENT or is_context_overflow_error(exc)


def compute_retry_delay(attempt: int) -> float:
    """
    返回简短的指数退避秒数。

    attempt 从 0 开始，表示第一次重试。
    """
    delays = (2.0, 5.0, 10.0)
    if attempt < 0:
        attempt = 0
    if attempt >= len(delays):
        return delays[-1]
    return delays[attempt]
