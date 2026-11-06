import unittest
from unittest.mock import call, patch

from flask import Flask

from app.providers import _magpie_get_json, discover_local_magpie, provider_bp


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    def read(self, limit=-1):
        return self._payload if limit < 0 else self._payload[:limit]


class FakeConnection:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request_args = None
        self.closed = False

    def request(self, method, path, headers=None):
        self.request_args = (method, path, headers or {})

    def getresponse(self):
        return FakeResponse(b'{"name":"magpie","version":"test"}')

    def close(self):
        self.closed = True


class MagpieGatewayTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(provider_bp)
        self.client = app.test_client()

    def test_discovery_reads_local_magpie_and_filters_model_ids(self):
        with patch("app.providers._magpie_get_json", side_effect=[
            {"name": "magpie", "version": "v0.1.3188"},
            {"data": [
                {"id": "codex/gpt-5.1"},
                {"id": "grok-4.6@500k"},
                {"id": "invalid model"},
                {"id": "../bad"},
            ]},
        ]) as get_json:
            result = discover_local_magpie()

        self.assertEqual(result["id"], "magpie")
        self.assertEqual(result["base_url"], "http://127.0.0.1:3425/v1")
        self.assertEqual(result["gateway_version"], "v0.1.3188")
        self.assertEqual(result["models"], ["codex/gpt-5.1", "grok-4.6@500k"])
        self.assertEqual(get_json.call_args_list, [
            call("/api/hello"),
            call("/v1/models", include_app_key=True),
        ])

    def test_discovery_rejects_a_different_local_service(self):
        with patch("app.providers._magpie_get_json", return_value={"name": "other"}):
            with self.assertRaisesRegex(RuntimeError, "不是 Magpie"):
                discover_local_magpie()

    def test_http_client_uses_fixed_loopback_without_proxy_or_redirects(self):
        with patch("app.providers.http.client.HTTPConnection") as factory:
            connection = factory.return_value
            connection.getresponse.return_value = FakeResponse(
                b'{"name":"magpie","version":"test"}'
            )
            payload = _magpie_get_json("/api/hello")
        self.assertEqual(payload["name"], "magpie")
        factory.assert_called_once_with("127.0.0.1", 3425, timeout=3)
        connection.request.assert_called_once()
        method, path, headers = connection.request.call_args.args
        self.assertEqual((method, path), ("GET", "/api/hello"))
        self.assertNotIn("Authorization", headers)
        connection.close.assert_called_once()

    def test_detection_route_does_not_return_credentials(self):
        with patch("app.providers.discover_local_magpie", return_value={
            "id": "magpie",
            "name": "Magpie Gateway",
            "base_url": "http://127.0.0.1:3425/v1",
            "models": ["codex/gpt-5.1"],
            "default_model": "codex/gpt-5.1",
            "gateway_version": "test",
        }):
            response = self.client.post("/api/providers/detect-magpie")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["item"]["models"], ["codex/gpt-5.1"])
        self.assertNotIn("api_key", response.get_data(as_text=True))
        self.assertNotIn("magpie-dsh017", response.get_data(as_text=True))

    def test_detection_route_rejects_offline_gateway(self):
        with patch("app.providers.discover_local_magpie", side_effect=OSError("refused")):
            response = self.client.post("/api/providers/detect-magpie")
        self.assertEqual(response.status_code, 502)
        self.assertIn("refused", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
