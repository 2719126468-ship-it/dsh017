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

        with patch("app.chat_ui.client.s.post", return_value=upstream):
            with app.test_request_context("/api/chat", method="POST", json=payload):
                response = api_chat()
                stream = iter(response.response)
                first_event = next(stream)
                self.assertIn("partial reply", first_event)
                stream.close()

        self.assertTrue(upstream.closed)


if __name__ == "__main__":
    unittest.main()
