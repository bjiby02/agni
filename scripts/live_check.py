#!/usr/bin/env python3
"""One real request per configured service. Skips missing keys. Saves live fixtures."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "tests" / "fixtures" / "live"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def save(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2)[:20000], encoding="utf-8")


def get(url: str, headers: dict | None = None, timeout: int = 12):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        try:
            return json.loads(body), resp.status
        except json.JSONDecodeError:
            return {"raw": body[:2000].decode("utf-8", errors="replace")}, resp.status


def main() -> int:
    load_env()
    checks = []

    firms = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not firms:
        print("SKIP: FIRMS_MAP_KEY not set")
    else:
        try:
            data, status = get(
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{firms}/VIIRS_SNPP_NRT/-118,32,-116,34/1"
            )
            save("firms.json", {"status": status, "data": data})
            print(f"OK: FIRMS ({status})")
            checks.append(True)
        except Exception as error:  # noqa: BLE001
            print(f"FAIL: FIRMS · {error}")
            checks.append(False)

    ors = os.environ.get("ORS_API_KEY", "").strip()
    if not ors:
        print("SKIP: ORS_API_KEY not set")
    else:
        try:
            data, status = get(
                "https://api.openrouteservice.org/v2/directions/driving-car?start=-117.25,32.87&end=-117.23,32.86",
                headers={"Authorization": ors},
            )
            save("ors.json", {"status": status, "data": data})
            print(f"OK: ORS ({status})")
            checks.append(True)
        except Exception as error:  # noqa: BLE001
            print(f"FAIL: ORS · {error}")
            checks.append(False)

    gemini = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini:
        print("SKIP: GEMINI_API_KEY not set")
    else:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini}",
                data=json.dumps({"contents": [{"parts": [{"text": "Reply with the word ok."}]}]}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                status = resp.status
            save("gemini.json", {"status": status, "data": data})
            print(f"OK: Gemini ({status})")
            checks.append(True)
        except Exception as error:  # noqa: BLE001
            print(f"FAIL: Gemini · {error}")
            checks.append(False)

    if not os.environ.get("ELEVENLABS_API_KEY", "").strip():
        print("SKIP: ELEVENLABS_API_KEY not set")
    else:
        try:
            data, status = get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            )
            save("elevenlabs_user.json", {"status": status, "data": data})
            print(f"OK: ElevenLabs ({status})")
            checks.append(True)
        except Exception as error:  # noqa: BLE001
            print(f"FAIL: ElevenLabs · {error}")
            checks.append(False)

    if not os.environ.get("BRIGHTDATA_API_TOKEN", "").strip():
        print("SKIP: BRIGHTDATA_API_TOKEN not set")
    else:
        print("SKIP: Bright Data live probe needs zone IDs from Bijin (H5)")

    if not os.environ.get("NEON_API_KEY", "").strip():
        print("SKIP: NEON_API_KEY not set")
    else:
        print("SKIP: Neon live probe needs project setup (H6)")

    # Free public feed with no key
    try:
        data, status = get("https://api.weather.gov/points/32.87,-117.25",
                           headers={"User-Agent": os.environ.get("NWS_USER_AGENT", "agni-sandhacks (local)")})
        save("nws_points.json", {"status": status, "data": data})
        print(f"OK: NWS ({status})")
        checks.append(True)
    except Exception as error:  # noqa: BLE001
        print(f"FAIL: NWS · {error}")
        checks.append(False)

    if not checks:
        print("No live checks ran (all keys missing). Mock mode remains the build path.")
        return 0
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
