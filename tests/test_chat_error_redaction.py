import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from flask import Flask

from app.chat_ui import chat_ui_bp


class ChatUpstreamErrorRedactionTests(unittest.TestCase):
    def setUp(self):
        self.secret = "synthetic-provider-api-key-should-never-echo"

        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler_self):
                length = int(handler_self.headers.get("Content-Length", "0"))
                handler_self.rfile.read(length)
                body = json.dumps({
                    "error": {
                        "message": "Authorization: Bearer " + self.secret
                            + "; api_key=" + self.secret
                    }
                }).encode("utf-8")
                handler_self.send_response(401)
                handler_self.send_header("Content-Type", "application/json")
                handler_self.send_header("Content-Length", str(len(body)))
                handler_self.end_headers()
                handler_self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%d/v1" % self.server.server_port

        app = Flask(__name__)
        app.register_blueprint(chat_ui_bp)
        self.client = app.test_client()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _provider(self):
        return {
            "id": "error-redaction-e2e",
            "name": "Local Error Redaction E2E",
            "base_url": self.base_url,
            "protocol": "openai-chat-completions",
            "models": ["local-chat-model"],
            "default_model": "local-chat-model",
            "enabled": True,
        }

    def _chat(self):
        return self.client.post("/api/chat", json={
            "provider_id": "error-redaction-e2e",
            "model": "local-chat-model",
            "messages": [{"role": "user", "content": "trigger a synthetic upstream failure"}],
        }, buffered=True)

    def test_http_error_body_cannot_reflect_provider_secret_into_chat_sse(self):
        with patch("app.providers.get_provider", return_value=self._provider()), \
             patch("app.providers.get_provider_secret", return_value=self.secret):
            response = self._chat()

        self.assertEqual(response.status_code, 200)
        stream = response.get_data(as_text=True)
        self.assertIn("HTTP 401", stream)
        self.assertIn("[REDACTED]", stream)
        self.assertNotIn(self.secret, stream)

    def test_transport_exception_cannot_reflect_provider_secret_into_chat_sse(self):
        exception = RuntimeError(
            "upstream transport failed: Authorization: Bearer " + self.secret
            + "; api_key=" + self.secret
        )
        with patch("app.providers.get_provider", return_value=self._provider()), \
             patch("app.providers.get_provider_secret", return_value=self.secret), \
             patch("app.chat_ui.provider_request", side_effect=exception), \
             patch("time.sleep", return_value=None):
            response = self._chat()

        self.assertEqual(response.status_code, 200)
        stream = response.get_data(as_text=True)
        self.assertIn("[REDACTED]", stream)
        self.assertNotIn(self.secret, stream)


if __name__ == "__main__":
    unittest.main()
