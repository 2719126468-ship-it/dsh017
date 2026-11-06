import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def remote_get(self, path, **kwargs):
        return self.client.get(path, environ_base={"REMOTE_ADDR": "192.0.2.44"}, **kwargs)

    def remote_post(self, path, **kwargs):
        return self.client.post(path, environ_base={"REMOTE_ADDR": "192.0.2.44"}, **kwargs)

    def bearer(self, token):
        return {"Authorization": "Bearer " + token}

    def basic(self, token):
        value = base64.b64encode(("dsh017:" + token).encode()).decode()
        return {"Authorization": "Basic " + value}

    def test_host_loopback_is_exempt(self):
        response = self.client.get("/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(response.status_code, 200)

    def test_host_detected_lan_ip_is_exempt(self):
        response = self.client.get("/", environ_base={"REMOTE_ADDR": "192.168.50.10"})
        self.assertEqual(response.status_code, 200)

    def test_remote_without_token_is_rejected_with_basic_challenge(self):
        response = self.remote_get("/")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic realm=", response.headers["WWW-Authenticate"])
        self.assertEqual(response.get_json()["code"], -401)

    def test_forwarded_headers_cannot_bypass_auth(self):
        response = self.remote_get("/", headers={"X-Forwarded-For": "127.0.0.1"})
        self.assertEqual(response.status_code, 401)

    def test_normal_token_can_read_and_write(self):
        response = self.remote_get("/api/read", headers=self.bearer(self.auth_token))
        self.assertEqual(response.status_code, 200)
        response = self.remote_post("/api/write", headers=self.basic(self.auth_token))
        self.assertEqual(response.status_code, 200)

    def test_cross_origin_write_is_rejected_even_with_valid_token(self):
        response = self.remote_post(
            "/api/write",
            headers={**self.bearer(self.auth_token), "Origin": "https://attacker.example"},
        )
        self.assertEqual(response.status_code, 403)

    def test_sec_fetch_site_cross_site_write_is_rejected(self):
        response = self.remote_post(
            "/api/write",
            headers={**self.bearer(self.auth_token), "Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(response.status_code, 403)

    def test_same_origin_write_is_allowed(self):
        response = self.client.post(
            "/api/write",
            environ_base={"REMOTE_ADDR": "192.0.2.44"},
            headers={**self.bearer(self.auth_token), "Origin": "http://localhost"},
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_token_can_read_and_write(self):
        response = self.remote_post("/api/write", headers=self.bearer(self.admin_token))
        self.assertEqual(response.status_code, 200)

    def test_normal_token_cannot_change_workspace_rules(self):
        response = self.remote_post("/api/workspace/rules", headers=self.bearer(self.auth_token))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["code"], -403)

    def test_admin_token_can_change_workspace_rules(self):
        response = self.remote_post("/api/workspace/rules", headers=self.bearer(self.admin_token))
        self.assertEqual(response.status_code, 200)

    def test_normal_token_cannot_create_backup(self):
        response = self.remote_post("/api/backup", headers=self.bearer(self.auth_token))
        self.assertEqual(response.status_code, 403)

    def test_normal_token_can_read_backup_list(self):
        response = self.remote_get("/api/backup", headers=self.bearer(self.auth_token))
        self.assertEqual(response.status_code, 200)

    def test_normal_token_cannot_mutate_presets(self):
        response = self.remote_post("/api/preset/test", headers=self.bearer(self.auth_token))
        self.assertEqual(response.status_code, 403)

    def test_normal_token_cannot_enable_auto_edit(self):
        response = self.remote_post(
            "/api/workspace/apply_edit",
            headers=self.bearer(self.auth_token),
            json={"mode": "auto"},
        )
        self.assertEqual(response.status_code, 403)

    def test_normal_token_can_request_manual_confirmation_mode(self):
        response = self.remote_post(
            "/api/workspace/apply_edit",
            headers=self.bearer(self.auth_token),
            json={"mode": "ask"},
        )
        self.assertEqual(response.status_code, 200)

    def test_auto_edit_admin_check_cannot_be_bypassed_with_text_plain_json(self):
        response = self.remote_post(
            "/api/workspace/apply_edit",
            headers={"Authorization": "Bearer " + self.auth_token, "Content-Type": "text/plain"},
            data='{"mode":"auto"}',
        )
        self.assertEqual(response.status_code, 403)

    def test_local_host_can_perform_admin_operation_without_token(self):
        response = self.client.post(
            "/api/workspace/rules",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(response.status_code, 200)

    def test_tokens_are_generated_as_private_files(self):
        with tempfile.TemporaryDirectory(prefix="dsh017-auth-generated-") as directory:
            generated_app = Flask("generated-auth")
            with patch.dict(os.environ, {
                "DSH017_AUTH_TOKEN": "", "DSH017_ADMIN_TOKEN": ""
            }, clear=False):
                info = install_auth(generated_app, data_dir=directory, local_ips={"192.0.2.1"})
            paths = [Path(path) for path in info["token_files"]]
            self.assertTrue(all(p.is_file() for p in paths))
            self.assertTrue(all(len(p.read_text().strip()) >= 32 for p in paths))
            self.assertNotEqual(paths[0].read_text(), paths[1].read_text())
            self.assertEqual(paths[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(paths[1].stat().st_mode & 0o777, 0o600)


class LocalAddressTests(unittest.TestCase):
    def test_ipv4_mapped_ipv6_loopback_is_local(self):
        self.assertTrue(_client_ip_is_local("::ffff:127.0.0.1", set()))

    def test_invalid_remote_address_is_not_local(self):
        self.assertFalse(_client_ip_is_local("not-an-ip", {"127.0.0.1"}))


if __name__ == "__main__":
    unittest.main()
