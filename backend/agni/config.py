"""Runtime configuration. Mock mode is the safe default for local development."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mock: bool = _flag("AGNI_MOCK", True)
    overflow_enabled: bool = _flag("OVERFLOW_ENABLED", False)
    operator_token: str = os.environ.get("OPERATOR_TOKEN", "")
    tool_secret: str = os.environ.get("ELEVENLABS_TOOL_SECRET", "")
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///data/agni-api.sqlite")
    demo_replay: bool = _flag("DEMO_REPLAY", True)


settings = Settings()
