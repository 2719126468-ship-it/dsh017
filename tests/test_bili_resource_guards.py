import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import app.bili_routes as bili_routes
import app.chat_routes as chat_routes


class JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class StreamResponse:
    def __init__(self, chunks=(), status_code=200, headers=None):
        self.chunks = list(chunks)
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    def iter_content(self, chunk_size):
        return iter(self.chunks)

    def close(self):
        self.closed = True


class BiliResourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(bili_routes.bili_bp)
        self.app.register_blueprint(chat_routes.chat_bp)
        self.client = self.app.test_client()

    def test_search_rejects_long_keyword_before_upstream_call(self):
        with patch.object(bili_routes.client, "search") as search:
            response = self.client.get("/api/search", query_string={"q": "x" * 101})
        self.assertEqual(response.status_code, 400)
        search.assert_not_called()

    def test_search_rejects_out_of_range_page_and_duration(self):
        with patch.object(bili_routes.client, "search") as search:
            page_response = self.client.get("/api/search?q=test&page=101")
            duration_response = self.client.get("/api/search?q=test&duration=99")
        self.assertEqual(page_response.status_code, 400)
        self.assertEqual(duration_response.status_code, 400)
        search.assert_not_called()

    def test_suggest_rejects_long_keyword_before_upstream_call(self):
        with patch.object(bili_routes.client.s, "get") as get:
            response = self.client.get("/api/suggest", query_string={"q": "x" * 101})
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    def test_hn_rejects_invalid_or_excessive_limit_before_upstream_call(self):
        with patch.object(chat_routes.client.s, "get") as get:
            invalid = self.client.get("/api/hn?limit=abc")
            excessive = self.client.get("/api/hn?limit=10000")
            zero = self.client.get("/api/hn?limit=0")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(excessive.status_code, 400)
        self.assertEqual(zero.status_code, 400)
        get.assert_not_called()

    def test_hn_fanout_is_bounded_by_requested_limit(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if url.endswith("topstories.json"):
                return JsonResponse([11, 22, 33, 44])
            return JsonResponse({"type": "story", "title": "Story"})

        with patch.object(chat_routes.client.s, "get", side_effect=fake_get):
            response = self.client.get("/api/hn?limit=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["stories"]), 2)
        self.assertEqual(len(calls), 3)

    def test_audio_rejects_untrusted_upstream_url_without_fetch(self):
        completed = subprocess.CompletedProcess(["ffmpeg"], 0, b"", b"")
        with patch("subprocess.run", return_value=completed), \
             patch.object(bili_routes.client, "get_audio_url",
                          return_value=("http://127.0.0.1/private", 1, "test")), \
             patch("app.bili_routes.validate_remote_url", return_value=False), \
             patch.object(bili_routes.client.s, "get") as get:
            response = self.client.get("/api/audio?bvid=BV1234567890")

        self.assertEqual(response.status_code, 502)
        get.assert_not_called()

    def test_audio_enforces_stream_size_limit_and_closes_upstream(self):
        upstream = StreamResponse(
            [b"1234", b"5678"],
            headers={"Content-Type": "audio/mp4"},
        )
        completed = subprocess.CompletedProcess(["ffmpeg"], 0, b"", b"")
        with patch.object(bili_routes, "_MAX_AUDIO_BYTES", 6), \
             patch("subprocess.run", return_value=completed), \
             patch.object(bili_routes.client, "get_audio_url",
                          return_value=("https://upos-sz-mirror.bilivideo.com/audio", 1, "test")), \
             patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch.object(bili_routes.client.s, "get", return_value=upstream) as get:
            response = self.client.get("/api/audio?bvid=BV1234567890")

        self.assertEqual(response.status_code, 413)
        self.assertTrue(upstream.closed)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])

    def test_audio_streams_validated_file_and_cleans_tempdir_after_response(self):
        upstream = StreamResponse(
            [b"m4a-data"],
            headers={"Content-Type": "audio/mp4", "Content-Length": "8"},
        )
        completed = subprocess.CompletedProcess(["ffmpeg"], 0, b"", b"")
        real_tempdir = tempfile.TemporaryDirectory
        created = {}

        def make_tempdir(*args, **kwargs):
            obj = real_tempdir(*args, **kwargs)
            created["path"] = obj.name
            return obj

        def fake_ffmpeg(command, **kwargs):
            if "-version" in command:
                return completed
            Path(command[-1]).write_bytes(b"mp3-data")
            return completed

        with patch("tempfile.TemporaryDirectory", side_effect=make_tempdir), \
             patch("subprocess.run", side_effect=fake_ffmpeg), \
             patch.object(bili_routes.client, "get_audio_url",
                          return_value=("https://upos-sz-mirror.bilivideo.com/audio", 1, "demo")), \
             patch("app.bili_routes.validate_remote_url", return_value=True), \
             patch.object(bili_routes.client.s, "get", return_value=upstream) as get:
            response = self.client.get("/api/audio?bvid=BV1234567890")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"mp3-data")
            self.assertTrue(Path(created["path"]).exists())
            response.close()

        self.assertTrue(upstream.closed)
        self.assertFalse(Path(created["path"]).exists())
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_video_rejects_untrusted_play_url_before_fetch(self):
        info = JsonResponse({
            "code": 0, "data": {"cid": 1, "title": "Demo"},
        })
        playurl = JsonResponse({
            "code": 0, "data": {"durl": [{"url": "http://127.0.0.1/private"}]},
        })
        with patch.object(bili_routes.client.s, "get", side_effect=[info, playurl]) as get, \
             patch.object(bili_routes.client, "sign", return_value={}), \
             patch("app.bili_routes.validate_remote_url", return_value=False):
            response = self.client.get("/api/video?bvid=BV1234567890")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(get.call_count, 2)

    def test_video_stream_disables_redirects_and_closes_upstream(self):
        info = JsonResponse({
            "code": 0, "data": {"cid": 1, "title": "Demo/video"},
        })
        playurl = JsonResponse({
            "code": 0, "data": {"durl": [{
                "url": "https://upos-sz-mirror.bilivideo.com/video.mp4",
            }]},
        })
        upstream = StreamResponse(
            [b"video-data"],
            headers={"Content-Type": "video/mp4", "Content-Length": "10"},
        )
        with patch.object(bili_routes.client.s, "get",
                          side_effect=[info, playurl, upstream]) as get, \
             patch.object(bili_routes.client, "sign", return_value={}), \
             patch("app.bili_routes.validate_remote_url", return_value=True):
            response = self.client.get("/api/video?bvid=BV1234567890")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"video-data")
            response.close()

        self.assertTrue(upstream.closed)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])


if __name__ == "__main__":
    unittest.main()
