#!/usr/bin/env python3
"""Poll until live-ready passes, then print next commands. Safe to leave running."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ready() -> bool:
    result = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python3"), str(ROOT / "scripts" / "live_ready.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stdout.flush()
    return result.returncode == 0


def main() -> int:
    print("Waiting for you to fill local .env + seed/warn_list.json …")
    print("I will keep checking every 15s. Do not paste keys into chat.\n")
    while True:
        if ready():
            print("\nLIVE KEYS READY.")
            print("Next I will run: make agents && make live-check && ./tunnel.sh")
            return 0
        time.sleep(15)


if __name__ == "__main__":
    sys.exit(main())
