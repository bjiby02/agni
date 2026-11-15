# Live end-to-end setup

AGNI is now configured for **live mode** (`AGNI_MOCK=0`). Mock fixtures are only used when a service key is missing or during `make test` / `make demo`.

## 1. Fill local `.env` (never paste keys in chat)

Required for phone E2E:

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_AGENT_ID` (or run `make agents` after the key is set)
- `ELEVENLABS_WARN_AGENT_ID` (warning agent; can reuse intake id temporarily)
- `ELEVENLABS_PHONE_NUMBER_ID` (Twilio number imported into ElevenLabs)
- `ELEVENLABS_TOOL_SECRET` (must match tool header)
- `DISPATCHER_PHONE_NUMBER` (JUMP IN target, E.164)
- `PUBLIC_BASE_URL` (set by `./tunnel.sh`)
- `GEMINI_API_KEY`

Also replace placeholder numbers in `seed/warn_list.json` with **opted-in** team/judge phones near the demo pin.

Optional but expected for the full product:

- Bright Data token + SERP zone
- `FIRMS_MAP_KEY`, `ORS_API_KEY`
- `SERIAL_PORT` after flashing `hardware/uno_station/uno_station.ino`
- Neon `DATABASE_URL` when ready (`USE_NEON=1`)

## 2. Boot sequence

```sh
make live-ready          # fails until core keys exist
make agents              # create/update ElevenLabs agents from agent/
make seed
make dev                 # API on :8000
./tunnel.sh              # public URL + repoint tool webhooks
cd frontend && npm run dev
make live-check          # one real request per keyed service
```

## 3. Console (storyboard HUD)

Open **http://127.0.0.1:5173** (must be the Vite from `/Users/bijinjiby/AGNI/frontend`, not another checkout).

You should see: full-bleed dark map, floating Fires list with `why_line`, gray unknown evidence, LIVE ALERTCalifornia camera strip, red **JUMP IN**, keys `↵ C A J R W M/N U`.

The UI is event-driven: phone tools → SSE → fire row + transcript. It is not a static mock.

## 4. Live judge path

1. Turn overflow ON in the console (top-right pill).
2. Judge dials the Twilio/ElevenLabs number.
3. Agent tools hit `PUBLIC_BASE_URL/api/tools/*` → console shows `call.started` / fire row within ~1 s.
4. Dispatcher: **Confirm** → route card → **Approve dispatch** → **JUMP IN** → Hand back → **R** ring → **W** Send warning → Press 1 → rescue pin → **S** Sign & close.

## 5. Safety

- Outbound calls only to numbers in `seed/warn_list.json` with `opted_in: true`.
- Humans still Confirm / Approve / Send.
- `/api/proof` never invents metrics.
