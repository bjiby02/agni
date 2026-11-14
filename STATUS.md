# AGNI build status

Mock mode is the build mode. Each task uses the states required by the agent brief.

| Task | Status | Evidence or next step |
|---|---|---|
| T0 Repo, config, mock switch, database, event bus and SSE | LIVE-UNVERIFIED | Offline event replay and caller-guidance API checks pass when the web stack is available. The default offline suite skips those checks when FastAPI is not installed. |
| T1 Voice tools and post-call webhook | LIVE-UNVERIFIED | Six tools match Build Spec §12 (`report_fire` accepts `address_text`). `agent/` holds both prompts and tool JSON; `scripts/create_agents.py` dry-runs offline and creates both agents with `--create`. H2/H3/H10 are needed for a live call. |
| T2 Dispatcher console shell | LIVE-UNVERIFIED | Leaflet map on CARTO dark_matter, incident queue, live transcript, evidence, keys C/A/J/W/M/N/U. State rebuilds from the event stream on refresh. `npm run build` passes and a headless browser render showed no app errors. Map tiles need network. |
| T3 Landmark location and bearings | LIVE-UNVERIFIED | The landmark resolver only pins a cached record; unknown places remain unpinned. Offline matching tests pass. H4 and a live cached landmark import are needed. |
| T4 Camera wall and triage | LIVE-UNVERIFIED | Gemini box normalization, unknown fallback and frame cache pass offline tests. Camera wall shows the 3 nearest stills with age and a gray "Not analyzed" verdict; `scripts/cache_feeds.py` saves stills for Wi-Fi-safe mode. H4 is needed for live verdicts. |
| T5 Evidence stack and human confirm/reject | LIVE-UNVERIFIED | Every source always has a row; unknown is gray with its reason (test_demo_flow). Confirm writes a decision and emits `incident.confirmed`. H7 is needed for live satellite data. |
| T6 Merge suggestions and undo | LIVE-UNVERIFIED | Offline tests prove suggest-only merge, human accept and undo restore the original row. |
| T7 Routing and safe shelter refusal | LIVE-UNVERIFIED | Closure avoidance and downwind refusal pass. Fixed a bug where a refused shelter could still be chosen. Route line is labeled "Direction only". H8 is needed for live ORS. |
| T8 Idempotent dispatch and serial bridge | LIVE-UNVERIFIED | Approving twice gives one dispatch and one serial write (fake records bytes). Sketch in `hardware/uno_station/`. H9 is needed for the buzz. |
| T9 Bright Data pollers and classifier | BLOCKED | Fixture poller remains. H5 is needed for live Bright Data zones, token and dataset IDs. |
| T10 JUMP IN and callback hand-back | LIVE-UNVERIFIED | `POST /api/calls/{id}/takeover` writes the summary card, then `get_guidance` returns `should_transfer=true` so the agent runs `transfer_to_number`. Hand-back calls the caller back through the ElevenLabs outbound-call adapter. Mock tests pass. H2/H3/H10 needed for a phone test. |
| T11 Wind spread ring | LIVE-UNVERIFIED | A 100 m-cell, 10 km model grid produces a labeled 30-minute downwind estimate. The NW-wind test passes. |
| T12 Targeted warning and rescue | LIVE-UNVERIFIED | Warning needs confirm, a ring and opted-in homes, then submits an ElevenLabs batch (mock records it). Practice mode uses fake 555 numbers when `seed/warn_list.json` is empty. Press 1 drops a rescue pin. H10 is needed for live calls. |
| T13 Neon branches and surge simulation | LIVE-UNVERIFIED | The isolated SQLite surge processes 75 calls into 4 incidents and writes `backend/sim/sim.json`. H6 is needed for Neon branches. |
| T14 After-action report and measured proof panel | LIVE-UNVERIFIED | Close drafts one line per milestone citing its event, measures the clock from event timestamps, hashes the canonical log; a human signs. Proof panel reads only `eval.json`/`sim.json`. Gemini draft and Solana anchor need keys (Solana is a stretch). |
| T15 Evaluation harness | LIVE-UNVERIFIED | `make eval` writes `eval.json` with n per metric. Merge precision is measured on 20 synthetic pairs. Frames, posts and caller personas show "not measured yet" until labeled data and keys exist. |
| T16 Stretch integrations | BLOCKED | Tiger Data only if the surge counter needs it. Solana is cut in v2. |
| T17 README, demo and rehearsal checklist | LIVE-UNVERIFIED | `make demo` plays every storyboard beat in mock mode in about 2 s and passes. `/ops` has Reset to Calm, a labeled replay call, surge and Wi-Fi-safe mode. H11 is needed for Devpost. |

## Not built yet

- C2 caller camera page `/sos/cam/{token}` with the compass. `send_cam_link` still answers that the link is not available.
- T9 Bright Data pollers for posts, closures and shelters (still BLOCKED on H5). The closure on the map is a labeled practice snapshot.
- Timed pollers for NWS wind and FIRMS. The wind is a labeled practice value in mock mode.
- Postgres/PostGIS migration and the Neon `surge-sim` branch switch (H6).
- Stretch: Tiger Data counter, Solana memo.

## Needs the account owner

- H1: Done. The independent public repository is configured and `main` is pushed.
- H2-H3: ElevenLabs and Twilio accounts, keys and phone integration.
- H4: Gemini API key.
- H5: Bright Data. The $100 credit is applied. Still needed: SERP zone `agni_serp` (started), Web Unlocker and Browser API zones, the API token in `.env`, and the Reddit and X dataset IDs.
- H6: Neon project and API key.
- H7: NASA FIRMS map key.
- H8: OpenRouteService key.
- H9: Connect the Arduino Uno and flash its firmware.
- H10: Add only opted-in phone numbers, set the dispatcher number and answer test calls.
- H11: Submit the Devpost entry.

Enter keys in local `.env`. Do not send keys in chat.

## Safety state

- Overflow is disabled by default.
- Mock mode does not call external services.
- A human must confirm a fire, approve a dispatch and approve a warning.
- No phone call is live-verified.
- Do not show unmeasured metrics as results.
