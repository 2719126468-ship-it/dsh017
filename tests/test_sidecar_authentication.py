import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SidecarAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="dsh017-sidecar-auth-")
        with patch.dict(os.environ, {"DSH017_DATA_DIR": cls.tmp.name}, clear=False):
            cls.tarot = importlib.reload(importlib.import_module("tarot_server"))
            cls.novel = importlib.reload(importlib.import_module("novel_server"))
            cls.hub = importlib.reload(importlib.import_module("hub_server"))

        cls.apps = {
            "tarot": cls.tarot.app,
            "novel": cls.novel.app,
            "hub": cls.hub.app,
        }
        cls.token_files = {
            tuple(app.extensions["dsh017_auth"]["token_files"])
            for app in cls.apps.values()
        }
        if len(cls.token_files) != 1:
            raise AssertionError("Sidecar services must use the same token files")
        normal_path, admin_path = next(iter(cls.token_files))
        cls.normal_token = Path(normal_path).read_text(encoding="utf-8").strip()
        cls.admin_token = Path(admin_path).read_text(encoding="utf-8").strip()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def remote(self, client, path, token=None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        return client.get(
            path,
            headers=headers,
            environ_overrides={"REMOTE_ADDR": "198.51.100.23"},
        )

    def test_every_sidecar_rejects_remote_requests_without_token(self):
        for name, app in self.apps.items():
            with self.subTest(service=name):
                response = self.remote(app.test_client(), "/health")
                self.assertEqual(response.status_code, 401)

    def test_shared_normal_token_works_on_every_sidecar(self):
        for name, app in self.apps.items():
            with self.subTest(service=name):
                response = self.remote(app.test_client(), "/health", self.normal_token)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["status"], "ok")

    def test_host_local_access_remains_exempt(self):
        for name, app in self.apps.items():
            with self.subTest(service=name):
                response = app.test_client().get(
                    "/health",
                    environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
                )
                self.assertEqual(response.status_code, 200)

    def test_hub_status_api_requires_remote_token(self):
        response = self.remote(self.hub.app.test_client(), "/api/status")
        self.assertEqual(response.status_code, 401)

    def test_hub_checks_services_server_side(self):
        class FakeResponse:
            status = 200

            def __init__(self, payload):
                self.payload = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self.payload

        def fake_urlopen(url, timeout=0):
            if url.endswith("/metrics"):
                return FakeResponse({"daily": {}, "counters": {}})
            return FakeResponse({"status": "ok"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.remote(
                self.hub.app.test_client(), "/api/status", self.normal_token
            )
        self.assertEqual(response.status_code, 200)
        statuses = response.get_json()["services"]
        for port in ("8080", "8084", "8091", "8092"):
            self.assertTrue(statuses[port]["online"], port)
        self.assertIn("metrics", statuses["8092"])


if __name__ == "__main__":
    unittest.main()
