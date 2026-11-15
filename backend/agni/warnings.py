"""Targeted warning selection. This module never dials a phone number."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WARN_LIST = Path(os.environ.get("AGNI_WARN_LIST", ROOT / "seed" / "warn_list.json"))


def opted_in_contacts() -> list[dict[str, Any]]:
    try:
        raw = json.loads(WARN_LIST.read_text(encoding="utf-8"))
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
        row = {**item, "phone": item["phone"].strip()}
        try:
            row["lat"] = float(item["lat"])
            row["lon"] = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            # SMS-only opt-ins may omit coordinates.
            row["lat"] = None
            row["lon"] = None
        contacts.append(row)
    return contacts


def phone_opted_in(phone: str | None) -> bool:
    """True only when the exact E.164 number is on the opt-in warn list."""
    if not phone or not isinstance(phone, str):
        return False
    want = phone.strip()
    if not want.startswith("+"):
        return False
    return any(c.get("phone") == want for c in opted_in_contacts())


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
