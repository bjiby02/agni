import asyncio
import tempfile
import unittest
from pathlib import Path

try:
    from starlette.requests import Request
    from agni import bus, db, main
    HAS_WEB_STACK = True
except ImportError:
    HAS_WEB_STACK = False


@unittest.skipUnless(HAS_WEB_STACK, "Install backend/requirements.txt to run API checks")
class SseRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "events.sqlite"
        db.init()

    async def asyncTearDown(self):
        db.DB_PATH = self.original
        self.tmp.cleanup()

    async def idle_receive(self):
        """Keep the synthetic SSE client connected until its iterator is closed."""
        await asyncio.sleep(3600)

    def request(self, last_event_id=None):
        headers = []
        if last_event_id is not None:
            headers.append((b"last-event-id", str(last_event_id).encode()))
        return Request({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": "/api/events",
            "raw_path": b"/api/events", "query_string": b"", "headers": headers,
            "client": ("testclient", 80), "server": ("testserver", 80),
        }, receive=self.idle_receive)

    async def test_replay_and_reconnect_do_not_repeat_event(self):
        event = bus.emit("call.started", "inc_test", {"call_id": "call-1"})
        response = await main.events(self.request(), since=0, authorization=None, _="local")
        first = await anext(response.body_iterator)
        first_text = first.decode() if isinstance(first, bytes) else first
        self.assertIn(f"id: {event['seq']}", first_text)
        self.assertIn('"call_id": "call-1"', first_text)
        await response.body_iterator.aclose()

        resumed = await main.events(self.request(event["seq"]), since=0, authorization=None, _="local")
        heartbeat = await anext(resumed.body_iterator)
        heartbeat_text = heartbeat.decode() if isinstance(heartbeat, bytes) else heartbeat
        self.assertEqual(heartbeat_text, ": ping\n\n")
        await resumed.body_iterator.aclose()

    def test_dispatched_guidance_does_not_claim_an_estimate_eta(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO incidents(id,status,level,kind,title) VALUES(?,?,?,?,?)",
                         ("inc_guidance", "dispatched", 1, "fire", "Mock fire"))
            conn.execute("INSERT INTO calls(id,incident_id) VALUES(?,?)",
                         ("call-guidance", "inc_guidance"))
            conn.execute("INSERT INTO dispatches(incident_id,unit_id,idempotency_key,approved_by,detail_json) "
                         "VALUES(?,?,?,?,?)",
                         ("inc_guidance", "E42", "guidance-dispatch", "mock-dispatcher", "{}"))

        result = main.get_guidance(main.GuidanceInput(conversation_id="call-guidance"), _="local")

        self.assertTrue(result["dispatched"])
        self.assertEqual(result["eta_s"], None)
        self.assertEqual(result["say"], "A dispatcher has sent E42. Stay where you are safe.")


if __name__ == "__main__":
    unittest.main()
