"""Gemini text adapter for the handoff summary and the after-action draft.

Callers must strip phone numbers and names before calling. Mock mode and a missing key
return None, and each caller falls back to a deterministic template that says so.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from ..config import settings

PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def scrub(text: str) -> str:
    return PHONE.sub("[number removed]", text)


def generate_json(prompt: str, schema: dict[str, Any], timeout: float = 5.0) -> dict[str, Any] | None:
    if settings.mock:
        return None
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"
    body = {"contents": [{"parts": [{"text": scrub(prompt)}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read())
        return json.loads(raw["candidates"][0]["content"]["parts"][0]["text"])
    except (OSError, ValueError, KeyError, IndexError, TypeError, urllib.error.URLError):
        return None
