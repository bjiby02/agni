"""Offline tests for serial, signals, JUMP IN, and Bright Data call-active guard."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


class ServiceDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite"
        os.environ["AGNI_DB_PATH"] = str(self.db_path)
        os.environ["AGNI_MOCK"] = "1"
        os.environ["ELEVENLABS_TOOL_SECRET"] = "mock-tool-secret"
        # Reload modules that cache DB path / settings
        import importlib
        import agni.db as db
        import agni.config as config
        importlib.reload(config)
        importlib.reload(db)
        import agni.bus as bus
        importlib.reload(bus)
        import agni.services.serial_bridge as serial_bridge
        import agni.services.brightdata as brightdata
        importlib.reload(serial_bridge)
        importlib.reload(brightdata)
        serial_bridge.clear()
        brightdata.clear_stats()
        db.init()
        self.db = db
        self.serial = serial_bridge
        self.brightdata = brightdata

    def tearDown(self):
        self.tmp.cleanup()

    def test_serial_records_dispatch_bytes(self):
        result = self.serial.write_dispatch("E42")
        self.assertTrue(result["ok"])
        self.assertEqual(result["bytes"], "D42\n")
        self.assertEqual(self.serial.recorded(), [b"D42\n"])

    def test_bright_data_skipped_while_call_live(self):
        from agni import pollers
        with self.db.connect() as conn:
            conn.execute("INSERT INTO incidents(id,status,level,kind,title) VALUES('inc_t', 'possible', 3, 'fire', 't')")
            conn.execute("INSERT INTO calls(id,incident_id,direction,state) VALUES('call_live','inc_t','inbound','live')")
        self.brightdata.block_http(False)
        result = pollers.refresh_crowd_signals()
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "call_active")

    def test_signal_refresh_emits_unverified(self):
        from agni import pollers, bus
        from agni.services import brightdata
        brightdata.block_http(False)
        result = pollers.refresh_crowd_signals()
        self.assertFalse(result["skipped"])
        self.assertGreaterEqual(result["emitted"], 1)
        events = self.db.events_after(0)
        types = [e["type"] for e in events]
        self.assertIn("signal.new", types)
        signal_events = [e for e in events if e["type"] == "signal.new"]
        self.assertEqual(signal_events[0]["data"]["status"], "unverified")


class ApiDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "api.sqlite"
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
        from agni.services import serial_bridge
        serial_bridge.clear()
        db.init()
        with db.connect() as conn:
            conn.execute("UPDATE settings SET overflow_enabled=1 WHERE id=1")
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(main.app)
        self.headers = {"X-Agni-Tool-Secret": "mock-tool-secret"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_jump_in_and_hand_back(self):
        report = self.client.post("/api/tools/report_fire", headers=self.headers, json={
            "conversation_id": "conv_jump", "landmark_text": "behind the Vons, Carmel Valley",
            "what_seen": "smoke", "language": "en",
        })
        self.assertEqual(report.status_code, 200, report.text)
        iid = report.json()["incident_id"]
        self.client.post("/api/calls/transcript", headers=self.headers, json={
            "conversation_id": "conv_jump", "speaker": "caller", "text": "Hay humo cerca del Vons", "lang": "es",
        })
        jump = self.client.post(f"/api/incidents/{iid}/jump-in", json={"actor": "dispatcher"})
        self.assertEqual(jump.status_code, 200, jump.text)
        self.assertIn("summary", jump.json())
        back = self.client.post(f"/api/incidents/{iid}/hand-back", json={"actor": "dispatcher"})
        self.assertEqual(back.status_code, 200, back.text)
        self.assertEqual(back.json()["resumed_by"], "agent")
        self.assertEqual(back.json()["mode"], "callback")

    def test_dispatch_writes_serial(self):
        from agni.services import serial_bridge
        report = self.client.post("/api/tools/report_fire", headers=self.headers, json={
            "conversation_id": "conv_d", "landmark_text": "Torrey Pines", "what_seen": "smoke",
        })
        iid = report.json()["incident_id"]
        with __import__("agni.db", fromlist=["db"]).connect() as conn:
            conn.execute("UPDATE incidents SET lat=32.866,lon=-117.251,status='confirmed' WHERE id=?", (iid,))
        serial_bridge.clear()
        disp = self.client.post(f"/api/incidents/{iid}/dispatch",
                                headers={"Idempotency-Key": "k1"},
                                json={"unit_id": "E42", "approved_by": "dispatcher"})
        self.assertEqual(disp.status_code, 200, disp.text)
        self.assertEqual(disp.json()["serial"]["bytes"], "D42\n")
        self.assertEqual(serial_bridge.recorded(), [b"D42\n"])

    def test_report_sign_closes(self):
        report = self.client.post("/api/tools/report_fire", headers=self.headers, json={
            "conversation_id": "conv_r", "landmark_text": "Torrey Pines", "what_seen": "smoke",
        })
        iid = report.json()["incident_id"]
        draft = self.client.get(f"/api/incidents/{iid}/report")
        self.assertEqual(draft.status_code, 200)
        signed = self.client.post(f"/api/incidents/{iid}/report/sign",
                                  json={"actor": "dispatcher", "edits": ""})
        self.assertEqual(signed.status_code, 200, signed.text)
        self.assertEqual(signed.json()["signed_by"], "dispatcher")


if __name__ == "__main__":
    unittest.main()
