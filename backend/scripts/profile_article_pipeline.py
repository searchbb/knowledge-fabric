"""Profile a single-article graph build using the existing Flask routes.

This script:
  1. Spins up the Flask app via `create_app()` (no separate server needed).
  2. POSTs the .md to /api/graph/ontology/generate to create a project + ontology.
  3. POSTs to /api/graph/build to start the build.
  4. Polls /api/graph/task/{task_id} until COMPLETED / FAILED / CANCELLED.
  5. Reads the wall-clock profile JSON the build thread wrote, prints a summary.

Requires:
  - Neo4j running (NEO4J_URI etc. configured in .env)
  - LLM creds in env / .env (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME, or the
    Bailian/DeepSeek equivalents the project supports)

The build pipeline is instrumented in app/api/graph.py via the
PipelineProfiler context manager. Profiling activates when PROFILE_BUILD_OUT
is set in the environment — this script sets it before importing the app so
the build thread picks it up.

Usage:

    cd backend
    LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL_NAME=qwen-plus \\
        uv run python scripts/profile_article_pipeline.py \\
            --article uploads/projects/proj_XXX/files/YYY.md \\
            --output ./pipeline_profile.json \\
            --simulation-requirement "测试用，剖析端到端耗时"
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

# Add backend/ to sys.path so `from app import ...` works under uv run python.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Profile end-to-end article-to-graph build pipeline."
    )
    p.add_argument("--article", required=True, help="Path to a .md file to process.")
    p.add_argument(
        "--output",
        default="pipeline_profile.json",
        help="Path to write profile JSON (build thread also writes to this file).",
    )
    p.add_argument(
        "--simulation-requirement",
        default="profile run: end-to-end timing instrumentation",
        help="Required by /ontology/generate; explains what the project is for.",
    )
    p.add_argument(
        "--project-name",
        default=None,
        help="Project name; defaults to the article filename stem.",
    )
    p.add_argument(
        "--chunk-size", type=int, default=None,
        help="Override chunk_size (defaults to project/Config defaults).",
    )
    p.add_argument(
        "--chunk-overlap", type=int, default=None,
        help="Override chunk_overlap.",
    )
    p.add_argument(
        "--poll-interval", type=float, default=2.0,
        help="Seconds between task polls (default: 2.0).",
    )
    p.add_argument(
        "--timeout", type=int, default=2700,
        help="Max seconds to wait for build completion (default: 2700 = 45 min).",
    )
    return p


def _post_ontology(client, *, article_path: Path, project_name: str,
                   simulation_requirement: str) -> str:
    """POST the article to /api/graph/ontology/generate.

    Werkzeug's test client wants files passed via the `data` mapping with a
    tuple value: data={"files": (BytesIO, "name.md")}.
    """
    with open(article_path, "rb") as f:
        content = f.read()
    data = {
        "project_name": project_name,
        "simulation_requirement": simulation_requirement,
        "files": (io.BytesIO(content), article_path.name),
    }
    resp = client.post(
        "/api/graph/ontology/generate",
        data=data,
        content_type="multipart/form-data",
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"ontology/generate failed: {resp.status_code} "
            f"{resp.get_data(as_text=True)[:500]}"
        )
    payload = resp.get_json()
    if not payload or not payload.get("success"):
        raise RuntimeError(f"ontology/generate non-success: {payload}")
    return payload["data"]["project_id"]


def _post_build(client, *, project_id: str, chunk_size: int | None,
                chunk_overlap: int | None) -> str:
    body: dict = {"project_id": project_id}
    if chunk_size is not None:
        body["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        body["chunk_overlap"] = chunk_overlap
    resp = client.post("/api/graph/build", json=body)
    if resp.status_code != 200:
        raise RuntimeError(
            f"build failed: {resp.status_code} {resp.get_data(as_text=True)[:500]}"
        )
    payload = resp.get_json()
    if not payload or not payload.get("success"):
        raise RuntimeError(f"build non-success: {payload}")
    return payload["data"]["task_id"]


def _poll_task(client, task_id: str, *, poll_interval: float, timeout: int) -> dict:
    deadline = time.time() + timeout
    last_progress = -1
    last_message = ""
    while time.time() < deadline:
        resp = client.get(f"/api/graph/task/{task_id}")
        if resp.status_code != 200:
            time.sleep(poll_interval)
            continue
        payload = resp.get_json() or {}
        task = (payload.get("data") or {})
        status = task.get("status")
        progress = task.get("progress", 0)
        message = task.get("message", "")
        if progress != last_progress or message != last_message:
            print(f"  [{progress:3d}%] {status:<10} {message}", flush=True)
            last_progress = progress
            last_message = message
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            return task
        time.sleep(poll_interval)
    raise TimeoutError(f"task {task_id} did not complete within {timeout}s")


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    article_path = Path(args.article).resolve()
    if not article_path.is_file():
        print(f"error: article not found: {article_path}", file=sys.stderr)
        return 2

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    project_name = args.project_name or article_path.stem

    # Set BEFORE importing the app so the build thread picks it up.
    os.environ["PROFILE_BUILD_OUT"] = str(output_path)

    # Lazy import after env is set.
    from app import create_app  # noqa: E402

    app = create_app()
    app.testing = True
    client = app.test_client()

    print(f"profiling: article={article_path}")
    print(f"output:    {output_path}")
    print(f"project:   {project_name}")

    print("\n[1/3] generating ontology...")
    t0 = time.perf_counter()
    project_id = _post_ontology(
        client,
        article_path=article_path,
        project_name=project_name,
        simulation_requirement=args.simulation_requirement,
    )
    t1 = time.perf_counter()
    print(f"  project_id={project_id}  ({t1 - t0:.1f}s)")

    print("\n[2/3] starting build...")
    task_id = _post_build(
        client,
        project_id=project_id,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(f"  task_id={task_id}")

    print(f"\n[3/3] polling task (interval={args.poll_interval}s, timeout={args.timeout}s)...")
    final = _poll_task(
        client, task_id, poll_interval=args.poll_interval, timeout=args.timeout
    )
    elapsed = time.perf_counter() - t1
    print(f"\nbuild finished: status={final.get('status')}  elapsed={elapsed:.1f}s")

    # Build thread writes the profile inside its `finally`. Wait briefly for it
    # to flush in case the task transitioned to COMPLETED before the file hit disk.
    deadline = time.time() + 5.0
    while not output_path.exists() and time.time() < deadline:
        time.sleep(0.2)

    if not output_path.exists():
        print(
            f"warning: profile file not written at {output_path}.\n"
            "Likely the build crashed before instrumentation flushed, or the\n"
            "process re-imported app.api.graph fresh and the env var didn't\n"
            "propagate. Check backend logs.",
            file=sys.stderr,
        )
        return 1

    profile = json.loads(output_path.read_text(encoding="utf-8"))
    _print_profile_summary(profile)
    return 0 if final.get("status") == "COMPLETED" else 1


def _print_profile_summary(profile: dict) -> None:
    print("\n" + "=" * 70)
    print(f"profile run_id: {profile.get('run_id')}")
    print(f"total wall-clock: {profile.get('total_wall_clock_seconds', 0):.1f}s")
    extra = profile.get("extra") or {}
    if extra:
        print(f"extra: {extra}")
    print("\nstages (sorted by total_seconds desc):")
    print(
        f"  {'stage':<30} {'count':>5} {'total(s)':>10} "
        f"{'mean(s)':>9} {'max(s)':>9} {'%':>6} {'llm':>4} {'fail':>4}"
    )
    for row in profile.get("stage_summary", []):
        print(
            f"  {row['stage']:<30} {row['count']:>5} "
            f"{row['total_seconds']:>10.2f} {row['mean_seconds']:>9.2f} "
            f"{row['max_seconds']:>9.2f} {row['percent_of_total']:>5.1f}% "
            f"{row['llm_calls']:>4} {row['failure_count']:>4}"
        )
    print("\ntop 3 by total_seconds:")
    for row in profile.get("stage_summary", [])[:3]:
        pct = row["percent_of_total"]
        print(f"  {row['stage']:<30} {row['total_seconds']:>8.1f}s  ({pct:.1f}% of total)")


if __name__ == "__main__":
    raise SystemExit(main())
