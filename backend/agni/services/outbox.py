"""Records what an adapter would have sent. Mock adapters write here instead of calling out."""
from __future__ import annotations

import json
from typing import Any

from .. import db


def record(channel: str, target: str, payload: dict[str, Any], status: str) -> int:
    with db.connect() as conn:
        cur = conn.execute("INSERT INTO outbox(channel,target,payload_json,status) VALUES(?,?,?,?)",
                           (channel, target, json.dumps(payload, separators=(",", ":")), status))
        return int(cur.lastrowid)


def rows(channel: str | None = None) -> list[dict[str, Any]]:
    with db.connect() as conn:
        q = "SELECT * FROM outbox" + (" WHERE channel=?" if channel else "") + " ORDER BY id"
        found = conn.execute(q, (channel,) if channel else ()).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in found]
