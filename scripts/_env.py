"""Load the local .env without printing anything from it."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
