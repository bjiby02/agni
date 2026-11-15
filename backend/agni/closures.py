"""Caltrans QuickMap road closures (C7).

QuickMap draws its Full Closures layer from public KML files (the layer list is in
https://quickmap.dot.ca.gov/config/layers.json, checked by hand on 2026-11-14). Reading those files
is steadier than clicking the map, so we fetch them, through Bright Data Web Unlocker when
BRIGHTDATA_UNLOCKER_ZONE is set, otherwise directly.

- Only full closures are kept (styleUrl #fullClosurePath, #full-closure, #pending-full-closure).
- Only closures inside the operating box are stored. Each path part becomes one LineString hazard.
- A closure with no path is stored as a Point. Routing ignores it, so no geometry is invented.
- Runs on a timer, never during an active inbound call, and caches the parsed result for the no-Wi-Fi path.
- In mock mode nothing is fetched and the practice snapshot stays on the map.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import bus, db
from .config import settings

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "caltrans"
LATEST = CACHE / "closures_latest.geojson"
BASE = "https://quickmap.dot.ca.gov"
KML_FILES = ["/data/v2_lcs2way.kml", "/data/v2_lcspending.kml", "/data/v2_gi.kml", "/data/v2_cc.kml", "/data/v2_chp-only.kml"]
FULL_STYLES = {"#fullClosurePath", "#full-closure", "#pending-full-closure"}
PATH_STYLES = {"#fullClosurePath"}
# San Diego County, generous. Override with CLOSURE_BBOX="south,west,north,east".
DEFAULT_BBOX = (32.5, -117.6, 33.5, -116.0)
NS = "{http://www.opengis.net/kml/2.2}"
ID_RE = re.compile(r"Closure ID:\s*([A-Za-z0-9-]+),\s*Log Number:\s*(\d+)")
PATH_NAME_RE = re.compile(r"^\s*([A-Za-z0-9-]+)\s+Log\s+(\d+)\s+path", re.I)


def bbox() -> tuple[float, float, float, float]:
    raw = os.environ.get("CLOSURE_BBOX", "").strip()
    if raw:
        try:
            south, west, north, east = (float(x) for x in raw.split(","))
            return south, west, north, east
        except ValueError:
            pass
    return DEFAULT_BBOX


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _coords(text: str) -> list[list[float]]:
    out = []
    for chunk in text.split():
        parts = chunk.split(",")
        try:
            out.append([round(float(parts[0]), 6), round(float(parts[1]), 6)])
        except (ValueError, IndexError):
            continue
    return out


def _inside(points: list[list[float]], box: tuple[float, float, float, float]) -> bool:
    south, west, north, east = box
    return any(south <= lat <= north and west <= lon <= east for lon, lat in points)


def _title(desc: str) -> str:
    """'Full Closure Route 56 ... Due to Construction Expected to end ...' -> 'Full Closure Route 56 ...'."""
    text = desc.split(" Expected to end")[0].split(" Information courtesy")[0]
    return text[:140] or "Caltrans full closure"


def parse(kml_text: str, box: tuple[float, float, float, float] | None = None, scraped_at: str | None = None) -> list[dict[str, Any]]:
    """Turn one QuickMap KML file into GeoJSON features for the full closures inside the box."""
    box = box or bbox()
    scraped_at = scraped_at or _stamp()
    root = ET.fromstring(kml_text.encode("utf-8") if isinstance(kml_text, str) else kml_text)
    points: dict[tuple[str, str], dict[str, Any]] = {}
    paths: dict[tuple[str, str], list[list[list[float]]]] = {}
    loose: list[dict[str, Any]] = []
    for pm in root.iter(f"{NS}Placemark"):
        style = _text(pm.find(f"{NS}styleUrl"))
        if style not in FULL_STYLES:
            continue
        name = _text(pm.find(f"{NS}name"))
        desc = _clean(_text(pm.find(f"{NS}description")))
        if style in PATH_STYLES:
            match = PATH_NAME_RE.match(name)
            parts = [_coords(_text(c)) for ls in pm.iter(f"{NS}LineString") for c in ls.iter(f"{NS}coordinates")]
            parts = [p for p in parts if len(p) >= 2 and _inside(p, box)]
            if match and parts:
                paths.setdefault((match.group(1), match.group(2)), []).extend(parts)
            continue
        point = next((_coords(_text(c)) for c in pm.iter(f"{NS}coordinates")), [])
        if not point or not _inside(point, box):
            continue
        match = ID_RE.search(desc)
        entry = {"desc": desc, "point": point[0], "pending": style == "#pending-full-closure",
                 "updated": (re.search(r"Last updated:\s*([^<]+?)\s*$", desc) or [None, None])[1],
                 "ends": (re.search(r"Expected to end at\s*(.+?)(?: Closure ID|$)", desc) or [None, None])[1]}
        if match:
            points.setdefault((match.group(1), match.group(2)), entry)
        else:
            loose.append(entry)
    features = []
    for key in sorted(set(points) | set(paths)):
        info = points.get(key, {})
        base = {"source": "caltrans_quickmap", "kind": "road_closure", "closure_id": key[0], "log": key[1],
                "title": f"{_title(info.get('desc', ''))} (Caltrans)" if info else f"Caltrans full closure {key[0]}",
                "pending": info.get("pending", False), "ends": info.get("ends"), "observed_at": info.get("updated"),
                "scraped_at": scraped_at}
        parts = paths.get(key) or []
        if parts:
            for index, part in enumerate(parts, 1):
                features.append({"type": "Feature", "id": f"caltrans-{key[0]}-{key[1]}-{index}",
                                 "properties": base, "geometry": {"type": "LineString", "coordinates": part}})
        elif info:
            features.append({"type": "Feature", "id": f"caltrans-{key[0]}-{key[1]}",
                             "properties": base, "geometry": {"type": "Point", "coordinates": info["point"]}})
    for index, info in enumerate(loose, 1):
        features.append({"type": "Feature", "id": f"caltrans-noid-{index}",
                         "properties": {"source": "caltrans_quickmap", "kind": "road_closure", "title": f"{_title(info['desc'])} (Caltrans)",
                                        "pending": info["pending"], "ends": info["ends"], "observed_at": info["updated"], "scraped_at": scraped_at},
                         "geometry": {"type": "Point", "coordinates": info["point"]}})
    return features


def fetch_kml(path: str, timeout: int = 40) -> str:
    url = BASE + path
    token = os.environ.get("BRIGHTDATA_API_TOKEN") or os.environ.get("BRIGHTDATA_API_KEY") or ""
    zone = os.environ.get("BRIGHTDATA_UNLOCKER_ZONE", "").strip()
    if token and zone:
        req = urllib.request.Request("https://api.brightdata.com/request", method="POST",
                                     data=json.dumps({"zone": zone, "url": url, "format": "raw"}).encode(),
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url, headers={"User-Agent": os.environ.get("NWS_USER_AGENT") or "AGNI prototype"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def store(features: list[dict[str, Any]], scraped_at: str) -> int:
    """Replace the stored Caltrans closures. The practice snapshot and manual rows stay."""
    with db.connect() as conn:
        conn.execute("DELETE FROM hazards WHERE source='caltrans_quickmap'")
        for f in features:
            props = f["properties"]
            geom = f["geometry"]
            first = geom["coordinates"][0] if geom["type"] == "LineString" else geom["coordinates"]
            conn.execute("INSERT OR REPLACE INTO hazards(id,source,kind,title,geometry_json,lat,lon,observed_at,scraped_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?)",
                         (f["id"], "caltrans_quickmap", "road_closure", props.get("title"), json.dumps(geom),
                          first[1], first[0], props.get("observed_at"), scraped_at))
    return len(features)


def poll(force: bool = False) -> dict[str, Any]:
    if settings.mock and not force:
        return {"status": "skipped", "reason": "mock mode keeps the practice closure snapshot"}
    from .brightdata import active_call
    if active_call() and not force:
        return {"status": "skipped", "reason": "a call is active; scraping waits"}
    scraped_at = _stamp()
    features: list[dict[str, Any]] = []
    failures = []
    for path in KML_FILES:
        try:
            features.extend(parse(fetch_kml(path), scraped_at=scraped_at))
        except Exception as error:  # one bad file must not drop the others
            failures.append(f"{path}: {type(error).__name__}")
    if failures and not features and len(failures) == len(KML_FILES):
        return {"status": "failed", "detail": "; ".join(failures)}
    seen: set[str] = set()
    unique = [f for f in features if not (f["id"] in seen or seen.add(f["id"]))]
    CACHE.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps({"type": "FeatureCollection", "scraped_at": scraped_at, "source": BASE,
                                  "features": unique}, indent=1), encoding="utf-8")
    count = store(unique, scraped_at)
    bus.emit("hazards.updated", None, {"count": count, "scraped_at": scraped_at, "source": "caltrans_quickmap",
                                       "failures": failures})
    return {"status": "ok", "closures": count, "scraped_at": scraped_at, "failures": failures}


def load_cached() -> int:
    """Wi-Fi-safe path: reload the last parsed closures from disk."""
    try:
        data = json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return store(data.get("features", []), data.get("scraped_at") or "cached")
