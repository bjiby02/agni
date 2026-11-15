"""Small HTTP helpers for live adapters."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def keyed(*names: str) -> bool:
    return all(env(name) for name in names)


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 12,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return resp.status, {}
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw[:4000].decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as error:
        payload = error.read()[:4000]
        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = {"raw": payload.decode("utf-8", errors="replace")}
        return error.code, parsed
