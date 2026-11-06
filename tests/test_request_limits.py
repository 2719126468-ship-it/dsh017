import unittest
from unittest.mock import patch

from flask import Flask

import novel_server
from app.chat_ui import chat_ui_bp, _MAX_CHAT_CHARS, _MAX_CHAT_MESSAGES


class NovelInputLimitTests(unittest.TestCase):
    def setUp(self):
        self.client = novel_server.app.test_client()

    def test_search_rejects_long_keywords_and_invalid_pages(self):
        with patch.object(novel_server.client, "search") as search:
            long_query = self.client.get(
                "/api/search",
                query_string={"q": "x" * 101},
            )
            bad_page = self.client.get("/api/search?q=test&page=abc")
            high_page = self.client.get("/api/search?q=test&page=101")

        self.assertEqual(long_query.status_code, 400)
        self.assertEqual(bad_page.status_code, 400)
        self.assertEqual(high_page.status_code, 400)
        search.assert_not_called()

    def test_book_and_chapter_identifiers_have_length_limits(self):
        with patch.object(novel_server.client, "book_info") as book_info, \
             patch.object(novel_server.client, "content") as content:
            book = self.client.get(
                "/api/book",
                query_string={"book_id": "b" * 129},
            )
            chapter = self.client.get(
                "/api/content",
                query_string={"item_id": "c" * 129},
            )

        self.assertEqual(book.status_code, 400)
        self.assertEqual(chapter.status_code, 400)
        book_info.assert_not_called()
        content.assert_not_called()


class ChatInputLimitTests(unittest.TestCase):
    def setUp(self):
        app = Flask("chat-input-limits")
        app.register_blueprint(chat_ui_bp)
        self.client = app.test_client()

    def test_chat_rejects_non_array_messages(self):
        with patch("app.chat_ui.provider_request") as post:
            response = self.client.post("/api/chat", json={"messages": "not-a-list"})
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    def test_chat_rejects_non_object_message_entries(self):
        with patch("app.chat_ui.provider_request") as post:
            response = self.client.post("/api/chat", json={"messages": ["bad-entry"]})
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    def test_chat_rejects_more_than_message_limit(self):
        messages = [{"role": "user", "content": "hello"}] * (_MAX_CHAT_MESSAGES + 1)
        with patch("app.chat_ui.provider_request") as post:
            response = self.client.post("/api/chat", json={"messages": messages})
        self.assertEqual(response.status_code, 413)
        post.assert_not_called()

    def test_chat_rejects_context_above_character_limit(self):
        message = {"role": "user", "content": "x" * (_MAX_CHAT_CHARS + 1)}
        with patch("app.chat_ui.provider_request") as post:
            response = self.client.post("/api/chat", json={"messages": [message]})
        self.assertEqual(response.status_code, 413)
        post.assert_not_called()

    def test_chat_counts_workspace_context_towards_limit(self):
        message = {"role": "user", "content": "x" * 100_000}
        workspace = {"name": "notes.md", "file_id": 1, "version": 1,
                     "content": "y" * 100_000}
        with patch("app.chat_ui.provider_request") as post:
            response = self.client.post(
                "/api/chat",
                json={"messages": [message], "workspace": workspace},
            )
        self.assertEqual(response.status_code, 413)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
