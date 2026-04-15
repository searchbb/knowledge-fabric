"""Tests for app/utils/pipeline_profiler.py."""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.pipeline_profiler import (  # noqa: E402
    PipelineProfiler,
    StageRecord,
    get_profiler,
    record_llm_call,
    set_profiler,
    stage,
)


@pytest.fixture(autouse=True)
def _reset_profiler():
    """Ensure each test starts with no profiler attached to this thread."""
    set_profiler(None)
    yield
    set_profiler(None)


# ----- stage() no-op path --------------------------------------------


def test_stage_is_noop_when_no_profiler_attached():
    # no set_profiler() → must be silent no-op
    with stage("foo"):
        pass
    assert get_profiler() is None  # still nothing attached


def test_record_llm_call_is_noop_when_no_profiler():
    # must not raise or explode
    record_llm_call()


# ----- basic profiler behavior ---------------------------------------


def test_profiler_records_single_stage_duration():
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    with stage("chunk_split"):
        time.sleep(0.01)
    data = p.to_dict()
    assert len(data["records"]) == 1
    r = data["records"][0]
    assert r["name"] == "chunk_split"
    assert r["success"] is True
    assert r["duration_seconds"] >= 0.01


def test_profiler_marks_failure_on_exception():
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    with pytest.raises(ValueError):
        with stage("boom"):
            raise ValueError("x")
    data = p.to_dict()
    assert len(data["records"]) == 1
    r = data["records"][0]
    assert r["success"] is False
    assert "ValueError" in r["error"]


def test_profiler_aggregates_stage_by_name():
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    for _ in range(3):
        with stage("entity_extract"):
            time.sleep(0.001)
    with stage("prune_edges"):
        time.sleep(0.05)  # clearly larger than 3 × 1ms above
    data = p.to_dict()
    entity = next(s for s in data["stage_summary"] if s["stage"] == "entity_extract")
    prune = next(s for s in data["stage_summary"] if s["stage"] == "prune_edges")
    assert entity["count"] == 3
    assert prune["count"] == 1
    # sorted by total_seconds desc: 50ms > 3ms
    assert data["stage_summary"][0]["stage"] == "prune_edges"


def test_profiler_metadata_is_captured():
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    with stage("chunk_entity", chunk_id=3, batch_size=2):
        pass
    r = p.to_dict()["records"][0]
    assert r["chunk_id"] == 3
    assert r["metadata"] == {"batch_size": 2}


# ----- LLM call counting --------------------------------------------


def test_record_llm_call_attributes_to_active_stage():
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    with stage("entity_extract"):
        record_llm_call()
        record_llm_call()
    with stage("prune_edges"):
        record_llm_call()
    summary = {s["stage"]: s for s in p.to_dict()["stage_summary"]}
    assert summary["entity_extract"]["llm_calls"] == 2
    assert summary["prune_edges"]["llm_calls"] == 1


def test_llm_calls_do_not_leak_across_nested_stages():
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    with stage("outer"):
        record_llm_call()  # → outer
        with stage("inner"):
            record_llm_call()  # → inner
        record_llm_call()  # → outer again
    summary = {s["stage"]: s for s in p.to_dict()["stage_summary"]}
    assert summary["outer"]["llm_calls"] == 2
    assert summary["inner"]["llm_calls"] == 1


# ----- asyncio isolation --------------------------------------------


def test_stage_tracking_isolates_concurrent_asyncio_tasks():
    """Two concurrent tasks each in their own stage should count their own
    LLM calls correctly, not mix them up."""
    p = PipelineProfiler(run_id="t")
    set_profiler(p)

    async def task(name: str, n_calls: int):
        with stage(name):
            for _ in range(n_calls):
                await asyncio.sleep(0.001)
                record_llm_call()

    async def main():
        await asyncio.gather(task("a", 3), task("b", 5))

    asyncio.run(main())
    summary = {s["stage"]: s for s in p.to_dict()["stage_summary"]}
    assert summary["a"]["llm_calls"] == 3
    assert summary["b"]["llm_calls"] == 5


# ----- thread isolation --------------------------------------------


def test_thread_local_profiler_isolation():
    """A profiler attached in one thread must not be visible from another."""
    results: dict[str, PipelineProfiler | None] = {}

    def worker():
        results["worker_initial"] = get_profiler()
        p = PipelineProfiler(run_id="worker")
        set_profiler(p)
        with stage("worker_stage"):
            pass
        results["worker_final"] = get_profiler()

    main_profiler = PipelineProfiler(run_id="main")
    set_profiler(main_profiler)
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    set_profiler(None)

    # Worker thread started with no profiler (thread-local).
    assert results["worker_initial"] is None
    # Main thread's profiler has no records from the worker.
    assert len(main_profiler.to_dict()["records"]) == 0


# ----- report writing -----------------------------------------------


def test_write_json_produces_valid_file(tmp_path):
    p = PipelineProfiler(run_id="t", extra={"article": "a.md"})
    set_profiler(p)
    with stage("stage_a"):
        time.sleep(0.001)
    out = tmp_path / "nested" / "profile.json"
    p.write_json(out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run_id"] == "t"
    assert data["extra"] == {"article": "a.md"}
    assert data["stage_summary"][0]["stage"] == "stage_a"
    assert "records" in data


def test_print_summary_handles_empty_profiler(capsys):
    p = PipelineProfiler(run_id="t")
    p.print_summary()
    out = capsys.readouterr().out
    assert "no stages recorded" in out


def test_print_summary_lists_stages_sorted_by_total(capsys):
    p = PipelineProfiler(run_id="t")
    set_profiler(p)
    with stage("slow"):
        time.sleep(0.01)
    with stage("fast"):
        time.sleep(0.001)
    p.print_summary()
    out = capsys.readouterr().out
    slow_idx = out.index("slow")
    fast_idx = out.index("fast")
    assert slow_idx < fast_idx  # "slow" should appear first
