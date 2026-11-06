import base64
import os
import tempfile
import unittest
from pathlib import Path

from flask import Flask, jsonify

from app.auth import install_auth, _client_ip_is_local


class RemoteAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="dsh017-auth-")
        self.auth_token = "normal-" + "n" * 48
        self.admin_token = "admin-" + "a" * 48
        self.app = Flask(__name__)
        self.app.add_url_rule("/", "home", lambda: jsonify(ok=True))
        self.app.add_url_rule("/api/read", "read", lambda: jsonify(ok=True), methods=["GET"])
        self.app.add_url_rule("/api/write", "write", lambda: jsonify(ok=True), methods=["POST"])
        self.app.add_url_rule(
            "/api/workspace/rules", "rules", lambda: jsonify(ok=True),
            methods=["GET", "POST", "DELETE"]
        )
        self.app.add_url_rule("/api/backup", "backup", lambda: jsonify(ok=True), methods=["GET", "POST"])
        self.app.add_url_rule(
            "/api/preset/<name>", "preset", lambda name: jsonify(ok=True),
            methods=["GET", "POST", "DELETE"]
        )
        self.app.add_url_rule(
            "/api/workspace/apply_edit", "apply_edit",
            lambda: jsonify(ok=True), methods=["POST"]
        )
        install_auth(
            self.app,
            auth_token=self.auth_token,
            admin_token=self.admin_token,
            data_dir=self.tmp.name,
            local_ips={"192.168.50.10"},
        )
        self.cl¶»§q«^