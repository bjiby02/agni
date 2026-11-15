"""Caller camera page: one-time links that expire in 30 minutes.

The page uploads one JPEG plus the phone's compass heading. The heading becomes a bearing,
the frame goes to Gemini triage, and an unknown verdict never changes priority.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from . import bus, db, vision

TTL = timedelta(minutes=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(incident_id: str, call_id: str | None) -> dict[str, Any]:
    token = secrets.token_urlsafe(16)
    expires = (_now() + TTL).isoformat().replace("+00:00", "Z")
    with db.connect() as conn:
        conn.execute("INSERT INTO cam_tokens(token,incident_id,call_id,expires_at) VALUES(?,?,?,?)",
                     (token, incident_id, call_id, expires))
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return {"token": token, "expires_at": expires, "path": f"/#/sos/cam/{token}",
            "url": f"{base}/#/sos/cam/{token}" if base else None}


def lookup(token: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM cam_tokens WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["expired"] = datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00")) < _now()
    return item


def last_result(token: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT verdict_json,fetched_at FROM camera_frames WHERE token=? ORDER BY id DESC LIMIT 1",
                           (token,)).fetchone()
    return {**json.loads(row["verdict_json"]), "fetched_at": row["fetched_at"]} if row else None


def submit(token: str, image: bytes, mime: str, heading_deg: float | None, lat: float | None, lon: float | None,
           accuracy_m: float | None, recompute) -> dict[str, Any]:
    item = lookup(token)
    if not item:
        raise LookupError("Link not found")
    if item["expired"]:
        raise PermissionError("This link has expired")
    if item["used_at"]:
        raise PermissionError("This link was already used")
    iid = item["incident_id"]
    with db.connect() as conn:  # claim the token first so a double tap cannot upload twice
        claimed = conn.execute("UPDATE cam_tokens SET used_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE token=? AND used_at IS NULL",
                               (token,)).rowcount
    if not claimed:
        raise PermissionError("This link was already used")
    result = vision.assess(image, mime)
    with db.connect() as conn:
        inc = conn.execute("SELECT level FROM incidents WHERE id=?", (iid,)).fetchone()
        level = inc["level"] if inc else 3
        suggested = result.get("recommended_level")
        if result["label"] in {"smoke", "flames"} and isinstance(suggested, int):
            level = min(level, suggested)  # AI may only raise priority
            conn.execute("UPDATE incidents SET level=? WHERE id=?", (level, iid))
        conn.execute("INSERT INTO camera_frames(camera_id,source,incident_id,token,heading_deg,lat,lon,accuracy_m,verdict_json) "
                     "VALUES(NULL,'caller',?,?,?,?,?,?,?)",
                     (iid, token, heading_deg, lat, lon, accuracy_m, json.dumps(result)))
        conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail) VALUES(?,?,?,?)",
                     (iid, "cameras", "agree" if result["label"] in {"smoke", "flames"} else "empty",
                      "Caller photo · " + result["reason"]))
    estimate = None
    if heading_deg is not None and lat is not None and lon is not None:
        with db.connect() as conn:
            conn.execute("INSERT INTO bearings(incident_id,call_id,lat,lon,bearing_deg,direction_words,source) VALUES(?,?,?,?,?,?,?)",
                         (iid, item["call_id"], lat, lon, heading_deg, None, "compass"))
        bus.emit("bearing.added", iid, {"call_id": item["call_id"], "lat": lat, "lon": lon, "bearing_deg": heading_deg,
                                        "source": "compass"})
        estimate = recompute(iid)
    data = {"source": "caller_frame", "frame_source": "caller", "label": result["label"], "box": result.get("box_2d"),
            "reason": result["reason"], "status": result["status"], "applied_level": level}
    bus.emit("triage.result", iid, data)
    return {**data, "estimate": estimate}
