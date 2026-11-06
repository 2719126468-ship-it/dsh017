import unittest
from unittest.mock import patch

from flask import Flask

import novel_server
import app.bili_routes as bili_routes
from app.security import (
    image_response_size_within_limit,
    iter_limited_response,
    safe_image_content_type,
)


class FakeImageResponse:
    def __init__(self, chunks=None, headers=None, status_code=200):
        self.chunks = chunks or []
        self.headers = headers or {"Content-Type": "image/png"}
        self.status_code = status_code
        self.closed = False
        self.requested_chunk_size = None

    def iter_content(self, chunk_size):
        self.requested_chunk_size = chunk_size
        return iter(self.chunks)

    def close(self):
        self.closed = True


class ImageProxyHelperTests(unittest.TestCase):
    def test_only_allowlisted_image_mime_types_are_accepted(self):
        self.assertEqual(
            safe_image_content_type(
                FakeImageResponse(headers={"Content-Type": "Image/PNG; charset=binary"})
            ),
            "image/png",
        )
        self.assertIsNone(
            safe_image_content_type(
                FakeImageResponse(headers={"Content-Type": "text/html"})
            )
        )
        self.assertIsNone(
            safe_image_content_type(
                FakeImageResponse(headers={"Content-Type": "application/octet-stream"})
            )
        )

    def test_declared_content_length_is_validated(self):
        self.assertTrue(
            image_response_size_within_limit(
                FakeImageResponse(headers={"Content-Type": "image/png"}), 10
            )
        )
        self.assertTrue(
            image_response_size_within_limit(
                FakeImageResponse(headers={"Content-Length": "10"}), 10
            )
        )
        self.assertFalse(
            image_response_size_within_limit(
                FakeImageResponse(headers={"Content-Length": "11"}), 10
            )
        )
        self.assertFalse(
            image_response_size_within_limit(
                FakeImageResponse(headers={"Content-Length": "unknown"}), 10
            )
        )

    def test_unknown_length_stream_is_capped_and_closed(self):
        upstream = FakeImageResponse(
            [b"1234", b"5678"],
            {"Content-Type": "image/png"},
        )
        body = b"".join(iter_limited_response(upstream, 6, chunk_size=4))
        self.assertEqual(body, b"123456")
        self.assertTrue(upstream.closed)
        self.assertEqual(upstream.requested_chunk_size, 4)


class ImageProxyRouteTests(unittest.TestCase):
    def setUp(self):
        self.bili_app = Flask("bili-image-proxy-tests")
        self.bili_app.register_blueprint(bili_routes.bili_bp)
        self.bili_client = self.bili_app.test_client()
        self.novel_client = novel_server.app.test_client()

    def test_bili_image_proxy_rejects_html_and_oversized_images(self):
        html = FakeImageResponse(
            [b"<script>alert(1)</script>"],
            {"Content-Type": "text/html", "Content-Length": "25"},
        )
        with patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch.object(bili_routes.client.s, "get", return_value=html):
            response = self.bili_client.get(
                "/api/img?u=https://i0.hdslb.com/example",
                buffered=True,
            )
        self.assertEqual(response.status_code, 415)
        self.assertTrue(html.closed)

        large = FakeImageResponse(
            headers={
                "Content-Type": "image/png",
                "Content-Length": str(bili_routes._MAX_PROXY_IMAGE_BYTES + 1),
            }
        )
        with patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch.object(bili_routes.client.s, "get", return_value=large):
            response = self.bili_client.get(
                "/api/img?u=https://i0.hdslb.com/example",
                buffered=True,
            )
        self.assertEqual(response.status_code, 413)
        self.assertTrue(large.closed)

    def test_novel_image_proxy_rejects_html_and_caps_streams(self):
        html = FakeImageResponse(
            [b"<html>nope</html>"],
            {"Content-Type": "text/html"},
        )
        with patch("novel_server.validate_remote_url", return_value=True), \
             patch.object(novel_server.client.s, "get", return_value=html):
            response = self.novel_client.get(
                "/api/img?u=https://p6-tt.bytecdn.cn/example",
                buffered=True,
            )
        self.assertEqual(response.status_code, 415)
        self.assertTrue(html.closed)

        large = FakeImageResponse(
            headers={
                "Content-Type": "image/webp",
                "Content-Length": str(novel_server.NOVEL_MAX_IMAGE_BYTES + 1),
            }
        )
        with patch("novel_server.validate_remote_url", return_value=True), \
             patch.object(novel_server.client.s, "get", return_value=large):
            response = self.novel_client.get(
                "/api/img?u=https://p6-tt.bytecdn.cn/example",
                buffered=True,
            )
        self.assertEqual(response.status_code, 413)
        self.assertTrue(large.closed)


if __name__ == "__main__":
    unittest.main()
