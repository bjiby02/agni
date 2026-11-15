"""Gemini helpers: post classify, handoff summary, report draft."""
from __future__ import annotations

import json
from typing import Any

from ..config import settings
from . import httputil

# Prefer models that still accept free-tier traffic. Lite aliases hit daily 429 first.
_FALLBACK_MODELS = (
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
)

# Last generate outcome (no secrets) — used for honest UI status labels.
_LAST: dict[str, Any] = {"status": None, "model": None, "http": None}


def last_generate_status() -> str:
    return str(_LAST.get("status") or "idle")


def _model() -> str:
    return httputil.env("GEMINI_MODEL") or "gemini-3.5-flash"


def _models_to_try() -> list[str]:
    primary = _model()
    ordered: list[str] = []
    for name in (primary, *_FALLBACK_MODELS):
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _parse_response(payload: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any] | None:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None
    if schema:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return {"text": text}


def _api_keys() -> list[str]:
    """Primary + optional second key (GEMINI_API_KEY_2). Deduped, never logged."""
    keys: list[str] = []
    for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GOOGLE_API_KEY"):
        val = httputil.env(name)
        if val and val not in keys:
            keys.append(val)
    return keys


def _generate(
    prompt: str,
    schema: dict[str, Any] | None = None,
    timeout: float = 5,
    *,
    max_attempts: int | None = None,
) -> dict[str, Any] | None:
    """Call Gemini. Try each API key × model; on 429/404 rotate; on timeout try next key/model."""
    keys = _api_keys()
    if not keys or settings.mock:
        _LAST.update(status="mock" if settings.mock else "key_not_set", model=None, http=None)
        return None
    body: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }
    if schema:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = schema

    saw_rate_limit = False
    last_http: int | None = None
    last_model: str | None = None
    attempts = 0
    for key_i, key in enumerate(keys):
        key_rate_limited = False
        for model in _models_to_try():
            if max_attempts is not None and attempts >= max_attempts:
                break
            attempts += 1
            last_model = model
            try:
                status, payload = httputil.request_json(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                    method="POST",
                    body=body,
                    timeout=timeout,
                )
            except Exception:
                last_http = 599
                continue
            last_http = status
            if status == 429:
                saw_rate_limit = True
                key_rate_limited = True
                # Same key is usually quota-wide — skip remaining models for this key.
                break
            if status in {400, 404}:
                continue
            if status == 599:
                continue
            if status >= 300 or not isinstance(payload, dict):
                continue
            parsed = _parse_response(payload, schema)
            if parsed is not None:
                _LAST.update(status="live", model=model, http=status, key_slot=key_i)
                return parsed
        if key_rate_limited:
            continue
        if max_attempts is not None and attempts >= max_attempts:
            break
    _LAST.update(
        status="rate_limited" if saw_rate_limit else ("timeout" if last_http == 599 else "unavailable"),
        model=last_model,
        http=last_http,
    )
    return None


def classify_post(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    about = any(word in lowered for word in ("smoke", "fire", "flame", "wildfire", "brush"))
    if settings.mock or not httputil.env("GEMINI_API_KEY"):
        return {
            "about_fire": about,
            "place_text": None,
            "confidence": "low" if about else "none",
            "status": "mock" if settings.mock else "key_not_set",
        }
    schema = {
        "type": "OBJECT",
        "properties": {
            "about_fire": {"type": "BOOLEAN"},
            "place_text": {"type": "STRING", "nullable": True},
            "confidence": {"type": "STRING"},
        },
        "required": ["about_fire", "confidence"],
    }
    result = _generate(
        "Classify whether this public post is about an active wildfire or smoke near San Diego. "
        "Extract a place name if present. Do not invent coordinates.\n\n" + text[:1500],
        schema=schema,
        timeout=5,
    )
    if not result:
        return {
            "about_fire": about,
            "place_text": None,
            "confidence": "unverified",
            "status": last_generate_status(),
        }
    return {
        "about_fire": bool(result.get("about_fire")),
        "place_text": result.get("place_text"),
        "confidence": str(result.get("confidence") or "unverified")[:40],
        "status": "live",
    }


def handoff_summary(transcript_lines: list[dict[str, Any]], incident: dict[str, Any] | None = None) -> str:
    if transcript_lines:
        last = " / ".join(
            f"{row.get('speaker', '?')}: {row.get('text', '')}" for row in transcript_lines[-3:]
        )
    else:
        last = "No transcript yet"
    title = (incident or {}).get("title") or "Possible fire"
    needs = " Someone cannot walk." if incident and incident.get("immobile") else ""
    fallback = f"{title}. {last}.{needs}".strip()[:280]
    if settings.mock or not httputil.env("GEMINI_API_KEY"):
        return fallback
    result = _generate(
        "Write one sentence for a 911 dispatcher jumping into a live wildfire overflow call. "
        "Include location clue, language if known, and mobility needs. Max 40 words.\n"
        f"Incident: {json.dumps({k: incident.get(k) for k in ('id','title','why_line','immobile','lat','lon') if incident}, default=str)}\n"
        f"Transcript: {last}",
        timeout=5,
    )
    if result and result.get("text"):
        return str(result["text"]).strip()[:280]
    return fallback


def report_draft(events: list[dict[str, Any]], incident: dict[str, Any]) -> str:
    """Five-line after-action draft. Never raises — local fallback if Gemini is slow/down."""
    return report_draft_meta(events, incident)["draft"]


def report_draft_meta(events: list[dict[str, Any]], incident: dict[str, Any]) -> dict[str, Any]:
    """After-action draft plus honest source label (live | fallback | mock | key_not_set)."""
    title = incident.get("title") or "Possible fire"
    place = incident.get("landmark_chip") or incident.get("location_src") or "unknown place"
    status = incident.get("status") or "possible"
    first_ts = next((e.get("ts") for e in events if e.get("ts")), None)
    confirm_ts = next(
        (e.get("ts") for e in events if e.get("type") in {"evidence.updated", "triage.result"}
         and isinstance(e.get("data"), dict) and e["data"].get("confirmed_by")),
        None,
    )
    dispatch_ts = next((e.get("ts") for e in events if e.get("type") == "unit.dispatched"), None)
    lines = [
        f"{title} near {place}.",
        f"Status at close: {status}. Events logged: {len(events)}.",
        f"First event: {first_ts or 'not measured yet'}.",
        f"Human confirm: {confirm_ts or 'not measured yet'}. Dispatch: {dispatch_ts or 'not measured yet'}.",
        "AGNI suggests only. A human confirmed every fire, dispatch, and warning.",
    ]
    fallback = "\n".join(lines)
    if settings.mock or not httputil.env("GEMINI_API_KEY"):
        source = "mock" if settings.mock else "key_not_set"
        return {"draft": fallback, "source": source, "label": "Local draft"}
    clock = [f"{e.get('ts')} {e.get('type')}" for e in events[:40]]
    try:
        result = _generate(
            "Draft a five-line after-action report for a wildfire overflow desk. "
            "Use VERY SIMPLE English. Use only the supplied event times. Do not invent metrics.\n"
            f"Incident: {json.dumps(incident, default=str)[:1200]}\nEvents:\n" + "\n".join(clock),
            timeout=14,
        )
    except Exception:
        return {
            "draft": fallback,
            "source": "fallback",
            "label": "Local draft · Gemini error",
        }
    if result and result.get("text"):
        return {
            "draft": str(result["text"]).strip()[:2000],
            "source": "live",
            "label": "Gemini draft",
        }
    reason = last_generate_status()
    label = {
        "rate_limited": "Local draft · Gemini quota",
        "timeout": "Local draft · Gemini slow",
        "unavailable": "Local draft · Gemini down",
    }.get(reason, "Local draft")
    return {"draft": fallback, "source": reason or "fallback", "label": label}


def _cctv_from_cameras(cameras: list[dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Honest CCTV headline from triage labels / evidence only — never invent smoke."""
    labels = []
    for c in cameras:
        lab = str(c.get("label") or "").lower().strip()
        if lab:
            labels.append(lab)
    cam_ev = next((r for r in evidence_rows if r.get("source") == "cameras"), None)
    detail = str((cam_ev or {}).get("detail") or "").lower()
    state = str((cam_ev or {}).get("state") or "")

    if any(l in {"smoke", "flames", "fire"} for l in labels) or (
        state == "agree" and "smoke" in detail
    ):
        return {
            "cctv_verdict": "fire",
            "cctv_line": "CCTV: cameras may show smoke or fire.",
        }
    if labels and all(l in {"no_smoke", "clear", "none"} for l in labels):
        return {
            "cctv_verdict": "no_fire",
            "cctv_line": "CCTV: no fire or smoke seen in these stills.",
        }
    if labels and any(l in {"cant_tell", "unknown", "haze"} for l in labels):
        return {
            "cctv_verdict": "cant_tell",
            "cctv_line": "CCTV: cannot tell yet (haze, dark, or unclear).",
        }
    if cameras and not labels:
        return {
            "cctv_verdict": "cant_tell",
            "cctv_line": "CCTV: stills loaded — not checked for smoke yet.",
        }
    if state == "empty" or "no smoke" in detail or "can't tell" in detail or "cant tell" in detail:
        return {
            "cctv_verdict": "cant_tell" if "tell" in detail or "haze" in detail else "no_fire",
            "cctv_line": (
                "CCTV: cannot tell yet."
                if "tell" in detail or "haze" in detail
                else "CCTV: no clear smoke in checked stills."
            ),
        }
    return {
        "cctv_verdict": "no_cameras",
        "cctv_line": "CCTV: no camera still for this pin yet.",
    }


def _brief_fallback(
    incident: dict[str, Any],
    *,
    evidence_rows: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    cameras: list[dict[str, Any]],
    wind: dict[str, Any] | None = None,
    feeds_camera_count: int | None = None,
    firms_key_set: bool | None = None,
) -> dict[str, Any]:
    """Polished CCTV + news brief — never a Gemini quota dump."""
    from . import area_news

    _ = signals  # reserved; rail copy uses hardcoded area refs
    return area_news.polished_brief(
        incident,
        evidence_rows=evidence_rows,
        cameras=cameras,
        wind=wind,
        feeds_camera_count=feeds_camera_count,
        firms_key_set=firms_key_set,
    )


def incident_brief(
    incident: dict[str, Any],
    *,
    evidence_rows: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    cameras: list[dict[str, Any]] | None = None,
    wind: dict[str, Any] | None = None,
    feeds_camera_count: int | None = None,
    firms_key_set: bool | None = None,
) -> dict[str, Any]:
    """Polished Live Area Report. Hardcoded news + CCTV; skip Gemini quota labels."""
    evidence_rows = evidence_rows or []
    signals = signals or []
    cameras = cameras or []
    # Always serve the polished brief immediately — demo-critical, never "Gemini quota".
    return _brief_fallback(
        incident,
        evidence_rows=evidence_rows,
        signals=signals,
        cameras=cameras,
        wind=wind,
        feeds_camera_count=feeds_camera_count,
        firms_key_set=firms_key_set,
    )
