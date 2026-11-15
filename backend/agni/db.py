"""Event store for the AGNI API: SQLite by default, Postgres/Neon when DATABASE_URL is a postgres URL."""
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
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def is_postgres() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


def backend_name() -> str:
    return "postgres" if is_postgres() else "sqlite"


@contextmanager
def connect():
    if is_postgres():
        from .pg import Connection
        db = Connection(DATABASE_URL)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init() -> None:
    with _LOCK, connect() as db:
        if is_postgres():
            from .pg import schema
            db.executescript(schema())
        else:
            for name in ("001_core.sqlite.sql", "002_ops.sqlite.sql", "003_feeds.sqlite.sql"):
                db.executescript((ROOT / "backend" / "migrations" / name).read_text())

        count = db.execute("SELECT COUNT(*) FROM units").fetchone()[0]
        if not count:
            db.executemany("INSERT INTO units(id,callsign,type,lat,lon,status) VALUES(?,?,?,?,?,?)", [
                ("E42", "Engine 42", "wildland", 32.862, -117.239, "available"),
                ("E17", "Engine 17", "structure", 32.875, -117.266, "available"),
                ("R08", "Rescue 8", "rescue", 32.853, -117.225, "available"),
            ])


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
        ops = dict(db.execute("SELECT mode,safe_mode,replay_label FROM ops_state WHERE id=1").fetchone() or {})
        handoffs = [dict(r) for r in db.execute("SELECT id,call_id,incident_id,summary,transfer_status,started_at,ended_at,resumed_by FROM handoffs ORDER BY id DESC LIMIT 20")]
        reports = [dict(r) for r in db.execute("SELECT incident_id,log_sha256,signed_by,signed_at,anchor_status FROM reports")]
        rescues = [dict(r) for r in db.execute("SELECT r.id,r.incident_id,r.call_id,r.created_at FROM rescues r ORDER BY r.id DESC LIMIT 50")]
    for h in hazards:
        h["geometry"] = json.loads(h.pop("geometry_json") or "null")
    for ring in rings:
        ring["geometry"] = json.loads(ring.pop("geom_json"))
        ring["wind"] = json.loads(ring.pop("wind_json"))
    return {"incidents": incidents, "units": units, "hazards": hazards, "merges": merges,
            "rings": rings, "last_seq": last, "ops": ops, "handoffs": handoffs, "reports": reports,
            "rescues": rescues}


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
