"""Timed feeds: NWS wind (C8), NASA FIRMS satellite (C7), Bright Data posts (C4) and Caltrans closures (C7).

Each poll is a plain function, so /ops can run one on demand and tests can call it.
The timer loop starts with the API when AGNI_POLLERS=1, or by default when AGNI_MOCK=0.
Wi-Fi-safe mode keeps the last stored values and labels them with their age.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from typing import Any

from . import bus, db, brightdata, closures, ops
from .config import settings
import feeds
import geo

AREA = (float(os.environ.get("OPERATOR_AREA_LAT") or 32.88), float(os.environ.get("OPERATOR_AREA_LON") or -117.2))
EVERY_S = {"wind": 600, "satellite": 600, "signals": 180, "closures": 600}


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _record(name: str, status: str, detail: str = "") -> None:
    with db.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO poll_runs(name,status,detail,ran_at) VALUES(?,?,?,?)", (name, status, detail[:300], _stamp()))


def latest_wind() -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM wind_obs ORDER BY fetched_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {"station": row["station"], "observed_at": row["ts"], "from_deg": row["dir_deg"],
            "to_deg": (row["dir_deg"] + 180) % 360 if row["dir_deg"] is not None else None,
            "speed_mps": row["speed_mps"], "source": f"NWS {row['station']} · as of {row['ts']}"}


def poll_wind() -> dict[str, Any]:
    if settings.mock:
        _record("wind", "mock", "practice wind value in use")
        return {"status": "mock", "note": "Practice wind value in use; NWS is not called in mock mode."}
    if ops.state().get("safe_mode"):
        last = latest_wind()
        return {"status": "safe_mode", "wind": last}
    try:
        obs = feeds.wind(*AREA)
    except Exception as error:  # feed down: keep the last observation, labeled
        obs = None
        _record("wind", "failed", str(error))
    if not obs:
        last = latest_wind()
        return {"status": "unavailable", "wind": last, "label": f"Wind as of {last['observed_at']}" if last else "Wind not checked"}
    speed = round(obs["kph"] / 3.6, 1) if obs.get("kph") is not None else None
    with db.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO wind_obs(station,ts,dir_deg,speed_mps,fetched_at) VALUES(?,?,?,?,?)",
                     (obs["station"], _stamp(), obs["from_deg"], speed, _stamp()))
    data = {"station": obs["station"], "dir_deg": obs["from_deg"], "speed_mps": speed, "observed_at": _stamp()}
    bus.emit("wind.updated", None, data)
    _record("wind", "ok", json.dumps(data))
    return {"status": "ok", **data}


def poll_satellite() -> dict[str, Any]:
    """Match FIRMS detections within 2 km of each located open incident. No hit is gray, never green."""
    key_set = bool(os.environ.get("FIRMS_MAP_KEY"))
    with db.connect() as conn:
        incs = [dict(r) for r in conn.execute("SELECT id,lat,lon FROM incidents WHERE lat IS NOT NULL AND merged_into IS NULL "
                                             "AND status NOT IN ('closed','rejected')")]
    checked = _stamp()
    results = []
    for inc in incs:
        if settings.mock or not key_set:
            state, detail, hits = "empty", "Satellite not checked · " + ("practice mode" if settings.mock else "FIRMS key not set"), []
        else:
            try:
                rows = feeds.hotspots(inc["lat"], inc["lon"], span_deg=0.1, days=1)
            except Exception:
                rows = []
            hits = [r for r in rows if geo.haversine_m(inc["lat"], inc["lon"], r["lat"], r["lon"]) <= 2000]
            with db.connect() as conn:
                for h in hits:
                    hid = hashlib.sha256(f"{h['lat']},{h['lon']},{h['at']}".encode()).hexdigest()[:16]
                    conn.execute("INSERT OR REPLACE INTO satellite_hits(id,lat,lon,acq_time,confidence,source,checked_at) VALUES(?,?,?,?,?,?,?)",
                                 (hid, h["lat"], h["lon"], h["at"], h["confidence"], h.get("sat") or "VIIRS", checked))
            state = "agree" if hits else "empty"
            detail = (f"{len(hits)} VIIRS detection(s) within 2 km · latest {hits[0]['at']}" if hits
                      else f"No detection within 2 km · checked {checked[11:16]} UTC · satellite data can lag hours")
        with db.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail) VALUES(?,?,?,?)", (inc["id"], "firms", state, detail))
        bus.emit("satellite.result", inc["id"], {"hits": hits[:10], "checked_at": checked, "status": state, "detail": detail})
        results.append({"incident_id": inc["id"], "state": state, "detail": detail})
    _record("satellite", "ok", f"{len(results)} incidents")
    return {"status": "ok", "checked_at": checked, "incidents": results}


def poll_signals(force: bool = False) -> dict[str, Any]:
    result = brightdata.poll(force=force)
    _record("signals", result["status"], json.dumps(result))
    return result


def poll_closures(force: bool = False) -> dict[str, Any]:
    result = closures.poll(force=force)
    _record("closures", result["status"], json.dumps(result)[:500])
    return result


POLLS = {"wind": poll_wind, "satellite": poll_satellite, "signals": poll_signals, "closures": poll_closures}


def enabled() -> bool:
    flag = os.environ.get("AGNI_POLLERS", "").strip().lower()
    return flag in {"1", "true", "yes", "on"} if flag else not settings.mock


async def run_forever() -> None:
    last: dict[str, float] = {}
    while True:
        now = time.monotonic()
        for name, fn in POLLS.items():
            if now - last.get(name, -1e9) >= EVERY_S[name]:
                last[name] = now
                try:
                    await asyncio.to_thread(fn)
                except Exception as error:  # one bad feed must not stop the others
                    _record(name, "failed", str(error))
        await asyncio.sleep(5)
