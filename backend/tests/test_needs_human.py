"""call.needs_human: silence / caller ask → JUMP IN cue."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class NeedsHumanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "needs.sqlite"
        os.environ["AGNI_DB_PATH"] = str(self.db_path)
        os.environ["AGNI_MOCK"] = "1"
        os.environ["ELEVENLABS_TOOL_SECRET"] = "mock-tool-secret"
        os.environ.pop("OPERATOR_TOKEN", None)
        import importlib
        import agni.db as db
        import agni.config as config
        importlib.reload(config)
        importlib.reload(db)
        import agni.bus as bus
        importlib.reload(bus)
        import agni.main as main
        importlib.reload(main)
        db.init()
        with db.connect() as conn:
            conn.execute("UPDATE settings SET overflow_enabled=1 WHERE id=1")
        from fastapi.testclient import TestClient
        self.db = db
        self.main = main
        self.client = TestClient(main.app)
        self.headers = {"X-Agni-Tool-Secret": "mock-tool-secret"}

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, cid="conv_stuck_1"):
        r = self.client.post(
            "/api/tools/report_fire",
            headers=self.headers,
            json={
                "conversation_id": cid,
                "landmark_text": "behind the Vons, Carmel Valley",
                "what_seen": "smoke",
                "language": "en",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json().get("overflow"))
        return r.json()

    def test_caller_asks_human_emits_event(self):
        self._report("conv_ask_1")
        r = self.client.post(
            "/api/calls/transcript",
            headers=self.headers,
            json={
                "conversation_id": "conv_ask_1",
                "speaker": "caller",
                "text": "Can I speak to a dispatcher please?",
                "lang": "en",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        events = [e for e in self.db.events_after(0) if e["type"] == "call.needs_human"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"]["reason"], "caller_asked_human")

    def test_mark_needs_human_idempotent(self):
        self._report("conv_idemp")
        first = self.main._mark_needs_human("conv_idemp", "silence")
        second = self.main._mark_needs_human("conv_idemp", "silence")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        events = [e for e in self.db.events_after(0) if e["type"] == "call.needs_human"]
        self.assertEqual(len(events), 1)

    def test_stuck_silence_marks_call(self):
        self._report("conv_silent")
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE calls SET started_at=strftime('%Y-%m-%dT%H:%M:%fZ','now','-40 seconds') "
                "WHERE id=?",
                ("conv_silent",),
            )
        n = self.main._check_stuck_calls()
        self.assertEqual(n, 1)
        state = self.db.state()
        call = next(c for c in state["calls"] if c["id"] == "conv_silent")
        self.assertTrue(call.get("needs_human"))

    def test_silence_stuck_clears_when_caller_speaks_again(self):
        self._report("conv_resume")
        self.main._mark_needs_human("conv_resume", "silence")
        state = self.db.state()
        call = next(c for c in state["calls"] if c["id"] == "conv_resume")
        self.assertTrue(call.get("needs_human"))
        r = self.client.post(
            "/api/calls/transcript",
            headers=self.headers,
            json={
                "conversation_id": "conv_resume",
                "speaker": "caller",
                "text": "Behind the Vons on Carmel Valley Road",
                "lang": "en",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        state = self.db.state()
        call = next(c for c in state["calls"] if c["id"] == "conv_resume")
        self.assertFalse(call.get("needs_human"))


if __name__ == "__main__":
    unittest.main()
