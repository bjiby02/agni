"""Offline route ranking and safe-shelter screening for dispatcher decisions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geo

ROOT = Path(__file__).resolve().parents[2]
REFUGES_FILE = ROOT / "data" / "refuges.json"


def _crosses(a_lon: float, a_lat: float, b_lon: float, b_lat: float,
             c_lon: float, c_lat: float, d_lon: float, d_lat: float) -> bool:
    def side(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> int:
        value = (qx - px) * (ry - py) - (qy - py) * (rx - px)
        return (value > 1e-12) - (value < -1e-12)
    return side(a_lon, a_lat, b_lon, b_lat, c_lon, c_lat) != side(a_lon, a_lat, b_lon, b_lat, d_lon, d_lat) and \
        side(c_lon, c_lat, d_lon, d_lat, a_lon, a_lat) != side(c_lon, c_lat, d_lon, d_lat, b_lon, b_lat)


def _segments(closure: dict[str, Any]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    geometry = closure.get("geometry") or closure.get("geometry_json") or closure
    if isinstance(geometry, str):
        try:
            geometry = json.loads(geometry)
        except json.JSONDecodeError:
            return []
    if not isinstance(geometry, dict):
        return []
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    rings = [coords] if kind == "LineString" else coords if kind == "Polygon" else []
    pairs = []
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 2:
            continue
        for index, point in enumerate(ring[:-1]):
            other = ring[index + 1]
            try:
                pairs.append(((float(point[0]), float(point[1])), (float(other[0]), float(other[1]))))
            except (TypeError, ValueError, IndexError):
                continue
    return pairs


def blocked_by_closure(unit: dict[str, Any], destination: tuple[float, float], closures: list[dict[str, Any]]) -> str | None:
    dest_lat, dest_lon = destination
    for closure in closures:
        for (start_lon, start_lat), (end_lon, end_lat) in _segments(closure):
            if _crosses(float(unit["lon"]), float(unit["lat"]), dest_lon, dest_lat, start_lon, start_lat, end_lon, end_lat):
                return str(closure.get("title") or closure.get("id") or "mapped road closure")
    return None


def route_options(destination: tuple[float, float], units: list[dict[str, Any]], closures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank units. Prefer live ORS/OSRM road routes when keys/network allow."""
    from .services import ors

    dest_lat, dest_lon = destination
    options = []
    for unit in units:
        if unit.get("status") != "available":
            continue
        closure = blocked_by_closure(unit, destination, closures)
        live = ors.route_unit(
            (float(unit["lat"]), float(unit["lon"])),
            (dest_lat, dest_lon),
            closures if not closure else [],
        )
        # If the straight-line path crosses a mapped closure and ORS did not return a road route,
        # keep the unit marked blocked so a human sees the hazard.
        path_blocked = bool(closure) and live.get("route_kind") != "road"
        options.append({
            "unit_id": unit["id"], "callsign": unit.get("callsign", unit["id"]),
            "distance_m": live["distance_m"], "eta_s": live["eta_s"],
            "route_kind": live["route_kind"], "available": True,
            "path_blocked": path_blocked, "blocked_by": closure if path_blocked else None,
            "note": live.get("note"), "geometry": live.get("geometry"),
        })
    return sorted(options, key=lambda item: (item["path_blocked"], item["eta_s"], item["distance_m"]))


def configured_refuges() -> list[dict[str, Any]]:
    try:
        rows = json.loads(REFUGES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def choose_shelter(origin: tuple[float, float], shelters: list[dict[str, Any]] | None, wind_to_deg: float | None) -> dict[str, Any]:
    """Use geo.py to screen configured refuges; expose every downwind refusal."""
    from . import brightdata_story

    shelters = configured_refuges() if shelters is None else shelters
    places: list[geo.Place] = []
    refused = []
    for shelter in shelters:
        try:
            lat, lon = float(shelter["lat"]), float(shelter["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        meters = geo.haversine_m(origin[0], origin[1], lat, lon)
        bearing = geo.bearing_deg(origin[0], origin[1], lat, lon)
        place = geo.Place(str(shelter.get("name") or "Unnamed refuge"), "R", lat, lon, meters, bearing)
        places.append(place)
        if wind_to_deg is not None and geo.angle_diff(bearing, wind_to_deg) < geo.DRIFT_ARC:
            refused.append({"name": place.name, "reason": "downwind of the estimate"})
    selected = geo.choose(origin, places, None, need="fire", drift=wind_to_deg)
    if selected is None:
        return {"shelter": None, "refused": refused}
    payload = {
        "name": selected.name, "lat": selected.lat, "lon": selected.lon,
        "distance_m": round(selected.meters), "bearing_deg": round(selected.bearing),
    }
    cap = brightdata_story.shelter_capacity_for(selected.name)
    if cap:
        payload.update({
            "capacity": cap.get("capacity"),
            "occupancy": cap.get("occupancy"),
            "room": cap.get("room"),
            "status": cap.get("status"),
            "capacity_source": "brightdata_browser",
            "capacity_label": "Shelter capacity from Bright Data",
        })
    return {"shelter": payload, "refused": refused}
