import unittest
from unittest.mock import patch

from flask import Flask

import app.chat_routes as chat_routes


class _JsonResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _ImageResponse:
    status_code = 200

    def __init__(self, chunks, headers=None):
        self.chunks = chunks
        self.headers = headers or {"Content-Type": "image/png"}
        self.closed = False
        self.chunk_size = None

    def iter_content(self, chunk_size):
        self.chunk_size = chunk_size
        return iter(self.chunks)

    def close(self):
        self.closed = True


class SummaryImageGuardTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(chat_routes.chat_bp)
        self.client = self.app.test_client()
        self.bili_info = _JsonResponse({
            "code": 0,
            "data": {
                "title": "test video",
                "desc": "description",
                "pic": "http://127.0.0.1/private-image",
            },
        })
        self.text_result = _JsonResponse({
            "choices": [{"message": {"content": "summary"}}]
        })

    def post_summary(self, vision=True):
        return self.client.post(
            "/api/summarize",
            json={"bvid": "BV1234567890", "vision": vision},
        )

    def test_rejects_non_public_cover_without_fetching_it(self):
        with patch.object(chat_routes.client.s, "get", return_value=self.bili_info) as get, \
             patch.object(chat_routes.client.s, "post", return_value=self.text_result):
            response = self.post_summary(vision=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 0)
        self.assertFalse(response.get_json()["visual_used"])
        # Only the fixed Bilibili metadata endpoint is fetched, never the cover URL.
        self.assertEqual(get.call_count, 1)
        self.assertIn("api.bilibili.com", get.call_args.args[0])

    def test_valid_cover_is_streamed_without_redirects_and_closed(self):
        cover = "https://i0.hdslb.com/bfs/archive/example.png"
        metadata = _JsonResponse({
            "code": 0,
            "data": {"title": "test video", "desc": "", "pic": cover},
        })
        image_response = _ImageResponse(
            [b"png-data"],
            {"Content-Type": "image/png", "Content-Length": "8"},
        )
        vision_result = _JsonResponse({
            "choices": [{"message": {"content": "cover description"}}]
        })
        with patch.object(chat_routes.client.s, "get",
                          side_effect=[metadata, image_response]) as get, \
             patch.object(chat_routes.client.s, "post",
                          side_effect=[vision_result, self.text_result]) as post:
            response = self.post_summary(vision=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["visual_used"])
        self.assertEqual(get.call_count, 2)
        image_call = get.call_args_list[1]
        self.assertEqual(image_call.args[0], cover)
        self.assertEqual(image_call.kwargs["timeout"], (5, 15))
        self.assertTrue(image_call.kwargs["stream"])
        self.assertFalse(image_call.kwargs["allow_redirects"])
        self.assertTrue(image_response.closed)
        self.assertGreaterEqual(post.call_count, 2)

    def test_summary_image_reader_rejects_non_image_content(self):
        response = _ImageResponse(
            [b"not an image"],
            {"Content-Type": "text/html", "Content-Length": "11"},
        )
        self.assertIsNone(chat_routes._read_summary_image(response))
        self.assertIsNone(response.chunk_size)

    def test_summary_image_reader_rejects_declared_oversize_before_reading(self):
        response = _ImageResponse(
            [b"ignored"],
            {
                "Content-Type": "image/png",
                "Content-Length": str(chat_routes._MAX_SUMMARY_IMAGE_BYTES + 1),
            },
        )
        self.assertIsNone(chat_routes._read_summary_image(response))
        self.assertIsNone(response.chunk_size)

    def test_summary_image_reader_stops_when_stream_exceeds_limit(self):
        response = _ImageResponse(
            [b"a" * 4, b"b" * 4],
            {"Content-Type": "image/webp"},
        )
        self.assertIsNone(chat_routes._read_summary_image(response, max_bytes=6))
        self.assertEqual(response.chunk_size, 64 * 1024)


if __name__ == "__main__":
    unittest.main()
