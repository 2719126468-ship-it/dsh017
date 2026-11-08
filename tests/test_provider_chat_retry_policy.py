import unittest
from unittest.mock import Mock, patch

from flask import Flask

from app.chat_ui import chat_ui_bp


class ProviderChatRetryPolicyTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(chat_ui_bp)
        self.client = app.test_client()
        self.provider = {
            "id": "retry-policy",
            "name": "Retry Policy Provider",
            "base_url": "https://provider.example.test/v1",
            "protocol": "openai-chat-completions",
            "models": ["chat-model"],
            "default_model": "chat-model",
            "enabled": True,
        }
        self.secret = "synthetic-retry-policy-key"

    def _request(self):
        return self.client.post("/api/chat", json={
            "provider_id": "retry-policy",
            "model": "chat-model",
            "messages": [{"role": "user", "content": "test retry policy"}],
        }, buffered=True)

    def _response(self, status, text):
        response = Mock()
        response.status_code = status
        response.text = text
        response.close = Mock()
        return response

    def _patch_provider(self):
        return patch(
            "app.chat_ui.resolve_provider",
            return_value=(self.provider, self.secret,
                          "https://provider.example.test/v1/chat/completions"),
        )

    def test_auth_and_not_found_errors_are_not_retried(self):
        for status in (401, 403, 404):
            with self.subTest(status=status):
                upstream = self._response(status, "upstream rejected request")
                with self._patch_provider(), \
                     patch("app.chat_ui.provider_request", return_value=upstream) as send, \
                     patch("time.sleep") as sleep:
                    response = self._request()

                self.assertEqual(response.status_code, 200)
                stream = response.get_data(as_text=True)
                self.assertIn("HTTP %d" % status, stream)
                self.assertEqual(send.call_count, 1)
                sleep.assert_not_called()
                upstream.close.assert_called_once()

    def test_server_error_is_returned_without_unbounded_retry(self):
        upstream = self._response(503, "temporarily unavailable")
        with self._patch_provider(), \
             patch("app.chat_ui.provider_request", return_value=upstream) as send, \
             patch("time.sleep") as sleep:
            response = self._request()

        self.assertIn("HTTP 503", response.get_data(as_text=True))
        self.assertEqual(send.call_count, 1)
        sleep.assert_not_called()
        upstream.close.assert_called_once()

    def test_rate_limit_is_retried_at_most_three_times(self):
        upstream = self._response(429, "rate limited")
        with self._patch_provider(), \
             patch("app.chat_ui.provider_request", return_value=upstream) as send, \
             patch("time.sleep") as sleep:
            response = self._request()

        stream = response.get_data(as_text=True)
        self.assertIn("已重试3次", stream)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(upstream.close.call_count, 3)

    def test_transport_exception_is_retried_at_most_three_times_and_redacted(self):
        error = RuntimeError(
            "connection failed Authorization: Bearer " + self.secret
        )
        with self._patch_provider(), \
             patch("app.chat_ui.provider_request", side_effect=error) as send, \
             patch("time.sleep") as sleep:
            response = self._request()

        stream = response.get_data(as_text=True)
        self.assertIn("[REDACTED]", stream)
        self.assertNotIn(self.secret, stream)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
