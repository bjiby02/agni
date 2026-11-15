# AGNI build status

Mock mode is the build mode. Each task uses the states required by the agent brief.

| Task | Status | Evidence or next step |
|---|---|---|
| T0 Repo, config, mock switch, database, event bus and SSE | DONE | Offline SSE replay and reconnect tests pass. `make test` green. |
| T1 Voice tools and post-call webhook | LIVE-UNVERIFIED | Tool routes + signed post-call exist; mock tool tests pass. Live phone needs H2/H3/H10. |
| T2 Dispatcher console shell | LIVE-UNVERIFIED | React console: Leaflet CARTO dark_matter, fire rows, why_line, NEW badge, keyboard map, JUMP IN. `npm run build` passes. Browser E2E not run in sandbox. |
| T3 Landmark location and bearings | LIVE-UNVERIFIED | Cached landmark match + bearing ellipse offline tests pass. Live Gemini extract needs H4. |
| T4 Camera wall and triage | LIVE-UNVERIFIED | Vision normalize/cache/`cant_tell` offline tests pass. Live frames need H4. |
| T5 Evidence stack and human confirm/reject | LIVE-UNVERIFIED | Evidence API + why_line + Confirm/Reject. FIRMS shows gray “Key not set” without H7. |
| T6 Merge suggestions and undo | DONE | Offline tests: suggest-only, accept, undo restore. |
| T7 Routing and safe shelter refusal | LIVE-UNVERIFIED | Closure avoidance + downwind refusal offline tests pass. Live ORS needs H8. |
| T8 Idempotent dispatch and serial bridge | LIVE-UNVERIFIED | Dispatch idempotency + mock serial `D42\n` recorded. Hardware buzz needs H9. |
| T9 Bright Data pollers and classifier | LIVE-UNVERIFIED | Fixture SERP → `signal.new` unverified. HTTP blocked while call live (test). Live zones need H5. |
| T10 JUMP IN and callback hand-back | LIVE-UNVERIFIED | Mock jump-in + hand-back emit `handoff.started` / `handoff.ended{resumed_by:agent,mode:callback}`. Live transfer needs H10. |
| T11 Wind spread ring | DONE | 100 m / 10 km / 30-min estimate; NW wind test passes. |
| T12 Targeted warning and rescue | LIVE-UNVERIFIED | Opt-in + ring filter + Press-1 → `rescue.requested`. Mock queues only. Live dial needs H10. |
| T13 Neon branches and surge simulation | LIVE-UNVERIFIED | SQLite isolated surge → `sim.json`. Neon branches BLOCKED on H6. |
| T14 After-action report and proof panel | DONE | Draft from events; Sign closes; `/api/proof` reads only `sim.json`/`eval.json` or null. |
| T15 Evaluation harness | LIVE-UNVERIFIED | `make eval` writes fixture-measured `eval.json` with `n` per metric. Live personas need H2/H10. |
| T16 Stretch integrations | BLOCKED | Cut per A8 until T0–T14 are live-green. Solana cut in v2. |
| T17 README, demo and rehearsal checklist | LIVE-UNVERIFIED | `make demo` runs storyboard path in mock. Devpost submit is H11. |

## Needs the account owner

- H1: Done. Public repo configured.
- H2–H3: ElevenLabs + Twilio keys and phone import.
- H4: Gemini API key.
- H5: Bright Data zones, token, dataset IDs.
- H6: Neon project + API key.
- H7: NASA FIRMS map key.
- H8: OpenRouteService key.
- H9: Flash `hardware/uno_station/uno_station.ino` and set `SERIAL_PORT`.
- H10: Opt-in phones in `seed/warn_list.json`, `DISPATCHER_PHONE_NUMBER`, answer test calls.
- H11: Devpost submit.

Enter keys in local `.env`. Do not send keys in chat.

## Safety state

- Overflow is disabled by default.
- Mock mode does not call external services.
- A human must confirm a fire, approve a dispatch and approve a warning.
- No phone call is live-verified.
- Do not show unmeasured metrics as results.
