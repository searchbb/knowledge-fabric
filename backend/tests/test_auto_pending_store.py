"""Tests for ``app.services.auto.pending_store.PendingUrlStore``."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.services.auto.pending_store import (
    DuplicateUrlError,
    PendingUrlStore,
    PendingUrlStoreError,
    RetryNotAllowedError,
)


@pytest.fixture
def store(tmp_path: Path) -> PendingUrlStore:
    return PendingUrlStore(tmp_path / "pending-urls.json")


class TestInitialState:
    def test_creates_empty_file_if_missing(self, tmp_path: Path):
        path = tmp_path / "fresh.json"
        assert not path.exists()
        PendingUrlStore(path)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"pending": [], "in_flight": [], "processed": [], "errored": []}

    def test_load_returns_four_buckets(self, store: PendingUrlStore):
        data = store.load()
        for bucket in ("pending", "in_flight", "processed", "errored"):
            assert bucket in data
            assert data[bucket] == []


class TestAddPending:
    def test_adds_to_pending_with_metadata(self, store: PendingUrlStore):
        item = store.add_pending("https://example.com/article")
        assert item["url"] == "https://example.com/article"
        assert "url_fingerprint" in item
        assert item["attempt"] == 0
        assert "created_at" in item

        data = store.load()
        assert len(data["pending"]) == 1

    def test_rejects_empty_url(self, store: PendingUrlStore):
        with pytest.raises(ValueError):
            store.add_pending("")

    def test_dedups_by_fingerprint(self, store: PendingUrlStore):
        store.add_pending("https://example.com/x?utm_source=a")
        with pytest.raises(DuplicateUrlError) as ei:
            store.add_pending("https://example.com/x?utm_source=b")
        assert ei.value.existing_bucket == "pending"

    def test_allow_duplicate_bypass(self, store: PendingUrlStore):
        store.add_pending("https://example.com/x")
        # explicit override should not raise
        store.add_pending("https://example.com/x?utm_source=z", allow_duplicate=True)
        assert len(store.load()["pending"]) == 2


class TestClaimAndProcess:
    def test_claim_returns_none_when_empty(self, store: PendingUrlStore):
        assert store.claim_next() is None

    def test_claim_oldest_first(self, store: PendingUrlStore):
        first = store.add_pending("https://example.com/a")
        time.sleep(0.01)
        store.add_pending("https://example.com/b")
        claimed = store.claim_next()
        assert claimed is not None
        assert claimed["url"] == first["url"]
        assert claimed["run_id"].startswith("auto_run_")
        assert "claimed_at" in claimed
        assert "last_heartbeat_at" in claimed
        assert claimed["attempt"] == 1
        assert claimed["phase"] == "claimed"

        data = store.load()
        assert len(data["pending"]) == 1
        assert len(data["in_flight"]) == 1

    def test_heartbeat_updates_inflight(self, store: PendingUrlStore):
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()
        original_hb = claimed["last_heartbeat_at"]
        time.sleep(0.05)
        store.heartbeat(claimed["run_id"], phase="building")
        data = store.load()
        new_hb = data["in_flight"][0]["last_heartbeat_at"]
        assert new_hb >= original_hb
        assert data["in_flight"][0]["phase"] == "building"

    def test_mark_processed_moves_to_processed(self, store: PendingUrlStore):
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()
        store.mark_processed(
            claimed["run_id"],
            project_id="proj_xxx",
            graph_id="graph_xxx",
            content_hash="sha256:abc",
            summary={"accepted": 5, "registered": 3},
            duration_ms=12345,
        )
        data = store.load()
        assert len(data["in_flight"]) == 0
        assert len(data["processed"]) == 1
        proc = data["processed"][0]
        assert proc["project_id"] == "proj_xxx"
        assert proc["graph_id"] == "graph_xxx"
        assert proc["content_hash"] == "sha256:abc"
        assert proc["summary"]["accepted"] == 5
        assert proc["duration_ms"] == 12345
        assert proc["phase"] == "done"
        assert proc["error"] is None

    def test_mark_errored_moves_to_errored(self, store: PendingUrlStore):
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()
        store.mark_errored(
            claimed["run_id"], error="fetch failed", phase="fetch"
        )
        data = store.load()
        assert len(data["in_flight"]) == 0
        assert len(data["errored"]) == 1
        err = data["errored"][0]
        assert err["error"] == "fetch failed"
        assert err["phase"] == "fetch"

    def test_mark_processed_unknown_run_id_raises(self, store: PendingUrlStore):
        with pytest.raises(PendingUrlStoreError):
            store.mark_processed(
                "auto_run_nope",
                project_id="x",
                graph_id="y",
                content_hash=None,
                summary={},
                duration_ms=0,
            )


class TestRecoverStale:
    def test_no_stale_no_changes(self, store: PendingUrlStore):
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()
        result = store.recover_stale_inflight(stale_after_seconds=600)
        assert result == {"requeued": [], "gave_up": []}
        assert len(store.load()["in_flight"]) == 1

    def test_stale_attempt1_requeued(self, store: PendingUrlStore, tmp_path: Path):
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()
        # Manually rewrite the file to make heartbeat ancient
        data = store.load()
        data["in_flight"][0]["last_heartbeat_at"] = (
            datetime.now() - timedelta(hours=1)
        ).isoformat(timespec="seconds")
        store.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        result = store.recover_stale_inflight(stale_after_seconds=1800, max_attempts=2)
        assert claimed["run_id"] in result["requeued"]

        post = store.load()
        assert len(post["in_flight"]) == 0
        assert len(post["pending"]) == 1
        # The retried item should not still carry the run_id
        assert "run_id" not in post["pending"][0]

    def test_stale_attempt_at_max_gives_up(self, store: PendingUrlStore):
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()  # attempt becomes 1

        # Manually bump attempt to max and rewind heartbeat
        data = store.load()
        data["in_flight"][0]["attempt"] = 2
        data["in_flight"][0]["last_heartbeat_at"] = (
            datetime.now() - timedelta(hours=2)
        ).isoformat(timespec="seconds")
        store.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        result = store.recover_stale_inflight(stale_after_seconds=1800, max_attempts=2)
        assert claimed["run_id"] in result["gave_up"]

        post = store.load()
        assert len(post["in_flight"]) == 0
        assert len(post["errored"]) == 1
        assert "stale" in (post["errored"][0].get("error") or "")


class TestRetryErrored:
    def _errored_item(self, store: PendingUrlStore, url: str = "https://example.com/a") -> dict:
        """Fixture helper: drive one URL through pending → in_flight → errored."""
        store.add_pending(url)
        claimed = store.claim_next()
        store.mark_errored(
            claimed["run_id"],
            error="timeout: no progress for 600s",
            phase="build_extract",
            project_id="proj_abc",
            graph_id="graph_abc",
        )
        return store.load()["errored"][0]

    def test_retry_moves_errored_back_to_pending(self, store: PendingUrlStore):
        errored = self._errored_item(store)
        fp = errored["url_fingerprint"]

        returned = store.retry_errored(fp)

        data = store.load()
        assert len(data["errored"]) == 0
        assert len(data["pending"]) == 1
        assert data["pending"][0]["url_fingerprint"] == fp
        assert returned["url_fingerprint"] == fp

    def test_retry_clears_run_fields(self, store: PendingUrlStore):
        errored = self._errored_item(store)
        fp = errored["url_fingerprint"]

        store.retry_errored(fp)

        pending_item = store.load()["pending"][0]
        for stale in (
            "run_id",
            "claimed_at",
            "last_heartbeat_at",
            "phase",
            "error",
            "failed_at",
            "project_id",
            "graph_id",
        ):
            assert stale not in pending_item, f"expected {stale!r} cleared after retry"

    def test_retry_preserves_attempt_and_history(self, store: PendingUrlStore):
        errored = self._errored_item(store)
        fp = errored["url_fingerprint"]
        prior_attempt = errored["attempt"]

        store.retry_errored(fp)

        pending_item = store.load()["pending"][0]
        # attempt is kept so the next claim_next() bumps it to prior+1 — the
        # UI can still show this is retry N without losing the audit trail.
        assert pending_item["attempt"] == prior_attempt
        # created_at stays the same — this URL is not new, it's being retried.
        assert pending_item["created_at"] == errored["created_at"]

    def test_retry_unknown_fingerprint_raises(self, store: PendingUrlStore):
        with pytest.raises(RetryNotAllowedError) as ei:
            store.retry_errored("sha256:nonexistent")
        assert "not in errored" in str(ei.value).lower()

    def test_retry_refuses_when_already_pending(self, store: PendingUrlStore):
        """If the same fingerprint is already pending/in_flight, retry is a no-op
        and must raise so the caller can show a useful error."""
        errored = self._errored_item(store, "https://example.com/dup")
        fp = errored["url_fingerprint"]
        # Sneak another copy of the same URL into pending (normally blocked
        # by add_pending dedup, but the dedup check scans every bucket
        # including errored, so we bypass it with allow_duplicate=True for
        # this test).
        store.add_pending("https://example.com/dup", allow_duplicate=True)

        with pytest.raises(RetryNotAllowedError):
            store.retry_errored(fp)

    def test_retry_subsequent_claim_bumps_attempt(self, store: PendingUrlStore):
        """After retry, claim_next should resume the attempt counter."""
        errored = self._errored_item(store)
        fp = errored["url_fingerprint"]
        prior_attempt = errored["attempt"]  # = 1 after one failed run

        store.retry_errored(fp)
        reclaimed = store.claim_next()

        assert reclaimed is not None
        assert reclaimed["attempt"] == prior_attempt + 1
        assert reclaimed["url_fingerprint"] == fp


class TestRetryAllErrored:
    def _seed_three_distinct(self, store: PendingUrlStore) -> list[str]:
        """Drive three distinct URLs into errored. Returns the fingerprints."""
        fps: list[str] = []
        for url in (
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ):
            store.add_pending(url)
            claimed = store.claim_next()
            store.mark_errored(
                claimed["run_id"], error="boom", phase="fetch"
            )
            fps.append(claimed["url_fingerprint"])
        return fps

    def test_retry_all_moves_every_unique_fingerprint(self, store: PendingUrlStore):
        self._seed_three_distinct(store)
        assert len(store.load()["errored"]) == 3

        result = store.retry_all_errored()

        assert len(result["retried"]) == 3
        data = store.load()
        assert len(data["errored"]) == 0
        assert len(data["pending"]) == 3

    def test_retry_all_dedupes_duplicate_fingerprints(self, store: PendingUrlStore):
        """If two errored entries share a fingerprint (historical data), only
        one moves to pending — the other is dropped."""
        store.add_pending("https://example.com/a")
        claimed = store.claim_next()
        store.mark_errored(claimed["run_id"], error="first", phase="fetch")
        # Sneak a second errored entry for the same fingerprint by bypassing
        # dedup via allow_duplicate.
        store.add_pending("https://example.com/a", allow_duplicate=True)
        claimed2 = store.claim_next()
        store.mark_errored(claimed2["run_id"], error="second", phase="fetch")
        assert len(store.load()["errored"]) == 2

        result = store.retry_all_errored()

        assert len(result["retried"]) == 1
        assert result["deduped"] == 1
        data = store.load()
        assert len(data["errored"]) == 0
        assert len(data["pending"]) == 1

    def test_retry_all_skips_fingerprints_already_live(self, store: PendingUrlStore):
        """Errored entries whose fingerprint is currently pending or in_flight
        should NOT be duplicated — they're dropped from errored without being
        moved (the live copy will handle the retry)."""
        # Final state we want BEFORE retry_all: errored=[b, a], pending=[a].
        # Order matters because claim_next pops pending[0], so seed 'b'
        # first to get it into errored without consuming 'a'.
        store.add_pending("https://example.com/b")
        claimed_b = store.claim_next()
        store.mark_errored(claimed_b["run_id"], error="boom", phase="fetch")
        store.add_pending("https://example.com/a")
        claimed_a = store.claim_next()
        store.mark_errored(claimed_a["run_id"], error="boom", phase="fetch")
        # Now add a new pending copy of 'a' so 'a' exists in both buckets.
        store.add_pending("https://example.com/a", allow_duplicate=True)

        result = store.retry_all_errored()

        data = store.load()
        # 'b' moved to pending, 'a' was skipped (already in pending)
        assert len(result["retried"]) == 1
        assert len(result["skipped_already_queued"]) == 1
        assert len(data["errored"]) == 0
        # Pending has: existing 'a' + newly-moved 'b' = 2
        assert len(data["pending"]) == 2

    def test_retry_all_on_empty_errored_is_noop(self, store: PendingUrlStore):
        result = store.retry_all_errored()
        assert result == {
            "retried": [],
            "skipped_already_queued": [],
            "deduped": 0,
        }


class TestClearErrored:
    def test_clear_deletes_every_errored_entry(self, store: PendingUrlStore):
        for url in (
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ):
            store.add_pending(url)
            claimed = store.claim_next()
            store.mark_errored(claimed["run_id"], error="boom", phase="fetch")
        assert len(store.load()["errored"]) == 3

        count = store.clear_errored()

        assert count == 3
        assert store.load()["errored"] == []

    def test_clear_on_empty_errored_is_zero(self, store: PendingUrlStore):
        assert store.clear_errored() == 0

    def test_clear_does_not_touch_other_buckets(self, store: PendingUrlStore):
        store.add_pending("https://example.com/pending")
        store.add_pending("https://example.com/flying")
        claimed = store.claim_next()  # moves 'flying' to in_flight (oldest first? no — 'pending' is first)
        # Actually claim_next takes the oldest, so 'pending' URL goes first.
        store.add_pending("https://example.com/failed")
        claimed_failed = store.claim_next()  # takes 'flying'
        store.mark_errored(claimed_failed["run_id"], error="boom", phase="fetch")
        # Now: pending has 1, in_flight has 1 (claimed), errored has 1
        # Claim again to push another to in_flight so we can measure
        # untouchedness across all three live buckets.
        store.claim_next()
        # Mark first claim as processed so it moves to processed bucket.
        store.mark_processed(
            claimed["run_id"],
            project_id="p",
            graph_id="g",
            content_hash=None,
            summary={},
            duration_ms=1,
        )

        before = store.load()
        before_counts = {b: len(before[b]) for b in ("pending", "in_flight", "processed")}

        store.clear_errored()

        after = store.load()
        for bucket in ("pending", "in_flight", "processed"):
            assert len(after[bucket]) == before_counts[bucket], (
                f"{bucket} should not change after clear_errored"
            )
