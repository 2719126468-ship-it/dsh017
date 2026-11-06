import unittest
from unittest.mock import patch

from flask import Flask

from app.chat_ui import api_chat


class FakeStreamingResponse:
    status_code = 200

    def __init__(self):
        self.closed = False

    def iter_content(self, chunk_size=None, decode_unicode=False):
        yield b'data: {"choices":[{"delta":{"content":"partial reply"}}]}\n\n'

    def close(self):
        self.closed = True


class ChatStreamCleanupTests(unittest.TestCase):
    def test_upstream_response_closes_when_client_stops_consuming_stream(self):
        app = Flask(__name__)
        upstream = FakeStreamingResponse()
        payload = {"messages": [{"role": "user", "content": "hello"}]}
        provider = {
            "id": "zhipu",
            "name": "Test provider",
            "base_url": "https://provider.example.test/v1",
            "protocol": "openai-chat-completions",
            "models": ["glm-4.7-flash"],
            "default_model": "glm-4.7-flash",
            "enabled": True,
        }

        with patch(
            "app.chat_ui.resolve_provider",
            return_value=(
                provider,
                "test-api-key",
                "https://provider.example.test/v1/chat/completions",
            ),
        ), patch("app.chat_ui.provider_request", return_value=upstream) as upstream_post:
            with app.test_request_context("/api/chat", method="POST", json=payload):
                response = api_chat()
                self.assertEqual(response.status_code, 200)
                stream = iter(response.response)
                first_event = next(stream)
                self.assertIn("partial reply", first_event)
                stream.close()

        self.assertTrue(upstream.closed)
        self.assertEqual(upstream_post.call_args.args[:2], (
            "POST",
            "https://provider.example.test/v1/chat/completions",
        ))
        self.assertEqual(upstream_post.call_args.kwargs["timeout"], (5, 180))


if __name__ == "__main__":
    unittest.main()
