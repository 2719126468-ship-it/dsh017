import os
import unittest
from unittest.mock import Mock, patch

import novel_server


def _response(payload):
    response = Mock()
    response.status_code = 200
    response.text = "mock response"
    response.json.return_value = payload
    return response


class NovelSearchProxyPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.client = novel_server.NovelClient()

    def test_legacy_http_proxies_are_disabled_by_default(self):
        official = _response({"data": {"search_tabs": []}})
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(novel_server.LEGACY_HTTP_SEARCH_PROXIES_ENV, None)
            with patch.object(self.client.s, "get", return_value=official) as get:
                with self.assertRaisesRegex(RuntimeError, "官方 HTTPS"):
                    self.client.search("private keyword")

        get.assert_called_once()
        self.assertEqual(
            get.call_args.args[0],
            "https://novel.snssdk.com/reading/bookapi/search/tab/v",
        )
        self.assertEqual(get.call_args.kwargs["params"]["query"], "private keyword")

    def test_non_truthy_value_does_not_enable_legacy_http_proxies(self):
        official = _response({"data": {"search_tabs": []}})
        with patch.dict(
            os.environ,
            {novel_server.LEGACY_HTTP_SEARCH_PROXIES_ENV: "false"},
        ):
            with patch.object(self.client.s, "get", return_value=official) as get:
                with self.assertRaises(RuntimeError):
                    self.client.search("private keyword")

        get.assert_called_once()
        self.assertTrue(get.call_args.args[0].startswith("https://"))

    def test_explicit_opt_in_keeps_legacy_proxy_compatibility(self):
        proxy = _response({
            "data": {
                "books": [{"book_id": "book-1", "book_name": "Example"}]
            }
        })
        with patch.dict(
            os.environ,
            {novel_server.LEGACY_HTTP_SEARCH_PROXIES_ENV: "1"},
        ):
            with patch.object(self.client.s, "get", return_value=proxy) as get:
                books = self.client.search("example")

        self.assertEqual(books[0]["book_id"], "book-1")
        get.assert_called_once()
        self.assertEqual(
            get.call_args.args[0],
            "http://101.35.133.34:5000/api/search",
        )
        self.assertEqual(get.call_args.kwargs["params"]["query"], "example")


if __name__ == "__main__":
    unittest.main()
