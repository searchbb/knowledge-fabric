"""Append-only rolling log of discover-schedule skip events.

Per-audit-2026-04-17 (GPT): the per-theme cooldown and global daily
budget are currently invisible to the user. They write a
``skipped_reason`` into ``summary.discover`` on the triggering URL, but
nobody drills into URL-level summaries to notice a runaway-ingest
throttle event. This module gives the Discover panel a single cheap
source to render "how many schedules did the system block recently".

Layout mirrors every other JSON store in ``services/auto/``:

- Single JSON file (``backend/data/discover-skips.json`` by default).
- Atomic rename on append; file lock shared with the discoverer so two
  workers can't race.
- Capped at ``DiscoverSkipLog.max_entries`` rows so the file never
  grows without bound.

Each row:

    {
      "skipped_at": "2026-04-17T22:10:30",
      "reason":     "theme cooldown: 11 in the last hour (cap=10)",
      "kind":       "theme_cooldown" | "daily_budget" | "other",
      "theme_id":   "gtheme_xyz",
      "trigger_project_id": "proj_abc",
      "origin_run_id":      "auto_run_def"
    }
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional


_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "discover-skips.json"
)

_EMPTY_STATE: dict[str, Any] = {"version": 1, "skips": []}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextlib.contextmanager
def _flock(file_path: Path) -> Iterator[Any]:
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


class DiscoverSkipLog:
    """Rolling append-only log of schedule-time skips."""

    def __init__(
        self,
        path: Optional[Path | str] = None,
        *,
        max_entries: int = 50,
    ) -> None:
        self.path: Path = (
            Path(path).expanduser().resolve() if path else _DEFAULT_DATA_PATH
        )
        self.max_entries = int(max_entries)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._atomic_write(dict(_EMPTY_STATE, skips=[]))

    # ------------------------------------------------------------------
    # Low-level read / write
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"version": 1, "skips": []}
        if not text.strip():
            return {"version": 1, "skips": []}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Corrupt store shouldn't fan out into every discover run.
            return {"version": 1, "skips": []}
        data.setdefault("version", 1)
        data.setdefault("skips", [])
        return data

    def _atomic_write(self, data: dict[str, Any]) -> None:
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

    def append(
        self,
        *,
        reason: str,
        kind: str = "other",
        theme_id: str = "",
        trigger_project_id: str = "",
        origin_run_id: str = "",
    ) -> dict[str, Any]:
        """Record one skip. Returns the persisted row."""
        entry = {
            "skipped_at": _now_iso(),
            "reason": str(reason),
            "kind": str(kind or "other"),
            "theme_id": theme_id,
            "trigger_project_id": trigger_project_id,
            "origin_run_id": origin_run_id,
        }
        with _flock(self.path):
            data = self._read()
            data["skips"].insert(0, entry)  # most-recent first
            if len(data["skips"]) > self.max_entries:
                data["skips"] = data["skips"][: self.max_entries]
            self._atomic_write(data)
        return dict(entry)

    def list_recent(
        self,
        *,
        within_seconds: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Return entries, newest first. Optionally filter by window / limit."""
        data = self._read()
        entries = list(data["skips"])
        if within_seconds is not None:
            cutoff = datetime.now() - timedelta(seconds=int(within_seconds))
            kept: list[dict[str, Any]] = []
            for e in entries:
                ts = e.get("skipped_at")
                if not ts:
                    continue
                try:
                    if datetime.fromisoformat(ts) >= cutoff:
                        kept.append(e)
                except ValueError:
                    continue
            entries = kept
        if limit is not None:
            entries = entries[: int(limit)]
        return entries

    def stats(self, *, within_seconds: Optional[int] = None) -> dict[str, Any]:
        """Counts by ``kind`` within the optional window."""
        entries = self.list_recent(within_seconds=within_seconds)
        by_kind: dict[str, int] = {}
        for e in entries:
            k = str(e.get("kind") or "other")
            by_kind[k] = by_kind.get(k, 0) + 1
        return {"total": len(entries), "by_kind": by_kind}
