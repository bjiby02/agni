#!/usr/bin/env python3
"""Create ElevenLabs intake + warning agents from agent/ when ELEVENLABS_API_KEY is set."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("SKIP: ELEVENLABS_API_KEY not set")
        return 0
    prompt = (AGENT_DIR / "system_prompt.md").read_text(encoding="utf-8")
    tools = []
    for path in sorted((AGENT_DIR / "tools").glob("*.json")):
        tools.append(json.loads(path.read_text(encoding="utf-8")))
    body = {
        "name": "AGNI Overflow Intake",
        "conversation_config": {
            "agent": {
                "prompt": {"prompt": prompt, "tools": tools},
                "first_message": "This is AGNI, helping 911 while lines are busy. What do you see?",
            }
        },
    }
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/convai/agents/create",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())
        print(json.dumps({"ok": True, "agent": payload}, indent=2)[:2000])
        return 0
    except urllib.error.HTTPError as error:
        print(f"LIVE-UNVERIFIED: create failed ({error.code})")
        print(error.read()[:500].decode("utf-8", errors="replace"))
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"LIVE-UNVERIFIED: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
