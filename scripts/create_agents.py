#!/usr/bin/env python3
"""Create ElevenLabs intake + warning agents from agent/ when ELEVENLABS_API_KEY is set."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"


def load_env() -> dict[str, str]:
    path = ROOT / ".env"
    env: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), env[key.strip()])
    return env


def upsert_env(updates: dict[str, str]) -> None:
    path = ROOT / ".env"
    text = path.read_text() if path.exists() else ""
    for key, value in updates.items():
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
        line = f'{key}="{value}"'
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            text += ("\n" if text and not text.endswith("\n") else "") + line + "\n"
    path.write_text(text)


def api(key: str, path: str, method: str = "GET", body: dict | None = None):
    req = urllib.request.Request(
        "https://api.elevenlabs.io" + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.status, json.loads(resp.read() or b"{}")


def build_tools(base_url: str, secret: str) -> list[dict]:
    tools = []
    for path in sorted((AGENT_DIR / "tools").glob("*.json")):
        tool = json.loads(path.read_text(encoding="utf-8"))
        name = tool.get("name") or path.stem
        tool.setdefault("api_schema", {})
        tool["api_schema"]["url"] = f"{base_url.rstrip('/')}/api/tools/{name}"
        tool["api_schema"]["method"] = "POST"
        tool["api_schema"].setdefault("request_headers", {})
        tool["api_schema"]["request_headers"]["X-Agni-Tool-Secret"] = secret
        tool["api_schema"]["request_headers"]["Content-Type"] = "application/json"
        tools.append(tool)
    return tools


def create_agent(key: str, name: str, prompt: str, first_message: str, tools: list[dict],
                 existing_id: str | None = None) -> str:
    body = {
        "name": name,
        "conversation_config": {
            "agent": {
                "prompt": {"prompt": prompt, "tools": tools},
                "first_message": first_message,
            }
        },
    }
    if existing_id:
        status, payload = api(key, f"/v1/convai/agents/{existing_id}", "PATCH", body)
        if 200 <= status < 300:
            return existing_id
    status, payload = api(key, "/v1/convai/agents/create", "POST", body)
    agent_id = payload.get("agent_id") or payload.get("id")
    if not agent_id:
        raise RuntimeError(f"create failed: {payload}")
    return str(agent_id)


def main() -> int:
    env = load_env()
    key = env.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        print("SKIP: ELEVENLABS_API_KEY not set")
        return 0
    secret = env.get("ELEVENLABS_TOOL_SECRET", "").strip() or "change-me-tool-secret"
    base = env.get("PUBLIC_BASE_URL", "").strip() or "http://127.0.0.1:8000"
    prompt = (AGENT_DIR / "system_prompt.md").read_text(encoding="utf-8")
    warn_prompt = prompt + "\n\n## Warning-call mode\nYou are placing a targeted wildfire warning. Speak slowly. Give direction and shelter. End with: Press 1 or say help if you need help getting out. On 1 or help, call request_rescue.\n"
    tools = build_tools(base, secret)
    try:
        intake_id = create_agent(
            key,
            "AGNI Overflow Intake",
            prompt,
            "This is AGNI, helping 911 while lines are busy. What do you see?",
            tools,
            env.get("ELEVENLABS_AGENT_ID") or None,
        )
        warn_id = create_agent(
            key,
            "AGNI Targeted Warning",
            warn_prompt,
            "This is an AGNI Alert for San Diego County.",
            [t for t in tools if t.get("name") == "request_rescue"],
            env.get("ELEVENLABS_WARN_AGENT_ID") or None,
        )
    except urllib.error.HTTPError as error:
        print(f"LIVE create failed ({error.code})")
        print(error.read()[:800].decode("utf-8", errors="replace"))
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"LIVE create failed: {error}")
        return 1
    upsert_env({
        "ELEVENLABS_AGENT_ID": intake_id,
        "ELEVENLABS_WARN_AGENT_ID": warn_id,
        "ELEVENLABS_TOOL_SECRET": secret,
    })
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "agent_id").write_text(intake_id + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "intake_agent_id": intake_id, "warn_agent_id": warn_id,
                      "tool_base": base}, indent=2))
    print("Wrote agent ids into local .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
