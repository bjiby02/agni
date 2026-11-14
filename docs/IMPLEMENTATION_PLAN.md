# AGNI implementation plan

## Product slice

Deliver a three-minute, end-to-end crisis dispatch demo:

1. A caller report creates or updates an incident.
2. Visual signals raise the incident priority.
3. Live hazard data informs a safe responder selection.
4. The dispatcher sees the recommendation, dispatches a unit, and can immediately assume control.

## Delivery sequence

| Phase | Outcome | Acceptance check |
| --- | --- | --- |
| 1. Foundation | Repository, local API, command UI, seeded scenario | One command starts each service and dashboard renders a live incident |
| 2. Dispatch core | Postgres/PostGIS persistence, unit scoring, hazard ingestion | A blocked route is deprioritized and decision rationale is visible |
| 3. Multimodal triage | Mobile capture page and structured vision result | High-confidence smoke/flame signals change triage deterministically |
| 4. Voice bridge | Voice tool webhooks and tactical radio generation | Dispatcher can hear an actionable callout and take control without losing the incident |
| 5. Resilience | Cached data snapshot, simulated mode, load script | Demo remains coherent without provider or venue network access |
| 6. Submission | Video, write-up, deployed link, repo | All judging artifacts are public and rehearsed |

## Workstreams

### Dispatch domain

- Replace the in-memory repository with Neon Postgres and PostGIS.
- Store incidents, units, hazards, assignments, audit events, and provider outputs separately.
- Implement route-aware scoring: availability, ETA, capability, and hazard penalty.
- Keep human decisions append-only in an audit log.

### Intelligence ingestion

- Fetch authorized public road closure, fire advisory, and shelter information through the selected data provider.
- Normalize every record to GeoJSON, preserve source URL/timestamp, and expire stale data.
- Retain a reviewed local snapshot for the demo; label it clearly as cached.

### Vision and voice

- Require explicit caller consent before camera upload.
- Send compressed frames to the vision adapter and validate structured output before any priority change.
- Expose narrow, authenticated voice-tool endpoints; never let model output dispatch directly without server validation.
- Treat dispatcher override as the highest-priority state transition.

### Console

- Left: active queue and compact transcript.
- Center: map, hazards, units, route, and data freshness.
- Right: vision evidence, dispatch action, and takeover controls.
- Use accessible labels, keyboard control, and explicit demo/live badges.

## Data model target

`incidents`, `units`, `hazards`, `assignments`, `vision_assessments`, `call_events`, and `operator_actions` form the core schema. Spatial columns use WGS84 geography; provider payloads live in JSONB with a source and observed timestamp.

## Safety and privacy gates

- Prominently state that the product is a prototype, not an emergency service.
- Minimize retention of audio, images, and precise location; require consent for camera capture.
- Authenticate inbound webhooks and verify provider signatures.
- Keep a human in the loop for any live dispatch-related action.
- Do not claim a route is safe; phrase it as a recommended route based on currently available data.

## Demo script

1. Start in simulation mode with one active brush-fire report.
2. Reveal a closure that blocks the nearest engine’s direct route.
3. Submit a pre-recorded visual assessment showing smoke and a blocked exit.
4. Show priority escalation and recommended available unit.
5. Dispatch the unit, play the simulated radio brief, and activate dispatcher override.

