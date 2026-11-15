"""Caller location: cache-first, then region-boxed geocode. Gemini never invents coords.

Why no pin before: resolve only matched seed/landmarks.json aliases. Phrases like
"Jacobs Call Center" missed the short cache → lat/lon stayed null → map stayed calm.

Order for a real map pin (never invent coordinates):
1) Tool/Twilio/client lat+lon → location_src=caller (immediate).
2) Cached landmark list (seed + optional Bright Data fixture + DB) → location_src=landmark.
3) Photon/Nominatim via geo.search, San Diego–boxed → location_src=geocode.
4) Else honest empty: UI "Location: not yet" — no fake pin.
"""
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
# Optional Bright Data landmark export — merge if present; do not fetch live (quota).
BD_LANDMARKS_FILE = Path(
    os.environ.get("AGNI_BD_LANDMARKS_FILE", ROOT / "seed" / "cached_landmarks.json")
)

# Default demo region: UCSD / La Jolla box (OPERATOR_AREA_* overrides via geo.bind_area).
SD_CENTER = (32.8801, -117.2340)
SD_BOX = {
    "lat_min": 32.70,
    "lat_max": 33.15,
    "lon_min": -117.45,
    "lon_max": -116.90,
}


def _clean(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _in_region(lat: float, lon: float) -> bool:
    return (
        SD_BOX["lat_min"] <= lat <= SD_BOX["lat_max"]
        and SD_BOX["lon_min"] <= lon <= SD_BOX["lon_max"]
    )


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []


def cached_landmarks() -> list[dict[str, Any]]:
    """Seed file first, then optional Bright Data fixture; later ids win on conflict."""
    by_id: dict[str, dict[str, Any]] = {}
    for path in (LANDMARKS_FILE, BD_LANDMARKS_FILE):
        for row in _load_json_list(path):
            key = str(row.get("id") or row.get("name") or "").strip()
            if not key:
                continue
            by_id[key] = row
    return list(by_id.values())


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
                # Longest matching phrase wins so "Torrey Pines High School"
                # beats the shorter alias "Torrey Pines" on the gliderport.
                matches.append((len(normalized), row))
    if not matches:
        return None
    matches.sort(key=lambda item: -item[0])
    candidate = matches[0][1]
    try:
        lat, lon = float(candidate["lat"]), float(candidate["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {**candidate, "lat": lat, "lon": lon, "location_src": "landmark"}


def _ensure_geo_area() -> None:
    import geo

    if geo.area_centre() is not None:
        return
    try:
        lat = float(os.environ.get("OPERATOR_AREA_LAT") or SD_CENTER[0])
        lon = float(os.environ.get("OPERATOR_AREA_LON") or SD_CENTER[1])
    except ValueError:
        lat, lon = SD_CENTER
    geo.bind_area(lat, lon)


def geocode_place(text: str) -> dict[str, Any] | None:
    """Region-boxed Photon/Nominatim. Offline mock → no network, no invented pin."""
    query = " ".join((text or "").split())
    if not query or len(query) < 3:
        return None
    if settings.mock:
        return None
    try:
        import geo
    except ImportError:
        return None
    _ensure_geo_area()
    try:
        hits = geo.search(query)
    except (LookupError, OSError, ValueError, TimeoutError):
        return None
    for hit in hits or []:
        try:
            lat, lon = float(hit.lat), float(hit.lon)
        except (TypeError, ValueError, AttributeError):
            continue
        if not _in_region(lat, lon):
            continue
        name = (getattr(hit, "name", None) or getattr(hit, "label", None) or query)[:200]
        return {
            "name": str(name),
            "lat": lat,
            "lon": lon,
            "location_src": "geocode",
            "source": "photon_nominatim",
            "kind": getattr(hit, "kind", None) or "geocode",
        }
    return None


def locate(spoken: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Cache match first; on miss, region geocode. Never invents coordinates."""
    match = match_landmark(spoken, rows=rows)
    if match:
        return match
    return geocode_place(spoken)


def seed_landmarks_table(conn: Any) -> int:
    """Upsert seed (+ optional BD fixture) into landmarks so SQL and file stay aligned."""
    rows = cached_landmarks()
    n = 0
    for row in rows:
        lid = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not lid or not name:
            continue
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        aliases = row.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        conn.execute(
            "INSERT INTO landmarks(id,name,aliases_json,kind,lat,lon,source,scraped_at) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, aliases_json=excluded.aliases_json, "
            "kind=excluded.kind, lat=excluded.lat, lon=excluded.lon, source=excluded.source",
            (
                lid,
                name,
                json.dumps(aliases, separators=(",", ":")),
                row.get("kind"),
                lat,
                lon,
                row.get("source") or "seed",
                row.get("scraped_at"),
            ),
        )
        n += 1
    return n


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
