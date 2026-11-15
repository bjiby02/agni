"""Bright Data early signals (C4): SERP plus Reddit and X scrapers, classified, cached, deduped.

- Runs on a timer, never from a voice tool, and skips while a call is active.
- Every raw response is cached to cache/brightdata/ for the no-Wi-Fi path.
- Coordinates come only from the cached landmark list. A post with no match stays unpinned.
- Only posts from the last 2 hours become pins, and every pin is gray "unverified".
Request shapes follow the Bright Data docs and are LIVE-UNVERIFIED.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import bus, db
from . import landmarks
from .config import settings
from .services import gemini

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "brightdata"
PRACTICE = CACHE / "practice_posts.json"
MAX_AGE = timedelta(hours=2)
FIRE_WORDS = re.compile(r"\b(smoke|fire|flames?|burning|humo|incendio|fuego)\b", re.I)
PAST_WORDS = re.compile(r"\b(throwback|anniversary|remember|years ago|20\d\d fires)\b", re.I)
CLASSIFY_SCHEMA = {"type": "OBJECT", "properties": {
    "is_fire_report": {"type": "BOOLEAN"}, "place_text": {"type": "STRING"},
    "confidence": {"type": "STRING", "enum": ["low", "med", "high"]}}, "required": ["is_fire_report", "confidence"]}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def active_call() -> bool:
    """A call that started in the last 15 minutes and has not ended. Scraping waits for it."""
    cutoff = _iso(_now() - timedelta(minutes=15))
    with db.connect() as conn:
        return conn.execute("SELECT 1 FROM calls WHERE ended_at IS NULL AND direction='inbound' AND started_at>=? LIMIT 1",
                            (cutoff,)).fetchone() is not None


def _cache(name: str, payload: Any) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


def _post(url: str, body: dict, timeout: int = 30) -> Any:
    token = os.environ.get("BRIGHTDATA_API_TOKEN") or os.environ.get("BRIGHTDATA_API_KEY") or ""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw)


def fetch_serp(query: str = "San Diego smoke fire") -> list[dict[str, Any]]:
    url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": query, "tbs": "qdr:h", "brd_json": 1})
    data = _post("https://api.brightdata.com/request", {"zone": os.environ["BRIGHTDATA_SERP_ZONE"], "url": url, "format": "raw"})
    _cache("serp_latest.json", data)
    items = []
    for row in (data.get("organic") or []) + (data.get("news") or []):
        if row.get("link"):
            items.append({"source": "serp", "url": row["link"], "text": f"{row.get('title', '')} {row.get('description', '')}".strip(),
                          "posted_at": None})
    return items


def fetch_dataset(source: str, dataset_var: str, inputs: list[dict]) -> list[dict[str, Any]]:
    dataset = os.environ.get(dataset_var, "").strip()
    if not dataset:
        return []
    data = _post(f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={urllib.parse.quote(dataset)}&format=json",
                 {"input": inputs}, timeout=60)
    _cache(f"{source}_latest.json", data)
    rows = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
    out = []
    for row in rows:
        text = row.get("title") or row.get("description") or row.get("text") or row.get("content") or ""
        link = row.get("url") or row.get("post_url") or row.get("link")
        if link and text:
            out.append({"source": source, "url": link, "text": str(text)[:600],
                        "posted_at": row.get("date_posted") or row.get("created_at") or row.get("date")})
    return out


def practice_items() -> list[dict[str, Any]]:
    data = json.loads(PRACTICE.read_text(encoding="utf-8"))
    now = _now()
    return [{**item, "posted_at": _iso(now - timedelta(minutes=item.get("minutes_ago", 0))), "practice": True}
            for item in data["items"]]


def classify(text: str) -> dict[str, Any]:
    out = gemini.generate_json("Is this a first-hand or news report of a fire or smoke happening now in San Diego County? "
                               "Give the place words if any. Post:\n" + text, CLASSIFY_SCHEMA)
    if out:
        return {"is_fire_report": bool(out.get("is_fire_report")), "place_text": out.get("place_text") or "",
                "confidence": out.get("confidence", "low"), "classifier": "gemini"}
    hit = bool(FIRE_WORDS.search(text)) and not PAST_WORDS.search(text)
    return {"is_fire_report": hit, "place_text": text, "confidence": "low", "classifier": "keyword fallback"}


def ingest(items: list[dict[str, Any]], scraped_at: str) -> list[dict[str, Any]]:
    created = []
    for item in items:
        sid = hashlib.sha256(item["url"].encode()).hexdigest()[:16]
        with db.connect() as conn:
            if conn.execute("SELECT 1 FROM signals WHERE id=?", (sid,)).fetchone():
                continue
        posted = item.get("posted_at")
        recent = True
        if posted:
            try:
                recent = _now() - datetime.fromisoformat(str(posted).replace("Z", "+00:00")) <= MAX_AGE
            except ValueError:
                recent = False
        verdict = classify(item["text"])
        match = landmarks.match_landmark(verdict["place_text"] or item["text"]) if verdict["is_fire_report"] else None
        lat, lon = (match["lat"], match["lon"]) if match and recent else (None, None)
        with db.connect() as conn:
            conn.execute("INSERT INTO signals(id,source,url,text,place_text,lat,lon,confidence,is_fire_report,classifier,posted_at,scraped_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (sid, item["source"], item["url"], item["text"], match["name"] if match else None, lat, lon,
                          verdict["confidence"], int(verdict["is_fire_report"]), verdict["classifier"], posted, scraped_at))
        if verdict["is_fire_report"]:
            data = {"id": sid, "source": item["source"], "url": item["url"], "text": item["text"][:280], "lat": lat, "lng": lon,
                    "confidence": verdict["confidence"], "scraped_at": scraped_at, "label": "unverified",
                    "practice": bool(item.get("practice"))}
            bus.emit("signal.new", None, data)
            created.append(data)
    return created


def attach_to_incidents() -> int:
    """A pinned signal within 800 m and 20 min of an open incident shows up in its evidence."""
    import geo
    attached = 0
    with db.connect() as conn:
        sigs = [dict(r) for r in conn.execute("SELECT * FROM signals WHERE lat IS NOT NULL AND is_fire_report=1")]
        incs = [dict(r) for r in conn.execute("SELECT id,lat,lon,created_at FROM incidents WHERE lat IS NOT NULL AND merged_into IS NULL "
                                             "AND status NOT IN ('closed','rejected')")]
    for inc in incs:
        near = [s for s in sigs if geo.haversine_m(inc["lat"], inc["lon"], s["lat"], s["lon"]) <= 800
                and abs((datetime.fromisoformat(inc["created_at"].replace("Z", "+00:00"))
                         - datetime.fromisoformat((s["posted_at"] or s["scraped_at"]).replace("Z", "+00:00"))).total_seconds()) <= 1200]
        if near:
            attached += 1
            with db.connect() as conn:
                conn.executemany("UPDATE signals SET incident_id=? WHERE id=?", [(inc["id"], s["id"]) for s in near])
                conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail) VALUES(?,?,?,?)",
                             (inc["id"], "public", "partial",
                              f"{len(near)} public post(s) nearby · unverified" + (" · practice fixture" if any(s['url'].startswith('https://practice.invalid') for s in near) else "")))
            bus.emit("evidence.updated", inc["id"], {"source": "public", "state": "partial", "count": len(near)})
    return attached


def poll(force: bool = False) -> dict[str, Any]:
    if active_call() and not force:
        return {"status": "skipped_active_call", "created": 0}
    scraped_at = _iso(_now())
    token = os.environ.get("BRIGHTDATA_API_TOKEN") or os.environ.get("BRIGHTDATA_API_KEY")
    if settings.mock or not token:
        items, mode = practice_items(), "practice fixture" if settings.mock else "cached (BRIGHTDATA_API_TOKEN not set)"
        if not settings.mock:
            items = _cached_items() or items
    else:
        items, mode = [], "live-unverified"
        try:
            if os.environ.get("BRIGHTDATA_SERP_ZONE"):
                items += fetch_serp()
            items += fetch_dataset("reddit", "BRIGHTDATA_REDDIT_DATASET_ID", [{"url": "https://www.reddit.com/r/sandiego/new/"}])
            items += fetch_dataset("x", "BRIGHTDATA_X_DATASET_ID", [{"url": "https://x.com/search?q=san%20diego%20smoke&f=live"}])
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            items, mode = _cached_items(), f"cached after error: {str(error)[:80]}"
    created = ingest(items, scraped_at)
    attached = attach_to_incidents()
    return {"status": "ok", "mode": mode, "seen": len(items), "created": len(created), "attached_incidents": attached,
            "scraped_at": scraped_at}


def _cached_items() -> list[dict[str, Any]]:
    """Last good scrape, used when the network is down. Read from the raw cache files."""
    items: list[dict[str, Any]] = []
    serp = CACHE / "serp_latest.json"
    if serp.exists():
        data = json.loads(serp.read_text(encoding="utf-8"))
        items += [{"source": "serp", "url": r["link"], "text": r.get("title", ""), "posted_at": None}
                  for r in (data.get("organic") or []) if r.get("link")]
    return items
