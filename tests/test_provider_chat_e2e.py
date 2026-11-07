import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from flask import Flask

from app.chat_ui import chat_ui_bp


class ProviderChatLoopbackE2ETests(unittest.TestCase):
    def setUp(self):
        self.received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler_self):
                length = int(handler_self.headers.get("Content-Length", "0"))
                payload = handler_self.rfile.read(length)
                self.received["path"] = handler_self.path
                self.received["authorization"] = handler_self.headers.get("Authorization")
                self.received["accept"] = handler_self.headers.get("Accept")
                self.received["payload"] = json.loads(payload.decode("utf-8"))

                events = [
                    {"choices": [{"delta": {"content": "Hello"}}]},
                    {"choices": [{"delta": {"content": " from local E2E"}}]},
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                ]
                body = b"".join(
                    ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8")
                    for event in events
                ) + b"data: [DONE]\n\n"
                handler_self.send_response(200)
                handler_self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                handler_self.send_header("Cache-Control", "no-cache")
                handler_self.send_header("Content-Length", str(len(body)))
                handler_self.end_headers()
                handler_self.wfile.write(body)
                handler_self.wfile.flush()

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

    def test_provider_registry_resolution_real_transport_and_sse_route(self):
        provider = {
            "id": "loopback-e2e",
            "name": "Local OpenAI-compatible E2E",
            "base_url": self.base_url,
            "protocol": "openai-chat-completions",
            "models": ["local-chat-model"],
            "default_model": "local-chat-model",
            "enabled": True,
        }
        synthetic_key = "dsh017-e2e-synthetic-key"

        # Keep the real resolve_provider(), provider_request(), DNS-pinned
        # loopback transport, Flask route and SSE parser in this test. Only
        # the provider registry lookup and secret store are replaced.
        with patch("app.providers.get_provider", return_value=provider), \
             patch("app.providers.get_provider_secret", return_value=synthetic_key):
            response = self.client.post("/api/chat", json={
                "provider_id": "loopback-e2e",
                "model": "local-chat-model",
                "messages": [{"role": "user", "content": "Say hello"}],
            }, buffered=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        stream = response.get_data(as_text=True)
        self.assertIn("Hello", stream)
        self.assertIn(" from local E2E", stream)
        self.assertIn("[DONE]", stream)
        self.assertNotIn(synthetic_key, stream)

        self.assertEqual(self.received["path"], "/v1/chat/completions")
        self.assertEqual(self.received["authorization"], "Bearer " + synthetic_key)
        self.assertEqual(self.received["accept"], "text/event-stream")
        self.assertEqual(self.received["payload"]["model"], "local-chat-model")
        self.assertTrue(self.received["payload"]["stream"])
        self.assertEqual(
            self.received["payload"]["messages"],
            [{"role": "user", "content": "Say hello"}],
        )

    def test_unknown_model_is_rejected_before_loopback_request(self):
        provider = {
            "id": "loopback-e2e",
            "name": "Local OpenAI-compatible E2E",
            "base_url": self.base_url,
            "protocol": "openai-chat-completions",
            "models": ["allowed-model"],
            "default_model": "allowed-model",
            "enabled": True,
        }
        with patch("app.providers.get_provider", return_value=provider), \
             patch("app.providers.get_provider_secret", return_value=""):
            response = self.client.post("/api/chat", json={
                "provider_id": "loopback-e2e",
                "model": "not-allow-listed",
                "messages": [{"role": "user", "content": "must not be sent"}],
            }, buffered=True)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.received, {})


if __name__ == "__main__":
    unittest.main()
