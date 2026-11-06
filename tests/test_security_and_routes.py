import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DSH017_DATA_DIR", tempfile.mkdtemp(prefix="dsh017-tests-"))

from app.security import validate_remote_url
from app.workspace_routes import _ws_scope_check, _ws_rule_lookup, _ws_auto_on_block, _ws_auto_guard
from app.bili_routes import bili_bp
from app.shorts_routes import shorts_bp
from app.chat_routes import chat_bp
from app.workspace_routes import workspace_bp
from flask import Flask


class SecurityTests(unittest.TestCase):
    def test_rejects_non_https_and_userinfo(self):
        self.assertFalse(validate_remote_url("http://i0.hdslb.com/a.jpg", ("hdslb.com",)))
        self.assertFalse(validate_remote_url("https://user@i0.hdslb.com/a.jpg", ("hdslb.com",)))

    def test_rejects_untrusted_host_and_suffix_spoof(self):
        self.assertFalse(validate_remote_url("https://example.com/a", ("hdslb.com",)))
        self.assertFalse(validate_remote_url("https://hdslb.com.evil.test/a", ("hdslb.com",)))

    @patch("app.security.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))])
    def test_rejects_private_dns_resolution(self, _dns):
        self.assertFalse(validate_remote_url("https://i0.hdslb.com/a.jpg", ("hdslb.com",)))

    @patch("app.security.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))])
    def test_accepts_allowlisted_public_host(self, _dns):
        self.assertTrue(validate_remote_url("https://i0.hdslb.com/a.jpg", ("hdslb.com",)))


class WorkspaceTests(unittest.TestCase):
    def test_filename_scope_rejects_traversal_and_paths(self):
        for value in ("../secret", "a/b", r"a\b", "/etc/passwd", "..", ""):
            self.assertFalse(_ws_scope_check(value), value)
        self.assertTrue(_ws_scope_check("notes.md"))

    @patch("app.workspace_routes._db_conn")
    def test_missing_rule_defaults_to_ask(self, db_conn):
        conn = db_conn.return_value
        conn.execute.return_value.fetchall.return_value = []
        self.assertEqual(_ws_rule_lookup("notes.md", "edit"), "ask")
        conn.close.assert_called_once()

    def test_auto_guard_is_thread_safe_and_trips(self):
        import app.workspace_routes as ws
        with ws._AUTO_GUARD_LOCK:
            ws._AUTO_BLOCK_STREAK = 0
            ws._AUTO_DOWNGRADED = False
        for _ in range(ws._AUTO_BLOCK_THRESHOLD):
            _ws_auto_on_block()
        self.assertTrue(_ws_auto_guard())
        with ws._AUTO_GUARD_LOCK:
            ws._AUTO_BLOCK_STREAK = 0
            ws._AUTO_DOWNGRADED = False


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(bili_bp)
        self.app.register_blueprint(shorts_bp)
        self.app.register_blueprint(chat_bp)
        self.app.register_blueprint(workspace_bp)
        self.client = self.app.test_client()

    def test_search_exception_returns_500_json_without_logger_nameerror(self):
        with patch("app.bili_routes.client.search", side_effect=RuntimeError("offline")):
            response = self.client.get("/api/search?q=test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], -500)

    def test_workspace_rejects_unknown_or_non_string_edit_modes(self):
        for mode in ("unexpected", " auto ", 123, None, []):
            response = self.client.post(
                "/api/workspace/apply_edit",
                json={"file_id": 1, "base_version": 1, "mode": mode},
            )
            self.assertEqual(response.status_code, 400, repr(mode))
        non_object = self.client.post("/api/workspace/apply_edit", json=["not", "an", "object"])
        self.assertEqual(non_object.status_code, 400)

    def test_workspace_rejects_invalid_edit_field_types_before_database_access(self):
        cases = [
            {"file_id": "1", "base_version": 1, "mode": "ask"},
            {"file_id": True, "base_version": 1, "mode": "ask"},
            {"file_id": 1, "base_version": "1", "mode": "ask"},
            {"file_id": 1, "base_version": 1, "old_str": [], "mode": "ask"},
            {"file_id": 1, "base_version": 1, "new_str": {}, "mode": "ask"},
        ]
        with patch("app.workspace_routes._db_conn") as db_conn:
            for payload in cases:
                response = self.client.post("/api/workspace/apply_edit", json=payload)
                self.assertEqual(response.status_code, 400, repr(payload))
            db_conn.assert_not_called()

    def test_shorts_rejects_invalid_page(self):
        response = self.client.get("/api/shorts?q=test&page=0")
        self.assertEqual(response.status_code, 400)

    def test_shorts_rejects_long_keyword(self):
        response = self.client.get("/api/shorts?q=" + "x" * 101)
        self.assertEqual(response.status_code, 400)

    def test_proxy_rejects_untrusted_url_before_network(self):
        with patch("app.bili_routes.client.s.get") as get:
            response = self.client.get("/api/proxy?u=http://127.0.0.1/admin")
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    def test_image_proxy_rejects_untrusted_url_before_network(self):
        with patch("app.bili_routes.client.s.get") as get:
            response = self.client.get("/api/img?u=https://example.com/image.png")
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    def test_x_proxy_accepts_valid_status_url_and_rewrites_host(self):
        mock_response = type("Response", (), {"json": lambda self: {"code": 404}})()
        with patch("app.chat_routes.client.s.get", return_value=mock_response) as get:
            self.client.get("/api/x?url=https://x.com/user/status/123")
        get.assert_called_once_with(
            "https://api.fxtwitter.com/user/status/123",
            timeout=(5, 15), allow_redirects=False
        )

    def test_x_proxy_rejects_non_x_url_before_network(self):
        with patch("app.chat_routes.client.s.get") as get:
            response = self.client.get("/api/x?url=https://example.com/user/status/123")
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    def test_x_proxy_rejects_x_url_with_extra_query(self):
        with patch("app.chat_routes.client.s.get") as get:
            response = self.client.get("/api/x?url=https://x.com/user/status/123?foo=bar")
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
