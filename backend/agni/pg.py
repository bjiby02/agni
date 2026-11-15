"""Postgres (Neon) adapter with the sqlite3 surface the rest of the app uses.

The app writes portable SQL with a few SQLite spellings. This module translates them:
`?` placeholders, strftime('now'), INSERT OR IGNORE/REPLACE, two-argument MIN, and
lastrowid. Rows behave like sqlite3.Row: row["col"], row[0] and dict(row) all work.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

NOW_SQL = "to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')"
# Conflict targets for INSERT OR REPLACE / OR IGNORE, by table.
KEYS = {"evidence": ["incident_id", "source"], "hazards": ["id"], "call_contacts": ["call_id"], "transfer_requests": ["call_id"],
        "reports": ["incident_id"], "poll_runs": ["name"], "wind_obs": ["station", "ts"], "satellite_hits": ["id"],
        "settings": ["id"], "ops_state": ["id"], "landmarks": ["id"]}
SERIAL = {"events": "seq", "bearings": "id", "decisions": "id", "dispatches": "id", "transcripts": "id", "rescues": "id",
          "merges": "id", "rings": "id", "warnings": "id", "handoffs": "id", "outbox": "id", "camera_frames": "id"}
_NOW = re.compile(r"strftime\('%Y-%m-%dT%H:%M:%fZ',\s*'now'\)")
_MIN2 = re.compile(r"\bMIN\(\s*([A-Za-z_]+)\s*,\s*([^()]+?)\)")
_INSERT = re.compile(r"^\s*INSERT\s+(OR\s+(REPLACE|IGNORE)\s+)?INTO\s+([a-z_]+)\s*\(([^)]*)\)", re.I | re.S)


def translate(sql: str) -> tuple[str, str | None]:
    """Return (postgres sql, serial column to RETURN or None)."""
    out = _NOW.sub(NOW_SQL, sql)
    out = _MIN2.sub(r"LEAST(\1,\2)", out)
    returning = None
    m = _INSERT.match(out)
    if m:
        mode, table, cols = (m.group(2) or "").upper(), m.group(3), [c.strip() for c in m.group(4).split(",")]
        out = _INSERT.sub(f"INSERT INTO {table}({m.group(4)})", out, count=1)
        if mode == "IGNORE":
            out += " ON CONFLICT DO NOTHING"
        elif mode == "REPLACE":
            keys = KEYS[table]
            sets = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols if c not in keys) or f"{keys[0]}=EXCLUDED.{keys[0]}"
            out += f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {sets}"
        if table in SERIAL:
            returning = SERIAL[table]
            out += f" RETURNING {returning}"
    out = out.replace("%", "%%").replace("?", "%s")
    return out, returning


class Row(dict):
    def __init__(self, cols: list[str], values: tuple):
        super().__init__(zip(cols, values))
        self._values = values

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)

    def keys(self):
        return super().keys()


class Cursor:
    def __init__(self, cur, returning):
        self._cur = cur
        self.lastrowid = None
        self.rowcount = cur.rowcount
        self._buffer = None
        if returning and cur.description:
            first = cur.fetchone()
            self.lastrowid = first[0] if first else None

    def _rows(self):
        if not self._cur.description:
            return []
        cols = [d.name for d in self._cur.description]
        return [Row(cols, tuple(r)) for r in self._cur.fetchall()]

    def fetchone(self):
        rows = self._rows() if self._buffer is None else self._buffer
        self._buffer = rows[1:]
        return rows[0] if rows else None

    def fetchall(self):
        rows = self._rows() if self._buffer is None else self._buffer
        self._buffer = []
        return rows

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    def __init__(self, url: str):
        import psycopg
        self._conn = psycopg.connect(url, autocommit=False)

    def execute(self, sql: str, params: tuple | list = ()):
        text, returning = translate(sql)
        cur = self._conn.cursor()
        cur.execute(text, tuple(params))
        return Cursor(cur, returning)

    def executemany(self, sql: str, seq):
        for params in seq:
            self.execute(sql, params)

    def executescript(self, script: str):
        with self._conn.cursor() as cur:
            cur.execute(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def schema() -> str:
    return (Path(__file__).resolve().parents[1] / "migrations" / "001_core.sql").read_text()
