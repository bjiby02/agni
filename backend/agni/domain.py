from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from math import hypot
from uuid import uuid4


class IncidentStatus(StrEnum):
    ACTIVE = "active"
    DISPATCHED = "dispatched"
    HUMAN_OVERRIDE = "human_override"


@dataclass
class Point:
    latitude: float
    longitude: float


@dataclass
class Hazard:
    id: str
    title: str
    kind: str
    severity: int
    center: Point
    radius_km: float
    observed_at: datetime


@dataclass
class Unit:
    id: str
    callsign: str
    capability: str
    location: Point
    available: bool = True


@dataclass
class Incident:
    id: str
    caller_label: str
    location: Point
    summary: str
    triage_level: int = 3
    status: IncidentStatus = IncidentStatus.ACTIVE
    assigned_unit_id: str | None = None
    vision: dict = field(default_factory=dict)
    override_note: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def public(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data


def distance_km(a: Point, b: Point) -> float:
    """Fast local approximation appropriate only for the prototype's small demo area."""
    return hypot((a.latitude - b.latitude) * 111, (a.longitude - b.longitude) * 92)


class DispatchService:
    def __init__(self, incidents: dict[str, Incident], units: dict[str, Unit], hazards: list[Hazard]):
        self.incidents, self.units, self.hazards = incidents, units, hazards

    def rank_units(self, incident: Incident) -> list[dict]:
        ranked = []
        for unit in self.units.values():
            if not unit.available:
                continue
            direct_distance = distance_km(unit.location, incident.location)
            # The production adapter will use PostGIS line/polygon intersection.
            # For this small deterministic demo, penalize units already inside a
            # closure zone rather than falsely blocking every route to an incident.
            blocked = any(
                distance_km(h.center, unit.location) < h.radius_km
                for h in self.hazards
                if h.kind in {"road_closure", "fire_perimeter"}
            )
            ranked.append({
                "unit": unit,
                "distance_km": round(direct_distance, 2),
                "hazard_penalty": 99 if blocked else 0,
                "path_blocked": blocked,
            })
        return sorted(ranked, key=lambda item: item["distance_km"] + item["hazard_penalty"])

    def dispatch(self, incident_id: str) -> dict:
        incident = self.incidents[incident_id]
        ranked = self.rank_units(incident)
        if not ranked:
            raise ValueError("No responder units are available")
        choice = ranked[0]
        unit = choice["unit"]
        unit.available = False
        incident.assigned_unit_id = unit.id
        incident.status = IncidentStatus.DISPATCHED
        return {"incident": incident.public(), "assignment": {**choice, "unit": asdict(unit)}}

    def record_vision(self, incident_id: str, smoke_density: str, visible_flames: bool, blocked_exit: bool) -> Incident:
        incident = self.incidents[incident_id]
        severity = {"none": 0, "light": 1, "moderate": 2, "heavy": 3}[smoke_density]
        incident.vision = {"smoke_density": smoke_density, "visible_flames": visible_flames, "blocked_exit": blocked_exit}
        if visible_flames or blocked_exit or severity >= 3:
            incident.triage_level = 1
        elif severity >= 2:
            incident.triage_level = min(incident.triage_level, 2)
        return incident

    def enable_override(self, incident_id: str, note: str) -> Incident:
        incident = self.incidents[incident_id]
        incident.status = IncidentStatus.HUMAN_OVERRIDE
        incident.override_note = note
        return incident


def demo_service() -> DispatchService:
    incident = Incident(str(uuid4()), "Caller near Torrey Pines", Point(32.866, -117.251), "Heavy smoke near a trail access point.")
    units = {
        "u-42": Unit("u-42", "Engine 42", "wildland", Point(32.862, -117.239)),
        "u-17": Unit("u-17", "Engine 17", "structure", Point(32.875, -117.266)),
    }
    hazards = [Hazard(str(uuid4()), "Torrey Pines Road closure", "road_closure", 4, Point(32.863, -117.245), 1.1, datetime.now(UTC))]
    return DispatchService({incident.id: incident}, units, hazards)

