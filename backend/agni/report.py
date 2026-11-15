"""After-action report: measured clock from event timestamps, a draft, a human signature,
and a SHA-256 of the canonical event log. Numbers are never typed in."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from . import bus, db
from .services import gemini

DRAFT_SCHEMA = {"type": "OBJECT", "properties": {"lines": {"type": "ARRAY", "items": {"type": "STRING"}}},
                "required": ["lines"]}


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def incident_log(iid: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        ids = [iid] + [r["id"] for r in conn.execute("SELECT id FROM incidents WHERE merged_into=?", (iid,))]
        marks = ",".join("?" * len(ids))
        rows = conn.execute(f"SELECT seq,type,incident_id,ts,data_json FROM events WHERE incident_id IN ({marks}) "
                            "ORDER BY seq", ids).fetchall()
    return [{"seq": r["seq"], "type": r["type"], "incident_id": r["incident_id"], "ts": r["ts"],
             "data": json.loads(r["data_json"])} for r in rows]


def canonical_hash(log: list[dict[str, Any]]) -> str:
    blob = json.dumps(log, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def measured_clock(log: list[dict[str, Any]]) -> dict[str, Any]:
    first = log[0] if log else None

    def first_of(*types: str) -> dict[str, Any] | None:
        return next((e for e in log if e["type"] in types), None)

    def gap(a, b):
        return round((_ts(b["ts"]) - _ts(a["ts"])).total_seconds(), 1) if a and b else None

    confirm = next((e for e in log if e["type"] == "incident.confirmed"
                    or (e["type"] == "evidence.updated" and e["data"].get("fire_status") == "confirmed")), None)
    dispatch, warn = first_of("unit.dispatched"), first_of("warning.sent")
    return {"first_signal": {"seq": first["seq"], "type": first["type"], "ts": first["ts"]} if first else None,
            "signal_to_confirm_s": gap(first, confirm), "signal_to_dispatch_s": gap(first, dispatch),
            "signal_to_warning_s": gap(first, warn),
            "confirm_seq": confirm["seq"] if confirm else None, "dispatch_seq": dispatch["seq"] if dispatch else None,
            "warning_seq": warn["seq"] if warn else None, "events": len(log),
            "callers": len({e["data"].get("call_id") for e in log if e["type"] == "call.started"})}


def template_draft(log: list[dict[str, Any]], clock: dict[str, Any]) -> list[str]:
    """One line per milestone, each citing the event that proves it."""
    labels = {"incident.created": "Report received", "call.started": "Call answered by AGNI",
              "estimate.updated": "Bearings crossed; location estimate made", "incident.merged": "Duplicate report merged by dispatcher",
              "incident.confirmed": "Fire confirmed by dispatcher", "route.ready": "Route prepared",
              "unit.dispatched": "Unit dispatched by dispatcher", "handoff.started": "Dispatcher jumped in",
              "handoff.ended": "Call handed back", "ring.updated": "Spread estimate drawn",
              "warning.sent": "Warning approved by dispatcher", "rescue.requested": "Resident asked for help"}
    seen, lines = set(), []
    for e in log:
        if e["type"] in labels and e["type"] not in seen:
            seen.add(e["type"])
            who = e["data"].get("approved_by") or e["data"].get("actor") or e["data"].get("accepted_by") or ""
            lines.append(f"{e['ts'][11:19]} UTC · {labels[e['type']]}{' (' + who + ')' if who else ''} [event #{e['seq']}]")
    if clock["signal_to_dispatch_s"] is not None:
        lines.append(f"Signal to dispatch: {clock['signal_to_dispatch_s']} s, measured from events "
                     f"#{clock['first_signal']['seq']} to #{clock['dispatch_seq']}.")
    return lines


def close(iid: str) -> dict[str, Any]:
    log = incident_log(iid)
    if not log:
        raise LookupError("No events for this incident")
    clock = measured_clock(log)
    digest = canonical_hash(log)
    source = "template"
    lines = template_draft(log, clock)
    compact = "\n".join(f"#{e['seq']} {e['ts']} {e['type']}" for e in log[-120:])
    drafted = gemini.generate_json("Write a 5-line after-action timeline for a dispatcher. Every line must end with "
                                   "the event number it comes from, like [event #12]. Use only these events:\n" + compact,
                                   DRAFT_SCHEMA, timeout=8)
    if drafted and isinstance(drafted.get("lines"), list) and all(isinstance(x, str) for x in drafted["lines"]):
        lines, source = [x[:240] for x in drafted["lines"][:8]], "gemini"
    with db.connect() as conn:
        signed = conn.execute("SELECT signed_by FROM reports WHERE incident_id=?", (iid,)).fetchone()
        if signed and signed["signed_by"]:
            raise ValueError("Report is already signed")
        conn.execute("INSERT OR REPLACE INTO reports(incident_id,draft,clock_json,log_sha256,event_count) VALUES(?,?,?,?,?)",
                     (iid, json.dumps({"lines": lines, "source": source}), json.dumps(clock), digest, len(log)))
    return {"incident_id": iid, "draft": lines, "draft_source": source, "clock": clock, "log_sha256": digest,
            "events": len(log), "signed_by": None, "anchor": "not anchored (Solana is a stretch item)"}


def sign(iid: str, actor: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE incident_id=?", (iid,)).fetchone()
        if not row:
            raise LookupError("Close the incident to draft a report first")
        if row["signed_by"]:
            raise ValueError("Report is already signed")
    log = incident_log(iid)
    digest = canonical_hash(log[:row["event_count"]])
    if digest != row["log_sha256"]:
        raise ValueError("The event log changed since the draft. Close again to redraft.")
    clock = json.loads(row["clock_json"])
    with db.connect() as conn:
        conn.execute("UPDATE reports SET signed_by=?,signed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE incident_id=?",
                     (actor, iid))
        conn.execute("UPDATE incidents SET status='closed',closed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (iid,))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (iid, actor, "report_signed", json.dumps({"log_sha256": digest})))
    data = {"report_id": iid, "clock_s": clock.get("signal_to_dispatch_s"), "log_sha256": digest,
            "signed_by": actor, "anchor": "not_anchored"}
    bus.emit("incident.closed", iid, data)
    return data


def get(iid: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE incident_id=?", (iid,)).fetchone()
    if not row:
        return None
    draft = json.loads(row["draft"])
    return {"incident_id": iid, "draft": draft["lines"], "draft_source": draft["source"],
            "clock": json.loads(row["clock_json"]), "log_sha256": row["log_sha256"], "events": row["event_count"],
            "signed_by": row["signed_by"], "signed_at": row["signed_at"], "anchor": row["anchor_status"]}
