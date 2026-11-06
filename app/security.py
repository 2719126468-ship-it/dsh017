"""Small security helpers for outbound URL handling."""
import ipaddress
import socket
from urllib.parse import urlsplit


def validate_remote_url(url, allowed_suffixes=()):
    """Accept HTTPS URLs on an explicit host allowlist and reject private IPs."""
    if not isinstance(url, str) or len(url) > 4096:
        return False
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        host = parsed.hostname.rstrip(".").lower()
        if not any(host == suffix or host.endswith("." + suffix)
                   for suffix in allowed_suffixes):
            return False
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            addresses = {ipaddress.ip_address(item[4][0])
                         for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        return bool(addresses) and all(
            addr.is_global and not addr.is_multicast and not addr.is_unspecified
            for addr in addresses
        )
    except (ValueError, OSError, socket.gaierror):
        return False



_SAFE_IMAGE_CONTENT_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
})


def safe_image_content_type(response):
    """Return a normalized allowlisted image MIME type, or None."""
    raw = response.headers.get("Content-Type", "")
    media_type = raw.split(";", 1)[0].strip().lower()
    return media_type if media_type in _SAFE_IMAGE_CONTENT_TYPES else None


def image_response_size_within_limit(response, max_bytes):
    """Reject invalid or oversized declared lengths; unknown lengths are streamed bounded."""
    raw = response.headers.get("Content-Length")
    if raw in (None, ""):
        return True
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return False
    return 0 <= size <= max_bytes


def iter_limited_response(response, max_bytes, chunk_size=32 * 1024):
    """Stream no more than max_bytes and always close the upstream response."""
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            remaining = max_bytes - total
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                yield chunk[:remaining]
                break
            total += len(chunk)
            yield chunk
    finally:
        response.close()
