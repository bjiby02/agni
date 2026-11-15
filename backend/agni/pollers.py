"""Background pollers. Bright Data never runs while any call is live."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import bus, db
from .services import brightdata, gemini

ROOT = Path(__file__).resolve().parents[2]
CACHED_SIGNALS = ROOT / "seed" / "cached_signals.json"
CACHED_CLOSURES = ROOT / "seed" / "cached_closures.json"
FIXTURE_SIGNALS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "serp_signals.json"


def live_call_count() -> int:
    with db.connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM calls WHERE state='live'").fetchone()
    return int(row["n"] if row else 0)


def _scraped_at_for(post: dict[str, Any]) -> str:
    """Prefer fixture relative age so 'first public mention → call' is demo-visible."""
    mins = post.get("posted_minutes_ago")
    if isinstance(mins, (int, float)) and mins >= 0:
        ts = datetime.now(timezone.utc) - timedelta(minutes=float(mins))
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = post.get("posted_at") or post.get("scraped_at")
    if raw:
        return str(raw)
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_cached_signals(min_rows: int = 4) -> dict[str, Any]:
    """Load Bright Data cache into signals for Public ears — no live HTTP.

    Prefer seed/cached_signals.json; fall back to the SERP fixture. Safe to call
    during a live call because it never touches Bright Data. Re-applies fixture
    ages so 'first public mention → call' stays demo-visible across restarts.
    """
    path = CACHED_SIGNALS if CACHED_SIGNALS.exists() else FIXTURE_SIGNALS
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        with db.connect() as conn:
            count = int(conn.execute(
                "SELECT COUNT(*) FROM signals WHERE about_fire=1"
            ).fetchone()[0])
        return {"ok": False, "source": str(path), "count": count, "inserted": 0}
    rows = raw if isinstance(raw, list) else []
    inserted = 0
    refreshed = 0
    with db.connect() as conn:
        for post in rows:
            if not isinstance(post, dict):
                continue
            text = str(post.get("text") or post.get("title") or "").strip()
            if not text:
                continue
            url = str(post.get("url") or "")
            source = str(post.get("source") or "serp")
            sid = str(post.get("id") or hashlib.sha1((url or text).encode()).hexdigest()[:16])
            about = post.get("about_fire")
            if about is None:
                about = "traffic" not in text.lower()
            scraped = _scraped_at_for(post)
            prior = conn.execute("SELECT id FROM signals WHERE id=?", (sid,)).fetchone()
            if prior:
                if post.get("posted_minutes_ago") is not None or post.get("posted_at"):
                    conn.execute("UPDATE signals SET scraped_at=? WHERE id=?", (scraped, sid))
                    refreshed += 1
                continue
            conn.execute(
                "INSERT INTO signals(id,source,url,text,about_fire,place_text,confidence,lat,lon,scraped_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    sid, source, url, text, int(bool(about)),
                    post.get("place_text"), post.get("confidence") or "unverified",
                    post.get("lat"), post.get("lon"), scraped,
                ),
            )
            inserted += 1
        count = int(conn.execute(
            "SELECT COUNT(*) FROM signals WHERE about_fire=1"
        ).fetchone()[0])
    return {
        "ok": True, "source": path.name, "count": count,
        "inserted": inserted, "refreshed": refreshed, "min_rows": min_rows,
    }


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
    """Seed Caltrans QuickMap closures from Bright Data cache (no live Browser API)."""
    rows: list[dict[str, Any]] = []
    if CACHED_CLOSURES.exists():
        try:
            raw = json.loads(CACHED_CLOSURES.read_text(encoding="utf-8"))
            rows = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError):
            rows = []
    if not rows:
        rows = [{
            "id": "hz_closure_genesee",
            "source": "brightdata_quickmap",
            "kind": "road_closure",
            "title": "Genesee Ave closure (Caltrans QuickMap)",
            "lat": 32.865,
            "lon": -117.250,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-117.255, 32.868], [-117.245, 32.868],
                    [-117.245, 32.862], [-117.255, 32.862], [-117.255, 32.868],
                ]],
            },
        }]
    with db.connect() as conn:
        for hazard in rows:
            geom = hazard.get("geometry") or {}
            conn.execute(
                "INSERT OR IGNORE INTO hazards(id,source,kind,title,geometry_json,lat,lon,scraped_at) "
                "VALUES(?,?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (
                    str(hazard.get("id") or hashlib.sha1(str(hazard.get("title")).encode()).hexdigest()[:12]),
                    str(hazard.get("source") or "brightdata_quickmap"),
                    str(hazard.get("kind") or "road_closure"),
                    str(hazard.get("title") or "Road closure"),
                    json.dumps(geom),
                    hazard.get("lat"),
                    hazard.get("lon"),
                ),
            )
        # Drop the old manual-only demo row if the Bright Data cache row replaced it.
        conn.execute("DELETE FROM hazards WHERE id='hz_closure_genesee' AND source='manual'")
