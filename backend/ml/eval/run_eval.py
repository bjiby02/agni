"""AGNI evaluation harness. Writes backend/ml/eval/eval.json, which the /ops proof panel reads.

Every metric carries n and a status. A metric with no labeled data or no key is
"not measured yet" with n=0: the console never shows a number that was not measured.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))

from agni import merge, vision  # noqa: E402
from agni.config import settings  # noqa: E402
from agni.services import gemini  # noqa: E402


def _rows(name: str) -> list[list[str]]:
    path = HERE / name
    if not path.exists():
        return []
    return [r for r in csv.reader(line for line in path.read_text(encoding="utf-8").splitlines()
                                  if line.strip() and not line.startswith("#"))]


def not_measured(reason: str) -> dict:
    return {"value": None, "n": 0, "status": "not measured yet", "reason": reason}


def eval_merges() -> dict:
    rows = _rows("merges.csv")
    if not rows:
        return not_measured("merges.csv has no rows")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tp = fp = fn = tn = 0
    for a_lat, a_lon, b_lat, b_lon, dt_s, same in rows:
        a = {"lat": float(a_lat), "lon": float(a_lon), "created_at": t0.isoformat()}
        b = {"lat": float(b_lat), "lon": float(b_lon), "created_at": (t0 + timedelta(seconds=int(dt_s))).isoformat()}
        predicted, _, _ = merge.eligible(a, b)
        truth = same == "1"
        tp += predicted and truth; fp += predicted and not truth
        fn += (not predicted) and truth; tn += (not predicted) and not truth
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"value": round(precision, 3) if precision is not None else None, "recall": round(recall, 3) if recall is not None else None,
            "n": len(rows), "status": "measured", "data": "synthetic hand-labeled pairs, not real calls",
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}}


def eval_frames() -> dict:
    rows = _rows("frames.csv")
    if not rows:
        return not_measured("no human-labeled frames in frames.csv yet")
    if settings.mock or not os.environ.get("GEMINI_API_KEY"):
        return not_measured("needs GEMINI_API_KEY and AGNI_MOCK=0")
    correct, scored = 0, 0
    for path, label in rows:
        image = (HERE / path).read_bytes()
        result = vision.assess(image, "image/jpeg")
        scored += 1
        correct += result["label"] == label
    return {"value": round(correct / scored, 3), "n": scored, "status": "measured", "data": "frames.csv",
            "text": f"{correct} of {scored} correct on real frames"}


POST_SCHEMA = {"type": "OBJECT", "properties": {"is_fire_report": {"type": "BOOLEAN"}}, "required": ["is_fire_report"]}


def eval_posts() -> dict:
    rows = _rows("posts.csv")
    if not rows:
        return not_measured("no human-labeled posts in posts.csv yet")
    if settings.mock or not os.environ.get("GEMINI_API_KEY"):
        return not_measured("needs GEMINI_API_KEY and AGNI_MOCK=0")
    tp = fp = 0
    scored = 0
    for text, label in rows:
        out = gemini.generate_json("Is this post a first-hand report of a fire or smoke in San Diego? " + text, POST_SCHEMA)
        if out is None:
            continue
        scored += 1
        if out.get("is_fire_report"):
            tp += label == "1"; fp += label != "1"
    if not scored:
        return not_measured("Gemini returned nothing")
    return {"value": round(tp / (tp + fp), 3) if tp + fp else None, "n": scored, "status": "measured", "data": "posts.csv"}


def main() -> None:
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "merge_precision": eval_merges(), "triage_accuracy": eval_frames(), "post_precision": eval_posts(),
           "caller_personas": not_measured("needs a live voice agent: 10 personas x 3 runs")}
    path = HERE / "eval.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    for key, metric in out.items():
        if isinstance(metric, dict):
            shown = metric["value"] if metric["n"] else metric["status"]
            print(f"{key:18} n={metric['n']:<3} {shown}")
    print(f"wrote {path.relative_to(BACKEND.parent)}")


if __name__ == "__main__":
    main()
