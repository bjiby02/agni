"""Demo-visible Bright Data story helpers. Cache/fixtures only — never live scrapes."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db

ROOT = Path(__file__).resolve().parents[2]
CACHED_SHELTERS = ROOT / "seed" / "cached_shelters.json"
ATTACH_KM = 8.0


def _parse_ts(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def cached_shelters() -> list[dict[str, Any]]:
    try:
        rows = json.loads(CACHED_SHELTERS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def shelter_capacity_for(name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    needle = str(name).casefold()
    for row in cached_shelters():
        label = str(row.get("name") or "")
        if label.casefold() == needle or needle in label.casefold() or label.casefold() in needle:
            capacity = row.get("capacity")
            occupancy = row.get("occupancy")
            status = row.get("status") or "unknown"
            room = None
            if isinstance(capacity, (int, float)) and isinstance(occupancy, (int, float)):
                room = max(0, int(capacity) - int(occupancy))
            return {
                "name": label,
                "capacity": capacity,
                "occupancy": occupancy,
                "room": room,
                "status": status,
                "source": "brightdata_browser",
                "source_label": row.get("source_label") or "Bright Data · shelter pages",
            }
    return None


def signals_near(lat: float | None, lon: float | None, place_hint: str | None = None) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM signals WHERE about_fire=1 ORDER BY scraped_at ASC LIMIT 80"
        )]
    if lat is None or lon is None:
        if not place_hint:
            return []
        hint = place_hint.casefold()
        return [r for r in rows if hint and hint in str(r.get("place_text") or "").casefold()]

    out: list[dict[str, Any]] = []
    hint = (place_hint or "").casefold()
    for row in rows:
        try:
            slat, slon = float(row["lat"]), float(row["lon"])
        except (TypeError, ValueError, KeyError):
            if hint and hint in str(row.get("place_text") or "").casefold():
                out.append(row)
            continue
        if _haversine_km(lat, lon, slat, slon) <= ATTACH_KM:
            out.append(row)
            continue
        if hint and hint in str(row.get("place_text") or "").casefold():
            out.append(row)
    return out


def attach_nearby_signals(incident_id: str, lat: float, lon: float, place_hint: str | None = None) -> int:
    """Link nearby cache signals to an incident (gray unverified — never auto-confirm)."""
    nearby = signals_near(lat, lon, place_hint)
    linked = 0
    with db.connect() as conn:
        for row in nearby:
            cur = conn.execute(
                "UPDATE signals SET incident_id=? WHERE id=? AND (incident_id IS NULL OR incident_id='')",
                (incident_id, row["id"]),
            )
            linked += cur.rowcount
        # Honest gray posts row — never green/agree from crowd alone.
        n = int(conn.execute(
            "SELECT COUNT(*) FROM signals WHERE incident_id=? AND about_fire=1", (incident_id,)
        ).fetchone()[0])
        if n:
            detail = (
                f"{n} public mention{'s' if n != 1 else ''} nearby "
                f"(unverified · Bright Data cache)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO evidence(incident_id,source,state,detail,updated_at) "
                "VALUES(?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (incident_id, "posts", "empty", detail),
            )
    return linked


def first_mention_story(incident_id: str, incident: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Public ears → overflow call lag when timestamps exist. Missing data → None."""
    with db.connect() as conn:
        inc = incident or dict(conn.execute(
            "SELECT * FROM incidents WHERE id=?", (incident_id,)
        ).fetchone() or {})
        if not inc:
            return None
        call = conn.execute(
            "SELECT MIN(started_at) AS first_call FROM calls WHERE incident_id=?",
            (incident_id,),
        ).fetchone()
        linked = [dict(r) for r in conn.execute(
            "SELECT scraped_at, place_text, source, text FROM signals "
            "WHERE incident_id=? AND about_fire=1 ORDER BY scraped_at ASC",
            (incident_id,),
        )]
        if not linked:
            lat, lon = inc.get("lat"), inc.get("lon")
            try:
                nearby = signals_near(
                    float(lat) if lat is not None else None,
                    float(lon) if lon is not None else None,
                    place_hint=str(inc.get("title") or ""),
                )
            except (TypeError, ValueError):
                nearby = []
            linked = nearby

    first_call_ts = _parse_ts(call["first_call"] if call else None) or _parse_ts(inc.get("created_at"))
    mention_times = [t for t in (_parse_ts(r.get("scraped_at")) for r in linked) if t is not None]
    if not mention_times or first_call_ts is None:
        return None
    first_public_ts = min(mention_times)
    lead_s = int(first_call_ts - first_public_ts)
    if lead_s < 60:
        # Mention after/with the call — still useful as co-occurring ears, not a lead.
        return {
            "signal_count": len(linked),
            "first_public_at": datetime.fromtimestamp(first_public_ts, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "first_call_at": datetime.fromtimestamp(first_call_ts, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "lead_s": None,
            "lead_label": None,
            "co_occurring": True,
            "place_text": linked[0].get("place_text") if linked else None,
            "unverified": True,
        }
    minutes = max(1, round(lead_s / 60))
    return {
        "signal_count": len(linked),
        "first_public_at": datetime.fromtimestamp(first_public_ts, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "first_call_at": datetime.fromtimestamp(first_call_ts, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "lead_s": lead_s,
        "lead_label": f"First public mention → call · ~{minutes} min earlier",
        "co_occurring": False,
        "place_text": linked[0].get("place_text") if linked else None,
        "unverified": True,
    }


def route_attribution(
    avoids: list[Any],
    shelter: dict[str, Any] | None,
) -> dict[str, Any]:
    """Chips for the route card when Bright Data cache supplied the data."""
    closure_titles: list[str] = []
    for item in avoids or []:
        if isinstance(item, str) and item.strip():
            closure_titles.append(item.strip())
        elif isinstance(item, dict):
            title = str(item.get("title") or item.get("blocked_by") or "").strip()
            if title:
                closure_titles.append(title)
    # Prefer DB hazards marked Bright Data / QuickMap.
    with db.connect() as conn:
        bd_hazards = [dict(r) for r in conn.execute(
            "SELECT title, source FROM hazards WHERE kind='road_closure' "
            "AND (source LIKE 'brightdata%' OR lower(title) LIKE '%quickmap%' OR lower(title) LIKE '%caltrans%')"
        )]
    chips: list[dict[str, str]] = []
    if closure_titles or bd_hazards:
        label = closure_titles[0] if closure_titles else (bd_hazards[0].get("title") or "mapped closure")
        short = label.replace("(Caltrans QuickMap)", "").replace("(demo)", "").strip()
        chips.append({
            "kind": "closure",
            "text": f"Avoids Caltrans closure (Bright Data)",
            "detail": short[:80],
        })
    cap = shelter_capacity_for((shelter or {}).get("name") if shelter else None)
    shelter_out = shelter
    if cap:
        shelter_out = {**(shelter or {}), **cap}
        room = cap.get("room")
        status = cap.get("status") or "unknown"
        if room is not None and status == "open":
            chips.append({
                "kind": "shelter",
                "text": "Shelter capacity from Bright Data",
                "detail": f"{cap['name']} · ~{room} open · {status}",
            })
        else:
            chips.append({
                "kind": "shelter",
                "text": "Shelter capacity from Bright Data",
                "detail": f"{cap['name']} · capacity {status}",
            })
    return {"chips": chips, "shelter": shelter_out, "closures_from_cache": bool(bd_hazards or closure_titles)}
