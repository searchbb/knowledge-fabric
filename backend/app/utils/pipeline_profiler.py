"""Pipeline wall-clock profiler.

Lightweight, thread-safe stage timer used to instrument the article → graph
build pipeline without changing any of its logic. Intended to answer
"where do the 30 minutes go".

Usage:

    from app.utils.pipeline_profiler import PipelineProfiler, set_profiler, stage

    profiler = PipelineProfiler(run_id="build-abc")
    set_profiler(profiler)  # attaches to the current thread
    try:
        with stage("chunk_split"):
            chunks = TextProcessor.split_text(text)
        with stage("add_text_batches", n_chunks=len(chunks)):
            ...
    finally:
        profiler.write_json(Path("profile.json"))
        profiler.print_summary()
        set_profiler(None)

Design notes:
  - When no profiler is attached to the current thread, `stage()` is a
    no-op. Zero cost. This lets us leave instrumentation in production code.
  - Thread-local binding: each build thread gets its own profiler.
  - Per-task "active stage" via ContextVar for asyncio safety: concurrent
    asyncio tasks inside a single thread each track their own stage
    correctly, so `record_llm_call()` attributes to the right stage.
  - Flat record list: we capture open/close events but don't rely on a
    stack. Each `stage()` context manager owns its record.
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass
class StageRecord:
    name: str
    chunk_id: int | None = None
    start_ts: float = 0.0
    end_ts: float = 0.0
    duration_seconds: float = 0.0
    llm_calls: int = 0
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Thread-local profiler handle. Each build thread sets its own.
_local = threading.local()

# ContextVar so concurrent asyncio tasks inside a thread track their own
# current stage. Used by record_llm_call() to attribute counts correctly.
_active_stage: ContextVar[StageRecord | None] = ContextVar(
    "pipeline_profiler_active_stage", default=None
)


def set_profiler(profiler: "PipelineProfiler | None") -> None:
    """Attach (or detach) a profiler to the current thread."""
    _local.profiler = profiler


def get_profiler() -> "PipelineProfiler | None":
    return getattr(_local, "profiler", None)


class PipelineProfiler:
    """Collects StageRecord entries from one pipeline run."""

    def __init__(self, run_id: str, *, extra: dict[str, Any] | None = None):
        self.run_id = run_id
        self.extra: dict[str, Any] = dict(extra or {})
        self._started_at: float = time.perf_counter()
        self._records: list[StageRecord] = []
        self._lock = threading.Lock()

    # ---- internal API used by the stage() context manager -----------

    def _open_stage(
        self, name: str, *, chunk_id: int | None = None, **metadata: Any
    ) -> StageRecord:
        record = StageRecord(
            name=name,
            chunk_id=chunk_id,
            start_ts=time.perf_counter(),
            metadata=dict(metadata),
        )
        return record

    def _close_stage(self, record: StageRecord) -> None:
        record.end_ts = time.perf_counter()
        record.duration_seconds = record.end_ts - record.start_ts
        with self._lock:
            self._records.append(record)

    # ---- public helpers ---------------------------------------------

    def record_llm_call(self) -> None:
        """Bump LLM counter on the current active stage (if any)."""
        record = _active_stage.get()
        if record is not None:
            record.llm_calls += 1

    @property
    def total_wall_clock_seconds(self) -> float:
        return time.perf_counter() - self._started_at

    def to_dict(self) -> dict[str, Any]:
        total = self.total_wall_clock_seconds
        # Aggregate by stage name.
        by_name: dict[str, list[StageRecord]] = {}
        for r in self._records:
            by_name.setdefault(r.name, []).append(r)

        summary: list[dict[str, Any]] = []
        for name, records in by_name.items():
            durations = [r.duration_seconds for r in records]
            summary.append(
                {
                    "stage": name,
                    "count": len(records),
                    "total_seconds": sum(durations),
                    "mean_seconds": sum(durations) / len(durations) if durations else 0.0,
                    "max_seconds": max(durations) if durations else 0.0,
                    "llm_calls": sum(r.llm_calls for r in records),
                    "success_count": sum(1 for r in records if r.success),
                    "failure_count": sum(1 for r in records if not r.success),
                    "percent_of_total": (
                        sum(durations) / total * 100.0 if total > 0 else 0.0
                    ),
                }
            )
        summary.sort(key=lambda s: s["total_seconds"], reverse=True)

        return {
            "run_id": self.run_id,
            "extra": self.extra,
            "total_wall_clock_seconds": total,
            "stage_summary": summary,
            "records": [asdict(r) for r in self._records],
        }

    def write_json(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def print_summary(self) -> None:
        data = self.to_dict()
        total = data["total_wall_clock_seconds"]
        print(f"\n=== pipeline profile: run_id={self.run_id} ===")
        print(f"total wall-clock: {total:.1f}s")
        rows = data["stage_summary"]
        if not rows:
            print("(no stages recorded)")
            return
        print(
            f"{'stage':<30} {'count':>6} {'total(s)':>10} "
            f"{'mean(s)':>9} {'max(s)':>9} {'%':>6} {'llm':>5} {'fail':>5}"
        )
        for row in rows:
            print(
                f"{row['stage']:<30} {row['count']:>6} "
                f"{row['total_seconds']:>10.2f} {row['mean_seconds']:>9.2f} "
                f"{row['max_seconds']:>9.2f} {row['percent_of_total']:>5.1f}% "
                f"{row['llm_calls']:>5} {row['failure_count']:>5}"
            )
        print()


# ----- stage context manager -----------------------------------------


class _NoOpStage:
    """Returned from stage() when no profiler is attached. Lets callers do
    `with stage('x') as s: s.metadata[...] = ...` even when disabled."""
    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {}

    # Mirror StageRecord attributes the caller might touch.
    chunk_id: int | None = None
    llm_calls: int = 0
    success: bool = True
    error: str | None = None


@contextmanager
def stage(
    name: str,
    *,
    chunk_id: int | None = None,
    **metadata: Any,
) -> Iterator[StageRecord | _NoOpStage]:
    """Record the wall-clock of a named stage. No-op when profiling is off."""
    profiler = get_profiler()
    if profiler is None:
        yield _NoOpStage()
        return
    record = profiler._open_stage(name, chunk_id=chunk_id, **metadata)
    token = _active_stage.set(record)
    try:
        yield record
    except BaseException as exc:  # noqa: BLE001 — mark failure, re-raise
        record.success = False
        record.error = f"{type(exc).__name__}: {exc}"[:300]
        raise
    finally:
        _active_stage.reset(token)
        profiler._close_stage(record)


def record_llm_call() -> None:
    """Convenience: bump LLM counter on the active stage."""
    profiler = get_profiler()
    if profiler is not None:
        profiler.record_llm_call()
