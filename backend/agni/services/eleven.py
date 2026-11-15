"""ElevenLabs outbound / transfer helpers. Mock never places a call."""
from __future__ import annotations

import os
from typing import Any

from ..config import settings

_OUTBOUND: list[dict[str, Any]] = []


def clear() -> None:
    _OUTBOUND.clear()


def outbound_log() -> list[dict[str, Any]]:
    return list(_OUTBOUND)


def transfer_to_dispatcher(conversation_id: str, summary: str) -> dict[str, Any]:
    target = os.environ.get("DISPATCHER_PHONE_NUMBER", "")
    record = {
        "action": "transfer",
        "conversation_id": conversation_id,
        "to": target or None,
        "summary": summary,
        "mode": "mock" if settings.mock else "live-unverified",
    }
    _OUTBOUND.append(record)
    if settings.mock or not target:
        return {**record, "ok": True, "placed": False,
                "reason": "mock" if settings.mock else "DISPATCHER_PHONE_NUMBER not set"}
    return {**record, "ok": True, "placed": False, "reason": "live path unverified"}


def callback_caller(conversation_id: str, to_number: str | None, context: dict[str, Any]) -> dict[str, Any]:
    record = {
        "action": "callback",
        "conversation_id": conversation_id,
        "to": to_number,
        "context": context,
        "mode": "mock" if settings.mock else "live-unverified",
    }
    _OUTBOUND.append(record)
    return {**record, "ok": True, "placed": False, "mode": record["mode"]}


def batch_warning_calls(recipients: list[dict[str, Any]], message_key: str) -> dict[str, Any]:
    record = {
        "action": "warning_batch",
        "recipients": len(recipients),
        "message_key": message_key,
        "mode": "mock" if settings.mock else "live-unverified",
    }
    _OUTBOUND.append(record)
    return {**record, "ok": True, "placed": False}
