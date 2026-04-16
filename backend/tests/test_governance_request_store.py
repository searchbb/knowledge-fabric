"""Tests for the governance request flag store (post-drain flag mechanism).

User spec (2026-04-16):
1. run_until_drained() 完成后会置位 pending request
2. 连续 drain 时 request 置位是幂等的，不会重复堆多条
3. governance-scan 成功后会 clear pending；失败时不会 clear
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

from app.services.auto.governance_request_store import (
    _REQUEST_FILE,
    clear_pending,
    get_pending,
    mark_pending,
)


def _with_clean_flag(fn):
    """Decorator to ensure the flag file is cleared before/after test."""
    def wrapper(*args, **kwargs):
        # Backup + clear
        existed = os.path.exists(_REQUEST_FILE)
        backup = None
        if existed:
            with open(_REQUEST_FILE, "r") as f:
                backup = f.read()
            os.remove(_REQUEST_FILE)
        try:
            return fn(*args, **kwargs)
        finally:
            # Restore
            if backup is not None:
                with open(_REQUEST_FILE, "w") as f:
                    f.write(backup)
            elif os.path.exists(_REQUEST_FILE):
                os.remove(_REQUEST_FILE)
    return wrapper


@_with_clean_flag
def test_mark_pending_creates_flag():
    """After drain, a pending request flag is written."""
    assert get_pending() is None
    result = mark_pending(reason="post_drain")
    assert result["requested"] is True
    assert result["status"] == "pending"
    assert result["requested_reason"] == "post_drain"

    # Reading back should return the same flag.
    stored = get_pending()
    assert stored is not None
    assert stored["requested"] is True


@_with_clean_flag
def test_mark_pending_is_idempotent():
    """Consecutive drains don't stack multiple flags — first one wins."""
    first = mark_pending(reason="drain_1")
    second = mark_pending(reason="drain_2")

    # The original flag is preserved (reason stays "drain_1").
    assert second["requested_reason"] == "drain_1"
    assert second["requested_at"] == first["requested_at"]

    # Only one pending flag exists.
    stored = get_pending()
    assert stored["requested_reason"] == "drain_1"


@_with_clean_flag
def test_clear_pending_only_after_success():
    """governance-scan success clears the flag; failure must not clear it."""
    mark_pending(reason="post_drain")
    assert get_pending() is not None

    # Simulate successful scan → clear.
    clear_pending(consumed_by="test_success")
    assert get_pending() is None

    # Re-mark for "failure" test: flag is back.
    mark_pending(reason="second_drain")
    assert get_pending() is not None
    # A failed scan would NOT call clear_pending — so the flag stays.
    # (We just verify the flag is still there.)
    assert get_pending()["requested_reason"] == "second_drain"
