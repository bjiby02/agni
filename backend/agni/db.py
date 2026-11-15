"""Small SQLite event store for the AGNI API. Postgres can replace this adapter later."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("AGNI_DB_PATH", ROOT / "data" / "agni-api.sqlite"))


@contextmanager
def connect():
    """Open a short SQLite connection.

    Do NOT call bus.emit() (or open another writer) while this context is open —
    nested writers caused live phone `report_fire` 500s (`database is locked`)
    so the console never updated when someone dialed.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()


def init() -> None:
    with _LOCK, connect() as db:
        db.executescript((ROOT / "backend" / "migrations" / "001_core.sqlite.sql").read_text())
        # Additive live-call columns (safe on existing DBs).
        cols = {row["name"] for row in db.execute("PRAGMA table_info(calls)").fetchall()}
        if "phone_e164" not in cols:
            db.execute("ALTER TABLE calls ADD COLUMN phone_e164 TEXT")
        if "phone_last4" not in cols:
            db.execute("ALTER TABLE calls ADD COLUMN phone_last4 TEXT")

        count = db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        if not count:
            db.executemany("INSERT INTO units(id,callsign,type,lat,lon,status) VALUES(?,?,?,?,?,?)", [
                ("E42", "Engine 42", "wildland", 32.862, -117.239, "available"),
                ("E17", "Engine 17", "structure", 32.875, -117.266, "available"),
                ("R08", "Rescue 8", "rescue", 32.853, -117.225, "available"),
            ])
        # Landmark cache: seed/landmarks.json (+ optional Bright Data fixture). Locate() hits this first.
        try:
            from . import landmarks as landmark_service
            n = landmark_service.seed_landmarks_table(db)
            if n:
                print(f"landmarks seeded: {n}", flush=True)
        except Exception as exc:
            print(f"landmarks seed failed: {exc}", flush=True)


def event(type_: str, incident_id: str | None, data: dict[str, Any]) -> dict[str, Any]:
    with _LOCK, connect() as db:
        cur = db.execute("INSERT INTO events(type,incident_id,data_json) VALUES(?,?,?)",
                          (type_, incident_id, json.dumps(data, separators=(",", ":"))))
        row = db.execute("SELECT ts FROM events WHERE seq=?", (cur.lastrowid,)).fetchone()
        return {"type": type_, "incident_id": incident_id, "seq": cur.lastrowid,
                "ts": row["ts"], "data": data}


def events_after(seq: int, limit: int = 500) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?", (seq, limit)).fetchall()
    return [{"type": r["type"], "incident_id": r["incident_id"], "seq": r["seq"],
             "ts": r["ts"], "data": json.loads(r["data_json"])} for r in rows]


def state() -> dict[str, Any]:
    with connect() as db:
        incidents = [dict(r) for r in db.execute("SELECT * FROM incidents WHERE status NOT IN ('closed','rejected') AND merged_into IS NULL ORDER BY created_at DESC")]
        units = [dict(r) for r in db.execute("SELECT * FROM units ORDER BY callsign")]
        hazards = [dict(r) for r in db.execute("SELECT * FROM hazards ORDER BY scraped_at DESC")]
        last = db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
        merges = [dict(r) for r in db.execute("SELECT * FROM merges WHERE state IN ('suggested','accepted') ORDER BY id")]
        rings = [dict(r) for r in db.execute(
            "SELECT rings.* FROM rings JOIN (SELECT incident_id,MAX(id) AS latest_id FROM rings GROUP BY incident_id) latest "
            "ON rings.id=latest.latest_id ORDER BY rings.id DESC"
        )]
        try:
            signals = [dict(r) for r in db.execute(
                "SELECT * FROM signals WHERE about_fire=1 ORDER BY scraped_at DESC LIMIT 50")]
        except Exception:
            signals = []
        calls = [dict(r) for r in db.execute(
            "SELECT id,incident_id,direction,language,state,landmark_text,started_at,ended_at,"
            "phone_last4,phone_e164,needs_json FROM calls "
            "WHERE state IN ('live','human') ORDER BY started_at DESC")]
        for c in calls:
            try:
                needs = json.loads(c.pop("needs_json") or "{}")
            except Exception:
                needs = {}
            c["needs"] = needs
            c["needs_human"] = bool(needs.get("needs_human"))
            c["needs_human_reason"] = needs.get("needs_human_reason")
            # Recent spoken lines so the console can hydrate without waiting on SSE.
            rows = [dict(r) for r in db.execute(
                "SELECT speaker,text,lang,ts FROM transcripts WHERE call_id=? ORDER BY id DESC LIMIT 20",
                (c["id"],),
            )]
            c["transcript"] = list(reversed(rows))
    for h in hazards:
        h["geometry"] = json.loads(h.pop("geometry_json") or "null")
    for ring in rings:
        ring["geometry"] = json.loads(ring.pop("geom_json"))
        ring["wind"] = json.loads(ring.pop("wind_json"))
    return {"incidents": incidents, "units": units, "hazards": hazards, "merges": merges,
            "rings": rings, "signals": signals, "calls": calls, "last_seq": last}


def incident(iid: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM incidents WHERE id=?", (iid,)).fetchone()
        if row is None: return None
        item = dict(row)
        item["evidence"] = [dict(e) for e in db.execute("SELECT * FROM evidence WHERE incident_id=?", (iid,))]
        return item


def overflow_enabled() -> bool:
    with connect() as db:
        row = db.execute("SELECT overflow_enabled FROM settings WHERE id=1").fetchone()
    return bool(row and row[0])
