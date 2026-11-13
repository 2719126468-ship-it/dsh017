import unittest
from unittest.mock import patch

from flask import Flask

from app.bili_routes import bili_bp


class BilibiliUpstreamErrorTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bili_bp)
        self.client = app.test_client()

    def assert_sanitized_upstream_error(self, response):
        self.assertEqual(response.status_code, 502)
        payload = response.get_json()
        self.assertEqual(payload["code"], -502)
        self.assertEqual(payload["message"], "Bilibili 服务暂时不可用，请稍后重试")
        self.assertNotIn("internal-hostname", response.get_data(as_text=True))
        self.assertNotIn("secret-token", response.get_data(as_text=True))

    def test_suggest_does_not_expose_transport_exception(self):
        with patch("app.bili_routes.client.s.get",
                   side_effect=RuntimeError("internal-hostname secret-token")):
            response = self.client.get("/api/suggest?q=demo")
        self.assert_sanitized_upstream_error(response)

    def test_pages_does_not_expose_transport_exception(self):
        with patch("app.bili_routes.client.s.get",
                   side_effect=RuntimeError("internal-hostname secret-token")):
            response = self.client.get("/api/pages?bvid=BV1abc123")
        self.assert_sanitized_upstream_error(response)

    def test_playurl_does_not_expose_transport_exception(self):
        with patch("app.bili_routes._playurl_cache_get", return_value=None), \
             patch("app.bili_routes.client.s.get",
                   side_effect=RuntimeError("internal-hostname secret-token")):
            response = self.client.get("/api/playurl?bvid=BV1abc123")
        self.assert_sanitized_upstream_error(response)


if __name__ == "__main__":
    unittest.main()
