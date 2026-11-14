# Sponsor integration checklist

This file contains setup work for local development only. Keep credentials in `.env`; do not paste tokens, coupon codes, or private links into source code, commits, screenshots, or issue comments.

## Bright Data - impact data layer

- Team credit: $100 in API credits.
- Promo code: `sandhacks26`.
- Create one team-owned service credential after signup; place it in `BRIGHTDATA_API_TOKEN` locally.
- First integration: ingest a small, attributable set of road closures and evacuation resources into `hazards`.
- Show each record's source and observed timestamp in the command console.
- Cache a reviewed GeoJSON snapshot so the demo has a clear offline fallback.

**Definition of done:** the UI can show that a fresh closure changes a responder recommendation, while cached mode clearly labels the data as cached.

## ElevenLabs - caller and radio experience

- Each participant can redeem one Creator-tier month through the event's Discord coupon flow using their registration email.
- Store the resulting API key only as `ELEVENLABS_API_KEY` in local `.env`.
- Begin with a narrow adapter for tactical radio narration, then add authenticated conversational tool webhooks.
- Tool calls must be validated server-side; a voice model must never directly alter unit availability or override status.
- Keep prerecorded/canned radio audio available for the demo fallback.

**Definition of done:** a successful unit assignment generates a concise, reviewable radio callout and a dispatcher can always take over.

## Neon and Gemini - next setup

- Neon credit redemption: use promo code `hackonneon` in Neon Console → Billing. Do not commit database URLs.
- Provision Neon Postgres with PostGIS; migrate the in-memory domain repository only after the simulation flow is stable.
- Create a separate, least-privilege application role and store its connection string in `DATABASE_URL` locally.
- Add migrations for incidents, units, hazards, assignments, and audit events before enabling a live database.
- Keep AI vision output structured, validate it, record the model/provider version, and require consent before image upload.

