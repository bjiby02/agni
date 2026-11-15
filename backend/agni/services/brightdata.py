"""Bright Data crowd-signal adapter. Never called while a call is live (enforced by poller)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, request

from ..config import settings

BACKEND = Path(__file__).resolve().parents[2]
FIXTURE = BACKEND / "tests" / "fixtures" / "serp_signals.json"

# Test hook: set True to fail if HTTP is attempted during a live call.
_HTTP_CALLS = 0
_BLOCK_HTTP = False


def clear_stats() -> None:
    global _HTTP_CALLS
    _HTTP_CALLS = 0


def http_call_count() -> int:
    return _HTTP_CALLS


def block_http(blocked: bool = True) -> None:
    global _BLOCK_HTTP
    _BLOCK_HTTP = blocked


def fetch_serp_signals() -> list[dict[str, Any]]:
    """Return recent public fire-related posts (fixture in mock, live SERP when keyed)."""
    global _HTTP_CALLS
    if settings.mock or not __import__("os").environ.get("BRIGHTDATA_API_TOKEN"):
        try:
            raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return raw if isinstance(raw, list) else []
    if _BLOCK_HTTP:
        raise RuntimeError("Bright Data HTTP blocked while a call is active")
    _HTTP_CALLS += 1
    # Live path left unverified until H5; return empty rather than inventing.
    token = __import__("os").environ.get("BRIGHTDATA_API_TOKEN", "")
    zone = __import__("os").environ.get("BRIGHTDATA_SERP_ZONE", "")
    if not token or not zone:
        return []
    try:
        req = request.Request(
            "https://api.brightdata.com/request",
            data=json.dumps({"zone": zone, "url": "https://www.google.com/search?q=san+diego+smoke+fire&tbs=qdr:h",
                             "format": "json"}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read())
        return payload if isinstance(payload, list) else []
    except (OSError, error.URLError, ValueError, json.JSONDecodeError):
        return []
