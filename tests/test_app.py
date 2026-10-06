import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import create_app


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = str(Path(self.tmp.name) / "test.db")
        self.config = {"TESTING": True, "SECRET_KEY": "test-only-key", "DATABASE": self.database}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def token(self):
        self.client.get("/deliveries/new")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def create(self, **overrides):
        data = dict(name="Catalogue", release="1.2.0", environment="staging", description="Nouvelle recherche")
        data.update(overrides)
        data["csrf_token"] = self.token()
        return self.client.post("/deliveries/new", data=data)

    def test_empty_dashboard_and_health(self):
        self.assertIn("Votre première livraison".encode(), self.client.get("/").data)
        self.assertEqual(self.client.get("/healthz").json["status"], "ok")
        self.assertEqual(self.client.get("/readyz").status_code, 200)

    def test_create_detail_and_audit(self):
        response = self.create()
        self.assertEqual(response.status_code, 303)
        detail = self.client.get(response.location)
        self.assertIn(b"Catalogue", detail.data)
        self.assertIn("Demande créée".encode(), detail.data)
        self.assertIn(b"Nouvelle recherche", detail.data)

    def test_status_update_and_filter(self):
        self.create()
        response = self.client.post("/deliveries/1/status", data={"status": "delivered", "csrf_token": self.token()})
        self.assertEqual(response.status_code, 303)
        self.assertIn("Statut : Livrée".encode(), self.client.get(response.location).data)
        self.assertIn(b"Catalogue", self.client.get("/?status=delivered").data)
        self.assertNotIn(b"Catalogue", self.client.get("/?status=pending").data)

    def test_invalid_input_is_not_saved(self):
        for override in [{"name": " "}, {"name": "a" * 81}, {"release": ""}, {"environment": "unknown"}, {"description": "a" * 1001}]:
            with self.subTest(override=override):
                self.assertEqual(self.create(**override).status_code, 422)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0], 0)

    def test_csrf_rejects_missing_wrong_unicode_and_other_session(self):
        for token in ["", "wrong", "é"]:
            self.assertEqual(self.client.post("/deliveries/new", data={"csrf_token": token}).status_code, 400)
        other = self.app.test_client()
        self.assertEqual(other.post("/deliveries/new", data={"csrf_token": self.token()}).status_code, 400)

    def test_csrf_blocks_status_change(self):
        self.create()
        self.assertEqual(self.client.post("/deliveries/1/status", data={"status": "delivered"}).status_code, 400)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT status FROM deliveries").fetchone()[0], "pending")

    def test_html_is_escaped(self):
        response = self.create(name='<script>alert("x")</script>')
        page = self.client.get(response.location).data
        self.assertNotIn(b"<script>", page)
        self.assertIn(b"&lt;script&gt;", page)

    def test_sql_input_is_stored_as_text(self):
        name = "'; DROP TABLE deliveries; --"
        self.create(name=name)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT name FROM deliveries").fetchone()[0], name)

    def test_invalid_status_and_unknown_delivery(self):
        self.create()
        self.assertEqual(self.client.get("/?status=unknown").status_code, 400)
        self.assertEqual(self.client.get("/deliveries/999").status_code, 404)
        self.assertEqual(self.client.post("/deliveries/1/status", data={"status": "bad", "csrf_token": self.token()}).status_code, 400)

    def test_data_survives_application_restart(self):
        self.create()
        second_app = create_app(self.config)
        self.assertIn(b"Catalogue", second_app.test_client().get("/").data)

    def test_security_headers_and_cookie(self):
        response = self.client.get("/deliveries/new")
        self.assertIn("script-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", response.headers["Set-Cookie"])
        self.assertTrue(re.search(r'name="csrf_token" value="[a-f0-9]{64}"', response.get_data(as_text=True)))

    def test_oversized_request_and_failed_readiness(self):
        self.assertEqual(self.client.post("/deliveries/new", data={"name": "x" * 20000}).status_code, 413)
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("DROP TABLE events")
            db.execute("DROP TABLE deliveries")
            db.commit()
        self.assertEqual(self.client.get("/readyz").status_code, 503)
        self.assertEqual(self.client.get("/healthz").status_code, 200)


if __name__ == "__main__":
    unittest.main()
