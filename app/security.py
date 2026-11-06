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
