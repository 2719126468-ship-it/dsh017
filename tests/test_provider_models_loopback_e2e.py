import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from flask import Flask

from app.providers import provider_bp


class ProviderModelsLoopbackE2ETests(unittest.TestCase):
    def setUp(self):
        self.secret = "synthetic-model-catalog-api-key"
        self.received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler_self):
                self.received["path"] = handler_self.path
                self.received["authorization"] = handler_self.headers.get("Authorization")
                if handler_self.path == "/v1/models":
                    status = self.server.status
                    payload = self.server.payload
                else:
                    status = 404
                    payload = {"error": {"message": "not found"}}
                body = json.dumps(payload).encode("utf-8")
                handler_self.send_response(status)
                handler_self.send_header("Content-Type", "application/json")
                handler_self.send_header("Content-Length", str(len(body)))
                handler_self.end_headers()
                handler_self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.server.status = 200
        self.server.payload = {
            "data": [
                {"id": "model-z"},
                {"id": "model-a"},
                {"id": "../invalid"},
                {"id": "bad model"},
                {"name": "missing id"},
            ]
        }
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%d/v1" % self.server.server_port

        app = Flask(__name__)
        app.register_blueprint(provider_bp)
        self.client = app.test_client()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _provider(self):
        return {
            "id": "models-loopback",
            "name": "Loopback Models E2E",
            "base_url": self.base_url,
            "protocol": "openai-chat-completions",
            "models": [],
            "default_model": "",
            "enabled": True,
        }

    def _call(self):
        return self.client.post("/api/providers/models-loopback/models")

    def test_real_loopback_models_catalog_filters_invalid_ids(self):
        with patch("app.providers.get_provider", return_value=self._provider()), \
             patch("app.providers.get_provider_secret", return_value=self.secret):
            response = self._call()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["models"], ["model-a", "model-z"])
        self.assertEqual(self.received["path"], "/v1/models")
        self.assertEqual(self.received["authorization"], "Bearer " + self.secret)

    def test_empty_models_catalog_is_a_valid_empty_result(self):
        self.server.payload = {"data": []}
        with patch("app.providers.get_provider", return_value=self._provider()), \
             patch("app.providers.get_provider_secret", return_value=self.secret):
            response = self._call()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"code": 0, "models": []})

    def test_authentication_error_redacts_secret_from_provider_api_response(self):
        self.server.status = 401
        self.server.payload = {
            "error": {
                "message": "Authorization: Bearer " + self.secret
                    + "; api_key=" + self.secret
            }
        }
        with patch("app.providers.get_provider", return_value=self._provider()), \
             patch("app.providers.get_provider_secret", return_value=self.secret):
            response = self._call()

        self.assertEqual(response.status_code, 502)
        body = response.get_data(as_text=True)
        self.assertNotIn(self.secret, body)
        self.assertIn("[REDACTED]", body)
        self.assertEqual(self.received["path"], "/v1/models")


if __name__ == "__main__":
    unittest.main()
