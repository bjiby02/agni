"""Suggest possible duplicate reports. This module never accepts a merge."""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from . import bus, db
import geo

MAX_DISTANCE_M = 800
MAX_AGE_S = 20 * 60


def eligible(first: dict[str, Any], second: dict[str, Any]) -> tuple[bool, float, int]:
    """Return whether two located incidents can be suggested for review."""
    if first.get("lat") is None or first.get("lon") is None or second.get("lat") is None or second.get("lon") is None:
        return False, 0.0, 0
    try:
        a = datetime.fromisoformat(str(first["created_at"]).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(second["created_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False, 0.0, 0
    age_s = abs(round((a - b).total_seconds()))
    distance_m = geo.haversine_m(float(first["lat"]), float(first["lon"]), float(second["lat"]), float(second["lon"]))
    return distance_m <= MAX_DISTANCE_M and age_s <= MAX_AGE_S, distance_m, age_s


def suggest_for_incident(incident_id: str) -> dict[str, Any] | None:
    new = db.incident(incident_id)
    if not new or new.get("merged_into") or new.get("lat") is None or new.get("lon") is None:
        return None
    with db.connect() as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT * FROM incidents WHERE id!=? AND merged_into IS NULL "
            "AND status NOT IN ('closed','rejected') AND lat IS NOT NULL AND lon IS NOT NULL",
            (incident_id,),
        )]
    candidates = []
    for old in rows:
        ok, distance, age_s = eligible(new, old)
        if ok:
            candidates.append((distance, age_s, old))
    if not candidates:
        return None
    distance, age_s, old = min(candidates, key=lambda row: row[0])
    # Keep the older incident as the suggested survivor. A dispatcher decides.
    new_time = datetime.fromisoformat(str(new["created_at"]).replace("Z", "+00:00"))
    old_time = datetime.fromisoformat(str(old["created_at"]).replace("Z", "+00:00"))
    kept, merged = (old, new) if old_time <= new_time else (new, old)
    with db.connect() as conn:
        prior = conn.execute("SELECT id FROM merges WHERE kept_id=? AND merged_id=? AND state='suggested'",
                             (kept["id"], merged["id"])).fetchone()
        if prior:
            return {"merge_id": prior["id"], "kept_id": kept["id"], "merged_id": merged["id"],
                    "distance_m": round(distance), "dt_s": age_s}
        cur = conn.execute("INSERT INTO merges(kept_id,merged_id,distance_m,dt_s,state) VALUES(?,?,?,?,'suggested')",
                           (kept["id"], merged["id"], distance, age_s))
        merge_id = cur.lastrowid
    data = {"merge_id": merge_id, "kept_id": kept["id"], "merged_id": merged["id"],
            "distance_m": round(distance), "dt_s": age_s,
            "reason": "Reports are close in time and location. Dispatcher review required."}
    bus.emit("incident.merge_suggested", kept["id"], data)
    return data


def accept(merge_id: int, actor: str) -> dict[str, Any]:
    """Apply one explicit dispatcher decision and hide the absorbed incident."""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
        if not row:
            raise LookupError("Merge suggestion not found")
        if row["state"] != "suggested":
            raise ValueError("Merge suggestion is no longer pending")
        conn.execute("UPDATE merges SET state='accepted',decided_by=? WHERE id=?", (actor, merge_id))
        conn.execute("UPDATE incidents SET merged_into=? WHERE id=?", (row["kept_id"], row["merged_id"]))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (row["kept_id"], actor, "merge_accept",
                      json.dumps({"merge_id": merge_id, "merged_id": row["merged_id"]})))
    data = {"merge_id": merge_id, "kept_id": row["kept_id"], "merged_id": row["merged_id"], "accepted_by": actor}
    bus.emit("incident.merged", row["kept_id"], data)
    return data


def keep_apart(merge_id: int, actor: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
        if not row:
            raise LookupError("Merge suggestion not found")
        if row["state"] != "suggested":
            raise ValueError("Merge suggestion is no longer pending")
        conn.execute("UPDATE merges SET state='kept_apart',decided_by=? WHERE id=?", (actor, merge_id))
    data = {"merge_id": merge_id, "incident_id": row["merged_id"], "kept_apart_by": actor}
    bus.emit("incident.created", row["merged_id"], data)
    return data


def undo(merge_id: int, actor: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
        if not row:
            raise LookupError("Merge not found")
        if row["state"] != "accepted":
            raise ValueError("Only an accepted merge can be undone")
        conn.execute("UPDATE merges SET state='undone',decided_by=?,undone_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (actor, merge_id))
        conn.execute("UPDATE incidents SET merged_into=NULL WHERE id=? AND merged_into=?",
                     (row["merged_id"], row["kept_id"]))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (row["kept_id"], actor, "merge_undo",
                      json.dumps({"merge_id": merge_id, "restored_id": row["merged_id"]})))
    data = {"merge_id": merge_id, "restored_id": row["merged_id"], "actor": actor}
    bus.emit("incident.created", row["merged_id"], data)
    return data
