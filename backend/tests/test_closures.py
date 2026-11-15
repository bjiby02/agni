"""Caltrans QuickMap closures: KML parse, storage, and routing around the stored closure."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agni import closures, db, routing

SAMPLE = (Path(__file__).parent / "fixtures" / "quickmap_sample.kml").read_text(encoding="utf-8")


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH, db.DATABASE_URL
        db.DB_PATH, db.DATABASE_URL = Path(self.tmp.name) / "c.sqlite", ""
        db.init()

    def tearDown(self):
        db.DB_PATH, db.DATABASE_URL = self.original
        self.tmp.cleanup()

    def test_parse_keeps_only_full_closures_inside_the_box(self):
        features = closures.parse(SAMPLE, scraped_at="2026-11-14T23:00:00Z")
        ids = {f["id"] for f in features}
        self.assertEqual(ids, {"caltrans-CTEST1-2-1", "caltrans-CTEST3-1"})  # lane closure and far-away closure dropped
        line = next(f for f in features if f["id"] == "caltrans-CTEST1-2-1")
        self.assertEqual(line["geometry"]["type"], "LineString")
        self.assertEqual(len(line["geometry"]["coordinates"]), 3)
        self.assertIn("Route 56", line["properties"]["title"])
        self.assertEqual(line["properties"]["ends"], "5:00am Nov 15, 2026")
        pending = next(f for f in features if f["id"] == "caltrans-CTEST3-1")
        self.assertTrue(pending["properties"]["pending"])
        self.assertEqual(pending["geometry"]["type"], "Point")   # no path, so no invented line

    def test_poll_stores_closures_and_routing_avoids_them(self):
        with mock.patch.object(closures, "fetch_kml", side_effect=lambda path, timeout=40: SAMPLE if "lcs2way" in path else "<kml xmlns='http://www.opengis.net/kml/2.2'/>"), \
             mock.patch.object(closures, "LATEST", Path(self.tmp.name) / "latest.geojson"), \
             mock.patch.object(closures, "CACHE", Path(self.tmp.name)):
            result = closures.poll(force=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["closures"], 2)
        with db.connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM hazards WHERE source='caltrans_quickmap'")]
        self.assertEqual(len(rows), 2)
        unit = {"id": "E1", "callsign": "Engine 1", "lat": 32.950, "lon": -117.200}
        blocked = routing.blocked_by_closure(unit, (32.920, -117.200), rows)
        self.assertIn("Route 56", blocked or "")

    def test_mock_mode_does_not_fetch(self):
        with mock.patch.object(closures, "settings", mock.Mock(mock=True)), mock.patch.object(closures, "fetch_kml") as fetch:
            self.assertEqual(closures.poll()["status"], "skipped")
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
