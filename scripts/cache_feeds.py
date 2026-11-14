"""Save the 3 nearest ALERTCalifornia stills per demo spot to cache/ for Wi-Fi-safe mode.

Run once on a networked laptop before the demo. The console shows these as
"Cached still · <time>" in mock mode and never as live.
"""
from __future__ import annotations

import json
import sys
import time

import _env

sys.path.insert(0, str(_env.ROOT / "backend" / "core"))
import feeds  # noqa: E402

SPOTS = [(32.90, -117.19), (32.866, -117.251)]


def main() -> None:
    out = _env.ROOT / "cache"
    (out / "frames").mkdir(parents=True, exist_ok=True)
    saved: dict[str, dict] = {}
    for lat, lon in SPOTS:
        for cam in feeds.cameras(lat, lon)[:3]:
            blob = feeds.camera_jpeg(lat, lon, cam["id"])
            if not blob:
                continue
            (out / "frames" / f"{cam['id']}.jpg").write_bytes(blob)
            saved[cam["id"]] = {k: cam.get(k) for k in ("id", "name", "site", "lat", "lon")} | {
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "ALERTCalifornia"}
    (out / "cameras.json").write_text(json.dumps(list(saved.values()), indent=2))
    print(f"cached {len(saved)} stills")


if __name__ == "__main__":
    main()
