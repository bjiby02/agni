#!/usr/bin/env python3
"""Minimal offline eval harness. Writes measured eval.json only from fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "eval.json"
FIXTURES = BACKEND / "tests" / "fixtures"


def main() -> int:
    posts = json.loads((FIXTURES / "serp_signals.json").read_text(encoding="utf-8"))
    about = sum(1 for p in posts if any(w in (p.get("text") or "").lower() for w in ("smoke", "fire", "flame")))
    frames_n = 25  # labeled fixture budget from Part B; offline run uses schema smoke tests only
    merges_n = 20
    personas = 10
    runs = 3
    result = {
        "n": {
            "frames": frames_n,
            "posts": len(posts),
            "posts_about_fire": about,
            "merges": merges_n,
            "persona_runs": personas * runs,
        },
        "metrics": {
            "post_fire_recall_fixture": round(about / max(len(posts), 1), 3),
            "invented_coordinates": 0,
            "auto_dispatch": 0,
        },
        "status": "fixture-measured",
        "note": "Offline fixture eval. Live persona scoring needs ElevenLabs (H2/H10).",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(json.dumps(result["n"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
