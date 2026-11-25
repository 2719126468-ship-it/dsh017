import tempfile
import unittest

from flask import Flask, jsonify

from app.auth import install_auth


class LoopbackCsrfBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-loopback-csrf-")
        self.write_calls = 0
        app = Flask(__name__)

        @app.post("/api/write")
        def write():
            self.write_calls += 1
            return jsonify({"ok": True})

        @app.get("/api/read")
        def read():
            return jsonify({"ok": True})

        install_auth(
            app,
            auth_token="normal-loopback-test-" + "n" * 40,
            admin_token="admin-loopback-test-" + "a" * 40,
            data_dir=self.temp.name,
            local_ips=[],
        )
        self.client = app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def _local_post(self, *, remote_addr="127.0.0.1", headers=None):
        return self.client.post(
            "/api/write",
            headers=headers or {},
            environ_overrides={"REMOTE_ADDR": remote_addr},
        )

    def test_loopback_cross_origin_write_is_rejected_for_ipv4_and_ipv6(self):
        for remote_addr in ("127.0.0.1", "::1"):
            with self.subTest(remote_addr=remote_addr):
                response = self._local_post(
                    remote_addr=remote_addr,
                    headers={"Origin": "https://attacker.example"},
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.get_json()["code"], -403)
        self.assertEqual(self.write_calls, 0)

    def test_loopback_cross_site_fetch_metadata_is_rejected(self):
        response = self._local_post(
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.write_calls, 0)

    def test_loopback_cross_origin_referer_is_rejected_when_origin_is_absent(self):
        response = self._local_post(
            headers={"Referer": "https://attacker.example/submit"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.write_calls, 0)

    def test_same_origin_loopback_browser_write_remains_allowed(self):
        response = self._local_post(
            headers={
                "Origin": "http://localhost",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.write_calls, 1)

    def test_loopback_non_browser_write_without_origin_metadata_remains_allowed(self):
        response = self._local_post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.write_calls, 1)

    def test_cross_site_loopback_read_is_not_blocked_by_write_guard(self):
        response = self.client.get(
            "/api/read",
            headers={"Sec-Fetch-Site": "cross-site"},
            environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
