"""Create the AGNI intake and warning agents in ElevenLabs from agent/*.md and agent/tools/*.json.

    python3 scripts/create_agents.py            # dry run: prints the payloads with secrets masked
    python3 scripts/create_agents.py --create   # POST /v1/convai/agents/create (needs ELEVENLABS_API_KEY)

The request shape follows the ElevenLabs docs and is LIVE-UNVERIFIED (AGENTS.md A9). After the
first real create, export the agent from the dashboard and fix this script if the fields differ.
Prints only the new agent ids; add them to .env as ELEVENLABS_AGENT_ID / ELEVENLABS_WARN_AGENT_ID.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import _env

ROOT = _env.ROOT
INTAKE_TOOLS = ["report_fire", "add_bearing", "set_needs", "get_guidance", "send_cam_link"]
WARN_TOOLS = ["request_rescue"]


def tool(name: str, base: str, secret: str) -> dict:
    raw = (ROOT / "agent" / "tools" / f"{name}.json").read_text()
    raw = raw.replace("{PUBLIC_BASE_URL}", base.rstrip("/")).replace("{ELEVENLABS_TOOL_SECRET}", secret)
    return json.loads(raw)


def payload(name: str, prompt_file: str, tools: list[str], first: str, base: str, secret: str, transfer: bool) -> dict:
    prompt = {"prompt": (ROOT / "agent" / prompt_file).read_text(), "llm": "gemini-2.5-flash",
              "tools": [tool(t, base, secret) for t in tools]}
    if transfer:
        prompt["tools"].append({"type": "system", "name": "transfer_to_number",
                                "params": {"system_tool_type": "transfer_to_number", "transfers": [
                                    {"phone_number": os.environ.get("DISPATCHER_PHONE_NUMBER", ""),
                                     "condition": "get_guidance returned should_transfer=true, or the caller asks for a human"}]}})
    return {"name": name, "conversation_config": {
        "agent": {"first_message": first, "language": "en", "prompt": prompt},
        "asr": {"keywords": ["Torrey Pines", "Genesee", "Del Mar Heights", "Peñasquitos", "RIMAC", "Carmel Valley"]}}}


def mask(obj: dict) -> str:
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    for var in ("ELEVENLABS_TOOL_SECRET", "DISPATCHER_PHONE_NUMBER"):
        if os.environ.get(var):
            text = text.replace(os.environ[var], f"<{var}>")
    return text


def main() -> None:
    _env.load()
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    args = ap.parse_args()
    base = os.environ.get("PUBLIC_BASE_URL", "") or "https://YOUR-TUNNEL.example"
    secret = os.environ.get("ELEVENLABS_TOOL_SECRET", "") or "SET-ELEVENLABS_TOOL_SECRET"
    agents = [
        payload("AGNI intake", "system_prompt.md", INTAKE_TOOLS,
                "This is AGNI, an automated emergency line helping while 911 is busy. Where are you?", base, secret, True),
        payload("AGNI warning", "warning_prompt.md", WARN_TOOLS,
                "This is an automated fire warning from AGNI for San Diego County.", base, secret, False),
    ]
    if not args.create:
        for a in agents:
            print(mask(a))
        print("\nDry run. Re-run with --create once ELEVENLABS_API_KEY, PUBLIC_BASE_URL and ELEVENLABS_TOOL_SECRET are set.")
        return
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    missing = [v for v in ("ELEVENLABS_API_KEY", "PUBLIC_BASE_URL", "ELEVENLABS_TOOL_SECRET", "DISPATCHER_PHONE_NUMBER") if not os.environ.get(v)]
    if missing:
        sys.exit("Set these in .env first: " + ", ".join(missing))
    for a, var in zip(agents, ("ELEVENLABS_AGENT_ID", "ELEVENLABS_WARN_AGENT_ID")):
        req = urllib.request.Request("https://api.elevenlabs.io/v1/convai/agents/create", data=json.dumps(a).encode(),
                                     headers={"xi-api-key": key, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                agent_id = json.loads(resp.read()).get("agent_id")
        except urllib.error.HTTPError as error:
            sys.exit(f"{a['name']}: HTTP {error.code} {error.read()[:400].decode(errors='replace')}")
        print(f"{var}={agent_id}")


if __name__ == "__main__":
    main()
