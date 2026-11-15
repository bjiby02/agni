"""Arduino Uno serial bridge. Mock records bytes; live writes USB when SERIAL_PORT is set."""
from __future__ import annotations

import os
from typing import Any

from ..config import settings

_WRITES: list[bytes] = []


def clear() -> None:
    _WRITES.clear()


def recorded() -> list[bytes]:
    return list(_WRITES)


def write_dispatch(unit_id: str) -> dict[str, Any]:
    """Send station buzz command like D42\\n for unit E42."""
    digits = "".join(ch for ch in unit_id if ch.isdigit()) or "00"
    payload = f"D{digits}\n".encode("ascii")
    _WRITES.append(payload)
    if settings.mock:
        return {"ok": True, "mode": "mock", "bytes": payload.decode("ascii"), "port": None}
    port = os.environ.get("SERIAL_PORT", "").strip()
    baud = int(os.environ.get("SERIAL_BAUD", "9600") or "9600")
    if not port:
        return {"ok": False, "mode": "live-unverified", "bytes": payload.decode("ascii"),
                "reason": "SERIAL_PORT not set"}
    try:
        import serial  # type: ignore
        with serial.Serial(port, baud, timeout=1) as ser:
            ser.write(payload)
        return {"ok": True, "mode": "live-unverified", "bytes": payload.decode("ascii"), "port": port}
    except Exception as error:  # noqa: BLE001 — hardware path must never crash dispatch
        return {"ok": False, "mode": "live-unverified", "bytes": payload.decode("ascii"),
                "reason": str(error)[:200]}
