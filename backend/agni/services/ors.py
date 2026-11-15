"""OpenRouteService / OSRM live routing with closure avoidance."""
from __future__ import annotations

from typing import Any

from ..config import settings
from . import httputil
import geo


def route_unit(
    origin: tuple[float, float],
    destination: tuple[float, float],
    closures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return road route when ORS/OSRM available; else straight-line estimate."""
    estimate_m = geo.haversine_m(origin[0], origin[1], destination[0], destination[1])
    estimate = {
        "distance_m": round(estimate_m),
        "eta_s": round(estimate_m / 1000 / 35 * 3600),
        "route_kind": "estimate",
        "geometry": None,
        "note": "Straight-line estimate. It is not a safe-route guarantee.",
    }
    if settings.mock:
        return estimate

    avoid = []
    for closure in closures:
        geometry = closure.get("geometry")
        if isinstance(geometry, dict) and geometry.get("type") in {"Polygon", "MultiPolygon"}:
            avoid.append(geometry)

    ors_key = httputil.env("ORS_API_KEY")
    if ors_key:
        body: dict[str, Any] = {
            "coordinates": [[origin[1], origin[0]], [destination[1], destination[0]]],
        }
        if avoid:
            body["options"] = {"avoid_polygons": {
                "type": "MultiPolygon",
                "coordinates": [
                    geom["coordinates"] if geom["type"] == "Polygon"
                    else geom["coordinates"][0]  # simplified
                    for geom in avoid if geom.get("type") == "Polygon"
                ],
            }}
            # ORS expects a GeoJSON polygon/multipolygon; keep simple single polygon list
            polys = [geom["coordinates"] for geom in avoid if geom.get("type") == "Polygon"]
            if polys:
                body["options"] = {"avoid_polygons": {"type": "MultiPolygon", "coordinates": polys}}
        status, payload = httputil.request_json(
            "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
            method="POST",
            headers={"Authorization": ors_key, "Content-Type": "application/json"},
            body=body,
            timeout=8,
        )
        if 200 <= status < 300 and isinstance(payload, dict):
            try:
                feat = payload["features"][0]
                summary = feat["properties"]["summary"]
                return {
                    "distance_m": round(float(summary["distance"])),
                    "eta_s": round(float(summary["duration"])),
                    "route_kind": "road",
                    "geometry": feat.get("geometry"),
                    "note": "OpenRouteService driving route; avoid_polygons applied when closures exist.",
                }
            except (KeyError, IndexError, TypeError, ValueError):
                pass

    osrm = httputil.env("OSRM_BASE_URL") or "https://router.project-osrm.org"
    status, payload = httputil.request_json(
        f"{osrm.rstrip('/')}/route/v1/driving/{origin[1]},{origin[0]};"
        f"{destination[1]},{destination[0]}?overview=full&geometries=geojson",
        timeout=8,
    )
    if 200 <= status < 300 and isinstance(payload, dict) and payload.get("code") == "Ok":
        try:
            route = payload["routes"][0]
            return {
                "distance_m": round(float(route["distance"])),
                "eta_s": round(float(route["duration"])),
                "route_kind": "road",
                "geometry": route.get("geometry"),
                "note": "OSRM driving route (closures not avoided on this fallback).",
            }
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    return estimate
