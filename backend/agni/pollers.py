"""Background pollers. Bright Data never runs while any call is live."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import bus, db
from .services import brightdata, gemini


def live_call_count() -> int:
    with db.connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM calls WHERE state='live'").fetchone()
    return int(row["n"] if row else 0)


def refresh_crowd_signals() -> dict[str, Any]:
    """Upsert fixture/live SERP posts into signals and emit signal.new for fire-related ones."""
    if live_call_count() > 0:
        brightdata.block_http(True)
        return {"skipped": True, "reason": "call_active", "http_calls": brightdata.http_call_count()}
    brightdata.block_http(False)
    posts = brightdata.fetch_serp_signals()
    created = 0
    for post in posts:
        text = str(post.get("text") or post.get("title") or "")
        url = str(post.get("url") or "")
        source = str(post.get("source") or "serp")
        sid = str(post.get("id") or hashlib.sha1(url.encode() or text.encode()).hexdigest()[:16])
        classified = gemini.classify_post(text)
        lat = post.get("lat")
        lon = post.get("lon")
        with db.connect() as conn:
            prior = conn.execute("SELECT id FROM signals WHERE id=?", (sid,)).fetchone()
            conn.execute(
                "INSERT OR REPLACE INTO signals(id,source,url,text,about_fire,place_text,confidence,lat,lon,scraped_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (sid, source, url, text, int(bool(classified["about_fire"])),
                 classified.get("place_text"), classified.get("confidence"), lat, lon),
            )
        if not prior and classified.get("about_fire"):
            bus.emit("signal.new", None, {
                "signal_id": sid, "source": source, "url": url, "text": text[:200],
                "status": "unverified", "lat": lat, "lon": lon,
            })
            created += 1
    return {"skipped": False, "posts": len(posts), "emitted": created,
            "http_calls": brightdata.http_call_count()}


def ensure_demo_hazards() -> None:
    """Seed a road closure near Torrey Pines for routing demos."""
    geom = {
        "type": "Polygon",
        "coordinates": [[
            [-117.255, 32.868], [-117.245, 32.868],
            [-117.245, 32.862], [-117.255, 32.862], [-117.255, 32.868],
        ]],
    }
    with db.connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO hazards(id,source,kind,title,geometry_json,lat,lon,scraped_at) "
            "VALUES(?,?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
            ("hz_closure_genesee", "manual", "road_closure", "Genesee Ave closure (demo)",
             json.dumps(geom), 32.865, -117.250),
        )
