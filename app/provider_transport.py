"""DNS-pinned HTTP transport for user-configured model providers.

Provider URLs are resolved and classified once per outbound request. The
validated numeric address is then used for the TCP connection while the
original hostname remains in the HTTP Host header and TLS SNI/certificate
verification. This closes the validation-to-connect DNS rebinding gap.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderTarget:
    scheme: str
    hostname: str
    port: int
    address: str
    path: str


def _is_public(address: ipaddress._BaseAddress) -> bool:
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_unspecified
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_reserved
    )


def resolve_provider_target(url: str) -> ProviderTarget:
    """Resolve and validate a provider URL, retaining the exact IP to connect."""
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise ValueError("供应商地址无效")
    if any(ord(char) < 32 or char.isspace() for char in url):
        raise ValueError("供应商地址包含非法空白字符")

    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").rstrip(".").lower()
        parsed_port = parsed.port
        port = parsed_port if parsed_port is not None else (443 if scheme == "https" else 80)
    except ValueError as error:
        raise ValueError("供应商地址格式无效") from error

    if (
        scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not 1 <= port <= 65535
    ):
        raise ValueError("供应商地址必须是无凭据、无查询参数的 HTTP(S) URL")

    # Convert internationalized hostnames before placing them in Host/SNI.
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        hostname = hostname.encode("idna").decode("ascii")

    # HTTP is permitted only for a literal loopback address or localhost.
    if scheme == "http" and hostname != "localhost":
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as error:
            raise ValueError("远程供应商必须使用 HTTPS") from error
        if not address.is_loopback:
            raise ValueError("HTTP 仅允许本机 loopback 地址")
        return ProviderTarget(scheme, hostname, port, str(address), parsed.path or "/")

    if scheme == "http" and hostname == "localhost":
        lookup_host = "localhost"
    else:
        if scheme != "https":
            raise ValueError("不支持的供应商协议")
        try:
            literal = ipaddress.ip_address(hostname)
            addresses = {literal}
        except ValueError:
            try:
                lookup_host = hostname.encode("idna").decode("ascii")
                results = socket.getaddrinfo(
                    lookup_host,
                    port,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                    proto=socket.IPPROTO_TCP,
                )
                addresses = {
                    ipaddress.ip_address(item[4][0].split("%", 1)[0])
                    for item in results
                }
            except (UnicodeError, OSError, ValueError) as error:
                raise ValueError("供应商域名无法解析到安全地址") from error

        if not addresses:
            raise ValueError("供应商域名没有可连接的地址")
        if not all(_is_public(address) for address in addresses):
            raise ValueError("供应商域名包含非公网 DNS 地址")
        address = sorted(addresses, key=lambda item: (item.version, int(item)))[0]
        return ProviderTarget(scheme, hostname, port, str(address), parsed.path or "/")

    # localhost must resolve exclusively to loopback, and the chosen IP is
    # pinned below rather than being resolved again by the HTTP client.
    try:
        results = socket.getaddrinfo(
            lookup_host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        addresses = {
            ipaddress.ip_address(item[4][0].split("%", 1)[0])
            for item in results
        }
    except (OSError, ValueError) as error:
        raise ValueError("localhost 无法解析") from error
    if not addresses or not all(address.is_loopback for address in addresses):
        raise ValueError("localhost 必须仅解析到 loopback 地址")
    address = sorted(addresses, key=lambda item: (item.version, int(item)))[0]
    return ProviderTarget(scheme, hostname, port, str(address), parsed.path or "/")



def validate_provider_url_syntax(url: str) -> bool:
    """Check provider URL syntax without requiring DNS to be online.

    Public-address classification is deliberately deferred until the exact
    outbound request is made, so saved providers remain visible while offline.
    """
    if not isinstance(url, str) or not url or len(url) > 2048:
        return False
    if any(ord(char) < 32 or char.isspace() for char in url):
        return False
    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port
        if (
            scheme not in {"http", "https"}
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            return False
        if scheme == "https":
            try:
                literal = ipaddress.ip_address(hostname)
            except ValueError:
                hostname.encode("idna")
                return True
            return _is_public(literal)
        if hostname == "localhost":
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False
    except (UnicodeError, ValueError):
        return False

def validate_provider_url(url: str) -> bool:
    """Boolean compatibility wrapper for provider configuration validation."""
    try:
        resolve_provider_target(url)
        return True
    except (TypeError, ValueError, OSError):
        return False


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, target: ProviderTarget, connect_timeout: float, read_timeout: float):
        super().__init__(target.hostname, target.port, timeout=connect_timeout)
        self._pinned_address = target.address
        self._read_timeout = read_timeout

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_address, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock.settimeout(self._read_timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, target: ProviderTarget, connect_timeout: float, read_timeout: float):
        context = ssl.create_default_context()
        super().__init__(
            target.hostname,
            target.port,
            timeout=connect_timeout,
            context=context,
        )
        self._pinned_address = target.address
        self._read_timeout = read_timeout

    def connect(self):
        raw_socket = socket.create_connection(
            (self._pinned_address, self.port),
            self.timeout,
            self.source_address,
        )
        try:
            # Keep the original hostname for both SNI and certificate checking.
            self.sock = self._context.wrap_socket(
                raw_socket,
                server_hostname=self.host,
            )
            self.sock.settimeout(self._read_timeout)
        except Exception:
            raw_socket.close()
            raise


class ProviderResponse:
    """Small requests-like response wrapper around http.client.HTTPResponse."""

    def __init__(self, connection, response):
        self._connection = connection
        self._response = response
        self.status_code = response.status
        self.headers = response.headers
        self._closed = False

    def _read_bounded(self, max_bytes: int) -> bytes:
        try:
            data = self._response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("供应商响应超过大小限制")
            return data
        finally:
            self.close()

    @property
    def text(self) -> str:
        return self._read_bounded(64 * 1024).decode("utf-8", "replace")

    def json(self):
        raw = self._read_bounded(2 * 1024 * 1024)
        return json.loads(raw.decode("utf-8"))

    def iter_content(self, chunk_size=None, decode_unicode=False):
        size = chunk_size or 64 * 1024
        try:
            while True:
                chunk = self._response.read(size)
                if not chunk:
                    break
                if decode_unicode:
                    yield chunk.decode("utf-8", "replace")
                else:
                    yield chunk
        finally:
            self.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._response.close()
        finally:
            self._connection.close()


def provider_request(method, url, headers=None, json_body=None, timeout=(5, 60)):
    """Make a direct, non-redirecting request to a DNS-pinned provider address."""
    target = resolve_provider_target(url)
    if isinstance(timeout, (tuple, list)):
        connect_timeout = float(timeout[0])
        read_timeout = float(timeout[1])
    else:
        connect_timeout = read_timeout = float(timeout)
    if connect_timeout <= 0 or read_timeout <= 0:
        raise ValueError("供应商请求超时必须大于0")

    request_headers = {
        "User-Agent": "DSH-017/0.1",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    for key, value in (headers or {}).items():
        if key.lower() not in {
            "host", "connection", "content-length", "transfer-encoding",
            "proxy-authorization", "proxy-connection",
        }:
            request_headers[key] = str(value)

    body = None
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if not any(key.lower() == "content-type" for key in request_headers):
            request_headers["Content-Type"] = "application/json; charset=utf-8"
        request_headers["Content-Length"] = str(len(body))

    connection_class = (
        _PinnedHTTPSConnection if target.scheme == "https"
        else _PinnedHTTPConnection
    )
    connection = connection_class(target, connect_timeout, read_timeout)
    try:
        connection.request(
            str(method).upper(),
            target.path,
            body=body,
            headers=request_headers,
        )
        response = connection.getresponse()
        return ProviderResponse(connection, response)
    except Exception:
        connection.close()
        raise
