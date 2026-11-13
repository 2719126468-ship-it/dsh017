import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DSH017_DATA_DIR", tempfile.mkdtemp(prefix="dsh017-bili-cache-tests-"))

from flask import Flask

from app.bili_routes import bili_bp, _search_cache_clear


class BilibiliSearchCacheTests(unittest.TestCase):
    def setUp(self):
        _search_cache_clear()
        self.app = Flask(__name__)
        self.app.register_blueprint(bili_bp)
        self.client = self.app.test_client()
        self.payload = {
            "code": 0,
            "data": {
                "numPages": 4,
                "numResults": 80,
                "result": [{"bvid": "BV1abc123", "title": "cached result"}],
            },
        }

    def tearDown(self):
        _search_cache_clear()

    def test_successful_search_page_is_cached(self):
        with patch("app.bili_routes.client.search", return_value=self.payload) as search, \
             patch("app.bili_routes.db_history_add"), \
             patch("app.bili_routes._metric_inc"):
            first = self.client.get("/api/search?q=landscape&page=2")
            second = self.client.get("/api/search?q=landscape&page=2")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.get_json(), second.get_json())
        search.assert_called_once_with("landscape", 2, "totalrank", "video", 0)

    def test_cache_key_includes_page_order_type_and_duration(self):
        with patch("app.bili_routes.client.search", return_value=self.payload) as search, \
             patch("app.bili_routes.db_history_add"), \
             patch("app.bili_routes._metric_inc"):
            self.client.get("/api/search?q=landscape&page=1")
            self.client.get("/api/search?q=landscape&page=1")
            self.client.get("/api/search?q=landscape&page=2")
            self.client.get("/api/search?q=landscape&page=1&order=click")
            self.client.get("/api/search?q=landscape&page=1&type=media_ft")
            self.client.get("/api/search?q=landscape&page=1&duration=2")

        self.assertEqual(search.call_count, 5)

    def test_expired_search_entry_is_requested_again(self):
        with patch("app.bili_routes.client.search", return_value=self.payload) as search, \
             patch("app.bili_routes.db_history_add"), \
             patch("app.bili_routes._metric_inc"), \
             patch("app.bili_routes.time.monotonic", side_effect=[100, 100, 150, 150]):
            self.client.get("/api/search?q=landscape&page=1")
            self.client.get("/api/search?q=landscape&page=1")

        self.assertEqual(search.call_count, 2)


if __name__ == "__main__":
    unittest.main()
