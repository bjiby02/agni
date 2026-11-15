#!/bin/bash
# Keep AGNI API + ONE public tunnel alive for ElevenLabs tools.
#
# Method lock (no flap):
#   1. If PUBLIC_BASE_URL already passes /health + tool POST → leave it alone.
#   2. Prefer localhost.run (*.lhr.life) — current demo primary.
#   3. NEVER start Cloudflare quick tunnel or Serveo while an lhr URL is healthy.
#   4. Named CF / ngrok only if credentials exist AND lhr is dead (opt-in later).
#
# Never kill a healthy uvicorn. Never kill a healthy lhr SSH.
# Never run api_watch.sh from here.
set -u
ROOT=/Users/bijinjiby/AGNI
API_LOG=/tmp/agni-api.log
LHR_LOG=/tmp/agni-lhr.log
WATCH_LOG=/tmp/agni-keep-live.log
LOCKDIR=/tmp/agni-keep-live.lock.dir
VENV="$ROOT/.venv/bin/uvicorn"
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"

if ! mkdir "$LOCKDIR" 2>/dev/null; then
  if pgrep -f 'scripts/keep_live.sh' >/dev/null 2>&1; then
    echo "$(date -u +%H:%M:%S) keep_live already running — exit" >>"$WATCH_LOG"
    exit 0
  fi
  rmdir "$LOCKDIR" 2>/dev/null || true
  mkdir "$LOCKDIR" 2>/dev/null || true
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$WATCH_LOG"; }

current_base() {
  grep -E '^PUBLIC_BASE_URL=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'
}

lhr_url_from_log() {
  grep -Eo 'https://[a-zA-Z0-9.-]+\.lhr\.life' "$LHR_LOG" 2>/dev/null | tail -1 || true
}

lhr_alive() {
  pgrep -f 'nokey@localhost.run' >/dev/null 2>&1 || pgrep -f 'ssh.*localhost\.run' >/dev/null 2>&1
}

ensure_api() {
  if curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
    return 0
  fi
  if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    sleep 2
    curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null && return 0
  fi
  log "API down — starting (no tunnel restart)"
  # Only kill dead/hung listeners — never pkill uvicorn by name while healthy
  for p in $(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true); do
    kill "$p" 2>/dev/null || true
  done
  sleep 1
  cd "$ROOT/backend" || exit 1
  nohup "$VENV" agni.main:app --host 127.0.0.1 --port 8000 >>"$API_LOG" 2>&1 &
  for _ in $(seq 1 30); do
    sleep 1
    curl -sf --max-time 2 http://127.0.0.1:8000/health >/dev/null && { log "API up"; return 0; }
  done
  log "API failed to start"
  return 1
}

# Strict: /health 200 AND report_fire 200 (or 401 with wrong secret still proves tunnel)
tunnel_ok() {
  local base="$1"
  [ -n "$base" ] || return 1
  case "$base" in
    *trycloudflare.com*|*serveo.net*|*serveousercontent.com*) return 1 ;; # never adopt flaky methods
  esac
  local code
  code=$(curl -4 -sS -o /dev/null -w "%{http_code}" --max-time 12 "$base/health" 2>/dev/null || echo 000)
  [ "$code" = "200" ] || return 1
  code=$(python3 - "$base" "$ROOT" <<'PY'
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
        "conversation_id": "conv_keep_live_probe",
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
        print(r.status)
except urllib.error.HTTPError as e:
    print(e.code)
except Exception:
    print(0)
PY
)
  [ "$code" = "200" ] || [ "$code" = "401" ]
}

repoint_agents() {
  local URL="$1"
  python3 - <<PY
from pathlib import Path
import re, json, urllib.request, urllib.error
ROOT = Path("$ROOT")
URL = "$URL".rstrip("/")
text = (ROOT / ".env").read_text()
if "PUBLIC_BASE_URL=" in text:
    text = re.sub(r"^PUBLIC_BASE_URL=.*$", f'PUBLIC_BASE_URL="{URL}"', text, flags=re.M)
else:
    text += f'\\nPUBLIC_BASE_URL="{URL}"\\n'
(ROOT / ".env").write_text(text)
env = {}
for line in text.splitlines():
    if not line.strip() or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"')
ek = env.get("ELEVENLABS_API_KEY")
if not ek:
    raise SystemExit("no EL key")
secret = env.get("ELEVENLABS_TOOL_SECRET") or "x"
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
for aid in (env.get("ELEVENLABS_AGENT_ID"), env.get("ELEVENLABS_WARN_AGENT_ID")):
    if not aid:
        continue
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/convai/agents/{aid}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={"xi-api-key": ek, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        print("agent", aid[:12], r.status, URL)
PY
}

kill_competitors() {
  # Never let CF quick / Serveo fight lhr
  pkill -f 'cloudflared tunnel --url' 2>/dev/null || true
  pkill -f 'ssh.*serveo.net' 2>/dev/null || true
  pkill -f 'api_watch' 2>/dev/null || true
}

start_lhr() {
  if lhr_alive; then
    log "lhr ssh already running — not spawning another"
    local u
    u=$(lhr_url_from_log)
    [ -n "$u" ] && echo "$u" && return 0
    return 1
  fi
  kill_competitors
  : >"$LHR_LOG"
  nohup ssh -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=4 \
    -o ExitOnForwardFailure=yes -o TCPKeepAlive=yes \
    -R 80:127.0.0.1:8000 nokey@localhost.run >>"$LHR_LOG" 2>&1 </dev/null &
  local NEW=""
  for _ in $(seq 1 40); do
    sleep 1
    NEW=$(lhr_url_from_log)
    if [ -n "$NEW" ] && tunnel_ok "$NEW"; then
      echo "$NEW"
      return 0
    fi
  done
  log "lhr URL never healthy (see $LHR_LOG)"
  return 1
}

ensure_tunnel() {
  ensure_api || return 1
  kill_competitors
  local base NEW
  base=$(current_base)

  # Healthy current base (must be lhr) → do nothing.
  if tunnel_ok "$base"; then
    return 0
  fi

  # Adopt live log URL without restart if SSH still up.
  if lhr_alive; then
    NEW=$(lhr_url_from_log)
    if [ -n "$NEW" ] && tunnel_ok "$NEW"; then
      if [ "$NEW" != "$base" ]; then
        log "Tunnel OK $NEW — repointing agents"
        repoint_agents "$NEW" || log "repoint failed"
      fi
      return 0
    fi
    log "lhr ssh up but tools not OK — waiting (no kill, no CF/Serveo)"
    for _ in $(seq 1 15); do
      sleep 2
      NEW=$(lhr_url_from_log)
      if [ -n "$NEW" ] && tunnel_ok "$NEW"; then
        log "Tunnel recovered $NEW — repointing"
        repoint_agents "$NEW" || log "repoint failed"
        return 0
      fi
      tunnel_ok "$base" && return 0
    done
    if [ "${AGNI_DEMO_STABLE:-0}" = "1" ]; then
      log "DEMO_STABLE: leaving unhealthy lhr alone (no CF/Serveo)"
      return 1
    fi
    log "lhr stuck unhealthy — restarting lhr ONLY once"
    pkill -f 'nokey@localhost.run' 2>/dev/null || true
    pkill -f 'ssh.*localhost\.run' 2>/dev/null || true
    sleep 2
  fi

  if [ "${AGNI_DEMO_STABLE:-0}" = "1" ]; then
    log "DEMO_STABLE: no healthy tunnel — not starting CF/Serveo"
    return 1
  fi

  log "Starting localhost.run (lhr) tunnel"
  NEW=$(start_lhr) || return 1
  log "Tunnel OK $NEW — repointing agents"
  repoint_agents "$NEW" || log "repoint failed"
  return 0
}

ensure_tunnel
while true; do
  ensure_api
  kill_competitors
  base=$(current_base)
  if ! tunnel_ok "$base"; then
    NEW=$(lhr_url_from_log)
    if [ -n "$NEW" ] && tunnel_ok "$NEW"; then
      [ "$NEW" != "$base" ] && repoint_agents "$NEW" || true
    else
      ensure_tunnel
    fi
  fi
  sleep 20
done
