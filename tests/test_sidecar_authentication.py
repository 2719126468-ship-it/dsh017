import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ServiceAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="dsh017-service-auth-")
        with patch.dict(os.environ, {"DSH017_DATA_DIR": cls.tmp.name}, clear=False):
            cls.tarot = importlib.reload(importlib.import_module("tarot_server"))
            cls.novel = importlib.reload(importlib.import_module("novel_server"))
            cls.hub = importlib.reload(importlib.import_module("hub_server"))
            cls.bili = importlib.reload(importlib.import_module("bili_console"))

        cls.apps = {
            "bili": cls.bili.app,
            "hub": cls.hub.app,
            "novel": cls.novel.app,
            "tarot": cls.tarot.app,
        }
        cls.token_files = {
            tuple(app.extensions["dsh017_auth"]["token_files"])
            for app in cls.apps.values()
        }
        if len(cls.token_files) != 1:
            raise AssertionError("All four services must use the same token files")
        normal_path, admin_path = next(iter(cls.token_files))
        cls.normal_token = Path(normal_path).read_text(encoding="utf-8").strip()
        cls.admin_token = Path(admin_path).read_text(encoding="utf-8").strip()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def remote(self, client, path, token=None, method="GET", **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if token:
            headers["Authorization"] = "Bearer " + token
        return client.open(
            path,
            method=method,
            headers=headers,
            environ_overrides={"REMOTE_ADDR": "198.51.100.23"},
            **kwargs,
        )

    def test_every_service_uses_one_auth_hook_and_request_body_limit(self):
        for name, app in self.apps.items():
            with self.subTest(service=name):
                hooks = [
                    fn for fn in app.before_request_funcs.get(None, [])
                    if getattr(fn, "__name__", "") == "_dsh017_auth_gate"
                ]
                self.assertEqual(len(hooks), 1)
                self.assertEqual(app.config["MAX_CONTENT_LENGTH"], 8 * 1024 * 1024)

    def test_every_service_rejects_remote_page_and_health_without_token(self):
        for name, app in self.apps.items():
            client = app.test_client()
            for path in ("/", "/health"):
                with self.subTest(service=name, path=path):
                    response = self.remote(client, path)
                    self.assertEqual(response.status_code, 401)

    def test_shared_normal_token_opens_every_service_page_and_health(self):
        for name, app in self.apps.items():
            client = app.test_client()
            for path in ("/", "/health"):
                with self.subTest(service=name, path=path):
                    response = self.remote(client, path, self.normal_token)
                    self.assertEqual(response.status_code, 200)
                    if path == "/health":
                        self.assertEqual(response.get_json()["status"], "ok")

    def test_api_routes_on_all_four_services_require_remote_token(self):
        api_paths = {
            "bili": "/api/providers",
            "hub": "/api/status",
            "novel": "/api/search?q=auth-boundary-test",
            "tarot": "/api/draw?n=1",
        }
        for name, path in api_paths.items():
            with self.subTest(service=name, path=path):
                response = self.remote(self.apps[name].test_client(), path)
                self.assertEqual(response.status_code, 401)

    def test_bili_provider_api_keeps_secrets_out_of_remote_read_response(self):
        client = self.bili.app.test_client()
        response = self.remote(client, "/api/providers", self.normal_token)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        for provider in payload["items"]:
            self.assertNotIn("api_key", provider)

    def test_bili_provider_write_requires_admin_token_on_real_service_app(self):
        client = self.bili.app.test_client()
        normal = self.remote(
            client, "/api/providers", self.normal_token, method="POST", json={}
        )
        self.assertEqual(normal.status_code, 403)

        # An invalid body is rejected by the route after the admin auth gate;
        # this proves the admin token reaches the handler without writing data.
        admin = self.remote(
            client, "/api/providers", self.admin_token, method="POST", json={}
        )
        self.assertEqual(admin.status_code, 400)

    def test_host_local_access_remains_exempt(self):
        for name, app in self.apps.items():
            with self.subTest(service=name):
                response = app.test_client().get(
                    "/health",
                    environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
                )
                self.assertEqual(response.status_code, 200)

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

    def test_novel_image_proxy_rejects_untrusted_urls_before_network(self):
        with patch("novel_server.validate_remote_url", return_value=False) as validate, \
             patch.object(self.novel.client.s, "get") as get:
            response = self.remote(
                self.novel.app.test_client(),
                "/api/img?u=http://127.0.0.1/admin",
                self.normal_token,
            )
        self.assertEqual(response.status_code, 400)
        validate.assert_called_once_with(
            "http://127.0.0.1/admin",
            allowed_suffixes=self.novel.NOVEL_IMAGE_HOSTS,
        )
        get.assert_not_called()

    def test_novel_image_proxy_fetches_allowlisted_cdn_without_redirects(self):
        class FakeImageResponse:
            status_code = 200
            headers = {"Content-Type": "image/png"}
            closed = False

            def iter_content(self, chunk_size):
                return [b"image-bytes"]

            def close(self):
                self.closed = True

        fake = FakeImageResponse()
        url = "https://p3-novel.byteimg.com/large/test.png"
        with patch("novel_server.validate_remote_url", return_value=True) as validate, \
             patch.object(self.novel.client.s, "get", return_value=fake) as get:
            response = self.remote(
                self.novel.app.test_client(),
                "/api/img?u=" + url,
                self.normal_token,
            )
            body = response.data

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body, b"image-bytes")
        validate.assert_called_once_with(url, allowed_suffixes=self.novel.NOVEL_IMAGE_HOSTS)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(fake.closed)

    def test_novel_image_proxy_does_not_follow_cdn_redirects(self):
        class FakeRedirectResponse:
            status_code = 302
            headers = {"Location": "http://127.0.0.1/admin"}
            closed = False

            def close(self):
                self.closed = True

        fake = FakeRedirectResponse()
        with patch("novel_server.validate_remote_url", return_value=True), \
             patch.object(self.novel.client.s, "get", return_value=fake) as get:
            response = self.remote(
                self.novel.app.test_client(),
                "/api/img?u=https://p3-novel.byteimg.com/large/test.png",
                self.normal_token,
            )

        self.assertEqual(response.status_code, 502)
        get.assert_called_once()
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(fake.closed)


if __name__ == "__main__":
    unittest.main()
