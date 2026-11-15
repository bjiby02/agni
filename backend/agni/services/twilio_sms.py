"""Twilio SMS for the caller camera link. Only to the number that phoned us. LIVE-UNVERIFIED."""
from __future__ import annotations

import base64
import os
import urllib.error
import urllib.parse
import urllib.request

from ..config import settings
from . import outbox


def send(to: str, body: str, ref: str) -> str:
    if settings.mock:
        outbox.record("sms", ref, {"body": body}, "mock")
        return "mock"
    sid, token, sender = (os.environ.get(k, "").strip() for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"))
    if not (sid and token and sender):
        outbox.record("sms", ref, {"body": body}, "key_not_set")
        return "key_not_set"
    data = urllib.parse.urlencode({"To": to, "From": sender, "Body": body}).encode()
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data,
                                 headers={"Authorization": f"Basic {auth}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8):
            status = "live-unverified"
    except (urllib.error.URLError, OSError) as error:
        status = "failed"
        outbox.record("sms", ref, {"error": str(error)[:160]}, status)
        return status
    outbox.record("sms", ref, {"body": body}, status)
    return status
