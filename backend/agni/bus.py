"""Persistent event log helpers used by the REST API and SSE stream."""
from . import db

EVENT_TYPES = {
    "signal.new", "call.started", "call.transcript", "incident.created", "incident.merge_suggested",
    "incident.merged", "triage.result", "route.ready", "unit.dispatched", "handoff.started",
    "handoff.ended", "ring.updated", "warning.sent", "surge.stats", "incident.closed",
    "bearing.added", "estimate.updated", "cameras.selected", "satellite.result",
    "evidence.updated", "rescue.requested", "camera.link",
    # Console: AGNI cannot finish alone — ask dispatcher to JUMP IN (J).
    "call.needs_human",
    # Judge demo: wipe fires/calls and return to calm.
    "ops.reset",
    # Spoken safe-path from Bright Data shelters (Jobs reveal for judges).
    "guidance.ready",
    # Human-approved SMS of maps link to nearest safe shelter (opt-in only).
    "escape.sms",
}


def emit(type_: str, incident_id: str | None, data: dict) -> dict:
    if type_ not in EVENT_TYPES:
        raise ValueError(f"Unknown AGNI event type: {type_}")
    return db.event(type_, incident_id, data)
