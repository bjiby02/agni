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

## 3. Live judge path

1. Turn overflow ON in the console.
2. Judge dials the Twilio/ElevenLabs number.
3. Agent tools hit `PUBLIC_BASE_URL/api/tools/*`.
4. Dispatcher Confirm → Approve (serial `D42`) → JUMP IN → Hand back (callback) → ring → Send warning (batch call) → Press 1 → rescue pin → Sign & close.

## 4. Safety

- Outbound calls only to numbers in `seed/warn_list.json` with `opted_in: true`.
- Humans still Confirm / Approve / Send.
- `/api/proof` never invents metrics.
