"""Neon branch helpers. SQLite remains the default until H6."""
from __future__ import annotations

import os
from typing import Any

from ..config import settings


def available() -> bool:
    return bool(os.environ.get("NEON_API_KEY") and os.environ.get("NEON_PROJECT_ID")
                and os.environ.get("USE_NEON", "").strip() in {"1", "true", "yes", "on"})


def surge_branch_status() -> dict[str, Any]:
    if settings.mock or not available():
        return {
            "backend": "sqlite",
            "branch": "local-sim",
            "status": "mock" if settings.mock else "blocked_needs_H6",
            "note": "Surge runs on an isolated temporary SQLite file until Neon is configured.",
        }
    return {
        "backend": "neon",
        "branch": os.environ.get("NEON_SURGE_BRANCH_ID") or "surge-sim",
        "status": "live-unverified",
    }


def reset_to_calm() -> dict[str, Any]:
    """Reset practice/surge state. Live Neon reset needs H6."""
    return {"ok": True, **surge_branch_status(), "reset": "local"}
