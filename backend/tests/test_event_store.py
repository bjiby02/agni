import tempfile
import unittest
from pathlib import Path

from agni import bus, db


class EventStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "events.sqlite"
        db.init()

    def tearDown(self):
        db.DB_PATH = self.original
        self.tmp.cleanup()

    def test_events_are_ordered_and_replay_from_sequence(self):
        first = bus.emit("call.started", "inc_test", {"call_id":"call-1"})
        second = bus.emit("evidence.updated", "inc_test", {"confirmed_by":"dispatcher:test"})
        replay = db.events_after(first["seq"])
        self.assertEqual([event["seq"] for event in replay], [second["seq"]])
        self.assertEqual(replay[0]["type"], "evidence.updated")

    def test_unknown_event_name_is_rejected(self):
        with self.assertRaises(ValueError):
            bus.emit("invented.event", None, {})


if __name__ == "__main__":
    unittest.main()
