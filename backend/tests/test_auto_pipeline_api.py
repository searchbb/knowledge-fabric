"""HTTP-level tests for :mod:`app.api.routes.auto_pipeline`.

The handler module is thin — most of the state-machine correctness lives in
``test_auto_pending_store.py``. These tests exercise the Flask surface:
status codes, JSON shape, error classification.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask

from app.api.routes.auto_pipeline import auto_pipeline_bp
from app.services.auto import pending_store as pending_store_module
from app.services.auto.pending_store import PendingUrlStore


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch):
    """Flask test client with ``PendingUrlStore`` pointed at a scratch file."""
    scratch = tmp_path / "pending-urls.json"
    # The routes call ``PendingUrlStore()`` with no arguments, so we
    # redirect the module-level default path at the scratch file.
    monkeypatch.setattr(pending_store_module, "_DEFAULT_DATA_PATH", scratch)

    app = Flask(__name__)
    app.register_blueprint(auto_pipeline_bp)
    client = app.test_client()
    # Return both the client and a handle to the store so tests can seed
    # data directly instead of going through the add-then-fail cycle.
    client.store_path = scratch
    return client


def _seed_errored(store_path: Path, url: str = "https://example.com/x") -> dict:
    """Helper: drive one URL through pending → in_flight → errored."""
    store = PendingUrlStore(store_path)
    store.add_pending(url)
    claimed = store.claim_next()
    store.mark_errored(
        claimed["run_id"],
        error="timeout: no progress for 600s (limit 600s)",
        phase="build_extract",
        project_id="proj_abc",
        graph_id="graph_abc",
    )
    return store.load()["errored"][0]


class TestRetryErroredEndpoint:
    def test_retry_moves_to_pending_and_returns_200(self, api_client):
        errored = _seed_errored(api_client.store_path)
        fp = errored["url_fingerprint"]

        resp = api_client.post(
            "/api/auto/retry-errored",
            json={"url_fingerprint": fp},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["url_fingerprint"] == fp
        assert body["data"]["url"] == "https://example.com/x"

        # Verify the state actually moved.
        after = PendingUrlStore(api_client.store_path).load()
        assert len(after["errored"]) == 0
        assert len(after["pending"]) == 1

    def test_retry_missing_body_returns_400(self, api_client):
        resp = api_client.post("/api/auto/retry-errored")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False
        assert "url_fingerprint" in body["error"].lower()

    def test_retry_missing_fingerprint_returns_400(self, api_client):
        resp = api_client.post("/api/auto/retry-errored", json={})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False

    def test_retry_unknown_fingerprint_returns_404(self, api_client):
        resp = api_client.post(
            "/api/auto/retry-errored",
            json={"url_fingerprint": "sha256:nonexistent"},
        )
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["success"] is False
        assert "errored" in body["error"].lower()

    def test_retry_already_pending_returns_409(self, api_client):
        """A second click on retry while the first retry is still pending
        should not silently succeed — return a conflict so the UI can show
        'already queued' instead of pretending the second click worked."""
        errored = _seed_errored(api_client.store_path, "https://example.com/dup")
        fp = errored["url_fingerprint"]
        # First retry moves it to pending.
        first = api_client.post(
            "/api/auto/retry-errored",
            json={"url_fingerprint": fp},
        )
        assert first.status_code == 200

        # Manually re-errorize so we can test the "already pending" guard
        # (can't just click retry twice because after the first click the
        # fingerprint is no longer in errored).
        # Actually — if it's already pending and no longer in errored,
        # retry should fail with 404 (not in errored), NOT 409. But if
        # somehow it ended up in BOTH errored and pending, we should 409.
        # Simulate the "also in pending" case by seeding a second errored
        # entry for the SAME fingerprint via the raw store API.
        store = PendingUrlStore(api_client.store_path)
        store.add_pending("https://example.com/dup", allow_duplicate=True)
        # Now: pending has 2 copies (original retried + the new one).
        # Restore one errored copy so the retry handler's branch for
        # "already in pending/in_flight" actually fires.
        state = store.load()
        state["errored"].append({
            "url": "https://example.com/dup",
            "url_fingerprint": fp,
            "created_at": "2026-04-14T00:00:00",
            "attempt": 1,
            "error": "simulated second failure",
            "phase": "build_extract",
            "failed_at": "2026-04-14T00:10:00",
        })
        store._atomic_write(state)  # type: ignore[attr-defined]

        resp = api_client.post(
            "/api/auto/retry-errored",
            json={"url_fingerprint": fp},
        )
        assert resp.status_code == 409
        body = resp.get_json()
        assert body["success"] is False
        assert "pending" in body["error"].lower()


class TestRetryAllErroredEndpoint:
    def test_retry_all_moves_uniques_and_reports_counts(self, api_client):
        # Three distinct errored URLs.
        for url in (
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ):
            _seed_errored(api_client.store_path, url)

        resp = api_client.post("/api/auto/retry-all-errored")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert len(body["data"]["retried"]) == 3
        assert body["data"]["deduped"] == 0
        assert len(body["data"]["skipped_already_queued"]) == 0
        assert body["data"]["cleared_errored_count"] == 3

        state = PendingUrlStore(api_client.store_path).load()
        assert len(state["errored"]) == 0
        assert len(state["pending"]) == 3

    def test_retry_all_on_empty_returns_200_with_zeros(self, api_client):
        resp = api_client.post("/api/auto/retry-all-errored")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["retried"] == []
        assert body["data"]["cleared_errored_count"] == 0


class TestClearErroredEndpoint:
    def test_clear_removes_all_errored_and_reports_count(self, api_client):
        for url in (
            "https://example.com/a",
            "https://example.com/b",
        ):
            _seed_errored(api_client.store_path, url)
        assert len(PendingUrlStore(api_client.store_path).load()["errored"]) == 2

        resp = api_client.post("/api/auto/clear-errored")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["cleared"] == 2

        state = PendingUrlStore(api_client.store_path).load()
        assert state["errored"] == []

    def test_clear_on_empty_returns_zero(self, api_client):
        resp = api_client.post("/api/auto/clear-errored")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["cleared"] == 0
