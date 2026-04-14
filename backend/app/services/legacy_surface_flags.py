"""Feature flags and helpers for legacy runtime surfaces."""

from __future__ import annotations

from typing import Any

from ..config import Config

LEGACY_SURFACE_SIMULATION = "simulation"
LEGACY_SURFACE_REPORTING = "reporting"
LEGACY_BACKEND_ZEP = "legacy_zep"

_LEGACY_SURFACE_CONFIG = {
    LEGACY_SURFACE_SIMULATION: "ENABLE_LEGACY_ZEP_SIMULATION",
    LEGACY_SURFACE_REPORTING: "ENABLE_LEGACY_ZEP_REPORTING",
}


def is_legacy_surface_enabled(surface: str) -> bool:
    attr_name = _LEGACY_SURFACE_CONFIG.get(surface)
    if not attr_name:
        raise ValueError(f"未知 legacy surface: {surface}")
    return bool(getattr(Config, attr_name, True))


def build_legacy_surface_disabled_payload(surface: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": f"legacy_zep {surface} surface 已禁用",
        "surface": surface,
        "runtime_surface": LEGACY_BACKEND_ZEP,
    }
