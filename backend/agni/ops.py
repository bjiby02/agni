"""Demo controls: Reset to Calm, offline-safe mode and the practice hazard snapshot."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import bus, db

ROOT = Path(__file__).resolve().parents[2]
HAZARDS_SNAPSHOT = ROOT / "cache" / "hazards_demo.geojson"
LIVE_TABLES = ("incidents", "calls", "transcripts", "bearings", "evidence", "decisions", "dispatches", "merges",
               "rings", "warnings", "rescues", "handoffs", "transfer_requests", "reports", "outbox", "call_contacts",
               "cam_tokens", "camera_frames", "signals", "satellite_hits")


def load_hazard_snapshot() -> int:
    try:
        data = json.loads(HAZARDS_SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    count = 0
    with db.connect() as conn:
        for f in data.get("features", []):
            props = f.get("properties", {})
            coords = (f.get("geometry") or {}).get("coordinates") or [[None, None]]
            conn.execute("INSERT OR REPLACE INTO hazards(id,source,kind,title,geometry_json,lat,lon,observed_at,scraped_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?)",
                         (f["id"], props.get("source", "snapshot"), props.get("kind", "road_closure"), props.get("title"),
                          json.dumps(f.get("geometry")), coords[0][1], coords[0][0], props.get("scraped_at"),
                          props.get("scraped_at") or "unknown"))
            count += 1
    return count


def state() -> dict[str, Any]:
    with db.connect() as conn:
        return dict(conn.execute("SELECT mode,safe_mode,replay_label,updated_at FROM ops_state WHERE id=1").fetchone())


def set_mode(mode: str, label: str | None = None) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE ops_state SET mode=?,replay_label=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=1",
                     (mode, label))
    bus.emit("ops.mode", None, {**state(), "reset": False})


def set_safe_mode(on: bool) -> dict[str, Any]:
    with db.connect() as conn:
        conn.execute("UPDATE ops_state SET safe_mode=? WHERE id=1", (int(on),))
    current = state()
    bus.emit("ops.mode", None, {**current, "reset": False})
    return current


def reset_to_calm() -> dict[str, Any]:
    """Clear every incident and call, free the units, reload the hazard snapshot. Event seq keeps rising
    so connected consoles never mistake new events for ones they have already seen."""
    started = time.perf_counter()
    with db.connect() as conn:
        for table in LIVE_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM hazards")
        conn.execute("UPDATE units SET status='available'")
        conn.execute("UPDATE ops_state SET mode='calm',replay_label=NULL WHERE id=1")
    hazards = load_hazard_snapshot()
    elapsed = round(time.perf_counter() - started, 3)
    bus.emit("ops.mode", None, {**state(), "reset": True, "elapsed_s": elapsed})
    bus.emit("hazards.updated", None, {"count": hazards, "scraped_at": "practice snapshot", "source": "cache/hazards_demo.geojson"})
    return {"mode": "calm", "elapsed_s": elapsed, "hazards": hazards}
