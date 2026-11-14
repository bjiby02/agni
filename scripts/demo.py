"""AGNI mock demo: runs the storyboard beats end to end against the real API code.

    make demo            # resets the practice database, then plays every beat
    make demo STEP=1     # wait for Enter between beats (for rehearsal on stage)

It uses the same SQLite file as `make dev`, so a console open on the dev server shows
every beat live. Mock mode only: nothing here calls a phone, Gemini or Bright Data.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("AGNI_MOCK", "1")
os.environ.setdefault("ELEVENLABS_TOOL_SECRET", "demo-local-secret")
if os.environ.get("AGNI_MOCK") != "1":
    sys.exit("make demo runs in mock mode only (AGNI_MOCK=1).")

from fastapi.testclient import TestClient  # noqa: E402
from agni import main  # noqa: E402

STEP = os.environ.get("STEP") == "1"
OPS = {"Authorization": f"Bearer {os.environ['OPERATOR_TOKEN']}"} if os.environ.get("OPERATOR_TOKEN") else {}


def beat(title: str) -> None:
    print(f"\n\033[1;36m▸ {title}\033[0m")
    if STEP:
        input("  (Enter) ")


def ok(label: str, response, expect: int = 200):
    if response.status_code != expect:
        raise SystemExit(f"  ✗ {label}: HTTP {response.status_code} {response.text[:300]}")
    print(f"  ✓ {label}")
    return response.json()


def wait_for(fn, what: str, timeout: float = 15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.2)
    raise SystemExit(f"  ✗ timed out waiting for {what}")


def main_demo() -> None:
    started = time.monotonic()
    with TestClient(main.app, client=("127.0.0.1", 50000)) as c:
        beat("0:00 Calm. Reset to Calm")
        r = ok("reset to calm", c.post("/api/ops/reset", headers=OPS))
        assert r["elapsed_s"] < 5, r

        beat("0:20 A Spanish call and a second caller (replay, labeled)")
        ok("replay started", c.post("/api/ops/replay", json={"name": "call_es", "speed": 4}, headers=OPS))
        state = lambda: c.get("/api/state", headers=OPS).json()
        merge = wait_for(lambda: next((m for m in state()["merges"] if m["state"] == "suggested"), None),
                         "the duplicate suggestion")
        print(f"  ✓ second report suggested as a duplicate ({round(merge['distance_m'])} m apart)")
        wait_for(lambda: state()["ops"]["mode"] != "replay", "the replay to finish")

        beat("0:50 Dispatcher accepts the merge; the two bearings cross")
        r = ok("merge accepted by dispatcher", c.post(f"/api/merges/{merge['id']}/accept", headers=OPS))
        iid = r["kept_id"]
        est = r.get("estimate")
        print(f"  {'✓ ' + est['label'] if est else '! bearings did not cross'}")
        cams = ok("camera wall", c.get("/api/cameras", params={"lat": 32.9, "lon": -117.19}, headers=OPS))
        print(f"    {cams['count']} cached stills" if cams["count"] else "    no cached stills: tiles show 'Replay not loaded' (gray)")

        beat("1:20 Evidence stack, then the human presses C")
        ev = ok("evidence rows", c.get(f"/api/incidents/{iid}/evidence", headers=OPS))
        for row in ev["rows"]:
            print(f"    · {row['source']}: {row['state']} · {row.get('detail')}")
        ok("confirm (C)", c.post(f"/api/incidents/{iid}/confirm", json={"actor": "dispatcher"}, headers=OPS))

        beat("1:40 Route around the closure, downwind shelter refused, approve twice")
        route = ok("route", c.get(f"/api/incidents/{iid}/route", headers=OPS))
        print(f"    recommended {route['recommended_unit']} · avoids {route['avoids'] or 'nothing'}")
        print(f"    shelter {route['shelter']['name'] if route['shelter'] else route['shelter_note']}"
              f" · refused {[x['name'] for x in route['refused']] or 'none'}")
        key = str(uuid.uuid4())
        body = {"unit_id": route["recommended_unit"], "approved_by": "dispatcher"}
        d1 = ok("approve (A)", c.post(f"/api/incidents/{iid}/dispatch", json=body, headers={**OPS, "Idempotency-Key": key}))
        d2 = ok("approve again (A)", c.post(f"/api/incidents/{iid}/dispatch", json=body, headers={**OPS, "Idempotency-Key": key}))
        assert d2.get("replayed") and d1["dispatch_id"] == d2["dispatch_id"]
        print(f"    one dispatch · buzzer {d1['buzzer']}")

        beat("2:10 Jump in: the human takes the Spanish call, then hands it back")
        h = ok("takeover (J)", c.post("/api/calls/replay-es-1/takeover", json={"actor": "dispatcher"}, headers=OPS))
        print(f"    summary: {h['summary']}")
        g = c.post("/api/tools/get_guidance", json={"conversation_id": "replay-es-1"},
                   headers={"X-Agni-Tool-Secret": os.environ["ELEVENLABS_TOOL_SECRET"]}).json()
        assert g["should_transfer"] is True
        print("    agent told should_transfer=true")
        b = ok("hand back", c.post("/api/calls/replay-es-1/handback", json={"actor": "dispatcher"}, headers=OPS))
        print(f"    resumed_by {b['resumed_by']} · callback {b['callback']}")

        beat("2:30 One more thing: spread ring and W")
        ring = ok("30-min ring", c.post(f"/api/incidents/{iid}/ring", json={"minutes": 30, "wind_to_deg": 200}, headers=OPS))
        print(f"    {ring['label']}")
        w = ok("warn (W)", c.post(f"/api/warnings/{iid}", json={"languages": ["es", "en"]},
                                  headers={**OPS, "Idempotency-Key": str(uuid.uuid4())}))
        print(f"    {w['recipients']} opted-in homes · dial {w['dial']}")
        resc = ok("practice home presses 1", c.post("/api/ops/press1", json={"warning_id": w["warning_id"],
                                                                             "home_id": w["recipient_ids"][0]}, headers=OPS))
        print(f"    {resc['say']}")

        beat("2:50 After-action with the measured clock")
        rep = ok("close incident", c.post(f"/api/incidents/{iid}/close", headers=OPS))
        for line in rep["draft"]:
            print(f"    {line}")
        signed = ok("dispatcher signs", c.post(f"/api/incidents/{iid}/report/sign", json={"actor": "dispatcher"}, headers=OPS))
        print(f"    log sha256 {signed['log_sha256'][:16]}… · signal to dispatch {signed['clock_s']} s (practice replay timing)")
        proof = c.get("/api/proof", headers=OPS).json()
        print(f"    proof panel: eval {'measured' if proof['eval'] else 'not measured yet'} · surge {'measured' if proof['sim'] else 'not measured yet'}")
    print(f"\n\033[1;32mDemo finished in {time.monotonic() - started:.1f} s. A human made every call.\033[0m")


if __name__ == "__main__":
    main_demo()
