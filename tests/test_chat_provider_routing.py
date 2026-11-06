import unittest
from unittest.mock import Mock, patch

from flask import Flask

from app.chat_ui import chat_ui_bp


class ChatProviderRoutingTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(chat_ui_bp)
        self.client = app.test_client()

    def test_chat_request_uses_selected_openai_compatible_endpoint(self):
        provider = {
            "id": "custom",
            "name": "Custom",
            "base_url": "https://gateway.example.test/v1",
            "protocol": "openai-chat-completions",
            "models": ["custom-model"],
            "default_model": "custom-model",
            "enabled": True,
        }
        upstream = Mock()
        upstream.status_code = 200
        upstream.iter_content.return_value = [
            b'data: {"choices":[{"delta":{"content":"hello from provider"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        response = None
        with patch("app.chat_ui.resolve_provider", return_value=(
            provider, "provider-secret", "https://gateway.example.test/v1/chat/completions"
        )), patch("app.chat_ui.provider_request", return_value=upstream) as post:
            response = self.client.post("/api/chat", json={
                "provider_id": "custom",
                "model": "custom-model",
                "messages": [{"role": "user", "content": "hello"}],
            })
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("hello from provider", body)
        self.assertEqual(post.call_args.args[:2], (
            "POST",
            "https://gateway.example.test/v1/chat/completions",
        ))
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer provider-secret")
        self.assertEqual(post.call_args.kwargs["json_body"]["model"], "custom-model")
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 180))
        upstream.close.assert_called_once()

    def test_unknown_provider_or_model_is_rejected_before_network(self):
        with patch("app.chat_ui.resolve_provider", side_effect=ValueError("provider unavailable")), \
             patch("app.chat_ui.provider_request") as post:
            response = self.client.post("/api/chat", json={
                "provider_id": "missing",
                "model": "not-listed",
                "messages": [{"role": "user", "content": "hello"}],
            })
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
