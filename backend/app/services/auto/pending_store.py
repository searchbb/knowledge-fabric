"""File-locked state machine over ``pending-urls.json``.

This module owns the durable record of which URLs are pending, in-flight,
processed, or errored. It is intentionally a simple JSON file with a
process-level file lock — no SQLite, no sqlite-on-NFS pitfalls, no
external dependencies.

State transitions:

    pending → in_flight → processed
                       ↘ errored
    in_flight (stale) → pending (retry, attempt+1) → ... → errored (after max_attempts)

Concurrency: single-process serial worker is the only supported mode in
this MVP. The file lock exists to prevent corruption from a second worker
mistakenly started by hand and to prevent partial writes if the worker is
killed mid-write.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import os.path
import secrets
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

from .url_fingerprint import compute_fingerprint, first_collision


# Default location: ``backend/data/pending-urls.json``. Resolved relative to
# this file's location so it works regardless of the current working
# directory.
_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "pending-urls.json"
)


_EMPTY_STATE: dict[str, list] = {
    "pending": [],
    "in_flight": [],
    "processed": [],
    "errored": [],
}


class PendingUrlStoreError(RuntimeError):
    """Raised when the store cannot be read or written safely."""


class DuplicateUrlError(RuntimeError):
    """Raised when a URL is added that already exists by fingerprint."""

    def __init__(self, url: str, existing_bucket: str, existing_item: dict[str, Any]):
        super().__init__(
            f"URL already known in bucket={existing_bucket}: {url}"
        )
        self.url = url
        self.existing_bucket = existing_bucket
        self.existing_item = existing_item


class RetryNotAllowedError(RuntimeError):
    """Raised when ``retry_errored`` cannot move an entry back to pending.

    This covers both "fingerprint not found in errored bucket" and
    "fingerprint already present in pending/in_flight" — either way, a
    user-initiated retry would be a no-op or a duplicate, so the caller
    is told explicitly instead of silently swallowing the request.
    """

    def __init__(self, fingerprint: str, reason: str):
        super().__init__(f"cannot retry {fingerprint}: {reason}")
        self.fingerprint = fingerprint
        self.reason = reason


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_run_id() -> str:
    return f"auto_run_{secrets.token_hex(5)}"


@contextlib.contextmanager
def _flock(file_path: Path) -> Iterator[Any]:
    """Acquire an exclusive flock on a separate ``.lock`` sidecar file.

    Using a sidecar means the lock survives the JSON file being replaced
    via atomic rename. The lock file is created if missing but never
    removed — a stale empty lock file is harmless.
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


class PendingUrlStore:
    """File-locked state machine over a single pending-urls.json file."""

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path: Path = Path(path).expanduser().resolve() if path else _DEFAULT_DATA_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write(_EMPTY_STATE)

    # ------------------------------------------------------------------
    # Low-level read / write
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, list]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {bucket: [] for bucket in _EMPTY_STATE}
        if not text.strip():
            return {bucket: [] for bucket in _EMPTY_STATE}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise PendingUrlStoreError(
                f"pending-urls.json is corrupted: {error}"
            ) from error
        # Make sure the four buckets exist even if the file was hand-edited
        for bucket in _EMPTY_STATE:
            data.setdefault(bucket, [])
        return data

    def _atomic_write(self, data: dict[str, list]) -> None:
        """Write atomically by writing to a temp file then renaming."""
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

    def load(self) -> dict[str, list]:
        """Return the current state. Read-only, no lock acquired."""
        return self._read()

    def add_pending(
        self,
        url: str | None = None,
        *,
        md_path: str | None = None,
        source_url: str | None = None,
        allow_duplicate: bool = False,
    ) -> dict[str, Any]:
        """Add a URL or local markdown file to the pending bucket.

        Exactly one of ``url`` or ``md_path`` must be provided. If
        ``md_path`` is used, the entry will be processed through
        ``ArticleWorkspacePipeline.process_markdown_file()`` instead of the
        URL fetch path. ``source_url`` is an optional original link that
        gets recorded in the OB note frontmatter.

        Returns the inserted item dict. Raises ``DuplicateUrlError`` if an
        entry with the same fingerprint already exists in any bucket and
        ``allow_duplicate`` is False.
        """
        if bool(url) == bool(md_path):
            raise ValueError(
                "add_pending requires exactly one of url or md_path"
            )

        if url:
            fingerprint = compute_fingerprint(url)
            is_file_mode = False
            lookup_label = url
        else:
            # For local files the fingerprint is the absolute path itself.
            # We intentionally skip the URL fingerprint helpers here — they
            # would strip the ``file://`` scheme and break dedup.
            abs_path = os.path.abspath(os.path.expanduser(md_path or ""))
            fingerprint = f"file://{abs_path}"
            is_file_mode = True
            lookup_label = fingerprint

        with _flock(self.path):
            data = self._read()
            for bucket in ("processed", "in_flight", "pending", "errored"):
                if is_file_mode:
                    hit = next(
                        (
                            item
                            for item in data[bucket]
                            if item.get("url_fingerprint") == fingerprint
                        ),
                        None,
                    )
                else:
                    hit = first_collision(lookup_label, data[bucket])
                if hit is not None and not allow_duplicate:
                    raise DuplicateUrlError(lookup_label, bucket, hit)

            item: dict[str, Any] = {
                "url": url or "",
                "url_fingerprint": fingerprint,
                "created_at": _now_iso(),
                "attempt": 0,
            }
            if md_path:
                item["md_path"] = os.path.abspath(os.path.expanduser(md_path))
                item["source_url"] = source_url or ""
            data["pending"].append(item)
            self._atomic_write(data)
            return item

    def claim_next(self) -> Optional[dict[str, Any]]:
        """Move the oldest pending URL into in_flight and return it.

        Returns ``None`` if there is nothing to claim. The returned dict
        will have ``run_id``, ``claimed_at``, ``last_heartbeat_at``, and
        a bumped ``attempt`` populated.
        """
        with _flock(self.path):
            data = self._read()
            if not data["pending"]:
                return None
            item = data["pending"].pop(0)
            now = _now_iso()
            item["run_id"] = _new_run_id()
            item["claimed_at"] = now
            item["last_heartbeat_at"] = now
            item["attempt"] = int(item.get("attempt") or 0) + 1
            item["phase"] = "claimed"
            data["in_flight"].append(item)
            self._atomic_write(data)
            return dict(item)  # return a copy so the caller cannot mutate state

    def heartbeat(self, run_id: str, *, phase: Optional[str] = None) -> None:
        """Update the heartbeat for an in-flight URL."""
        with _flock(self.path):
            data = self._read()
            for entry in data["in_flight"]:
                if entry.get("run_id") == run_id:
                    entry["last_heartbeat_at"] = _now_iso()
                    if phase:
                        entry["phase"] = phase
                    self._atomic_write(data)
                    return
            # Silent miss is fine — the runner may have already moved the
            # entry into processed/errored.

    def mark_processed(
        self,
        run_id: str,
        *,
        project_id: str,
        graph_id: str,
        content_hash: Optional[str],
        summary: dict[str, Any],
        duration_ms: int,
    ) -> None:
        """Move an in-flight URL into processed with the result fields."""
        with _flock(self.path):
            data = self._read()
            entry = self._pop_inflight(data, run_id)
            if entry is None:
                raise PendingUrlStoreError(
                    f"mark_processed: run_id not in_flight: {run_id}"
                )
            entry.update(
                {
                    "project_id": project_id,
                    "graph_id": graph_id,
                    "content_hash": content_hash,
                    "summary": summary,
                    "duration_ms": duration_ms,
                    "finished_at": _now_iso(),
                    "phase": "done",
                    "error": None,
                }
            )
            data["processed"].append(entry)
            self._atomic_write(data)

    def mark_errored(
        self,
        run_id: str,
        *,
        error: str,
        phase: str,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
    ) -> None:
        """Move an in-flight URL into errored with the failure fields."""
        with _flock(self.path):
            data = self._read()
            entry = self._pop_inflight(data, run_id)
            if entry is None:
                raise PendingUrlStoreError(
                    f"mark_errored: run_id not in_flight: {run_id}"
                )
            entry.update(
                {
                    "error": error,
                    "phase": phase,
                    "project_id": project_id,
                    "graph_id": graph_id,
                    "failed_at": _now_iso(),
                }
            )
            data["errored"].append(entry)
            self._atomic_write(data)

    def retry_errored(self, url_fingerprint: str) -> dict[str, Any]:
        """Move an entry from the errored bucket back to pending.

        Used by the /api/auto/retry-errored endpoint when a user clicks the
        "retry" button on a failed URL. Run-specific fields from the failed
        attempt are cleared so the next ``claim_next()`` starts fresh, but
        ``attempt`` and ``created_at`` are preserved so the audit trail of
        "this is retry N of the same URL" is visible in the UI.

        Raises :class:`RetryNotAllowedError` if the fingerprint is not in
        the errored bucket, or if an entry with the same fingerprint is
        already sitting in pending or in_flight (in which case retrying
        would create a duplicate).
        """
        with _flock(self.path):
            data = self._read()

            # Guard: can't retry something that isn't already in-flight or
            # pending elsewhere — the user would end up with two live copies.
            for bucket in ("pending", "in_flight"):
                if any(item.get("url_fingerprint") == url_fingerprint for item in data[bucket]):
                    raise RetryNotAllowedError(
                        url_fingerprint,
                        f"already in {bucket} bucket",
                    )

            # Find the errored entry and pop it.
            errored_index = next(
                (
                    idx
                    for idx, item in enumerate(data["errored"])
                    if item.get("url_fingerprint") == url_fingerprint
                ),
                None,
            )
            if errored_index is None:
                raise RetryNotAllowedError(url_fingerprint, "not in errored bucket")

            entry = data["errored"].pop(errored_index)

            # Strip every field that came from the failed run. Leave
            # ``url``, ``url_fingerprint``, ``created_at``, ``attempt``, and
            # any ``md_path`` / ``source_url`` that identify the original
            # request alone.
            for stale in (
                "run_id",
                "claimed_at",
                "last_heartbeat_at",
                "phase",
                "error",
                "failed_at",
                "project_id",
                "graph_id",
                "summary",
                "content_hash",
                "duration_ms",
                "finished_at",
            ):
                entry.pop(stale, None)

            data["pending"].append(entry)
            self._atomic_write(data)
            return dict(entry)  # copy so callers can't mutate our state

    def retry_all_errored(self) -> dict[str, Any]:
        """Batch retry: move every unique-fingerprint errored entry to pending.

        Behaviour:
            - For each fingerprint currently in ``pending`` or ``in_flight``,
              the matching errored entries are dropped (no duplicate retry).
            - For duplicate errored entries sharing a fingerprint, only the
              first one encountered is moved back to pending; the rest are
              dropped (historical dedup).
            - Returns counters so the UI can tell the user what happened.

        After this call, the ``errored`` bucket is always empty.
        """
        with _flock(self.path):
            data = self._read()
            live_fps = {
                item.get("url_fingerprint")
                for bucket in ("pending", "in_flight")
                for item in data[bucket]
                if item.get("url_fingerprint")
            }
            retried: list[str] = []
            skipped_already_queued: list[str] = []
            deduped = 0
            seen_in_this_call: set[str] = set()
            kept: list[dict[str, Any]] = []

            for entry in data["errored"]:
                fp = entry.get("url_fingerprint")
                if not fp:
                    # Malformed entry — keep in errored untouched so a human
                    # can investigate. Don't silently drop data.
                    kept.append(entry)
                    continue
                if fp in live_fps:
                    skipped_already_queued.append(fp)
                    continue
                if fp in seen_in_this_call:
                    deduped += 1
                    continue
                # Move this one back to pending.
                for stale in (
                    "run_id",
                    "claimed_at",
                    "last_heartbeat_at",
                    "phase",
                    "error",
                    "failed_at",
                    "project_id",
                    "graph_id",
                    "summary",
                    "content_hash",
                    "duration_ms",
                    "finished_at",
                ):
                    entry.pop(stale, None)
                data["pending"].append(entry)
                retried.append(fp)
                seen_in_this_call.add(fp)

            data["errored"] = kept
            self._atomic_write(data)
            return {
                "retried": retried,
                "skipped_already_queued": skipped_already_queued,
                "deduped": deduped,
            }

    def clear_errored(self) -> int:
        """Delete every entry in the errored bucket. Returns the count removed.

        This is the destructive "forget these failures" action used by the
        frontend's "清空失败" button. Other buckets are left untouched.
        """
        with _flock(self.path):
            data = self._read()
            count = len(data["errored"])
            data["errored"] = []
            self._atomic_write(data)
            return count

    def recover_stale_inflight(
        self,
        *,
        stale_after_seconds: int = 1800,
        max_attempts: int = 2,
    ) -> dict[str, list[str]]:
        """Recover in-flight entries that haven't heart-beaten recently.

        Stale entries with attempt < max_attempts go back to pending.
        Stale entries with attempt >= max_attempts go to errored.

        Returns a dict ``{"requeued": [run_id, ...], "gave_up": [run_id, ...]}``.
        """
        cutoff = datetime.now() - timedelta(seconds=stale_after_seconds)
        requeued: list[str] = []
        gave_up: list[str] = []

        with _flock(self.path):
            data = self._read()
            still_in_flight: list[dict[str, Any]] = []
            for entry in data["in_flight"]:
                hb = entry.get("last_heartbeat_at")
                if not hb:
                    still_in_flight.append(entry)
                    continue
                try:
                    hb_dt = datetime.fromisoformat(hb)
                except ValueError:
                    still_in_flight.append(entry)
                    continue
                if hb_dt > cutoff:
                    still_in_flight.append(entry)
                    continue
                # stale — capture identifying fields BEFORE we mutate the entry
                attempt = int(entry.get("attempt") or 0)
                stale_run_id = entry.get("run_id") or ""
                if attempt >= max_attempts:
                    entry["error"] = (
                        f"recovered after stale heartbeat (attempt={attempt})"
                    )
                    entry["phase"] = entry.get("phase") or "stale"
                    entry["failed_at"] = _now_iso()
                    data["errored"].append(entry)
                    gave_up.append(stale_run_id)
                else:
                    # Reset run-specific fields and put back to pending
                    for key in ("run_id", "claimed_at", "last_heartbeat_at", "phase"):
                        entry.pop(key, None)
                    data["pending"].append(entry)
                    requeued.append(stale_run_id)
            data["in_flight"] = still_in_flight
            self._atomic_write(data)

        return {"requeued": requeued, "gave_up": gave_up}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pop_inflight(data: dict[str, list], run_id: str) -> Optional[dict[str, Any]]:
        for index, entry in enumerate(data["in_flight"]):
            if entry.get("run_id") == run_id:
                return data["in_flight"].pop(index)
        return None
