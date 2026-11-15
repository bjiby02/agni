"""JUMP IN: a human takes over a live call, then hands it back by calling the caller.

After transfer_to_number the voice agent is off the line, so hand-back is a callback,
not a rejoin. The console asks for the transfer; the agent sees should_transfer=true
on its next get_guidance call and runs the transfer_to_number system tool.
"""
from __future__ import annotations

from typing import Any

from . import bus, db
from .services import elevenlabs, gemini

SUMMARY_SCHEMA = {"type": "OBJECT", "properties": {"summary": {"type": "STRING"}}, "required": ["summary"]}


def _facts(call_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        call = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not call:
            raise LookupError("Call not found")
        call = dict(call)
        lines = [dict(r) for r in conn.execute(
            "SELECT speaker,text FROM transcripts WHERE call_id=? ORDER BY id", (call_id,))]
        incident = conn.execute("SELECT * FROM incidents WHERE id=?", (call["incident_id"],)).fetchone()
        unit = conn.execute("SELECT u.callsign FROM dispatches d JOIN units u ON u.id=d.unit_id "
                            "WHERE d.incident_id=? ORDER BY d.id DESC LIMIT 1", (call["incident_id"],)).fetchone()
    return {"call": call, "lines": lines, "incident": dict(incident) if incident else None,
            "unit": unit["callsign"] if unit else None}


def template_summary(facts: dict[str, Any]) -> str:
    """Deterministic card used in mock mode or when Gemini is down. Built only from stored fields."""
    call, inc = facts["call"], facts["incident"] or {}
    import json
    needs = json.loads(call.get("needs_json") or "{}")
    parts = [f"Language {str(call.get('language') or 'unknown').upper()}",
             f"Location: {call.get('landmark_text') or 'not given'}"
             + (" (estimate)" if inc.get("location_src") == "estimate" else ""),
             f"Sees: {inc.get('description') or 'not described'}",
             "Someone cannot move" if needs.get("mobility") else "No mobility issue reported",
             f"Fire {inc.get('status', 'possible')}" + (f", {facts['unit']} sent" if facts["unit"] else ", no unit sent")]
    return " · ".join(parts)


def summarize(call_id: str) -> tuple[str, str]:
    facts = _facts(call_id)
    transcript = "\n".join(f"{l['speaker']}: {l['text']}" for l in facts["lines"][-30:])
    result = gemini.generate_json(
        "Summarize this emergency call for a dispatcher taking over, in under 40 words. "
        "Location, what they see, who cannot move, what was already done. No names or numbers.\n" + transcript,
        SUMMARY_SCHEMA)
    if result and isinstance(result.get("summary"), str):
        return result["summary"][:400], "gemini"
    return template_summary(facts), "template"


def takeover(call_id: str, actor: str) -> dict[str, Any]:
    with db.connect() as conn:
        live = conn.execute("SELECT id FROM handoffs WHERE call_id=? AND ended_at IS NULL", (call_id,)).fetchone()
    if live:
        raise ValueError("A dispatcher already has this call")
    summary, source = summarize(call_id)  # written before the transfer so it is on screen at pickup
    facts = _facts(call_id)
    with db.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO transfer_requests(call_id) VALUES(?)", (call_id,))
        conn.execute("UPDATE calls SET state='transferring' WHERE id=?", (call_id,))
        cur = conn.execute("INSERT INTO handoffs(call_id,incident_id,summary,transfer_status,actor) VALUES(?,?,?,?,?)",
                           (call_id, facts["call"]["incident_id"], summary, "requested", actor))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (facts["call"]["incident_id"], actor, "jump_in", '{"call_id":"%s"}' % call_id))
    data = {"call_id": call_id, "handoff_id": cur.lastrowid, "summary": summary, "summary_source": source,
            "to": "dispatcher", "transfer": "requested"}
    bus.emit("handoff.started", facts["call"]["incident_id"], data)
    return data


def transfer_pending(call_id: str) -> bool:
    with db.connect() as conn:
        return conn.execute("SELECT 1 FROM transfer_requests WHERE call_id=?", (call_id,)).fetchone() is not None


def handback(call_id: str, actor: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM handoffs WHERE call_id=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
                           (call_id,)).fetchone()
        if not row:
            raise ValueError("No open handoff for this call")
        contact = conn.execute("SELECT phone FROM call_contacts WHERE call_id=?", (call_id,)).fetchone()
    phone = contact["phone"] if contact else None
    if phone is None and not _mock():
        result = {"status": "no_caller_number"}
    else:
        result = elevenlabs.callback(call_id, phone or "mock", {"handoff_summary": row["summary"],
                                                               "incident_id": row["incident_id"] or ""})
    with db.connect() as conn:
        conn.execute("UPDATE handoffs SET ended_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),resumed_by='agent',"
                     "transfer_status=? WHERE id=?", ("handed_back:" + result["status"], row["id"]))
        conn.execute("DELETE FROM transfer_requests WHERE call_id=?", (call_id,))
        conn.execute("UPDATE calls SET state='live' WHERE id=?", (call_id,))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (row["incident_id"], actor, "hand_back", '{"call_id":"%s"}' % call_id))
    data = {"call_id": call_id, "handoff_id": row["id"], "resumed_by": "agent", "callback": result["status"]}
    if result["status"] == "no_caller_number":
        data["banner"] = "Call the caller back by hand · number not captured"
    bus.emit("handoff.ended", row["incident_id"], data)
    return data


def _mock() -> bool:
    from .config import settings
    return settings.mock
