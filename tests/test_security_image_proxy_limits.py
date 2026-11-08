import unittest
from unittest.mock import Mock, patch

from flask import Flask

from app.bili_routes import bili_bp
from app.security import validate_remote_url


class RemoteUrlDnsBoundaryTests(unittest.TestCase):
    def test_mixed_public_and_private_dns_answers_are_rejected(self):
        answers = [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("10.0.0.7", 443)),
        ]
        with patch("app.security.socket.getaddrinfo", return_value=answers):
            self.assertFalse(
                validate_remote_url("https://i0.hdslb.com/a.jpg", ("hdslb.com",))
            )

    def test_ipv6_ula_and_link_local_dns_answers_are_rejected(self):
        for address in ("fc00::1", "fe80::1"):
            with self.subTest(address=address):
                answers = [
                    (10, 1, 6, "", (address, 443, 0, 0)),
                ]
                with patch("app.security.socket.getaddrinfo", return_value=answers):
                    self.assertFalse(
                        validate_remote_url("https://i0.hdslb.com/a.jpg", ("hdslb.com",))
                    )


class ImageProxyLimitTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bili_bp)
        self.client = app.test_client()

    def _upstream(self, content_type="image/png", content_length="3", status=200, chunks=None):
        response = Mock()
        response.status_code = status
        response.headers = {"Content-Type": content_type}
        if content_length is not None:
            response.headers["Content-Length"] = content_length
        response.iter_content.return_value = iter(chunks or [b"img"])
        response.close = Mock()
        return response

    def _get(self):
        return self.client.get("/api/img?u=https://i0.hdslb.com/test.png", buffered=True)

    def test_image_proxy_uses_streaming_without_following_redirects(self):
        upstream = self._upstream(chunks=[b"png"])
        with patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch("app.bili_routes.client.s.get", return_value=upstream) as get:
            response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.get_data(), b"png")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])

    def test_image_proxy_rejects_non_image_mime_and_redirect_response(self):
        html = self._upstream(content_type="text/html")
        with patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch("app.bili_routes.client.s.get", return_value=html):
            response = self._get()
        self.assertEqual(response.status_code, 415)
        html.close.assert_called()

        redirect = self._upstream(status=302)
        with patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch("app.bili_routes.client.s.get", return_value=redirect) as get:
            response = self._get()
        self.assertEqual(response.status_code, 502)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        redirect.close.assert_called()

    def test_image_proxy_rejects_declared_oversize_and_caps_unknown_length_stream(self):
        oversized = self._upstream(content_length="6")
        with patch("app.bili_routes._MAX_PROXY_IMAGE_BYTES", 5), \
             patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch("app.bili_routes.client.s.get", return_value=oversized):
            response = self._get()
        self.assertEqual(response.status_code, 413)
        oversized.close.assert_called()

        unknown_length = self._upstream(
            content_length=None,
            chunks=[b"abc", b"def", b"ghi"],
        )
        with patch("app.bili_routes._MAX_PROXY_IMAGE_BYTES", 5), \
             patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch("app.bili_routes.client.s.get", return_value=unknown_length):
            response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), b"abcde")
        unknown_length.close.assert_called()


if __name__ == "__main__":
    unittest.main()
