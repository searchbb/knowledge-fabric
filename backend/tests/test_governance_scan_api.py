"""Integration tests for the governance-request flag and governance-scan API.

Tests D–H per the plan:
D. GET governance-request → no pending flag
E. GET governance-request → pending flag present
F. POST governance-scan (live) → clears pending flag on success
G. POST governance-scan (dry_run) → does NOT clear flag on success
H. POST governance-scan → does NOT clear flag on failure
"""

from __future__ import annotations

import pytest
from flask import Flask
from unittest.mock import patch

from app.api import registry_bp
from app.services.auto.governance_request_store import (
    _REQUEST_FILE,
    clear_pending,
    get_pending,
    mark_pending,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMPTY_SCAN = {"merged": [], "skipped": [], "errors": []}
_EMPTY_PROMOTE = {"promoted": [], "skipped": [], "errors": []}


@pytest.fixture()
def api_client():
    """Minimal Flask app with the registry blueprint registered."""
    app = Flask(__name__)
    app.register_blueprint(registry_bp, url_prefix="/api/registry")
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_flag(tmp_path, monkeypatch):
    """Redirect _REQUEST_FILE to a temp path and wipe it before each test."""
    tmp_flag = str(tmp_path / "governance_request.json")
    monkeypatch.setattr(
        "app.services.auto.governance_request_store._REQUEST_FILE", tmp_flag
    )
    # Also patch the same name in the routes module (imported lazily, so patching
    # the store module is sufficient — they share the same module object).
    yield
    # File is auto-cleaned by tmp_path fixture.


# ---------------------------------------------------------------------------
# Test D — GET /governance-request, no pending flag
# ---------------------------------------------------------------------------

def test_get_governance_request_no_pending(api_client):
    """No flag file → response: pending=false, request=null."""
    resp = api_client.get("/api/registry/themes/governance-request")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["pending"] is False
    assert data["request"] is None


# ---------------------------------------------------------------------------
# Test E — GET /governance-request, pending flag present
# ---------------------------------------------------------------------------

def test_get_governance_request_with_pending(api_client):
    """After mark_pending(), GET returns pending=true with the stored payload."""
    mark_pending(reason="test_trigger")

    resp = api_client.get("/api/registry/themes/governance-request")
    assert resp.status_code == 200
    body = resp.get_json()
    data = body["data"]
    assert data["pending"] is True
    req = data["request"]
    assert req is not None
    assert req["requested"] is True
    assert req["status"] == "pending"
    assert req["requested_reason"] == "test_trigger"


# ---------------------------------------------------------------------------
# Test F — POST governance-scan (live) clears flag on success
# ---------------------------------------------------------------------------

def test_governance_scan_clears_flag_on_success(api_client):
    """A successful live scan must clear the pending governance flag."""
    mark_pending(reason="post_drain")
    assert get_pending() is not None

    with (
        patch(
            "app.services.auto.theme_merge_scanner.scan_and_merge_candidates",
            return_value=_EMPTY_SCAN,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.promote_eligible_candidate_themes",
            return_value=_EMPTY_PROMOTE,
        ),
    ):
        resp = api_client.post(
            "/api/registry/themes/governance-scan",
            json={"dry_run": False},
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    req_info = body["data"]["request"]
    assert req_info["had_pending_request"] is True
    assert req_info["cleared"] is True

    # Flag must be gone.
    assert get_pending() is None


# ---------------------------------------------------------------------------
# Test G — POST governance-scan (dry_run) does NOT clear flag
# ---------------------------------------------------------------------------

def test_governance_scan_does_not_clear_flag_on_dry_run(api_client):
    """Dry-run scans must leave the pending flag intact even on success."""
    mark_pending(reason="post_drain")

    with (
        patch(
            "app.services.auto.theme_merge_scanner.scan_and_merge_candidates",
            return_value=_EMPTY_SCAN,
        ),
        patch(
            "app.services.auto.theme_merge_scanner.promote_eligible_candidate_themes",
            return_value=_EMPTY_PROMOTE,
        ),
    ):
        resp = api_client.post(
            "/api/registry/themes/governance-scan",
            json={"dry_run": True},
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    req_info = body["data"]["request"]
    assert req_info["had_pending_request"] is True
    assert req_info["cleared"] is False  # dry_run → never clears

    # Flag must still be pending.
    assert get_pending() is not None


# ---------------------------------------------------------------------------
# Test H — POST governance-scan failure does NOT clear flag
# ---------------------------------------------------------------------------

def test_governance_scan_does_not_clear_flag_on_failure(api_client):
    """A scan that raises an exception must leave the pending flag untouched."""
    mark_pending(reason="post_drain")

    with patch(
        "app.services.auto.theme_merge_scanner.scan_and_merge_candidates",
        side_effect=RuntimeError("neo4j unavailable"),
    ):
        resp = api_client.post(
            "/api/registry/themes/governance-scan",
            json={"dry_run": False},
        )

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False

    # Flag must still be there — not cleared on failure.
    assert get_pending() is not None
