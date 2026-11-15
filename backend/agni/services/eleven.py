"""ElevenLabs outbound, transfer cue, and warning batch calls."""
from __future__ import annotations

import os
from typing import Any

from ..config import settings
from . import httputil

_OUTBOUND: list[dict[str, Any]] = []
_TRANSFER_FLAGS: dict[str, bool] = {}


def clear() -> None:
    _OUTBOUND.clear()
    _TRANSFER_FLAGS.clear()


def outbound_log() -> list[dict[str, Any]]:
    return list(_OUTBOUND)


def request_transfer(conversation_id: str, enabled: bool = True) -> None:
    """Agent reads this via get_guidance.should_transfer on its next turn."""
    _TRANSFER_FLAGS[conversation_id] = enabled


def should_transfer(conversation_id: str) -> bool:
    return bool(_TRANSFER_FLAGS.get(conversation_id))


def _live_ready() -> bool:
    return (not settings.mock) and httputil.keyed("ELEVENLABS_API_KEY")


def transfer_to_dispatcher(conversation_id: str, summary: str) -> dict[str, Any]:
    target = httputil.env("DISPATCHER_PHONE_NUMBER")
    request_transfer(conversation_id, True)
    record = {
        "action": "transfer",
        "conversation_id": conversation_id,
        "to": target or None,
        "summary": summary,
        "mode": "mock" if settings.mock else "live",
        "transfer_type": "twilio_warm_conference_transfer",
    }
    _OUTBOUND.append(record)
    if settings.mock or not target:
        return {**record, "ok": True, "placed": False,
                "reason": "mock" if settings.mock else "DISPATCHER_PHONE_NUMBER not set",
                "should_transfer": True}
    # Live path: agent performs transfer_to_number after should_transfer flips true.
    # Optional contextual update when conversation id + agent id are known.
    agent_id = httputil.env("ELEVENLABS_AGENT_ID")
    if _live_ready() and agent_id and conversation_id:
        status, payload = httputil.request_json(
            f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
            method="POST",
            headers={"xi-api-key": httputil.env("ELEVENLABS_API_KEY")},
            body={"conversation_initiation_client_data": {
                "dynamic_variables": {"dispatcher_summary": summary, "should_transfer": "true"},
            }},
            timeout=8,
        )
        # Some accounts only support agent tool transfer; treat non-2xx as soft failure.
        record["contextual_update"] = {"status": status, "payload": payload}
        record["placed"] = 200 <= status < 300
        record["ok"] = True
        record["reason"] = "transfer_flag_set" if record["placed"] else f"update_status_{status}"
        return record
    return {**record, "ok": True, "placed": False, "should_transfer": True,
            "reason": "should_transfer set; agent must call transfer_to_number"}


def callback_caller(conversation_id: str, to_number: str | None, context: dict[str, Any]) -> dict[str, Any]:
    record = {
        "action": "callback",
        "conversation_id": conversation_id,
        "to": to_number,
        "context": context,
        "mode": "mock" if settings.mock else "live",
    }
    _OUTBOUND.append(record)
    if settings.mock:
        return {**record, "ok": True, "placed": False, "mode": "mock"}
    if not _live_ready():
        return {**record, "ok": False, "placed": False, "reason": "ELEVENLABS_API_KEY not set"}
    agent_id = httputil.env("ELEVENLABS_AGENT_ID")
    phone_id = httputil.env("ELEVENLABS_PHONE_NUMBER_ID")
    if not agent_id or not phone_id or not to_number:
        return {**record, "ok": False, "placed": False,
                "reason": "Need ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID, and caller number"}
    status, payload = httputil.request_json(
        "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
        method="POST",
        headers={"xi-api-key": httputil.env("ELEVENLABS_API_KEY")},
        body={
            "agent_id": agent_id,
            "agent_phone_number_id": phone_id,
            "to_number": to_number,
            "conversation_initiation_client_data": {"dynamic_variables": context},
        },
        timeout=15,
    )
    placed = 200 <= status < 300
    return {**record, "ok": placed, "placed": placed, "http_status": status, "response": payload,
            "reason": None if placed else f"outbound_status_{status}"}


def batch_warning_calls(recipients: list[dict[str, Any]], message_key: str,
                        *, incident_id: str, direction: str | None = None,
                        shelter: str | None = None) -> dict[str, Any]:
    """Place warning batch to opt-in phones only. Caller must pre-filter the list."""
    record = {
        "action": "warning_batch",
        "recipients": len(recipients),
        "message_key": message_key,
        "mode": "mock" if settings.mock else "live",
        "incident_id": incident_id,
    }
    _OUTBOUND.append(record)
    if settings.mock:
        return {**record, "ok": True, "placed": False, "batch_id": f"mock-{incident_id}",
                "status": "mock_queued"}
    if not _live_ready():
        return {**record, "ok": False, "placed": False, "reason": "ELEVENLABS_API_KEY not set",
                "status": "blocked"}
    warn_agent = httputil.env("ELEVENLABS_WARN_AGENT_ID") or httputil.env("ELEVENLABS_AGENT_ID")
    phone_id = httputil.env("ELEVENLABS_PHONE_NUMBER_ID")
    if not warn_agent or not phone_id:
        return {**record, "ok": False, "placed": False,
                "reason": "ELEVENLABS_WARN_AGENT_ID and ELEVENLABS_PHONE_NUMBER_ID required",
                "status": "blocked"}
    payload_recipients = []
    for person in recipients:
        phone = str(person.get("phone") or "").strip()
        if not phone:
            continue
        payload_recipients.append({
            "phone_number": phone,
            "conversation_initiation_client_data": {
                "dynamic_variables": {
                    "language": person.get("language") or "en",
                    "direction": direction or "follow local guidance",
                    "shelter": shelter or "nearest open shelter",
                    "incident_id": incident_id,
                    "message_key": message_key,
                }
            },
        })
    if not payload_recipients:
        return {**record, "ok": False, "placed": False, "reason": "no dialable recipients",
                "status": "blocked"}
    status, payload = httputil.request_json(
        "https://api.elevenlabs.io/v1/convai/batch-calling/submit",
        method="POST",
        headers={"xi-api-key": httputil.env("ELEVENLABS_API_KEY")},
        body={
            "call_name": f"warn-{incident_id}",
            "agent_id": warn_agent,
            "agent_phone_number_id": phone_id,
            "recipients": payload_recipients,
        },
        timeout=20,
    )
    placed = 200 <= status < 300
    batch_id = None
    if isinstance(payload, dict):
        batch_id = payload.get("id") or payload.get("batch_call_id")
    if placed:
        return {**record, "ok": True, "placed": True, "batch_id": batch_id,
                "http_status": status, "response": payload, "status": "submitted"}
    # Fallback: single outbound calls
    results = []
    for person in payload_recipients:
        one = callback_caller(
            f"warn-{incident_id}",
            person["phone_number"],
            person["conversation_initiation_client_data"]["dynamic_variables"],
        )
        results.append(one)
    any_placed = any(item.get("placed") for item in results)
    return {**record, "ok": any_placed, "placed": any_placed, "batch_id": batch_id,
            "http_status": status, "response": payload, "fallback": results,
            "status": "fallback_outbound" if any_placed else f"batch_status_{status}"}
