"""Rolling append-only log of discover schedule skips (GPT audit 2026-04-17).

Per-theme cooldown and global daily budget already record a
``skipped_reason`` into ``summary.discover`` on the triggering URL.
GPT flagged that as insufficient visibility: the user has no easy way
to see "system is rate-limiting my ingests" without grepping URL
summaries.

This module captures every skip into a tiny rolling log so the
AutoPipelinePage Discover panel can surface recent skips as a
compact warning.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.services.auto.discover_skip_log import DiscoverSkipLog


@pytest.fixture
def log(tmp_path: Path) -> DiscoverSkipLog:
    return DiscoverSkipLog(tmp_path / "discover-skips.json")


class TestAppend:
    def test_empty_log_lists_nothing(self, log: DiscoverSkipLog):
        assert log.list_recent() == []

    def test_append_records_all_fields(self, log: DiscoverSkipLog):
        log.append(
            reason="theme cooldown: 10 in the last hour (cap=10)",
            theme_id="gtheme_hot",
            trigger_project_id="proj_1",
            origin_run_id="auto_run_abc",
            kind="theme_cooldown",
        )
        entries = log.list_recent()
        assert len(entries) == 1
        e = entries[0]
        assert e["theme_id"] == "gtheme_hot"
        assert e["trigger_project_id"] == "proj_1"
        assert e["origin_run_id"] == "auto_run_abc"
        assert "cooldown" in e["reason"].lower()
        assert e["kind"] == "theme_cooldown"
        assert "skipped_at" in e

    def test_append_is_most_recent_first(self, log: DiscoverSkipLog):
        log.append(reason="first", kind="theme_cooldown")
        time.sleep(0.01)
        log.append(reason="second", kind="daily_budget")
        entries = log.list_recent()
        assert [e["reason"] for e in entries] == ["second", "first"]


class TestCap:
    def test_append_caps_at_max_entries(self, tmp_path: Path):
        log = DiscoverSkipLog(tmp_path / "discover-skips.json", max_entries=5)
        for i in range(12):
            log.append(reason=f"skip #{i}", kind="daily_budget")
        entries = log.list_recent()
        assert len(entries) == 5
        # The most recent (#11) is first; the earliest kept is #7.
        assert entries[0]["reason"] == "skip #11"
        assert entries[-1]["reason"] == "skip #7"


class TestWindowFilter:
    def test_list_recent_respects_window_seconds(self, log: DiscoverSkipLog):
        log.append(reason="old", kind="theme_cooldown")
        # Backdate that entry.
        from datetime import datetime, timedelta
        import json as _j
        data = _j.loads(log.path.read_text())
        data["skips"][0]["skipped_at"] = (
            datetime.now() - timedelta(hours=3)
        ).isoformat(timespec="seconds")
        log.path.write_text(_j.dumps(data, ensure_ascii=False, indent=2))

        log.append(reason="fresh", kind="daily_budget")

        # Window = 1 hour drops the old one.
        within_hour = log.list_recent(within_seconds=3600)
        assert [e["reason"] for e in within_hour] == ["fresh"]

        # No window returns both.
        all_entries = log.list_recent()
        assert len(all_entries) == 2


class TestStats:
    def test_stats_counts_by_kind_in_window(self, log: DiscoverSkipLog):
        log.append(reason="x", kind="theme_cooldown")
        log.append(reason="y", kind="theme_cooldown")
        log.append(reason="z", kind="daily_budget")
        stats = log.stats(within_seconds=3600)
        assert stats["total"] == 3
        assert stats["by_kind"] == {"theme_cooldown": 2, "daily_budget": 1}
