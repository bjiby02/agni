"""Re-run the flow tests on Postgres. Set AGNI_TEST_PG_URL to a throwaway database to enable.

    AGNI_TEST_PG_URL=postgresql://user@127.0.0.1:5432/agni_test make test

Each test drops and recreates the public schema, so never point this at Neon main.
"""
import os
import unittest

URL = os.environ.get("AGNI_TEST_PG_URL", "")

try:
    import psycopg  # noqa: F401
    from agni import db, pg
    from test_demo_flow import DemoFlowTests
    from test_camlink_feeds import CamAndFeedTests
    READY = bool(URL)
except ImportError:
    READY = False


if READY:
    class PostgresMixin:
        def setUp(self):
            self._url = db.DATABASE_URL
            db.DATABASE_URL = URL
            import psycopg
            with psycopg.connect(URL, autocommit=True) as conn:
                conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            super().setUp()

        def tearDown(self):
            super().tearDown()
            db.DATABASE_URL = self._url

    class PostgresDemoFlowTests(PostgresMixin, DemoFlowTests):
        pass

    class PostgresCamAndFeedTests(PostgresMixin, CamAndFeedTests):
        pass

    class TranslateTests(unittest.TestCase):
        def test_replace_becomes_upsert_and_serial_returns_id(self):
            sql, ret = pg.translate("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail) VALUES(?,?,?,?)")
            self.assertIn("ON CONFLICT (incident_id, source) DO UPDATE SET state=EXCLUDED.state, detail=EXCLUDED.detail", sql)
            self.assertIsNone(ret)
            sql, ret = pg.translate("INSERT INTO events(type,incident_id,data_json) VALUES(?,?,?)")
            self.assertTrue(sql.endswith("RETURNING seq"))
            self.assertEqual(ret, "seq")
else:
    @unittest.skip("Set AGNI_TEST_PG_URL (and install psycopg) to run the Postgres checks")
    class PostgresSkipped(unittest.TestCase):
        def test_skipped(self):
            pass
