"""Neon helpers: apply the schema, create the surge-sim branch, reset it to its parent.

    python3 scripts/neon.py migrate          # apply backend/migrations/001_core.sql to DATABASE_URL
    python3 scripts/neon.py branches         # list branches (names and ids only)
    python3 scripts/neon.py create-surge     # create surge-sim from main; writes DATABASE_URL_SURGE to .env
    python3 scripts/neon.py reset-surge      # restore surge-sim from its parent (Reset to Calm for the surge)

Needs NEON_API_KEY and NEON_PROJECT_ID. Only branches named surge-sim or practice may be
created or reset here; main is never touched. Connection strings go into .env, never to the
terminal. Neon API paths follow the docs and are LIVE-UNVERIFIED (AGENTS.md A9).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import _env

API = "https://console.neon.tech/api/v2"
ALLOWED = {"surge-sim", "practice"}


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{API}{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['NEON_API_KEY']}",
                                          "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as error:
        sys.exit(f"Neon {method} {path}: HTTP {error.code} {error.read()[:300].decode(errors='replace')}")


def project() -> str:
    return os.environ["NEON_PROJECT_ID"]


def branches() -> list[dict]:
    return call("GET", f"/projects/{project()}/branches").get("branches", [])


def by_name(name: str) -> dict | None:
    return next((b for b in branches() if b.get("name") == name), None)


def write_env(key: str, value: str) -> None:
    path = _env.ROOT / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [l for l in lines if not l.startswith(f"{key}=")] + [f"{key}={value}"]
    path.write_text("\n".join(lines) + "\n")


def connection_uri(branch_id: str) -> str:
    q = urllib.parse.urlencode({"branch_id": branch_id, "database_name": os.environ.get("NEON_DATABASE", "neondb"),
                                "role_name": os.environ.get("NEON_ROLE", "neondb_owner")})
    return call("GET", f"/projects/{project()}/connection_uri?{q}")["uri"]


def migrate(url: str) -> None:
    import psycopg
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute((_env.ROOT / "backend" / "migrations" / "001_core.sql").read_text())
    print("schema applied")


def main() -> None:
    _env.load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "migrate":
        url = os.environ.get("DATABASE_URL", "")
        if not url.startswith(("postgres://", "postgresql://")):
            sys.exit("Set DATABASE_URL to the Neon main connection string in .env first.")
        migrate(url)
        return
    missing = [v for v in ("NEON_API_KEY", "NEON_PROJECT_ID") if not os.environ.get(v)]
    if missing:
        sys.exit("Set in .env: " + ", ".join(missing))
    if cmd == "branches":
        for b in branches():
            print(f"{b['name']:20} {b['id']}  parent={b.get('parent_id')}")
    elif cmd == "create-surge":
        if by_name("surge-sim"):
            sys.exit("surge-sim already exists. Use reset-surge.")
        main_branch = next((b for b in branches() if b.get("default") or b.get("primary")), None)
        if not main_branch:
            sys.exit("Could not find the default branch.")
        made = call("POST", f"/projects/{project()}/branches",
                    {"branch": {"name": "surge-sim", "parent_id": main_branch["id"]}, "endpoints": [{"type": "read_write"}]})
        branch_id = made["branch"]["id"]
        time.sleep(3)
        write_env("DATABASE_URL_SURGE", connection_uri(branch_id))
        print(f"created surge-sim ({branch_id}); DATABASE_URL_SURGE written to .env")
    elif cmd == "reset-surge":
        branch = by_name("surge-sim")
        if not branch or branch["name"] not in ALLOWED:
            sys.exit("No surge-sim branch. Run create-surge first.")
        started = time.monotonic()
        call("POST", f"/projects/{project()}/branches/{branch['id']}/restore", {"source_branch_id": branch["parent_id"]})
        print(f"surge-sim restored from its parent in {time.monotonic() - started:.1f} s")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
