"""Offline 75-call surge rehearsal. It uses a separate SQLite file, never main."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agni import bus, db, merge  # noqa: E402

CENTERS = [
    (32.895, -117.203, "Smoke near North Creek"),
    (32.870, -117.235, "Flames by canyon trail"),
    (32.925, -117.175, "Smoke by eastern ridge"),
    (32.850, -117.215, "Smoke over the southern mesa"),
]


def run(n: int = 75, max_seconds: int = 90, output: Path | None = None) -> dict:
    if n < len(CENTERS):
        raise ValueError(f"The surge needs at least {len(CENTERS)} calls")
    output = output or ROOT / "backend" / "sim" / "sim.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    previous, previous_url = db.DB_PATH, db.DATABASE_URL
    surge_url = os.environ.get("DATABASE_URL_SURGE", "").strip()
    if surge_url and surge_url == os.environ.get("DATABASE_URL", "").strip():
        raise ValueError("DATABASE_URL_SURGE points at the main database. The surge never runs on main.")
    with tempfile.TemporaryDirectory() as temp:
        # Neon surge-sim branch when configured, otherwise a throwaway SQLite file. Never main.
        db.DB_PATH = Path(temp) / "agni-surge-sim.sqlite"
        db.DATABASE_URL = surge_url
        try:
            db.init()
            if surge_url:
                from agni import ops
                ops.reset_to_calm()  # same start every run, so two runs end with the same numbers
            started = time.monotonic()
            start_time = datetime.now(timezone.utc).replace(microsecond=0)
            accepted_merges = 0
            for index in range(n):
                center = CENTERS[index % len(CENTERS)]
                lat = center[0] + ((index % 5) - 2) * 0.00035
                lon = center[1] + ((index % 7) - 3) * 0.00035
                incident_id = f"inc_surge_{index:03d}"
                call_id = f"surge_call_{index:03d}"
                created_at = (start_time + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
                with db.connect() as conn:
                    conn.execute(
                        "INSERT INTO incidents(id,status,level,kind,title,lat,lon,location_src,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        (incident_id, "possible", 3, "fire", center[2], lat, lon, "replay", created_at),
                    )
                    conn.execute("INSERT INTO calls(id,incident_id,direction,language,landmark_text) VALUES(?,?,'inbound','en','surge fixture')",
                                 (call_id, incident_id))
                bus.emit("call.started", incident_id, {"call_id": call_id, "direction": "inbound", "language": "en"})
                bus.emit("incident.created", incident_id, {"title": center[2], "location_src": "replay", "lat": lat, "lon": lon})
                suggested = merge.suggest_for_incident(incident_id)
                if suggested:
                    merge.accept(suggested["merge_id"], "human:surge-script")
                    accepted_merges += 1
            duration_s = round(time.monotonic() - started, 3)
            visible_incidents = len(db.state()["incidents"])
            result = {
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "branch": ("neon:surge-sim" if "neon.tech" in surge_url else "postgres:surge") if surge_url else "surge-sim-local",
                "calls": n,
                "visible_incidents": visible_incidents,
                "accepted_merges": accepted_merges,
                "duration_s": duration_s,
                "target_seconds": max_seconds,
                "within_target": duration_s <= max_seconds,
            }
        finally:
            db.DB_PATH, db.DATABASE_URL = previous, previous_url
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=75)
    parser.add_argument("--seconds", type=int, default=90)
    parser.add_argument("--out", type=Path, default=ROOT / "backend" / "sim" / "sim.json")
    args = parser.parse_args()
    print(json.dumps(run(args.n, args.seconds, args.out), indent=2))
