"""Governance scan request flag store.

Pipeline drain writes a "pending" flag after finishing; the governance-scan
API reads + clears it after a successful scan. The flag is persisted in
``backend/data/governance_request.json`` so it survives server restarts.

Design (user spec 2026-04-16):
- post-drain only 置位, never executes governance itself
- idempotent: multiple drains don't stack duplicate flags
- soft-fail: write failure logs warning, never breaks drain
- clear only after successful scan, never after failed scan
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("mirofish.governance_request_store")

_REQUEST_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..",
    "data",
    "governance_request.json",
)
_REQUEST_FILE = os.path.abspath(_REQUEST_FILE)

_write_lock = threading.Lock()


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(_REQUEST_FILE), exist_ok=True)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def mark_pending(*, reason: str = "post_drain") -> dict[str, Any]:
    """Write a pending governance request flag. Idempotent — if one is already
    pending, it's left as-is (don't overwrite requested_at / reason so the
    original trigger is preserved).

    Returns the current request payload (either newly written or existing).
    """
    existing = get_pending()
    if existing is not None:
        logger.debug(
            "governance request already pending (from %s at %s), not overwriting",
            existing.get("requested_reason"),
            existing.get("requested_at"),
        )
        return existing

    payload = {
        "requested": True,
        "status": "pending",
        "requested_at": _now_iso(),
        "requested_reason": reason,
    }
    _write(payload)
    logger.info("governance scan request marked pending (reason=%s)", reason)
    return payload


def get_pending() -> Optional[dict[str, Any]]:
    """Return the pending request payload, or None if no pending request."""
    if not os.path.exists(_REQUEST_FILE):
        return None
    try:
        with open(_REQUEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("status") == "pending" and data.get("requested"):
        return data
    return None


def clear_pending(*, consumed_by: str = "governance_scan") -> dict[str, Any]:
    """Mark the pending request as consumed. Only call after a SUCCESSFUL
    governance scan — never after a failed one.

    Returns the cleared payload for audit.
    """
    existing = get_pending()
    payload = {
        "requested": False,
        "status": "consumed",
        "requested_at": existing.get("requested_at") if existing else None,
        "requested_reason": existing.get("requested_reason") if existing else None,
        "consumed_at": _now_iso(),
        "consumed_by": consumed_by,
    }
    _write(payload)
    logger.info("governance scan request cleared (consumed_by=%s)", consumed_by)
    return payload


def _write(payload: dict[str, Any]) -> None:
    with _write_lock:
        _ensure_dir()
        tmp = _REQUEST_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _REQUEST_FILE)
