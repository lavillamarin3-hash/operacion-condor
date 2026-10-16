import tempfile
import unittest
from pathlib import Path

from condor_app import create_app
from condor_app.db import get_db
from condor_app.models import user


class CondorLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.password = "TestCredential-23!"
        self.flag = "COCIBER{temporary_test_only}"
        wordlist = root / "candidates.txt"
        wordlist.write_text("WrongCandidate!\n" + self.password + "\n", encoding="utf-8")
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "test-only-session-key-no-production-use",
            "DATABASE": str(root / "lab.sqlite3"),
            "WORDLIST_PATH": str(wordlist),
            "TRUSTED_HOSTS": ["localhost"],
            "LAB_ADMIN_PASSWORD": self.password,
            "LAB_FLAG": self.flag,
        }
        self.app = create_app(self.config)
        result = self.app.test_cli_runner().invoke(args=["init-lab"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, client=None):
        return (client or self.client).post("/login", data={
            "username": "admin.condor", "password": self.password,
        })

    def csrf(self):
        self.client.get("/admin")
        with self.client.session_transaction() as current_session:
            return current_session["csrf_token"]

    def test_public_pages_and_dictionary_never_reveal_flag(self):
        for path in ("/", "/noticias", "/login", "/recursos/candidatas.txt", "/healthz"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.flag.encode(), response.data)
        self.assertIn(self.password.encode(), self.client.get("/recursos/candidatas.txt").data)
        self.assertEqual(self.client.get("/healthz").json["status"], "ok")

    def test_admin_guard_and_generic_login_failure(self):
        self.assertEqual(self.client.get("/admin").status_code, 302)
        self.assertEqual(self.client.post("/admin/comunicados").status_code, 302)
        for username in ("admin.condor", "unknown", "' OR 1=1 --"):
            response = self.client.post("/login", data={"username": username, "password": "wrong"})
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Credenciales incorrectas", response.data)
            self.assertNotIn(self.flag.encode(), response.data)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_login_without_csrf_rotates_session_and_sets_cookie(self):
        with self.client.session_transaction() as current_session:
            current_session["publication_id"] = 999
            current_session["csrf_token"] = "old-csrf"
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin")
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Expires=", cookie)
        with self.client.session_transaction() as current_session:
            self.assertNotIn("publication_id", current_session)
            self.assertNotIn("csrf_token", current_session)
        self.assertNotIn(self.flag.encode(), self.client.get("/admin").data)

    def test_csrf_and_validation_prevent_publication(self):
        self.login()
        payload = {"title": "Título de prueba", "body": "Comunicado válido de entrenamiento"}
        self.assertEqual(self.client.post("/admin/comunicados", data=payload).status_code, 403)
        payload["csrf_token"] = "wrong"
        self.assertEqual(self.client.post("/admin/comunicados", data=payload).status_code, 403)
        payload["csrf_token"] = "sesión-inválida"
        self.assertEqual(self.client.post("/admin/comunicados", data=payload).status_code, 403)
        payload.update(csrf_token=self.csrf(), title="x")
        self.assertEqual(self.client.post("/admin/comunicados", data=payload).status_code, 302)
        self.assertNotIn(self.flag.encode(), self.client.get("/admin").data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT count(*) FROM announcements").fetchone()[0], 0)

    def test_publication_unlocks_flag_only_for_current_session_and_escapes_html(self):
        self.login()
        response = self.client.post("/admin/comunicados", data={
            "title": "<script>alert(1)</script>",
            "body": "Prueba de auditoría: <img src=x onerror=alert(1)>",
            "csrf_token": self.csrf(),
        })
        self.assertEqual(response.status_code, 302)
        dashboard = self.client.get("/admin")
        self.assertIn(self.flag.encode(), dashboard.data)
        self.assertNotIn(b"<script>alert(1)</script>", dashboard.data)
        public_page = self.client.get("/")
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", public_page.data)
        self.assertNotIn(self.flag.encode(), public_page.data)
        second_client = self.app.test_client()
        self.login(second_client)
        self.assertNotIn(self.flag.encode(), second_client.get("/admin").data)

    def test_logout_is_post_and_csrf_protected(self):
        self.login()
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.assertEqual(self.client.post("/logout").status_code, 403)
        response = self.client.post("/logout", data={"csrf_token": self.csrf()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_initialization_is_idempotent_and_password_is_hashed(self):
        with self.app.app_context():
            first = user.find_by_username("admin.condor")["password_hash"]
            self.assertNotEqual(first, self.password)
            self.assertTrue(first.startswith("scrypt:"))
        self.app.config.update(LAB_ADMIN_PASSWORD="WrongCandidate!", LAB_FLAG="COCIBER{different_test_flag}")
        result = self.app.test_cli_runner().invoke(args=["init-lab"])
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            self.assertEqual(user.find_by_username("admin.condor")["password_hash"], first)
            self.assertEqual(get_db().execute("SELECT value FROM lab_settings WHERE key='flag'").fetchone()[0], self.flag)
            self.assertEqual(get_db().execute("SELECT count(*) FROM users").fetchone()[0], 1)

    def test_untrusted_host_rejected_and_security_headers(self):
        self.assertEqual(self.client.get("/healthz", base_url="http://untrusted.example").status_code, 400)
        response = self.client.get("/login")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_missing_production_secret_refused(self):
        config = dict(self.config, TESTING=False, SECRET_KEY=None)
        with self.assertRaisesRegex(RuntimeError, "CONDOR_SECRET_KEY"):
            create_app(config)
        with self.assertRaisesRegex(RuntimeError, "CONDOR_TRUSTED_HOSTS"):
            create_app(dict(self.config, TRUSTED_HOSTS=[]))

    def test_missing_dictionary_candidate_refuses_init(self):
        self.app.config["LAB_ADMIN_PASSWORD"] = "NotInTheDictionary!"
        result = self.app.test_cli_runner().invoke(args=["init-lab"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("diccionario", result.output)

    def test_failed_login_logs_never_contain_password(self):
        with self.assertLogs(self.app.logger, level="INFO") as logs:
            self.client.post("/login", data={"username": "admin.condor", "password": "PrivateWrongValue"})
        self.assertNotIn("PrivateWrongValue", " ".join(logs.output))
        self.assertIn("lab_login failure", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
