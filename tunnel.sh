#!/bin/bash
# Public tunnel to the FastAPI app on :8000 and repoint ElevenLabs tool URLs.
cd "$(dirname "$0")"
ROOT="$(pwd)"
PORT="${AGNI_PORT:-8000}"

load_env() {
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
}

start_tunnel() {
  pkill -f "serveo.net" 2>/dev/null || true
  pkill -f "localhost.run" 2>/dev/null || true
  sleep 1
  : > /tmp/agni-tunnel.log
  nohup ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=20 \
    -o ExitOnForwardFailure=yes -R 80:localhost:"$PORT" serveo.net \
    > /tmp/agni-tunnel.log 2>&1 &
  for _ in $(seq 1 20); do
    sleep 2
    URL=$(grep -oE "https://[a-z0-9-]+\.serveousercontent\.com" /tmp/agni-tunnel.log | head -1)
    [ -n "$URL" ] && return 0
  done
  : > /tmp/agni-tunnel.log
  nohup ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=20 \
    -o ExitOnForwardFailure=yes -R 80:127.0.0.1:"$PORT" nokey@localhost.run \
    > /tmp/agni-tunnel.log 2>&1 &
  for _ in $(seq 1 20); do
    sleep 2
    URL=$(grep -oE "https://[a-z0-9]+\.lhr\.life" /tmp/agni-tunnel.log | head -1)
    [ -n "$URL" ] && return 0
  done
  return 1
}

repoint_agent() {
  python3 - "$1" "$ROOT" <<'PY'
import json, pathlib, re, sys, urllib.request, urllib.error
URL, ROOT = sys.argv[1].rstrip("/"), pathlib.Path(sys.argv[2])
envp = ROOT / ".env"
if not envp.exists():
    print("  no .env"); raise SystemExit(1)
text = envp.read_text()
if "PUBLIC_BASE_URL=" in text:
    text = re.sub(r"^PUBLIC_BASE_URL=.*$", f'PUBLIC_BASE_URL="{URL}"', text, flags=re.M)
else:
    text += f'\nPUBLIC_BASE_URL="{URL}"\n'
envp.write_text(text)
env = {}
for line in text.splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"')
key = env.get("ELEVENLABS_API_KEY", "")
aid = env.get("ELEVENLABS_AGENT_ID", "")
secret = env.get("ELEVENLABS_TOOL_SECRET", "")
if not key or not aid:
    print("  SKIP agent repoint (need ELEVENLABS_API_KEY + ELEVENLABS_AGENT_ID)")
    print("  PUBLIC_BASE_URL updated to", URL)
    raise SystemExit(0)
tools_dir = ROOT / "agent" / "tools"
tools = []
for path in sorted(tools_dir.glob("*.json")):
    tool = json.loads(path.read_text())
    name = tool.get("name") or path.stem
    tool.setdefault("api_schema", {})
    tool["api_schema"]["url"] = f"{URL}/api/tools/{name}"
    tool["api_schema"]["method"] = "POST"
    tool["api_schema"].setdefault("request_headers", {})
    tool["api_schema"]["request_headers"]["X-Agni-Tool-Secret"] = secret
    tool["api_schema"]["request_headers"]["Content-Type"] = "application/json"
    tools.append(tool)
body = {"conversation_config": {"agent": {"prompt": {"tools": tools}}}}
req = urllib.request.Request(
    f"https://api.elevenlabs.io/v1/convai/agents/{aid}",
    data=json.dumps(body).encode(),
    method="PATCH",
    headers={"xi-api-key": key, "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=40) as resp:
        print("  agent tools repointed ->", resp.status, URL)
except urllib.error.HTTPError as err:
    print("  agent repoint failed", err.code, err.read()[:300].decode())
    raise SystemExit(1)
PY
}

load_env
if ! start_tunnel; then
  echo "could not raise a public tunnel"
  exit 1
fi
URL=$(grep -oE "https://[a-z0-9-]+\.serveousercontent\.com" /tmp/agni-tunnel.log | head -1)
[ -z "$URL" ] && URL=$(grep -oE "https://[a-z0-9]+\.lhr\.life" /tmp/agni-tunnel.log | head -1)
echo "tunnel: $URL -> localhost:$PORT"
repoint_agent "$URL"
echo "health: curl -s $URL/health"
