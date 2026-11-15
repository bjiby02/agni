"""Evidence stack helpers. Unknown is gray, never green. why_line only from agree sources."""
from __future__ import annotations

from typing import Any


def why_line(rows: list[dict[str, Any]], max_len: int = 60) -> str:
    """Build a short trust line from evidence rows in state=agree only."""
    parts: list[str] = []
    for row in rows:
        if row.get("state") != "agree":
            continue
        source = str(row.get("source") or "")
        detail = str(row.get("detail") or "").strip()
        if source in {"callers", "caller_location"}:
            # Prefer short readable phrases over mid-word truncation
            if "landmark" in detail.lower() or "matched" in detail.lower():
                parts.append("landmark match")
            else:
                parts.append((detail[:40] if detail else "caller report").rstrip())
        elif source == "cameras":
            parts.append(detail[:40] if detail else "camera smoke")
        elif source == "wind":
            parts.append(detail[:28] if detail else "wind")
        elif source in {"reddit", "x", "serp", "posts"}:
            parts.append("crowd post")
        elif source == "firms":
            parts.append("satellite")
        else:
            if detail:
                parts.append(detail[:24])
    line = " · ".join(parts[:4]) if parts else ""
    return line[:max_len]


def default_rows(firms_key_set: bool = False) -> list[dict[str, Any]]:
    firms_detail = ("Key not set" if not firms_key_set
                    else "No detection yet; satellite data can lag hours")
    firms_state = "empty" if firms_key_set else "unknown"
    return [
        {"source": "callers", "state": "empty", "detail": "No caller bearings yet", "age_s": None},
        {"source": "cameras", "state": "empty", "detail": "Camera feed not checked yet", "age_s": None},
        {"source": "posts", "state": "empty", "detail": "No public posts in the last hour", "age_s": None},
        {"source": "firms", "state": firms_state, "detail": firms_detail, "age_s": None},
        {"source": "nifc", "state": "empty", "detail": "No perimeter mapped; this does not rule out fire", "age_s": None},
        {"source": "wind", "state": "empty", "detail": "Wind feed not checked yet", "age_s": None},
    ]
