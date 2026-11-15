# SanD Hacks Fall 2026 — sponsor credits from Opening Ceremony PDF

Source of truth: `Opening Ceremony - Fall 2026.pdf` (prefer over older AGENTS.md credit notes when they conflict).

## Claim map for AGNI live E2E

| Sponsor | Ceremony says | Exact start links | Promo / claim | AGNI `.env` keys |
|---|---|---|---|---|
| **Gemini (Google AI Studio)** | Grab an API key; Best Use of Gemini API prize | `https://mlh.link/aistudio` → AI Studio welcome; `https://mlh.link/gemini`; workshop `https://mlh.link/sandhacks-gemini` (Sat 2:00–2:30 WLH 2207) | Free AI Studio key after Google sign-in | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| **Bright Data** | Every team gets **$100 API credits**; Data for Good track $1k/$750/$500 | Control panel `https://brightdata.com/cp/start` | Ceremony slide does **not** print a code. Use team room code **`sandhacks26`** only as the fill-in when the CP asks (from AGENTS room note; blank in ceremony). | `BRIGHTDATA_API_TOKEN`, `BRIGHTDATA_SERP_ZONE`, `BRIGHTDATA_BROWSER_WS`, dataset IDs |
| **ElevenLabs** | All participants get **Creator tier credits**; Scale for winners | Sign up `https://elevenlabs.io/app/sign-up`; keys in app settings | Ceremony: Creator credits for all. Claim path not printed (no Discord URL on slides). AGENTS said SanD Hacks Discord — ceremony QR points to **Slack** for hacker ops. Prefer Slack/staff desk for the Creator claim link if Discord is empty. | `ELEVENLABS_API_KEY`, agent/phone ids |
| **Neon** | All participants get **Neon promo credits**; Best DB/Agent Backend track | `https://console.neon.tech/signup` | Ceremony does **not** print a code. Use **`hackonneon`** when billing asks (AGENTS room note). | `NEON_API_KEY`, `NEON_PROJECT_ID`, `DATABASE_URL` |
| **Vultr** (optional hosting) | Best Use of Vultr | `https://mlh.link/vultr` | Promo **`MAJORLEAGUEHACKING`** (printed on ceremony slide) | `VULTR_API_KEY` |
| **Tiger Data** (stretch) | Best Use of Tiger Data | `https://mlh.link/tigerdata` | Ceremony: get started link only | `TIGER_DATABASE_URL` |
| **Solana** (cut in AGNI v2) | Best Use of Solana | `https://mlh.link/solana` | — | cut |
| **GoDaddy Registry** | Best domain | `https://mlh.link/GoDaddyRegistry` | Code **`MLHSH77`** | n/a |
| **SpaceXSI / Cursor+Grok** | Workshop track | `https://mlh.link/spacexsi`, `https://mlh.link/sandhacks-spacexsi` | Workshop Sat | n/a for AGNI keys |

## Not on ceremony slides (still needed for AGNI phone E2E)

| Need | Where | Notes |
|---|---|---|
| Twilio trial number | `https://www.twilio.com/try-twilio` | Import into ElevenLabs for `ELEVENLABS_PHONE_NUMBER_ID` |
| NASA FIRMS map key | `https://firms.modaps.eosdis.nasa.gov/api/map_key/` | Email registration |
| OpenRouteService | `https://openrouteservice.org/dev/#/signup` → HeiGIT | Free key; OSRM works without it |
| Opt-in phones | `seed/warn_list.json` | Real E.164 only |

## Ops channels (ceremony)

- Hacker Guide + **Slack** QR codes (not Discord) on “Important QR Codes” slide
- Help desk / Slack for questions; staff in hackathon shirts
- WiFi: eduroam or UCSD-Guest

## Conflict resolution

1. Ceremony PDF wins for printed links and Vultr/GoDaddy codes.
2. For Bright Data / Neon **numeric promo strings** missing from slides, keep `sandhacks26` / `hackonneon` from the team room note until Slack/staff gives a replacement.
3. ElevenLabs Creator claim: try Slack/staff first (ceremony), Discord only if staff points there (AGENTS).
