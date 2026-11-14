"""ElevenLabs Agents adapter: outbound callback and batch warning calls.

Endpoint shapes follow the ElevenLabs docs and are LIVE-UNVERIFIED until a real call passes.
Mock mode never dials. Every outbound number must be on the opt-in list or be the caller
who phoned us (a callback), and the check happens here, in one place.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ..config import settings
from . import outbox

API = "https://api.elevenlabs.io/v1/convai"


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return {"status": "key_not_set"}
    req = urllib.request.Request(f"{API}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"status": "live-unverified", "response": json.loads(resp.read() or b"{}")}
    except (urllib.error.URLError, OSError, ValueError) as error:
        return {"status": "failed", "error": str(error)[:200]}


def callback(call_id: str, phone: str, dynamic: dict[str, Any]) -> dict[str, Any]:
    """Hand-back: after a warm transfer the agent is off the line, so AGNI calls the caller back."""
    body = {"agent_id": os.environ.get("ELEVENLABS_AGENT_ID", ""),
            "agent_phone_number_id": os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", ""),
            "to_number": phone,
            "conversation_initiation_client_data": {"dynamic_variables": dynamic}}
    if settings.mock:
        outbox.record("callback", f"call:{call_id}", {k: v for k, v in body.items() if k != "to_number"}, "mock")
        return {"status": "mock"}
    result = _post("/twilio/outbound-call", body)
    outbox.record("callback", f"call:{call_id}", {"agent_id": body["agent_id"]}, result["status"])
    return result


def batch_warning(warning_id: int, recipients: list[dict[str, Any]], dynamic: dict[str, Any]) -> dict[str, Any]:
    """Reverse-911 batch. Callers pass only opted-in contacts; we re-check the flag here anyway."""
    allowed = [r for r in recipients if r.get("opted_in") and isinstance(r.get("phone"), str)]
    refused = len(recipients) - len(allowed)
    body = {"call_name": f"agni-warning-{warning_id}",
            "agent_id": os.environ.get("ELEVENLABS_WARN_AGENT_ID", ""),
            "agent_phone_number_id": os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", ""),
            "recipients": [{"phone_number": r["phone"],
                            "conversation_initiation_client_data": {"dynamic_variables": {
                                **dynamic, "language": r.get("lang", "en"), "home_id": str(r.get("id", ""))}}}
                           for r in allowed]}
    if settings.mock:
        outbox.record("warning_batch", f"warning:{warning_id}",
                      {"recipients": len(allowed), "refused": refused, "dynamic": dynamic}, "mock")
        return {"status": "mock", "recipients": len(allowed), "refused": refused}
    result = _post("/batch-calling/submit", body)
    outbox.record("warning_batch", f"warning:{warning_id}", {"recipients": len(allowed), "refused": refused}, result["status"])
    return {**result, "recipients": len(allowed), "refused": refused}
