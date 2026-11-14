"""Landmark extraction and cache matching. Coordinates must come from a record."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import settings

ROOT = Path(__file__).resolve().parents[2]
LANDMARKS_FILE = Path(os.environ.get("AGNI_LANDMARKS_FILE", ROOT / "seed" / "landmarks.json"))


def _clean(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def cached_landmarks() -> list[dict[str, Any]]:
    try:
        raw = json.loads(LANDMARKS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []


def match_landmark(text: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Return a cached record only after a full alias/name match."""
    query = _clean(text)
    if not query:
        return None
    rows = cached_landmarks() if rows is None else rows
    matches = []
    for row in rows:
        aliases = row.get("aliases") or []
        names = [row.get("name", ""), *aliases]
        for name in names:
            normalized = _clean(str(name))
            if normalized and (normalized in query or query in normalized):
                # The shortest matching phrase is the narrowest identification.
                matches.append((len(normalized), row))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    candidate = matches[0][1]
    try:
        lat, lon = float(candidate["lat"]), float(candidate["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {**candidate, "lat": lat, "lon": lon}


def extract_landmark(spoken: str) -> dict[str, Any]:
    """Extract location words only. Gemini cannot return coordinates."""
    if settings.mock:
        return {"text": spoken[:300].strip(), "status": "mock"}
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return {"text": spoken[:300].strip(), "status": "key_not_set"}
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    body = {
        "contents": [{"parts": [{"text": (
            "Extract only the place or landmark words from this caller statement. "
            "Do not return coordinates, an address guess, a person's name, or other details. "
            "If no place is named, return an empty string. Caller statement: " + spoken[:300]
        )}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {"type": "OBJECT", "properties": {"landmark_text": {"type": "STRING"}},
                                "required": ["landmark_text"]},
            "temperature": 0,
        },
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = json.loads(response.read())
        result = json.loads(raw["candidates"][0]["content"]["parts"][0]["text"])
        text = str(result.get("landmark_text", ""))[:300].strip()
        return {"text": text, "status": "live-unverified"}
    except (OSError, ValueError, KeyError, IndexError, TypeError, urllib.error.URLError):
        return {"text": "", "status": "unavailable"}
