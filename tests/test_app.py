import csv
import io
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
            "LAB_ADMIN_USERNAME": "admin.condor",
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

    def discover_accounts(self, client=None):
        client = client or self.client
        robots = client.get("/robots.txt").get_data(as_text=True)
        manifest_path = next(
            line.partition(":")[2].strip()
            for line in robots.splitlines() if line.startswith("Disallow:")
        )
        manifest = client.get(manifest_path).get_json()
        paths = manifest["archivos"]
        accounts = list(csv.DictReader(io.StringIO(
            client.get(paths["cuentas"]).get_data(as_text=True)
        )))
        events = client.get(paths["bitacora"]).get_json()["eventos"]
        latest_events = {}
        for event in events:
            account_id = event["cuenta_id"]
            if account_id not in latest_events or event["secuencia"] > latest_events[account_id]["secuencia"]:
                latest_events[account_id] = event
        rule = manifest["regla_publicacion"]
        eligible = [
            account for account in accounts
            if account["perfil"] == rule["perfil_requerido"]
            and latest_events[account["id"]]["estado"] == rule["estado_requerido"]
        ]
        return manifest, accounts, eligible

    def test_html_does_not_give_username_dictionary_or_access_solution(self):
        for path in ("/", "/noticias", "/login"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            for hidden_value in (
                "admin.condor", self.password, self.flag,
                "/recursos/candidatas.txt", "/respaldo/operaciones/",
            ):
                self.assertNotIn(hidden_value, page)
        # Failure remains a stable marker for the terminal HTTP exercise.
        failed_login = self.client.post("/login", data={"username": "wrong", "password": "wrong"})
        self.assertIn(b"Credenciales incorrectas", failed_login.data)

    def test_reconnaissance_requires_latest_state_and_has_one_eligible_account(self):
        manifest, accounts, eligible = self.discover_accounts()
        self.assertEqual(len(accounts), 5)
        self.assertGreater(len([account for account in accounts if account["perfil"] == "editor"]), 1)
        self.assertEqual([account["usuario"] for account in eligible], ["admin.condor"])
        for name in ("cuentas", "bitacora"):
            response = self.client.get(manifest["archivos"][name])
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.flag.encode(), response.data)
            self.assertNotIn(self.password.encode(), response.data)
            self.assertNotIn(b"password_hash", response.data)
        # An obsolete editor record looks plausible, but cannot authenticate.
        for account in accounts:
            response = self.client.post("/login", data={
                "username": account["usuario"], "password": self.password,
            })
            self.assertEqual(response.status_code, 302 if account in eligible else 200)

    def test_terminal_discovery_and_bounded_dictionary_reach_admin_but_not_flag(self):
        manifest, _accounts, eligible = self.discover_accounts()
        candidates = self.client.get(manifest["archivos"]["diccionario"]).get_data(as_text=True).splitlines()
        self.assertGreaterEqual(len(candidates), 2)
        self.assertLessEqual(len(candidates), 50)
        successes = []
        for candidate in candidates:
            response = self.client.post("/login", data={
                "username": eligible[0]["usuario"], "password": candidate,
            })
            if response.status_code == 302:
                successes.append(candidate)
            else:
                self.assertIn(b"Credenciales incorrectas", response.data)
        self.assertEqual(successes, [self.password])
        dashboard = self.client.get("/admin")
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotIn(self.flag.encode(), dashboard.data)
        denied = self.client.post("/admin/comunicados", data={
            "title": "Auditoría terminal", "body": "Prueba sin token: no debe publicar.",
        })
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn(self.flag.encode(), self.client.get("/admin").data)

    def test_artifact_urls_and_login_redirect_respect_wsgi_mount_prefix(self):
        prefix = "/practice/abc123"
        env = {"SCRIPT_NAME": prefix}
        robots = self.client.get("/robots.txt", environ_overrides=env).get_data(as_text=True)
        manifest_path = next(line.partition(":")[2].strip() for line in robots.splitlines() if line.startswith("Disallow:"))
        self.assertEqual(manifest_path, prefix + "/respaldo/operaciones/manifest.json")
        manifest = self.client.get(manifest_path.removeprefix(prefix), environ_overrides=env).get_json()
        for path in manifest["archivos"].values():
            self.assertTrue(path.startswith(prefix + "/"))
            self.assertEqual(self.client.get(path.removeprefix(prefix), environ_overrides=env).status_code, 200)
        response = self.client.post("/login", data={
            "username": "admin.condor", "password": self.password,
        }, environ_overrides=env)
        self.assertEqual(response.headers["Location"], prefix + "/admin")

    def test_configured_run_username_is_used_for_initialization_and_discovery(self):
        custom_username = "editor.pacifico"
        configuration = dict(self.config, DATABASE=str(Path(self.tmp.name) / "run.sqlite3"), LAB_ADMIN_USERNAME=custom_username)
        app = create_app(configuration)
        result = app.test_cli_runner().invoke(args=["init-lab"])
        self.assertEqual(result.exit_code, 0, result.output)
        client = app.test_client()
        _manifest, accounts, eligible = self.discover_accounts(client)
        self.assertEqual([account["usuario"] for account in eligible], [custom_username])
        self.assertEqual(len({account["usuario"] for account in accounts}), len(accounts))
        with app.app_context():
            self.assertIsNone(user.find_by_username("admin.condor"))
        self.assertEqual(client.post("/login", data={"username": custom_username, "password": self.password}).status_code, 302)
        self.assertEqual(client.post("/login", data={"username": "admin.condor", "password": self.password}).status_code, 200)
        for invalid in ("", "../admin", "UpperCase", "a" * 41, None):
            with self.subTest(username=invalid), self.assertRaisesRegex(RuntimeError, "LAB_ADMIN_USERNAME"):
                create_app(dict(self.config, LAB_ADMIN_USERNAME=invalid))


if __name__ == "__main__":
    unittest.main()
