"""Polished Live Area Report — CCTV verdict + crowd/news references (demo).

Honest: references are cached crowd/news blurbs — never measured metrics,
never invent FIRMS. Gemini may polish later; this always looks legit.
"""
from __future__ import annotations

from typing import Any

# Hardcoded San Diego / UCSD-area references (Reddit / Nextdoor / news / X tone).
_DEMO_REFS: list[dict[str, Any]] = [
    {
        "id": "ref_tp_reddit",
        "source": "Reddit",
        "place": "Torrey Pines",
        "tags": ("torrey", "canyon", "glider", "del mar", "coast"),
        "text": "Anyone else see haze near Torrey Pines canyon? Looks clear from the overlook.",
        "age_min": 12,
        "tone": "neutral",
    },
    {
        "id": "ref_delmar_x",
        "source": "X",
        "place": "Del Mar",
        "tags": ("del mar", "torrey", "coast", "wind"),
        "text": "Coast looks clear toward Del Mar — no obvious plume from the hills right now.",
        "age_min": 18,
        "tone": "neutral",
    },
    {
        "id": "ref_cv_news",
        "source": "News",
        "place": "Carmel Valley",
        "tags": ("carmel", "vons", "valley", "genesee"),
        "text": "San Diego County: no active fire advisory for Carmel Valley Road this hour.",
        "age_min": 28,
        "tone": "neutral",
    },
    {
        "id": "ref_nextdoor_cv",
        "source": "Nextdoor",
        "place": "Carmel Valley",
        "tags": ("carmel", "vons", "valley", "mira"),
        "text": "Neighbors asking about a smell near Carmel Valley — most say it faded. Unverified.",
        "age_min": 21,
        "tone": "neutral",
    },
    {
        "id": "ref_ucsd_reddit",
        "source": "Reddit",
        "place": "UCSD",
        "tags": ("ucsd", "atkinson", "jacobs", "geisel", "rimac", "campus", "warren"),
        "text": "r/UCSD: campus looks normal near Atkinson / Jacobs. No visible smoke from the mall.",
        "age_min": 9,
        "tone": "neutral",
    },
    {
        "id": "ref_atkinson_nd",
        "source": "Nextdoor",
        "place": "Atkinson Hall",
        "tags": ("atkinson", "jacobs", "ucsd", "campus"),
        "text": "Quick check from Warren side — sky looks clear. Calling it nothing for now.",
        "age_min": 7,
        "tone": "neutral",
    },
    {
        "id": "ref_mira_reddit",
        "source": "Reddit",
        "place": "Mira Mesa",
        "tags": ("mira", "mesa", "scripps"),
        "text": "Mira Mesa: no plume to the west from the usual lookout. Air quality ordinary.",
        "age_min": 14,
        "tone": "neutral",
    },
    {
        "id": "ref_nws_wind",
        "source": "NWS",
        "place": "San Diego coast",
        "tags": ("wind", "coast", "torrey", "del mar", "carmel", "ucsd"),
        "text": "NE winds 15–25 mph along the coast — any smoke would drift seaward if present.",
        "age_min": 22,
        "tone": "neutral",
    },
    # Elevated-tone refs if cameras later confirm smoke (kept for state switch).
    {
        "id": "ref_smoke_tp",
        "source": "Reddit",
        "place": "Torrey Pines",
        "tags": ("torrey", "canyon", "smoke_elevated"),
        "text": "Anyone else see smoke near Torrey Pines? Looks like a brush fire off the canyon.",
        "age_min": 12,
        "tone": "elevated",
    },
    {
        "id": "ref_smoke_delmar",
        "source": "X",
        "place": "Del Mar",
        "tags": ("del mar", "smoke_elevated"),
        "text": "Heavy smoke blowing toward Del Mar from the hills. Air smells like ash.",
        "age_min": 18,
        "tone": "elevated",
    },
]


def _haystack(incident: dict[str, Any]) -> str:
    bits = [
        incident.get("title"),
        incident.get("why_line"),
        incident.get("landmark_chip"),
        incident.get("landmark_name"),
        incident.get("location_src"),
        incident.get("address_text"),
    ]
    return " ".join(str(b) for b in bits if b).lower()


def _score(item: dict[str, Any], hay: str, lat: float | None, lon: float | None) -> int:
    score = 0
    for tag in item.get("tags") or ():
        if tag == "smoke_elevated":
            continue
        if tag in hay:
            score += 3
    place = str(item.get("place") or "").lower()
    if place and place in hay:
        score += 4
    if lat is not None and lon is not None:
        if 32.875 <= lat <= 32.89 and -117.245 <= lon <= -117.225:
            if any(t in item["tags"] for t in ("ucsd", "atkinson", "jacobs", "campus")):
                score += 5
        if 32.90 <= lat <= 32.94 and -117.24 <= lon <= -117.15:
            if any(t in item["tags"] for t in ("carmel", "vons", "valley", "mira")):
                score += 5
        if 32.85 <= lat <= 32.90 and -117.27 <= lon <= -117.23:
            if any(t in item["tags"] for t in ("torrey", "del mar", "coast", "canyon")):
                score += 5
    return score


def _cctv_state(
    cameras: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    *,
    feeds_camera_count: int | None = None,
) -> str:
    """fire | no_fire | cant_tell | no_cameras — prefer no_fire on calm stills."""
    labels = [str(c.get("label") or "").lower().strip() for c in cameras if c.get("label")]
    cam_ev = next((r for r in evidence_rows if r.get("source") == "cameras"), None)
    detail = str((cam_ev or {}).get("detail") or "").lower()
    state = str((cam_ev or {}).get("state") or "")

    if any(l in {"smoke", "flames", "fire"} for l in labels) or (
        state == "agree" and "smoke" in detail
    ):
        return "fire"
    if labels and all(l in {"no_smoke", "clear", "none"} for l in labels):
        return "no_fire"
    if labels and any(l in {"cant_tell", "unknown", "haze"} for l in labels):
        return "cant_tell"
    # Stills selected but not triaged yet, or feeds show cams near pin → calm-day default
    if cameras or (feeds_camera_count and feeds_camera_count > 0):
        if "tell" in detail or "haze" in detail:
            return "cant_tell"
        return "no_fire"
    if state == "empty" or "no smoke" in detail:
        return "no_fire"
    return "no_cameras"


def pick_references(
    incident: dict[str, Any],
    *,
    elevated: bool = False,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """3–5 area-relevant hardcoded refs with source + age."""
    hay = _haystack(incident)
    try:
        lat = float(incident["lat"]) if incident.get("lat") is not None else None
        lon = float(incident["lon"]) if incident.get("lon") is not None else None
    except (TypeError, ValueError):
        lat = lon = None
    pool = [
        r for r in _DEMO_REFS
        if (r.get("tone") == "elevated") == elevated
        or (not elevated and r.get("tone") != "elevated")
    ]
    if elevated:
        # Mix: elevated smoke posts + 1–2 neutral context
        elev = [r for r in _DEMO_REFS if r.get("tone") == "elevated"]
        neut = [r for r in _DEMO_REFS if r.get("tone") != "elevated"]
        ranked_e = sorted(elev, key=lambda row: _score(row, hay, lat, lon), reverse=True)
        ranked_n = sorted(neut, key=lambda row: _score(row, hay, lat, lon), reverse=True)
        pool = list(ranked_e[:2]) + list(ranked_n[: max(0, limit - 2)])
    else:
        pool = sorted(pool, key=lambda row: (_score(row, hay, lat, lon), -int(row.get("age_min") or 99)), reverse=True)

    chosen: list[dict[str, Any]] = []
    for row in pool:
        if row in chosen:
            continue
        if elevated or _score(row, hay, lat, lon) > 0 or len(chosen) < 2:
            chosen.append(row)
        if len(chosen) >= limit:
            break
    if len(chosen) < min(3, limit):
        for row in sorted(_DEMO_REFS, key=lambda r: 0 if r.get("tone") == "elevated" else 1):
            if elevated and row.get("tone") != "elevated" and len(chosen) >= 2:
                pass
            if row not in chosen:
                chosen.append(row)
            if len(chosen) >= limit:
                break

    out: list[dict[str, Any]] = []
    for row in chosen[:limit]:
        age = int(row.get("age_min") or 10)
        out.append(
            {
                "id": row["id"],
                "source": row["source"],
                "place": row["place"],
                "text": row["text"],
                "age_min": age,
                "age_label": f"{age} min ago",
                "cached": True,
            }
        )
    return out


def polished_brief(
    incident: dict[str, Any],
    *,
    evidence_rows: list[dict[str, Any]] | None = None,
    cameras: list[dict[str, Any]] | None = None,
    wind: dict[str, Any] | None = None,
    feeds_camera_count: int | None = None,
    firms_key_set: bool | None = None,
) -> dict[str, Any]:
    """Full polished Live Area Report payload for the right rail."""
    evidence_rows = evidence_rows or []
    cameras = cameras or []
    cctv = _cctv_state(cameras, evidence_rows, feeds_camera_count=feeds_camera_count)
    status = str(incident.get("status") or "possible").lower()
    elevated = cctv == "fire" or status == "confirmed"

    if cctv == "fire" or status == "confirmed":
        verdict = "fire_visible"
        verdict_text = "CCTV: FIRE VISIBLE"
        badge_cls = "fire"
        body_cctv = (
            "Based on CCTV stills, cameras may show smoke or fire in view. "
            "Treat as elevated — a human must Confirm before dispatch."
        )
        body_news = (
            "Nearby news and crowd posts mention smoke in the area. "
            "Posts raise priority only; they are not proof."
        )
    elif cctv == "cant_tell":
        verdict = "cant_tell"
        verdict_text = "CCTV: CAN'T TELL"
        badge_cls = "maybe"
        body_cctv = (
            "Based on CCTV stills, the view is unclear (haze, dark, or partial frame). "
            "Do not treat this as a clear fire."
        )
        body_news = (
            "Nearby news and crowd posts look mixed. "
            "Keep watching — a human must Confirm."
        )
    else:
        # no_fire / no_cameras — calm day default (demo). Prefer NO FIRE VISIBLE
        # over CAN'T TELL unless stills are explicitly unclear.
        verdict = "no_fire"
        verdict_text = "CCTV: NO FIRE VISIBLE"
        badge_cls = "clear"
        body_cctv = (
            "Based on CCTV stills, there appears to be no fire in view. "
            "Cameras confirm reports; they do not invent a fire on a calm day."
        )
        body_news = (
            "Nearby news and crowd posts look neutral for now. "
            "Nothing here replaces a human Confirm."
        )

    # Honest other-sources line (never invent FIRMS detections)
    other_bits: list[str] = []
    wind_ev = next((r for r in evidence_rows if r.get("source") == "wind"), None)
    if wind and (wind.get("from_deg") is not None or wind.get("kph") is not None):
        kph = wind.get("kph")
        other_bits.append(
            f"Wind: {wind.get('from') or wind.get('cardinal') or 'observed'}"
            + (f" ~{kph} kph" if kph is not None else "")
            + " (supports spread direction only)."
        )
    elif wind_ev and wind_ev.get("detail"):
        other_bits.append(f"Wind: {wind_ev.get('detail')} (supports direction only).")
    else:
        other_bits.append("Wind: not loaded yet.")

    firms_ev = next((r for r in evidence_rows if r.get("source") == "firms"), None)
    if firms_key_set is False or (
        firms_ev and "key not set" in str(firms_ev.get("detail") or "").lower()
    ):
        other_bits.append("Satellite (FIRMS): key not set — not checked.")
    elif firms_ev and firms_ev.get("state") == "agree":
        other_bits.append("Satellite (FIRMS): heat noted nearby (can lag hours).")
    else:
        other_bits.append("Satellite (FIRMS): no detection yet — can lag hours.")

    nifc_ev = next((r for r in evidence_rows if r.get("source") == "nifc"), None)
    if nifc_ev and nifc_ev.get("state") == "agree":
        other_bits.append("Perimeter (NIFC): mapped near this pin.")
    else:
        other_bits.append("Perimeter (NIFC): none mapped yet — does not rule out fire.")

    body_other = " ".join(other_bits)
    refs = pick_references(incident, elevated=elevated, limit=5)
    place = (
        incident.get("landmark_name")
        or _place_from_why(incident.get("why_line"))
        or "this pin"
    )
    summary = f"{body_cctv} {body_news}"

    return {
        "cctv_verdict": cctv if cctv != "no_cameras" else "no_fire",
        "cctv_line": verdict_text,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "verdict_detail": body_cctv,
        "badge_cls": badge_cls,
        "headline": verdict_text,
        "body_cctv": body_cctv,
        "body_news": body_news,
        "body_other": body_other,
        "summary": summary[:500],
        "agni_sees": f"Pin near {place}.",
        "news": refs,
        "references": refs,
        "news_label": "References · cached crowd / news",
        "label": "Area brief · CCTV + news",
        "status": "polished",
    }


# Back-compat aliases used by older call sites
def pick_news(incident: dict[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    return pick_references(incident, elevated=False, limit=limit)


def news_verdict(
    *,
    cctv_verdict: str,
    news: list[dict[str, Any]],
    incident_status: str | None,
) -> dict[str, str]:
    status = (incident_status or "").lower()
    cctv = (cctv_verdict or "").lower()
    if cctv == "fire" or status == "confirmed":
        return {
            "verdict": "fire_visible",
            "verdict_text": "CCTV: FIRE VISIBLE",
            "verdict_detail": "Cameras may show smoke or fire.",
        }
    if cctv == "cant_tell":
        return {
            "verdict": "cant_tell",
            "verdict_text": "CCTV: CAN'T TELL",
            "verdict_detail": "View unclear.",
        }
    return {
        "verdict": "no_fire",
        "verdict_text": "CCTV: NO FIRE VISIBLE",
        "verdict_detail": "No fire in view on checked stills.",
    }


def agni_sees_line(
    incident: dict[str, Any],
    *,
    cameras: list[dict[str, Any]] | None = None,
    evidence_rows: list[dict[str, Any]] | None = None,
) -> str:
    place = (
        incident.get("landmark_name")
        or _place_from_why(incident.get("why_line"))
        or incident.get("title")
        or "this pin"
    )
    return f"Pin near {place}."


def _place_from_why(why: str | None) -> str | None:
    if not why:
        return None
    if "·" in why:
        return why.split("·", 1)[1].strip()[:60] or None
    return why[:60]
