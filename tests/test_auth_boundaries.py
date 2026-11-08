import tempfile
import unittest

from flask import Flask, jsonify, request

from app.auth import install_auth


NORMAL_TOKEN = "normal-test-token-" + "n" * 40
ADMIN_TOKEN = "admin-test-token-" + "a" * 40


class AuthenticationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-auth-boundaries-")
        app = Flask(__name__)

        @app.get("/health")
        def health():
            return jsonify({"ok": True})

        @app.post("/api/providers")
        def providers_write():
            return jsonify({"ok": True}), 201

        @app.post("/api/workspace/rules")
        def rules_write():
            return jsonify({"ok": True}), 201

        @app.post("/api/workspace/apply_edit")
        def workspace_edit():
            return jsonify({"mode": (request.get_json(silent=True) or {}).get("mode")})

        @app.post("/api/write")
        def generic_write():
            return jsonify({"ok": True})

        install_auth(
            app,
            auth_token=NORMAL_TOKEN,
            admin_token=ADMIN_TOKEN,
            data_dir=self.temp.name,
            local_ips=[],
        )
        self.client = app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def _remote(self, method, path, token=None, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if token:
            headers["Authorization"] = "Bearer " + token
        return self.client.open(
            path,
            method=method,
            headers=headers,
            environ_overrides={"REMOTE_ADDR": "198.51.100.25"},
            **kwargs
        )

    def test_remote_health_requires_a_valid_token(self):
        missing = self._remote("GET", "/health")
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.headers.get("Cache-Control"), "no-store")
        self.assertNotIn(NORMAL_TOKEN, missing.get_data(as_text=True))

        normal = self._remote("GET", "/health", NORMAL_TOKEN)
        self.assertEqual(normal.status_code, 200)
        self.assertTrue(normal.get_json()["ok"])

    def test_normal_token_cannot_change_provider_or_workspace_policy(self):
        provider = self._remote("POST", "/api/providers", NORMAL_TOKEN, json={})
        self.assertEqual(provider.status_code, 403)

        rules = self._remote("POST", "/api/workspace/rules", NORMAL_TOKEN, json={})
        self.assertEqual(rules.status_code, 403)

        admin_provider = self._remote("POST", "/api/providers", ADMIN_TOKEN, json={})
        self.assertEqual(admin_provider.status_code, 201)

    def test_normal_token_can_use_ask_mode_workspace_edit(self):
        response = self._remote(
            "POST",
            "/api/workspace/apply_edit",
            NORMAL_TOKEN,
            json={"mode": "ask"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["mode"], "ask")

    def test_cross_site_and_same_site_write_metadata_are_rejected(self):
        for fetch_site in ("cross-site", "same-site"):
            with self.subTest(fetch_site=fetch_site):
                response = self._remote(
                    "POST",
                    "/api/write",
                    NORMAL_TOKEN,
                    headers={"Sec-Fetch-Site": fetch_site},
                    json={},
                )
                self.assertEqual(response.status_code, 403)

        origin = self._remote(
            "POST",
            "/api/write",
            NORMAL_TOKEN,
            headers={"Origin": "https://attacker.example"},
            json={},
        )
        self.assertEqual(origin.status_code, 403)

        same_origin = self._remote(
            "POST",
            "/api/write",
            NORMAL_TOKEN,
            headers={"Origin": "http://localhost/"},
            json={},
        )
        # The request Host defaults to localhost in Flask's test client.
        self.assertEqual(same_origin.status_code, 200)

    def test_loopback_request_remains_local_and_does_not_need_remote_token(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
