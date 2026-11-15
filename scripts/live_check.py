"""One real request per service whose key is set. Skips the rest with `SKIP: <VAR> not set`.

Real responses are saved to backend/tests/fixtures/live/ so the fakes can be fixed when the
real shape differs. Never prints a key. Run: make live-check
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import _env

OUT = _env.ROOT / "backend" / "tests" / "fixtures" / "live"
UA = os.environ.get("NWS_USER_AGENT") or "agni-sandhacks (contact via repo)"
LAT, LON = 32.88, -117.24


def get(url: str, headers: dict | None = None, data: bytes | None = None, method: str = "GET"):
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": UA, **(headers or {})})
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read()
    return body, round((time.monotonic() - started) * 1000)


def save(name: str, body: bytes) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(body)


def check(name: str, needs: list[str], fn) -> bool:
    missing = [v for v in needs if not os.environ.get(v)]
    if missing:
        print(f"SKIP: {name:16} {', '.join(missing)} not set")
        return True
    try:
        detail = fn()
        print(f"PASS: {name:16} {detail}")
        return True
    except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
        print(f"FAIL: {name:16} {str(error)[:160]}")
        return False


def nws():
    body, ms = get(f"https://api.weather.gov/points/{LAT},{LON}")
    save("nws_points.json", body)
    return f"{ms} ms · forecast office {json.loads(body)['properties']['gridId']}"


def cameras():
    q = urllib.parse.urlencode({"geometry": f"{LON},{LAT}", "geometryType": "esriGeometryPoint", "inSR": "4326",
                                "distance": 40000, "units": "esriSRUnit_Meter", "outFields": "*", "f": "json"})
    body, ms = get("https://services8.arcgis.com/X84q166Srnyl4JMV/ArcGIS/rest/services/ALERTCalifornia_Camera_Feed/FeatureServer/0/query?" + q)
    save("alertca_cameras.json", body)
    return f"{ms} ms · {len(json.loads(body).get('features', []))} cameras"


def nifc():
    q = urllib.parse.urlencode({"where": "1=1", "outFields": "poly_IncidentName", "returnGeometry": "false", "resultRecordCount": 5, "f": "json"})
    body, ms = get("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query?" + q)
    save("nifc_perimeters.json", body)
    return f"{ms} ms · {len(json.loads(body).get('features', []))} perimeters (sample)"


def osrm():
    base = os.environ.get("OSRM_BASE_URL") or "https://router.project-osrm.org"
    body, ms = get(f"{base}/route/v1/driving/-117.239,32.862;-117.251,32.866?overview=false")
    save("osrm_route.json", body)
    return f"{ms} ms · {json.loads(body)['code']}"


def firms():
    key = os.environ["FIRMS_MAP_KEY"]
    body, ms = get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/-117.6,32.5,-116.8,33.2/1")
    save("firms_area.csv", body)
    return f"{ms} ms · {max(0, body.decode(errors='replace').count(chr(10)) - 1)} detections"


def ors():
    body = json.dumps({"coordinates": [[-117.239, 32.862], [-117.251, 32.866]]}).encode()
    resp, ms = get("https://api.openrouteservice.org/v2/directions/driving-car/geojson", data=body, method="POST",
                   headers={"Authorization": os.environ["ORS_API_KEY"], "Content-Type": "application/json"})
    save("ors_route.geojson", resp)
    return f"{ms} ms · {len(json.loads(resp).get('features', []))} route"


def gemini():
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    body = json.dumps({"contents": [{"parts": [{"text": "Reply with the JSON {\"ok\": true}."}]}],
                       "generationConfig": {"responseMimeType": "application/json"}}).encode()
    resp, ms = get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                   data=body, method="POST", headers={"Content-Type": "application/json"})
    save("gemini_text.json", resp)
    return f"{ms} ms · {model}"


def elevenlabs():
    resp, ms = get("https://api.elevenlabs.io/v1/convai/agents", headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
    save("elevenlabs_agents.json", resp)
    return f"{ms} ms · {len(json.loads(resp).get('agents', []))} agents"


def brightdata():
    body = json.dumps({"zone": os.environ["BRIGHTDATA_SERP_ZONE"], "format": "raw",
                       "url": "https://www.google.com/search?q=san+diego+smoke+fire&tbs=qdr:h"}).encode()
    resp, ms = get("https://api.brightdata.com/request", data=body, method="POST",
                   headers={"Authorization": f"Bearer {os.environ['BRIGHTDATA_API_TOKEN']}", "Content-Type": "application/json"})
    save("brightdata_serp.html", resp)
    return f"{ms} ms · {len(resp)} bytes (1 billed SERP request)"


def neon():
    resp, ms = get(f"https://console.neon.tech/api/v2/projects/{os.environ['NEON_PROJECT_ID']}/branches",
                   headers={"Authorization": f"Bearer {os.environ['NEON_API_KEY']}", "Accept": "application/json"})
    save("neon_branches.json", resp)
    return f"{ms} ms · {len(json.loads(resp).get('branches', []))} branches"


def main() -> None:
    _env.load()
    results = [
        check("nws", [], nws), check("alertcalifornia", [], cameras), check("nifc", [], nifc), check("osrm", [], osrm),
        check("firms", ["FIRMS_MAP_KEY"], firms), check("ors", ["ORS_API_KEY"], ors), check("gemini", ["GEMINI_API_KEY"], gemini),
        check("elevenlabs", ["ELEVENLABS_API_KEY"], elevenlabs),
        check("brightdata", ["BRIGHTDATA_API_TOKEN", "BRIGHTDATA_SERP_ZONE"], brightdata),
        check("neon", ["NEON_API_KEY", "NEON_PROJECT_ID"], neon),
    ]
    print(f"\nSaved real responses to {OUT.relative_to(_env.ROOT)}/" if OUT.exists() else "")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
