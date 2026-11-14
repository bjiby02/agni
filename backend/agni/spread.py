"""Small, explicit wildfire-spread estimate for a dispatcher review screen."""
from __future__ import annotations

import math
from typing import Any

EARTH_RADIUS_M = 6_371_000
GRID_CELL_M = 100
GRID_SIDE_M = 10_000


def _destination(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    angle = math.radians(bearing_deg)
    start_lat = math.radians(lat)
    start_lon = math.radians(lon)
    ratio = distance_m / EARTH_RADIUS_M
    end_lat = math.asin(math.sin(start_lat) * math.cos(ratio) + math.cos(start_lat) * math.sin(ratio) * math.cos(angle))
    end_lon = start_lon + math.atan2(math.sin(angle) * math.sin(ratio) * math.cos(start_lat),
                                     math.cos(ratio) - math.sin(start_lat) * math.sin(end_lat))
    return math.degrees(end_lat), math.degrees(end_lon)


def estimate_ring(lat: float, lon: float, wind_to_deg: float, minutes: int = 30,
                  base_rate_m_min: float = 16.0) -> dict[str, Any]:
    """Create a 30-minute downwind ellipse-like polygon on a 100m/10km model grid.

    This is a decision aid. It does not predict a real fire perimeter.
    """
    if not 1 <= minutes <= 120:
        raise ValueError("minutes must be between 1 and 120")
    if not 0 <= wind_to_deg < 360:
        raise ValueError("wind_to_deg must be in [0, 360)")
    downwind_m = min(GRID_SIDE_M / 2, max(250, base_rate_m_min * minutes * 2.2))
    crosswind_m = max(200, downwind_m * 0.48)
    upwind_m = max(150, downwind_m * 0.32)
    # Start downwind and describe a closed, asymmetric oval around the ignition point.
    coordinates: list[list[float]] = []
    for step in range(25):
        theta = math.tau * step / 24
        forward = math.cos(theta)
        side = math.sin(theta)
        forward_m = downwind_m * forward if forward >= 0 else upwind_m * forward
        angle = math.radians(wind_to_deg)
        east = forward_m * math.sin(angle) + side * crosswind_m * math.cos(angle)
        north = forward_m * math.cos(angle) - side * crosswind_m * math.sin(angle)
        distance = math.hypot(east, north)
        bearing = (math.degrees(math.atan2(east, north)) + 360) % 360
        point_lat, point_lon = _destination(lat, lon, bearing, distance)
        coordinates.append([round(point_lon, 6), round(point_lat, 6)])
    return {
        "type": "Feature",
        "properties": {
            "label": f"{minutes}-min estimate",
            "minutes": minutes,
            "wind_to_deg": wind_to_deg,
            "grid_cell_m": GRID_CELL_M,
            "grid_side_m": GRID_SIDE_M,
            "model": "asymmetric downwind spread estimate",
        },
        "geometry": {"type": "Polygon", "coordinates": [coordinates]},
    }


def centroid(ring: dict[str, Any]) -> tuple[float, float]:
    points = ring["geometry"]["coordinates"][0][:-1]
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return lat, lon
