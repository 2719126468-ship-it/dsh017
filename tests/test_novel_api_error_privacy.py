import unittest
from unittest.mock import patch

import novel_server


class NovelApiErrorPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.client = novel_server.app.test_client()

    def test_search_does_not_return_upstream_exception_details(self):
        with patch.object(
            novel_server.client,
            "search",
            side_effect=RuntimeError("internal host http://10.0.0.8/private"),
        ):
            response = self.client.get("/api/search?q=example")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], -500)
        self.assertNotIn("10.0.0.8", payload["message"])
        self.assertNotIn("/private", payload["message"])

    def test_book_and_chapter_errors_are_generic(self):
        with patch.object(
            novel_server.client,
            "book_info",
            side_effect=RuntimeError("private upstream detail"),
        ):
            book = self.client.get("/api/book?book_id=123")
        self.assertNotIn("private upstream detail", book.get_json()["message"])

        with patch.object(
            novel_server.client,
            "content",
            side_effect=RuntimeError("private chapter detail"),
        ):
            chapter = self.client.get("/api/content?item_id=456")
        self.assertNotIn("private chapter detail", chapter.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
