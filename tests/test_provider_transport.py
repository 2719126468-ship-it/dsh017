import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock, patch

from app.provider_transport import (
    ProviderTarget,
    ProviderResponse,
    _PinnedHTTPSConnection,
    _PinnedHTTPConnection,
    provider_request,
    resolve_provider_target,
)


class ProviderTransportTests(unittest.TestCase):
    def test_https_dns_result_is_retained_as_connection_target(self):
        with patch("app.provider_transport.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("8.8.8.8", 443)),
        ]):
            target = resolve_provider_target("https://api.example.test/v1")
        self.assertEqual(target.hostname, "api.example.test")
        self.assertEqual(target.address, "8.8.8.8")
        self.assertEqual(target.path, "/v1")

    def test_http_connection_uses_pinned_ip_not_provider_hostname(self):
        target = ProviderTarget(
            scheme="http",
            hostname="localhost",
            port=11434,
            address="127.0.0.1",
            path="/v1",
        )
        fake_socket = Mock()
        connection = _PinnedHTTPConnection(target, 5, 15)
        with patch("app.provider_transport.socket.create_connection", return_value=fake_socket) as connect:
            connection.connect()
        connect.assert_called_once_with(("127.0.0.1", 11434), 5, None)
        fake_socket.settimeout.assert_called_once_with(15)
        connection.close()

    def test_https_connection_pins_ip_and_keeps_hostname_for_tls_sni(self):
        target = ProviderTarget(
            scheme="https",
            hostname="api.example.test",
            port=443,
            address="8.8.8.8",
            path="/v1",
        )
        raw_socket = Mock()
        tls_socket = Mock()
        context = Mock()
        context.wrap_socket.return_value = tls_socket
        with patch("app.provider_transport.ssl.create_default_context", return_value=context), \
             patch("app.provider_transport.socket.create_connection", return_value=raw_socket) as connect:
            connection = _PinnedHTTPSConnection(target, 5, 30)
            connection.connect()

        connect.assert_called_once_with(("8.8.8.8", 443), 5, None)
        context.wrap_socket.assert_called_once_with(
            raw_socket,
            server_hostname="api.example.test",
        )
        tls_socket.settimeout.assert_called_once_with(30)
        connection.close()

    def test_stream_reader_prefers_read1_to_avoid_buffering_sse_chunks(self):
        class ChunkResponse:
            status = 200
            headers = {}

            def __init__(self):
                self.chunks = [b"data: one\\n\\n", b"data: two\\n\\n", b""]
                self.read_calls = 0
                self.read1_calls = 0
                self.closed = False

            def read(self, _size):
                self.read_calls += 1
                raise AssertionError("read() would wait to fill the requested buffer")

            def read1(self, _size):
                self.read1_calls += 1
                return self.chunks.pop(0)

            def close(self):
                self.closed = True

        response = ChunkResponse()
        connection = Mock()
        stream = __import__(
            "app.provider_transport", fromlist=["ProviderResponse"]
        ).ProviderResponse(connection, response)
        self.assertEqual(
            list(stream.iter_content(chunk_size=64 * 1024)),
            [b"data: one\\n\\n", b"data: two\\n\\n"],
        )
        self.assertEqual(response.read_calls, 0)
        self.assertEqual(response.read1_calls, 3)
        self.assertTrue(response.closed)
        connection.close.assert_called_once()

    def test_provider_request_sends_json_to_pinned_loopback_server(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                self.server.received = json.loads(self.rfile.read(length).decode("utf-8"))
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/models")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.server.model_hits += 1
                body = b'{"data":[{"id":"local-model"}]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.model_hits = 0
        server.received = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_port
        try:
            response = provider_request(
                "POST",
                base + "/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                json_body={"model": "local-model", "stream": True},
                timeout=(2, 2),
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"ok": True})
            self.assertEqual(server.received, {
                "model": "local-model",
                "stream": True,
            })

            redirect = provider_request("GET", base + "/redirect", timeout=(2, 2))
            self.assertEqual(redirect.status_code, 302)
            redirect.close()
            self.assertEqual(server.model_hits, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


    def test_provider_request_rejects_header_injection_before_sending(self):
        class Handler(BaseHTTPRequestHandler):
            hits = 0

            def do_GET(self):
                type(self).hits += 1
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_port
        try:
            with self.assertRaises(ValueError):
                provider_request(
                    "GET",
                    base + "/models",
                    headers={"Authorization": "Bearer safe\r\nX-Injected: yes"},
                    timeout=(2, 2),
                )
            self.assertEqual(Handler.hits, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_provider_response_text_and_json_reads_are_bounded_and_closed(self):
        class FakeResponse:
            status = 200
            headers = {}

            def __init__(self, payload):
                self.payload = payload
                self.closed = False

            def read(self, size):
                return self.payload[:size]

            def close(self):
                self.closed = True

        for payload, accessor in (
            (b"x" * (64 * 1024 + 1), "text"),
            (b" " * (2 * 1024 * 1024 + 1), "json"),
        ):
            with self.subTest(accessor=accessor):
                upstream = FakeResponse(payload)
                connection = Mock()
                response = ProviderResponse(connection, upstream)
                with self.assertRaisesRegex(ValueError, "超过大小限制"):
                    getattr(response, accessor)
                self.assertTrue(upstream.closed)
                connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
