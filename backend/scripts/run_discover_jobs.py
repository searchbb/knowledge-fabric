"""Drain pending cross-concept discover jobs.

Part of P1 (Discover V2): the main auto-pipeline no longer executes
cross-concept discovery inline — it only records a ``pending`` job in
``backend/data/discover-jobs.json``. This script is the simplest possible
"worker" that picks those jobs up and runs them.

The background service that will eventually replace this can share the
same executor (``app.services.auto.discover_job_executor``) — the only
thing missing here is a daemon loop, heartbeat refresh, and metrics.

Usage:

    cd backend
    uv run python scripts/run_discover_jobs.py                 # drain until empty
    uv run python scripts/run_discover_jobs.py --max 5         # stop after 5 jobs
    uv run python scripts/run_discover_jobs.py --recover-stale # rescue crashed runs first
    uv run python scripts/run_discover_jobs.py --list          # print queue snapshot only

Exits with status 0 on clean drain, 2 on executor failure.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


# Make ``app`` importable when invoked as ``python scripts/run_discover_jobs.py``.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.auto.discover_job_executor import claim_and_execute_one  # noqa: E402
from app.services.auto.discover_job_store import DiscoverJobStore  # noqa: E402


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _print_queue_snapshot(store: DiscoverJobStore) -> None:
    data = store.load()
    jobs = data["jobs"]
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.get("status", "?")] = counts.get(job.get("status", "?"), 0) + 1
    print(json.dumps({"total": len(jobs), "by_status": counts}, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="stop after N jobs (0 = drain until empty, default)",
    )
    parser.add_argument(
        "--recover-stale",
        action="store_true",
        help="recover stale running jobs (crashed workers) before draining",
    )
    parser.add_argument(
        "--stale-seconds",
        type=int,
        default=1800,
        help="heartbeat-stale threshold for --recover-stale (default 1800s)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print queue snapshot and exit without draining",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="override the discover-jobs.json path (tests / staging)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    store = DiscoverJobStore(args.path) if args.path else DiscoverJobStore()

    if args.list:
        _print_queue_snapshot(store)
        return 0

    if args.recover_stale:
        result = store.recover_stale_running(stale_after_seconds=args.stale_seconds)
        print(
            f"recovered stale running jobs: "
            f"requeued={len(result['requeued'])} gave_up={len(result['gave_up'])}"
        )

    executed = 0
    failures = 0
    while True:
        if args.max and executed >= args.max:
            break
        outcome = claim_and_execute_one(store=store)
        if outcome is None:
            break
        executed += 1
        status = outcome.get("status", "?")
        discovered = (outcome.get("stats") or {}).get("discovered", 0)
        print(
            f"[{executed}] {outcome.get('job_id')} -> {status} "
            f"(discovered={discovered})"
        )
        if status == "failed":
            failures += 1

    print(
        f"drain complete: executed={executed} failures={failures}"
    )
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
