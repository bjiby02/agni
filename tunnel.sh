#!/bin/bash
# Public HTTPS for ElevenLabs tools via localhost.run (*.lhr.life).
# NEVER starts Cloudflare quick tunnel or Serveo (they race and die mid-call).
# If PUBLIC_BASE_URL already passes /health + report_fire, leave it alone.
set -u
cd "$(dirname "$0")"
ROOT="$(pwd)"
PORT="${AGNI_PORT:-8000}"
LHR_LOG=/tmp/agni-lhr.log
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"

current_base() {
  grep -E '^PUBLIC_BASE_URL=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'
}

lhr_url_from_log() {
  grep -Eo 'https://[a-zA-Z0-9.-]+\.lhr\.life' "$LHR_LOG" 2>/dev/null | tail -1 || true
}

tunnel_ok() {
  local base="$1"
  [ -n "$base" ] || return 1
  case "$base" in *trycloudflare.com*|*serveo.net*|*serveousercontent.com*) return 1 ;; esac
  local h
  h=$(curl -4 -sS -o /dev/null -w "%{http_code}" --max-time 12 "$base/health" 2>/dev/null || echo 000)
  [ "$h" = "200" ] || return 1
  python3 - "$base" "$ROOT" <<'PY'
import json, sys, urllib.request, urllib.error
from pathlib import Path
base, root = sys.argv[1].rstrip("/"), Path(sys.argv[2])
env = {}
for line in root.joinpath(".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
req = urllib.request.Request(
    base + "/api/tools/report_fire",
    data=json.dumps({
        "conversation_id": "conv_tunnel_sh",
        "landmark_text": "behind the Vons on Carmel Valley",
        "what_seen": "smoke",
        "language": "en",
    }).encode(),
    method="POST",
    headers={
        "Content-Type": "application/json",
        "X-Agni-Tool-Secret": env.get("ELEVENLABS_TOOL_SECRET", ""),
    },
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        raise SystemExit(0 if r.status == 200 else 1)
except urllib.error.HTTPError as e:
    raise SystemExit(0 if e.code == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
}

repoint_agents() {
  python3 - "$1" "$ROOT" <<'PY'
import json, pathlib, re, sys, urllib.request, urllib.error
URL, ROOT = sys.argv[1].rstrip("/"), pathlib.Path(sys.argv[2])
envp = ROOT / ".env"
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
secret = env.get("ELEVENLABS_TOOL_SECRET", "")
if not key:
    print("  SKIP agent repoint (need ELEVENLABS_API_KEY)")
    raise SystemExit(0)
tools = []
for path in sorted((ROOT / "agent" / "tools").glob("*.json")):
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
for label, aid in (("intake", env.get("ELEVENLABS_AGENT_ID")), ("warn", env.get("ELEVENLABS_WARN_AGENT_ID"))):
    if not aid:
        continue
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/convai/agents/{aid}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        print(f"  {label} tools ->", resp.status, URL)
PY
}

# Kill only competing methods — never api_watch from here either
pkill -f 'cloudflared tunnel --url' 2>/dev/null || true
pkill -f 'ssh.*serveo.net' 2>/dev/null || true
pkill -f 'api_watch' 2>/dev/null || true

BASE=$(current_base)
if tunnel_ok "$BASE"; then
  echo "tunnel already OK: $BASE"
  exit 0
fi

LOG=$(lhr_url_from_log)
if [ -n "$LOG" ] && tunnel_ok "$LOG"; then
  echo "adopting live lhr: $LOG"
  repoint_agents "$LOG"
  exit 0
fi

if ! pgrep -f 'nokey@localhost.run|ssh.*localhost\.run' >/dev/null 2>&1; then
  : >"$LHR_LOG"
  nohup ssh -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=4 \
    -o ExitOnForwardFailure=yes -o TCPKeepAlive=yes \
    -R 80:127.0.0.1:"$PORT" nokey@localhost.run >>"$LHR_LOG" 2>&1 </dev/null &
fi

URL=""
for _ in $(seq 1 40); do
  sleep 1
  URL=$(lhr_url_from_log)
  if [ -n "$URL" ] && tunnel_ok "$URL"; then
    break
  fi
  URL=""
done

if [ -z "$URL" ]; then
  echo "could not raise localhost.run tunnel (see $LHR_LOG)"
  exit 1
fi

echo "tunnel: $URL -> localhost:$PORT"
repoint_agents "$URL"
echo "keep alive: bash scripts/keep_live.sh"
echo "DO NOT run api_watch.sh (it thrash-kills uvicorn)"
