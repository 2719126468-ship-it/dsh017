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
  ¶»§q«^