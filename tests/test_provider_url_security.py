import unittest
from unittest.mock import patch

from app.security import validate_provider_url
from app.provider_transport import validate_provider_url_syntax


class ProviderUrlSecurityTests(unittest.TestCase):
    def test_https_provider_with_public_dns_answer_is_allowed(self):
        with patch("app.provider_transport.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("8.8.8.8", 443)),
        ]):
            self.assertTrue(validate_provider_url("https://api.example.test/v1"))

    def test_private_or_mixed_dns_answers_are_rejected(self):
        answers = [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("192.168.1.10", 443)),
        ]
        with patch("app.provider_transport.socket.getaddrinfo", return_value=answers):
            self.assertFalse(validate_provider_url("https://api.example.test/v1"))

    def test_dns_resolution_failure_is_rejected(self):
        with patch("app.provider_transport.socket.getaddrinfo", side_effect=OSError("no DNS")):
            self.assertFalse(validate_provider_url("https://missing.example.test/v1"))

    def test_remote_http_is_rejected(self):
        self.assertFalse(validate_provider_url("http://api.example.test/v1"))

    def test_http_loopback_gateways_are_allowed(self):
        self.assertTrue(validate_provider_url("http://127.0.0.1:3425/v1"))
        self.assertTrue(validate_provider_url("http://[::1]:1234/v1"))
        with patch("app.provider_transport.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("127.0.0.1", 80)),
            (10, 1, 6, "", ("::1", 80, 0, 0)),
        ]):
            self.assertTrue(validate_provider_url("http://localhost:11434/v1"))

    def test_localhost_resolving_outside_loopback_is_rejected(self):
        with patch("app.provider_transport.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("8.8.8.8", 80)),
        ]):
            self.assertFalse(validate_provider_url("http://localhost:11434/v1"))

    def test_credentials_query_fragment_and_non_http_schemes_are_rejected(self):
        self.assertFalse(validate_provider_url("https://user:pass@example.com/v1"))
        self.assertFalse(validate_provider_url("https://example.com/v1?token=secret"))
        self.assertFalse(validate_provider_url("https://example.com/v1#fragment"))
        self.assertFalse(validate_provider_url("file:///etc/passwd"))

    def test_private_ip_literal_is_rejected(self):
        self.assertFalse(validate_provider_url("https://10.0.0.8/v1"))
        self.assertFalse(validate_provider_url("https://[fd00::1]/v1"))

    def test_saved_remote_provider_syntax_does_not_require_live_dns(self):
        with patch("app.provider_transport.socket.getaddrinfo", side_effect=OSError("offline")):
            self.assertTrue(validate_provider_url_syntax("https://api.example.test/v1"))
            self.assertFalse(validate_provider_url("https://api.example.test/v1"))

    def test_private_https_ip_literal_is_rejected_at_configuration_time(self):
        self.assertFalse(validate_provider_url_syntax("https://127.0.0.1/v1"))
        self.assertFalse(validate_provider_url_syntax("https://10.0.0.8/v1"))
        self.assertTrue(validate_provider_url_syntax("https://8.8.8.8/v1"))

    def test_https_private_dns_target_cannot_be_connected(self):
        with patch("app.provider_transport.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("10.0.0.8", 443)),
        ]):
            self.assertFalse(validate_provider_url("https://api.example.test/v1"))

    def test_ipv6_ula_and_link_local_dns_answers_are_rejected(self):
        for address in ("fc00::1", "fd12:3456::1", "fe80::1", "::ffff:127.0.0.1"):
            with self.subTest(address=address):
                answers = [(10, 1, 6, "", (address, 443, 0, 0))]
                with patch("app.provider_transport.socket.getaddrinfo", return_value=answers):
                    with self.assertRaisesRegex(ValueError, "非公网 DNS 地址"):
                        resolve_provider_target("https://api.example.test/v1")

    def test_mixed_public_ipv4_and_ipv6_ula_dns_answers_are_rejected(self):
        answers = [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (10, 1, 6, "", ("fd00::10", 443, 0, 0)),
        ]
        with patch("app.provider_transport.socket.getaddrinfo", return_value=answers):
            with self.assertRaisesRegex(ValueError, "非公网 DNS 地址"):
                resolve_provider_target("https://api.example.test/v1")

    def test_global_ipv6_provider_dns_answer_is_allowed_and_pinned(self):
        answers = [(10, 1, 6, "", ("2606:4700:4700::1111", 443, 0, 0))]
        with patch("app.provider_transport.socket.getaddrinfo", return_value=answers):
            target = resolve_provider_target("https://api.example.test/v1")
        self.assertEqual(target.address, "2606:4700:4700::1111")


if __name__ == "__main__":
    unittest.main()
