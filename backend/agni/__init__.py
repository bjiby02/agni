"""AGNI crisis-intelligence prototype."""
from pathlib import Path
import sys

# Bearing, geography and feed helpers carried over from Ares live in backend/core.
CORE = Path(__file__).resolve().parents[1] / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
