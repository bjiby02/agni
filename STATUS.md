# AGNI build status

**Product mode is live (`AGNI_MOCK=0`).** Offline unit tests still force mock. Live phone/data paths activate when their keys are present in local `.env`.

| Task | Status | Evidence or next step |
|---|---|---|
| T0 Repo, config, mock switch, database, event bus and SSE | DONE | Offline SSE tests pass. |
| T1 Voice tools and post-call webhook | LIVE-UNVERIFIED | Live tool URLs + `make agents` + tunnel repoint ready. Needs H2/H3/H10. |
| T2 Dispatcher console shell | LIVE-UNVERIFIED | Storyboard HUD at :5173 (CARTO dark, fire rows, why_line, keys, SSE). Live phone still needs H10. |
| T3 Landmark location and bearings | LIVE-UNVERIFIED | Cache match offline; live Gemini extract needs H4. |
| T4 Camera wall and triage | LIVE-UNVERIFIED | Live Gemini vision when `AGNI_MOCK=0` + H4. |
| T5 Evidence stack and human confirm/reject | LIVE-UNVERIFIED | why_line + Confirm. FIRMS key in `.env`; live satellite path still needs a measured check. |
| T6 Merge suggestions and undo | DONE | Offline tests pass. |
| T7 Routing and safe shelter refusal | LIVE-UNVERIFIED | ORS key in `.env`; live avoid_polygons path still needs a measured check (OSRM fallback remains). |
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


## PM friction pass (phone → console) — Nov 14 eve

| Hard point | Before | After |
|---|---|---|
| Tunnel 502 / no caller on UI | Flaky SSH + API restarts killing tunnel | Tunnel tools **200**; API reload kills only `:8000` listener; keep_live does not pkill healthy SSH |
| SMS / long URLs | Twilio trial 572006; agent/dispatcher friction | CODE path + Copy short link; agent never asks caller to type a URL; SMS when `TWILIO_CONTENT_SID` set |
| Call feels unhelpful | Generic “stay safe” after intake | `get_guidance` speaks real shelter cardinal (e.g. west toward Torrey Pines Center); prompt pushed to ElevenLabs |
| Console next step vague on live call | “Listen then Confirm” without Confirm button | `live_confirm`: landmark chip, giant CODE, Copy link, Confirm ↵ primary |

Smoke (tunnel tools + local confirm/dispatch): report_fire / add_bearing / set_needs / get_guidance / send_cam_link all **200**; Confirm → route (3 units) → dispatch idempotent (same id twice). Residual score **~8/10**.

## Jobs E2E arc + wow ending (Nov 14 night) — DONE (UI)

Silent demo script: `DEMO_FLOW.md`. Stage rail (Standby → Call → Confirm → Approve → Help) advances from real state/events. Climax banner + wow card **only** after real `unit.dispatched` (“Caller heard. Fire confirmed. Help is on the way.” + unit/ETA); `warning.sent` adds opt-in homes beat. Hard-refresh :5173. No commit / no tunnel thrash.

## Console WOW pass (Nov 14 eve) — DONE (mock)

Local signals glass box (`/api/state` + `signal.new`), incoming `call.started` pop (auto-select + Open/Jump in), AGNI-stuck → `call.needs_human` + J takeover CTA. Prove: `python -m unittest backend.tests.test_needs_human` + hard-refresh :5173. JUMP IN live phone still H10 / `DISPATCHER_PHONE_NUMBER`.

## Live-call screenshot fix (Nov 14 night) — DONE (local)

Bijin screenshot: gray Esri “Map data not yet available”, coach copy looking like transcript, “Jacobs Call Center” with no pin/CCTV.
- Map → HTTPS CARTO `dark_all` (+ invalidateSize); Esri Canvas removed.
- Role legend moved out of transcript; `/api/state` hydrates `calls[].transcript`.
- Spoken landmark preferred; miss → region geocode, else “Location: not yet”; CCTV waits for lat/lon.
- Agent prompt patched: use spoken place words (Vons / Torrey Pines / UCSD…), not call-center names.
- **Landmark cache expand (Nov 14 night):** ~70 UCSD/La Jolla/Torrey/Carmel Valley/Mira Mesa/Del Mar places in `seed/landmarks.json` (Jacobs/Geisel/RIMAC/Price/…). DB seeded on init. Caller GPS + geocode fallback. Prove: `python -m unittest backend.tests.test_landmarks`.
Hard-refresh :5173 **and restart API** (so landmarks re-seed) before next dial. Tunnel left up (no thrash).

## BLOCKED for full live demo (Bijin)

- **NEEDS BIJIN:** Twilio trial → upgrade + approve a Content Template, then set `TWILIO_CONTENT_SID` in `.env` (API already wired). Until then SMS to callers fails; dispatcher Copy-link path is the demo workaround.
- JUMP IN warm transfer still needs a answered live phone check (H10).
- Real warning calls: only opt-in `+18582479608` is live-safe in `seed/warn_list.json`; keep placeholders refused.

### BLOCKED: needs Bijin – Twilio SMS camera links (trial 572006)

Trial Twilio **cannot** send freeform SMS (`572006`) and **cannot** create Content Templates via API (`20003` Content API: "not available on a Trial account"). Custom camera URLs need an upgraded account (costs money — stop/ask before paying).

After upgrade:

1. Console → Messaging → Content Template Builder (or wait; agent can `POST https://content.twilio.com/v1/Content`).
2. Create English `twilio/text` template: body `AGNI camera: {{1}}`, sample var `https://da.gd/xxxx`, friendly name `agni_camera_link`.
3. Approve if the console asks (SMS text templates are usually instant after upgrade; WhatsApp approval is separate and not needed here).
4. Copy the Content SID (`HX…`) into local `.env` as `TWILIO_CONTENT_SID=` (name already in `.env.example`).
5. Confirm the From number (`TWILIO_PHONE_NUMBER`) can SMS the verified/opt-in recipient (trial error `572003` = wrong From for that recipient).
6. Tell the agent `TWILIO_CONTENT_SID ready` — code path already sends `ContentSid` + `ContentVariables={"1":"<short-url>"}` when set; freeform `Body` remains the fallback when unset.

Smoke (2026-11-15): Content create → HTTP 401/20003; freeform → HTTP 400/572006; predefined `sms_account_alerts` → HTTP 403/572003 (From not assigned for +18582479608). No `TWILIO_CONTENT_SID` written.

## Live keys now in `.env` (not blocked)

- `FIRMS_MAP_KEY` set → satellite evidence uses FIRMS (honest empty if no heat).
- `ORS_API_KEY` set → road routing can use OpenRouteService.

Console + ALERTCalifornia camera wall + SSE/tool path are up on `:5173` / `:8000`.

## Stack ready (Nov 14 eve — thrash stop)

- **Ready:** partial. Old uvicorn shells exited 143/137; stack restarted. Serveo off — do not start keep_live/tunnel_watch.
- **Tunnel:** cloudflared `https://cope-dry-continuously-prospects.trycloudflare.com` — local /health 200, public /health 530.
- **API:** uvicorn 127.0.0.1:8000. **Console:** Vite 127.0.0.1:5173 (200).
- **Dial:** only when public /health is 200 — AGNI Twilio/ElevenLabs overflow (opt-in). Console http://127.0.0.1:5173

## Live boot

```sh
make live-ready
make agents
./tunnel.sh
make dev
# frontend: cd frontend && npm run dev
make live-check
```
