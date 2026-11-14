import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("agni_surge", ROOT / "backend" / "sim" / "surge.py")
surge = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(surge)


class SurgeTests(unittest.TestCase):
    def test_surge_writes_measured_result_and_does_not_use_main_database(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "sim.json"
            result = surge.run(n=12, max_seconds=90, output=out)
            self.assertTrue(out.exists())
        self.assertEqual(result["calls"], 12)
        self.assertEqual(result["visible_incidents"], 3)
        self.assertEqual(result["accepted_merges"], 9)
        self.assertTrue(result["within_target"])


if __name__ == "__main__":
    unittest.main()
