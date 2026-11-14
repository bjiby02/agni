"""Targeted warning selection. This module never dials a phone number."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WARN_LIST = Path(os.environ.get("AGNI_WARN_LIST", ROOT / "seed" / "warn_list.json"))


MOCK_WARN_LIST = ROOT / "backend" / "tests" / "fixtures" / "warn_list.mock.json"


def _source() -> Path:
    """Practice mode falls back to fake 555 numbers when the real opt-in list is empty."""
    from .config import settings
    try:
        empty = not json.loads(WARN_LIST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        empty = True
    return MOCK_WARN_LIST if settings.mock and empty else WARN_LIST


def opted_in_contacts() -> list[dict[str, Any]]:
    try:
        raw = json.loads(_source().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    contacts = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("opted_in"):
            continue
        if not isinstance(item.get("phone"), str) or not item["phone"].strip():
            continue
        try:
            contacts.append({**item, "lat": float(item["lat"]), "lon": float(item["lon"])})
        except (KeyError, TypeError, ValueError):
            continue
    return contacts


def _inside(point_lon: float, point_lat: float, polygon: list[list[float]]) -> bool:
    contained = False
    for index, current in enumerate(polygon):
        previous = polygon[index - 1]
        current_lon, current_lat = current
        previous_lon, previous_lat = previous
        crosses = (current_lat > point_lat) != (previous_lat > point_lat)
        if crosses:
            slope_lon = (previous_lon - current_lon) * (point_lat - current_lat) / (previous_lat - current_lat) + current_lon
            if point_lon < slope_lon:
                contained = not contained
    return contained


def targeted_contacts(ring: dict[str, Any], contacts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return only opted-in contacts inside the human-reviewed estimate ring."""
    contacts = opted_in_contacts() if contacts is None else contacts
    polygon = ring["geometry"]["coordinates"][0]
    return [contact for contact in contacts if contact.get("opted_in") and _inside(contact["lon"], contact["lat"], polygon)]
