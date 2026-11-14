import tempfile
import unittest
from pathlib import Path

from agni import db, merge


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "merge.sqlite"
        db.init()
        with db.connect() as conn:
            conn.executemany(
                "INSERT INTO incidents(id,status,level,kind,title,lat,lon,location_src,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                [
                    ("inc_one", "possible", 3, "fire", "First report", 32.9000, -117.2000, "caller", "2026-11-14T12:00:00Z"),
                    ("inc_two", "possible", 3, "fire", "Second report", 32.9020, -117.2020, "caller", "2026-11-14T12:04:00Z"),
                    ("inc_far", "possible", 3, "fire", "Separate report", 32.9500, -117.2700, "caller", "2026-11-14T12:04:00Z"),
                ],
            )

    def tearDown(self):
        db.DB_PATH = self.original
        self.tmp.cleanup()

    def test_close_reports_create_a_suggestion_not_an_auto_merge(self):
        suggestion = merge.suggest_for_incident("inc_two")
        self.assertEqual(suggestion["kept_id"], "inc_one")
        self.assertEqual(suggestion["merged_id"], "inc_two")
        self.assertLess(suggestion["distance_m"], 800)
        self.assertIsNone(db.incident("inc_two")["merged_into"])
        self.assertEqual(db.events_after(0)[0]["type"], "incident.merge_suggested")

    def test_far_report_has_no_suggestion(self):
        self.assertIsNone(merge.suggest_for_incident("inc_far"))

    def test_accept_then_undo_restores_the_second_incident(self):
        suggestion = merge.suggest_for_incident("inc_two")
        merged = merge.accept(suggestion["merge_id"], "human:dispatcher")
        self.assertEqual(merged["kept_id"], "inc_one")
        self.assertEqual(db.incident("inc_two")["merged_into"], "inc_one")
        self.assertEqual([item["id"] for item in db.state()["incidents"]], ["inc_far", "inc_one"])

        merge.undo(suggestion["merge_id"], "human:dispatcher")
        self.assertIsNone(db.incident("inc_two")["merged_into"])
        self.assertEqual({item["id"] for item in db.state()["incidents"]}, {"inc_one", "inc_two", "inc_far"})


if __name__ == "__main__":
    unittest.main()
