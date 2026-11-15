"""Bright Data crowd-signal adapter. Never called while a call is live."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..config import settings
from . import httputil

BACKEND = Path(__file__).resolve().parents[2]
FIXTURE = BACKEND / "tests" / "fixtures" / "serp_signals.json"

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


def _fixture_posts() -> list[dict[str, Any]]:
    try:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return raw if isinstance(raw, list) else []


def _normalize_serp(payload: Any) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("organic") or payload.get("results") or payload.get("body") or []
        if isinstance(rows, str):
            try:
                rows = json.loads(rows)
            except json.JSONDecodeError:
                rows = []
    else:
        rows = []
    if not isinstance(rows, list):
        return posts
    for row in rows[:40]:
        if not isinstance(row, dict):
            continue
        text = str(row.get("description") or row.get("snippet") or row.get("title") or row.get("text") or "")
        url = str(row.get("link") or row.get("url") or "")
        if not text:
            continue
        sid = hashlib.sha1((url or text).encode()).hexdigest()[:16]
        posts.append({"id": sid, "source": "serp", "url": url, "text": text, "lat": None, "lon": None})
    return posts


def fetch_serp_signals() -> list[dict[str, Any]]:
    """Return recent public fire-related posts."""
    global _HTTP_CALLS
    token = httputil.env("BRIGHTDATA_API_TOKEN")
    zone = httputil.env("BRIGHTDATA_SERP_ZONE")
    if settings.mock or not token or not zone:
        return _fixture_posts()
    if _BLOCK_HTTP:
        raise RuntimeError("Bright Data HTTP blocked while a call is active")
    _HTTP_CALLS += 1
    status, payload = httputil.request_json(
        "https://api.brightdata.com/request",
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        body={
            "zone": zone,
            "url": "https://www.google.com/search?q=san+diego+smoke+OR+wildfire&tbs=qdr:h&brd_json=1",
            "format": "raw",
        },
        timeout=20,
    )
    if status >= 300:
        return _fixture_posts()
    posts = _normalize_serp(payload)
    return posts or _fixture_posts()
