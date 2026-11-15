#!/usr/bin/env python3
"""Print live E2E readiness. Exit 1 if core telephony keys are missing."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        print("MISSING: .env (copy from .env.example)")
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def present(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def main() -> int:
    load_env()
    mock = (os.environ.get("AGNI_MOCK") or "1").strip() in {"1", "true", "yes", "on"}
    print(f"AGNI_MOCK={'1 (still mock)' if mock else '0 (live mode)'}")
    required = [
        ("AGNI_MOCK=0", not mock),
        ("OVERFLOW_ENABLED", present("OVERFLOW_ENABLED")),
        ("ELEVENLABS_API_KEY", present("ELEVENLABS_API_KEY")),
        ("ELEVENLABS_AGENT_ID", present("ELEVENLABS_AGENT_ID")),
        ("ELEVENLABS_WARN_AGENT_ID", present("ELEVENLABS_WARN_AGENT_ID") or present("ELEVENLABS_AGENT_ID")),
        ("ELEVENLABS_PHONE_NUMBER_ID", present("ELEVENLABS_PHONE_NUMBER_ID")),
        ("ELEVENLABS_TOOL_SECRET", present("ELEVENLABS_TOOL_SECRET")),
        ("DISPATCHER_PHONE_NUMBER", present("DISPATCHER_PHONE_NUMBER")),
        ("PUBLIC_BASE_URL", present("PUBLIC_BASE_URL")),
        ("GEMINI_API_KEY", present("GEMINI_API_KEY")),
    ]
    optional = [
        ("BRIGHTDATA_API_TOKEN + SERP_ZONE", present("BRIGHTDATA_API_TOKEN") and present("BRIGHTDATA_SERP_ZONE")),
        ("FIRMS_MAP_KEY", present("FIRMS_MAP_KEY")),
        ("ORS_API_KEY", present("ORS_API_KEY")),
        ("NEON / DATABASE_URL", present("DATABASE_URL") and "postgres" in (os.environ.get("DATABASE_URL") or "")),
        ("SERIAL_PORT", present("SERIAL_PORT")),
        ("OPERATOR_TOKEN", present("OPERATOR_TOKEN")),
    ]
    missing = []
    for label, ok in required:
        mark = "OK" if ok else "NEED"
        print(f"  [{mark}] {label}")
        if not ok:
            missing.append(label)
    print("Optional:")
    for label, ok in optional:
        print(f"  [{'OK' if ok else '--'}] {label}")

    warn = ROOT / "seed" / "warn_list.json"
    text = warn.read_text(encoding="utf-8") if warn.exists() else "[]"
    if "+1555555" in text or '"opted_in": true' not in text.lower().replace(" ", ""):
        # crude check: placeholder demo numbers still present
        if "+1555555" in text:
            print("  [NEED] seed/warn_list.json still has placeholder +1555555… numbers")
            print("         Replace with real opted-in team/judge phones (E.164) near the demo pin.")
            missing.append("warn_list real phones")
    if missing:
        print("\nLive E2E is blocked until you fill the NEED items in local .env (never paste keys in chat).")
        print("Then: make agents && ./tunnel.sh && make live-check && make dev")
        return 1
    print("\nCore live keys look present. Run: make live-check && make agents && ./tunnel.sh && make dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
