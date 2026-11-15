"""Gemini helpers: post classify, handoff summary, report draft."""
from __future__ import annotations

import json
import os
from typing import Any

from ..config import settings
from . import httputil


def _model() -> str:
    return httputil.env("GEMINI_MODEL") or "gemini-2.5-flash"


def _generate(prompt: str, schema: dict[str, Any] | None = None, timeout: float = 5) -> dict[str, Any] | None:
    key = httputil.env("GEMINI_API_KEY")
    if not key or settings.mock:
        return None
    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }
    if schema:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = schema
    status, payload = httputil.request_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{_model()}:generateContent?key={key}",
        method="POST",
        body=body,
        timeout=timeout,
    )
    if status >= 300 or not isinstance(payload, dict):
        return None
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text) if schema else {"text": text}
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def classify_post(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    about = any(word in lowered for word in ("smoke", "fire", "flame", "wildfire", "brush"))
    if settings.mock or not httputil.env("GEMINI_API_KEY"):
        return {
            "about_fire": about,
            "place_text": None,
            "confidence": "low" if about else "none",
            "status": "mock" if settings.mock else "key_not_set",
        }
    schema = {
        "type": "OBJECT",
        "properties": {
            "about_fire": {"type": "BOOLEAN"},
            "place_text": {"type": "STRING", "nullable": True},
            "confidence": {"type": "STRING"},
        },
        "required": ["about_fire", "confidence"],
    }
    result = _generate(
        "Classify whether this public post is about an active wildfire or smoke near San Diego. "
        "Extract a place name if present. Do not invent coordinates.\n\n" + text[:1500],
        schema=schema,
        timeout=5,
    )
    if not result:
        return {"about_fire": about, "place_text": None, "confidence": "unverified",
                "status": "unavailable"}
    return {
        "about_fire": bool(result.get("about_fire")),
        "place_text": result.get("place_text"),
        "confidence": str(result.get("confidence") or "unverified")[:40],
        "status": "live",
    }


def handoff_summary(transcript_lines: list[dict[str, Any]], incident: dict[str, Any] | None = None) -> str:
    if transcript_lines:
        last = " / ".join(
            f"{row.get('speaker', '?')}: {row.get('text', '')}" for row in transcript_lines[-3:]
        )
    else:
        last = "No transcript yet"
    title = (incident or {}).get("title") or "Possible fire"
    needs = " Someone cannot walk." if incident and incident.get("immobile") else ""
    fallback = f"{title}. {last}.{needs}".strip()[:280]
    if settings.mock or not httputil.env("GEMINI_API_KEY"):
        return fallback
    result = _generate(
        "Write one sentence for a 911 dispatcher jumping into a live wildfire overflow call. "
        "Include location clue, language if known, and mobility needs. Max 40 words.\n"
        f"Incident: {json.dumps({k: incident.get(k) for k in ('id','title','why_line','immobile','lat','lon') if incident}, default=str)}\n"
        f"Transcript: {last}",
        timeout=5,
    )
    if result and result.get("text"):
        return str(result["text"]).strip()[:280]
    return fallback


def report_draft(events: list[dict[str, Any]], incident: dict[str, Any]) -> str:
    lines = [
        f"Incident {incident.get('id')} · status {incident.get('status')}",
        f"Title: {incident.get('title') or 'untitled'}",
        f"Location src: {incident.get('location_src') or 'unknown'}",
        f"Events recorded: {len(events)}",
        "Human confirmation required for every dispatch and warning.",
    ]
    fallback = "\n".join(lines)
    if settings.mock or not httputil.env("GEMINI_API_KEY"):
        return fallback
    clock = [f"{e.get('ts')} {e.get('type')}" for e in events[:40]]
    result = _generate(
        "Draft a five-line after-action report for a wildfire overflow desk. "
        "Use only the supplied event times. Do not invent metrics.\n"
        f"Incident: {json.dumps(incident, default=str)[:1200]}\nEvents:\n" + "\n".join(clock),
        timeout=8,
    )
    if result and result.get("text"):
        return str(result["text"]).strip()[:2000]
    return fallback
