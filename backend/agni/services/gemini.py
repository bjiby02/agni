"""Gemini helpers used outside vision.py (post classify, handoff summary, report draft)."""
from __future__ import annotations

import json
import os
from typing import Any

from ..config import settings


def classify_post(text: str) -> dict[str, Any]:
    """Classify a crowd post. Mock marks smoke/fire keywords as about_fire."""
    lowered = (text or "").lower()
    about = any(word in lowered for word in ("smoke", "fire", "flame", "wildfire", "brush"))
    if settings.mock or not os.environ.get("GEMINI_API_KEY"):
        return {
            "about_fire": about,
            "place_text": None,
            "confidence": "low" if about else "none",
            "status": "mock" if settings.mock else "key_not_set",
        }
    # Live path: keep shape; full structured call is LIVE-UNVERIFIED until H4.
    return {
        "about_fire": about,
        "place_text": None,
        "confidence": "unverified",
        "status": "live-unverified",
    }


def handoff_summary(transcript_lines: list[dict[str, Any]], incident: dict[str, Any] | None = None) -> str:
    """One-sentence dispatcher brief. Falls back to last transcript lines within 5 s budget."""
    if transcript_lines:
        last = " / ".join(
            f"{row.get('speaker', '?')}: {row.get('text', '')}" for row in transcript_lines[-3:]
        )
    else:
        last = "No transcript yet"
    title = (incident or {}).get("title") or "Possible fire"
    needs = ""
    if incident and incident.get("immobile"):
        needs = " Someone cannot walk."
    if settings.mock or not os.environ.get("GEMINI_API_KEY"):
        return f"{title}. {last}.{needs}".strip()[:280]
    return f"{title}. {last}.{needs}".strip()[:280]


def report_draft(events: list[dict[str, Any]], incident: dict[str, Any]) -> str:
    """Five-line after-action draft from measured events only."""
    lines = [
        f"Incident {incident.get('id')} · status {incident.get('status')}",
        f"Title: {incident.get('title') or 'untitled'}",
        f"Location src: {incident.get('location_src') or 'unknown'}",
        f"Events recorded: {len(events)}",
        "Human confirmation required for every dispatch and warning.",
    ]
    return "\n".join(lines)
