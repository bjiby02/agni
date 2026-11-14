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

    def request(self, last_event_id=None):
        headers = []
        if last_event_id is not None:
            headers.append((b"last-event-id", str(last_event_id).encode()))
        return Request({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": "/api/events",
            "raw_path": b"/api/events", "query_string": b"", "headers": headers,
            "client": ("testclient", 80), "server": ("testserver", 80),
        })

    async def test_replay_and_reconnect_do_not_repeat_event(self):
        event = bus.emit("call.started", "inc_test", {"call_id": "call-1"})
        response = await main.events(self.request(), since=0, authorization=None, _="local")
        first = await anext(response.body_iterator)
        self.assertIn(f"id: {event['seq']}".encode(), first)
        self.assertIn(b'"call_id":"call-1"', first)
        await response.body_iterator.aclose()

        resumed = await main.events(self.request(event["seq"]), since=0, authorization=None, _="local")
        heartbeat = await anext(resumed.body_iterator)
        self.assertEqual(heartbeat, b": ping\n\n")
        await resumed.body_iterator.aclose()


if __name__ == "__main__":
    unittest.main()
