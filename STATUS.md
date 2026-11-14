# AGNI build status

Mock mode is the build mode. Each task uses the states required by the agent brief.

| Task | Status | Evidence or next step |
|---|---|---|
| T0 Repo, config, mock switch, database, event bus and SSE | LIVE-UNVERIFIED | Offline event replay and caller-guidance API checks pass when the web stack is available. The default offline suite skips those checks when FastAPI is not installed. |
| T1 Voice tools and post-call webhook | LIVE-UNVERIFIED | Intake, bearing, needs, guidance, rescue, transcript and signed post-call routes are in progress. Mock API tests and ElevenLabs payload verification remain. H2/H3/H10 are needed for live calls. |
| T2 Dispatcher console shell | LIVE-UNVERIFIED | Responsive console now reads the AGNI state and event APIs. `npm run build` passes. Browser preview is blocked by the local-server sandbox policy; end-to-end UI proof remains. |
| T3 Landmark location and bearings | LIVE-UNVERIFIED | The landmark resolver only pins a cached record; unknown places remain unpinned. Offline matching tests pass. H4 and a live cached landmark import are needed. |
| T4 Camera wall and triage | LIVE-UNVERIFIED | Gemini box normalization, unknown fallback and frame caching pass offline tests. H4 is needed for live Gemini and camera checks. |
| T5 Evidence stack and human confirm/reject | LIVE-UNVERIFIED | Confirm/reject routes exist. Evidence ages, gray unknown states and acceptance tests remain. H7 is needed for live satellite data. |
| T6 Merge suggestions and undo | LIVE-UNVERIFIED | Offline tests prove suggest-only merge, human accept and undo restore the original row. |
| T7 Routing and safe shelter refusal | LIVE-UNVERIFIED | Closure avoidance and downwind shelter refusal pass offline tests. Fallback routes remain labeled estimates. H8 is needed for live ORS. |
| T8 Idempotent dispatch and serial bridge | LIVE-UNVERIFIED | Dispatch idempotency exists. Serial adapter and one-write test remain. H9 is needed for the hardware check. |
| T9 Bright Data pollers and classifier | BLOCKED | Fixture poller remains. H5 is needed for live Bright Data zones, token and dataset IDs. |
| T10 JUMP IN and callback hand-back | BLOCKED | Mock transfer path remains. H10 is needed for phone checks. |
| T11 Wind spread ring | LIVE-UNVERIFIED | A 100 m-cell, 10 km model grid produces a labeled 30-minute downwind estimate. The NW-wind test passes. |
| T12 Targeted warning and rescue | LIVE-UNVERIFIED | The warning API needs human confirmation, a ring and opted-in recipients. Offline tests reject unlisted contacts. H10 is needed for live calls. |
| T13 Neon branches and surge simulation | LIVE-UNVERIFIED | The isolated SQLite surge rehearsal processed 75 calls into 3 visible incidents in 0.64 s and wrote `backend/sim/sim.json`. H6 is needed for Neon branches. |
| T14 After-action report and measured proof panel | BLOCKED | Must read measured `sim.json` and `eval.json` only. |
| T15 Evaluation harness | BLOCKED | Persona and fixture evaluation remain. |
| T16 Stretch integrations | BLOCKED | Tiger Data only if the surge counter needs it. Solana is cut in v2. |
| T17 README, demo and rehearsal checklist | LIVE-UNVERIFIED | README is updated. A mock end-to-end intake-to-dispatch workflow passed. `make demo` and the acceptance checklist remain. H11 is needed for Devpost submission. |

## Needs the account owner

- H1: Done. The independent public repository is configured and `main` is pushed.
- H2-H3: ElevenLabs and Twilio accounts, keys and phone integration.
- H4: Gemini API key.
- H5: Bright Data zones, token and dataset IDs.
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
