"""Caller camera links, Bright Data practice ingest and the satellite poll in mock mode."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
    from agni import brightdata, db, main, pollers
    HAS_WEB_STACK = True
except ImportError:
    HAS_WEB_STACK = False

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@unittest.skipUnless(HAS_WEB_STACK, "Install backend/requirements.txt to run API checks")
class CamAndFeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "feeds.sqlite"
        self.client = TestClient(main.app, client=("127.0.0.1", 50000)).__enter__()
        self.client.post("/api/ops/reset")
        with db.connect() as conn:
            conn.execute("INSERT INTO incidents(id,status,level,title,lat,lon,location_src) VALUES('inc_x','possible',3,'t',32.91,-117.17,'caller')")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        db.DB_PATH = self.original
        self.tmp.cleanup()

    def test_camera_link_is_one_time_and_heading_becomes_a_bearing(self):
        link = self.client.post("/api/ops/cam-link", json={"incident_id": "inc_x"}).json()
        token = link["token"]
        self.assertTrue(self.client.get(f"/api/cam/{token}").json()["valid"])
        r = self.client.post(f"/api/cam/{token}/frame?heading_deg=225&lat=32.91&lon=-117.17&accuracy_m=12",
                             content=JPEG, headers={"Content-Type": "image/jpeg"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["label"], "cant_tell")          # mock never invents a verdict
        self.assertEqual(r.json()["applied_level"], 3)             # unknown never changes priority
        again = self.client.post(f"/api/cam/{token}/frame", content=JPEG, headers={"Content-Type": "image/jpeg"})
        self.assertEqual(again.status_code, 410)
        with db.connect() as conn:
            row = conn.execute("SELECT bearing_deg,source FROM bearings WHERE incident_id='inc_x'").fetchone()
        self.assertEqual((row["bearing_deg"], row["source"]), (225, "compass"))
        self.assertIsNotNone(self.client.get(f"/api/cam/{token}/result").json()["result"])

    def test_expired_or_unknown_link_is_refused(self):
        self.assertEqual(self.client.get("/api/cam/not-a-real-token").status_code, 404)
        link = self.client.post("/api/ops/cam-link", json={"incident_id": "inc_x"}).json()
        with db.connect() as conn:
            conn.execute("UPDATE cam_tokens SET expires_at='2000-01-01T00:00:00Z'")
        r = self.client.post(f"/api/cam/{link['token']}/frame", content=JPEG, headers={"Content-Type": "image/jpeg"})
        self.assertEqual(r.status_code, 410)

    def test_practice_posts_make_gray_pins_only_from_cached_landmarks(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network in mock")):
            result = self.client.post("/api/ops/poll/signals").json()
        self.assertEqual(result["mode"], "practice fixture")
        signals = self.client.get("/api/state").json()["signals"]
        self.assertTrue(signals)
        pinned = [s for s in signals if s["lat"] is not None]
        self.assertTrue(all((s["lat"], s["lon"]) == (32.91, -117.17) for s in pinned))  # the cached Vons record
        self.assertFalse(any("tacos" in s["text"] or "Throwback" in s["text"] for s in signals))
        rows = {r["source"]: r for r in self.client.get("/api/incidents/inc_x/evidence").json()["rows"]}
        self.assertEqual(rows["public"]["state"], "partial")
        again = self.client.post("/api/ops/poll/signals").json()
        self.assertEqual(again["created"], 0)                        # deduped by URL

    def test_scraper_waits_while_a_call_is_active(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO calls(id,incident_id,direction) VALUES('c1','inc_x','inbound')")
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no Bright Data during a call")):
            self.assertEqual(brightdata.poll()["status"], "skipped_active_call")

    def test_satellite_poll_in_mock_is_gray_with_a_reason(self):
        out = pollers.poll_satellite()
        self.assertEqual(out["incidents"][0]["state"], "empty")
        rows = {r["source"]: r for r in self.client.get("/api/incidents/inc_x/evidence").json()["rows"]}
        self.assertIn("not checked", rows["firms"]["detail"])


if __name__ == "__main__":
    unittest.main()
