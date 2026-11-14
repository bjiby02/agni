"""AGNI crisis-intelligence prototype."""
from pathlib import Path
import sys

# The independent AGNI app reuses selected local hazard helpers from this repo.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

