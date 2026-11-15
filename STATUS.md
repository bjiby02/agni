# AGNI build status

**Product mode is live (`AGNI_MOCK=0`).** Offline unit tests still force mock. Live phone/data paths activate when their keys are present in local `.env`.

| Task | Status | Evidence or next step |
|---|---|---|
| T0 Repo, config, mock switch, database, event bus and SSE | DONE | Offline SSE tests pass. |
| T1 Voice tools and post-call webhook | LIVE-UNVERIFIED | Live tool URLs + `make agents` + tunnel repoint ready. Needs H2/H3/H10. |
| T2 Dispatcher console shell | LIVE-UNVERIFIED | Leaflet console + JUMP IN/hand-back wired. |
| T3 Landmark location and bearings | LIVE-UNVERIFIED | Cache match offline; live Gemini extract needs H4. |
| T4 Camera wall and triage | LIVE-UNVERIFIED | Live Gemini vision when `AGNI_MOCK=0` + H4. |
| T5 Evidence stack and human confirm/reject | LIVE-UNVERIFIED | why_line + Confirm. FIRMS live needs H7. |
| T6 Merge suggestions and undo | DONE | Offline tests pass. |
| T7 Routing and safe shelter refusal | LIVE-UNVERIFIED | ORS/OSRM live adapter wired; needs H8 (OSRM works without key). |
| T8 Idempotent dispatch and serial bridge | LIVE-UNVERIFIED | Live serial when `SERIAL_PORT` set (H9). |
| T9 Bright Data pollers and classifier | LIVE-UNVERIFIED | Live SERP when token+zone set; poller skips during live calls. Needs H5. |
| T10 JUMP IN and callback hand-back | LIVE-UNVERIFIED | `should_transfer` + live Twilio outbound callback. Needs H10. |
| T11 Wind spread ring | DONE | Offline model tests pass. |
| T12 Targeted warning and rescue | LIVE-UNVERIFIED | Live ElevenLabs batch/outbound submit wired. Needs H2/H3/H10 + real warn_list phones. |
| T13 Neon branches and surge simulation | LIVE-UNVERIFIED | SQLite surge works; Neon needs H6. |
| T14 After-action report and proof panel | DONE | Live Gemini draft when keyed; proof reads measured files only. |
| T15 Evaluation harness | LIVE-UNVERIFIED | Fixture `make eval` works; live personas need phones. |
| T16 Stretch integrations | BLOCKED | Cut until core live path is green. |
| T17 README, demo and rehearsal checklist | LIVE-UNVERIFIED | See `docs/LIVE_E2E.md`. Devpost is H11. |

## Needs the account owner (blocks live E2E)

Ceremony credit map: [docs/CEREMONY_SPONSOR_CREDITS.md](docs/CEREMONY_SPONSOR_CREDITS.md) (Opening Ceremony PDF is source of truth).

Fill these in **local `.env` only**, then say `keys ready`:

- H4 Gemini: sign in at `https://mlh.link/aistudio` (Google) → copy key into `GEMINI_API_KEY`
- H2 ElevenLabs Creator: claim via **Slack**/staff (ceremony QR), then `https://elevenlabs.io/app/sign-up` → API key
- H3 Twilio trial → import number into ElevenLabs → `ELEVENLABS_PHONE_NUMBER_ID`
- H5 Bright Data: `https://brightdata.com/cp/start` + promo **`sandhacks26`** (room note; not printed on ceremony slide)
- H6 Neon: `https://console.neon.tech/signup` + promo **`hackonneon`** when billing asks
- H7 FIRMS email map key; H8 ORS/HeiGIT (optional; OSRM works)
- H9 Uno `SERIAL_PORT`; H10 opted-in phones + `DISPATCHER_PHONE_NUMBER`
- H11 Devpost

Optional ceremony codes: Vultr `MAJORLEAGUEHACKING`, GoDaddy `MLHSH77`.

## Live boot

```sh
make live-ready
make agents
./tunnel.sh
make dev
# frontend: cd frontend && npm run dev
make live-check
```
