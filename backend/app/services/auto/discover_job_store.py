"""File-locked state machine over ``discover-jobs.json``.

Part of P1 (Discover V2): cross-concept discover is detached from the main
pipeline. The pipeline now only *schedules* a job here; a background worker
(or the ``scripts/run_discover_jobs.py`` drainer for the P1 first cut) picks
pending jobs up and executes them.

The layout mirrors :class:`app.services.auto.pending_store.PendingUrlStore`:
a single JSON file with a sidecar ``.lock`` acquired via ``fcntl.flock`` and
atomic rename on every write. Differences:

- One flat ``jobs`` list rather than four buckets. ``status`` is a field,
  so queries always scan-and-filter — jobs are long-lived but low-volume
  (one per processed article at most), so a flat list is plenty.
- No URL fingerprint / dedupe. Each job has a unique ``job_id``; whether a
  given (theme_id, new_entry_ids) combination should be scheduled again is
  a policy question for the caller (pipeline_runner), not the store.

State machine:

    pending → running → completed
                     → partial     (some chunks failed, some succeeded)
                     → failed      (max_attempts exhausted)
    pending → cancelled
    running (stale) → pending      (attempt_count incremented; retry)
                   → failed        (attempt_count >= max_attempts)

``recover_stale_running`` is the only transition that changes state without
an explicit caller — it's how crashed workers get their jobs back into the
queue after restart.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional


_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "discover-jobs.json"
)


_EMPTY_STATE: dict[str, list[dict[str, Any]]] = {"jobs": []}


_TERMINAL_STATUSES = {"completed", "partial", "failed", "cancelled"}


class DiscoverJobStoreError(RuntimeError):
    """Raised when a requested job_id is missing or a write fails."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_job_id() -> str:
    return f"djob_{secrets.token_hex(5)}"


@contextlib.contextmanager
def _flock(file_path: Path) -> Iterator[Any]:
    """Acquire an exclusive flock on a sidecar ``.lock`` file.

    Same pattern as :func:`pending_store._flock`. The lock file survives
    atomic renames of the JSON payload.
    """
    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class DiscoverJobStore:
    """File-locked state machine over a single discover-jobs.json file."""

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path: Path = (
            Path(path).expanduser().resolve() if path else _DEFAULT_DATA_PATH
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write(_EMPTY_STATE)

    # ------------------------------------------------------------------
    # Low-level read / write
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"jobs": []}
        if not text.strip():
            return {"jobs": []}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise DiscoverJobStoreError(
                f"discover-jobs.json is corrupted: {error}"
            ) from error
        data.setdefault("jobs", [])
        return data

    def _atomic_write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, list[dict[str, Any]]]:
        return self._read()

    def create_job(
        self,
        *,
        theme_id: str,
        trigger_project_id: str,
        new_entry_ids: list[str],
        origin_run_id: str = "",
        scope_snapshot: Optional[dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """Create a new ``pending`` discover job and return a copy of the record.

        The caller (typically ``pipeline_runner``) owns the policy decision
        of whether this invocation deserves a job — an empty
        ``new_entry_ids`` is legal here because manual reruns may scope by
        ``entry_ids`` instead. Semantic gates live upstream, not in the store.
        """
        now = _now_iso()
        item: dict[str, Any] = {
            "job_id": _new_job_id(),
            "status": "pending",
            "theme_id": theme_id,
            "trigger_project_id": trigger_project_id,
            "new_entry_ids": list(new_entry_ids or []),
            "origin_run_id": origin_run_id,
            "scope_snapshot": dict(scope_snapshot) if scope_snapshot else {},
            "attempt_count": 0,
            "max_attempts": int(max_attempts),
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "heartbeat_at": None,
            "stats": {},
            "last_error": None,
        }
        with _flock(self.path):
            data = self._read()
            data["jobs"].append(item)
            self._atomic_write(data)
        return dict(item)

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        data = self._read()
        for job in data["jobs"]:
            if job.get("job_id") == job_id:
                return dict(job)
        return None

    def list_jobs(self, *, status: Optional[str] = None) -> list[dict[str, Any]]:
        data = self._read()
        jobs = data["jobs"]
        if status is not None:
            jobs = [j for j in jobs if j.get("status") == status]
        return [dict(j) for j in jobs]

    def claim_next(self) -> Optional[dict[str, Any]]:
        """Move the oldest ``pending`` job into ``running`` atomically.

        Returns the updated record, or ``None`` if no pending job exists.
        The record's ``attempt_count`` is incremented, ``started_at`` and
        ``heartbeat_at`` are stamped.
        """
        with _flock(self.path):
            data = self._read()
            for job in data["jobs"]:
                if job.get("status") != "pending":
                    continue
                now = _now_iso()
                job["status"] = "running"
                job["attempt_count"] = int(job.get("attempt_count") or 0) + 1
                job["started_at"] = now
                job["heartbeat_at"] = now
                job["updated_at"] = now
                self._atomic_write(data)
                return dict(job)
        return None

    def heartbeat(self, job_id: str) -> None:
        """Update ``heartbeat_at`` on a running job. Silent no-op if unknown."""
        with _flock(self.path):
            data = self._read()
            for job in data["jobs"]:
                if job.get("job_id") == job_id:
                    now = _now_iso()
                    job["heartbeat_at"] = now
                    job["updated_at"] = now
                    self._atomic_write(data)
                    return

    def mark_completed(self, job_id: str, *, stats: dict[str, Any]) -> None:
        self._transition(job_id, new_status="completed", stats=stats)

    def mark_partial(self, job_id: str, *, stats: dict[str, Any]) -> None:
        self._transition(job_id, new_status="partial", stats=stats)

    def mark_failed(self, job_id: str, *, error: str) -> None:
        self._transition(job_id, new_status="failed", error=str(error))

    def mark_cancelled(self, job_id: str) -> None:
        self._transition(job_id, new_status="cancelled")

    def count_started_today(self) -> int:
        """Count jobs created today (local-midnight boundary), excluding
        cancelled ones. Used by the global daily-budget soft-gate.
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        n = 0
        data = self._read()
        for job in data["jobs"]:
            if job.get("status") == "cancelled":
                continue
            created = job.get("created_at")
            if not created:
                continue
            try:
                created_dt = datetime.fromisoformat(created)
            except ValueError:
                continue
            if created_dt >= today_start:
                n += 1
        return n

    def count_recent_for_theme(
        self,
        theme_id: str,
        *,
        window_seconds: int = 3600,
    ) -> int:
        """Count jobs created for a given theme within the last ``window_seconds``.

        Used by ``pipeline_runner._schedule_discover_job`` to enforce the
        per-theme cooldown (P4 step 10). Cancelled jobs don't count —
        they never executed, so letting them eat the quota would penalise
        the user for hitting a bad job they cancelled on purpose.
        """
        cutoff = datetime.now() - timedelta(seconds=int(window_seconds))
        n = 0
        data = self._read()
        for job in data["jobs"]:
            if job.get("theme_id") != theme_id:
                continue
            if job.get("status") == "cancelled":
                continue
            created = job.get("created_at")
            if not created:
                continue
            try:
                created_dt = datetime.fromisoformat(created)
            except ValueError:
                continue
            if created_dt >= cutoff:
                n += 1
        return n

    def retry_job(self, job_id: str) -> dict[str, Any]:
        """Move a terminal job (partial/failed/cancelled) back to ``pending``.

        The audit trail (``attempt_count``, ``created_at``) is preserved so
        the UI can still show "this is retry N of the original schedule".
        Run-specific fields are reset so the next ``claim_next()`` starts
        fresh.

        Refuses to retry a currently ``running`` job (would race with the
        worker), a still-``pending`` one (no-op user mistake, surface it),
        or a ``completed`` one (discovered relations already committed;
        rerun should create a new job via the normal schedule path).

        Returns the post-retry job dict.
        """
        retriable = {"partial", "failed", "cancelled"}
        with _flock(self.path):
            data = self._read()
            for job in data["jobs"]:
                if job.get("job_id") != job_id:
                    continue
                status = job.get("status")
                if status not in retriable:
                    raise DiscoverJobStoreError(
                        f"cannot retry job in status={status!r} "
                        f"(retriable: {sorted(retriable)})"
                    )
                now = _now_iso()
                job["status"] = "pending"
                job["started_at"] = None
                job["heartbeat_at"] = None
                job["finished_at"] = None
                job["last_error"] = None
                job["updated_at"] = now
                self._atomic_write(data)
                return dict(job)
        raise DiscoverJobStoreError(f"unknown job_id: {job_id}")

    def cancel_pending_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a ``pending`` job so the worker never picks it up.

        Distinct from :meth:`mark_cancelled` (which is the unconditional
        internal setter): this is the policy-enforcing API the REST layer
        and the UI should call. Refuses to cancel a ``running`` job
        because cooperative mid-LLM cancellation is not implemented —
        the worker holds the job until it releases. For crashed workers,
        use :meth:`recover_stale_running` instead.
        """
        with _flock(self.path):
            data = self._read()
            for job in data["jobs"]:
                if job.get("job_id") != job_id:
                    continue
                status = job.get("status")
                if status != "pending":
                    raise DiscoverJobStoreError(
                        f"cannot cancel job in status={status!r} "
                        f"(only pending jobs can be cancelled)"
                    )
                now = _now_iso()
                job["status"] = "cancelled"
                job["finished_at"] = now
                job["updated_at"] = now
                self._atomic_write(data)
                return dict(job)
        raise DiscoverJobStoreError(f"unknown job_id: {job_id}")

    def recover_stale_running(
        self,
        *,
        stale_after_seconds: int = 1800,
        max_attempts: int = 3,
    ) -> dict[str, list[str]]:
        """Revive ``running`` jobs whose heartbeat is older than the cutoff.

        - ``attempt_count < max_attempts`` → back to ``pending``, run-specific
          fields reset so the next ``claim_next()`` starts fresh.
        - ``attempt_count >= max_attempts`` → ``failed`` with an explanatory
          ``last_error``.

        Returns ``{"requeued": [job_id, ...], "gave_up": [job_id, ...]}``.
        """
        cutoff = datetime.now() - timedelta(seconds=stale_after_seconds)
        requeued: list[str] = []
        gave_up: list[str] = []

        with _flock(self.path):
            data = self._read()
            for job in data["jobs"]:
                if job.get("status") != "running":
                    continue
                hb = job.get("heartbeat_at")
                if not hb:
                    continue
                try:
                    hb_dt = datetime.fromisoformat(hb)
                except ValueError:
                    continue
                if hb_dt > cutoff:
                    continue

                attempt = int(job.get("attempt_count") or 0)
                now = _now_iso()
                if attempt >= max_attempts:
                    job["status"] = "failed"
                    job["last_error"] = (
                        f"recovered after stale heartbeat (attempt_count={attempt})"
                    )
                    job["finished_at"] = now
                    job["updated_at"] = now
                    gave_up.append(job.get("job_id", ""))
                else:
                    job["status"] = "pending"
                    job["started_at"] = None
                    job["heartbeat_at"] = None
                    job["updated_at"] = now
                    requeued.append(job.get("job_id", ""))
            self._atomic_write(data)

        return {"requeued": requeued, "gave_up": gave_up}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(
        self,
        job_id: str,
        *,
        new_status: str,
        stats: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        with _flock(self.path):
            data = self._read()
            for job in data["jobs"]:
                if job.get("job_id") != job_id:
                    continue
                now = _now_iso()
                job["status"] = new_status
                job["updated_at"] = now
                if new_status in _TERMINAL_STATUSES:
                    job["finished_at"] = now
                if stats is not None:
                    job["stats"] = dict(stats)
                if error is not None:
                    job["last_error"] = error
                self._atomic_write(data)
                return
        raise DiscoverJobStoreError(f"unknown job_id: {job_id}")
