import unittest

from flask import Flask, jsonify, Response

from app.ui_theme import install_theme_support


class GlobalThemeSupportTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        install_theme_support(app)

        @app.route("/")
        def page():
            return "<!doctype html><html lang='zh-CN'><head><title>test</title></head><body><main>ready</main></body></html>"

        @app.route("/api")
        def api():
            return jsonify({"status": "ok"})

        @app.route("/api/html")
        def api_html():
            return Response("<html><head></head><body>upstream</body></html>", mimetype="text/html")

        self.client = app.test_client()

    def test_html_gets_global_theme_picker_and_security_headers(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="dsh017-global-themes"', body)
        self.assertIn('id="dsh017-theme-switcher"', body)
        self.assertIn('id="dsh017-theme-select"', body)
        self.assertIn('value="claude"', body)
        self.assertIn('value="chatgpt"', body)
        self.assertIn("X-Content-Type-Options", response.headers)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(
            response.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )
        self.assertEqual(
            response.headers["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

    def test_saved_claude_theme_is_applied_before_first_paint(self):
        self.client.set_cookie("dsh017_theme", "claude")
        response = self.client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn('<html data-dsh-theme="claude"', body)

    def test_saved_chatgpt_theme_is_applied_before_first_paint(self):
        self.client.set_cookie("dsh017_theme", "chatgpt")
        response = self.client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn('<html data-dsh-theme="chatgpt"', body)

    def test_invalid_theme_cookie_is_not_reflected_into_html(self):
        self.client.set_cookie("dsh017_theme", '"><script>alert(1)</script>')
        response = self.client.get("/")
        body = response.get_data(as_text=True)

        import re
        html_tag = re.search(r"<html\\b[^>]*>", body, re.IGNORECASE)
        self.assertIsNotNone(html_tag)
        self.assertNotIn("data-dsh-theme", html_tag.group(0))
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn('id="dsh017-theme-switcher"', body)

    def test_api_html_payload_is_not_rewritten(self):
        # An API may proxy an upstream HTML payload; it must never receive our UI script.
        response = self.client.get("/api/html")
        self.assertNotIn("dsh017-theme-switcher", response.get_data(as_text=True))

    def test_non_html_response_is_not_modified_but_is_hardened(self):
        response = self.client.get("/api")
        body = response.get_data(as_text=True)

        self.assertEqual(response.get_json(), {"status": "ok"})
        self.assertNotIn("dsh017-theme-switcher", body)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")


if __name__ == "__main__":
    unittest.main()
