"""Gemini camera triage. Results suggest priority only; they never confirm a fire."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .config import settings

CACHE_SECONDS = 120
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

SCHEMA = {
    "type": "OBJECT", "properties": {
        "label": {"type": "STRING", "enum": ["smoke", "flames", "no_smoke", "cant_tell"]},
        "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}, "nullable": True},
        "flames_visible": {"type": "BOOLEAN"}, "reason": {"type": "STRING"},
        "recommended_level": {"type": "INTEGER", "minimum": 1, "maximum": 5},
    }, "required": ["label", "flames_visible", "reason", "recommended_level"],
}


def clear_cache() -> None:
    _CACHE.clear()


def _unknown(reason: str, status: str) -> dict[str, Any]:
    return {"label": "cant_tell", "box_2d": None, "flames_visible": False,
            "reason": reason, "recommended_level": None, "status": status}


def normalize_box(box: Any) -> list[float] | None:
    """Convert Gemini [ymin,xmin,ymax,xmax] 0..1000 into [x0,y0,x1,y1] 0..1."""
    if not isinstance(box, list) or len(box) != 4:
        return None
    try:
        ymin, xmin, ymax, xmax = (float(value) for value in box)
    except (TypeError, ValueError):
        return None
    if min(ymin, xmin, ymax, xmax) < 0 or max(ymin, xmin, ymax, xmax) > 1000:
        return None
    if xmin >= xmax or ymin >= ymax:
        return None
    return [round(xmin / 1000, 4), round(ymin / 1000, 4), round(xmax / 1000, 4), round(ymax / 1000, 4)]


def _normalise(result: dict[str, Any]) -> dict[str, Any]:
    label = result.get("label")
    if label not in {"smoke", "flames", "no_smoke", "cant_tell"}:
        return _unknown("Gemini returned an unsupported camera verdict", "invalid_response")
    recommended = result.get("recommended_level")
    if not isinstance(recommended, int) or not 1 <= recommended <= 5:
        recommended = None
    return {
        "label": label,
        "box_2d": normalize_box(result.get("box_2d")),
        "flames_visible": bool(result.get("flames_visible", False)),
        "reason": str(result.get("reason") or "No reason supplied")[:240],
        "recommended_level": recommended,
        "status": result.get("status", "assessed"),
    }


def _assess_uncached(image: bytes, mime_type: str) -> dict[str, Any]:
    if settings.mock:
        return _unknown("Mock mode has no verified camera verdict", "mock")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return _unknown("Gemini key not set", "key_not_set")
    body = {
        "contents": [{"parts": [
            {"text": "Look for visible smoke or flames. If unclear, return cant_tell. Do not infer location or identity. Return a reason in 20 words or less."},
            {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image).decode("ascii")}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0},
    }
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = json.loads(response.read())
        result = json.loads(raw["candidates"][0]["content"]["parts"][0]["text"])
        result["status"] = "live-unverified"
        return _normalise(result)
    except (OSError, ValueError, KeyError, IndexError, TypeError, urllib.error.URLError):
        return _unknown("Gemini could not assess this frame", "unavailable")


def assess(image: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
    key = hashlib.sha256(mime_type.encode() + image).hexdigest()
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        return {**hit[1], "cache": "hit"}
    result = _normalise(_assess_uncached(image, mime_type))
    _CACHE[key] = (now, result)
    return {**result, "cache": "miss"}
