"""Station buzzer over USB serial. Sends one 'D' byte per approved dispatch.

The fake records bytes so tests can count writes. With no SERIAL_PORT or no pyserial,
the write is skipped quietly: the demo never depends on the Uno.
"""
from __future__ import annotations

import os

from ..config import settings
from . import outbox

WRITES: list[bytes] = []


def buzz(dispatch_id: int) -> str:
    port = os.environ.get("SERIAL_PORT", "").strip()
    if settings.mock or not port:
        WRITES.append(b"D")
        outbox.record("serial", port or "fake", {"byte": "D", "dispatch_id": dispatch_id}, "mock")
        return "mock"
    try:
        import serial  # type: ignore
    except ImportError:
        return "skipped_no_pyserial"
    try:
        with serial.Serial(port, int(os.environ.get("SERIAL_BAUD", "9600") or 9600), timeout=1) as link:
            link.write(b"D")
        outbox.record("serial", port, {"byte": "D", "dispatch_id": dispatch_id}, "sent")
        return "sent"
    except Exception as error:  # unplugged board: skip silently, record why
        outbox.record("serial", port, {"error": str(error)[:120]}, "skipped")
        return "skipped"
