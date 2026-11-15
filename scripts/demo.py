#!/usr/bin/env python3
"""Mock storyboard replay: signal → call → confirm → dispatch → jump → ring → warn → rescue → close."""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("AGNI_MOCK", "1")
os.environ.setdefault("ELEVENLABS_TOOL_SECRET", "mock-tool-secret")
# Use a fresh demo DB so the script is idempotent.
os.environ["AGNI_DB_PATH"] = str(ROOT / "data" / "agni-demo.sqlite")


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    os.environ["ELEVENLABS_TOOL_SECRET"] = os.environ.get("ELEVENLABS_TOOL_SECRET") or "mock-tool-secret"

    db_path = Path(os.environ["AGNI_DB_PATH"])
    if db_path.exists():
        db_path.unlink()

    from fastapi.testclient import TestClient
    from agni import db
    from agni import main as app_main
    from agni.services import serial_bridge
    from agni import pollers

    db.init()
    pollers.ensure_demo_hazards()
    serial_bridge.clear()
    client = TestClient(app_main.app)
    tool = {"X-Agni-Tool-Secret": os.environ["ELEVENLABS_TOOL_SECRET"]}

    def step(name: str, response) -> dict:
        if response.status_code >= 400:
            raise SystemExit(f"FAIL {name}: {response.status_code} {response.text}")
        print(f"OK  {name}")
        return response.json() if response.content else {}

    step("enable overflow", client.put("/api/settings", json={"overflow_enabled": True}))
    step("S1 signals", client.post("/api/ops/signals/refresh"))

    conv = f"demo_{uuid.uuid4().hex[:8]}"
    report = step("S2 report_fire", client.post("/api/tools/report_fire", headers=tool, json={
        "conversation_id": conv,
        "landmark_text": "behind the Vons, Carmel Valley",
        "what_seen": "smoke and ash",
        "language": "es",
        "lat": 32.866,
        "lon": -117.251,
    }))
    iid = report["incident_id"]
    assert iid, "overflow must create an incident"

    step("transcript", client.post("/api/calls/transcript", headers=tool, json={
        "conversation_id": conv, "speaker": "caller", "text": "Hay humo detras del Vons", "lang": "es",
    }))
    # Allow landmark background match (Vons Carmel Valley cache) to settle.
    for _ in range(20):
        item = client.get(f"/api/incidents/{iid}").json()
        if item.get("lat") is not None:
            break
        time.sleep(0.05)
    with db.connect() as conn:
        row = conn.execute("SELECT lat,lon FROM incidents WHERE id=?", (iid,)).fetchone()
        if row is None or row["lat"] is None:
            conn.execute(
                "UPDATE incidents SET lat=32.91,lon=-117.17,location_src='caller',why_line=? WHERE id=?",
                ("Caller landmark · Vons Carmel Valley", iid),
            )
        else:
            conn.execute(
                "UPDATE incidents SET why_line=? WHERE id=? AND (why_line IS NULL OR why_line='')",
                ("Caller landmark · Vons Carmel Valley", iid),
            )
        pin = conn.execute("SELECT lat,lon FROM incidents WHERE id=?", (iid,)).fetchone()
    pin_lat, pin_lon = float(pin["lat"]), float(pin["lon"])

    step("bearing", client.post("/api/tools/add_bearing", headers=tool, json={
        "conversation_id": conv, "direction_words": "north",
        "lat": pin_lat - 0.01, "lon": pin_lon - 0.01, "bearing_deg": 0,
    }))
    step("bearing2", client.post("/api/tools/add_bearing", headers=tool, json={
        "conversation_id": conv, "direction_words": "east",
        "lat": pin_lat + 0.01, "lon": pin_lon - 0.01, "bearing_deg": 90,
    }))
    step("needs", client.post("/api/tools/set_needs", headers=tool, json={
        "conversation_id": conv, "mobility": True, "people": 2,
    }))

    step("confirm", client.post(f"/api/incidents/{iid}/confirm", json={"actor": "dispatcher", "note": "demo"}))
    route = step("route", client.get(f"/api/incidents/{iid}/route"))
    unit = (route.get("units") or [{}])[0].get("unit_id") or "E42"
    disp = step("dispatch", client.post(
        f"/api/incidents/{iid}/dispatch",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"unit_id": unit, "approved_by": "dispatcher"},
    ))
    serial_bytes = (disp.get("serial") or {}).get("bytes", "")
    if not serial_bytes.startswith("D"):
        raise SystemExit(f"FAIL serial buzz missing: {disp.get('serial')}")
    if not serial_bridge.recorded():
        raise SystemExit("FAIL serial bridge recorded no writes")

    jump = step("JUMP IN", client.post(f"/api/incidents/{iid}/jump-in", json={"actor": "dispatcher"}))
    assert jump.get("summary"), "handoff summary required"
    back = step("hand-back", client.post(f"/api/incidents/{iid}/hand-back", json={"actor": "dispatcher"}))
    assert back.get("resumed_by") == "agent"

    # Warning homes are seeded near the Vons landmark. Bearing estimates can drift the pin;
    # re-anchor to the landmark before the ring so opted-in contacts fall inside.
    from agni import warnings as warning_mod
    from agni import landmarks as landmark_mod
    match = landmark_mod.match_landmark("behind the Vons, Carmel Valley") or warning_mod.opted_in_contacts()[0]
    with db.connect() as conn:
        conn.execute(
            "UPDATE incidents SET lat=?,lon=?,location_src='caller' WHERE id=?",
            (float(match["lat"]), float(match["lon"]), iid),
        )
    step("ring", client.post(f"/api/incidents/{iid}/ring", json={"minutes": 30, "wind_to_deg": 135}))
    warn = step("warning", client.post(
        f"/api/warnings/{iid}",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"languages": ["en", "es"], "message_key": "wildfire_targeted_warning"},
    ))
    assert warn.get("recipients", 0) >= 1

    rescue_conv = f"warn_{uuid.uuid4().hex[:8]}"
    with db.connect() as conn:
        conn.execute("INSERT INTO calls(id,incident_id,direction,language,state) VALUES(?,?,'outbound_warning','en','live')",
                     (rescue_conv, iid))
    step("rescue", client.post("/api/tools/request_rescue", headers=tool, json={
        "conversation_id": rescue_conv, "digits": "1", "said_help": False,
    }))

    step("sign close", client.post(f"/api/incidents/{iid}/report/sign", json={"actor": "dispatcher", "edits": ""}))
    proof = step("proof", client.get("/api/proof"))
    print("Proof panel:", "sim measured" if proof.get("sim") else "sim not measured yet",
          "/", "eval measured" if proof.get("eval") else "eval not measured yet")
    print("Demo storyboard path completed in mock mode.")
    return 0


if __name__ == "__main__":
    started = time.time()
    code = main()
    print(f"Elapsed {time.time() - started:.2f}s")
    sys.exit(code)
