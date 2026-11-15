"""End-to-end mock flow: replay call, merge, confirm, dispatch, jump in, warn, report."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from agni import db, main, report
    from agni.services import outbox, serial_bridge
    HAS_WEB_STACK = True
except ImportError:
    HAS_WEB_STACK = False


@unittest.skipUnless(HAS_WEB_STACK, "Install backend/requirements.txt to run API checks")
class DemoFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "flow.sqlite"
        self.client = TestClient(main.app, client=("127.0.0.1", 50000)).__enter__()
        serial_bridge.WRITES.clear()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        db.DB_PATH = self.original
        self.tmp.cleanup()

    def post(self, path, body=None, headers=None, expect=200):
        r = self.client.post(path, json=body or {}, headers=headers or {})
        self.assertEqual(r.status_code, expect, r.text)
        return r.json()

    def wait(self, fn, timeout=10):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = fn()
            if value:
                return value
            time.sleep(0.05)
        self.fail("timed out")

    def run_to_dispatch(self):
        r = self.post("/api/ops/reset")
        self.assertLess(r["elapsed_s"], 5)
        self.post("/api/ops/replay", {"name": "call_es", "speed": 20})
        state = lambda: self.client.get("/api/state").json()
        self.wait(lambda: state()["ops"]["mode"] == "calm" and state()["merges"])
        merge = next(m for m in state()["merges"] if m["state"] == "suggested")
        accepted = self.post(f"/api/merges/{merge['id']}/accept")
        self.assertEqual(accepted["estimate"]["n"], 2)
        iid = accepted["kept_id"]
        self.post(f"/api/incidents/{iid}/confirm", {"actor": "dispatcher"})
        route = self.client.get(f"/api/incidents/{iid}/route").json()
        self.assertIsNotNone(route["shelter"])
        self.assertNotIn(route["shelter"]["name"], [r["name"] for r in route["refused"]])
        body = {"unit_id": route["recommended_unit"], "approved_by": "dispatcher"}
        first = self.post(f"/api/incidents/{iid}/dispatch", body, {"Idempotency-Key": "k1"})
        second = self.post(f"/api/incidents/{iid}/dispatch", body, {"Idempotency-Key": "k1"})
        self.assertEqual(first["dispatch_id"], second["dispatch_id"])
        self.assertEqual(serial_bridge.WRITES, [b"D"])
        return iid

    def test_evidence_lists_every_source_and_unknowns_are_not_green(self):
        iid = self.run_to_dispatch()
        rows = {r["source"]: r for r in self.client.get(f"/api/incidents/{iid}/evidence").json()["rows"]}
        for source in ("callers", "cameras", "wind", "firms", "nifc"):
            self.assertIn(source, rows)
        for source in ("cameras", "wind", "firms", "nifc"):
            self.assertEqual(rows[source]["state"], "empty")
        self.assertIn("FIRMS key not set", rows["firms"]["detail"])

    def test_jump_in_then_hand_back_by_callback(self):
        self.run_to_dispatch()
        started = self.post("/api/calls/replay-es-1/takeover", {"actor": "dispatcher"})
        self.assertIn("Someone cannot move", started["summary"])
        self.post("/api/calls/replay-es-1/takeover", {"actor": "dispatcher"}, expect=409)
        guidance = self.post("/api/tools/get_guidance", {"conversation_id": "replay-es-1"},
                             {"X-Agni-Tool-Secret": main.settings.tool_secret or "x"}, expect=200 if main.settings.tool_secret else 503)
        if main.settings.tool_secret:
            self.assertTrue(guidance["should_transfer"])
        ended = self.post("/api/calls/replay-es-1/handback", {"actor": "dispatcher"})
        self.assertEqual(ended["resumed_by"], "agent")
        self.assertEqual(ended["callback"], "mock")
        self.assertEqual(len(outbox.rows("callback")), 1)
        types = [e["type"] for e in db.events_after(0)]
        self.assertIn("handoff.started", types)
        self.assertIn("handoff.ended", types)

    def test_warning_only_reaches_opted_in_homes_and_press_1_drops_a_pin(self):
        iid = self.run_to_dispatch()
        self.post(f"/api/incidents/{iid}/ring", {"minutes": 30, "wind_to_deg": 200})
        warning = self.post(f"/api/warnings/{iid}", {"languages": ["es"]}, {"Idempotency-Key": "w1"})
        self.assertNotIn("practice-home-3", warning["recipient_ids"])
        self.assertEqual(warning["dial"], "mock")
        self.post("/api/ops/press1", {"warning_id": warning["warning_id"], "home_id": "practice-home-3"}, expect=404)
        self.post("/api/ops/press1", {"warning_id": warning["warning_id"], "home_id": warning["recipient_ids"][0]})
        rescue = [e for e in db.events_after(0) if e["type"] == "rescue.requested"][-1]
        self.assertIsNotNone(rescue["data"]["lat"])

    def test_report_hash_is_reproducible_and_needs_a_human_signature(self):
        iid = self.run_to_dispatch()
        drafted = self.post(f"/api/incidents/{iid}/close")
        self.assertEqual(drafted["log_sha256"], report.canonical_hash(report.incident_log(iid)))
        self.assertIsNotNone(drafted["clock"]["signal_to_dispatch_s"])
        self.assertTrue(all("[event #" in line for line in drafted["draft"][:-1]))
        self.assertIsNone(drafted["signed_by"])
        signed = self.post(f"/api/incidents/{iid}/report/sign", {"actor": "dispatcher"})
        self.assertEqual(signed["log_sha256"], drafted["log_sha256"])
        self.post(f"/api/incidents/{iid}/report/sign", {"actor": "dispatcher"}, expect=409)

    def test_proof_panel_reads_files_only(self):
        proof = self.client.get("/api/proof").json()
        self.assertEqual(set(proof), {"sim", "eval"})


if __name__ == "__main__":
    unittest.main()
